"""Scorecard model over the factor library: rank stocks by how likely they are to outperform.

Run it by hand; nothing here is wired into the API or the SPA. Four subcommands share one dataset
builder, so the analysis, the fit, and a prediction cannot disagree about what the data means.

    cd backend
    python -m scripts.scorecard data     --start 2026-06-01 --end 2026-10-09
    python -m scripts.scorecard analyze  --start 2026-06-01 --end 2026-10-09
    python -m scripts.scorecard train    --start 2026-06-01 --end 2026-10-09 --top-n 10
    python -m scripts.scorecard score    --date 2026-10-09 --top 10

The label is **relative**: a stock is "good" on day t when its forward return beats that day's
median. Predicting up-versus-down would mostly learn the market's direction (beta), which is not
what a stock-picking score is for; the cross-section is what we can rank.

Two deliberate choices keep the model honest:

- **Cross-sectional ranks, not raw values.** Factors live on wildly different scales and their
  distributions drift, so each factor is ranked within its date (0..1) and bucketed into deciles.
  A bin therefore means "top decile of momentum that day", not "value above 3.2".
- **Time split, never random.** The last `--holdout` fraction of dates is held out. A random split
  would let the same day's cross-section sit in both halves and report a model that cannot exist.

No scikit-learn: WOE binning is a groupby, and the fit is ridge-penalised logistic regression by
Newton's method, both in numpy. The artifact is JSON so a score run needs nothing but this file.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from app.database import SessionLocal
from app.models import FactorDefinition

MODEL_DIR = Path(__file__).resolve().parents[2] / "reports"
BINS = 10
#: Missing factor values are ranked neutral rather than dropped: one absent factor out of nineteen
#: should not remove the stock, but it must not look like a strong signal either.
NEUTRAL_RANK = 0.5


# --- data -------------------------------------------------------------------------------


@dataclass
class Dataset:
    """One row per stock per day: factor ranks, the forward return, and the label."""

    frame: pd.DataFrame
    factors: list[str]
    dates: list[date] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.frame)


def _factor_codes(db) -> list[str]:
    return [
        code
        for code in db.scalars(
            FactorDefinition.__table__.select()
            .with_only_columns(FactorDefinition.code)
            .where(FactorDefinition.formula.isnot(None))
            .order_by(FactorDefinition.code)
        ).all()
    ]


def forward_returns(prices: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Enter at the next session's open, exit at the close `horizon` sessions after the signal.

    Buying on the close that produced the signal is not something a reader of this table could have
    done, so the entry is always the next open.
    """
    prices = prices.sort_values(["ts_code", "trade_date"])
    grouped = prices.groupby("ts_code", sort=False)
    prices = prices.assign(
        entry=grouped["open"].shift(-1),
        exit=grouped["close"].shift(-horizon),
    )
    prices = prices.assign(fwd_ret=prices["exit"] / prices["entry"] - 1)
    return prices[["trade_date", "ts_code", "fwd_ret"]]


def excluded_codes(db, exclude_st: bool) -> list[str]:
    """ST and delisting names. A scorecard that recommends a *ST stock is not usable."""
    if not exclude_st:
        return []
    rows = db.execute(
        text(
            "SELECT ts_code FROM tushare.stock_basic "
            "WHERE name LIKE :st OR name LIKE :delisting OR name LIKE :delisting_cn"
        ),
        {"st": "%ST%", "delisting": "%退%", "delisting_cn": "%退市%"},
    ).all()
    return [row[0] for row in rows]


