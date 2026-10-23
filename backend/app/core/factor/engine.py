"""Factor panel: market data reshaped wide, and a tiny expression language over it.

A factor formula is evaluated on a **panel** — one DataFrame per field, all indexed by
``trade_date`` with one column per ``ts_code``. Widening first is what makes the language small:
every time-series operator is a column-wise ``rolling``/``shift``, and every cross-sectional
operator is a row-wise ``rank``/``zscore``, so neither needs a groupby over five thousand codes.

Formulas are plain expressions over field names and the functions registered in ``FUNCTIONS``
(``ma(close, 20)``, ``close / shift(close, 20) - 1``). They are parsed and every AST node is
checked against an allow-list before evaluation, so a stored formula cannot reach the interpreter.
"""

from __future__ import annotations

import ast
import operator
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy import text

#: Columns a formula may read. Anything else is a definition-only factor.
FIELDS: dict[str, str] = {
    # tushare.stock_trade_daily
    "open": "trade",
    "high": "trade",
    "low": "trade",
    "close": "trade",
    "pre_close": "trade",
    "pct_chg": "trade",
    "vol": "trade",
    "amount": "trade",
    # tushare.daily_basic
    "turnover_rate": "basic",
    "turnover_rate_f": "basic",
    "volume_ratio": "basic",
    "pe": "basic",
    "pe_ttm": "basic",
    "pb": "basic",
    "ps": "basic",
    "ps_ttm": "basic",
    "dv_ratio": "basic",
    "dv_ttm": "basic",
    "total_share": "basic",
    "float_share": "basic",
    "free_share": "basic",
    "total_mv": "basic",
    "circ_mv": "basic",
}

@dataclass
class Panel:
    """``field -> (trade_date x ts_code)`` frames, all on the same index and columns."""

    frames: dict[str, pd.DataFrame]

    @property
    def dates(self) -> pd.Index:
        return next(iter(self.frames.values())).index

    @property
    def codes(self) -> pd.Index:
        return next(iter(self.frames.values())).columns


def required_fields(formula: str) -> set[str]:
    """The market-data columns a formula reads, so a run loads nothing it does not need."""
    return {name for name in _names(formula) if name in FIELDS}


def load_panel(db, fields: set[str], start, end) -> Panel:
    """Read the market data a formula needs, widened to ``date x code`` frames.

    Only the requested columns are read, and each field is pivoted on its own: reading the whole
    table (sixteen unreferenced columns) and pivoting all of it at once is what ran a 1 GiB pod out
    of memory for a single-factor run.
    """
    frames: dict[str, pd.DataFrame] = {}
    for source in ("trade", "basic"):
        wanted = [f for f in fields if FIELDS.get(f) == source]
        if not wanted:
            continue
        columns = ["ts_code", "trade_date", *wanted]
        statement = text(
            f"SELECT {', '.join(columns)} FROM {_table(source)} "
            "WHERE trade_date BETWEEN :start AND :end"
        )
        frame = pd.read_sql(statement, db.connection(), params={"start": start, "end": end})
        if frame.empty:
            return Panel({})
        for field in wanted:
            # `float64` both ways: NUMERIC arrives as Decimal (object dtype) otherwise, and every
            # arithmetic then mixes Decimal with float.
            frames[field] = frame.pivot(
                index="trade_date", columns="ts_code", values=field
            ).astype("float64")
        del frame
    if not frames:
        return Panel({})
    # Align every frame on the union of dates and codes (a stock need not trade every day).
    if len(frames) > 1:
        index = sorted(set().union(*(f.index for f in frames.values())))
        codes = sorted(set().union(*(f.columns for f in frames.values())))
        frames = {
            name: f.reindex(index=index, columns=codes) for name, f in frames.items()
        }
    return Panel(frames)


def _table(source: str) -> str:
    from app.core.tushare_schema import tushare_table

    return tushare_table("stock_trade_daily" if source == "trade" else "daily_basic")


# --- expression language ---------------------------------------------------------------

_ALLOWED = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Call,
    ast.Name,
    ast.Constant,
    ast.Load,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.USub,
    ast.UAdd,
    ast.Compare,
    ast.Lt,
    ast.Gt,
    ast.LtE,
    ast.GtE,
    ast.Eq,
    ast.NotEq,
    ast.BitAnd,
    ast.BitOr,
    ast.IfExp,
)


def _names(formula: str) -> set[str]:
    try:
        tree = ast.parse(formula or "", mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"formula is not a valid expression: {exc.msg}") from exc
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}


