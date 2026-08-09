from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping, Sequence


MIN_CONTRACT = 14
MAX_CONTRACT = 28
EXPECTED_CANONICAL_KEYS = 2262
_DATA_PATH = Path(__file__).with_name("data") / "bid_stats_v2.json"

CanonicalKey = tuple[tuple[str, ...], ...]
BidPolicyMode = Literal["aggressive", "optimal", "custom"]


class BidPolicyDataError(RuntimeError):
    """Raised when the bundled empirical bidding data is missing or invalid."""


@dataclass(frozen=True)
class BidThresholds:
    opening_15: int
    opening_16: int
    later_bid: int
    jump_to_16: int

    def __post_init__(self) -> None:
        for name, value in (
            ("opening_15", self.opening_15),
            ("opening_16", self.opening_16),
            ("later_bid", self.later_bid),
            ("jump_to_16", self.jump_to_16),
        ):
            if type(value) is not int or not 0 <= value <= 100:
                raise ValueError(f"{name} must be an integer from 0 to 100.")

    def to_public_dict(self) -> dict[str, int]:
        return {
            "opening15": self.opening_15,
            "opening16": self.opening_16,
            "laterBid": self.later_bid,
            "jumpTo16": self.jump_to_16,
        }


AGGRESSIVE_THRESHOLDS = BidThresholds(61, 66, 61, 71)
OPTIMAL_THRESHOLDS = BidThresholds(67, 70, 67, 75)


@dataclass(frozen=True)
class BidPolicyConfig:
    mode: BidPolicyMode = "aggressive"
    position_aware: bool = False
    thresholds: BidThresholds = AGGRESSIVE_THRESHOLDS

    def __post_init__(self) -> None:
        if self.mode not in ("aggressive", "optimal", "custom"):
            raise ValueError("mode must be aggressive, optimal, or custom.")
        expected = {
            "aggressive": AGGRESSIVE_THRESHOLDS,
            "optimal": OPTIMAL_THRESHOLDS,
        }.get(self.mode)
        if expected is not None and self.thresholds != expected:
            raise ValueError(f"{self.mode} mode must use its preset thresholds.")

    @classmethod
    def aggressive(cls, *, position_aware: bool = False) -> BidPolicyConfig:
        return cls("aggressive", position_aware, AGGRESSIVE_THRESHOLDS)

    @classmethod
    def optimal(cls, *, position_aware: bool = False) -> BidPolicyConfig:
        return cls("optimal", position_aware, OPTIMAL_THRESHOLDS)

    @classmethod
    def custom(
        cls, thresholds: BidThresholds, *, position_aware: bool = False
    ) -> BidPolicyConfig:
        return cls("custom", position_aware, thresholds)

    def to_public_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "positionAware": self.position_aware,
            "thresholds": self.thresholds.to_public_dict(),
        }


@dataclass(frozen=True)
class BidStats:
    completed: int
    # Index 0 is P14, index 14 is P28. Values are cumulative success counts.
    successes: tuple[int, ...]

    def success_count(self, contract: int) -> int:
        if contract < MIN_CONTRACT or contract > MAX_CONTRACT:
            raise ValueError(f"Contract must be in {MIN_CONTRACT}..{MAX_CONTRACT}.")
        return self.successes[contract - MIN_CONTRACT]

    def meets_percent(self, contract: int, percent: int) -> bool:
        if self.completed <= 0:
            return False
        return self.success_count(contract) * 100 >= self.completed * percent


# Compatibility name for callers/tests written for the original pooled-only policy.
PooledBidStats = BidStats


@dataclass(frozen=True)
class KeyBidStats:
    pooled: BidStats
    positions: tuple[BidStats, BidStats, BidStats, BidStats]


@dataclass(frozen=True)
class BidPolicyDataset:
    metadata: Mapping[str, object]
    by_key: Mapping[CanonicalKey, KeyBidStats]


def _canonical_tuple(groups: Sequence[Sequence[str]]) -> CanonicalKey:
    return tuple(tuple(rank for rank in group) for group in groups)