def load_dataset(
    db,
    *,
    start: date,
    end: date,
    horizon: int = 5,
    label: str = "relative",
    factors: list[str] | None = None,
    exclude_st: bool = True,
) -> Dataset:
    """Join factor values to forward returns and rank everything within its date."""
    codes = factors or _factor_codes(db)
    price_end = end + timedelta(days=horizon * 3 + 10)

    values = pd.read_sql(
        text(
            "SELECT v.trade_date, v.ts_code, f.code, v.value "
            "FROM factor_values v JOIN factor_definitions f ON f.id = v.factor_id "
            "WHERE v.trade_date BETWEEN :start AND :end AND f.code = ANY(:codes)"
        ),
        db.connection(),
        params={"start": start, "end": end, "codes": codes},
    )
    if values.empty:
        raise SystemExit("no factor values in that window — compute some factors first")
    wide = values.pivot_table(
        index=["trade_date", "ts_code"], columns="code", values="value"
    ).reset_index()

    prices = pd.read_sql(
        text(
            "SELECT ts_code, trade_date, open, close FROM tushare.stock_trade_daily "
            "WHERE trade_date BETWEEN :start AND :end ORDER BY ts_code, trade_date"
        ),
        db.connection(),
        params={"start": start, "end": price_end},
    )
    if prices.empty:
        raise SystemExit("no market data in that window")
    frame = wide.merge(forward_returns(prices, horizon), on=["trade_date", "ts_code"], how="inner")
    frame = frame.dropna(subset=["fwd_ret"])
    skip = excluded_codes(db, exclude_st)
    if skip:
        frame = frame[~frame["ts_code"].isin(skip)]
    if frame.empty:
        raise SystemExit("no rows with both factors and a forward return")

    present = [code for code in codes if code in frame.columns]
    ranks = frame.groupby("trade_date")[present].rank(pct=True)
    ranks = ranks.fillna(NEUTRAL_RANK)
    dates = sorted(frame["trade_date"].unique())
    out = pd.concat([frame[["trade_date", "ts_code", "fwd_ret"]], ranks], axis=1)
    if label == "relative":
        median = out.groupby("trade_date")["fwd_ret"].transform("median")
        out["label"] = (out["fwd_ret"] > median).astype(int)
    elif label == "absolute":
        out["label"] = (out["fwd_ret"] > 0).astype(int)
    else:
        raise SystemExit(f"unknown label kind: {label}")
    return Dataset(frame=out, factors=present, dates=[pd.Timestamp(d).date() for d in dates])


# --- statistics -------------------------------------------------------------------------


def woe_table(ranks: pd.Series, labels: pd.Series, bins: int = BINS) -> pd.DataFrame:
    """Good/bad counts, WOE and IV per rank decile.

    ``good`` is an outperformer. The 0.5 added to every count keeps a bin with no positives from
    producing an infinite WOE — the usual scorecard smoothing.
    """
    index = np.clip((ranks.to_numpy() * bins).astype(int), 0, bins - 1)
    frame = pd.DataFrame({"bin": index, "label": labels.to_numpy()})
    grouped = frame.groupby("bin")["label"].agg(good="sum", n="count")
    grouped["bad"] = grouped["n"] - grouped["good"]
    total_good, total_bad = grouped["good"].sum(), grouped["bad"].sum()
    good_rate = (grouped["good"] + 0.5) / (total_good + 0.5 * bins)
    bad_rate = (grouped["bad"] + 0.5) / (total_bad + 0.5 * bins)
    grouped["woe"] = np.log(good_rate / bad_rate)
    grouped["iv"] = (good_rate - bad_rate) * grouped["woe"]
    grouped["good_rate"] = grouped["good"] / grouped["n"].replace(0, np.nan)
    return grouped


def rank_ic(frame: pd.DataFrame, factor: str) -> tuple[float, float]:
    """Cross-sectional Spearman IC per date: mean and information ratio."""
    def _ic(part: pd.DataFrame) -> float:
        if len(part) < 30 or part[factor].nunique() < 2:
            return np.nan
        with warnings.catch_warnings():          # a flat cross-section has no correlation
            warnings.simplefilter("ignore")
            return part[factor].corr(part["fwd_ret"], method="spearman")

    per_date = frame.groupby("trade_date").apply(_ic, include_groups=False)
    per_date = per_date.dropna()
    if len(per_date) < 3 or per_date.std() == 0:
        return float("nan"), float("nan")
    return float(per_date.mean()), float(per_date.mean() / per_date.std())


def auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Rank-based AUC (Mann–Whitney), no sklearn."""
    positives = labels == 1
    n_pos, n_neg = positives.sum(), (~positives).sum()
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = pd.Series(scores).rank(method="average").to_numpy()
    return float((order[positives].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def fit_logit(X: np.ndarray, y: np.ndarray, l2: float = 1.0, iters: int = 60) -> np.ndarray:
    """Ridge-penalised logistic regression by Newton's method. The intercept is not penalised."""
    beta = np.zeros(X.shape[1])
    penalty = np.eye(X.shape[1]) * l2
    penalty[0, 0] = 0.0
    for _ in range(iters):
        eta = np.clip(X @ beta, -30, 30)
        mu = 1.0 / (1.0 + np.exp(-eta))
        weights = np.clip(mu * (1.0 - mu), 1e-9, None)
        gradient = X.T @ (y - mu) - penalty @ beta
        hessian = X.T @ (X * weights[:, None]) + penalty
        try:
            step = np.linalg.solve(hessian, gradient)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(hessian, gradient, rcond=None)[0]
        beta = beta + step
        if np.max(np.abs(step)) < 1e-8:
            break
    return beta


# --- model ------------------------------------------------------------------------------


def build_model(
    train: Dataset,
    *,
    horizon: int,
    label: str,
    min_iv: float,
    max_corr: float,
) -> dict:
    """Pick factors by IV, prune correlated ones, then fit WOE → logistic → points."""
    stats_rows = []
    for code in train.factors:
        table = woe_table(train.frame[code], train.frame["label"])
        ic_mean, ic_ir = rank_ic(train.frame, code)
        stats_rows.append(
            {"code": code, "iv": float(table["iv"].sum()), "ic_mean": ic_mean, "ic_ir": ic_ir}
        )
    stats = pd.DataFrame(stats_rows).sort_values("iv", ascending=False)

    selected: list[str] = []
    for code in stats.loc[stats["iv"] >= min_iv, "code"]:
        if all(
            abs(train.frame[code].corr(train.frame[other], method="spearman")) <= max_corr
            for other in selected
        ):
            selected.append(code)
    if not selected:
        raise SystemExit(
            f"no factor reached IV >= {min_iv}; lower the threshold or widen the window"
        )

    tables = {}
    design = np.ones((len(train.frame), len(selected) + 1))
    for column, code in enumerate(selected, start=1):
        table = woe_table(train.frame[code], train.frame["label"])
        tables[code] = table
        index = np.clip(
            (train.frame[code].to_numpy() * BINS).astype(int), 0, BINS - 1
        )
        design[:, column] = table["woe"].reindex(index).to_numpy()

    beta = fit_logit(design, train.frame["label"].to_numpy())

    metrics = {
        "train_auc": auc(design @ beta, train.frame["label"].to_numpy()),
        "n_train": int(len(train.frame)),
    }
    return {
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "horizon": horizon,
        "label_kind": label,
        "bins": BINS,
        "intercept": float(beta[0]),
        "factors": [
            {
                "code": code,
                "coef": float(beta[i]),
                "iv": float(stats.set_index("code").loc[code, "iv"]),
                "ic_mean": float(stats.set_index("code").loc[code, "ic_mean"]),
                "ic_ir": float(stats.set_index("code").loc[code, "ic_ir"]),
                "woe": [float(value) for value in tables[code]["woe"].reindex(range(BINS)).fillna(0)],
            }
            for i, code in enumerate(selected, start=1)
        ],
        "train_window": [train.dates[0].isoformat(), train.dates[-1].isoformat()],
        "metrics": metrics,
    }


