from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.engine.game_manager import game_manager
from app.engine.room_manager import (
    BOT_NAMES,
    PRODUCT_BID_POLICY,
    PRODUCT_BOT_THINK_SECONDS,
    PRODUCT_K_POLICY,
)
from app.main import app


def _create(client: TestClient, human_count: int, name: str = "Alice") -> dict:
    response = client.post(
        "/rooms",
        json={"playerName": name, "humanCount": human_count, "startingBidderIndex": 1},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_public_product_creates_single_player_game_immediately() -> None:
    with TestClient(app) as client:
        created = _create(client, 1)
        assert created["targetHumanCount"] == 1
        assert created["seatIndex"] == 3
        assert created["waitingForPlayer"] is False
        assert created["gameId"]
        roster = created["seats"]
        assert {seat["seatIndex"] for seat in roster if seat["type"] == "human"} == {3}
        assert all(
            seat["name"] == BOT_NAMES[seat["seatIndex"]]
            for seat in roster
            if seat["type"] == "bot"
        )


@pytest.mark.parametrize("human_count", [2, 3, 4])
def test_public_product_rejects_multiplayer_room_sizes(human_count: int) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/rooms",
            json={"playerName": "Alice", "humanCount": human_count},
        )
        assert response.status_code == 422


def test_product_bot_policy_is_fixed_and_client_overrides_are_rejected() -> None:
    with TestClient(app) as client:
        invalid = client.post(
            "/rooms",
            json={
                "playerName": "Alice",
                "humanCount": 1,
                "biddingPolicy": {"mode": "optimal"},
            },
        )
        assert invalid.status_code == 422

        room = _create(client, 1)
        state = game_manager.get_game(room["gameId"])
        assert state is not None
        assert state.bot_bidding_policy == PRODUCT_BID_POLICY
        assert state.bot_k_policy == PRODUCT_K_POLICY
        assert state.bot_think_timeout_seconds == PRODUCT_BOT_THINK_SECONDS
        assert state.bot_bidding_policy.to_public_dict() == {
            "mode": "custom",
            "positionAware": False,
            "thresholds": {
                "opening15": 60,
                "opening16": 75,
                "laterBid": 60,
                "jumpTo16": 75,
            },
        }
        assert state.bot_k_policy.to_public_dict()["kByCatch"] == [3, 3, 4, 4, 4, 3, 2, 1]


def test_join_full_room_and_token_restore() -> None:
    with TestClient(app) as client:
        created = _create(client, 1)

        full = client.post(
            "/rooms/join",
            json={"roomCode": created["roomCode"], "playerName": "Carol"},
        )
        assert full.status_code == 409

        restored = client.post(
            "/rooms/join",
            json={
                "roomCode": created["roomCode"],
                "playerToken": created["playerToken"],
            },
        )
        assert restored.status_code == 200
        assert restored.json()["seatIndex"] == created["seatIndex"]
        assert restored.json()["gameId"] == created["gameId"]

        invalid = client.post(
            "/rooms/join",
            json={"roomCode": created["roomCode"], "playerToken": "not-a-token"},
        )
        assert invalid.status_code == 401
