# Design (greenfield): what the system should be, ignoring today's schema

Written from the problem, not from the current tables. Where this disagrees with the code, this document is
the target and the code is the debt.

## 1. Who it is for, and what they actually do

One person, working alone, with three jobs:

| Job | Frequency | Question |
|---|---|---|
| **看盘 / 复盘** | daily | 我今天该看什么？我持有的东西怎么样了？ |
| **试想法** | weekly | 这个选股思路能不能挣钱？ |
| **判断真假** | monthly | 这个结果算本事，还是运气？ |

Everything follows from those three. Anything that serves none of them is not in the product.

## 2. The one abstraction that fixes most of the mess: a **Book**

A real account and a backtest are the same object seen twice: *something that holds positions over time and
has a value on every day*. Today they are separate tables with separate code paths and separate bugs, and a
backtest has to borrow a real portfolio's settings.

```
Book (id, kind: real | simulated, name, currency, cost_model_id, initial_cash)
 ├── Position (book_id, symbol, opened_at, closed_at, qty, cost_basis)
 ├── Fill     (book_id, ts, symbol, side, qty, price, fees)      ← real: recorded by the user
 │                                                                ← simulated: produced by a strategy
 └── Valuation(book_id, date, cash, market_value, total)          ← derived, same formula for both
```

Consequences, all of them good:

- **One ledger, one valuation, one P&L.** A bug fixed in the simulated path is fixed for the real one, and the
  numbers mean the same thing.
- **"组合跟随回测" becomes trivial**: `book.real.follows = book.simulated.id` — copying positions from a
  simulated book is the same operation as copying between two real ones.
- **No fake portfolios for research.** A simulation is a book created by a run, not a real account in disguise.

## 3. The rest of the model

```
Symbol        a stock. Static facts only (code, board, listing date).
Bar           daily prices. Read-only, written by an external ETL.
Factor        a named, versioned computation over Bars/Fundamentals → per (date, symbol) value.
              A factor declares: formula, inputs, point-in-time rule, version.
Universe      a stored filter (conditions over factors/bars) → a set of symbols per date.
              "选股" is the process of editing one and looking at today's result.
Method        how to score today's cross-section: a set of (factor, weight/transform) or a trained model.
              Produces `Ranking(date, symbol, score)` — nothing else.
Strategy      a pure rule: (ranking, book state, date, params) → list[Order]. No I/O, no bookkeeping.
              Examples: enter-on-pool, exit-on-policy, top-N-hold-D-days.
CostModel     commission, stamp duty, lot size, slippage. Versioned facts (broker/market), not per-book data.
Run           one execution: method × strategy × book-kind × window × cost snapshot × dataset snapshot.
              Writes a simulated Book and its Valuations.
Baseline      a Run whose method is "pick symbols at random from this universe".
Comparison    several Runs + their baselines → per-candidate excess and σ. Stored with a Verdict.
Verdict       one sentence + numbers + when + on what evidence. Immutable.
```

Relationships: a Method never knows about books; a Strategy never knows about factors; a Run binds them and
records **exactly** what it bound (dataset version, factor versions, model fingerprint, cost snapshot).

## 4. Invariants (write these tests before the code)

1. `Valuation.total = cash + Σ(qty × close)` — every day, no exceptions, suspended names carried at their last close.
2. The first valuation of a book equals its `initial_cash`.
3. A fill is executable: price ≥ next session's open, not inside a suspension or a limit-lock; first-day listings excluded.
4. Buying and selling at the same price never increases equity (fees only reduce it).
5. A run is reproducible: same inputs ⇒ identical fills, byte for byte.
6. Real and simulated books go through the same ledger and valuation functions (asserted structurally, not by review).

## 5. Flows

**Daily（5 分钟）**: 概览 (data freshness, my books' changes, today's picks from my methods) → 选股 to look
for something new → 组合 to record a trade if I made one.

**Try an idea（30 分钟）**: 方法: define/refresh a scoring method → 回测: pick method + strategy + window,
tick "also run 3 random baselines" → result page: equity, fills, excess vs baselines with σ → "保存结论".

**Judge（once）**: the verdict lives on the run. No separate experiment page, no separate object to keep in sync.

## 6. Information architecture

```
概览

投资    选股 · 我的组合
研究    方法 · 回测
数据    行情 · 指数 · 数据状态
系统    任务 · 设置（费率）
```

Rules: groups name a subject, never a frequency; a concept appears once; a page exists only if a recurring
decision needs it; every page states its purpose, its single primary action and its empty state.

## 7. API shape

```
GET  /api/overview
GET  /api/universe/{id}?date=            filtered symbols for a day
CRUD /api/factors  /api/methods  /api/strategies  /api/cost-models
POST /api/runs        {method_id, strategy_id, window, baselines?: int, cost_model_id?}
GET  /api/runs/{id}                      book, valuations, fills, metrics, provenance
POST /api/runs/{id}/verdict   {text, numbers}
GET  /api/books/{id}                     same shape for a real book
POST /api/books/{id}/fills               record a real trade
```

No request body ever carries a filesystem path, a dataset version, or a fingerprint — those are resolved from
ids and recorded by the server. Three separate bugs in the current code came from payload fields that were
silently ignored; the fix is to let the server own every derived field.

## 8. Build order (each step ships something usable)

| Step | Deliverable | Acceptance |
|---|---|---|
| 1 | Book abstraction: ledger + valuation + invariants 1–4 | a real book and a simulated book produce identical P&L from identical fills |
| 2 | CostModel in config with snapshots | changing the fee rate does not alter an old run's numbers |
| 3 | Universe + 选股 page on top of factors | "筛出今天满足条件的票" without a book in sight |
| 4 | Method (scoring) + Run on a simulated book | a run needs only method + strategy + window |
| 5 | Baselines + σ on the result page + verdict | a result states whether it clears the baselines |
| 6 | Overview page on top of books and methods | the daily loop needs no research pages |

Steps 1–2 are pure model work with no UI; they are first because every later step depends on the numbers
being right, and because they are what stops two code paths from diverging again.

## 9. Deliberately not built

- An experiment object with a lifecycle. A verdict on a run covers it.
- A registry of immutable ranking artifacts. A method plus a pinned dataset reproduces any ranking; a stored
  artifact is an optimisation, added only if a profiler asks for it.
- Multi-user, permissions, sharing. One person.
- A strategy DSL. Three strategies cover the questions; a DSL is a project of its own.
- Real-time data, broker integration. Out of scope by definition.

## 10. What this fixes, concretely

| Today | With this design |
|---|---|
| backtest requires a portfolio | run needs only method + strategy + window |
| policy params live on the account and change history | params are a Strategy record; runs snapshot costs |
| real and simulated books have separate code | one ledger, one valuation, one set of invariants |
| "实验", "对照比较", "排序来源" as separate nouns | 回测 + 基线 + 结论, three words that match the three jobs |
| payload can silently drop a field | server owns derived fields; ids only |