def score_frame(model: dict, ranks: pd.DataFrame) -> np.ndarray:
    """Points: intercept plus each factor's WOE times its coefficient."""
    score = np.full(len(ranks), model["intercept"])
    for factor in model["factors"]:
        ranks_series = ranks[factor["code"]].fillna(NEUTRAL_RANK)
        index = np.clip((ranks_series.to_numpy() * model["bins"]).astype(int), 0, model["bins"] - 1)
        woe = np.asarray(factor["woe"])[index]
        score += factor["coef"] * woe
    return score


# --- reports ----------------------------------------------------------------------------


def _fmt(value: float, digits: int = 4) -> str:
    return "—" if value is None or (isinstance(value, float) and math.isnan(value)) else f"{value:.{digits}f}"


def cmd_data(args, db) -> None:
    data = load_dataset(
        db,
        start=args.start,
        end=args.end,
        horizon=args.horizon,
        label=args.label,
        exclude_st=not args.include_st,
    )
    print(f"rows {len(data):,} · dates {len(data.dates)} · factors {len(data.factors)}")
    print(f"window {data.dates[0]} → {data.dates[-1]}")
    print(f"label rate (outperformers) {data.frame['label'].mean():.3f}")
    print("\nper-date rows and label rate:")
    per_date = data.frame.groupby("trade_date").agg(rows=("label", "size"), rate=("label", "mean"))
    print(per_date.tail(8).to_string())


