import pytest

from ffvaluation.evaluation.metrics import (
    mean_absolute_error,
    pairwise_preference_accuracy,
    root_mean_squared_error,
)


def test_error_metrics_use_shared_players() -> None:
    actual = {"a": 10.0, "b": 5.0, "c": 1.0}
    predicted = {"a": 8.0, "b": 6.0, "x": 100.0}

    assert mean_absolute_error(actual, predicted) == 1.5
    assert root_mean_squared_error(actual, predicted) == pytest.approx(1.5811, rel=1e-3)


def test_pairwise_preference_accuracy() -> None:
    actual = {"a": 10.0, "b": 5.0, "c": 1.0}
    predicted = {"a": 9.0, "b": 3.0, "c": 4.0}

    assert pairwise_preference_accuracy(actual, predicted) == pytest.approx(2 / 3)


def test_metrics_raise_without_shared_players() -> None:
    with pytest.raises(ValueError):
        mean_absolute_error({"a": 1.0}, {"b": 1.0})

