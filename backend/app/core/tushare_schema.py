"""PostgreSQL schema for Tushare market data tables."""

TUSHARE_SCHEMA = "tushare"


def tushare_table(name: str) -> str:
    return f"{TUSHARE_SCHEMA}.{name}"
