from datetime import date

import pandas as pd

from app.core.util.simulation_analysis import calculate_cagr


def test_calculate_cagr_with_python_dates():
    df = pd.DataFrame(
        {
            "date": [date(2024, 1, 2), date(2025, 6, 1)],
            "total": [100_000.0, 120_000.0],
        }
    )
    result = calculate_cagr(0, df)
    assert result["policy_id"] == 0
    assert result["start_date"] == "2024-01-02"
    assert result["end_date"] == "2025-06-01"
    assert result["initial_total"] == 100_000.0
    assert result["total"] == 120_000.0
    assert result["return_rate_pct"] == 120.0


def test_calculate_cagr_with_parsed_csv_dates():
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2025-06-01"]),
            "total": [100_000.0, 120_000.0],
        }
    )
    result = calculate_cagr(1, df)
    assert result["start_date"] == "2024-01-02"
    assert result["end_date"] == "2025-06-01"


def test_summarize_run_stores_what_a_reader_asks():
    """The stored summary must answer total/CAGR/drawdown/win-loss without replays."""
    import pandas as pd

    from app.core.util.simulation_analysis import summarize_run

    daily = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-06-03", "2024-12-31"]),
            "total": [100.0, 80.0, 120.0],
        }
    )
    trades = pd.DataFrame(
        [
            {"ts_code": "600519.SH", "side": "buy", "shares": 100, "benefit": 0.0},
            {"ts_code": "600519.SH", "side": "sell", "shares": 40, "benefit": 250.0},
            {"ts_code": "000001.SZ", "side": "sell", "shares": 10, "benefit": -30.0},
        ]
    )
    summary = summarize_run(0, daily, trades)

    assert summary["initial_total"] == 100.0
    assert summary["final_total"] == 120.0
    assert summary["return_rate_pct"] == 120.0
    assert summary["max_drawdown_pct"] == -20.0      # 100 -> 80
    assert summary["win_count"] == 1 and summary["loss_count"] == 1
    assert summary["trade_count"] == 3
    assert summary["holding_count"] == 1             # 100 bought - 40 sold
    assert summary["window_start"].isoformat() == "2024-01-02"
    assert summary["window_end"].isoformat() == "2024-12-31"


def test_summarize_run_on_an_empty_run_is_empty():
    import pandas as pd

    from app.core.util.simulation_analysis import summarize_run

    assert summarize_run(0, pd.DataFrame(), pd.DataFrame()) == {}