def cmd_analyze(args, db) -> None:
    data = load_dataset(
        db,
        start=args.start,
        end=args.end,
        horizon=args.horizon,
        label=args.label,
        exclude_st=not args.include_st,
    )
    print(f"rows {len(data):,} · dates {len(data.dates)} · window {data.dates[0]} → {data.dates[-1]}\n")
    rows = []
    for code in data.factors:
        table = woe_table(data.frame[code], data.frame["label"])
        ic_mean, ic_ir = rank_ic(data.frame, code)
        rows.append(
            {
                "factor": code,
                "iv": table["iv"].sum(),
                "ic_mean": ic_mean,
                "ic_ir": ic_ir,
                "top_decile_rate": table["good_rate"].iloc[-1],
                "bottom_decile_rate": table["good_rate"].iloc[0],
            }
        )
    report = pd.DataFrame(rows).sort_values("iv", ascending=False)
    print("factor diagnostics (IV > 0.02 weak, > 0.1 useful):")
    print(report.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print("\nmost correlated pairs (|rho| > 0.6, prune before fitting):")
    corr = data.frame[data.factors].corr(method="spearman").abs()
    pairs = [
        (corr.columns[i], corr.columns[j], corr.iloc[i, j])
        for i in range(len(corr)) for j in range(i + 1, len(corr))
        if corr.iloc[i, j] > 0.6
    ]
    if pairs:
        for a, b, rho in sorted(pairs, key=lambda p: -p[2])[:10]:
            print(f"  {a:24} {b:24} {rho:.3f}")
    else:
        print("  none")


def cmd_train(args, db) -> None:
    data = load_dataset(
        db,
        start=args.start,
        end=args.end,
        horizon=args.horizon,
        label=args.label,
        exclude_st=not args.include_st,
    )
    cut = max(1, int(len(data.dates) * (1 - args.holdout)))
    if cut >= len(data.dates):
        raise SystemExit("holdout leaves nothing to test on; widen the window")
    train_dates, test_dates = set(data.dates[:cut]), set(data.dates[cut:])
    train = Dataset(
        frame=data.frame[data.frame["trade_date"].isin(train_dates)],
        factors=data.factors,
        dates=data.dates[:cut],
    )
    test_frame = data.frame[data.frame["trade_date"].isin(test_dates)]

    model = build_model(
        train, horizon=args.horizon, label=args.label, min_iv=args.min_iv, max_corr=args.max_corr
    )
    model["holdout_window"] = [data.dates[cut].isoformat(), data.dates[-1].isoformat()]

    test_scores = score_frame(model, test_frame)
    test_labels = test_frame["label"].to_numpy()
    model["metrics"].update(
        {
            "test_auc": auc(test_scores, test_labels),
            "n_test": int(len(test_frame)),
            "factors_used": len(model["factors"]),
        }
    )

    # Forward evidence: what the top-N would actually have earned on the held-out dates.
    scored = test_frame[["trade_date", "ts_code", "fwd_ret", "label"]].copy()
    scored["score"] = test_scores
    picks = scored.sort_values(["trade_date", "score"], ascending=[True, False]).groupby(
        "trade_date"
    ).head(args.top_n)
    per_date = picks.groupby("trade_date").agg(
        picked_ret=("fwd_ret", "mean"), picked_hit=("fwd_ret", lambda s: (s > 0).mean())
    )
    universe = scored.groupby("trade_date").agg(
        universe_ret=("fwd_ret", "mean"), universe_hit=("fwd_ret", lambda s: (s > 0).mean())
    )
    backtest = per_date.join(universe)
    backtest["excess"] = backtest["picked_ret"] - backtest["universe_ret"]
    model["metrics"].update(
        {
            "top_n": args.top_n,
            "picked_mean_ret": float(backtest["picked_ret"].mean()),
            "universe_mean_ret": float(backtest["universe_ret"].mean()),
            "mean_excess": float(backtest["excess"].mean()),
            "picked_hit_rate": float(backtest["picked_hit"].mean()),
            "excess_positive_dates": float((backtest["excess"] > 0).mean()),
        }
    )

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"scorecard_{args.horizon}d_{args.label}"
    path = MODEL_DIR / f"{stem}.json"
    path.write_text(json.dumps(model, indent=1))

    print(f"train {model['train_window'][0]} → {model['train_window'][1]}  ({len(train.frame):,} rows)")
    print(f"test  {model['holdout_window'][0]} → {model['holdout_window'][1]}  ({len(test_frame):,} rows)")
    print(f"\nfitted {len(model['factors'])} of {len(data.factors)} factors:")
    for factor in model["factors"]:
        print(
            f"  {factor['code']:24} coef {factor['coef']:+.3f}  IV {factor['iv']:.3f}  "
            f"IC {_fmt(factor['ic_mean'])}  IC-IR {_fmt(factor['ic_ir'])}"
        )
    metrics = model["metrics"]
    print(
        f"\nAUC train {_fmt(metrics['train_auc'], 3)} · test {_fmt(metrics['test_auc'], 3)}"
    )
    print(
        f"top-{args.top_n} on held-out dates: mean {metrics['picked_mean_ret'] * 100:+.2f}% "
        f"vs universe {metrics['universe_mean_ret'] * 100:+.2f}% "
        f"(excess {metrics['mean_excess'] * 100:+.2f}%, "
        f"{metrics['excess_positive_dates'] * 100:.0f}% of dates ahead)"
    )
    print(f"\nper-date, held-out:")
    print(backtest.assign(**{c: backtest[c] * 100 for c in ("picked_ret", "universe_ret", "excess")})
          .to_string(float_format=lambda v: f"{v:+.2f}"))
    print(f"\nmodel saved to {path}")


def cmd_score(args, db) -> None:
    path = Path(args.model) if args.model else MODEL_DIR / f"scorecard_{args.horizon}d_{args.label}.json"
    if not path.exists():
        raise SystemExit(f"no model at {path}; run `train` first")
    model = json.loads(path.read_text())
    codes = [factor["code"] for factor in model["factors"]]

    values = pd.read_sql(
        text(
            "SELECT v.trade_date, v.ts_code, f.code, v.value "
            "FROM factor_values v JOIN factor_definitions f ON f.id = v.factor_id "
            "WHERE v.trade_date = :day AND f.code = ANY(:codes)"
        ),
        db.connection(),
        params={"day": args.date, "codes": codes},
    )
    skip = excluded_codes(db, not args.include_st)
    if skip:
        values = values[~values["ts_code"].isin(skip)]
    if values.empty:
        raise SystemExit(f"no factor values for {args.date}; compute them first")
    ranks = values.pivot_table(index=["trade_date", "ts_code"], columns="code", values="value")
    ranks = ranks.reindex(columns=codes)
    ranks = ranks.rank(pct=True).fillna(NEUTRAL_RANK).reset_index()

    ranks["score"] = score_frame(model, ranks)
    names = pd.read_sql(
        text("SELECT ts_code, name, industry FROM tushare.stock_basic"),
        db.connection(),
    )
    ranked = ranks.sort_values("score", ascending=False).head(args.top)
    ranked = ranked.merge(names, on="ts_code", how="left")

    print(
        f"model {path.name} · trained {model['trained_at']} · horizon {model['horizon']} sessions "
        f"· {len(model['factors'])} factors"
    )
    print(f"top {args.top} for {args.date} (out of {len(ranks):,} stocks scored)\n")
    header = f"{'rank':>4} {'ts_code':12} {'name':10} {'industry':10} {'score':>8}"
    print(header)
    for position, row in enumerate(ranked.itertuples(), start=1):
        print(
            f"{position:>4} {row.ts_code:12} {(row.name or ''):10} {(row.industry or ''):10} "
            f"{row.score:>8.3f}"
        )
    print("\ncontributions (coef × WOE) for the first pick:")
    first = ranked.iloc[0]
    parts = []
    for factor in model["factors"]:
        rank_value = first[factor["code"]]
        index = int(min(rank_value * model["bins"], model["bins"] - 1))
        parts.append((factor["code"], factor["coef"] * factor["woe"][index]))
    for code, contribution in sorted(parts, key=lambda p: -abs(p[1])):
        print(f"  {code:24} {contribution:+.3f}")


# --- cli ---------------------------------------------------------------------------------


def _date(value: str) -> date:
    return date.fromisoformat(value)


def main(argv: list[str] | None = None) -> None:
    # The window options belong to every subcommand, so a run reads left to right the way it is
    # written in this module's docstring: `score --date …`, `train --holdout 0.25`.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--start", type=_date, default=None, help="first signal date")
    common.add_argument("--end", type=_date, default=None, help="last signal date")
    common.add_argument("--horizon", type=int, default=5, help="holding sessions (default 5)")
    common.add_argument(
        "--label", choices=("relative", "absolute"), default="relative",
        help="relative = beat that day's median (default); absolute = positive return",
    )
    common.add_argument(
        "--include-st", action="store_true",
        help="keep ST / delisting names (excluded by default)",
    )

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("data", parents=[common], help="load the dataset and describe it")
    sub.add_parser("analyze", parents=[common], help="IV / IC / correlation report per factor")

    train = sub.add_parser(
        "train", parents=[common], help="fit the scorecard and print its held-out behaviour"
    )
    train.add_argument("--holdout", type=float, default=0.25, help="fraction of dates held out")
    train.add_argument(
        "--min-iv", type=float, default=0.02, help="keep factors at least this informative"
    )
    train.add_argument(
        "--max-corr", type=float, default=0.7,
        help="drop a factor above this |rho| with one already kept",
    )
    train.add_argument("--top-n", type=int, default=10, help="stocks the backtest would have held")

    score = sub.add_parser("score", parents=[common], help="rank one day and print the top N")
    score.add_argument("--date", type=_date, required=True)
    score.add_argument("--top", type=int, default=10)
    score.add_argument(
        "--model", default=None,
        help="model json path (default: reports/scorecard_<h>d_<label>.json)",
    )

    args = parser.parse_args(argv)
    db = SessionLocal()
    try:
        latest = db.scalar(text("SELECT max(trade_date) FROM factor_values"))
        if latest is None:
            raise SystemExit("no factor values at all; compute some factors first")
        args.end = args.end or latest
        args.start = args.start or args.end - timedelta(days=180)
        {"data": cmd_data, "analyze": cmd_analyze, "train": cmd_train, "score": cmd_score}[
            args.command
        ](args, db)
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
