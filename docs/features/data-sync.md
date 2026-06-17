# 市场数据（外部写入）

本系统**不负责**从 Tushare 或其他源同步数据。`tushare` schema 中的表由**外部 ETL / 数据管道**写入；本应用以 **只读** 方式查询，用于行情、选股、回测。

## 本系统做什么

| 能力 | 说明 |
|------|------|
| 读取 `tushare.*` | 行情、筛选、引擎、回测 |
| 数据新鲜度（规划） | `GET /api/data/status` — 各表 `MAX(trade_date)` |
| 因子计算（规划） | 读库计算 → 写入 `factor_values`，**不是**外部行情入库 |

## 本系统不做什么

- 发起 Tushare API 拉数  
- `/data` 页的 `data_sync` / `calendar_sync` 任务（**遗留功能，产品上不再规划**）  
- 维护 `TUSHARE_TOKEN` 作为核心部署条件（可选保留给遗留代码）

## 表结构契约

DDL 以 Alembic `002_market_data.py` 为准，外部管道需保持兼容：

- `stock_basic`, `stock_trade_daily`, `stock_adj_daily`, `daily_basic`, `dividends`, `trade_calendar`

字段说明见 [数据模型](data-models.md)。

## 联调检查

1. 外部 job 跑完后，PostgreSQL 中 `SELECT MAX(trade_date) FROM tushare.stock_trade_daily` 为预期交易日。  
2. 同日 `daily_basic` 行数与可 JOIN 的标的数量合理。  
3. 本系统 `/market` 与选股 job 能读到数据。

## 遗留实现（待废弃）

以下代码仍存在于仓库，**新功能不得依赖**：

- `backend/app/core/dataset/sync.py`  
- `JobService` 中 `data_sync`、`calendar_sync`  
- 前端 `DataCollection.tsx`（`/data`）

移除时间表见 [技术底座 — 遗留 sync](research/06-technical-enablers.md)。

## 相关文档

- [因子分析与选股 — 数据契约](research/07-factor-and-stock-selection.md)
- [数据与 API 策略](research/05-data-and-api-strategy.md)
- [配置](configuration.md) — `TUSHARE_TOKEN` 说明可视为遗留
