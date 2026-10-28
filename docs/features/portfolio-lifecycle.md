# 组合生命周期与每日选股

**已实现**（`backend/app/services/portfolio_lifecycle_service.py`、`scripts/daily_selection.py`）。

目标：每天按模型对全市场打分，用最后的 Top-50 维护组合里的**候选池**（观察状态），再由交易规则决定买/卖；用户要能查到**过去任意一天组合里有哪些股票**。

这份稿子只定义 turtle 侧的结构与语义；模型训练、AUC/IC 分析是**线下脚本**（见 [Scorecard](../developer/scorecard.md)），不在这条链路里。数据侧的版本化方案见 openKMS 的 `datasets-files` 设计稿。

## 状态：四个词，两个维度

| 状态 | 含义 | 有持仓 | 在组合里 |
|---|---|---|---|
| `watching` | 在池中，未持有 | ✗ | ✓ |
| `holding` | 持有中 | ✓ | ✓ |
| `closed` | 卖出过（回合结束），票仍留在组合里 | ✗ | ✓ |
| `dropped` | 已移出组合（软删除，行保留） | ✗ | ✗ |

- **`closed` 与 `dropped` 不同**：`closed` 是"卖掉了"，这只票还在组合的视野里；`dropped` 是"不在组合里了"。
- **重新进池 = 复活，不是插入**：`portfolio_stocks` 上有 `UNIQUE(portfolio_id, ts_code)`，一只票第二次进入只能是 `dropped/closed → watching` 的状态变更，不能新增一行。
- 因此同一只票在一个组合里会有**多个回合（episode）**：建仓 → 卖出 → 再建仓。回合号是持有天数、单次收益、胜率的分组键，必须有。

## 每日流程

```
1. 数据新鲜度闸门：目标日的因子 last_date 必须 = 目标日，否则当天不跑（明确失败，不静默降级）
2. 打分：用当日的因子值 + 当日生效的模型版本 → 全市场分数与排名
3. Top-50 → 更新候选池（只改 watching 资格，不动持仓）
4. 交易规则：对 holding 判定卖出；对 watching 判定买入
5. 写回：状态变更 + 事件 + 成交（成交走已有的 Action/台账路径）
```

三条边界：

- **排名只决定"谁有资格"**，不决定买卖。掉出 Top-50 的持仓**不自动卖**，等卖出规则触发。
- **Top-50 差异小是正常的**：排名稳定的日子里，第 3 步只会复活/新增少量票；这本身不是问题，也说明不需要每日大换手。
- **`dropped` 不由排名产生**：掉出 Top-50 不等于移出组合。移出只能由显式规则或人工操作触发（例如连续 N 天不在池且无持仓、或人工清理）。

## 表结构

### 1. `portfolio_stocks` 增列

```sql
ALTER TABLE portfolio_stocks
  ADD COLUMN joined_at  date,         -- 本回合进入组合的日期
  ADD COLUMN left_at    date,         -- 本回合移出组合的日期（dropped 时写入）
  ADD COLUMN episode    integer default 1,   -- 第几个回合
  ADD COLUMN dropped_at timestamptz;  -- 软删除时间（status='dropped' 时写入）
```

`status` 取值扩为 `watching | holding | closed | dropped`。

### 2. `portfolio_stock_events`（新表，append-only）

```sql
CREATE TABLE portfolio_stock_events (
  id            uuid PRIMARY KEY,
  portfolio_id  uuid NOT NULL,
  ts_code       varchar(16) NOT NULL,
  trade_date    date NOT NULL,
  event         varchar(24) NOT NULL,   -- added | resurrected | status_changed | removed
  from_status   varchar(16),
  to_status     varchar(16),
  episode       integer NOT NULL,
  score         numeric(18,6),          -- 当日评分（人工操作时为空）
  rank          integer,                -- 当日全市场排名
  reason        varchar(255),           -- 例如 "in_top_50" / "ma_cross" / "manual"
  rule          varchar(64),            -- 触发的规则名
  rule_params   jsonb,                  -- 规则参数快照
  model_name    varchar(128),           -- 当日生效的模型
  model_version integer,
  dataset_version integer,              -- 训练该模型所用的数据版本
  source        varchar(16) NOT NULL,   -- simulation | manual
  created_at    timestamptz default now(),
  UNIQUE (portfolio_id, trade_date, ts_code, event)   -- 幂等
);
```

`UNIQUE(...)` 是**每日任务的幂等键**：job 是进程内线程，重启会重跑，同一天重跑不能产生第二条事件。

