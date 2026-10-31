# Rankings: from offline scripts to an online pipeline

Today an experiment is a hand-written `POST /api/jobs` payload pointing at a file path on disk
(`/app/reports/models/regime-scores.json`). That is how experiments 1–3 were run, and it produced two
real errors: a same-bar execution bug and a provenance field pointing at a dataset version that no
longer exists. This page describes the system that replaces the payload-with-a-path: an **analysis**
that runs in the product, produces an **artifact**, registers a **ranking source**, and is consumed by
the simulation as a first-class reference.

The goal is reproducibility, not convenience: every number in a report must be re-derivable from the
UI by someone who has never seen the script.

---

## 1. Concepts

```
Analysis ──run──▶ AnalysisRun ──produces──▶ Artifact ──registered as──▶ RankingSource
   │                                                                        │
   ├─ params schema (drives the UI form)                                    │
   └─ input dataset (versioned, pinned)                     SimulationRun ───┘
                                                                │
                                                                └─ optionally trains models (cached)
```

| Concept | What it is | Where it lives |
|---|---|---|
| **Analysis** | a named, parameterised computation: `regime_score`, `ic_weights`, `scorecard_train`, `factor_scan` | `analyses` table + a Python implementation in `app/analysis/methods/` |
| **AnalysisRun** | one execution of an analysis with concrete parameters and a pinned dataset version | `analysis_runs` table + a `jobs` row |
| **Artifact** | the immutable output: a score table (parquet) or a model (json/onnx) | object storage, content-addressed |
| **RankingSource** | a published artifact that a simulation may rank by | `ranking_sources` table |
| **ModelArtifact** | a trained model for one period, keyed by a fingerprint so training is idempotent | `model_artifacts` table + object storage |

Why four layers instead of one: re-running an analysis must not silently change past experiments
(`AnalysisRun` is history), and a simulation must not depend on a mutable file (`RankingSource` is a
frozen snapshot). Model training is separated because it happens *inside* a simulation run and must be
cacheable.

---

## 2. Analysis methods

An analysis is code plus a declared contract:

```python
@dataclass
class MethodSpec:
    name: str                       # "regime_score"
    display_name: str               # "regime 打分（MA60 切换动量/反转）"
    description: str
    params_model: type[BaseModel]   # pydantic → JSON schema → UI form
    output_kind: str                # "score_table" | "model"
    needs: list[str]                # required columns / factor codes, checked before running
```

Registered methods (P0–P2):

| Method | Params | Output | Replaces script |
|---|---|---|---|
| `regime_score` | `ma_window`, `horizon`, `benchmark`, `factors` | score_table | `scripts/regime_score.py` |
| `ic_weights` | `lookback`, `horizon`, `factors` | score_table | inline in experiment 2 |
| `constant_pool` | `codes`, `as_of` | score_table | `frozen-scores.json` / `random50-*.json` |
| `scorecard_train` | `label`, `factors`, `bins`, `alpha`, `train_window` | model | `scripts/scorecard.py` |
| `factor_scan` (P2) | `factor`, `horizon`, `buckets` | score_table + report | one-off notebooks |

Each method is a pure function over a `DatasetHandle` and a `Session`:

```python
def run(db: Session, dataset: DatasetHandle, params: BaseModel, progress) -> ArtifactDraft
```

The method never writes to storage or to the database itself; it returns a draft, and the runner
handles artifact upload, hashing, registration and provenance. That keeps methods testable without a
storage backend, and keeps the audit trail in one place.

---

## 3. Artifacts

### 3.1 Score tables — parquet, not JSON

```
trade_date (date) | ts_code (str) | score (float32) | rank_hint (int32, optional)
```

- partitioned by month: `month=2025-07/part-000.parquet`;
- a `card.json` next to it: `{schema_version, kind, method, params, dataset_ref, coverage, row_count, columns, created_by}`;
- a dataset-level snapshot at 3.4M rows is ~40 MB parquet vs ~66 MB JSON, and lookups are by date row
  group instead of parsing the whole file into memory;
- the reader (`ScoreTableSource`) resolves "the latest score on or before `day`" in one query, which is
  the same carry-forward semantics the JSON provider already used.

The existing `regime-scores.json` (66 MB) and the frozen/random pool tables become P0 migrations.

### 3.2 Models — parameters, never pickle

