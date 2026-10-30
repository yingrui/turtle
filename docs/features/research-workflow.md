# Research workflow: who does what, how it is judged, what the UI must show

`rankings.md` describes the machinery. This page describes the **process** it serves: the steps a
researcher actually walks, who is responsible at each step, how a result is judged, and which UI
surfaces exist at each build phase. Without this, the machinery has no acceptance test.

The workflow exists because of a concrete failure pattern from experiments 1–3: a number was produced,
looked convincing (+64.5 points), and was wrong twice over (same-bar fills, then no control group).
Both defects were caught by *process*, not by code review. The process below makes those catches
mandatory instead of lucky.

---

## 1. Roles

| Role | Who | Owns | Not responsible for |
|---|---|---|---|
| **Researcher（研究员）** | the person with the question | hypothesis, factor/label choice, ranking source, interpretation, report | infrastructure, data pipelines |
| **Data engineer（数据）** | whoever maintains ingest | raw tables, point-in-time joins, universe definition, dataset exports | model choices, verdicts |
| **Platform（平台）** | engineering | analysis runner, ranking sources, simulation engine, UI | deciding which experiments matter |
| **Reviewer（评审）** | a different researcher, or the platform lead | whether a verdict is admissible: controls present, in-sample/out-of-sample separated, provenance complete | re-running the work |

One person can hold several roles at this size, but the **reviewer must not be the researcher** — the
+64.5 error was self-reviewed and passed.

---

## 2. The end-to-end research loop

```
(1) question ─▶ (2) experiment definition ─▶ (3) ranking source ─▶ (4) simulation run
                       ▲                                                    │
                       │                                                    ▼
             (8) promote / abandon ◀── (7) verdict + report ◀── (6) evaluation ◀── (5) controls
```

| # | Step | Input | Action | Output | Who | UI |
|---|---|---|---|---|---|---|
| 1 | Question | an observation ("regime switching feels better") | write it as a testable claim with a kill criterion | a one-line hypothesis + "what would falsify it" | Researcher | Experiment page (draft) |
| 2 | Definition | hypothesis | pick label, window, strategy, universe, **controls** | an `Experiment` record: variant matrix + controls | Researcher, reviewed by Reviewer | Experiment page: label/window/strategy pickers, controls must be non-empty to save |
| 3 | Ranking source | factor set or a method | run an analysis (or pick an existing source) | `RankingSource` with coverage + validation report | Researcher | Analyses page (params form from schema, run, history) |
| 4 | Run | source × strategy × window | launch the matrix | `SimulationRun` per cell, with provenance | Researcher | Run dialog (source dropdown, retrain cadence, name) |
| 5 | Controls | the experiment's control list | same matrix on random/constant pools | control runs in the same comparison | automatic (defined in step 2) | Experiment page: variant × control grid |
| 6 | Evaluation | run books | metrics + significance vs controls | evaluation table + verdict candidates | automatic; Researcher interprets | Experiment page: metric table, noise band σ, in/out-of-sample split |
| 7 | Verdict | evaluation | write conclusion + evidence + limits | report article in the `因子实验` channel | Researcher; Reviewer signs off | Experiment page: conclusion fields → publishes the article |
| 8 | Promote / abandon | verdict | either make it a product feature (a saved strategy + source pair) or mark abandoned | status change; abandoned sources hidden | Reviewer | Experiment page: status buttons |

Nothing reaches step 7 without step 5: **a verdict with no control runs is not admissible.** The system
enforces this by refusing to mark an experiment `concluded` while its control cell is missing.

---

## 3. Judgement criteria (how a result is evaluated)

Evaluation is three layers, in order. A result must pass each to move on.

### 3.1 Correctness gates (blocking, mechanical)

