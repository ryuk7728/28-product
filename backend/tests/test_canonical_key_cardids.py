from __future__ import annotations

import json
from typing import Any, List, Tuple

import pytest

from app.bots.bidding_bot import plan_bid_and_trump_from_first4
from app.engine.canonical_key import build_canonical_key_and_mapping
from app.engine.rules_infer import predict_bid_and_trump_index

RANK_CODE_TO_NAME = {
    "J": "Jack",
    "9": "Nine",
    "A": "Ace",
    "10": "Ten",
    "K": "King",
    "Q": "Queen",
    "8": "Eight",
    "7": "Seven",
}
RANK_NAME_TO_CODE = {v: k for k, v in RANK_CODE_TO_NAME.items()}
SUITS = ["Hearts", "Diamonds", "Spades", "Clubs"]


def _groups_from_case(case_key: Any) -> List[List[str]]:
    if isinstance(case_key, str):
        groups = json.loads(case_key)
    else:
        groups = case_key
    return groups


def _card_ids_from_groups(groups: List[List[str]]) -> List[str]:
    if len(groups) > len(SUITS):
        raise ValueError("At most 4 groups can be mapped to suits.")

    card_ids: List[str] = []
    for i, group in enumerate(groups):
        suit = SUITS[i]
        for rank in group:
            rank_name = RANK_CODE_TO_NAME[rank]
            card_ids.append(f"{suit}_{rank_name}")
    return card_ids


def _rank_code_from_card_id(card_id: str) -> str:
    _suit, rank_name = card_id.split("_", 1)
    return RANK_NAME_TO_CODE[rank_name]


@pytest.mark.parametrize(
    ("case_key", "expected"),
    [
        ('[["A"],["K"],["Q"],["7"]]', (14, 0)),
        ([["7"], ["J"], ["J"], ["A"]], (14, 0)),
        ('[["J","K"],["7"],["8"]]', (14, 1)),
        ('[["A","K"],["7"],["8"]]', (14, 0)),
        ('[["J","10"],["J"],["7"]]', (16, 1)),
        ('[["J","9","7"],["A"]]', (16, 2)),
        ('[["J","A","K"],["7"]]', (16, 1)),
        ('[["J","10","Q"],["7"]]', (16, 1)),
        ('[["J","10","8"],["7"]]', (15, 1)),
        ('[["J","K","Q"],["7"]]', (15, 1)),
        ('[["J","8","7"],["A"]]', (14, 1)),
        ('[["9","A","K"],["7"]]', (15, 1)),
        ('[["A","K","Q"],["7"]]', (14, 1)),
        ('[["J","A","8","7"]]', (16, 3)),
        ('[["J","K","8","7"]]', (15, 3)),
        ('[["10","K","8","7"]]', (15, 3)),
        ('[["K","Q","8","7"]]', (14, 3)),
        ('[["J","9"],["J"],["J"]]', (17, 1)),
        ('[["J","A","10"],["J"]]', (17, 1)),
    ],
)
def test_bid_and_trump_from_card_ids_examples(
    case_key: Any, expected: Tuple[int, int]
) -> None:
    groups = _groups_from_case(case_key)
    card_ids = _card_ids_from_groups(groups)
    assert len(card_ids) == 4

    canonical = build_canonical_key_and_mapping(card_ids)
    got = predict_bid_and_trump_index(canonical.canonical_groups)
    assert got == expected

    plan = plan_bid_and_trump_from_first4(card_ids)
    assert plan.bid == expected[0]

    flat_ranks = [r for g in canonical.canonical_groups for r in g]
    expected_trump_rank = flat_ranks[expected[1]]
    got_trump_rank = _rank_code_from_card_id(plan.trump_card_id)
    assert got_trump_rank == expected_trump_rank


def test_canonical_tie_order_prefers_stronger_group() -> None:
    card_ids = [
        "Spades_Jack",
        "Spades_Nine",
        "Clubs_Jack",
        "Clubs_Eight",
    ]
    canonical = build_canonical_key_and_mapping(card_ids)
    assert canonical.canonical_groups == [["J", "9"], ["J", "8"]]

    bid, trump_index = predict_bid_and_trump_index(canonical.canonical_groups)
    assert (bid, trump_index) == (16, 1)