```json
{
  "schema_version": 1,
  "scorer": "linear_woe",
  "label": {"kind": "benchmark", "horizon": 20, "benchmark": "000300.SH"},
  "trained_for_period": {"kind": "month", "value": "2025-07"},
  "inputs": {"factors": ["liq_turn_std_6M", "mom_20d"], "columns": ["close", "turnover_rate"]},
  "universe": {"exclude_st": true, "min_price": 2.0},
  "intercept": -0.158,
  "factors": [{"code": "liq_turn_std_6M", "coef": 0.915, "bins": [...], "woe": [...]}],
  "dataset": {"name": "scorecard-training-20d-bench", "version": 2, "manifest_sha256": "..."},
  "metrics": {"train_auc": 0.627, "target_period_auc": 0.505}
}
```

`scorer` names an adapter in a registry (`linear_woe`, `linear_raw`, later `onnx:<path>`). Pickle is
rejected: loading it is arbitrary code execution, and it makes the artifact unauditable.

The current `reports/models/expanding-bench20/YYYY-MM.json` files already have this shape (they carry
`intercept`, `factors[{code,coef,bins,woe}]`, `label_kind`, `horizon`, `metrics`) — P1 adds
`schema_version`, `inputs`, `universe` and `dataset_ref`, and moves them out of the image.

### 3.3 Storage layout

```
rankings/<source_id>/<sha256>/card.json
rankings/<source_id>/<sha256>/scores/             # parquet partitions
models/<fingerprint>/<sha256>/model.json
```

Published artifacts are immutable; a change means a new `source_id` (or a new model fingerprint).
This mirrors the dataset rules already in place (new dates = new version, draft → publish → frozen).

---

## 4. Model cache: training inside a simulation, skipped when it exists

A model-driven run declares a retraining cadence:

```json
{"mode": "model", "ranking_source_id": "scorecard-bench20", "retrain": "monthly" | "weekly" | "none"}
```

For each period `P` in the run window:

```
fingerprint = sha256(dataset.name, dataset.version, manifest_sha256,
                     sorted(factors), hyperparams, label, horizon, P)
if model_artifacts[fingerprint] exists and is published:
    reuse it                                   → provenance.model_cache = "hit"
else:
    train via scorecard_train (same code the offline script uses)
    store as model_artifacts[fingerprint]      → provenance.model_cache = "trained"
```

| Situation | Behaviour |
|---|---|
| `retrain=monthly`, models exist for every month | zero training, run starts immediately |
| `retrain=weekly`, monthly models exist | 3 new models per month trained on demand |
| `retrain=none` | no training at all; missing model for a period is an **error**, not a fallback |
| dataset version changed | every fingerprint changes → full retrain (correct: the data changed) |
| factor set or hyperparams changed | same — fingerprint changes |

The run's provenance records both the resolved model fingerprint per period and the hit/train mix, so
"which model produced this month's picks" is answerable from the run record alone.

---

## 5. Tradability: one module, three call sites

Experiment 3's +43.81 points were measured without any execution constraints. The rules are the same
everywhere, so they live in one module (`app/core/market/tradability.py`) and are applied at three
points: pool construction, buy, sell.

| Case | Effect |
|---|---|
| suspended today (no daily row) | not eligible to buy; a holding stays, valued at its last close |
| no data yet / first day of listing | not eligible |
| limit-up at open (buy side) | cannot buy; retry next tradable day |
| limit-down at open (sell side) | cannot sell; retry next tradable day |
| delisting period (`name` contains 退) | not eligible; force close on the last tradable day |
| ST | excluded from the pool (already in `model_runner`, must move here) |
| price below floor | excluded |

The pool keeps the ranking order untouched; tradability only filters and defers. That separation
matters: "ranked 3rd but unbuyable" is information (it tells you the strategy's turnover is
constrained), not a reason to renumber the pool.

---

## 6. Ranking resolution at runtime

```
RankingService.resolve(source_id, day) -> list[Ranked]
```

| kind | resolution |
|---|---|
| `score_table` | latest partition ≤ day, sorted desc |
| `model` | `retrain` policy → model fingerprint for the period containing `day` → score today's cross-section |
| `factor_combo` | factor engine evaluates the expression, weights applied |
| `external` (P2) | HTTP call to a registered service, response normalised |

All sources yield the same `Ranked(ts_code, score, rank)` list, so `policy_runner`,
`ModelRankingProvider`'s consumers and the mechanical runner stay untouched. `RankingSource` also
carries `universe` and `inputs`, which the validator and the pool builder both read.