| Check | Rule | Why it exists |
|---|---|---|
| provenance complete | run has `{source_id, artifact_sha256, dataset version + manifest sha, label_id, model fingerprints}` | experiment 1's report pointed at a dataset version whose objects no longer existed |
| fills are executable | every fill price ≥ next session's open, none inside a suspension or limit-lock | the same-bar bug inflated +43.8 by 20.7 points |
| no look-ahead in inputs | factor `as_of` respected; label `shift(horizon)`; IC weights shifted | experiment 2's +1.39%/month was entirely leakage |
| smoke equivalence | online scores == artifact scores on 5 sampled dates (1e-6) | offline/online drift is otherwise invisible |
| determinism | same config ⇒ same trades (seeded) | a verdict nobody can reproduce is not a verdict |
| checks green | `./check.sh`, `npm run check`, `mkdocs --strict` | existing repo rule |

### 3.2 Statistical gates (blocking, judgement)

| Check | Threshold now | Rationale |
|---|---|---|
| beats controls | excess > best control + 2σ of the control distribution, σ from ≥10 random pools | with 3 random pools the band was 26 points wide; the ±1σ of noise is not a finding |
| sign consistency | mean and median excess share a sign | +0.35% mean with −1.27% median is a few lucky months, not an edge |
| discrimination | mean monthly AUC ≥ 0.53 and stable (std ≤ 0.05) | 0.505–0.517 is a coin flip with extra steps |
| out-of-sample | verdict uses a window the factor/label/model choice never saw | all three experiments were selected on one window |
| cost-adjusted | report shows gross and net, plus turnover | +43.8 points with 6,492 fills is not the same as +43.8 points with 400 |

### 3.3 Product gates (non-blocking, for promotion)

Only relevant when promoting a result into the product: does it work on the current universe, is the
data fresh enough to run daily, does it survive the deployment's cost model, is there a human-readable
explanation for the pool it produces.

---

## 4. Build phases: how each is done, by whom, evaluated how

Each phase has one acceptance test that a second person can execute without reading the code.

### P0 — analyses and score-table sources

| Item | Detail |
|---|---|
| **How** | `analyses`/`analysis_runs`/`ranking_sources` tables + migration; method registry with `regime_score` and `constant_pool`; parquet artifacts in object storage; `RankingService.resolve` for `score_table`; job payload takes `ranking_source_id` |
| **Who** | Platform builds; Researcher is the acceptance tester |
| **Acceptance** | From the UI/API: register `regime-ma60-v1` from an analysis run, then launch a simulation referencing it and reproduce **+43.81 / 153.31** on 2025-07-01 → 2026-10-09 with the same trade count (6,492). A mismatch of any of the three is a failure |
| **UI needed** | Analyses page (method list, generated param form, dataset picker, run history with status/errors); Rankings page (list, coverage, validation report, deprecate); Run dialog (source dropdown replacing free-text) |
| **Judged by** | Reviewer replays the acceptance test from the UI, without shell access |

### P1 — model artifacts, cache, retrain

| Item | Detail |
|---|---|
| **How** | `model_artifacts` + fingerprint `(dataset, version, manifest, factors+versions, hyperparams, label, period)`; `retrain: monthly / weekly / none`; migrate `expanding-bench20`; smoke gate for models |
| **Who** | Platform builds; Researcher validates the numbers match the offline run |
| **Acceptance** | `retrain=monthly` over the same window reports "N reused / M trained", and reproduces experiment 1's **+2.50 / 111.99**. `retrain=none` with a missing period fails loudly |
| **UI needed** | Model artifacts list (period, metrics, cache state, fingerprint); run dialog `retrain` selector; run detail shows the hit/train mix |
| **Judged by** | Reviewer checks that the numbers match the offline script for one month, and that a deliberate factor-version bump invalidates the cache |

### P2 — tradability

