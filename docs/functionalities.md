# Functionalities

Index of stock trading features. Each page links to behaviour, API routes, and related tables.

## Trading & data

| Feature | Doc | SPA route |
|---------|-----|-----------|
| Market data sync | [Data sync](features/data-sync.md) | `/data` |
| Market quotes (universe) | [Stock universe](features/stock-universe.md) | `/market`, `/stocks/:tsCode` |
| Portfolios (DB-backed config) | [Portfolios](features/portfolios.md) | `/portfolio` |
| Stock screening | [Screening & analysis](features/screening-and-analysis.md) | `/screening` |
| Backtest simulation | [Simulation](features/simulation.md) | `/simulation`, `/simulation/results` |
| Single-stock charts & forecast | [Screening & analysis](features/screening-and-analysis.md) | `/stocks`, `/forecast` |
| Background jobs | [Data sync](features/data-sync.md) | `/jobs` |

## Platform

| Feature | Doc |
|---------|-----|
| Local JWT auth | [Auth](features/auth.md) |
| Environment variables | [Configuration](features/configuration.md) |
| Database tables | [Data models](features/data-models.md) |
| HTTP routes | [API reference](features/api-reference.md) |

## Operations

| Topic | Doc |
|-------|-----|
| Docker Compose | [Operations · Docker](operations/docker.md) |
| Host development | [Developer setup](developer/setup.md) |
| Frontend styling | [Design system](design-system.md) |
