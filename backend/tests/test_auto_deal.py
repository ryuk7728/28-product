"""
Tests for the auto-deal functionality.

Test coverage:
- T2.2.1: POST /games/auto returns valid gameId
- T2.2.2: Each player has 4 cards, 16 in draw pile
- T2.2.3: All 32 cards unique across hands + draw pile
- T2.2.4: Two calls produce different distributions (randomness)
- T2.3.1: Auto-deal-rest distributes correctly
- T2.3.2: Auto-deal-rest checks abort conditions
"""
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
            # Return special marker for abort
            return {"aborted": True, "reason": msg.get("reason")}, {"type": "ABORTED"}

        if state is not None and legal is not None and predicate(state, legal):
            return state, legal

    raise AssertionError("Timed out waiting for expected WS state/actions.")


def _card_ids_for_seat(state: dict[str, Any], seat: int) -> list[str]:
    return [c["cardId"] for c in state["players"][seat]["cards"]]


def _all_card_ids_in_state(state: dict[str, Any]) -> set[str]:
    """Get all card IDs from all players' hands."""
    all_ids = set()
    for player in state["players"]:
        for card in player["cards"]:
            all_ids.add(card["cardId"])
    return all_ids


class TestAutoCreateGame:
    """Tests for POST /games/auto endpoint."""

    def test_auto_deal_creates_game(self):
        """T2.2.1: POST /games/auto returns valid gameId."""
        with TestClient(app) as client:
            res = client.post("/games/auto", json={"startingBidderIndex": 0})
            assert res.status_code == 200
            data = res.json()
            assert "gameId" in data
            assert isinstance(data["gameId"], str)
            assert len(data["gameId"]) > 0

    def test_auto_deal_distributes_16_cards(self):
        """T2.2.2: Each player has 4 cards, 16 in draw pile."""
        with TestClient(app) as client:
            res = client.post("/games/auto", json={"startingBidderIndex": 1})
            assert res.status_code == 200
            game_id = res.json()["gameId"]

            # Get game state
            state_res = client.get(f"/games/{game_id}")
            assert state_res.status_code == 200
            state = state_res.json()

            # Each player should have 4 cards
            for i, player in enumerate(state["players"]):
                assert player["cardCount"] == 4, f"Player {i} should have 4 cards"
                assert len(player["cards"]) == 4, f"Player {i} cards list should have 4 items"

            # Draw pile should have 16 cards
            assert state["drawPileCount"] == 16

    def test_auto_deal_no_duplicates(self):
        """T2.2.3: All 32 cards unique across hands + draw pile."""
        with TestClient(app) as client:
            res = client.post("/games/auto", json={"startingBidderIndex": 2})
            assert res.status_code == 200
            game_id = res.json()["gameId"]

            # Access internal state to verify draw pile contents
            state_obj = game_manager.get_game(game_id)
            assert state_obj is not None

            # Collect all card IDs
            all_card_ids = []
            for hand in state_obj.players_cards:
                for card in hand:
                    all_card_ids.append(to_card_id(card))
            for card in state_obj.draw_pile:
                all_card_ids.append(to_card_id(card))

            # Should be exactly 32 unique cards
            assert len(all_card_ids) == 32
            assert len(set(all_card_ids)) == 32, "All cards should be unique"

    def test_auto_deal_random(self):
        """T2.2.4: Two calls produce different distributions."""
        with TestClient(app) as client:
            # Create two games
            res1 = client.post("/games/auto", json={"startingBidderIndex": 0})
            res2 = client.post("/games/auto", json={"startingBidderIndex": 0})
            assert res1.status_code == 200
            assert res2.status_code == 200

            game_id1 = res1.json()["gameId"]
            game_id2 = res2.json()["gameId"]

            # Get states
            state1 = client.get(f"/games/{game_id1}").json()
            state2 = client.get(f"/games/{game_id2}").json()

            # Get all card IDs for both games
            cards1 = _all_card_ids_in_state(state1)
            cards2 = _all_card_ids_in_state(state2)

            # Both should have same set of cards (dealt from same 32-card deck)
            # but the distribution should be different (with very high probability)
            # Compare player 0's cards as a simple check
            p0_cards1 = set(_card_ids_for_seat(state1, 0))
            p0_cards2 = set(_card_ids_for_seat(state2, 0))

            # Note: There's a tiny probability they're the same, but astronomically unlikely
            # If this test flakes, we can make it more robust
            assert p0_cards1 != p0_cards2, "Two random deals should produce different hands"

    def test_auto_deal_starting_bidder_index(self):
        """Verify starting bidder index is respected."""
        with TestClient(app) as client:
            for bidder_idx in range(4):
                res = client.post("/games/auto", json={"startingBidderIndex": bidder_idx})
                assert res.status_code == 200
                game_id = res.json()["gameId"]

                state = client.get(f"/games/{game_id}").json()
                assert state["startingBidderIndex"] == bidder_idx
                assert state["biddingOrder"][0] == bidder_idx

    def test_auto_deal_invalid_starting_bidder(self):
        """Verify invalid starting bidder indices are rejected."""
        with TestClient(app) as client:
            # Test out of range values
            for invalid_idx in [-1, 4, 5, 100]:
                res = client.post("/games/auto", json={"startingBidderIndex": invalid_idx})
                assert res.status_code == 422  # Validation error

    def test_auto_deal_sets_auto_deal_flag(self):
        """Verify autoDeal flag is set in state."""
        with TestClient(app) as client:
            res = client.post("/games/auto", json={"startingBidderIndex": 0})
            assert res.status_code == 200
            game_id = res.json()["gameId"]

            state = client.get(f"/games/{game_id}").json()
            assert state["autoDeal"] is True