**状态与事件必须同事务写入**，并且事件是唯一写入口：任何地方都不应直接 `UPDATE status`，否则事件与状态会分叉，历史就不可信了。

### 3. 为什么还要"某天有哪些票"的快速查询

事件表能回答"为什么"，但回答"那一天组合里有哪些票"需要按日 replay。既然**只需要成员资格、不需要恢复状态机**，最直接的是**区间查询**：

```sql
-- 2026-11-02 这天，组合 main 里有哪些股票（含状态）
SELECT ts_code, status, episode, joined_at, left_at
FROM portfolio_stocks
WHERE portfolio_id = :pf
  AND joined_at <= :day
  AND (left_at IS NULL OR left_at > :day);
```

一行索引扫描，与事件表无关。事件表负责审计与归因，`joined_at/left_at/episode` 负责成员资格。

若之后要按历史价格算当天市值，再加一层"当日持仓快照"（`positions_daily`：组合×日期×代码×数量×收盘价×市值），并作为 dataset 暴露给 openKMS；这一层是查询加速，不改变上面的写入语义。

## 与模型/数据版本的关系

事件表记录 `(model_name, model_version, dataset_version)`，于是：

- "2026-11-02 为什么买 600519" 可以答到：第 7 版模型、用第 3 版训练集、当天排名第 12、触发 `ma_cross`；
- 排序依据（分数/排名）**按日落库**，模型的输入（因子值）本来就在 `factor_values` 里按日可查；
- 每日生效的模型版本必须**按日固定**，不能先查 alias 再跑（alias 中途变更会让同一天的两次运行结果不同）。

## 幂等与失败处理

| 场景 | 处理 |
|---|---|
| 同一天重跑 | `(portfolio, trade_date)` 幂等键；已存在则跳过或以"覆盖本次结果"的方式重算（事件唯一键保证不重复） |
| 部分成交失败 | 保留失败明细，下一次运行前先做对账（目标状态 vs 台账实际持仓），补单而非重下单 |
| 数据新鲜度不足 | 当天标记为 skipped，并在任务结果里写明原因，不用旧因子打分 |

## 与 openKMS 的边界

| 内容 | 归属 |
|---|---|
| 每日决策记录（事件、分数、原因、版本） | **turtle**（应用自己的账） |
| 当前持仓/观察池（`Holding` 对象） | openKMS 只镜像当前状态 |
| 历史查询（某天组合里有哪些票） | turtle 的表；需要 agent 查询时把表注册成 dataset |
| 训练期指标（AUC / IC / excess） | 线下脚本，不进每日 pipeline |
| 训练集版本与文件 | openKMS 的 Datasets（文件型数据集） |

## 已实现的部分

| 内容 | 位置 |
|---|---|
| `portfolio_stocks` 的 `joined_at` / `left_at` / `episode` / `dropped_at` / `last_seen_in_pool` | 迁移 `009` |
| `portfolio_stock_events`（append-only，唯一键 = (portfolio, trade_date, ts_code, event)） | 迁移 `009` |
| 观察池 + 买卖规则 + 弃用规则，写状态与事件同事务 | `app/services/portfolio_lifecycle_service.py` |
| `GET /api/portfolios/{name}/members?day=` · `GET /api/portfolios/{name}/events?day=` | `app/api/portfolios.py` |
| 每日选股脚本（模型打分 → 规则 → 决策），带因子新鲜度闸门 | `scripts/daily_selection.py` |
| 每月一个模型：`--date` 按月份解析对应模型，`--all-days --month` 回放整月 | `scripts/daily_selection.py` + `reports/models/<policy>/index.json` |
| 月度训练与 MLflow 记录 | `scripts/train_monthly.py`、`scripts/mlflow_tracking.py` |
| 训练切片导出（parquet）并发布成 openKMS 文件数据集版本 | `scripts/export_training_set.py` |
| 训练集样本构造 | `scripts/scorecard.py`（`load_dataset`） |

实测：`python -m scripts.daily_selection --portfolio main --date 2026-09-30` 为 `main` 写入 10 条
`added` + 10 条 `bought`（排名 1–10 进入池并触发买入规则），`/members?day=2026-09-30` 返回这 10 只。

## 股票池：固定 vs 动态

组合的股票池现在有两个来源，由 `portfolios.active_run_id` 决定：

