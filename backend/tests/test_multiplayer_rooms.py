from __future__ import annotations

from fastapi.testclient import TestClient

from app.engine.game_manager import game_manager
from app.main import app


def _drain_state_and_actions(ws, max_msgs: int = 60) -> tuple[dict, dict]:
    state = None
    actions = None
    for _ in range(max_msgs):
        msg = ws.receive_json()
        msg_type = msg.get("type")
        if msg_type == "STATE_UPDATE":
            state = msg["state"]
        elif msg_type == "LEGAL_ACTIONS":
            actions = msg["actions"]
        elif msg_type == "ERROR":
            raise AssertionError(f"Unexpected WS error: {msg.get('message')}")
        if state is not None and actions is not None:
            return state, actions
    raise AssertionError("Timed out waiting for state/actions.")


def _receive_until(ws, expected_type: str, max_msgs: int = 80) -> dict:
    for _ in range(max_msgs):
        msg = ws.receive_json()
        if msg.get("type") == expected_type:
            return msg
        if msg.get("type") == "ERROR":
            raise AssertionError(f"Unexpected WS error: {msg.get('message')}")
    raise AssertionError(f"Timed out waiting for {expected_type}.")


def _receive_rematch_status(ws, expected_status: str, max_msgs: int = 120) -> dict:
    for _ in range(max_msgs):
        msg = ws.receive_json()
        msg_type = msg.get("type")
        if msg_type == "ERROR":
            raise AssertionError(f"Unexpected WS error: {msg.get('message')}")
        if msg_type != "REMATCH_STATUS":
            continue
        if msg.get("status") == expected_status:
            return msg
    raise AssertionError(f"Timed out waiting for REMATCH_STATUS={expected_status}.")


def test_room_create_join_reconnect_flow() -> None:
    with TestClient(app) as client:
        create = client.post(
            "/rooms", json={"startingBidderIndex": 0, "playerName": "Alice"}
        )
        assert create.status_code == 200
        created = create.json()
        assert created["waitingForPlayer"] is True
        assert created["playersJoined"] == 1
        assert created["seatIndex"] in (1, 3)
        assert created["gameId"] is None

        join = client.post(
            "/rooms/join",
            json={"roomCode": created["roomCode"], "playerName": "Bob"},
        )
        assert join.status_code == 200
        joined = join.json()
        assert joined["waitingForPlayer"] is False
        assert joined["playersJoined"] == 2
        assert joined["gameId"]
        assert joined["seatIndex"] in (1, 3)
        assert joined["seatIndex"] != created["seatIndex"]

        reconnect = client.post(
            "/rooms/join",
            json={
                "roomCode": created["roomCode"],
                "playerToken": created["playerToken"],
            },
        )
        assert reconnect.status_code == 200
        rejoin = reconnect.json()
        assert rejoin["seatIndex"] == created["seatIndex"]
        assert rejoin["playerToken"] == created["playerToken"]
        assert rejoin["gameId"] == joined["gameId"]


def test_room_propagates_custom_position_aware_policy_to_game_state() -> None:
    policy = {
        "mode": "custom",
        "positionAware": True,
        "thresholds": {
            "opening15": 64,
            "opening16": 73,
            "laterBid": 69,
            "jumpTo16": 81,
        },
    }
    with TestClient(app) as client:
        created = client.post(
            "/rooms",
            json={
                "startingBidderIndex": 2,
                "playerName": "Alice",
                "biddingPolicy": policy,
                "kPolicy": "aggressive",
            },
        )
        assert created.status_code == 200
        room = created.json()
        status = client.get(f"/rooms/{room['roomCode']}").json()
        assert status["biddingPolicy"] == policy
        assert status["kPolicy"] == {
            "mode": "aggressive",
            "kByCatch": [3, 3, 4, 4, 4, 3, 2, 1],
        }

        joined = client.post(
            "/rooms/join",
            json={"roomCode": room["roomCode"], "playerName": "Bob"},
        )
        assert joined.status_code == 200
        game = client.get(f"/games/{joined.json()['gameId']}").json()
        assert game["startingBidderIndex"] == 2
        assert game["botBiddingPolicy"] == policy
        assert game["botKPolicy"] == status["kPolicy"]


def test_custom_policy_requires_thresholds() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/rooms",
            json={
                "playerName": "Alice",
                "biddingPolicy": {"mode": "custom", "positionAware": False},
            },
        )
        assert response.status_code == 422


def test_room_defaults_to_regular_k_policy_and_rejects_unknown_mode() -> None:
    with TestClient(app) as client:
        created = client.post("/rooms", json={"playerName": "Alice"})
        assert created.status_code == 200
        status = client.get(f"/rooms/{created.json()['roomCode']}").json()
        assert status["kPolicy"] == {
            "mode": "regular",
            "kByCatch": [2, 2, 3, 3, 4, 3, 2, 1],
        }

        invalid = client.post(
            "/rooms", json={"playerName": "Alice", "kPolicy": "maximum"}
        )
        assert invalid.status_code == 422


