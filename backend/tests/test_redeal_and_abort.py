from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.engine.game_manager import game_manager
from app.legacy.cards import Cards
from app.engine.cards_adapter import to_card_id


def _drain_until(
    ws, predicate, *, max_msgs: int = 300
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Reads WS messages until predicate(state, legal) is satisfied.
    Returns last (state, legal).
    """
    state = None
    legal = None

    for _ in range(max_msgs):
        msg = ws.receive_json()
        t = msg.get("type")

        if t == "STATE_UPDATE":
            state = msg["state"]
        elif t == "LEGAL_ACTIONS":
            legal = msg["actions"]
        elif t == "ERROR":
            raise AssertionError(f"WS ERROR: {msg.get('message')}")
        elif t == "GAME_ABORTED":
            raise AssertionError(f"Unexpected GAME_ABORTED: {msg}")

        if state is not None and legal is not None and predicate(state, legal):
            return state, legal

    raise AssertionError("Timed out waiting for expected WS state/actions.")


def _wait_for_game_aborted(
    ws, *, max_msgs: int = 200
) -> dict[str, Any]:
    """
    Waits for GAME_ABORTED message and returns it.
    """
    for _ in range(max_msgs):
        msg = ws.receive_json()
        t = msg.get("type")
        if t == "GAME_ABORTED":
            return msg
        if t == "ERROR":
            raise AssertionError(f"WS ERROR: {msg.get('message')}")
        # ignore STATE_UPDATE / LEGAL_ACTIONS while waiting
    raise AssertionError("Timed out waiting for GAME_ABORTED.")


def _card_ids_for_seat(state: dict[str, Any], seat: int) -> list[str]:
    return [c["cardId"] for c in state["players"][seat]["cards"]]


def _make_fixed_deck_order(first16_card_ids: list[str]) -> list:
    """
    Create a deterministic deck list of legacy Cards objects where the first 16 cards
    match first16_card_ids in order, and the remaining 16 are the rest in stable order.
    """
    deck = Cards.packOf28()
    by_id = {to_card_id(c): c for c in deck}

    used = set(first16_card_ids)
    remaining_ids = [cid for cid in by_id.keys() if cid not in used]

    fixed_ids = list(first16_card_ids) + remaining_ids
    assert len(fixed_ids) == 32
    assert len(set(fixed_ids)) == 32

    return [by_id[cid] for cid in fixed_ids]


def test_ws_bot_auto_redeal_when_starting_bidder_has_zero_points(monkeypatch) -> None:
    """
    Rule 1:
      - starting bidder is bot seat0
      - seat0 first4 has 0 point cards => canRedeal True
      - bot must always redeal
      - redeal happens in-place (same gameId)
      - after redeal, bot proceeds to bid and it becomes seat1's turn
    """
    with TestClient(app) as client:
        # First-4: seat0 has 0 points (only K/Q/8/7)
        first4Hands = [
            ["Clubs_King", "Diamonds_Queen", "Hearts_Seven", "Spades_Eight"],  # seat0 bot
            ["Hearts_Ace", "Diamonds_Ace", "Clubs_Ace", "Spades_Ace"],  # seat1 human
            ["Hearts_Ten", "Diamonds_Ten", "Clubs_Ten", "Spades_Ten"],  # seat2 bot
            ["Hearts_King", "Diamonds_King", "Clubs_Queen", "Spades_Queen"],  # seat3 human
        ]

        res = client.post(
            "/games",
            json={"startingBidderIndex": 0, "first4Hands": first4Hands},
        )
        assert res.status_code == 200
        game_id = res.json()["gameId"]

        # Make redeal deterministic so the test is stable.
        #
        # After redeal, seat0 receives a known hand whose empirical opening bid is 15:
        # seat0: Spades_Jack, Spades_Nine, Spades_Seven, Hearts_Ace
        fixed_first16 = (
            ["Spades_Jack", "Spades_Nine", "Spades_Seven", "Hearts_Ace"]
            + ["Hearts_King", "Diamonds_Ace", "Clubs_Seven", "Clubs_Eight"]
            + ["Diamonds_King", "Diamonds_Queen", "Clubs_Ace", "Spades_Ace"]
            + ["Hearts_Seven", "Hearts_Eight", "Clubs_King", "Diamonds_Seven"]
        )
        fixed_deck = _make_fixed_deck_order(fixed_first16)

        # Patch packOf28 for the duration of this test and disable shuffle inside redeal
        monkeypatch.setattr(Cards, "packOf28", classmethod(lambda cls: list(fixed_deck)))
        monkeypatch.setattr(
            __import__("app.engine.game_manager", fromlist=["random"]).random,
            "shuffle",
            lambda _x: None,
        )

        with client.websocket_connect(f"/ws/games/{game_id}") as ws:
            # After connect, bot seat0 should have requested redeal and then bid,
            # so it should now be seat1's turn in BID_R1.
            state, legal = _drain_until(
                ws,
                lambda s, a: a.get("type") == "BID_R1" and a.get("seatIndex") == 1,
            )

            assert state["phase"] == "BIDDING_R1"
            assert state["gameId"] == game_id

            # Confirm redeal happened (event log contains messages)
            log = "\n".join(state["eventLog"]).lower()
            assert "requested redeal" in log
            assert "redeal performed" in log

            # Confirm the bot used the pooled empirical policy after the redeal.
            assert state["bidsR1"][0] == 15

            # Confirm seat0's current hand is the redealt one (4 cards at this stage)
            seat0_cards = _card_ids_for_seat(state, 0)
            for cid in ["Spades_Jack", "Spades_Nine", "Spades_Seven", "Hearts_Ace"]:
                assert cid in seat0_cards


def test_ws_game_aborted_all_four_jacks_after_rest_deal() -> None:
    """
    Rule 2:
      - after full 8-card deal, if any player's 8-card hand includes all 4 jacks,
        backend must send GAME_ABORTED and delete game.
    """
    with TestClient(app) as client:
        # Ensure none of the four jacks are in first4 (so all four are in draw pile)
        first4Hands = [
            ["Spades_Nine", "Spades_Ace", "Hearts_Ace", "Diamonds_Ace"],  # seat0 bot
            ["Clubs_Nine", "Clubs_Ace", "Hearts_Ten", "Diamonds_Ten"],  # seat1 human
            ["Spades_Ten", "Hearts_Nine", "Diamonds_Nine", "Clubs_Ten"],  # seat2 bot
            ["Hearts_King", "Diamonds_King", "Clubs_King", "Spades_King"],  # seat3 human
        ]

        res = client.post(
            "/games",
            json={"startingBidderIndex": 0, "first4Hands": first4Hands},
        )
        assert res.status_code == 200
        game_id = res.json()["gameId"]

        with client.websocket_connect(f"/ws/games/{game_id}") as ws:
            # Let R1 complete: seat0 bot bids, seat1 human pass, seat2 bot pass, seat3 human pass
            state, legal = _drain_until(
                ws,
                lambda s, a: a.get("type") == "BID_R1" and a.get("seatIndex") == 1,
            )
            ws.send_json({"type": "SUBMIT_BID", "seatIndex": 1, "bidValue": 0})

            state, legal = _drain_until(
                ws,
                lambda s, a: a.get("type") == "BID_R1" and a.get("seatIndex") == 3,
            )
            ws.send_json({"type": "SUBMIT_BID", "seatIndex": 3, "bidValue": 0})

            # Bot should select trump and we should reach MANUAL_DEAL_REST
            state, legal = _drain_until(
                ws, lambda s, a: a.get("type") == "MANUAL_DEAL_REST"
            )

            remaining = legal["remainingCardIds"]
            assert len(remaining) == 16

            # Give seat1 ALL FOUR JACKS as its rest 4 cards
            jacks = ["Hearts_Jack", "Clubs_Jack", "Diamonds_Jack", "Spades_Jack"]
            for j in jacks:
                assert j in remaining

            remaining_wo_jacks = [cid for cid in remaining if cid not in set(jacks)]
            assert len(remaining_wo_jacks) == 12

            restHands = [
                remaining_wo_jacks[0:4],  # seat0
                jacks,  # seat1 -> will have all 4 jacks after 8 cards
                remaining_wo_jacks[4:8],  # seat2
                remaining_wo_jacks[8:12],  # seat3
            ]

            ws.send_json({"type": "SUBMIT_REST_DEAL", "restHands": restHands})

            aborted = _wait_for_game_aborted(ws)
            assert aborted["reason"] == "ALL_FOUR_JACKS"

        # Ensure game is deleted (new gameId required)
        g = client.get(f"/games/{game_id}")
        assert g.status_code == 404


def test_ws_game_aborted_all_trumps_one_side_after_rest_deal() -> None:
    """
    Rule 3:
      - after full 8-card deal, if bidding team has all 8 trumps and defenders 0,
        backend must send GAME_ABORTED and delete game.
    We craft:
      - bidder is seat0 bot (team1)
      - trump suit becomes Spades (bot selects Spades_Seven as concealed)
      - seats 0 and 2 collectively hold all 8 spades in their first4
      - remaining draw pile contains no spades
    """
    with TestClient(app) as client:
        # All 8 spades distributed to seats 0 and 2 in first4
        first4Hands = [
            ["Spades_Jack", "Spades_Nine", "Spades_Eight", "Spades_Seven"],  # seat0 bot
            ["Hearts_Ace", "Hearts_Ten", "Diamonds_Ace", "Clubs_Ace"],  # seat1 human
            ["Spades_Ace", "Spades_Ten", "Spades_King", "Spades_Queen"],  # seat2 bot
            ["Hearts_King", "Diamonds_King", "Clubs_King", "Hearts_Nine"],  # seat3 human
        ]

        res = client.post(
            "/games",
            json={"startingBidderIndex": 0, "first4Hands": first4Hands},
        )
        assert res.status_code == 200
        game_id = res.json()["gameId"]

        with client.websocket_connect(f"/ws/games/{game_id}") as ws:
            # Complete R1 with passes by humans
            state, legal = _drain_until(
                ws,
                lambda s, a: a.get("type") == "BID_R1" and a.get("seatIndex") == 1,
            )
            ws.send_json({"type": "SUBMIT_BID", "seatIndex": 1, "bidValue": 0})

            state, legal = _drain_until(
                ws,
                lambda s, a: a.get("type") == "BID_R1" and a.get("seatIndex") == 3,
            )
            ws.send_json({"type": "SUBMIT_BID", "seatIndex": 3, "bidValue": 0})

            # Bot selects trump -> should be Spades_Seven (weakest in [J,9,8,7])
            state, legal = _drain_until(
                ws, lambda s, a: a.get("type") == "MANUAL_DEAL_REST"
            )
            assert state["finalBidderSeat"] == 0
            assert state["hasConcealedTrump"] is True

            # Remaining should have no spades at all
            remaining = legal["remainingCardIds"]
            assert all(not cid.startswith("Spades_") for cid in remaining)

            # Any distribution works; condition depends only on trump suit and spade ownership
            restHands = [
                remaining[0:4],
                remaining[4:8],
                remaining[8:12],
                remaining[12:16],
            ]
            ws.send_json({"type": "SUBMIT_REST_DEAL", "restHands": restHands})

            aborted = _wait_for_game_aborted(ws)
            assert aborted["reason"] == "ALL_TRUMPS_ONE_SIDE"

        # Ensure game is deleted
        g = client.get(f"/games/{game_id}")
        assert g.status_code == 404
