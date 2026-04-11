from __future__ import annotations

import json
from typing import Any, List, Tuple, Union

CanonicalKey = Union[str, List[List[str]]]

POINT_CARDS = {"J", "9", "A", "10"}
RANK_POINTS = {
    "J": 3,
    "9": 2,
    "A": 1,
    "10": 1,
    "K": 0,
    "Q": 0,
    "8": 0,
    "7": 0,
}


def _parse_canonical_key(canonical_key: Any) -> List[List[str]]:
    """
    Accepts either:
      - JSON string: '[[\"J\",\"A\"],[\"7\",\"8\"]]'
      - already-parsed list-of-lists: [["J","A"],["7","8"]]
    """
    if isinstance(canonical_key, str):
        groups = json.loads(canonical_key)
    else:
        groups = canonical_key

    if not isinstance(groups, list) or not groups:
        raise ValueError(
            f"canonical_key must be a non-empty list-of-lists: {groups!r}"
        )

    for g in groups:
        if not isinstance(g, list) or not g:
            raise ValueError(f"Each canonical group must be a non-empty list: {g!r}")
        for r in g:
            if not isinstance(r, str):
                raise ValueError(f"Rank must be a string: {r!r}")

    return groups


def _base_bid_from_first_group(first: List[str]) -> int:
    """
    Base bid rules based on only the first group.
    """
    l1 = len(first)
    s = set(first)

    if l1 == 1:
        return 14

    if l1 == 2:
        if "J" in s and any(r in s for r in ("9", "A", "10")):
            return 15
        return 14

    if l1 == 3:
        if "J" in s and "9" in s:
            return 16

        if (
            ("J" in s)
            and ("A" in s or "10" in s)
            and (("A" in s and "10" in s) or ("K" in s or "Q" in s))
        ):
            return 16

        if "J" in s and (("A" in s) or ("10" in s)):
            return 15

        if "J" in s and ("K" in s) and ("Q" in s):
            return 15

        if "J" in s:
            return 14

        if ("9" in s) and ("A" in s) and ("K" in s):
            return 15

        return 14

    # l1 >= 4
    if "J" in s and any((r in POINT_CARDS) for r in first if r != "J"):
        return 16
    if "J" in s:
        return 15
    if any(r in POINT_CARDS for r in first):
        return 15
    return 14


def _predict_bid(groups: List[List[str]]) -> int:
    """
    Full bid prediction = base rule + extra-jacks adjustment.

    Extra-jacks adjustment:
      If len(first_group) >= 2 and points(first_group) >= 2,
      then each Jack outside first group increments bid by 1.
      Bid is allowed to exceed 16.
    """
    first = groups[0]
    bid = _base_bid_from_first_group(first)

    first_group_points = sum(RANK_POINTS.get(rank, 0) for rank in first)
    if len(first) >= 2:
        extra_jacks = sum(1 for g in groups[1:] for r in g if r == "J")
        bid += extra_jacks

    return bid


def _predict_trump_rank(groups: List[List[str]]) -> str:
    """
    Trump selection rules (rank-only), always choosing a rank from first group.
    """
    first = groups[0]

    if len(first) == 1:
        return first[0]

    if len(first) == 2:
        # If first is Jack, pick second; else pick first.
        return first[1] if first[0] == "J" else first[0]

    if len(first) == 3:
        # If J and 9 present, pick last; else pick second.
        if "J" in first and "9" in first:
            return first[-1]
        return first[1]

    # len(first) >= 4
    return first[-1]


def predict_bid_and_trump_index(canonical_key: CanonicalKey) -> Tuple[int, int]:
    """
    Args:
      canonical_key:
        Either a JSON string like '[[\"J\",\"A\",\"K\"],[\"7\"]]'
        or a list-of-lists like [["J","A","K"],["7"]].

    Returns:
      (bid, trump_index) where:
        - bid is the rules-based predicted bid (can exceed 16)
        - trump_index is the 0-based index of the selected trump rank in the
          1-D flattened canonical order (group0 then group1 then ...).
    """
    groups = _parse_canonical_key(canonical_key)

    bid = _predict_bid(groups)
    trump_rank = _predict_trump_rank(groups)

    flat = [r for g in groups for r in g]
    try:
        trump_index = flat.index(trump_rank)
    except ValueError as exc:
        raise ValueError(
            f"Predicted trump rank {trump_rank!r} not found in flattened canonical key"
        ) from exc

    return bid, trump_index
