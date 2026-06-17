# 因子分析与选股

本系统的**核心演进方向**：在**外部系统已写入 `tushare` schema** 的前提下，提供因子计算、截面分析、条件选股与研究闭环——对齐聚宽/同花顺「选股器 + 因子研究」，而非数据采集。

> **数据同步不在本系统范围内。** 行情、`daily_basic`、财务等表由外部管道维护；本系统只读 PostgreSQL，并在 UI 展示数据截至日期。

---

## 现状

| 能力 | 实现 | 局限 |
|------|------|------|
| 技术选股 | `PortfolioFilter` — 趋势 + ADF 平稳性 | 全市场 job，参数少，无因子截面 |
| 行情筛选 | `/market` 行业/涨跌/搜索 | 非因子逻辑，不能与回测因子一致 |
| 估值字段 | `daily_basic` 已在库 | 未暴露为可组合因子 |
| 回测 | 多 policy 模拟 | 与选股条件脱节 |
| 因子存储 | 无 | F-406 待建 |

当前 `/screening` 是**第一代选股**：引擎内硬编码规则，不是可配置因子表达式。

---

## 目标架构

```mermaid
flowchart TB
  subgraph external [外部系统 — 不在本仓库]
    ETL[ETL / Tushare 管道]
  end

  subgraph db [PostgreSQL tushare + public]
    RAW[stock_trade_daily / daily_basic / …]
    FACT[factor_values 规划中]
    APP[portfolios / simulation_*]
  end

  subgraph this [本系统]
    FC[因子计算服务]
    FS[选股引擎]
    UI[/screening /factor /market]
    SIM[回测]
  end

  ETL --> RAW
  FC --> FACT
  RAW --> FC
  FACT --> FS
  RAW --> FS
  FS --> UI
  FS --> SIM
  UI --> APP
```

---

## 因子分层

| 层级 | 示例 | 数据来源 | 更新频率 |
|------|------|----------|----------|
| **原始字段** | `pct_chg`, `circ_mv`, `pe_ttm`, `turnover_rate` | `daily_basic`, `stock_trade_daily` | 随外部 ETL |
| **衍生因子** | 20 日动量、60 日波动率、MA 偏离度 | 本系统计算，写入因子表 | 日终批任务 |
| **截面因子** | 行业内 PE 分位、市值分组 | 横截面 rank / z-score | 日终 |
| **复合条件** | 「PE&lt;30 且 动量&gt;0 且 ADF 非平稳」 | 选股 DSL 或 JSON 规则 | 按需 |

---

## 选股能力规划

### 阶段 A — 基本面 + 估值选股（近期）

利用已有 `daily_basic`，无需新同步：

| 能力 | 说明 |
|------|------|
| 条件面板 | PE/PB/PS/市值/换手率区间筛选 |
| 截面排序 | 按单因子降序/升序，取 Top N |
| 与 `/market` 联动 | 行业、板块条 → 预填选股条件 |
| 结果操作 | 加入自选、送入回测（F-203b） |

### 阶段 B — 因子库与批计算

| 能力 | 说明 |
|------|------|
| `factor_definitions` | 因子元数据：名称、公式、来源表 |
| `factor_values` | `(ts_code, trade_date, factor_id, value)` |
| 批任务 | 日终 job 计算动量、波动、均线距离等 |
| API | `GET /api/factors`, `GET /api/factors/{id}/values` |

### 阶段 C — 多因子选股与分析

| 能力 | 说明 |
|------|------|
| 多条件组合 | AND/OR，分组括号 |
| 因子相关性 | 选股前相关矩阵（防共线） |
| IC / 分层回测 | 单因子有效性检验（研究向） |
| 因子暴露 | 组合内各因子均值/分位 |

### 阶段 D — 与现有引擎统一

| 能力 | 说明 |
|------|------|
| 合并 `PortfolioFilter` | 趋势/ADF 作为可选因子节点 |
| 选股 = 回测标的池 | 同一 JSON 定义驱动 screening job 与 simulation |
| 个股详情 | 「因子雷达」Tab — 当日各因子分位 |

---

## 数据契约（对外部 ETL 的假设）

本系统**不实现**同步，但依赖以下约定：

| 要求 | 说明 |
|------|------|
| Schema | `tushare.*` 表结构与 Alembic `002` 一致 |
| 主键 | `(ts_code, trade_date)` 日线表可 upsert |
| 最新日 | 各表 `MAX(trade_date)` 一致或可查 |
| `daily_basic` | 与 `stock_trade_daily` 同日可 JOIN |
| 权限 | 应用 DB 用户对 `tushare` 有 SELECT |

可选：外部系统写入 **`tushare.data_freshness`** 元数据表（表名、最新日期、更新时间），本系统 `/api/data/status` 只读展示——**非同步任务**。

---

## API  sketch（规划）

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/data/status` | 各表最新 `trade_date`（只读，替代 sync job） |
| GET | `/api/factors` | 因子目录 |
| POST | `/api/factors/compute` | 触发日终因子计算 job |
| POST | `/api/stock-pick` | 条件选股（JSON 规则 → 标的列表） |
| GET | `/api/stock-pick/presets` | 内置模板（低 PE、高动量等） |
| POST | `/api/jobs` type=`factor_screen` | 异步全市场选股 |

现有 `POST /api/screening`、`portfolio_screen` job 逐步迁移为 `stock-pick` 的一种 preset。

---

## UI 规划

| 路由 | 用途 |
|------|------|
| `/screening` | 升级为「选股中心」：条件 + 结果 + 导出 |
| `/factor`（新） | 因子列表、单因子分布、IC 研究（阶段 C） |
| `/market` | 浏览；选中条件「复制到选股」 |
| `/stocks/:tsCode` | 因子分位 Tab |

---

## 与待办 ID 对应

| ID | 内容 | 优先级 |
|----|------|--------|
| F-501 | 估值/基本面条件选股（daily_basic） | P0 |
| F-502 | `GET /api/data/status` 只读新鲜度 | P0 |
| F-503 | 选股结果 → 自选 / 回测 | P0（原 F-203b） |
| F-504 | `factor_values` schema + 动量/波动批算 | P1 |
| F-505 | 多因子 JSON 规则引擎 | P1 |
| F-506 | `/factor` 研究页 | P2 |
| F-507 | 单因子 IC / 分层检验 | P2 |
| F-406 | 因子库（与 F-504 合并规划） | P1 |

原 **F-105、F-211**（本系统内数据同步）**取消**。

---

## 相关文档

- [功能待办](04-feature-backlog.md)
- [数据与 API 策略](05-data-and-api-strategy.md)
- [筛选与分析（现有）](../features/screening-and-analysis.md)
