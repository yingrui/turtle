# Factors

A factor library: what a factor means, what it produced, and an explicit step to produce more.
Route: **`/factor`**.

## Two tables, two questions

| Table | Answers | Grain |
|-------|---------|-------|
| `factor_definitions` | What is this factor, and can we compute it? | one row per factor |
| `factor_values` | What was its value for this stock on this day? | `(factor_id, ts_code, trade_date)` |

`factor_definitions.code` is the stable identifier (`mom_20d`, `EP_TTM`) — code, rules, and this
page reference it. The catalogue is seeded from the openKMS `AlphaFactor` library plus the three
baseline factors the roadmap asks for:

```bash
cd backend && python -m scripts.seed_factor_definitions   # upsert by code, safe to re-run
```

**A definition without a `formula` is documentation.** 28 of the 47 need inputs this database does
not hold (financial statements, order flow, northbound holdings), so they are listed, described,
and marked *definition only*; the Compute button refuses them with the reason.

## The formula language

A formula is an expression over market-data columns and a small operator set. It is evaluated on a
**panel**: one `date × ts_code` frame per field, widened from `tushare.stock_trade_daily` and
`tushare.daily_basic`.

```
mom_20d        close / shift(close, 20) - 1
liq_turn_std_6M std(turnover_rate, 120)
corr_ret_turn_post_1M  corr(shift(turnover_rate, 1), ts_ret(close, 1), 20)
RSI            100 * ma(where(ts_ret(close, 1) > 0, ts_ret(close, 1), 0), 14) /
               (ma(where(...), 14) + ma(where(ts_ret(close, 1) < 0, -ts_ret(close, 1), 0), 14))
EP_TTM         where(pe_ttm > 0, 1 / pe_ttm, nan)
```

| Operators | Meaning |
|-----------|---------|
| `ma(s,n)` `ema(s,n)` `std(s,n[,min_periods])` | trailing mean, exponential mean, rolling std |
| `ts_max(s,n)` `ts_min(s,n)` `ts_sum(s,n)` `shift(s,n)` `ts_ret(s,n)` | trailing window, lag, return over n days |
| `corr(a,b,n)` | rolling correlation of two fields |
| `where(cond,a,b)` | pick elementwise; a NaN condition counts as false |
| `rank_cs(s)` `zscore_cs(s)` | cross-sectional rank / z-score within each date |
| `abs log sqrt sign minimum maximum` | elementwise math |

Widening the panel is what keeps the language small: time-series operators are column-wise
`rolling`/`shift`, cross-sectional ones are row-wise, so neither needs a groupby over five thousand
codes. Formulas are parsed and every AST node is checked against an allow-list before evaluation —
a stored formula cannot reach `__import__`, attribute access, or comprehension.

## Computing

```http
POST /api/factors/{code}/compute?start=2026-07-01&end=2026-10-09
→ {"job_id": "...", "code": "mom_20d", "status": "pending"}
```

A job, not a request: the run walks the whole panel. History before `start` is loaded (and not
stored) so a rolling operator has its window — `lookback_days` decides how much. Values upsert by
`(factor_id, ts_code, trade_date)`, so re-running a window corrects it in place. Nothing recomputes
on read: `last_date` tells you when someone last ran it.

Only the fields the formula names are read, and each field is pivoted on its own — reading the
whole table and pivoting it at once ran a 1 GiB pod out of memory for a single factor.

## Reading

| Route | Query | Use |
|-------|-------|-----|
| `GET /api/factors` | `computable`, `category` | catalogue + coverage (`value_count`, `stock_count`, `last_date`) |
| `GET /api/factors/{code}` | — | one definition with coverage |
| `GET /api/factors/{code}/dates` | `limit` | dates that have values, newest first |
| `GET /api/factors/{code}/values` | `ts_code` **or** `trade_date`, `start`, `end`, `sort`, `order`, `limit`, `offset` | one stock's history, or one day across the market |

## The page

`/factor` lists the catalogue (search, category, *computable only*), and for the selected factor
shows its definition, formula, coverage, a Compute control with the job's log, and a values table
with two views: **one stock** (its history) and **one day** (the cross-section, ranked).

## Adding a factor

1. Add an entry to `backend/scripts/data/factor_definitions.json` (or create the row directly).
2. Give it a `formula` and a `lookback_days`; leave both null if the inputs are not here.
3. Re-run the seed script, open `/factor`, press Compute.

Turtle-native factors live here and can be pushed to the knowledge base later; the openKMS
`AlphaFactor` objects stay the documentation layer (prose, handbook source, wiki link), matched by
`code`.