---

## 7. API

```
GET    /api/analyses                      methods: name, display_name, params schema, output kind
POST   /api/analyses/{name}/runs          run it: {params, dataset, version} → job id
GET    /api/analyses/runs                 history: status, params, artifact, source id
GET    /api/analyses/runs/{id}            detail + progress + error

GET    /api/rankings                      published sources: coverage, dataset_ref, status
GET    /api/rankings/{id}                 card + validation report
GET    /api/rankings/{id}/preview?date=   top 20 with per-factor contribution
POST   /api/rankings/{id}/validate        re-run the four checks
POST   /api/rankings/{id}/deprecate

GET    /api/models                        model artifacts: fingerprint, period, metrics, cache state
```

`POST /api/jobs` with `type=simulation` accepts `ranking_source_id` and **no path fields**. The
`dataset`, `dataset_version`, `label`, `horizon` fields are removed from the payload and filled from
the source's `dataset_ref` — the mechanism that produced `dataset_version: 1` by hand is deleted, not
guarded.

---

## 8. Validation: four gates, stored as a report

Run at registration and on demand:

1. **schema** — required fields, known `schema_version`/`scorer`, numeric types;
2. **inputs available** — every `inputs.factors` code exists in `factor_definitions` with panel
   coverage; every `inputs.columns` exists in the market tables;
3. **coverage** — artifact date range vs the simulation window it will be used for (warning, not an
   error: a short artifact is legal, an absent one is not);
4. **smoke equivalence** — recompute scores online for 5 sampled dates and compare with the artifact
   (tolerance 1e-6). This is the gate that guarantees the online path has not drifted from the offline
   one; without it, every comparison across experiments is suspect.

A source that fails gates 1, 2 or 4 stays `draft` and cannot be referenced by a simulation.

---

## 9. UI

**Analyses page** (`/analyses`)
- list of methods with a one-line description and their last run;
- "Run" opens a form generated from `params_model.json_schema()` + a dataset/version picker;
- run history table: params, dataset version, duration, artifact size, resulting source, status;
- failure shows the method's error and the validation report.

**Rankings page** (`/rankings`)
- cards: name, kind, coverage bar, dataset version, status badge, `stale` warning if its dataset was
  deprecated;
- detail: `card.json` fields, per-factor importance (models), preview of the top 20 on a chosen date;
- actions: validate, deprecate, "run a simulation with this" (prefills the run dialog).

**Run dialog** (existing Simulation page, extended)
- pool source: dropdown of published sources (grouped by kind), with coverage shown;
- trade rule: `组合策略`（default, pool → policy）or `机械 Top-N`;
- retrain: `monthly / weekly / none` (only for model sources);
- run name + description;
- no dataset, no path, no factor fields.

---

## 10. Migration of existing assets

| Asset | Destination |
|---|---|
| `reports/models/expanding/`, `expanding-bench20/`, `expanding-rel20/` | `models/` in object storage, registered as model artifacts with fingerprints; `STOCK_MODELS_DIR` stays only as a dev fallback |
| `regime-scores.json` (66 MB) | parquet, source `regime-ma60-v1` |
| `frozen-scores.json`, `random50-{11,12,13}.json` | parquet, sources `pool-frozen-20240603`, `pool-random-{11,12,13}` |
| `ic-weights/lookback60.json` | parquet, source `ic60-rev-v1` (marked deprecated: experiment 2 was invalidated) |
| existing `simulation_runs.provenance.ranking` (= path strings) | rewritten to `{source_id, artifact_sha256}` where the file still exists |

---

## 11. Compatibility and failure modes

| Concern | Handling |
|---|---|
| artifact loss (happened once already, with the dataset objects) | **not backed up, by design**: an artifact is derived — code + pinned dataset regenerate it, and `regime_score` over 28 months takes ~40 s. The source keeps its `artifact_sha256`, so a recomputed artifact whose hash differs is a signal that an input changed, not a fault to paper over. Recovery: re-run the analysis with the same parameters and dataset version (below) |
| method code changes | `AnalysisRun` records `code_version` (git sha at runtime); an old source stays reproducible because the artifact is frozen |
| long analyses (3.4M-row exports) | run as a job with progress; the UI polls; cancellation is allowed between partitions |
| big score tables | parquet partition per month; preview reads one row group |
| artifact upload security | uploads go through the API with size/type limits; `scorer` names must be in the registry; no arbitrary pickle |
| provenance drift | `dataset_ref` comes from the source, never from the request body |

