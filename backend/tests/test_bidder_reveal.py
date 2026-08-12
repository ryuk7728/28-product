import pytest

import app.bots.rollout_bot as rb
from app.engine.cards_adapter import from_card_id, to_card_id
from _pytest.monkeypatch import MonkeyPatch


def test_rollout_worker_bidder_reveal_adds_then_plays_trump_indicator(
    monkeypatch,
) -> None:
    """
    Scenario:
      - P3 (seat 2) is the bidder (finalBid=3 1-indexed) with concealed trump
        indicator = Ace of Clubs.
      - P2 (seat 1) leads Jack of Hearts.
      - P3 is void in Hearts, so legal actions include [False, True].
      - We want to ensure that when the reveal=True branch is explored inside
        minimax_extended (called by rollout_worker):
          1) the indicator card is appended to bidder's hand
          2) actions() returns [playerTrump] (non-None) for bidder
          3) after playing, it's removed from bidder's hand.
    """
    # This test instruments Python recursion internals; make that dependency
    # explicit so a developer's strict-Rust environment cannot bypass the spies.
    monkeypatch.setattr(rb.legacy_minimax, "_MINIMAX_BACKEND_REQUESTED", "python")

    bidder_seat = 2  # P3
    indicator_cid = "Clubs_Ace"

    # Minimal snapshot at the moment AFTER P2 led Jack of Hearts
    # It's now P3's turn (actor = (leaderIndex + len(s)) % 4 = (1 + 1) % 4 = 2)
    snapshot = {
        "botSeat": bidder_seat,
        "finalBid": 3,  # legacy 1-indexed bidder seat
        "bidderSeat": bidder_seat,
        "leaderIndex": 1,  # P2 led the trick
        "catchNumber": 1,
        "k": 1,  # keep minimax_extended shallow/fast: evaluate 1 completed trick
        "trumpReveal": False,
        "knownTrumpSuit": None,
        "chose": False,
        "currentSuit": "Hearts",
        "trumpPlayed": False,
        "trumpIndice": [0, 0, 0, 0],
        "sCardIds": ["Hearts_Jack"],  # P2 already played
        # Bot/bidder's visible hand: only Queen of Diamonds (no Hearts)
        # (Concealed trump indicator is NOT in hand pre-reveal)
        "botHandCardIds": ["Diamonds_Queen"],
        # Hand sizes for each seat at this moment:
        # P1: 2 cards, P2: 1 card left, P3: 1 card, P4: 2 cards
        "handSizes": [2, 1, 1, 2],
        "playedCardIds": ["Hearts_Jack"],
        "concealedTrumpCardId": indicator_cid,
        # No void knowledge constraints for this unit test
        "suitMatrix": [[1, 1, 1, 1] for _ in range(4)],
    }

    # Flags that must become True during the rollout search
    saw_reveal_true_by_bidder = {"ok": False}
    saw_actions_return_player_trump = {"ok": False}
    saw_play_indicator = {"ok": False}

    # --- Wrap legacy actions() to assert it returns [playerTrump] post-reveal ---
    orig_actions = rb.legacy_minimax.actions

    def wrapped_actions(
        s,
        players,
        trumpReveal,
        trumpSuit,
        currentSuit,
        chose,
        finalBid,
        playerTrump,
        trumpPlayed,
        trumpIndice,
        reveal=-1,
        playerChance=0,
    ):
        out = orig_actions(
            s,
            players,
            trumpReveal,
            trumpSuit,
            currentSuit,
            chose,
            finalBid,
            playerTrump,
            trumpPlayed,
            trumpIndice,
            reveal,
            playerChance,
        )
        print("INSIDE ACTIONS")

        # Determine actor the same way legacy actions does internally:
        actor = (playerChance + len(s)) % 4

        # We only assert in the very specific state we care about:
        # - bidder is actor
        # - trumpReveal True and chose True (right after reveal decision)
        # - playerTrump is still present (your modified legacy keeps it)
        if (
            actor == bidder_seat
            and trumpReveal is True
            and chose is True
            and playerTrump is not None
            and to_card_id(playerTrump) == indicator_cid
        ):
            # In this state, legacy rules say bidder must play playerTrump:
            assert isinstance(out, list)
            assert len(out) == 1, f"Expected [playerTrump], got {out}"
            assert out[0] is not None, "Expected playerTrump to be non-None"
            assert to_card_id(out[0]) == indicator_cid, (
                f"Expected actions() to return the indicator {indicator_cid}, "
                f"got {to_card_id(out[0])}"
            )
            print("MODIFIED ACTIONS")
            saw_actions_return_player_trump["ok"] = True

        return out

    monkeypatch.setattr(rb.legacy_minimax, "actions", wrapped_actions)

    # --- Wrap legacy result() to assert bidder hand mutation correctness ---
    orig_result = rb.legacy_minimax.result

    def wrapped_result(
        s,
        a,
        currentSuit,
        trumpReveal,
        chose,
        playerTrump,
        trumpPlayed,
        trumpIndice,
        players,
        trumpSuit,
        finalBid,
        playerChance,
    ):
        actor = (playerChance + len(s)) % 4

        # Case 1: bidder chooses reveal=True
        if isinstance(a, bool) and a is True and actor == bidder_seat:
            # Preconditions: indicator not in hand yet
            assert playerTrump is not None, "playerTrump unexpectedly None pre-reveal"
            assert to_card_id(playerTrump) == indicator_cid
            assert not any(
                to_card_id(c) == indicator_cid for c in players[bidder_seat]["cards"]
            ), "Indicator should not be in bidder hand before reveal"

            out = orig_result(
                s,
                a,
                currentSuit,
                trumpReveal,
                chose,
                playerTrump,
                trumpPlayed,
                trumpIndice,
                players,
                trumpSuit,
                finalBid,
                playerChance,
            )

            (
                _cs2,
                _s2,
                trumpReveal2,
                chose2,
                playerTrump2,
                _tp2,
                _ti2,
                players2,
                _ts2,
                _fb2,
                _undo2,
            ) = out

            assert trumpReveal2 is True and chose2 is True
            assert playerTrump2 is not None, (
                "Expected playerTrump to remain non-None after bidder reveal=True "
                "(per your modified legacy behavior)"
            )
            assert to_card_id(playerTrump2) == indicator_cid

            # Postcondition: indicator is now in bidder's hand
            assert any(
                to_card_id(c) == indicator_cid for c in players2[bidder_seat]["cards"]
            ), "Indicator should be appended to bidder hand after reveal=True"
            print("MODIFIED RESULT CASE 1")
            saw_reveal_true_by_bidder["ok"] = True
            return out

        # Case 2: bidder plays the indicator card (must be in hand beforehand)
        if (
            not isinstance(a, bool)
            and actor == bidder_seat
            and playerTrump is not None
            and to_card_id(playerTrump) == indicator_cid
            and to_card_id(a) == indicator_cid
        ):
            # Must be in bidder hand BEFORE playing
            assert any(
                to_card_id(c) == indicator_cid for c in players[bidder_seat]["cards"]
            ), "Indicator must be in bidder hand before it is played"

            out = orig_result(
                s,
                a,
                currentSuit,
                trumpReveal,
                chose,
                playerTrump,
                trumpPlayed,
                trumpIndice,
                players,
                trumpSuit,
                finalBid,
                playerChance,
            )

            (
                _cs2,
                s2,
                _tr2,
                _ch2,
                playerTrump2,
                _tp2,
                _ti2,
                players2,
                _ts2,
                _fb2,
                _undo2,
            ) = out

            # Must appear in trick now
            assert any(to_card_id(c) == indicator_cid for c in s2)

            # Must be removed from bidder hand after play (no duplicates)
            assert not any(
                to_card_id(c) == indicator_cid for c in players2[bidder_seat]["cards"]
            ), "Indicator should not remain in bidder hand after being played"

            # Ideally becomes None when actually played (depends on object identity)
            # This is the behavior you described: only becomes None if a == playerTrump.
            assert (
                playerTrump2 is None
            ), "Expected playerTrump to become None once it is actually played"
            print("MODIFIED RESULT CASE 2")
            saw_play_indicator["ok"] = True
            return out

        return orig_result(
            s,
            a,
            currentSuit,
            trumpReveal,
            chose,
            playerTrump,
            trumpPlayed,
            trumpIndice,
            players,
            trumpSuit,
            finalBid,
            playerChance,
        )

    monkeypatch.setattr(rb.legacy_minimax, "result", wrapped_result)

    # Run exactly the worker code path (in-process) so our patches apply.
    # n=1 is sufficient because minimax_extended explores both False/True branches
    # at the root (no beta bound to prune the second action).
    rb.rollout_worker(snapshot=snapshot, n=1, seed=123)

    assert saw_reveal_true_by_bidder["ok"], "Did not observe bidder reveal=True branch"
    assert saw_actions_return_player_trump["ok"], (
        "Did not observe actions() returning [playerTrump] post-reveal"
    )
    assert saw_play_indicator["ok"], "Did not observe bidder playing the indicator"



# monke = MonkeyPatch()

# test_rollout_worker_bidder_reveal_adds_then_plays_trump_indicator(monke)