class TestAutoRestDeal:
    """Tests for automatic rest deal (R2 cards) when auto_deal=True."""

    def test_auto_deal_rest_distributes_correctly(self):
        """T2.3.1: Auto-deal-rest distributes 4 cards to each player."""
        with TestClient(app) as client:
            # Create auto-deal game with bot (seat 0) as starting bidder
            # This ensures bot bids first and humans can pass
            res = client.post("/games/auto", json={"startingBidderIndex": 0})
            assert res.status_code == 200
            game_id = res.json()["gameId"]

            with client.websocket_connect(f"/ws/games/{game_id}") as ws:
                # After connection, bot seat 0 bids first, then human at seat 1 gets turn.
                state, legal = _drain_until(
                    ws,
                    lambda s, a: a.get("type") == "BID_R1" and a.get("seatIndex") == 1,
                )

                # Human passes (can pass since not first bidder)
                ws.send_json({"type": "SUBMIT_BID", "seatIndex": 1, "bidValue": 0})

                # Wait for seat 3's turn (after bot seat 2 bids)
                state, legal = _drain_until(
                    ws,
                    lambda s, a: a.get("type") == "BID_R1" and a.get("seatIndex") == 3,
                )

                # Human passes
                ws.send_json({"type": "SUBMIT_BID", "seatIndex": 3, "bidValue": 0})

                # Now R1 should complete, trump selected by bot, and auto-deal should happen.
                # We should skip MANUAL_DEAL_REST and go directly to BIDDING_R2 or PLAY.
                # Since bots pass in R2, it should go to PLAY or we get human's R2 turn.
                #
                # Use a simpler predicate that just checks the state phase, since that's
                # what we really care about (phase != MANUAL_DEAL_REST after auto-deal).
                state, legal = _drain_until(
                    ws,
                    lambda s, a: (
                        s is not None
                        and s.get("phase") in ("BIDDING_R2", "PLAY", "GAME_OVER")
                    ),
                )

                # Check if game was aborted (can happen with random deals)
                if isinstance(state, dict) and state.get("aborted"):
                    # Abort is acceptable - it means abort conditions were checked
                    return

                # GAME_OVER with winnerTeam indicates abort or finished game
                if state.get("phase") == "GAME_OVER":
                    # Aborted game - acceptable for random deals that hit abort conditions
                    return

                # If not aborted, verify cards were dealt
                # Each player should now have 8 cards total.
                # Note: The bidder has 7 cards + 1 concealed trump (stored separately),
                # so their visible cardCount is 7 but they effectively have 8 cards.
                final_bidder = state["finalBidderSeat"]
                has_concealed = state["hasConcealedTrump"]

                for i, player in enumerate(state["players"]):
                    card_count = len(player["cards"])
                    if i == final_bidder and has_concealed:
                        # Bidder has 7 visible cards + 1 concealed trump = 8 total
                        assert card_count == 7, f"Bidder (Player {i}) should have 7 visible cards (plus concealed trump)"
                    else:
                        assert card_count == 8, f"Player {i} should have 8 cards after auto-deal-rest"

                # Draw pile should be empty
                assert state["drawPileCount"] == 0

                # Phase should be BIDDING_R2 or PLAY (not MANUAL_DEAL_REST)
                assert state["phase"] in ("BIDDING_R2", "PLAY")

    def test_auto_deal_skips_manual_deal_phase(self):
        """Verify MANUAL_DEAL_REST phase is skipped when auto_deal=True."""
        with TestClient(app) as client:
            # Create auto-deal game
            res = client.post("/games/auto", json={"startingBidderIndex": 1})
            assert res.status_code == 200
            game_id = res.json()["gameId"]

            phases_seen = set()

            with client.websocket_connect(f"/ws/games/{game_id}") as ws:
                # Collect phases as we go through the game
                for _ in range(100):
                    try:
                        msg = ws.receive_json()
                    except Exception:
                        break

                    if msg.get("type") == "STATE_UPDATE":
                        phase = msg["state"]["phase"]
                        phases_seen.add(phase)

                        # If we've reached R2 or PLAY, break
                        if phase in ("BIDDING_R2", "PLAY"):
                            break

                    if msg.get("type") == "GAME_ABORTED":
                        # Abort is fine - abort conditions were checked
                        return

                    if msg.get("type") == "LEGAL_ACTIONS":
                        actions = msg["actions"]
                        if actions.get("type") == "BID_R1":
                            seat = actions.get("seatIndex")
                            if seat in (1, 3):  # Human seats
                                ws.send_json({"type": "SUBMIT_BID", "seatIndex": seat, "bidValue": 0})

            # MANUAL_DEAL_REST should never appear in auto-deal mode
            assert "MANUAL_DEAL_REST" not in phases_seen, "MANUAL_DEAL_REST should be skipped in auto-deal mode"

    def test_auto_deal_rest_checks_abort_all_jacks(self, monkeypatch):
        """T2.3.2: Auto-deal-rest checks abort conditions (all four jacks)."""
        # This test forces a specific deck order where one player gets all 4 jacks
        # after the auto-deal-rest happens.

        # Create a fixed deck where after dealing:
        # - First 16 cards (first4 for 4 players) have no jacks
        # - Next 4 cards (rest for player 0) are all 4 jacks
        first16 = [
            # Seat 0 first 4
            "Spades_Nine", "Hearts_Nine", "Diamonds_Nine", "Clubs_Nine",
            # Seat 1 first 4
            "Spades_Ace", "Hearts_Ace", "Diamonds_Ace", "Clubs_Ace",
            # Seat 2 first 4
            "Spades_Ten", "Hearts_Ten", "Diamonds_Ten", "Clubs_Ten",
            # Seat 3 first 4
            "Spades_King", "Hearts_King", "Diamonds_King", "Clubs_King",
        ]

        # Rest 16 cards - put all jacks first so they go to seat 0
        rest16 = [
            # Will go to seat 0 (giving them all 4 jacks)
            "Spades_Jack", "Hearts_Jack", "Diamonds_Jack", "Clubs_Jack",
            # Will go to seat 1
            "Spades_Queen", "Hearts_Queen", "Diamonds_Queen", "Clubs_Queen",
            # Will go to seat 2
            "Spades_Eight", "Hearts_Eight", "Diamonds_Eight", "Clubs_Eight",
            # Will go to seat 3
            "Spades_Seven", "Hearts_Seven", "Diamonds_Seven", "Clubs_Seven",
        ]

        full_deck = first16 + rest16

        def _make_fixed_deck() -> list:
            deck = Cards.packOf28()
            by_id = {to_card_id(c): c for c in deck}
            return [by_id[cid] for cid in full_deck]

        fixed_deck = _make_fixed_deck()

        # Patch to use fixed deck and disable shuffle
        monkeypatch.setattr(Cards, "packOf28", classmethod(lambda cls: list(fixed_deck)))

        import app.engine.game_manager as gm_module
        monkeypatch.setattr(gm_module.random, "shuffle", lambda x: None)

        with TestClient(app) as client:
            res = client.post("/games/auto", json={"startingBidderIndex": 0})
            assert res.status_code == 200
            game_id = res.json()["gameId"]

            with client.websocket_connect(f"/ws/games/{game_id}") as ws:
                # Advance through bidding - humans pass
                aborted = False
                abort_reason = None

                for _ in range(200):
                    try:
                        msg = ws.receive_json()
                    except Exception:
                        break

                    if msg.get("type") == "GAME_ABORTED":
                        aborted = True
                        abort_reason = msg.get("reason")
                        break

                    if msg.get("type") == "LEGAL_ACTIONS":
                        actions = msg["actions"]
                        if actions.get("type") == "BID_R1":
                            seat = actions.get("seatIndex")
                            if seat in (1, 3):
                                ws.send_json({"type": "SUBMIT_BID", "seatIndex": seat, "bidValue": 0})

                assert aborted, "Game should be aborted due to all four jacks"
                assert abort_reason == "ALL_FOUR_JACKS"