---

## 12. Roadmap and acceptance criteria

| Phase | Scope | Done when |
|---|---|---|
| **P0** | `analyses`, `analysis_runs`, `ranking_sources` tables; `regime_score` + `constant_pool` methods; parquet artifacts; `RankingService` for `score_table`; job payload takes `ranking_source_id` | running "regime 打分" from the UI reproduces experiment 3's **+43.81** exactly (same source, same window, same trades) |
| **P1** | `model_artifacts` + fingerprint cache + `retrain` semantics; migrate `expanding-bench20`; smoke gate | `retrain=monthly` on the 15-month window reports "N reused / M trained" and reproduces experiment 1's **+2.50** |
| **P2** | `tradability` module wired into pool/buy/sell (limit-up/down, new listings, delisting); rerun experiment 3 | the +43.81 becomes a number produced under realistic execution, and the delta is written into the report |
| **P3** | `factor_combo`, `onnx` scorer, external ranking service | a new factor combination can be evaluated without a code change |
| **P4** | Analyses + Rankings pages, extended run dialog | `npm run check` green; experiments 1 and 3 re-derivable end-to-end from the UI |

P2 sits before the UI work deliberately: reporting a return computed without execution constraints is
the more expensive mistake, and the tradability delta may change which experiments are worth building
UI for.

---

## 13. Open questions

1. **Survivorship**: the universe comes from the current `stock_basic`; delisted names never appear.
   Fixing this needs a historical listing table — out of scope here, but it bounds every result and
   should be stated in each experiment report.
2. **Holdout**: experiments 1–3 were all selected on the same window. The ranking pipeline makes it
   cheap to add a rolling out-of-sample protocol, but choosing the protocol is a research decision.
3. **Where analyses execute**: in-process job worker for now; a separate worker pool is warranted once
   a single analysis exceeds ~10 minutes.

---

## 14. Extensibility: adding a factor, adding an experiment

The pipeline above is built around four kinds of things that will keep growing: **factors**, **labels**,
**strategies**, and **experiments**. Each needs a declared contract, otherwise the growth shows up as
code churn in the core.

### 14.1 Factors

A factor is not just a formula — it has dependencies, a point-in-time rule, and a version.

```python
@dataclass
class FactorSpec:
    code: str                     # "mom_20d"
    version: int                  # bumped when the formula changes
    formula: str                  # engine expression
    needs: list[ColumnRef]        # ("stock_trade_daily", "close"), ("income", "n_income", as_of="ann_date")
    pit: PointInTime              # as-of join key, publication lag, restatement policy
    universe: str                 # "all_a" | "non_st" | custom
    direction: int                # +1 / -1, documentation for humans and for sign checks
    category: str                 # price / fundamental / flow / sentiment
    coverage_ok_from: date        # first date with enough history for this formula
```

Consequences for the rest of the system:

| Concern | Rule |
|---|---|
| model fingerprint | includes `(factor code, version)` — a formula change invalidates cached models instead of silently reusing a model trained on different inputs |
| analysis validation | `needs` are checked against the actual tables; a fundamental factor trained on a non-PIT join is rejected, because `ann_date` lag is where look-ahead lives |
| recompute | a version bump marks `factor_values` for that factor stale from the change date; analyses refuse stale inputs unless explicitly allowed |
| panel load | the existing wide-panel loader already reads only named factor columns — the new part is that the column set now comes from `inputs.factors` instead of a hardcoded list |

Adding a factor therefore = one `FactorSpec` + its data columns + a recompute job. No change to
analyses, models, runs or the UI: the factor picker is driven by the factor table.

### 14.2 Labels

A label is currently a script flag (`--label benchmark --horizon 20`) and appears in the code in at
least four places: export, training, dataset naming, report text. It becomes a first-class object:

```json
{"id": "bench20", "kind": "benchmark", "horizon": 20, "benchmark": "000300.SH",
 "entry": "open[t+1]", "exit": "close[t+1+h]", "filter": {"exclude_st": true},
 "notes": "跑赢沪深300，20 个交易日"}
```

