# Scorecard model (script-only)

Rank stocks by how likely they are to outperform, from the factor library. **Not wired into the
API or the SPA** — this is a research script, run by hand, that writes a JSON model and prints
reports.

```
backend/scripts/scorecard.py
```

## Running it

```bash
cd backend

# 1. is there anything to learn from this window?
python -m scripts.scorecard analyze --start 2026-06-01 --end 2026-10-09

# 2. fit, look at held-out behaviour, save reports/scorecard_5d_relative.json
python -m scripts.scorecard train --start 2026-06-01 --end 2026-10-09 --top-n 10

# 3. rank one day and print the top N
python -m scripts.scorecard score --date 2026-10-09 --top 10
```

| Option | Default | Meaning |
|--------|---------|---------|
| `--horizon` | `5` | holding sessions; the label is the return over this window |
| `--label` | `relative` | `relative` = beat that day's median; `absolute` = positive return |
| `--holdout` | `0.25` | last fraction of dates held out, never randomly |
| `--min-iv` | `0.02` | factors below this IV are not fitted |
| `--max-corr` | `0.7` | drop a factor correlated above this with one already kept |
| `--include-st` | off | keep ST / delisting names (excluded by default) |
| `--model` | `reports/scorecard_<h>d_<label>.json` | artifact to load when scoring |

`data` prints the dataset as loaded (rows, dates, label rate), which is the fastest way to notice an
empty factor or a window with no labels.

## What the model is

A scorecard, in the credit-scoring sense:

1. **Rank within the date.** Every factor becomes a cross-sectional percentile (0..1), so a value
   means "top decile of momentum that day" rather than "above 3.2". Factor distributions drift;
   raw thresholds do not survive a regime change.
2. **Deciles → WOE.** Each factor's ten rank-buckets get `WOE = ln(%good / %bad)` against the label,
   with 0.5 smoothing so a bin with no positives stays finite. `IV = Σ (%good − %bad) × WOE` measures
   how much the factor separates.
3. **Prune.** Keep factors with IV ≥ `min-iv`, drop any whose Spearman ρ with an already-kept factor
   exceeds `max-corr` (dividend-yield-like factors cluster; `distribution_ret_std` and `vol_60d` are
   the same formula and correlate at 1.000).
4. **Fit.** Ridge-penalised logistic regression on the WOE columns by Newton's method — no
   scikit-learn, because WOE binning is a groupby and the fit is 20 lines of numpy. L2 keeps a
   separable factor from sending its coefficient to infinity.
5. **Score.** `intercept + Σ coef × WOE`. Monotone with the fitted probability, so ranking by score
   is ranking by probability; `score` prints the contributions so a pick can be explained.

The label is **relative** by default (beat the day's median) because absolute up/down is mostly the
market's direction. Entry is the **next session's open** and exit is the close `horizon` sessions
later: a signal computed on a close cannot be traded at that close.

## Reading the output

```
AUC train 0.575 · test 0.561
top-10 on held-out dates: mean +0.56% vs universe -0.43% (excess +1.00%, 57% of dates ahead)
```

- **AUC** is cross-sectional discrimination: 0.5 is a coin flip, 0.56 is a weak but real edge. A
  train/test gap much wider than this is overfitting.
- **Excess** is the honest number: top-10 mean forward return minus the equal-weight universe on the
  same dates. In a falling market a top-10 list can lose money and still be working; `picked_hit` and
  `universe_hit` side by side say which happened.
- A factor with a **negative IC** is not a bug: in this window momentum and size reversed, so the fit
  gives those factors a positive coefficient on their WOE (high WoE = that decile historically held
  more outperformers, whichever way the raw factor runs). Check `analyze` before trusting it — a
  regime that flips will flip those coefficients.

## Limits worth knowing

- The window is short (88 sessions at the time of writing, ~330k training rows). Everything here is
  one regime; treat the held-out numbers as a sanity check, not an estimate of future returns.
- Factors cover the price/volume and `daily_basic` families only — 19 of 47 definitions are
  computable, so nothing here sees fundamentals.
- No transaction costs, no liquidity filter beyond data presence, no position limits. `top_n` is a
  ranking experiment, not a portfolio construction.
- Nothing schedules it. A daily run would be a cron or a job type, deliberately not added yet.
