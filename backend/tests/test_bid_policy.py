from __future__ import annotations

import pytest

from app.bots.bid_policy import (
    AGGRESSIVE_THRESHOLDS,
    OPTIMAL_THRESHOLDS,
    BidPolicyConfig,
    BidThresholds,
    EXPECTED_CANONICAL_KEYS,
    PooledBidStats,
    choose_r1_bid_from_stats,
    load_bid_policy_dataset,
    pooled_stats_for_canonical,
    stats_for_canonical,
)
from app.engine.canonical_key import build_canonical_key_and_mapping


def _stats(**percentages: int) -> PooledBidStats:
    successes = [0] * 15
    last = 100
    for contract in range(14, 29):
        value = percentages.get(f"p{contract}", 0)
        if value > last:
            raise ValueError("Synthetic cumulative probabilities must not increase.")
        successes[contract - 14] = value
        last = value
    return PooledBidStats(completed=100, successes=tuple(successes))


@pytest.mark.parametrize(
    ("stats", "expected"),
    [
        (_stats(p14=80, p15=70, p16=66), 16),
        (_stats(p14=80, p15=70, p16=65), 15),
        (_stats(p14=61, p15=60, p16=50), 14),
        (_stats(p14=60, p15=50, p16=40), 14),
    ],
)
def test_opening_bid_uses_approved_thresholds_and_forced_fallback(
    stats: PooledBidStats, expected: int
) -> None:
    assert (
        choose_r1_bid_from_stats(
            stats,
            min_bid_exclusive=13,
            max_bid_inclusive=23,
            is_opening_bidder=True,
        )
        == expected
    )


def test_opening_bid_with_no_completed_games_is_forced_to_14() -> None:
    stats = PooledBidStats(completed=0, successes=(0,) * 15)
    assert (
        choose_r1_bid_from_stats(
            stats,
            min_bid_exclusive=13,
            max_bid_inclusive=23,
            is_opening_bidder=True,
        )
        == 14
    )


@pytest.mark.parametrize(
    ("stats", "minimum", "expected"),
    [
        (_stats(p14=90, p15=75, p16=70), 14, 15),
        (_stats(p14=90, p15=80, p16=71), 14, 16),
        (_stats(p14=90, p15=80, p16=61), 15, 16),
        (_stats(p14=90, p15=80, p16=70, p17=60), 16, 0),
        (_stats(p14=90, p15=80, p16=70, p17=61), 16, 17),
        (
            _stats(
                p14=90,
                p15=85,
                p16=80,
                p17=75,
                p18=70,
                p19=65,
                p20=61,
            ),
            19,
            20,
        ),
    ],
)
def test_later_bidder_uses_next_legal_bid_with_only_approved_jump(
    stats: PooledBidStats, minimum: int, expected: int
) -> None:
    assert (
        choose_r1_bid_from_stats(
            stats,
            min_bid_exclusive=minimum,
            max_bid_inclusive=23,
            is_opening_bidder=False,
        )
        == expected
    )


def test_bundled_dataset_is_complete_and_uses_engine_canonical_keys() -> None:
    dataset = load_bid_policy_dataset()
    assert dataset.metadata["isComplete"] is True
    assert dataset.metadata["sourceRunId"] == "prod-20260808-bd500efa"
    assert dataset.metadata["recordCount"] == 226200
    assert len(dataset.by_key) == EXPECTED_CANONICAL_KEYS

    canonical = build_canonical_key_and_mapping(
        ["Clubs_Ace", "Clubs_Ten", "Diamonds_King", "Diamonds_Queen"]
    )
    stats = pooled_stats_for_canonical(canonical.canonical_groups)
    assert stats.completed == 100
    assert stats.success_count(14) >= stats.success_count(15)


def test_aggressive_preset_is_exactly_equivalent_to_previous_strict_thresholds() -> None:
    assert AGGRESSIVE_THRESHOLDS == BidThresholds(61, 66, 61, 71)
    stats = _stats(p14=70, p15=70, p16=66)
    assert choose_r1_bid_from_stats(
        stats,
        min_bid_exclusive=13,
        max_bid_inclusive=23,
        is_opening_bidder=True,
        thresholds=AGGRESSIVE_THRESHOLDS,
    ) == 16


@pytest.mark.parametrize(
    ("stats", "expected"),
    [
        (_stats(p14=80, p15=70, p16=69), 15),
        (_stats(p14=80, p15=70, p16=70), 16),
        (_stats(p14=66, p15=60, p16=50), 14),
    ],
)
def test_optimal_opening_boundaries(stats: PooledBidStats, expected: int) -> None:
    assert choose_r1_bid_from_stats(
        stats,
        min_bid_exclusive=13,
        max_bid_inclusive=23,
        is_opening_bidder=True,
        thresholds=OPTIMAL_THRESHOLDS,
    ) == expected


def test_custom_thresholds_control_later_bid_and_jump_independently() -> None:
    thresholds = BidThresholds(55, 80, 68, 76)
    stats = _stats(p14=90, p15=80, p16=75)
    assert choose_r1_bid_from_stats(
        stats,
        min_bid_exclusive=14,
        max_bid_inclusive=23,
        is_opening_bidder=False,
        thresholds=thresholds,
    ) == 15
    stats = _stats(p14=90, p15=80, p16=76)
    assert choose_r1_bid_from_stats(
        stats,
        min_bid_exclusive=14,
        max_bid_inclusive=23,
        is_opening_bidder=False,
        thresholds=thresholds,
    ) == 16


def test_position_buckets_are_complete_and_sum_to_pooled() -> None:
    canonical = [["A", "10"], ["K", "Q"]]
    pooled = stats_for_canonical(canonical)
    positions = [
        stats_for_canonical(canonical, bid_position=position)
        for position in range(1, 5)
    ]
    assert pooled.completed == 100
    assert all(position.completed == 25 for position in positions)
    for contract in range(14, 29):
        assert pooled.success_count(contract) == sum(
            position.success_count(contract) for position in positions
        )
    assert len({position.success_count(14) for position in positions}) > 1


def test_policy_config_exposes_resolved_preset_and_custom_values() -> None:
    assert BidPolicyConfig.optimal(position_aware=True).to_public_dict() == {
        "mode": "optimal",
        "positionAware": True,
        "thresholds": {
            "opening15": 67,
            "opening16": 70,
            "laterBid": 67,
            "jumpTo16": 75,
        },
    }
