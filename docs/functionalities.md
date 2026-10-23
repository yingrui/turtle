# Functionalities

Index of stock trading features. Each page links to behaviour, API routes, and related tables.

> Market data in `tushare` is **loaded by an external system**; this app reads it only. Product focus: **factor analysis** and **stock picking**.

## Trading & research

Sidebar is grouped by task: **研究** (工作台/选股/因子/行情) · **组合** (组合/回测) · **设置**.

| Feature | Doc | SPA route |
|---------|-----|-----------|
| Workbench (今日待办) | [Design system](design-system.md) | `/` |
| Market quotes (universe) | [Stock universe](features/stock-universe.md) | `/market`, `/stocks/:tsCode` |
| Stock picking (选股) | [Screening & factors](features/screening-and-analysis.md) | `/screening` |
| Factor library (因子) | [Factors](features/factors.md) | `/factor`, `/factor/:code` |
| Portfolios & watchlist | [Portfolios](features/portfolios.md) | `/portfolio?tab=holdings&status=…` (`/watchlist` redirects) |
| Backtest simulation | [Simulation](features/simulation.md) | `/simulation`, `/simulation/results` |
| Charts & forecast | [Screening & analysis](features/screening-and-analysis.md) | `/stocks`, `/forecast` |
| Settings | [Configuration](features/configuration.md) | `/settings` |
| Background jobs / data status | [Simulation](features/simulation.md) / [Data models](features/data-models.md) | `/jobs`, `/data` (secondary) |

## Data (external)

| Feature | Doc |
|---------|-----|
| Market data contract | [External data](features/data-sync.md) — **not in-app sync** |

Legacy: `/data` page and `data_sync` jobs exist in code but are **out of product scope**.

## Platform

| Feature | Doc |
|---------|-----|
| Local JWT auth | [Auth](features/auth.md) |
| Configuration | [Configuration](features/configuration.md) |
| Database tables | [Data models](features/data-models.md) |
| HTTP routes | [API reference](features/api-reference.md) |

## Research & roadmap

| Topic | Doc |
|-------|-----|
| Product roadmap | [product-roadmap.md](product-roadmap.md) |
| Feature backlog (中文) | [research/README.md](research/README.md) |

## Operations

| Topic | Doc |
|-------|-----|
| Docker Compose | [Operations · Docker](operations/docker.md) |
| Kubernetes / openKMS App | [Operations · Kubernetes](operations/kubernetes.md) |
| Host development | [Developer setup](developer/setup.md) |
| Frontend styling | [Design system](design-system.md) |
