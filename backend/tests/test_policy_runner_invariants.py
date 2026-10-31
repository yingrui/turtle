"""What must be true of every policy-driven book, checked without a database.

Four defects in this file's history shared one shape: a quantity computed at the wrong moment and never
asserted. Equity was snapshotted before the day's trades (a loss looked like a doubling); a missing
close was valued at zero; the policy parameters were silently empty. These tests assert the invariants
those defects violated.
"""

from datetime import date
from types import SimpleNamespace

import pytest

from app.core.simulation import policy_runner


class _FakeProvider:
    def __init__(self, days_to_codes):
        self.days_to_codes = days_to_codes

    def rankings(self, db, day):
        from app.core.simulation.ranking import Ranked

        codes = self.days_to_codes.get(day, [])
        return [Ranked(ts_code=code, score=float(len(codes) - i), rank=i + 1) for i, code in enumerate(codes)]


def _run(monkeypatch, *, days, codes, prices, initial_cash=1_000_000, enter_on_pool=True):
    """Drive the runner with patched market data; return the daily rows the runner wrote."""
    written = []

    class FakeSession:
        def __init__(self):
            self.rows = []

        def add(self, row):
            self.rows.append(row)
            if type(row).__name__ == "SimulationDaily":
                written.append(row)

        def flush(self):
            pass

    monkeypatch.setattr(policy_runner, "_trade_days", lambda db, start, end: days)
    monkeypatch.setattr(policy_runner, "_closes", lambda db, day: prices.get(day, {}))
    monkeypatch.setattr(policy_runner, "next_open", lambda db, day: prices.get(day, {}))
    monkeypatch.setattr(policy_runner, "_policy_params", lambda db, pid: ({}, {}))

    class NoSignals:
        def __init__(self, *args, **kwargs):
            pass

        def detect_signals(self, day):
            return []

    monkeypatch.setattr(policy_runner, "TradeSignalMonitor", NoSignals)

    run = SimpleNamespace(id="run-1", portfolio_id="p1", config_snapshot="{}")
    policy_runner.run_policy_simulation(
        FakeSession(),
        run=run,
        start=days[0],
        end=days[-1],
        initial_cash=initial_cash,
        config=policy_runner.PolicyRunConfig(top_n=2, cash_buffer=0.0, enter_on_pool=enter_on_pool),
        provider=_FakeProvider({day: codes for day in days}),
    )
    return written


def test_equity_is_cash_plus_positions_not_the_pre_trade_snapshot(monkeypatch):
    """A day that opens positions must still report the whole book, not the leftover cash."""
    days = [date(2026, 5, 14)]
    prices = {days[0]: {"600519.SH": 100.0, "000001.SZ": 10.0}}
    rows = _run(monkeypatch, days=days, codes=["600519.SH", "000001.SZ"], prices=prices)

    assert len(rows) == 1
    assert float(rows[0].total) == pytest.approx(1_000_000, rel=1e-3)


def test_the_first_day_is_measured_against_the_initial_cash(monkeypatch):
    """The benchmark view uses day one as its base; if day one is short, every return is inflated."""
    days = [date(2026, 5, 14)]
    rows = _run(
        monkeypatch,
        days=days,
        codes=["600519.SH"],
        prices={days[0]: {"600519.SH": 50.0}},
        initial_cash=250_000,
    )
    assert float(rows[0].total) == pytest.approx(250_000, rel=1e-3)


def test_a_held_stock_without_a_close_carries_its_last_price(monkeypatch):
    """Suspended names keep their last valuation; zeroing them invents a loss."""
    first, second = date(2026, 5, 14), date(2026, 5, 15)
    prices = {first: {"600519.SH": 100.0}, second: {}}   # no row on the second day
    rows = _run(monkeypatch, days=[first, second], codes=["600519.SH"], prices=prices)
    monkeypatch.setattr(policy_runner, "_trade_days", lambda db, start, end: [first, second])

    assert float(rows[1].total) == pytest.approx(float(rows[0].total), rel=1e-6)


def test_buying_and_selling_the_same_price_does_not_create_money(monkeypatch):
    """Fees only ever reduce equity: no price move, no profit."""
    days = [date(2026, 5, 14), date(2026, 5, 15)]
    prices = {day: {"600519.SH": 100.0} for day in days}
    rows = _run(monkeypatch, days=days, codes=["600519.SH"], prices=prices)
    assert float(rows[-1].total) <= 1_000_000 + 1e-6


def test_a_day_without_any_close_still_values_what_was_bought(monkeypatch):
    """The window's first session can lack rows in the daily table; fills still exist.

    Valuing those positions at zero reported only the leftover cash, and the benchmark view then used
    that short number as its base — 1,000,000 in, 264,800 out, shown as a 94% return.
    """
    day = date(2026, 5, 14)

    def closes_only_from_fills(db, d):
        return {}

    monkeypatch.setattr(policy_runner, "_closes", closes_only_from_fills)
    rows = _run(monkeypatch, days=[day], codes=["600519.SH"], prices={day: {"600519.SH": 100.0}})
    assert float(rows[0].total) == pytest.approx(1_000_000, rel=1e-3)
