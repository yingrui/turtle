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
