"""Experiment 2: score by trailing information coefficient — no training at all.

The scorecard fits **one** coefficient per factor over the whole training window. When the market's
style flips, those coefficients keep pointing the old way: that is exactly what the 2025-11 and
2026-02 failures looked like.

This scores the cross-section with **the factor's own recent IC** as weight:

    score(t) = Σ_f  IC̄_f(t-1) · (rank_f(t) − 0.5)

where `IC̄_f(t-1)` is the mean cross-sectional Spearman correlation between factor `f` and the forward
return over the `--lookback` sessions *before* t. A factor that has been working keeps its weight; one
that flipped gets a negative weight, which is the same as inverting it. No model, no training, no
overfitting to a window — just "what worked lately, weighted by how much".

    cd backend
    python -m scripts.ic_weighted --start 2024-06-03 --end 2026-09-30 --lookback 60
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

from app.database import SessionLocal
from scripts.scorecard import auc, load_dataset

REPORTS = Path(__file__).resolve().parents[2] / "reports"


def per_date_ic(frame: pd.DataFrame, factors: list[str]) -> pd.DataFrame:
    """Cross-sectional Spearman IC of every factor, per date (one row per date)."""
    rows = []
    for day, part in frame.groupby("trade_date"):
        if len(part) < 100:
            continue
        ic = part[factors].corrwith(part["fwd_ret"], method="spearman")
        ic["trade_date"] = day
        rows.append(ic)
    return pd.DataFrame(rows).set_index("trade_date").sort_index()


def score_with_rolling_ic(
    frame: pd.DataFrame, factors: list[str], ic: pd.DataFrame, lookback: int
) -> pd.DataFrame:
    """Weight each date's ranks by the mean IC of the preceding `lookback` sessions."""
    # shift(1): today's weight may only use ICs measured before today.
    weights = ic.rolling(lookback, min_periods=max(20, lookback // 3)).mean().shift(1)
    centred = frame[factors].sub(0.5)
    score = pd.Series(0.0, index=frame.index)
    for factor in factors:
        score += weights[factor].reindex(frame["trade_date"]).to_numpy() * centred[factor].to_numpy()
    return frame.assign(score=score.to_numpy())


def evaluate(scored: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """Per month: AUC on the ranking, and what top-N would have earned over the universe."""
    out = []
    for month, part in scored.groupby(scored["trade_date"].str[:7]):
        if part["label"].nunique() < 2:
            continue
        picks = (
            part.sort_values(["trade_date", "score"], ascending=[True, False])
            .groupby("trade_date")
            .head(top_n)
        )
        per_date = picks.groupby("trade_date").agg(picked=("fwd_ret", "mean"))
        universe = part.groupby("trade_date").agg(all=("fwd_ret", "mean"))
        joined = per_date.join(universe)
        out.append(
            {
                "month": month,
                "auc": auc(part["score"].to_numpy(), part["label"].to_numpy()),
                "picked": joined["picked"].mean(),
                "universe": joined["all"].mean(),
                "excess": (joined["picked"] - joined["all"]).mean(),
                "dates": len(joined),
            }
        )
    return pd.DataFrame(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2024, 6, 3))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 9, 30))
    parser.add_argument("--lookback", type=int, default=60, help="sessions of IC used as the weight")
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--label", default="benchmark", choices=("relative", "absolute", "benchmark"))
    parser.add_argument("--benchmark", default="000300.SH")
    parser.add_argument("--top-n", type=int, default=50, dest="top_n")
    parser.add_argument("--out", default=None, help="write the per-month table as CSV")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        data = load_dataset(
            db,
            start=args.start,
            end=args.end,
            horizon=args.horizon,
            label=args.label,
            benchmark=args.benchmark,
            exclude_st=True,
        )
    finally:
        db.close()

    frame = data.frame.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
    ic = per_date_ic(frame, data.factors)
    scored = score_with_rolling_ic(frame, data.factors, ic, args.lookback)
    scored = scored.dropna(subset=["score"])
    table = evaluate(scored, args.top_n)

    print(
        f"IC-weighted · lookback {args.lookback} · horizon {args.horizon} · label {args.label} "
        f"· {len(scored):,} rows · {scored['trade_date'].nunique()} dates"
    )
    print(table.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    positive = int((table["excess"] > 0).sum())
    print(
        f"\nmonths {len(table)} · excess positive {positive} "
        f"({positive / max(1, len(table)) * 100:.0f}%) · mean excess {table['excess'].mean() * 100:+.2f}% "
        f"· mean AUC {table['auc'].mean():.3f}"
    )
    if args.out:
        table.to_csv(args.out, index=False)
        print(f"written {args.out}")


if __name__ == "__main__":
    main()