| Item | Detail |
|---|---|
| **How** | `app/core/market/tradability.py`: suspension, new listing, limit-up/down, delisting, ST, price floor; wired into pool construction, buy and sell |
| **Who** | Platform builds; Data engineer supplies the limit prices and delisting list |
| **Acceptance** | Re-run experiment 3; the report states the delta between "no constraints" (+43.81) and "realistic" versions, and the number of deferred/rejected fills. Every rejected fill is explainable by a rule name |
| **UI needed** | Run detail: rejected-fill breakdown by reason; pool day view marks unbuyable names with the rule |
| **Judged by** | Researcher accepts the delta or re-scopes the conclusion; Reviewer spot-checks 10 rejections against the raw data |

### P3 — extensibility (factors, labels, strategies)

| Item | Detail |
|---|---|
| **How** | `FactorSpec` with `needs`/`pit`/`version` feeding the fingerprint; `Label` objects; strategy registry; triple-barrier label implementation; a new factor as the first end-to-end exercise |
| **Who** | Data engineer adds the new source; Researcher defines the factor and reads the IC; Platform wires the registry |
| **Acceptance** | Add one genuinely new factor (e.g. 北向持股) and take it from raw table → factor panel → analysis → ranking source → experiment, with no core code change. The review checks the PIT join by hand |
| **UI needed** | Factor page: dependency/coverage/version columns; Analyses form: factor multi-select; Experiment page: label picker with entry/exit rendered as text |
| **Judged by** | Reviewer confirms the factor's `as_of` column and that a version bump invalidated the cached models |

### P4 — experiment surface

| Item | Detail |
|---|---|
| **How** | `Experiment` with variant matrix + controls + status + conclusion; comparison view; conclusion publishes into the `因子实验` channel |
| **Who** | Platform builds; Researchers are the users |
| **Acceptance** | Experiment 3 is re-created end-to-end as an `Experiment` record: 3 variants × 3 controls, conclusion "no incremental information", report generated from the record. A new experiment copying it and changing one factor takes < 10 minutes |
| **UI needed** | Experiment page (definition form, matrix grid, metric table with noise band and in/out-of-sample split, conclusion editor, status transitions); comparison charts |
| **Judged by** | Reviewer performs a full loop on a throwaway question |

---

## 5. Where each role touches the UI

| Surface | Researcher | Data engineer | Reviewer |
|---|---|---|---|
| Analyses page | run, read history | sees coverage/`needs` failures | checks reproducibility of a past run |
| Rankings page | pick source, preview top-20 | fixes stale inputs | verifies coverage vs window |
| Run dialog | launch | — | — |
| Run detail | read metrics, rejected fills | — | spot-check fills and provenance |
| Experiment page | define, interpret, conclude | — | approve verdict, promote/abandon |
| Factor page | browse, add definition | own data deps + PIT | — |

The rule behind this table: **the Researcher never types a path, a version number, or a fingerprint.**
Every identifier they select is an object someone else already validated. That is what makes the
numbers re-derivable by a second person.

---

## 6. What stays manual (and why)

| Manual step | Performed by | Why not automated |
|---|---|---|
| Choosing the question and the kill criterion | Researcher | not a computation |
| Declaring controls | Researcher | the control choice is part of the hypothesis |
| Interpreting a verdict ("is 0.4σ economically meaningful?") | Researcher + Reviewer | thresholds are judgement, encoded but overridable with justification |
| Promotion to a product feature | Reviewer | needs a product decision, not a metric |
| Universe/survivorship repair | Data engineer | needs a historical listing source we do not have yet |

---

## 7. Current state vs this process

| Process step | Today | Gap |
|---|---|---|
| 3 Ranking source | hand-written payload with a file path | P0 |
| 4 Run | API/curl only | P0 (backend), P4 (dialog) |
| 5 Controls | ad-hoc, added after the fact | P4 (and the verdict gate) |
| 6 Evaluation | numbers copied by hand into a report | P4 (metric table + σ band) |
| 7 Verdict | free-form article | P4 (record + generated report) |
| Correctness gates | partially enforced by tests | P2 (fills), P1 (smoke), P0 (provenance) |
| Statistical gates | not enforced at all | P4 |
