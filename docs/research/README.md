# 产品研究

**股票交易系统** 的产品与工程研究：接下来做什么、为什么做、按什么顺序做。

本目录是对 [产品路线图](../product-roadmap.md) 的深化补充。

> **战略边界（2026-06）：** 市场数据 **由外部系统写入 `tushare` schema**，本系统**不再规划数据同步**；产品重心转向 **因子分析** 与 **选股**。

| 文档 | 回答的问题 |
|------|------------|
| [产品定位](01-product-positioning.md) | 为谁做？明确不做什么？ |
| [竞品能力](02-competitor-capabilities.md) | 东财/同花顺/雪球/TradingView/聚宽 差距 |
| [用户动线](03-user-workflows.md) | 今天怎么走 vs 理想怎么走 |
| [功能待办](04-feature-backlog.md) | 优先级、影响、工作量 |
| [数据与 API](05-data-and-api-strategy.md) | 只读数据契约、接口规划 |
| [技术底座](06-technical-enablers.md) | 任务、性能、多用户 |
| [因子分析与选股](07-factor-and-stock-selection.md) | **核心方向**：因子库、选股、与回测联动 |

## 如何使用

1. **规划迭代** — [因子分析与选股](07-factor-and-stock-selection.md) + [功能待办](04-feature-backlog.md) P0。
2. **设计选股/因子页** — [用户动线](03-user-workflows.md) + [竞品能力](02-competitor-capabilities.md)。
3. **对接外部 ETL** — [数据与 API](05-data-and-api-strategy.md) 中的数据契约。

## 与路线图的关系

| 文档 | 范围 |
|------|------|
| `product-roadmap.md` | 阶段里程碑与上线顺序 |
| `research/*` | 依据、因子/选股细节、待办评分 |

## 最近审阅

2026-06-11 — 数据同步划归外部系统；确立因子分析 + 选股为核心演进方向。
