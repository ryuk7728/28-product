from __future__ import annotations

import json

import pytest

from app.legacy import minimax as legacy_minimax

rl428_minimax_rust = pytest.importorskip("rl428_minimax_rust")


def _empty_search_payload() -> dict[str, object]:
    return {
        "s": [],
        "first": True,
        "secondary": True,
        "trumpPlayed": False,
        "trumpIndice": [0, 0, 0, 0],
        "playerChance": 0,
        "players": [
            {"cards": [], "isTrump": seat == 0, "team": 1 if seat % 2 == 0 else 2}
            for seat in range(4)
        ],
        "currentSuit": "",
        "trumpReveal": False,
        "trumpSuit": "Clubs",
        "chose": False,
        "finalBid": 1,
        "playerTrump": None,
        "total": 0,
        "num": 0,
        "k": 1,
        "alpha": None,
        "beta": None,
    }


def test_rust_search_honors_expired_absolute_deadline() -> None:
    payload = _empty_search_payload()
    payload["deadlineEpochMs"] = 0
    result = json.loads(
        rl428_minimax_rust.minimax_extended_core(json.dumps(payload))
    )
    assert result["timedOut"] is True
    assert result["reward_distribution"] == []


def test_rust_search_without_deadline_completes_normally() -> None:
    result = json.loads(
        rl428_minimax_rust.minimax_extended_core(
            json.dumps(_empty_search_payload())
        )
    )
    assert result["timedOut"] is False


def test_python_search_honors_expired_absolute_deadline() -> None:
    with pytest.raises(legacy_minimax.MinimaxDeadlineExceeded):
        legacy_minimax._minimax_extended_python(
            [],
            True,
            True,
            False,
            [],
            [0, 0, 0, 0],
            0,
            [],
            "",
            False,
            "Clubs",
            False,
            1,
            None,
            -1,
            [],
            0,
            0,
            1,
            deadline_epoch_ms=0,
        )
