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
| object storage loss (happened once already) | artifact sha256 recorded on the source; a missing object marks the source `stale` and simulations refuse to start with a clear message, rather than silently degrading |
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
