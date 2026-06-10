from __future__ import annotations

from collections.abc import Mapping
from math import sqrt


def mean_absolute_error(actual: Mapping[str, float], predicted: Mapping[str, float]) -> float:
    shared = actual.keys() & predicted.keys()
    if not shared:
        raise ValueError("actual and predicted have no shared player IDs")
    return sum(abs(actual[player_id] - predicted[player_id]) for player_id in shared) / len(shared)


def root_mean_squared_error(actual: Mapping[str, float], predicted: Mapping[str, float]) -> float:
    shared = actual.keys() & predicted.keys()
    if not shared:
        raise ValueError("actual and predicted have no shared player IDs")
    return sqrt(
        sum((actual[player_id] - predicted[player_id]) ** 2 for player_id in shared) / len(shared)
    )


def pairwise_preference_accuracy(
    actual: Mapping[str, float],
    predicted: Mapping[str, float],
) -> float:
    shared = sorted(actual.keys() & predicted.keys())
    if len(shared) < 2:
        raise ValueError("at least two shared player IDs are required")

    correct = 0
    comparable = 0
    for index, left in enumerate(shared):
        for right in shared[index + 1 :]:
            actual_diff = actual[left] - actual[right]
            predicted_diff = predicted[left] - predicted[right]
            if actual_diff == 0 or predicted_diff == 0:
                continue
            comparable += 1
            if (actual_diff > 0) == (predicted_diff > 0):
                correct += 1

    if comparable == 0:
        raise ValueError("no non-tied player pairs are comparable")
    return correct / comparable