def _parse_canonical_key(key_text: str) -> CanonicalKey:
    try:
        groups = json.loads(key_text)
    except json.JSONDecodeError as exc:
        raise BidPolicyDataError(f"Invalid canonical key JSON: {key_text!r}") from exc
    if not isinstance(groups, list) or not groups:
        raise BidPolicyDataError(f"Invalid canonical key: {key_text!r}")
    if any(not isinstance(group, list) or not group for group in groups):
        raise BidPolicyDataError(f"Invalid canonical groups: {key_text!r}")
    if any(not isinstance(rank, str) for group in groups for rank in group):
        raise BidPolicyDataError(f"Invalid canonical ranks: {key_text!r}")
    if sum(len(group) for group in groups) != 4:
        raise BidPolicyDataError(f"Canonical key does not contain four cards: {key_text!r}")
    return _canonical_tuple(groups)


def _parse_counts(values: object, *, context: str, max_completed: int) -> BidStats:
    expected_width = 1 + (MAX_CONTRACT - MIN_CONTRACT + 1)
    if (
        not isinstance(values, list)
        or len(values) != expected_width
        or any(type(value) is not int or value < 0 for value in values)
    ):
        raise BidPolicyDataError(f"Invalid empirical counts for {context}.")
    completed = values[0]
    successes = tuple(values[1:])
    if completed > max_completed:
        raise BidPolicyDataError(f"Too many completed games for {context}: {completed}.")
    if successes[0] > completed:
        raise BidPolicyDataError(f"P14 exceeds completed games for {context}.")
    if any(left < right for left, right in zip(successes, successes[1:])):
        raise BidPolicyDataError(f"Success counts are not cumulative for {context}.")
    return BidStats(completed=completed, successes=successes)


