from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.main import app


def _drain_until(ws, predicate, max_msgs: int = 200) -> tuple[dict[str, Any], dict]:
    state = None
    legal = None

    for _ in range(max_msgs):
        msg = ws.receive_json()
        if msg.get("type") == "STATE_UPDATE":
            state = msg["state"]
        elif msg.get("type") == "LEGAL_ACTIONS":
            legal = msg["actions"]
        elif msg.get("type") == "ERROR":
            raise AssertionError(f"WS ERROR: {msg.get('message')}")
        if state is not None and legal is not None and predicate(state, legal):
            return state, legal

    raise AssertionError("Timed out waiting for expected WS state/actions.")


def _card_ids_for_seat(state: dict[str, Any], seat: int) -> list[str]:
    return [c["cardId"] for c in state["players"][seat]["cards"]]


def test_ws_bot_bid_r1_then_bot_selects_trump_then_bots_pass_r2() -> None:
    with TestClient(app) as client:
        first4Hands = [
            ["Spades_Jack", "Spades_Nine", "Spades_Seven", "Hearts_Ace"],
            ["Hearts_King", "Diamonds_Ace", "Clubs_Seven", "Clubs_Eight"],
            ["Diamonds_Jack", "Diamonds_Nine", "Clubs_Ace", "Spades_Ace"],
            ["Hearts_Seven", "Hearts_Eight", "Clubs_King", "Diamonds_Seven"],
        ]

        res = client.post(
            "/games",
            json={"startingBidderIndex": 0, "first4Hands": first4Hands},
        )
        assert res.status_code == 200
        game_id = res.json()["gameId"]

        with client.websocket_connect(f"/ws/games/{game_id}") as ws:
            state, legal = _drain_until(
                ws,
                lambda s, a: a.get("type") == "BID_R1" and a.get("seatIndex") == 1,
            )
            assert state["phase"] == "BIDDING_R1"
            # The pooled empirical policy opens this canonical hand at 15.
            assert state["bidsR1"][0] == 15

            ws.send_json({"type": "SUBMIT_BID", "seatIndex": 1, "bidValue": 0})

            state, legal = _drain_until(
                ws,
                lambda s, a: a.get("type") == "BID_R1" and a.get("seatIndex") == 3,
            )
            assert state["bidsR1"][2] == 0

            ws.send_json({"type": "SUBMIT_BID", "seatIndex": 3, "bidValue": 0})

            state, legal = _drain_until(
                ws, lambda s, a: a.get("type") == "MANUAL_DEAL_REST"
            )
            assert state["phase"] == "MANUAL_DEAL_REST"
            assert state["finalBidderSeat"] == 0
            assert state["finalBidValue"] == 15
            assert state["hasConcealedTrump"] is True

            seat0_cards = _card_ids_for_seat(state, 0)
            assert "Spades_Seven" not in seat0_cards

            remaining = legal["remainingCardIds"]
            assert len(remaining) == 16

            restHands = [
                remaining[0:4],
                remaining[4:8],
                remaining[8:12],
                remaining[12:16],
            ]
            ws.send_json({"type": "SUBMIT_REST_DEAL", "restHands": restHands})

            state, legal = _drain_until(
                ws,
                lambda s, a: a.get("type") == "BID_R2" and a.get("seatIndex") == 1,
            )
            assert state["phase"] == "BIDDING_R2"
            assert state["bidsR2"][0] == 0

            ws.send_json({"type": "SUBMIT_BID", "seatIndex": 1, "bidValue": 0})

            state, legal = _drain_until(
                ws,
                lambda s, a: a.get("type") == "BID_R2" and a.get("seatIndex") == 3,
            )
            assert state["bidsR2"][2] == 0


def test_ws_bot_uses_per_game_policy_and_actual_bid_position(monkeypatch) -> None:
    observed: list[dict[str, Any]] = []

    def fake_choose(_groups, **kwargs) -> int:
        observed.append(kwargs)
        return 14

    monkeypatch.setattr("app.api.ws.choose_r1_bid_from_data", fake_choose)
    first4_hands = [
        ["Spades_Jack", "Spades_Nine", "Spades_Seven", "Hearts_Ace"],
        ["Hearts_King", "Diamonds_Ace", "Clubs_Seven", "Clubs_Eight"],
        ["Diamonds_Jack", "Diamonds_Nine", "Clubs_Ace", "Spades_Ace"],
        ["Hearts_Seven", "Hearts_Eight", "Clubs_King", "Diamonds_Seven"],
    ]
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
        response = client.post(
            "/games",
            json={
                "startingBidderIndex": 0,
                "first4Hands": first4_hands,
                "biddingPolicy": policy,
            },
        )
        assert response.status_code == 200
        with client.websocket_connect(f"/ws/games/{response.json()['gameId']}") as socket:
            state, _legal = _drain_until(
                socket,
                lambda _state, actions: actions.get("type") == "BID_R1"
                and actions.get("seatIndex") == 1,
            )
    assert state["botBiddingPolicy"] == policy
    assert len(observed) == 1
    assert observed[0]["bid_position"] == 1
    assert observed[0]["policy"].position_aware is True
    assert observed[0]["policy"].thresholds.jump_to_16 == 81
