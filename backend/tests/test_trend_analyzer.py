import pandas as pd

from app.core.engine.TrendAnalyzer import TrendAnalyzer


def _make_qfq_df(n: int, *, slope: float = 0.0, base: float = 10.0) -> pd.DataFrame:
    closes = [base + slope * i for i in range(n)]
    return pd.DataFrame({
        'trade_date': pd.date_range('2020-01-01', periods=n, freq='B'),
        'close': closes,
        'adj_factor': [1.0] * n,
        'qfq': closes,
    })


def test_insufficient_history():
    df = _make_qfq_df(120)
    trend = TrendAnalyzer('000001.SZ', df).analysis_trend()
    assert trend.status == 'unknown'
    assert trend.reason == 'insufficient_history'


def test_strong_uptrend():
    df = _make_qfq_df(220, slope=0.5)
    trend = TrendAnalyzer('000001.SZ', df).analysis_trend()
    assert trend.status == 'up'
    assert trend.reason == 'strong_up'
    assert trend.gradient > 0


def test_weak_uptrend():
    # Flat long history then recent rise: MA20 > MA70 but MA150 still high
    n = 200
    closes = [10.0] * 150 + [10.0 + i * 0.3 for i in range(50)]
    df = pd.DataFrame({
        'trade_date': pd.date_range('2020-01-01', periods=n, freq='B'),
        'close': closes,
        'adj_factor': [1.0] * n,
        'qfq': closes,
    })
    trend = TrendAnalyzer('000001.SZ', df).analysis_trend()
    assert trend.status == 'up'
    assert trend.reason in ('weak_up', 'strong_up')


def test_sideways():
    n = 200
    # Tight range oscillation — MAs converge, no clear stack
    closes = [10.0 + 0.02 * (i % 7 - 3) for i in range(n)]
    df = pd.DataFrame({
        'trade_date': pd.date_range('2020-01-01', periods=n, freq='B'),
        'close': closes,
        'adj_factor': [1.0] * n,
        'qfq': closes,
    })
    trend = TrendAnalyzer('000001.SZ', df).analysis_trend()
    assert trend.status == 'unknown'
    assert trend.reason == 'sideways'
