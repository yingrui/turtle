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

## 2. Inventory and verdict

| Current page | What it really is | Verdict |
|---|---|---|
| 今天 (home) | status + shortcuts | keep, becomes the daily dashboard |
| 选股 (screening) | ad-hoc filter over the universe | keep |
| 我的组合 (portfolio) | holdings, watchlist, transactions, policies | keep — 自选 folds in as a tab |
| 选股方法 (methods) | produce a selection + list of selections | keep (merged from "截面分析" + "排序来源") |
| 因子 (factors) | what methods are built from | demote: reachable from 方法, not a top-level item |
| 回测 (simulation) | run list / new run / result detail | keep; **baselines become an option on the new-run form** |
| 对照比较 (experiments) | several runs + baselines + verdict | **dissolve**: the comparison is a block on the run result page |
| 行情 / 指数 | market data browsing | keep, merged into one "市场" group |
| 数据状态 (data collection) | data freshness and coverage | move under 系统 |
| 任务 (jobs) | background job log | move under 系统 |
| 设置 (settings) | preferences, DB admin | keep under 系统 |

Two pages disappear as top-level items (因子, 对照比较); two move groups (数据状态, 任务); one pair merges
(截面分析 + 排序来源 → 选股方法).

## 3. Target tree

Groups name a **subject**, never a frequency. "每天" was a mistake worth recording: it mixed two axes
(frequency and subject), so "每天 / 市场" could not be told apart — a screen is used daily, an index is
looked at daily. Nothing in the industry groups a menu by cadence; the home page carries that idea on
its own (Home / Overview / 今日概览), and the groups stay object-based.

```
概览                         (a single entry, not a group) 数据新鲜度、我有哪些方法、今日选出什么、持仓异动

投资
├── 选股                    用条件筛一遍全市场（决策：这次买什么）
└── 我的组合                持仓 / 自选 / 成交 / 策略设置（决策：拿着还是换掉）

研究                         想验证一个想法时才来
├── 选股方法                新建一套方法；已有方法列表；某天的前 20 名
├── 回测                    运行列表 → 新建回测（含"同时跑基线"选项）→ 结果：净值、成交、与基线的 σ
└── 实验记录                已下过结论的对照（只读档案，从回测结果页"保存为实验"进入）

数据
├── 行情                    查一只票：走势、因子、公告（检索，不决策）
├── 指数                    指数列表与走势
└── 数据状态                数据到哪一天、缺什么

系统
├── 任务
└── 设置
```

选股 and 行情 are different jobs, which is why they stay apart: **选股 narrows the universe to decide;
行情 looks one name up.** 行情 is a lookup, 选股 is a decision.

Note the asymmetry: 回测 is the page that produces a verdict; 实验记录 is where verdicts are *filed*. The
comparison itself happens on the run page — that is the change that removes a whole concept from the
user's head.

## 4. Page contracts

Each page states its purpose, its single primary action, and what it shows when empty.

| Page | Purpose (one line, shown at top) | Primary action | Empty state |
|---|---|---|---|
| 今天 | 今天需要你决定的事 | — | "还没有方法：去 选股方法 建一套" |
| 选股 | 用条件筛一遍全市场 | 保存为观察池 | "没有满足条件的股票，放宽条件试试" |
| 我的组合 | 你持有的和关注的 | 记录一笔成交 | "还没有持仓，从 选股 里挑几只" |
| 选股方法 | 一套方法 = 怎么给股票打分 | 新建方法 | "还没有方法，用 regime 打分或训练一个评分卡开始" |
| 回测 | 一套方法在历史上挣了多少 | 新建回测 | "还没有回测，选一套方法跑一次" |
| 回测结果 | 这次回测的账本与相对基线的位置 | 保存为实验记录 | — |
| 行情 / 指数 | 市场数据 | 搜索代码 | "数据截至 X，请联系管理员同步" |
| 数据状态 | 数据到哪一天，缺什么 | — | — |
| 任务 | 后台在跑什么 | — | "没有正在运行的任务" |

## 5. Vocabulary

| Internal (never shown) | User-facing | Why |
|---|---|---|
| ranking source / artifact | 选股方法 | a person owns methods, not rows |
| analysis method / registry entry | 计算方法（方法页里的一个选项） | it is a choice, not a place |
| simulation run | 回测（一次回测 = 一次运行） | one word for the action and its result |
| experiment / variant / control | 对照比较 / 候选 / 基线 | 变体 and 对照 are lab words; 候选 and 基线 say what they do |
| provenance / manifest / sha256 | 用了哪份数据（版本与日期） | hashes belong in the record, not the sentence |
| dataset version | 数据版本 | fine, but only inside a detail view |
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