class TestManualVsAutoDeal:
    """Comparison tests between manual and auto deal."""

    def test_manual_deal_has_auto_deal_false(self):
        """Manual deal games should have autoDeal=False."""
        with TestClient(app) as client:
            first4Hands = [
                ["Hearts_Jack", "Spades_Nine", "Diamonds_Ace", "Clubs_Ten"],
                ["Hearts_Nine", "Spades_Ace", "Diamonds_Ten", "Clubs_Jack"],
                ["Hearts_Ace", "Spades_Ten", "Diamonds_Jack", "Clubs_Nine"],
                ["Hearts_Ten", "Spades_Jack", "Diamonds_Nine", "Clubs_Ace"],
            ]

            res = client.post("/games", json={"startingBidderIndex": 0, "first4Hands": first4Hands})
            assert res.status_code == 200
            game_id = res.json()["gameId"]

            state = client.get(f"/games/{game_id}").json()
            assert state["autoDeal"] is False

    def test_manual_deal_requires_manual_rest_deal(self):
        """Manual deal games should require MANUAL_DEAL_REST phase."""
        with TestClient(app) as client:
            first4Hands = [
                ["Hearts_Jack", "Spades_Nine", "Diamonds_Ace", "Clubs_Ten"],
                ["Hearts_Nine", "Spades_Ace", "Diamonds_Ten", "Clubs_Jack"],
                ["Hearts_Ace", "Spades_Ten", "Diamonds_Jack", "Clubs_Nine"],
                ["Hearts_Ten", "Spades_Jack", "Diamonds_Nine", "Clubs_Ace"],
            ]

            res = client.post("/games", json={"startingBidderIndex": 0, "first4Hands": first4Hands})
            assert res.status_code == 200
            game_id = res.json()["gameId"]

            with client.websocket_connect(f"/ws/games/{game_id}") as ws:
                # Let bots bid and humans pass
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

                # Should reach MANUAL_DEAL_REST
                state, legal = _drain_until(
                    ws, lambda s, a: a.get("type") == "MANUAL_DEAL_REST"
                )

                assert state["phase"] == "MANUAL_DEAL_REST"
                assert legal["type"] == "MANUAL_DEAL_REST"
                assert len(legal["remainingCardIds"]) == 16
