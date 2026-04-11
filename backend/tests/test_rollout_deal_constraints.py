import time
import random

import app.bots.rollout_bot as rb
from app.settings import Settings

from _pytest.monkeypatch import MonkeyPatch

def test_deal_respects_void_constraints_multiple_runs() -> None:
    # Seat 1 is void in Hearts
    suit_matrix = [
        [1, 0, 1, 1],  # Hearts
        [1, 1, 1, 1],  # Diamonds
        [1, 1, 1, 1],  # Spades
        [1, 1, 1, 1],  # Clubs
    ]

    pool_ids = [
        "Hearts_Seven",
        "Hearts_Eight",
        "Diamonds_Seven",
        "Diamonds_Eight",
        "Spades_Seven",
        "Spades_Eight",
        "Clubs_Seven",
        "Clubs_Eight",
    ]

    # We will "fill" seats 1,2,3 (as if bot is seat 0)
    seats_to_fill = [1, 2, 3]
    hand_sizes = [0, 2, 3, 3]  # sums to 8, exactly pool size

    # Run multiple times with different seeds to ensure we never violate.
    for seed in range(50):
        rng = random.Random(seed)
        dealt = rb._deal_unknown_with_suit_constraints(
            rng=rng,
            pool_ids=pool_ids,
            seats_to_fill=seats_to_fill,
            hand_sizes=hand_sizes,
            suit_matrix=suit_matrix,
        )
        assert dealt is not None

        seat1_cards = dealt[1]
        assert all(not cid.startswith("Hearts_") for cid in seat1_cards)
        assert len(seat1_cards) == 2


def test_rollout_worker_fallback_does_not_hang_when_constraints_impossible(
    monkeypatch,
) -> None:
    """
    Construct an impossible constrained deal:
      - remaining pool is ONLY Hearts (8 cards)
      - seat 1 needs 6 cards
      - seat 1 is void in Hearts
    This should cause constrained dealing to fail, then rollout_worker should
    fall back to unconstrained slicing and still complete quickly.

    We monkeypatch minimax_extended to a trivial stub to keep the test fast.
    """

    # Make rollout_worker fast: stub minimax_extended to just add one action.
    def fake_minimax_extended(*args, **kwargs):
        reward_distribution = args[15]
        reward_distribution.append((True, 0.0))
        return 0.0

    monkeypatch.setattr(rb.legacy_minimax, "minimax_extended", fake_minimax_extended)

    # Force small retries so we exercise "retries exhausted -> fallback"
    rb.settings = Settings(rollouts=1, workers=1, rollout_deal_retries=2)

    deck_ids = rb._full_deck_card_ids()
    non_hearts = [cid for cid in deck_ids if not cid.startswith("Hearts_")]

    # Put all non-hearts into bot's known hand => unknown pool becomes only Hearts (8)
    snapshot = {
        "botSeat": 0,
        "finalBid": 1,  # 1-indexed
        "bidderSeat": 0,
        "leaderIndex": 0,
        "catchNumber": 1,
        "k": 1,
        "trumpReveal": True,
        "knownTrumpSuit": "Spades",
        "chose": False,
        "currentSuit": "",
        "trumpPlayed": False,
        "trumpIndice": [0, 0, 0, 0],
        "sCardIds": [],
        "botHandCardIds": non_hearts,  # 24 cards
        "handSizes": [len(non_hearts), 6, 1, 1],  # others sum to 8 (Hearts)
        "playedCardIds": [],
        "concealedTrumpCardId": None,
        # Seat 1 is void in Hearts (impossible because pool is all Hearts)
        "suitMatrix": [
            [1, 0, 1, 1],  # Hearts
            [1, 1, 1, 1],  # Diamonds
            [1, 1, 1, 1],  # Spades
            [1, 1, 1, 1],  # Clubs
        ],
    }

    start = time.time()
    out = rb.rollout_worker(snapshot=snapshot, n=1, seed=123)
    elapsed = time.time() - start

    # Should complete quickly (no hang)
    assert elapsed < 2.0

    # Our fake minimax always returns True once
    assert out.get(True) == 1

