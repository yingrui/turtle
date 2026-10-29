"""Experiment 3: let the market decide whether momentum or reversal is the signal.

Momentum works while a trend persists and fails when it breaks; the difference is not in the stocks, it
is in the **market state**. So the sign of the momentum factor is taken from the index:

    regime(t) = 沪深300 close(t) > its 60-day moving average

- **trend**: score = +Σ (rank − 0.5) over the momentum family
- **reversal**: score = −Σ (rank − 0.5) over the same family

Only data up to and including `t` is used (the moving average is trailing, the close is today's close), so
there is no path for the forward-looking leak that invalidated experiment 2. No training, no fitted
weights.

    cd backend
    python -m scripts.regime_score --start 2024-06-03 --end 2026-09-30
"""

from __future__ import annotations

import argparse
from datetime import date

import pandas as pd
from sqlalchemy import text

from app.core.tushare_schema import tushare_table
from app.database import SessionLocal
from scripts.ic_weighted import evaluate
from scripts.scorecard import load_dataset

#: The momentum family whose sign the regime flips. One set, so the comparison stays honest.
MOMENTUM = ("mom_20d", "MACD", "ma_dev_20")


def market_regime(db, benchmark: str, start: date, end: date, window: int = 60) -> pd.Series:
    """`True` where the index closed above its own trailing mean — computed only from the past."""
    rows = pd.read_sql(
        text(
            f"SELECT trade_date, close FROM {tushare_table('index_daily')} "
            "WHERE ts_code = :code AND trade_date BETWEEN :start AND :end ORDER BY trade_date"
        ),
        db.connection(),
        params={"code": benchmark, "start": start - pd.Timedelta(days=window * 3).to_pytimedelta(),
                "end": end},
    )
    rows["ma"] = rows["close"].rolling(window).mean()
    rows["trend"] = rows["close"] > rows["ma"]
    return pd.Series(
        rows["trend"].to_numpy(), index=rows["trade_date"].astype(str)
    )


def score(frame: pd.DataFrame, factors: list[str], regime: pd.Series, flip: bool = True) -> pd.Series:
    """`+Σ(rank−0.5)` in a trend, `−Σ(rank−0.5)` otherwise (or one sign only, for the baselines)."""
    centred = frame[factors].sub(0.5).sum(axis=1)
    if not flip:
        return centred
    sign = frame["trade_date"].map(regime).fillna(False).map({True: 1.0, False: -1.0})
    return centred * sign.to_numpy()


def summarise(name: str, table: pd.DataFrame) -> None:
    positive = int((table["excess"] > 0).sum())
    print(
        f"{name:14} months {len(table):>3} · positive {positive:>3} "
        f"({positive / max(1, len(table)) * 100:>3.0f}%) · mean excess "
        f"{table['excess'].mean() * 100:+6.2f}% · mean AUC {table['auc'].mean():.3f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2024, 6, 3))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 9, 30))
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--benchmark", default="000300.SH")
    parser.add_argument("--ma-window", type=int, default=60, dest="ma_window")
    parser.add_argument("--top-n", type=int, default=50, dest="top_n")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        data = load_dataset(
            db, start=args.start, end=args.end, horizon=args.horizon, label="benchmark",
            benchmark=args.benchmark, exclude_st=True,
        )
        regime = market_regime(db, args.benchmark, args.start, args.end, args.ma_window)
    finally:
        db.close()

    frame = data.frame.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
    factors = [f for f in MOMENTUM if f in frame.columns]
    trend_share = float(frame["trade_date"].map(regime).fillna(False).mean())

    print(
        f"regime: 沪深300 vs MA{args.ma_window} · trend on {trend_share * 100:.0f}% of dates "
        f"· factors {', '.join(factors)} · horizon {args.horizon}"
    )
    variants = {
        "regime-aware": score(frame, factors, regime, flip=True),
        "always-mom": score(frame, factors, regime, flip=False),
        "always-rev": -score(frame, factors, regime, flip=False),
    }
    tables = {}
    for name, series in variants.items():
        scored = frame.assign(score=series.to_numpy()).dropna(subset=["score"])
        tables[name] = evaluate(scored, args.top_n)
        summarise(name, tables[name])

    if args.out:
        combined = pd.concat(tables, names=["variant"]).reset_index(level=0)
        combined.to_csv(args.out, index=False)
        print(f"written {args.out}")

    detail = tables["regime-aware"]
    print("\nregime-aware, per month:")
    print(detail.to_string(index=False, float_format=lambda v: f"{v:.4f}"))


if __name__ == "__main__":
    main()
