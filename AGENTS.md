# Project instructions

**股票交易系统** — 个人 A 股量化研究与回测 Web 应用。**factor analysis (因子) + stock picking (选股)** 是产品重心，不是数据管道，也不是券商终端。

对外部市场数据**只读**：行情由**外部 ETL** 写入 PostgreSQL schema `tushare`（本系统不做数据同步）；应用表在 `public`。

Canonical docs: `docs/`（MkDocs 站点，入口 `docs/index.md`）。本文件是给 coding agent 的速查约定；权威技术细节仍在 `docs/`。

## Goals

- 让个人用户在自有数据上完成闭环：**条件选股 → 回测 → 复盘 → 自选**。
- 阶段目标与优先级见 `docs/product-roadmap.md`、`docs/research/04-feature-backlog.md`、`docs/research/07-factor-and-stock-selection.md`。
- 近期重点：Phase 3 因子库（`factor_values` / `factor_definitions`、多因子 JSON 规则引擎、`/factor` 研究页）。

## Constraints

- **不做数据同步**：不在本系统内接 Tushare / 建抓数管道。`data_sync`、`calendar_sync` job 已被显式拒绝（400）。UI 需标注数据截至日期（`GET /api/data/status`）。
- **不做**：实时 L2、券商实盘、社交、Pine Script。
- 市场数据表放在 schema `tushare`，本系统只读；不要在应用层写这些表。
- 端口固定：backend **8200**、frontend **3200**；Compose 内 Postgres 5432（宿主机映射 5433）。

## Layout

| Path | Role |
|------|------|
| `backend/app/api/` | REST routers（auth、data、jobs、portfolios、screening、simulations、stocks、stock_pick） |
| `backend/app/models/` | ORM 模型（`public` schema） |
| `backend/app/services/` | 业务逻辑 + job runner |
| `backend/app/core/` | 交易引擎：`engine/`（policy、筛选）、`simulation/`、`dataset/`、`tushare_schema.py` |
| `backend/alembic/` | Schema 迁移（`001_initial`、`002_market_data`、`003_portfolios`） |
| `frontend/src/` | React 19 + Vite SPA；路由集中在 `App.tsx` |
| `frontend/src/styles/design-system/` | SCSS tokens（派生自 openKMS） |
| `docker/` | Dockerfile、`docker-compose.yml` |
| `docs/` | 文档站点 |

环境变量：`STOCK_*`（见 `docs/features/configuration.md`）；前端 API base 在 `frontend/src/config.ts`。

## Dev workflow

```bash
# 后端：venv + alembic upgrade head + uvicorn :8200
cd backend && ./dev.sh
# 前端：Vite dev :3200（/api 代理到 8200）
cd frontend && npm run dev
# 全栈
docker compose -f docker/docker-compose.yml up -d --build
```

测试与构建：

```bash
cd backend && source .venv/bin/activate && pytest tests/
cd frontend && npm run build && npm test
```

## Database & migrations

**Alembic 是唯一权威 DDL 来源。**

- 任何 `backend/app/models/` 改动或市场数据 DDL 变更 → 在 `backend/alembic/versions/` **新增迁移**，review 后再 upgrade。
- 从 `backend/` 用**项目 venv** 执行：`python -m alembic upgrade head` —— 不要用系统裸 `alembic`（`alembic/env.py` 会 prepend backend 路径，避免误导入其他 `app` 包，例如 openKMS）。
- 新 ORM 模型必须在 `backend/alembic/env.py` 的 import 中注册，autogenerate 才看得到。
- 市场数据表属 schema `tushare`：`op.execute("CREATE SCHEMA IF NOT EXISTS tushare")` 并限定表名，与 `app/core/tushare_schema.py` 保持一致。
- `app/main.py` lifespan 里的 `Base.metadata.create_all` **只是开发便利**；新表不要依赖它。

## Code conventions

- 后端同步 SQLAlchemy（FastAPI 同步路由）；引擎逻辑放 `app/core/`，路由保持薄。
- 写代码前先想清楚：说明假设、暴露取舍、有多解就问；路径不是最短时直说。**不要写超出请求范围的功能、抽象和配置项。**
- 改动要**外科手术式**：不顺手「改进」相邻代码或格式，不重构没坏的东西；匹配现有风格。只清理**自己**改动造成的孤儿 import/变量。发现无关死代码 → 提一句，别删。
- 把任务转成可验证目标（"加校验" → 先写非法输入测试再让它通过），多步任务先给简短计划。

## Doc and wording conventions

**SPA 文案**（`frontend/src/`）：只说功能**做什么**，不说**怎么存/怎么调**。避免出现 schema 名（`tushare`）、原始 `/api/…` URL、环境变量、引擎内部实现——除非该界面明确面向运维。SCSS 用 design-system token（`var(--color-*)`、`var(--space-*)`），见 `docs/design-system.md`。

**`docs/`**：可以写技术细节（Alembic revision、`STOCK_*`、`tushare` DDL）。保持与相邻文件一致的表格与标题风格，遵循 openKMS 式布局（`index.md`、`features/`、`developer/`、`operations/`）。

**Assistant 回复**：长度匹配任务，无填充话、无「随时说一声」式收尾；web URL 用 markdown 链接，仓库代码用 code citation。

**Commit**：简短**祈使句**标题（`Fix empty latest-date when market data missing`）；只有原因或风险不明显时才写 body。

## Docs before commit

提交时 review staged 变更，**只更新真正变化的文档**：

| File | When |
|------|------|
| `docs/architecture.md` | 新模块、流程、布局、端口 |
| `docs/features/<area>.md` | 该领域的功能与 UI |
| `docs/features/api-reference.md` | 新增 / 变更的 HTTP 端点 |
| `docs/features/data-models.md` | 新增表 / 列 / schema |
| `docs/features/configuration.md` | 新增或变更的 `STOCK_*` / 环境变量 |
| `docs/design-system.md` | 共享 SCSS token、模式或设计系统文件布局 |
| `docs/developer/setup.md` | 开发流程、Alembic、Postgres 设置 |
| `docs/operations/docker.md` | Compose 服务、端口、volume |

`docs/functionalities.md` 是路由索引 —— 仅在新增/删除功能页时改。

若 staged 变更触及 `docs/**`、`mkdocs.yml` 或 `docs/requirements.txt`，提交前验证：

```bash
pip install -r docs/requirements.txt
mkdocs build --strict --site-dir _site
```

文档更新与代码同一次提交。

## Definition of done

1. API + 测试。
2. SPA 接入。
3. 更新 `docs/features/api-reference.md` 与对应 feature 文档。
4. i18n（zh-CN + en）。
5. 标注数据截至日期；**不引入 sync 依赖**。

## Known tech debt

`simulation_service` 缺 settings 导入、`PortfolioFilter` print 刷屏、`Job.progress` 未更新 —— 随选股/回测改动顺带修，细节见 `docs/research/04-feature-backlog.md`。

## Skills

- `.openkms/skills/`（含 `openkms`、`wiki-*`）由 openKMS 管理，已被 `.gitignore` 忽略；保持不入 git。
- openKMS 数据操作（search / documents / wiki / KB）走 `python .openkms/skills/<skill_id>/scripts/cli.py …`，从项目根执行，不要 `cd` 进 skill 目录，不要 `pip install`。
