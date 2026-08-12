from __future__ import annotations

from fastapi.testclient import TestClient

from app.engine.game_manager import game_manager
from app.engine.room_manager import (
    BOT_NAMES,
    PRODUCT_BID_POLICY,
    PRODUCT_BOT_THINK_SECONDS,
    PRODUCT_K_POLICY,
    room_manager,
)
from app.main import app


def _create(client: TestClient, human_count: int, name: str = "Alice") -> dict:
    response = client.post(
        "/rooms",
        json={"playerName": name, "humanCount": human_count, "startingBidderIndex": 1},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _join(client: TestClient, room_code: str, name: str) -> dict:
    response = client.post(
        "/rooms/join", json={"roomCode": room_code, "playerName": name}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _drain_state_and_actions(ws, max_messages: int = 80) -> tuple[dict, dict]:
    state = None
    actions = None
    for _ in range(max_messages):
        message = ws.receive_json()
        if message.get("type") == "STATE_UPDATE":
            state = message["state"]
        elif message.get("type") == "LEGAL_ACTIONS":
            actions = message["actions"]
        elif message.get("type") == "ERROR":
            raise AssertionError(message["message"])
        if state is not None and actions is not None:
            return state, actions
    raise AssertionError("Timed out waiting for state and actions")


def test_all_human_counts_create_correct_roster_and_start_timing() -> None:
    expected_humans = {
        1: {3},
        2: {1, 3},
        3: {1, 2, 3},
        4: {0, 1, 2, 3},
    }
    with TestClient(app) as client:
        for human_count, human_seats in expected_humans.items():
            created = _create(client, human_count)
            assert created["targetHumanCount"] == human_count
            assert created["seatIndex"] == min(human_seats)
            assert bool(created["gameId"]) is (human_count == 1)
            assert created["waitingForPlayer"] is (human_count > 1)

            roster = created["seats"]
            assert {s["seatIndex"] for s in roster if s["type"] == "human"} == human_seats
            assert all(
                seat["name"] == BOT_NAMES[seat["seatIndex"]]
                for seat in roster
                if seat["type"] == "bot"
            )

            latest = created
            for number in range(2, human_count + 1):
                latest = _join(client, created["roomCode"], f"Player {number}")
            assert latest["playersJoined"] == human_count
            assert latest["waitingForPlayer"] is False
            assert latest["gameId"]


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
        created = _create(client, 2)
        joined = _join(client, created["roomCode"], "Bob")
        assert joined["seatIndex"] == 3

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
        assert restored.json()["gameId"] == joined["gameId"]

        invalid = client.post(
            "/rooms/join",
            json={"roomCode": created["roomCode"], "playerToken": "not-a-token"},
        )
        assert invalid.status_code == 401


def test_two_humans_are_opposite_partners() -> None:
    with TestClient(app) as client:
        first = _create(client, 2)
        second = _join(client, first["roomCode"], "Bob")
        assert {first["seatIndex"], second["seatIndex"]} == {1, 3}
        assert first["seats"][1]["team"] == first["seats"][3]["team"] == 2


def test_three_human_rematch_rotates_bot_partner_and_token_seats() -> None:
    with TestClient(app) as client:
        players = [_create(client, 3)]
        players.append(_join(client, players[0]["roomCode"], "Bob"))
        players.append(_join(client, players[0]["roomCode"], "Carol"))
        room_code = players[0]["roomCode"]
        game_id = players[-1]["gameId"]
        state = game_manager.get_game(game_id)
        assert state is not None
        assert state.seat_types == ["bot", "human", "human", "human"]
        state.phase = "GAME_OVER"

        for index, player in enumerate(players):
            result = room_manager.request_rematch(
                room_code=room_code, player_token=player["playerToken"]
            )
            assert result.started is (index == 2)

        assert state.seat_types == ["human", "bot", "human", "human"]
        restored_seats = []
        for player in players:
            restored = client.post(
                "/rooms/join",
                json={"roomCode": room_code, "playerToken": player["playerToken"]},
            )
            assert restored.status_code == 200
            restored_seats.append(restored.json()["seatIndex"])
        assert sorted(restored_seats) == [0, 2, 3]
        assert state.starting_bidder_index == 2


def test_four_human_websocket_redacts_hands_and_scopes_actions() -> None:
    with TestClient(app) as client:
        players = [_create(client, 4)]
        for name in ("Bob", "Carol", "Dev"):
            players.append(_join(client, players[0]["roomCode"], name))
        alice = players[0]
        with client.websocket_connect(
            f"/ws/rooms/{alice['roomCode']}?token={alice['playerToken']}"
        ) as websocket:
            state, actions = _drain_state_and_actions(websocket)
            assert state["viewerSeatIndex"] == alice["seatIndex"]
            assert state["seatTypes"] == ["human", "human", "human", "human"]
            for player in state["players"]:
                if player["seatIndex"] == alice["seatIndex"]:
                    assert not player["cards"][0]["cardId"].startswith("HIDDEN_")
                else:
                    assert player["cards"][0]["cardId"].startswith("HIDDEN_")
            if actions["type"] != "NO_ACTION":
                assert actions["seatIndex"] == alice["seatIndex"]
            websocket.send_json(
                {"type": "SUBMIT_BID", "seatIndex": 3, "bidValue": 0}
            )
            error = websocket.receive_json()
            assert error["type"] == "ERROR"
            assert "assigned seat" in error["message"]
