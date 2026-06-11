"""Chart data as JSON-serializable dicts for the frontend."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _series_to_list(s: pd.Series) -> list:
    return [None if pd.isna(v) else float(v) if isinstance(v, (np.floating, float)) else str(v) for v in s]


def _dates_to_list(s: pd.Series) -> list[str]:
    return [pd.Timestamp(v).strftime("%Y-%m-%d") for v in s]


def moving_average_chart(x_series, y_series, sma_days_list=None) -> dict:
    sma_days_list = sma_days_list or [5, 10, 20, 30]
    series = [{"name": "close", "data": _series_to_list(y_series)}]
    for days in sma_days_list:
        series.append({"name": f"MA{days}", "data": _series_to_list(y_series.rolling(days).mean())})
    return {"dates": _dates_to_list(x_series), "series": series}


def atr_chart(trade_date, close_price, daily_range, ma_days=350, atr_days=20, up=7, down=3) -> dict:
    sma = close_price.rolling(ma_days).mean()
    atr = daily_range.rolling(atr_days).mean()
    return {
        "dates": _dates_to_list(trade_date),
        "series": [
            {"name": "close", "data": _series_to_list(close_price)},
            {"name": "high", "data": _series_to_list(sma + atr * up)},
            {"name": "low", "data": _series_to_list(sma - atr * down)},
            {"name": f"MA{ma_days}", "data": _series_to_list(sma)},
        ],
    }


def bolling_chart(trade_date, close_price, ma_days=350, up=2, down=1.5) -> dict:
    sma = close_price.rolling(ma_days).mean()
    std = close_price.rolling(ma_days).std()
    return {
        "dates": _dates_to_list(trade_date),
        "series": [
            {"name": "close", "data": _series_to_list(close_price)},
            {"name": f"MA{ma_days}", "data": _series_to_list(sma)},
            {"name": f"upper_{up}std", "data": _series_to_list(sma + std * up)},
            {"name": f"lower_{down}std", "data": _series_to_list(sma - std * down)},
        ],
    }


def donchian_chart(trade_date, close_price, ma_days=150, up=20, down=10) -> dict:
    sma = close_price.rolling(ma_days).mean()
    return {
        "dates": _dates_to_list(trade_date),
        "series": [
            {"name": "close", "data": _series_to_list(close_price)},
            {"name": f"max_{up}", "data": _series_to_list(close_price.rolling(up).max())},
            {"name": f"min_{down}", "data": _series_to_list(close_price.rolling(down).min())},
            {"name": f"MA{ma_days}", "data": _series_to_list(sma)},
        ],
    }


def distribution_chart(x_series, y_series) -> dict:
    desc = y_series.describe()
    mean = float(desc["mean"])
    std = float(desc["std"])
    n = len(y_series)
    mean_line = [mean] * n
    return {
        "dates": _dates_to_list(x_series),
        "series": [
            {"name": "returns", "data": _series_to_list(y_series)},
            {"name": "mean", "data": mean_line},
            {"name": "+1σ", "data": [mean + std] * n},
            {"name": "-1σ", "data": [mean - std] * n},
            {"name": "+2σ", "data": [mean + 2 * std] * n},
            {"name": "-2σ", "data": [mean - 2 * std] * n},
        ],
        "stats": {"mean": mean, "std": std},
    }


def investment_log_chart(df: pd.DataFrame) -> dict:
    return {
        "dates": _dates_to_list(df["date"]),
        "series": [
            {"name": "total", "data": _series_to_list(df["total"] / 10000)},
            {"name": "position", "data": _series_to_list((df["total"] - df["balance"]) / 10000)},
        ],
    }
