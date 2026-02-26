from __future__ import annotations

from fastapi.testclient import TestClient

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
