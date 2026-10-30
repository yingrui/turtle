from datetime import date

import pandas as pd

from app.analysis.artifact import ScoreTable, read_scores, scores_on_or_before, write_score_table


def _table(days, codes=("600519.SH", "000001.SZ")):
    rows = [
        {"trade_date": day, "ts_code": code, "score": float(index + 1)}
        for day in days
        for index, code in enumerate(codes)
    ]
    return ScoreTable(frame=pd.DataFrame(rows), params={"ma_window": 60}, label={"kind": "relative"})


def test_a_written_artifact_round_trips_with_a_content_hash(tmp_path, monkeypatch):
    monkeypatch.setattr("app.analysis.artifact.ARTIFACT_ROOT", tmp_path)
    table = _table([date(2026, 5, 14), date(2026, 5, 15)])

    key, digest = write_score_table("regime-ma60", table)
    again_key, again_digest = write_score_table("regime-ma60", table)

    assert again_digest == digest and again_key == key, "same table must reuse the same artifact"
    assert len(digest) == 64
    frame = read_scores(key)
    assert len(frame) == 4
    assert (tmp_path / "regime-ma60" / digest / "card.json").exists()


def test_a_changed_table_gets_a_new_hash(tmp_path, monkeypatch):
    monkeypatch.setattr("app.analysis.artifact.ARTIFACT_ROOT", tmp_path)
    _, first = write_score_table("s", _table([date(2026, 5, 14)]))
    _, second = write_score_table("s", _table([date(2026, 5, 15)]))
    assert first != second


def test_scores_carry_forward_to_days_without_a_run(tmp_path, monkeypatch):
    """A score computed on the 14th is still the newest information on a holiday."""
    monkeypatch.setattr("app.analysis.artifact.ARTIFACT_ROOT", tmp_path)
    key, _ = write_score_table("s", _table([date(2026, 5, 14), date(2026, 5, 18)]))
    frame = read_scores(key)

    assert set(scores_on_or_before(frame, date(2026, 5, 16))["trade_date"]) == {date(2026, 5, 14)}
    assert set(scores_on_or_before(frame, date(2026, 5, 18))["trade_date"]) == {date(2026, 5, 18)}
    assert scores_on_or_before(frame, date(2026, 5, 1)).empty


def test_a_missing_artifact_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.setattr("app.analysis.artifact.ARTIFACT_ROOT", tmp_path)
    try:
        read_scores(str(tmp_path / "gone"))
    except FileNotFoundError as exc:
        assert "ranking artifact missing" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected FileNotFoundError")
