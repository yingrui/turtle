import json

import pandas as pd

from app.core.util.json_utils import dataframe_to_records


def test_dataframe_to_records_replaces_nan():
    df = pd.DataFrame([{"ts_code": "000001.SZ", "sum_0": float("nan"), "w_cnt_0": 0.0}])
    records = dataframe_to_records(df)
    assert records == [{"ts_code": "000001.SZ", "sum_0": None, "w_cnt_0": 0.0}]
    json.dumps(records)


def test_dataframe_to_records_empty():
    assert dataframe_to_records(pd.DataFrame()) == []
