# Information architecture

The product accumulated four nouns for two ideas — *score the cross-section* and *test a selection* —
and exposed all four in the sidebar. This page is the inventory, the principles, and the target tree.
It is a design decision record: when a page or a label changes, this is what it has to stay consistent
with.

## 1. Principles

1. **Group by what the user is doing, not by how it is built.** "Ranking source" is a database row;
   "选股方法" is what a person has. The menu speaks the second language.
2. **One concept, one entry.** If two pages describe one idea (an action and its stored result), they are
   one page with two sections.
3. **A page earns its place by a recurring decision.** If a page exists only because a table needed a
   home, it belongs inside the page that owns the decision.
4. **Depth over breadth.** Four groups of at most four items; anything deeper is reached from the thing
   it modifies (a factor is edited from the method that uses it, not from the menu).
5. **Every page answers three questions in its first screen:** what is this, what do I do here, what is
   the state of my data.
6. **Words come from the domain, not from the code.** `run`, `artifact`, `source`, `registry` never
   appear in the UI.

## 2. Concept model

Six concepts, each with exactly one name in the UI. Everything else is a detail view or an archive.

| Concept | User-facing word | What it is | Where it lives |
|---|---|---|---|
| 打分方法 | **选股方法** | how stocks get scored; produces a daily ranking | 研究 → 选股方法 |
| 试一次 | **回测** | one method + one window + one strategy → an equity curve | 研究 → 回测 |
| 参照 | **基线** | the same run with stocks picked at random; stands for luck | an option on 新建回测 |
| 判断 | **结论** | "beats baselines by ≥2σ" or "no incremental information" | attached to a 回测, archived |
| 规则 | **策略** | how to trade the ranking: enter on pool, exit on policy, fees | 策略配置, chosen in 新建回测 |
| 账户 | **我的组合** | holdings, cash, transactions, watchlist | 投资 → 我的组合 |

Two things that are *not* concepts in the menu:

- **因子** — raw material for a method, edited from the method that uses it (and visible on a stock's page).
- **任务 / 数据状态** — plumbing, under 系统.

## 3. Target tree

Groups name a **subject**, never a frequency. "每天" was a mistake worth recording: it mixed two axes
(frequency and subject), so "每天 / 市场" could not be told apart — 选股 is used daily, an index is looked at
daily. Nothing in the industry groups a menu by cadence; the home page carries that idea on its own, and the
groups stay object-based.

```
概览                         (a single entry, not a group)
                             数据到哪一天 · 我有哪些方法 · 今天各选出什么 · 持仓异动

投资
├── 选股                    用条件筛一遍全市场          (决策：这次买什么)
└── 我的组合                持仓 / 自选 / 成交 / 策略绑定  (决策：拿着还是换掉)

研究
├── 选股方法                新建一套方法 · 已有方法 · 某天的前 20 名
└── 回测                    运行列表 · 新建回测（可勾选"同时跑基线"）· 结果与结论

数据
├── 行情                    查一只票：走势、因子、公告      (检索，不决策)
├── 指数                    指数列表与走势
└── 数据状态                数据到哪一天、缺什么

系统
├── 任务
└── 设置                    含交易费率（佣金、印花税、手数）
```

选股 and 行情 stay apart because they are different jobs: **选股 narrows the universe to decide; 行情 looks one
name up.** 行情 is a lookup, 选股 is a decision.

The menu item 「对照比较」 is gone; `/experiments` survives only as a deep link to legacy records until verdicts
move onto runs (feature list E8). There is no 「对照比较」page. Running baselines is a checkbox on 新建回测; the result page shows
`本策略 −15.13 | 基线均值 −0.36 ± 9.32 → −1.59σ`; "保存为结论" files the verdict. A verdict is read from the
run it belongs to, not from a separate list.

## 4. Page contracts

Each page answers, in its first screen: what is this, what do I do here, what is the state of my data.

| Page | Purpose | Primary action | Empty state |
|---|---|---|---|
| 概览 | 今天需要你决定的事 | — | "还没有方法：去 选股方法 建一套" |
| 选股 | 用条件筛一遍全市场 | 加入自选 | "没有满足条件的股票，放宽条件试试" |
| 我的组合 | 你持有的和关注的 | 记一笔成交 | "还没有持仓，从 选股 里挑几只" |
| 选股方法 | 一套方法 = 怎么给股票打分 | 新建方法 | "还没有方法，用 regime 打分或训练一个评分卡开始" |
| 回测（列表） | 一次回测 = 一套方法 + 一段区间 → 一条净值曲线 | 新建回测 | "还没有回测，选一套方法跑一次" |
| 新建回测 | 方法 + 区间 + 策略（+ 可选基线） | 开始回测 | — |
| 回测结果 | 这次回测的账本，以及它相对基线的位置 | 保存为结论 | — |
| 行情 | 查一只票 | 搜索代码 | "数据截至 X" |
| 指数 | 指数走势 | 选一个指数 | "暂无数日线数据" |
| 数据状态 | 数据到哪一天、缺什么 | — | — |
| 任务 | 后台在跑什么 | — | "没有正在运行的任务" |

## 5. Vocabulary

| Internal (never shown) | User-facing | Why |
|---|---|---|
| ranking source / artifact | 选股方法 | a person owns methods, not rows |
| analysis method / registry entry | 计算方法（新建方法时的一个选项） | it is a choice, not a place |
| simulation run | 回测 | one word for the action and its result |
| experiment / variant / control | 结论 / 候选 / 基线 | lab words replaced by what they do |
| strategy config / trading rules | 策略 | the thing you pick when starting a backtest |
| provenance / manifest / sha256 | 用了哪份数据（版本与日期） | hashes belong in the record, not the sentence |
| job | 后台任务 | and only under 系统 |

## 6. Migration order

1. **回测表单加"同时跑 3 个随机基线"** → result page shows mean ± σ; then remove 对照比较 from the menu
   and keep `/experiments` as a read-only archive behind "保存为实验".
2. **因子 demote**: the factor list stays at `/factor` but leaves the menu; a method page links to it
   ("用到的因子").
3. **系统 group**: move 数据状态 and 任务 under one collapsible group; nothing else changes.
4. **今天** becomes the only entry point for the daily loop, so a user can work a whole day without
   opening the research section.

## 7. What this buys

Three interactions cover the product:

- **每天**: 今天 → 选股 → 我的组合
- **试一试**: 选股方法 → 回测（带基线）→ 看 σ
- **查一查**: 行情 / 指数

Everything else is either a detail view of one of those, or an archive.

## 8. Open questions

1. 因子 as a top-level item: some users browse factors like a library. If usage shows that, promote it
   back and let 方法 link downward instead — the tree above is the default, not a dogma.
2. Whether 实验记录 should be a page at all, or simply a filter on the run list ("只看带基线的")。Decide
   after the baseline option ships and we can see how often verdicts are filed.

## 9. The data model behind the navigation

Three different things are called "portfolio" in the current schema, and that is why the navigation feels
tangled. Separating the **words** is not enough; the **records** have to separate too — but not into a new
catch-all table.

| What it is | Nature | Where it belongs |
|---|---|---|
| **投资组合**: holdings, cash, transactions, watchlist | one long-lived account per user | `portfolios` — the only thing called a portfolio |
| **交易成本**: commission rate, minimum fee, stamp duty, lot size | a market/broker **fact**, the same for every run | configuration (`settings`), not a table of user data |
| **策略参数**: cash buffer, position cap, stop loss, MA windows | a **choice** the user iterates on | one reusable record per strategy configuration |

An earlier draft of this section proposed a `trading_rules` table holding costs *and* strategy parameters
together. That was wrong on both halves: costs are facts (they belong in configuration, and hard-coding
them in the runner — as it happens today — is nearly as wrong in the other direction), and strategy
parameters are choices that have nothing to do with fees. A table that mixes a constant with a preference
is a table that will be denormalised the first time the broker changes its rate.

### Target

```
settings / config            commission, stamp duty, lot size, cash buffer default  ← facts
strategy_configs (策略配置)   strategy name + params (pool_entry / policy / mechanical) ← choices
portfolios ── strategy_config_id (bound, replaceable)
           └─ active_run_id (optional)
simulation_runs ── strategy_config_id, window, ranking_source_id, model fingerprints,
                   cost model snapshot (the numbers actually used)
experiments ──── several runs
```

- **选股 → 组合**: writes `portfolio_stocks`. A portfolio action, correctly so.
- **选股方法**: produces a `ranking_source`. Needs no portfolio.
- **回测**: needs a strategy configuration, a window and a ranking source. **Needs no portfolio.**
- **组合跟随回测**: only when the user asks (`active_run_id`), one direction only.

The one thing a run must *store* rather than reference is the **cost model snapshot** — the fee numbers in
force when it ran. Costs are configuration and configuration changes; a 2025 backtest must not silently be
re-priced with 2026 fees.

### Migration

1. Move the fee constants out of the runner into configuration (they are already constants in code; give them
   one home and a settings screen section).
2. Introduce `strategy_configs`; backfill one per existing portfolio from `portfolio_policies` +
   `portfolio_risk_control`, parameters unchanged (the numbers must not move).
3. Add `simulation_runs.strategy_config_id` and `cost_snapshot`, backfill from the run's `portfolio_id`.
4. Make `simulation_runs.portfolio_id` nullable. The run form asks for a strategy configuration, not a
   portfolio, and shows the cost numbers it will use.
5. Only then remove the portfolio selector from the backtest form — UI follows the model, not the reverse.

### Why the separation matters for the navigation

「选股方法」and「回测」are research; they must not require an object the user manages daily. As long as a run
needs a portfolio, the menu has to pretend research and investing are the same area, and 「回测」versus
「对照比较」keeps looking like one thing split in two.
