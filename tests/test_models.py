from ffvaluation.models import DEFAULT_FORMAT, FantasyFormat


def test_default_format_matches_project_scope() -> None:
    assert DEFAULT_FORMAT.teams == 12
    assert DEFAULT_FORMAT.superflex is True
    assert DEFAULT_FORMAT.ppr == 1.0
    assert DEFAULT_FORMAT.passing_touchdown_points == 4.0
    assert DEFAULT_FORMAT.tight_end_premium == 0.0
    assert "Full PPR" in DEFAULT_FORMAT.scoring_notes


def test_format_can_mark_dynasty_without_changing_scoring() -> None:
    format_ = FantasyFormat(dynasty=True)

    assert format_.dynasty is True
    assert format_.superflex is True
    assert format_.passing_touchdown_points == 4.0
