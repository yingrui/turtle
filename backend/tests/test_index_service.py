"""Index data: which indexes are usable as benchmarks, and how a series is rebased."""

from __future__ import annotations

import pandas as pd
import pytest


def test_the_rebased_series_starts_at_100_and_holds_the_last_close_over_a_gap():
    """A day the index did not trade keeps the previous value instead of punching a hole."""
    from app.services.index_service import IndexService

    class _Db:
        """The service reads through pandas; a stub connection returning the frame is enough."""

        def __init__(self, frame: pd.DataFrame):
            self.frame = frame

        def connection(self):
            return self

    service = IndexService()
    frame = pd.DataFrame(
        {
            "trade_date": [pd.Timestamp("2026-05-06").date(), pd.Timestamp("2026-05-08").date()],
            "close": [4000.0, 4200.0],
        }
    )
    # The SQL is executed by pandas; swap the loader for the frame.
    monkey = pytest.MonkeyPatch()
    monkey.setattr(pd, "read_sql", lambda *args, **kwargs: frame)
    try:
        series = service.benchmark_series(
            _Db(frame), "000300.SH", ["2026-05-06", "2026-05-07", "2026-05-08"]
        )
    finally:
        monkey.undo()

    assert series[0] == pytest.approx(100.0)
    assert series[1] == pytest.approx(100.0)      # 05-07 has no bar: carry 05-06 forward
    assert series[2] == pytest.approx(105.0)


def test_an_empty_window_is_all_none_not_an_error():
    from app.services.index_service import IndexService

    class _Db:
        def connection(self):
            return self

    monkey = pytest.MonkeyPatch()
    monkey.setattr(pd, "read_sql", lambda *args, **kwargs: pd.DataFrame(columns=["trade_date", "close"]))
    try:
        assert IndexService().benchmark_series(_Db(), "000300.SH", ["2026-05-06"]) == [None]
        assert IndexService().benchmark_series(_Db(), "000300.SH", []) == []
    finally:
        monkey.undo()
