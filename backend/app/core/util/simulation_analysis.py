"""Simulation result analysis helpers."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from app.core.engine.StockRepository import StockRepository
from app.core.util.math_methods import round_down


def _row_date(value) -> date:
    """Normalize DB date, pandas Timestamp, or numpy datetime64 to datetime.date."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()


def calculate_cagr(policy_id: int, df: pd.DataFrame) -> dict:
    start_date = _row_date(df.date.values[0])
    end_date = _row_date(df.date.values[-1])
    years = end_date.year - start_date.year if end_date.year > start_date.year else 1
    initial_total = float(df.total.values[0])
    total = float(df.total.values[-1])
    cagr = round_down((total / initial_total) ** (1 / years) - 1)
    return_rate = round_down(total / initial_total * 100)
    return {
        "policy_id": policy_id,
        "initial_total": initial_total,
        "total": total,
        "years": years,
        "return_rate_pct": return_rate,
        "cagr": cagr,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }


def get_stock_benefit(policy_id: int, df_trade: pd.DataFrame) -> pd.DataFrame:
    df_benefit = df_trade[["ts_code", "benefit"]].groupby(["ts_code"]).sum().rename(
        columns={"benefit": f"sum_{policy_id}"}
    )
    df_win = df_trade[df_trade["status"] == "win"]
    df_loss = df_trade[df_trade["status"] == "loss"]
    for prefix, subset in [("win", df_win), ("loss", df_loss)]:
        df_benefit = df_benefit.join(
            subset[["ts_code", "benefit"]].groupby(["ts_code"]).sum().rename(columns={"benefit": f"{prefix}_{policy_id}"}),
            how="left",
        )
        df_benefit = df_benefit.join(
            subset[["ts_code", "benefit"]].groupby(["ts_code"]).count().rename(
                columns={"benefit": f"{'w' if prefix == 'win' else 'l'}_cnt_{policy_id}"}
            ),
            how="left",
        )
    return df_benefit


def load_simulation_logs_from_disk(portfolio_name: str, total_policies: int, follow_stocks: list[str], logs_folder: str):
    stock_repo = StockRepository()
    stocks = [stock_repo.find_stock(stock) for stock in follow_stocks]
    df_stocks = pd.DataFrame([{"ts_code": stock.ts_code, "name": stock.name} for stock in stocks])

    df_list = []
    for pid in range(total_policies):
        df = pd.read_csv(f"{logs_folder}/{portfolio_name}-{pid}.log", parse_dates=["date"])
        df_list.append(df)

    df_trade_list = []
    for pid in range(total_policies):
        df_trade = pd.read_csv(
            f"{logs_folder}/trade_{portfolio_name}-{pid}.log", parse_dates=["date", "hold_date"]
        )
        df_trade = pd.merge(df_trade, df_stocks, on="ts_code", how="left")
        df_trade_list.append(df_trade)

    df_benefit = get_stock_benefit(0, df_trade_list[0])
    df_benefit = pd.merge(df_stocks, df_benefit, on="ts_code", how="left")
    for pid in range(1, total_policies):
        df_benefit = pd.merge(df_benefit, get_stock_benefit(pid, df_trade_list[pid]), on="ts_code", how="outer")

    return df_list, df_trade_list, df_benefit


def max_drawdown_pct(totals) -> float:
    """Worst peak-to-trough decline of the equity series, as a negative percentage."""
    peak = None
    worst = 0.0
    for value in totals:
        total = float(value)
        peak = total if peak is None else max(peak, total)
        if peak:
            worst = min(worst, (total / peak - 1) * 100)
    return round_down(worst)


def summarize_run(policy_id: int, daily_df: pd.DataFrame, trades_df: pd.DataFrame) -> dict:
    """The stored summary of one run. Pure, so the migration backfill and the live path agree.

    ``daily_df`` needs ``date`` and ``total``; ``trades_df`` needs ``ts_code``/``side``/``shares``/
    ``benefit`` (sell rows only carry a realised benefit).
    """
    if daily_df is None or daily_df.empty:
        return {}
    summary = calculate_cagr(policy_id, daily_df)
    totals = [float(v) for v in daily_df.total.values]
    sells = trades_df[trades_df["side"] == "sell"] if not trades_df.empty else trades_df
    wins = int((sells["benefit"] > 0).sum()) if not sells.empty else 0
    losses = int((sells["benefit"] <= 0).sum()) if not sells.empty else 0
    # Net open positions after replaying the run's trades.
    positions: dict[str, int] = {}
    if not trades_df.empty:
        for row in trades_df.itertuples():
            delta = int(row.shares) * (1 if row.side == "buy" else -1)
            positions[row.ts_code] = positions.get(row.ts_code, 0) + delta
    return {
        "window_start": _row_date(summary["start_date"]),
        "window_end": _row_date(summary["end_date"]),
        "initial_total": summary["initial_total"],
        "final_total": summary["total"],
        "return_rate_pct": summary["return_rate_pct"],
        "cagr": summary["cagr"],
        "years": summary["years"],
        "max_drawdown_pct": max_drawdown_pct(totals),
        "win_count": wins,
        "loss_count": losses,
        "holding_count": sum(1 for shares in positions.values() if shares > 0),
        "trade_count": int(len(trades_df)),
    }