# monke = MonkeyPatch()

# test_rollout_worker_fallback_does_not_hang_when_constraints_impossible(monke)


def test_rollout_worker_respects_bidder_spade_non_trump_inference(monkeypatch) -> None:
    sampled_suits: list[str] = []

    def fake_minimax_extended(*args, **kwargs):
        sampled_suits.append(args[10])
        reward_distribution = args[15]
        reward_distribution.append((True, 0.0))
        return 0.0

    monkeypatch.setattr(rb.legacy_minimax, "minimax_extended", fake_minimax_extended)

    rb.settings = Settings(rollouts=1, workers=1, rollout_deal_retries=5)

    snapshot = {
        "botSeat": 0,
        "finalBid": 2,
        "bidderSeat": 1,
        "leaderIndex": 1,
        "catchNumber": 1,
        "k": 1,
        "trumpReveal": False,
        "knownTrumpSuit": None,
        "chose": False,
        "currentSuit": "Spades",
        "trumpPlayed": False,
        "trumpIndice": [0, 0, 0, 0],
        "sCardIds": ["Spades_Ace"],
        "playedCardIds": ["Spades_Ace"],
        "concealedTrumpCardId": None,
        "botHandCardIds": [
            "Hearts_Seven",
            "Hearts_Eight",
            "Diamonds_Seven",
            "Diamonds_Eight",
            "Clubs_Seven",
            "Clubs_Eight",
            "Spades_Seven",
            "Spades_Eight",
        ],
        "handSizes": [8, 6, 8, 8],
        "suitMatrix": [[1, 1, 1, 1] for _ in range(4)],
        "trumpMatrix": [
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [1, 0, 1, 1],
            [1, 1, 1, 1],
        ],
    }

    out = rb.rollout_worker(snapshot=snapshot, n=40, seed=123)

    assert out.get(True) == 40
    assert sampled_suits
    assert all(suit != "Spades" for suit in sampled_suits)


def test_rollout_worker_respects_bidder_diamond_non_trump_inference(monkeypatch) -> None:
    sampled_suits: list[str] = []

    def fake_minimax_extended(*args, **kwargs):
        sampled_suits.append(args[10])
        reward_distribution = args[15]
        reward_distribution.append((True, 0.0))
        return 0.0

    monkeypatch.setattr(rb.legacy_minimax, "minimax_extended", fake_minimax_extended)

    rb.settings = Settings(rollouts=1, workers=1, rollout_deal_retries=5)

    snapshot = {
        "botSeat": 0,
        "finalBid": 2,
        "bidderSeat": 1,
        "leaderIndex": 1,
        "catchNumber": 1,
        "k": 1,
        "trumpReveal": False,
        "knownTrumpSuit": None,
        "chose": False,
        "currentSuit": "Diamonds",
        "trumpPlayed": False,
        "trumpIndice": [0, 0, 0, 0],
        "sCardIds": ["Diamonds_Ace"],
        "playedCardIds": ["Diamonds_Ace"],
        "concealedTrumpCardId": None,
        "botHandCardIds": [
            "Hearts_Seven",
            "Hearts_Eight",
            "Spades_Seven",
            "Spades_Eight",
            "Clubs_Seven",
            "Clubs_Eight",
            "Diamonds_Seven",
            "Diamonds_Eight",
        ],
        "handSizes": [8, 6, 8, 8],
        "suitMatrix": [[1, 1, 1, 1] for _ in range(4)],
        "trumpMatrix": [
            [1, 1, 1, 1],
            [1, 0, 1, 1],
            [1, 1, 1, 1],
            [1, 1, 1, 1],
        ],
    }

    out = rb.rollout_worker(snapshot=snapshot, n=40, seed=456)

    assert out.get(True) == 40
    assert sampled_suits
    assert all(suit != "Diamonds" for suit in sampled_suits)
