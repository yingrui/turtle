# Portfolios

Portfolio configuration is stored in PostgreSQL (`portfolios` table), not YAML files on disk. The UI provides a YAML editor for convenience; the API accepts both JSON and YAML.

## SPA

Route: **`/portfolio`**

Create, select, edit, and delete named portfolios. Config structure matches the legacy YAML format used by the trading engine (`app/core/configurer.py`).

## API

See [API reference — Portfolios](api-reference.md#portfolios-apportfolios).

- `GET /api/portfolios/{name}/yaml` — serialize config for the editor
- `PUT /api/portfolios/{name}/yaml` — parse YAML and save

## Engine usage

Simulation and screening services load config via `PortfolioService(db).get_portfolio(name)` before running the engine in `app/core/`.