| `active_run_id` | 池来源 | 含义 |
|---|---|---|
| 空 | `portfolio_stocks` | 手工维护的自选列表（旧行为） |
| 指向某次 run | 该 run 的池 | `pool_mode=fixed` 用 run 配置里的自选列表；`pool_mode=dynamic` 用**当天模型选出的 top-N** |

- 信号回测（`mode=signal`）的池是**固定**的，就是配置里的 `follow_stocks`，所以不逐日存行；
- 模型回测（`mode=model`）的池是**动态**的，每天写入 `simulation_pool`（代码、排名、分数、当天是否真的持有）。

```http
POST /api/portfolios/{name}/active-run   {"run_id": "…"}   # 绑定（null 解绑，回到手工列表）
GET  /api/portfolios/{name}/pool?day=2026-05-14            # 组合的股票池（按日）
GET  /api/simulations/{run}/pool?day=…                     # 某次 run 的股票池
GET  /api/simulations/{run}/pool-dates                     # 它有池的日期（动态池才有）
```

**持仓与成交同样跟随绑定的 run**：`GET /portfolios/{name}/stocks`（可带 `?day=`）与
`/transactions` 在绑定了 run 时返回该 run 的持仓与成交（响应带 `source: "run"` 与 `available_dates`），
解绑后回到 `portfolio_stocks` / 组合自己的账本（`source: "portfolio"`）。所以"组合的持仓/成交"和
"回测的账本"是同一份事实，不再两处各说一套。

前端在组合页新增 **股票池** 标签页：选择池来源（手工列表 / 某次 run）、看当前池，动态池还能按日期回看；
持仓标签在 run 模式下带日期选择器与"来自 run"的提示，成交标签直接显示该 run 的成交。

## 首次回放：`top50-sim`（2026-02 → 2026-10）

新建组合 `top50-sim`，启动资金 100 万、初始为空；每月用"该月之前的数据训练"的模型，没有模型的月份
沿用最近一个更早的模型（`--policy expanding` 的显式回退，绝不会用未来模型）。每天都按 Top-50 更新
观察池、按规则买卖，并按等权 + 100 股整数倍 + 佣金/印花税落成**纸面成交**。

| 月末 | 权益 | 持仓数 | 现金 | 累计收益 |
|---|---|---|---|---|
| 2026-02 | 1,036,949 | 49 | 61,441 | +3.7% |
| 2026-03 | 944,745 | 53 | 2,420 | −5.5% |
| 2026-04 | 931,387 | 50 | 13,189 | −6.9% |
| 2026-05 | 872,803 | 50 | 11,698 | −12.7% |
| 2026-06 | 784,816 | 51 | 1,011 | −21.5% |
| 2026-07 | 819,638 | 51 | 4,118 | −18.0% |
| 2026-08 | 859,958 | 51 | 4,393 | −14.0% |
| 2026-09 | 830,802 | 52 | 8,868 | −16.9% |
| 2026-10 | 854,094 | 52 | 6,137 | **−14.6%** |

147 个交易日、5,450 笔成交，最大回撤 −24.6%。

三个必须一起看的对照：

| 指标 | 值 |
|---|---|
| 同期全市场等权（5,435 只，2026-02-02 → 2026-10-09） | 均值 **−11.6%**、中位数 −17.7%、上涨占比 22% |
| 成交额合计 | **4,751 万**（≈ 初始资金的 47 倍） |
| 佣金 + 印花税 | **75,194**（初始资金的 **7.5%**） |

也就是说：**毛收益大约 −7.6%，比全市场等权的 −11.6% 好；净收益 −14.6%，被 7.5% 的交易成本吃掉了。**
问题不在选股方向，而在**每天重排 50 只带来的换手**：平均每天 5–8 笔买卖，一个月六七个来回。

下一步优先顺序（成本影响最大）：把重排频率降到每周、或给卖出加迟滞（连续 N 天掉出池才卖），
目标是把换手压到现在的 1/5，成本降到 1.5% 以内；之后再谈模型本身。

## 后续（不在本期，但要留位置）

- **可交易性闸门**：停牌、次日开盘一字板（买不到）、上市不足 N 日、成交额/换手率下限；
- **资金约束**：A 股一手 100 股、单票上限、行业上限、现金缓冲（当前 `target_weight` 引擎不读）；
- **成本模型**：佣金 + 印花税（仅卖出），每日重排的换手率会显著吞掉 alpha；
- **企业行动**：分红、送转、拆股会改变股数与成本价，按"目标股数"覆盖写会造出不存在的卖出；
- **调度**：以 `trade_calendar` 为准，收盘后计算、次日开盘执行。
