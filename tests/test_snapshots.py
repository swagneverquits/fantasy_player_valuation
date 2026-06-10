from pathlib import Path

from ffvaluation.ingestion.snapshots import load_manual_snapshot


def test_load_manual_snapshot_fixture() -> None:
    rows = load_manual_snapshot(Path("tests/fixtures/manual_snapshot.csv"))

    assert len(rows) == 2
    assert rows[0].valuation.source == "KeepTradeCut"
    assert rows[0].valuation.format.superflex is True
    assert rows[1].valuation.raw_value == 9850