def _check(formula: str) -> ast.Expression:
    tree = ast.parse(formula, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ValueError(
                f"formula uses something a factor cannot: {type(node).__name__}"
            )
        if isinstance(node, ast.Call) and not (
            isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS
        ):
            raise ValueError(f"unknown function in formula: {ast.dump(node.func)[:40]}")
    return tree


def _window(value) -> int:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or int(value) <= 0:
        raise ValueError(f"a window must be a positive integer, got {value!r}")
    return int(value)


def _ma(s, n):
    return s.rolling(_window(n)).mean()


def _ema(s, n):
    return s.ewm(span=_window(n), adjust=False).mean()


def _std(s, n, min_periods=None):
    window = _window(n)
    return s.rolling(window, min_periods=window if min_periods is None else int(min_periods)).std()


def _ts_max(s, n):
    return s.rolling(_window(n)).max()


def _ts_min(s, n):
    return s.rolling(_window(n)).min()


def _ts_sum(s, n):
    return s.rolling(_window(n)).sum()


def _shift(s, n):
    return s.shift(int(n))


def _ts_ret(s, n=1):
    return s / s.shift(_window(n)) - 1


def _corr(a, b, n):
    return a.rolling(_window(n)).corr(b)


def _where(cond, when_true, when_false):
    """``cond ? when_true : when_false`` — NaN counts as false, as a comparison already does."""
    if isinstance(cond, pd.DataFrame):
        return when_true.where(cond, when_false)
    return when_true.where(cond, when_false)


def _rank_cs(s):
    """Cross-sectional rank within each date, 0..1."""
    return s.rank(axis=1, pct=True)


def _zscore_cs(s):
    """Cross-sectional z-score within each date."""
    return s.sub(s.mean(axis=1), axis=0).div(s.std(axis=1), axis=0)


FUNCTIONS = {
    "abs": abs,
    "log": np.log,
    "sqrt": np.sqrt,
    "sign": np.sign,
    "ma": _ma,
    "ema": _ema,
    "std": _std,
    "ts_max": _ts_max,
    "ts_min": _ts_min,
    "ts_sum": _ts_sum,
    "shift": _shift,
    "ts_ret": _ts_ret,
    "corr": _corr,
    "where": _where,
    "rank_cs": _rank_cs,
    "zscore_cs": _zscore_cs,
    "minimum": np.minimum,
    "maximum": np.maximum,
}

_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
_COMPARE = {
    ast.Lt: operator.lt,
    ast.Gt: operator.gt,
    ast.LtE: operator.le,
    ast.GtE: operator.ge,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}


def evaluate(formula: str, panel: Panel) -> pd.DataFrame:
    """Evaluate a formula on the panel; the result is a ``date x code`` frame of values."""
    tree = _check(formula)
    missing = required_fields(formula) - set(panel.frames)
    if missing:
        raise ValueError(f"panel is missing {', '.join(sorted(missing))}")
    scope = {**panel.frames, **FUNCTIONS, "nan": float("nan")}
    result = _eval(tree.body, scope)
    if isinstance(result, pd.DataFrame):
        return result
    # A constant formula (or a scalar op) still produces a full panel.
    frame = next(iter(panel.frames.values()))
    return pd.DataFrame(
        np.full(frame.shape, result, dtype="float64"), index=frame.index, columns=frame.columns
    )


def _eval(node, scope):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in scope:
            raise ValueError(f"unknown name in formula: {node.id}")
        return scope[node.id]
    if isinstance(node, ast.BinOp):
        return _BINARY[type(node.op)](_eval(node.left, scope), _eval(node.right, scope))
    if isinstance(node, ast.UnaryOp):
        value = _eval(node.operand, scope)
        return -value if isinstance(node.op, ast.USub) else +value
    if isinstance(node, ast.Compare):
        left = _eval(node.left, scope)
        result = None
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval(comparator, scope)
            comparison = _COMPARE[type(op)](left, right)
            result = comparison if result is None else result & comparison
            left = right
        return result
    if isinstance(node, ast.BitAnd):
        return _eval(node.left, scope) & _eval(node.right, scope)
    if isinstance(node, ast.BitOr):
        return _eval(node.left, scope) | _eval(node.right, scope)
    if isinstance(node, ast.IfExp):
        return _where(
            _eval(node.test, scope), _eval(node.body, scope), _eval(node.orelse, scope)
        )
    if isinstance(node, ast.Call):
        args = [_eval(arg, scope) for arg in node.args]
        return FUNCTIONS[node.func.id](*args)
    raise ValueError(f"formula uses an unsupported construct: {type(node).__name__}")
