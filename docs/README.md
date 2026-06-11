# 股票交易系统 docs

Navigable documentation for the stock trading web app. Structure follows [openKMS](https://github.com/yingrui/openKMS) (`docs/` + MkDocs Material).

If you are reading this on GitHub, start at:

- [Home (index)](index.md) — overview, ports, where to read what
- [Quickstart](quickstart.md) — Docker or host dev
- [Architecture](architecture.md) — how backend, frontend, and DB fit together
- [Functionalities](functionalities.md) — feature index
- [Developer setup](developer/setup.md) — venv, Alembic, PostgreSQL grants
- [Operations · Docker](operations/docker.md) — Compose stack
- [Design system](design-system.md) — SCSS tokens and conventions

Build locally (optional):

```bash
pip install -r docs/requirements.txt
mkdocs serve
```

Site config: `mkdocs.yml` at the repo root.
