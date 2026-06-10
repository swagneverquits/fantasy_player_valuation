from ffvaluation.sources.registry import list_sources


def test_initial_sources_are_keeptradecut_and_rosteraudit() -> None:
    sources = list_sources()

    assert [source.name for source in sources] == ["KeepTradeCut", "RosterAudit"]
