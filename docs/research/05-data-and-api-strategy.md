# 数据与 API 策略

本系统对 **`tushare` schema 只读**；表数据由**外部 ETL** 写入。本文说明数据假设、因子/选股所需字段，以及 API 规划。

---

## 战略边界

| 在本系统内 | 不在本系统内 |
|------------|--------------|
| 读 PostgreSQL 做行情、选股、回测 | Tushare 拉数、定时 sync job |
| 展示各表最新 `trade_date` | `/data` 页发起 data_sync |
| 日终 **因子计算** job（读库 → 写 factor 表） | 日线/分钟线 **入库** |

遗留代码 `app/core/dataset/sync.py`、`data_sync` job 类型视为**待废弃**，文档与新功能不再依赖。

---

## 现有表（只读消费）

| 表 | 用途 | 选股/因子 |
|----|------|-----------|
| `stock_basic` | 代码、行业、上市状态 | universe、行业过滤 |
| `stock_trade_daily` | OHLCV、pct_chg | 动量、波动、技术因子 |
| `stock_adj_daily` | 复权因子 | 前复权序列 |
| `daily_basic` | PE/PB/市值/换手/limit_status | **基本面选股核心** |
| `trade_calendar` | 交易日 | 因子批算对齐交易日 |
| `dividends` | 分红 | 回测除权 |

应用 schema：`portfolios`、`simulation_*`、`jobs`（仅存选股/回测任务，非 sync）。

---

## 规划中的因子表（public 或 tushare）

| 表 | 用途 |
|----|------|
| `factor_definitions` | 因子 id、名称、公式类型、参数 |
| `factor_values` | `(ts_code, trade_date, factor_id, value)` |

详见 [因子分析与选股](07-factor-and-stock-selection.md)。

---

## daily_basic → 选股字段

| 字段 | 选股用途 |
|------|----------|
| `pe`, `pe_ttm`, `pb`, `ps`, `ps_ttm` | 估值区间 |
| `total_mv`, `circ_mv` | 市值分层、加权 |
| `turnover_rate`, `turnover_rate_f`, `volume_ratio` | 流动性 |
| `limit_status` | 排除涨跌停/停牌 |
| `dv_ratio`, `dv_ttm` | 股息策略 |

单位：`circ_mv`/`total_mv` 为 **万元**。

---

## API 现状

### 股票 — 已有

`GET /universe`、`/universe/meta`、`/universe/industry-summary`、`/search`、`/{ts_code}/snapshot|ohlcv|indicators`、`POST /{ts_code}/forecast`

### 筛选 — 已有（待升级）

- `POST /api/screening` — 同步趋势+ADF  
- `POST /api/jobs` type=`portfolio_screen`

### 规划 — 选股与因子

| 接口 | 用途 | 待办 |
|------|------|------|
| `GET /api/data/status` | 各 tushare 表最新日期 | F-502 |
| `POST /api/stock-pick` | 多条件选股（JSON 规则） | F-501、F-505 |
| `GET /api/stock-pick/presets` | 内置模板 | F-501 |
| `GET /api/factors` | 因子目录 | F-504 |
| `POST /api/jobs` type=`factor_compute` | 日终因子批算 | F-504 |
| `POST /api/jobs` type=`factor_screen` | 异步全市场选股 | F-505 |
| `GET /api/factors/{id}/ic` | 单因子 IC（研究） | F-507 |

### 组合 / 回测 — 规划

| 接口 | 用途 |
|------|------|
| simulation job + `ts_codes[]` | F-503 |
| `GET /api/simulations/by-stock/{ts_code}` | 个股回测 Tab |

---

## 对外部 ETL 的数据契约

| 要求 | 说明 |
|------|------|
| Schema 与 Alembic `002` 一致 | 列名、类型兼容 |
| 日线表主键 | `(ts_code, trade_date)` |
| `daily_basic` 与 `daily` 同日可 JOIN | 选股与行业加权 |
| 应用 DB 用户 | `SELECT` on `tushare` |
| 可选元数据表 | `data_freshness(table_name, latest_date, updated_at)` |

本系统**不校验** Tushare token；`TUSHARE_TOKEN` 配置可逐步从部署文档中弱化。

---

## 性能（读路径）

| 手段 | 场景 |
|------|------|
| 物化 `latest_quotes` | 全市场列表、自选行情 F-212 |
| 因子表按 `(factor_id, trade_date)` 索引 | 截面选股 F-504 |
| 预计算分位 | 个股因子 Tab F-104 |

~~按交易日历 sync~~ — 已移除。

---

## 相关文档

- [因子分析与选股](07-factor-and-stock-selection.md)
- [数据模型](../features/data-models.md)
- [外部数据说明](../features/data-sync.md)（只读契约）
- [API 参考](../features/api-reference.md)