def test_ws_room_redacts_hands_and_enforces_seat_actions() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/rooms", json={"startingBidderIndex": 0, "playerName": "Alice"}
        ).json()
        joined = client.post(
            "/rooms/join",
            json={"roomCode": created["roomCode"], "playerName": "Bob"},
        ).json()

        seat1 = created if created["seatIndex"] == 1 else joined
        room_code = seat1["roomCode"]
        token = seat1["playerToken"]

        with client.websocket_connect(f"/ws/rooms/{room_code}?token={token}") as ws:
            state, actions = _drain_state_and_actions(ws)

            # Viewer sees their own hand, everyone else hidden.
            assert state["viewerSeatIndex"] == 1
            own_cards = state["players"][1]["cards"]
            other_cards = state["players"][0]["cards"]
            assert own_cards and not own_cards[0]["cardId"].startswith("HIDDEN_")
            assert other_cards and other_cards[0]["cardId"].startswith("HIDDEN_")

            # Server must reject seat spoofing.
            ws.send_json({"type": "SUBMIT_BID", "seatIndex": 3, "bidValue": 0})
            err = ws.receive_json()
            assert err["type"] == "ERROR"
            assert "assigned seat" in err["message"]

            # Actions are scoped to the connected player (NO_ACTION or seat 1).
            if actions["type"] != "NO_ACTION":
                assert actions.get("seatIndex") == 1


def test_ws_room_spectator_gets_full_state_and_read_only_actions() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/rooms", json={"startingBidderIndex": 0, "playerName": "Alice"}
        ).json()
        joined = client.post(
            "/rooms/join",
            json={"roomCode": created["roomCode"], "playerName": "Bob"},
        ).json()
        assert joined["gameId"]

        room_code = created["roomCode"]
        with client.websocket_connect(f"/ws/rooms/{room_code}?spectator=1") as ws:
            state, actions = _drain_state_and_actions(ws)

            # Spectator should see all cards (no hidden placeholders).
            assert "viewerSeatIndex" not in state
            for player in state["players"]:
                cards = player["cards"]
                if cards:
                    assert not cards[0]["cardId"].startswith("HIDDEN_")

            # Spectator receives NO_ACTION and cannot submit moves.
            assert actions["type"] == "NO_ACTION"
            ws.send_json({"type": "SUBMIT_BID", "seatIndex": 1, "bidValue": 14})
            err = ws.receive_json()
            assert err["type"] == "ERROR"
            assert "read-only" in err["message"].lower()


def test_room_rematch_requires_both_humans_and_rotates_starting_bidder() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/rooms", json={"startingBidderIndex": 0, "playerName": "Alice"}
        ).json()
        joined = client.post(
            "/rooms/join",
            json={"roomCode": created["roomCode"], "playerName": "Bob"},
        ).json()

        seat1 = created if created["seatIndex"] == 1 else joined
        seat3 = joined if seat1 is created else created
        room_code = created["roomCode"]
        game_id = joined["gameId"]
        assert game_id

        state_obj = game_manager.get_game(game_id)
        assert state_obj is not None
        previous_start = state_obj.starting_bidder_index
        state_obj.phase = "GAME_OVER"
        state_obj.winnerTeam = 2
        state_obj.team2Points = 18
        state_obj.team1Points = 10

        with client.websocket_connect(
            f"/ws/rooms/{room_code}?token={seat1['playerToken']}"
        ) as ws1, client.websocket_connect(
            f"/ws/rooms/{room_code}?token={seat3['playerToken']}"
        ) as ws2:
            _drain_state_and_actions(ws1)
            _drain_state_and_actions(ws2)

            # First human clicks New Game -> waiting for second human.
            ws1.send_json({"type": "REQUEST_NEW_GAME"})
            waiting_msg = _receive_rematch_status(ws1, "waiting")
            assert waiting_msg["status"] == "waiting"
            assert waiting_msg["waitingForSeatIndex"] in (1, 3)
            assert waiting_msg["waitingForSeatIndex"] != seat1["seatIndex"]
            assert seat1["seatIndex"] in waiting_msg["readySeatIndices"]

            # Second human clicks New Game -> rematch starts immediately.
            ws2.send_json({"type": "REQUEST_NEW_GAME"})
            started_msg = _receive_rematch_status(ws2, "started")
            assert started_msg["status"] == "started"

            updated = _receive_until(ws2, "STATE_UPDATE")["state"]
            assert updated["gameId"] == game_id
            assert updated["phase"] != "GAME_OVER"
            assert updated["startingBidderIndex"] == (previous_start + 1) % 4
