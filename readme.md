# 个人股票交易系统

本项目为个人提供一个中国股票市场分析、筛选与回测的 Web 交易系统。

A personal stock trading web app for Chinese A-share markets — data sync, portfolio management, screening, and multi-policy backtesting.

## Documentation

Full docs live in **[`docs/`](docs/index.md)** (MkDocs layout, same structure as [openKMS](https://github.com/yingrui/openKMS)):

| Topic | Link |
|-------|------|
| Quickstart (Docker / host) | [docs/quickstart.md](docs/quickstart.md) |
| Architecture | [docs/architecture.md](docs/architecture.md) |
| Features & API | [docs/functionalities.md](docs/functionalities.md) |
| Configuration | [docs/features/configuration.md](docs/features/configuration.md) |
| Developer setup | [docs/developer/setup.md](docs/developer/setup.md) |

```bash
pip install -r docs/requirements.txt && mkdocs serve   # optional local docs site
```

## Quick start

```bash
cp docker/.env.example docker/.env   # set TUSHARE_TOKEN
docker compose -f docker/docker-compose.yml up -d --build
open http://localhost:3200
```

Local dev: [docs/quickstart.md](docs/quickstart.md#option-b--backend-and-frontend-on-the-host).

## Layout

| Path | Role |
|------|------|
| `backend/` | FastAPI, trading engine (`app/core/`), Alembic |
| `frontend/` | React SPA (openKMS-derived design system) |
| `docker/` | Compose stack |
| `docs/` | Documentation |

## Tests

```bash
cd backend && pytest tests/
```
