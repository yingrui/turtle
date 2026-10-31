"""The rules that stop a backtest from booking fills that never existed."""

from app.core.market.tradability import judge, limit_ratio


def _buy(**overrides):
    base = dict(side="buy", ts_code="600519.SH", price=100.0, pre_close=100.0, listed_days=500)
    base.update(overrides)
    return judge(**base)


def test_a_normal_session_is_tradable_both_ways():
    assert _buy().ok and judge(side="sell", ts_code="600519.SH", price=100.0, pre_close=100.0, listed_days=500).ok


def test_no_price_means_suspended():
    assert _buy(price=None).reason == "suspended"


def test_a_limit_up_open_cannot_be_bought():
    assert _buy(price=110.0).reason == "limit_up"


def test_a_limit_down_open_cannot_be_sold():
    verdict = judge(side="sell", ts_code="600519.SH", price=90.0, pre_close=100.0, listed_days=500)
    assert verdict.reason == "limit_down"


def test_limit_ratios_follow_the_board_and_the_st_flag():
    assert limit_ratio("600519.SH") == 0.10
    assert limit_ratio("688981.SH") == 0.20      # STAR
    assert limit_ratio("300750.SZ") == 0.20      # ChiNext
    assert limit_ratio("000001.SZ", "ST某某") == 0.05


def test_a_first_day_listing_cannot_be_bought():
    assert _buy(listed_days=0).reason == "first_day_listing"


def test_a_delisting_stock_is_excluded():
    assert _buy(name="某某退").reason == "delisting"
