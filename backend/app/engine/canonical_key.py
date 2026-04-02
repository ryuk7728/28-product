from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

RANK_STRENGTH_ORDER = ["J", "9", "A", "10", "K", "Q", "8", "7"]
RANK_STRENGTH = {r: i for i, r in enumerate(RANK_STRENGTH_ORDER)}

RANK_NAME_TO_CODE = {
    "Jack": "J",
    "Nine": "9",
    "Ace": "A",
    "Ten": "10",
    "King": "K",
    "Queen": "Q",
    "Eight": "8",
    "Seven": "7",
}


def _rank_code_from_card_id(card_id: str) -> str:
    # cardId is "Hearts_Jack" => rank_name is "Jack"
    try:
        _suit, rank_name = card_id.split("_", 1)
    except ValueError as e:
        raise ValueError(f"Invalid cardId: {card_id}") from e

    code = RANK_NAME_TO_CODE.get(rank_name)
    if code is None:
        raise ValueError(f"Unknown rank name in cardId: {card_id}")
    return code


def _strength_key(rank_codes: List[str]) -> Tuple[int, ...]:
    # smaller index means stronger; plain ascending lexicographic comparison
    # keeps stronger groups ahead in tie-breaks.
    return tuple(RANK_STRENGTH[r] for r in rank_codes)


@dataclass(frozen=True)
class CanonicalResult:
    canonical_groups: List[List[str]]          # e.g. [["J","A","K"],["7"]]
    canonical_cardid_groups: List[List[str]]  # aligned cardIds in same order
    flat_card_ids: List[str]                  # flattened canonical_cardid_groups


def build_canonical_key_and_mapping(first4_card_ids: List[str]) -> CanonicalResult:
    """
    Implements your canonical rules and returns both:
      - canonical rank groups (suit-agnostic)
      - aligned original cardIds in canonical order, so trump_index can map to cardId
    """
    if len(first4_card_ids) != 4:
        raise ValueError("Expected exactly 4 cardIds for canonicalization.")

    # 1) Group by suit
    by_suit: dict[str, List[str]] = {}
    for cid in first4_card_ids:
        suit = cid.split("_", 1)[0]
        by_suit.setdefault(suit, []).append(cid)

    # 2) Within each suit, sort by 28 rank strength (strongest to weakest)
    suit_groups: List[Tuple[List[str], List[str]]] = []
    for _suit, cids in by_suit.items():
        # build (rank_code, cardId)
        pairs = [(_rank_code_from_card_id(cid), cid) for cid in cids]
        pairs.sort(key=lambda x: RANK_STRENGTH[x[0]])
        ranks = [r for r, _ in pairs]
        ids = [cid for _, cid in pairs]
        suit_groups.append((ranks, ids))

    # 3) Sort suit-groups by length desc, then lexicographic by rank strength desc
    suit_groups.sort(
        key=lambda g: (-len(g[0]), _strength_key(g[0]))
    )

    # 4) Drop suit labels and output rank lists; keep cardId lists aligned
    canonical_groups = [ranks for ranks, _ids in suit_groups]
    canonical_cardid_groups = [ids for _ranks, ids in suit_groups]
    flat_card_ids = [cid for grp in canonical_cardid_groups for cid in grp]

    return CanonicalResult(
        canonical_groups=canonical_groups,
        canonical_cardid_groups=canonical_cardid_groups,
        flat_card_ids=flat_card_ids,
    )