def _read_dataset(path: Path) -> BidPolicyDataset:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BidPolicyDataError(f"Bundled bidding data is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise BidPolicyDataError(f"Bundled bidding data is invalid JSON: {path}") from exc
    if payload.get("version") != 2:
        raise BidPolicyDataError("Unsupported empirical bidding-data version.")
    metadata = payload.get("meta")
    raw_keys = payload.get("keys")
    if not isinstance(metadata, dict) or metadata.get("isComplete") is not True:
        raise BidPolicyDataError("Empirical bidding dataset is not marked complete.")
    if not isinstance(raw_keys, dict) or len(raw_keys) != EXPECTED_CANONICAL_KEYS:
        count = len(raw_keys) if isinstance(raw_keys, dict) else 0
        raise BidPolicyDataError(f"Expected {EXPECTED_CANONICAL_KEYS} empirical keys, found {count}.")
    if metadata.get("canonicalKeyCount") != EXPECTED_CANONICAL_KEYS:
        raise BidPolicyDataError("Empirical bidding metadata has the wrong key count.")
    if metadata.get("expectedSamplesPerKey") != 100:
        raise BidPolicyDataError("Empirical bidding data does not contain 100 samples per key.")
    if metadata.get("samplesPerPosition") != 25 or metadata.get("positions") != [1, 2, 3, 4]:
        raise BidPolicyDataError("Empirical bidding data lacks four 25-game position buckets.")
    if not isinstance(metadata.get("sourceRunId"), str):
        raise BidPolicyDataError("Empirical bidding data has no source run ID.")
    source_hash = metadata.get("sourceSha256")
    if not isinstance(source_hash, str) or len(source_hash) != 64:
        raise BidPolicyDataError("Empirical bidding data has no valid source hash.")

    parsed: dict[CanonicalKey, KeyBidStats] = {}
    for key_text, buckets in raw_keys.items():
        if not isinstance(key_text, str) or not isinstance(buckets, list) or len(buckets) != 5:
            raise BidPolicyDataError(f"Invalid empirical buckets for {key_text!r}.")
        pooled = _parse_counts(buckets[0], context=f"{key_text!r} pooled", max_completed=100)
        positions = tuple(
            _parse_counts(bucket, context=f"{key_text!r} position {position}", max_completed=25)
            for position, bucket in enumerate(buckets[1:], start=1)
        )
        if sum(position.completed for position in positions) != pooled.completed:
            raise BidPolicyDataError(f"Position completions do not sum to pooled completions for {key_text!r}.")
        if any(
            sum(position.success_count(contract) for position in positions)
            != pooled.success_count(contract)
            for contract in range(MIN_CONTRACT, MAX_CONTRACT + 1)
        ):
            raise BidPolicyDataError(f"Position counts do not sum to pooled counts for {key_text!r}.")
        canonical_key = _parse_canonical_key(key_text)
        if canonical_key in parsed:
            raise BidPolicyDataError(f"Duplicate canonical key: {key_text!r}.")
        parsed[canonical_key] = KeyBidStats(pooled=pooled, positions=positions)  # type: ignore[arg-type]
    return BidPolicyDataset(
        metadata=MappingProxyType(dict(metadata)),
        by_key=MappingProxyType(parsed),
    )


@lru_cache(maxsize=1)
def load_bid_policy_dataset() -> BidPolicyDataset:
    return _read_dataset(_DATA_PATH)


def stats_for_canonical(
    canonical_groups: Sequence[Sequence[str]], *, bid_position: int | None = None
) -> BidStats:
    key = _canonical_tuple(canonical_groups)
    key_stats = load_bid_policy_dataset().by_key.get(key)
    if key_stats is None:
        raise BidPolicyDataError(f"Canonical hand is missing from bidding data: {key!r}")
    if bid_position is None:
        return key_stats.pooled
    if not 1 <= bid_position <= 4:
        raise ValueError("bid_position must be in 1..4.")
    return key_stats.positions[bid_position - 1]


def pooled_stats_for_canonical(canonical_groups: Sequence[Sequence[str]]) -> BidStats:
    return stats_for_canonical(canonical_groups)


def choose_r1_bid_from_stats(
    stats: BidStats,
    *,
    min_bid_exclusive: int,
    max_bid_inclusive: int,
    is_opening_bidder: bool,
    thresholds: BidThresholds = AGGRESSIVE_THRESHOLDS,
) -> int:
    """Apply one threshold policy and return 0 for pass."""
    if is_opening_bidder:
        opening_candidates = (
            (16, thresholds.opening_16),
            (15, thresholds.opening_15),
            (14, thresholds.opening_15),
        )
        for contract, threshold in opening_candidates:
            if (
                min_bid_exclusive < contract <= max_bid_inclusive
                and stats.meets_percent(contract, threshold)
            ):
                return contract
        forced_bid = max(MIN_CONTRACT, min_bid_exclusive + 1)
        if forced_bid > max_bid_inclusive:
            raise ValueError("Opening bidder has no legal contract available.")
        return forced_bid

    next_legal_bid = max(MIN_CONTRACT, min_bid_exclusive + 1)
    if next_legal_bid > max_bid_inclusive:
        return 0
    if (
        next_legal_bid == 15
        and 16 <= max_bid_inclusive
        and stats.meets_percent(16, thresholds.jump_to_16)
    ):
        return 16
    return (
        next_legal_bid
        if stats.meets_percent(next_legal_bid, thresholds.later_bid)
        else 0
    )


def choose_r1_bid_from_data(
    canonical_groups: Sequence[Sequence[str]],
    *,
    min_bid_exclusive: int,
    max_bid_inclusive: int,
    is_opening_bidder: bool,
    policy: BidPolicyConfig = BidPolicyConfig(),
    bid_position: int,
) -> int:
    stats = stats_for_canonical(
        canonical_groups,
        bid_position=bid_position if policy.position_aware else None,
    )
    return choose_r1_bid_from_stats(
        stats,
        min_bid_exclusive=min_bid_exclusive,
        max_bid_inclusive=max_bid_inclusive,
        is_opening_bidder=is_opening_bidder,
        thresholds=policy.thresholds,
    )