| Concern | Rule |
|---|---|
| dataset | a dataset is built *for* a label id; the manifest records it, so `scorecard-training-20d-bench` is derivable rather than hand-named |
| model | `label_id` in the artifact; training and scoring both read the same definition — no drift between "what we trained on" and "what the report claims" |
| new label kinds | triple-barrier is just another `kind` with `{"upper": 0.05, "lower": -0.03, "vertical": 20}` — the export path needs a new implementation, but nothing downstream changes |
| comparison | runs with different labels are not comparable; the UI must show the label next to every metric, and experiment comparison refuses a mixed-label selection |

### 14.3 Strategies (the trade rule)

`buy_rule: "policy" | "mechanical"` is an enum — it will not survive the third strategy. It becomes a
registry with the same shape as analyses:

| Strategy | Reads | Notes |
|---|---|---|
| `policy` | the portfolio's configured policies | current default; pool → policy → trades |
| `mechanical` | `top_n`, `hold_days`, `sell_rank_limit` | the ranking diagnostic used in experiments 1–3 |
| `quarterly_rebalance` | `top_n`, `rebalance` | the low-turnover experiment that is currently next in the queue |
| `risk_parity` (later) | volatility, correlations | sizing, not selection |
| `custom` (later) | a declared rule set | only if the above prove insufficient |

A strategy declares `requires` (rankings? positions? volatility?) and `params_model`, and produces
`list[Order]` from `(pool, book, cash, day)`. The runner owns execution and accounting for all of them,
so cost and tradability rules cannot differ between strategies — which is exactly the bug that would
otherwise appear when a second strategy is added.

### 14.4 Experiments

Today an experiment lives in a report and a run name. Two structural problems follow: comparing
variants requires manual matching, and "same experiment, new factor" means re-writing a payload.

```json
{"id": "exp3-regime", "question": "regime 切换是否优于固定符号",
 "ranking": [{"source": "regime-ma60-v1"}, {"source": "mom-sign-always-v1"}, {"source": "rev-sign-always-v1"}],
 "label": "bench20", "strategy": "policy", "window": ["2025-07-01", "2026-10-09"],
 "controls": [{"source": "pool-random-11"}, {"source": "pool-random-12"}],
 "conclusion": {"verdict": "no incremental information", "evidence": "..."}}
```

| Concern | Rule |
|---|---|
| variant matrix | an experiment expands into runs: `ranking × strategy × window × seed`; each cell is a `SimulationRun`, the experiment holds the comparison and the verdict |
| controls | random-pool controls are part of the definition, not an afterthought — a verdict without controls is rejected by review |
| new factor / new label | change one field, re-expand; the diff between two experiments is the answer to "did the factor help" |
| sweep | `params` may carry a grid; expansion creates one run per cell (bounded by a declared limit) |
| provenance | every cell records source id + artifact sha + model fingerprints + dataset version, so a verdict is auditable years later |
| sprawl | experiments have `status` (draft / running / concluded / abandoned) and their own tags; abandoned ones are hidden from the source picker |

### 14.5 What stays out of the core

Deliberately not built: a general DSL for strategies, a plugin system with dynamic imports, an
arbitrary-code analysis runner. Every extension point above is a **registry entry with a typed params
model**, because that is what keeps the audit trail intact. If a future experiment cannot be expressed
as a registry entry, that is a signal to discuss the shape of the abstraction — not to add an `eval`.

---

## 15. Recovering a lost artifact

The artifact store is a PVC, so a restart keeps it and a lost node does not. Nothing copies it, on
purpose — see the failure-mode table above. Recovery is a re-run, and the run record is what makes the
re-run faithful:

1. `GET /api/rankings/{id}` → read `method`, `params`, `dataset.name`, `dataset.version`.
2. `POST /api/analyses/{method}/runs` with those parameters, plus `source_id` set to the same id.
3. Compare the new `artifact_sha256` with the old one:
   - **equal** — the same artifact, byte for byte; old runs reproduce exactly.
   - **different** — an input moved (dataset version, factor formula, upstream data). That is the signal
     the backup would have hidden. Decide explicitly: republish under a new id, or investigate.
4. Old runs keep their original `artifact_sha256`; they become comparable to each other, not to the new
   one. Re-pointing them is a deliberate act, never automatic.

Model artifacts (`model.json`) are parameter files of a few kilobytes and take longer to regenerate than
a score table, but the same rule applies: the fingerprint names the inputs, so retraining with the same
inputs and a different fingerprint means something upstream changed.
