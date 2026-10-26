"""Apply one day's ranking to a portfolio: pool, rules, decisions.

Run it for a trading day after that day's factors exist:

    cd backend
    python -m scripts.daily_selection --portfolio main --date 2026-10-09
    python -m scripts.daily_selection --portfolio main --date 2026-10-09 --dry-run

The model is the promoted scorecard (`reports/runs/<id>/model.json`) or an explicit `--model`. Its
`run_id` and the dataset version it was trained on travel into every event, so a decision can be
explained later: which model, which data, what rank, which rule.

This records **decisions**, not fills: a `bought` event means the rule said buy. Cash, lot sizes,
costs and corporate actions belong to the trading layer.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import select, text

from app.database import SessionLocal
from app.models import FactorDefinition, Portfolio
from app.services.portfolio_lifecycle_service import (
    LifecycleError,
    SelectionRules,
    apply_daily_selection,
)
from scripts.scorecard import NEUTRAL_RANK, excluded_codes, score_frame

REPORTS = Path(__file__).resolve().parents[2] / "reports"


def load_model(path: str | None, run_id: str | None) -> tuple[dict, Path]:
    if path:
        model_path = Path(path)
    elif run_id:
        model_path = REPORTS / "runs" / run_id / "model.json"
    else:
        candidates = sorted((REPORTS / "runs").glob("*/model.json")) if (REPORTS / "runs").exists() else []
        if candidates:
            model_path = candidates[-1]
        else:
            model_path = REPORTS / "scorecard_5d_relative.json"
    if not model_path.exists():
        raise SystemExit(f"no model at {model_path}: train one or pass --model")
    return json.loads(model_path.read_text()), model_path


def load_scores(db, codes: list[str], day: date) -> pd.DataFrame:
    """The day's cross-section, scored exactly the way the model was trained (within-date ranks)."""
    values = pd.read_sql(
        text(
            "SELECT v.trade_date, v.ts_code, f.code, v.value "
            "FROM factor_values v JOIN factor_definitions f ON f.id = v.factor_id "
            "WHERE v.trade_date = :day AND f.code = ANY(:codes)"
        ),
        db.connection(),
        params={"day": day, "codes": codes},
    )
    if values.empty:
        raise SystemExit(f"no factor values for {day}: compute that day's factors first")
    # The gate the training data already applied: a scorecard that recommends *ST or a delisting
    # name is not usable, so they are removed before ranking rather than filtered afterwards.
    skip = excluded_codes(db, True)
    if skip:
        values = values[~values["ts_code"].isin(skip)]
    ranks = values.pivot_table(index=["trade_date", "ts_code"], columns="code", values="value")
    ranks = ranks.reindex(columns=codes).rank(pct=True).fillna(NEUTRAL_RANK).reset_index()
    return ranks


def freshness(db, codes: list[str], day: date) -> list[str]:
    """Factors whose newest value is older than the target day — the gate that stops silent decay."""
    stale = []
    for code in codes:
        latest = db.scalar(
            text(
                "SELECT max(v.trade_date) FROM factor_values v JOIN factor_definitions f "
                "ON f.id = v.factor_id WHERE f.code = :code"
            ),
            {"code": code},
        )
        if latest is None or latest < day:
            stale.append(f"{code}@{latest}")
    return stale


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--portfolio", required=True)
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    parser.add_argument("--model", default=None, help="model json path")
    parser.add_argument("--run", default=None, help="run id under reports/runs/")
    parser.add_argument("--top-n", type=int, default=None, help="pool size (default: model top_n or 50)")
    parser.add_argument("--buy-rank-limit", type=int, default=None)
    parser.add_argument("--sell-rank-limit", type=int, default=None)
    parser.add_argument("--max-holding-days", type=int, default=None)
    parser.add_argument("--drop-after-absent-days", type=int, default=30)
    parser.add_argument("--ignore-stale", action="store_true", help="score even if factors are stale")
    parser.add_argument("--dry-run", action="store_true", help="print the decisions, write nothing")
    args = parser.parse_args()

    model, model_path = load_model(args.model, args.run)
    codes = [factor["code"] for factor in model["factors"]]

    db = SessionLocal()
    try:
        portfolio = db.scalar(select(Portfolio).where(Portfolio.name == args.portfolio))
        if portfolio is None:
            raise SystemExit(f"no portfolio named {args.portfolio}")

        stale = freshness(db, codes, args.date)
        if stale and not args.ignore_stale:
            raise SystemExit(
                "factors are older than the target date: " + ", ".join(stale) + " — compute them first"
            )

        ranked = load_scores(db, codes, args.date)
        ranked["score"] = score_frame(model, ranked.drop(columns=["trade_date"]))
        ranked = ranked.sort_values("score", ascending=False).reset_index(drop=True)
        ranked["rank"] = range(1, len(ranked) + 1)

        rules = SelectionRules(
            top_n=args.top_n or int(model.get("metrics", {}).get("top_n") or 50),
            buy_rank_limit=args.buy_rank_limit,
            sell_rank_limit=args.sell_rank_limit,
            max_holding_days=args.max_holding_days,
            drop_after_absent_days=args.drop_after_absent_days,
        )
        rankings = [(row.ts_code, float(row.score), int(row.rank)) for row in ranked.itertuples()]

        print(
            f"{len(rankings):,} stocks scored for {args.date} · model {model_path.name} "
            f"· pool {rules.top_n} · buy ≤{rules.buy_rank_limit} · sell >{rules.sell_rank_limit}"
        )
        print("top 10: " + ", ".join(f"{code}({score:.3f})" for code, score, _ in rankings[:10]))

        if args.dry_run:
            print("dry run: nothing written")
            return

        try:
            result = apply_daily_selection(
                db,
                portfolio_id=portfolio.id,
                trade_date=args.date,
                rankings=rankings,
                rules=rules,
                model={
                    "name": Path(model_path.parent).name if model.get("run_id") else "scorecard",
                    "version": model.get("run_id") or None,
                    "dataset_version": model.get("dataset_version"),
                },
            )
        except LifecycleError as exc:
            raise SystemExit(str(exc)) from exc

        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=1))
    finally:
        db.close()


if __name__ == "__main__":
    main()
