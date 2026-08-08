from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from importlib import metadata
from itertools import combinations
import json
import os
from pathlib import Path
import random
import time
from typing import Any, Awaitable, Callable

from app.bots.bidding_bot import plan_bid_and_trump_from_first4
from app.bots.rollout_bot import choose_action_with_rollouts_parallel
from app.engine.canonical_key import build_canonical_key_and_mapping
from app.engine.cards_adapter import from_card_id, to_card_id
from app.engine.k_policy import compute_k
from app.engine.play_engine import (
    apply_play_card,
    apply_reveal_choice,
    compute_play_legal_actions,
    init_play_state,
    resolve_if_catch_complete,
)
from app.engine.state import GameState
from app.legacy import minimax as legacy_minimax
from app.legacy.cards import Cards
from app.settings import settings


BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT_PATH = (
    BACKEND_DIR / "experiments" / "bid_data_v1" / "experiment.json"
)


class ExperimentContractError(RuntimeError):
    pass


class SampleGenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CanonicalCatalogEntry:
    index: int
    canonical_key_id: str
    canonical_key_text: str
    canonical_key: tuple[tuple[str, ...], ...]
    physical_hands: tuple[tuple[str, ...], ...]

    def canonical_key_lists(self) -> list[list[str]]:
        return [list(group) for group in self.canonical_key]


@dataclass(frozen=True)
class SampleRequest:
    canonical_key_id: str
    sample_index: int
    root_seed: str
    policy_name: str = "baseline"
    run_id: str = "local-phase-2"


@dataclass(frozen=True)
class PreparedSample:
    request: SampleRequest
    entry: CanonicalCatalogEntry
    deal_id: str
    deal_seed: int
    bid_position: int
    target_seat: int
    starting_bidder_seat: int
    physical_first4_card_ids: tuple[str, ...]
    first4_card_ids_by_seat: tuple[tuple[str, ...], ...]
    full_hand_card_ids_by_seat: tuple[tuple[str, ...], ...] | None
    visible_hand_card_ids_by_seat: tuple[tuple[str, ...], ...] | None
    selected_trump_card_id: str | None
    full_deal_attempt_count: int
    abort_reason_counts: dict[str, int]
    status: str


Chooser = Callable[..., Awaitable[tuple[str, dict[str, Any]]]]


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _sha256_parts(*parts: object) -> str:
    digest = hashlib.sha256()
    for part in parts:
        encoded = str(part).encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _seed_from_parts(*parts: object) -> int:
    return int(_sha256_parts(*parts), 16)


@lru_cache(maxsize=4)
def load_contract(path: str | Path = DEFAULT_CONTRACT_PATH) -> dict[str, Any]:
    contract_path = Path(path)
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExperimentContractError(
            f"Unable to load experiment contract: {contract_path}"
        ) from exc

    required = {
        "schema_version",
        "experiment_id",
        "population",
        "sampling",
        "game",
        "search",
        "result_schema",
    }
    missing = sorted(required - set(contract))
    if missing:
        raise ExperimentContractError(f"Contract is missing fields: {missing}")
    return contract


def _canonical_key_text(groups: list[list[str]]) -> str:
    return json.dumps(groups, ensure_ascii=True, separators=(",", ":"))


@lru_cache(maxsize=1)
def canonical_catalog() -> tuple[CanonicalCatalogEntry, ...]:
    """Enumerate the exact physical-hand population represented by each key."""
    deck = sorted(to_card_id(card) for card in Cards.packOf28())
    by_key: dict[str, list[tuple[str, ...]]] = defaultdict(list)
    key_groups: dict[str, tuple[tuple[str, ...], ...]] = {}

    for physical_hand in combinations(deck, 4):
        result = build_canonical_key_and_mapping(list(physical_hand))
        key_text = _canonical_key_text(result.canonical_groups)
        by_key[key_text].append(tuple(physical_hand))
        key_groups[key_text] = tuple(tuple(group) for group in result.canonical_groups)

    entries: list[CanonicalCatalogEntry] = []
    for index, key_text in enumerate(sorted(by_key)):
        entries.append(
            CanonicalCatalogEntry(
                index=index,
                canonical_key_id=hashlib.sha256(key_text.encode("utf-8")).hexdigest(),
                canonical_key_text=key_text,
                canonical_key=key_groups[key_text],
                physical_hands=tuple(sorted(by_key[key_text])),
            )
        )

    contract = load_contract()
    expected_keys = int(contract["population"]["canonical_key_count"])
    expected_hands = int(contract["population"]["first_four_physical_hand_count"])
    if len(entries) != expected_keys:
        raise ExperimentContractError(
            f"Canonical catalog has {len(entries)} keys; expected {expected_keys}."
        )
    if sum(len(entry.physical_hands) for entry in entries) != expected_hands:
        raise ExperimentContractError("Physical-hand population count does not match contract.")
    return tuple(entries)


@lru_cache(maxsize=1)
def _catalog_by_id() -> dict[str, CanonicalCatalogEntry]:
    return {entry.canonical_key_id: entry for entry in canonical_catalog()}


def catalog_entry_by_index(index: int) -> CanonicalCatalogEntry:
    catalog = canonical_catalog()
    if index < 0 or index >= len(catalog):
        raise ValueError(f"key index must be in 0..{len(catalog) - 1}")
    return catalog[index]


def catalog_entry_by_id(canonical_key_id: str) -> CanonicalCatalogEntry:
    entry = _catalog_by_id().get(canonical_key_id)
    if entry is None:
        raise ValueError(f"Unknown canonical key id: {canonical_key_id}")
    return entry


def build_sample_request(
    *,
    sample_index: int,
    root_seed: str,
    policy_name: str = "baseline",
    run_id: str = "local-phase-2",
    canonical_key_id: str | None = None,
    key_index: int | None = None,
) -> SampleRequest:
    contract = load_contract()
    sample_count = int(contract["population"]["samples_per_key"])
    if sample_index < 0 or sample_index >= sample_count:
        raise ValueError(f"sample_index must be in 0..{sample_count - 1}")
    if (canonical_key_id is None) == (key_index is None):
        raise ValueError("Provide exactly one of canonical_key_id or key_index.")
    if policy_name not in contract["search"]["policies"]:
        raise ValueError(f"Unknown policy: {policy_name}")

    entry = (
        catalog_entry_by_id(canonical_key_id)
        if canonical_key_id is not None
        else catalog_entry_by_index(int(key_index))
    )
    return SampleRequest(
        canonical_key_id=entry.canonical_key_id,
        sample_index=sample_index,
        root_seed=str(root_seed),
        policy_name=policy_name,
        run_id=run_id,
    )


def _is_zero_point_hand(card_ids: tuple[str, ...]) -> bool:
    return sum(from_card_id(card_id).points for card_id in card_ids) == 0


def _full_deal_abort_reason(
    full_hands: tuple[tuple[str, ...], ...],
    *,
    bidder_seat: int,
    trump_suit: str,
) -> str | None:
    if any(sum(card_id.endswith("_Jack") for card_id in hand) == 4 for hand in full_hands):
        return "ALL_FOUR_JACKS"

    bidder_team = bidder_seat % 2
    bidder_team_trumps = 0
    defender_team_trumps = 0
    for seat, hand in enumerate(full_hands):
        count = sum(card_id.startswith(f"{trump_suit}_") for card_id in hand)
        if seat % 2 == bidder_team:
            bidder_team_trumps += count
        else:
            defender_team_trumps += count
    if bidder_team_trumps == 8 and defender_team_trumps == 0:
        return "ALL_TRUMPS_ONE_SIDE"
    return None


def _deal_from_remaining(
    physical_first4: tuple[str, ...],
    remaining: list[str],
    *,
    target_seat: int,
) -> tuple[tuple[tuple[str, ...], ...], tuple[tuple[str, ...], ...]]:
    first4: list[list[str]] = [[] for _ in range(4)]
    first4[target_seat] = list(physical_first4)
    cursor = 0
    for seat in range(4):
        if seat == target_seat:
            continue
        first4[seat] = remaining[cursor : cursor + 4]
        cursor += 4

    full_hands = [cards[:] for cards in first4]
    for seat in range(4):
        full_hands[seat].extend(remaining[cursor : cursor + 4])
        cursor += 4
    if cursor != 28:
        raise AssertionError(f"Conditional deal consumed {cursor} cards, expected 28.")
    return (
        tuple(tuple(cards) for cards in first4),
        tuple(tuple(cards) for cards in full_hands),
    )


def prepare_sample(request: SampleRequest) -> PreparedSample:
    contract = load_contract()
    entry = catalog_entry_by_id(request.canonical_key_id)
    target_seat = int(contract["sampling"]["target_seat"])
    bid_position = 1 + (request.sample_index % 4)
    starting_bidder_seat = (target_seat - (bid_position - 1)) % 4
    deal_id = _sha256_parts(
        contract["experiment_id"],
        request.root_seed,
        entry.canonical_key_id,
        request.sample_index,
    )
    deal_seed = int(deal_id, 16)
    hand_rng = random.Random(_seed_from_parts(deal_seed, "physical-first4"))
    physical_first4 = hand_rng.choice(entry.physical_hands)

    empty_first4: list[tuple[str, ...]] = [tuple() for _ in range(4)]
    empty_first4[target_seat] = physical_first4
    if bid_position == 1 and _is_zero_point_hand(physical_first4):
        return PreparedSample(
            request=request,
            entry=entry,
            deal_id=deal_id,
            deal_seed=deal_seed,
            bid_position=bid_position,
            target_seat=target_seat,
            starting_bidder_seat=starting_bidder_seat,
            physical_first4_card_ids=physical_first4,
            first4_card_ids_by_seat=tuple(empty_first4),
            full_hand_card_ids_by_seat=None,
            visible_hand_card_ids_by_seat=None,
            selected_trump_card_id=None,
            full_deal_attempt_count=0,
            abort_reason_counts={},
            status="REDEAL",
        )

    if sum(card_id.endswith("_Jack") for card_id in physical_first4) == 4:
        return PreparedSample(
            request=request,
            entry=entry,
            deal_id=deal_id,
            deal_seed=deal_seed,
            bid_position=bid_position,
            target_seat=target_seat,
            starting_bidder_seat=starting_bidder_seat,
            physical_first4_card_ids=physical_first4,
            first4_card_ids_by_seat=tuple(empty_first4),
            full_hand_card_ids_by_seat=None,
            visible_hand_card_ids_by_seat=None,
            selected_trump_card_id=None,
            full_deal_attempt_count=1,
            abort_reason_counts={"ALL_FOUR_JACKS": 1},
            status="ABORT",
        )

    trump_plan = plan_bid_and_trump_from_first4(list(physical_first4))
    selected_trump_id = trump_plan.trump_card_id
    selected_trump_suit = selected_trump_id.split("_", 1)[0]
    full_deck = sorted(to_card_id(card) for card in Cards.packOf28())
    remaining_base = [card_id for card_id in full_deck if card_id not in physical_first4]
    max_attempts = int(contract["redeal_and_abort"]["full_deal_abort"]["max_attempts_per_sample"])
    abort_counts: Counter[str] = Counter()

    for attempt_index in range(max_attempts):
        remaining = remaining_base[:]
        attempt_rng = random.Random(_seed_from_parts(deal_seed, "full-deal", attempt_index))
        attempt_rng.shuffle(remaining)
        first4_by_seat, full_hands = _deal_from_remaining(
            physical_first4,
            remaining,
            target_seat=target_seat,
        )
        abort_reason = _full_deal_abort_reason(
            full_hands,
            bidder_seat=target_seat,
            trump_suit=selected_trump_suit,
        )
        if abort_reason is not None:
            abort_counts[abort_reason] += 1
            continue

        visible_hands = [list(hand) for hand in full_hands]
        visible_hands[target_seat].remove(selected_trump_id)
        return PreparedSample(
            request=request,
            entry=entry,
            deal_id=deal_id,
            deal_seed=deal_seed,
            bid_position=bid_position,
            target_seat=target_seat,
            starting_bidder_seat=starting_bidder_seat,
            physical_first4_card_ids=physical_first4,
            first4_card_ids_by_seat=first4_by_seat,
            full_hand_card_ids_by_seat=full_hands,
            visible_hand_card_ids_by_seat=tuple(tuple(hand) for hand in visible_hands),
            selected_trump_card_id=selected_trump_id,
            full_deal_attempt_count=attempt_index + 1,
            abort_reason_counts=dict(abort_counts),
            status="READY",
        )

    raise SampleGenerationError(
        f"{request.canonical_key_id}/{request.sample_index} exceeded "
        f"{max_attempts} full-deal attempts; aborts={dict(abort_counts)}"
    )


def _policy_values(policy_name: str) -> list[int]:
    contract = load_contract()
    return [
        int(value)
        for value in contract["search"]["policies"][policy_name]["k_by_catch_1_to_8"]
    ]


def validate_runtime_for_sample(request: SampleRequest) -> dict[str, object]:
    contract = load_contract()
    expected_rollouts = int(contract["search"]["rollouts_per_decision"])
    if int(settings.rollouts) != expected_rollouts:
        raise ExperimentContractError(
            f"APP_ROLLOUTS={settings.rollouts}; experiment requires {expected_rollouts}."
        )
    expected_k = _policy_values(request.policy_name)
    active_k = [compute_k(catch) for catch in range(1, 9)]
    if active_k != expected_k:
        raise ExperimentContractError(
            f"Active K policy {active_k} does not match {request.policy_name} {expected_k}."
        )
    if settings.rollout_backend != "local":
        raise ExperimentContractError("Phase 2/Cloud Run runner requires local rollout backend.")

    info = legacy_minimax.strict_rust_smoke_test()
    if info["active"] != "rust" or not info["strictRust"]:
        raise ExperimentContractError(f"Strict Rust backend is not active: {info}")
    return info


def _build_game_state(prepared: PreparedSample) -> GameState:
    if prepared.status != "READY" or prepared.visible_hand_card_ids_by_seat is None:
        raise ValueError("Only READY samples can create a play state.")
    if prepared.selected_trump_card_id is None:
        raise ValueError("READY sample is missing its selected trump.")

    players_cards = [
        [from_card_id(card_id) for card_id in hand]
        for hand in prepared.visible_hand_card_ids_by_seat
    ]
    bidding_order = [
        (prepared.starting_bidder_seat + offset) % 4 for offset in range(4)
    ]
    state = GameState(
        game_id=prepared.deal_id,
        phase="PLAY",
        starting_bidder_index=prepared.starting_bidder_seat,
        bidding_order=bidding_order,
        players_cards=players_cards,
        draw_pile=[],
        auto_deal=True,
        fixed_deck_mode=False,
        seat_types=["bot", "bot", "bot", "bot"],
        player_names=["Bot 1", "Bot 2", "Bot 3", "Bot 4"],
        event_log=["Headless bid-data sample initialized."],
    )
    state.round1_bidder_seat = prepared.target_seat
    state.round1_bid_value = 0
    state.final_bidder_seat = prepared.target_seat
    state.final_bid_value = 0
    state.player_trump = from_card_id(prepared.selected_trump_card_id)
    state.bids_r1_by_seat[prepared.target_seat] = 0
    init_play_state(state)
    return state


def _package_version() -> str:
    for package_name in ("rl428-minimax-rust", "rl428_minimax_rust"):
        try:
            return metadata.version(package_name)
        except metadata.PackageNotFoundError:
            continue
    return "unknown"


def _peak_memory_bytes() -> int:
    try:
        import resource

        value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return value * 1024
    except (ImportError, OSError, ValueError):
        return 0


def _provenance() -> dict[str, str]:
    rust_version = _package_version()
    return {
        "git_commit": os.getenv("APP_GIT_COMMIT", "unknown"),
        "rules_version": "rules-7c91e06",
        "engine_build_id": os.getenv("APP_ENGINE_BUILD_ID", f"rust-{rust_version}"),
        "container_image_digest": os.getenv("APP_CONTAINER_IMAGE_DIGEST", "local"),
        "rust_extension_version": rust_version,
    }


def _base_result_row(prepared: PreparedSample) -> dict[str, Any]:
    contract = load_contract()
    policy = contract["search"]["policies"][prepared.request.policy_name]
    provenance = _provenance()
    result_id = _sha256_parts(
        prepared.deal_id,
        policy["policy_id"],
        provenance["rules_version"],
        provenance["engine_build_id"],
    )
    return {
        "experiment_id": contract["experiment_id"],
        "schema_version": contract["schema_version"],
        "run_id": prepared.request.run_id,
        "policy_id": policy["policy_id"],
        "canonical_key_id": prepared.entry.canonical_key_id,
        "deal_id": prepared.deal_id,
        "result_id": result_id,
        "sample_index": prepared.request.sample_index,
        "canonical_key": prepared.entry.canonical_key_lists(),
        "canonical_key_text": prepared.entry.canonical_key_text,
        "physical_first4_card_ids": list(prepared.physical_first4_card_ids),
        "root_seed": prepared.request.root_seed,
        "deal_seed": format(prepared.deal_seed, "064x"),
        "target_seat": prepared.target_seat,
        "bid_position": prepared.bid_position,
        "starting_bidder_seat": prepared.starting_bidder_seat,
        "selected_trump_card_id": prepared.selected_trump_card_id,
        "selected_trump_suit": (
            prepared.selected_trump_card_id.split("_", 1)[0]
            if prepared.selected_trump_card_id
            else None
        ),
        "full_deal_attempt_count": prepared.full_deal_attempt_count,
        "abort_reason_counts": prepared.abort_reason_counts,
        "rollouts_per_decision": int(contract["search"]["rollouts_per_decision"]),
        "k_by_catch_1_to_8": _policy_values(prepared.request.policy_name),
        "worker_count": int(settings.workers),
        "cloud_run_task_index": (
            int(os.environ["CLOUD_RUN_TASK_INDEX"])
            if os.getenv("CLOUD_RUN_TASK_INDEX") is not None
            else None
        ),
        "cloud_run_task_attempt": (
            int(os.environ["CLOUD_RUN_TASK_ATTEMPT"])
            if os.getenv("CLOUD_RUN_TASK_ATTEMPT") is not None
            else None
        ),
        **provenance,
    }


async def simulate_prepared_sample(
    prepared: PreparedSample,
    *,
    pool: ProcessPoolExecutor | None,
    chooser: Chooser = choose_action_with_rollouts_parallel,
    enforce_runtime: bool = True,
) -> dict[str, Any]:
    if prepared.status in {"REDEAL", "ABORT"}:
        backend_info = (
            validate_runtime_for_sample(prepared.request)
            if enforce_runtime
            else legacy_minimax.minimax_backend_info()
        )
        row = _base_result_row(prepared)
        row.update(
            {
                "status": prepared.status,
                "bidder_team_points": None,
                "team1_points": None,
                "team2_points": None,
                "simulation_seconds": 0.0,
                "decision_count": 0,
                "decision_seconds_by_catch": [],
                "peak_memory_bytes": _peak_memory_bytes(),
                "minimax_backend": str(backend_info["active"]),
                "minimax_invoked": False,
                "debug_trace_selected": False,
            }
        )
        return row

    if pool is None:
        raise ValueError("A process pool is required for a playable sample.")
    backend_info = (
        validate_runtime_for_sample(prepared.request)
        if enforce_runtime
        else legacy_minimax.minimax_backend_info()
    )
    state = _build_game_state(prepared)
    decision_timings: dict[int, list[float]] = defaultdict(list)
    trace: list[dict[str, Any]] = []
    decision_index = 0
    started = time.perf_counter()

    while state.phase == "PLAY":
        if decision_index >= 64:
            raise RuntimeError("Headless game exceeded the 64-decision safety limit.")
        actor = (state.leaderIndex + len(state.s)) % 4
        catch_number = int(state.catchNumber)
        legal = compute_play_legal_actions(state)
        decision_started = time.perf_counter()

        if (
            legal.type == "NO_ACTION"
            and state.player_trump is not None
            and actor == state.finalBid - 1
            and not state.trumpReveal
            and len(state.play_players[actor]["cards"]) == 0
        ):
            action_type = "REVEAL"
            payload: dict[str, Any] = {"seatIndex": actor, "reveal": True}
        else:
            if legal.type == "NO_ACTION":
                raise RuntimeError(f"P{actor + 1} has no legal headless action.")
            rollout_seed_base = _seed_from_parts(
                prepared.deal_id,
                "decision",
                decision_index,
            )
            action_type, payload = await chooser(
                state,
                actor,
                pool,
                rollout_seed_base=rollout_seed_base,
                strict=True,
            )

        if action_type == "REVEAL":
            apply_reveal_choice(state, int(payload["seatIndex"]), bool(payload["reveal"]))
            action_value: Any = bool(payload["reveal"])
        elif action_type == "PLAY":
            apply_play_card(state, int(payload["seatIndex"]), str(payload["cardId"]))
            action_value = str(payload["cardId"])
        else:
            raise RuntimeError(f"Unknown chooser action type: {action_type}")

        elapsed = time.perf_counter() - decision_started
        decision_timings[catch_number].append(elapsed)
        trace.append(
            {
                "decision_index": decision_index,
                "catch_number": catch_number,
                "actor_seat": actor,
                "action_type": action_type,
                "action": action_value,
                "seconds": elapsed,
            }
        )
        decision_index += 1
        resolve_if_catch_complete(state)

    simulation_seconds = time.perf_counter() - started
    bidder_team = 1 if prepared.target_seat % 2 == 0 else 2
    bidder_points = state.team1Points if bidder_team == 1 else state.team2Points
    debug_selected = int(prepared.deal_id[:12], 16) < int((16**12) * 0.001)
    timing_summary = [
        {
            "catch_number": catch,
            "count": len(values),
            "total_seconds": sum(values),
            "max_seconds": max(values),
        }
        for catch, values in sorted(decision_timings.items())
    ]
    row = _base_result_row(prepared)
    row.update(
        {
            "status": "COMPLETED",
            "bidder_team_points": int(bidder_points),
            "team1_points": int(state.team1Points),
            "team2_points": int(state.team2Points),
            "simulation_seconds": simulation_seconds,
            "decision_count": decision_index,
            "decision_seconds_by_catch": timing_summary,
            "peak_memory_bytes": _peak_memory_bytes(),
            "minimax_backend": str(backend_info["active"]),
            "minimax_invoked": True,
            "debug_trace_selected": debug_selected,
        }
    )
    if debug_selected:
        row["debug_trace"] = trace
    return row


async def simulate_requests(
    requests: list[SampleRequest],
    *,
    chooser: Chooser = choose_action_with_rollouts_parallel,
    enforce_runtime: bool = True,
) -> list[dict[str, Any]]:
    if not requests:
        return []
    if enforce_runtime:
        validated_policies: set[str] = set()
        for request in requests:
            if request.policy_name not in validated_policies:
                validate_runtime_for_sample(request)
                validated_policies.add(request.policy_name)
    workers = max(1, int(settings.workers))
    rows: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for request in requests:
            prepared = prepare_sample(request)
            rows.append(
                await simulate_prepared_sample(
                    prepared,
                    pool=pool,
                    chooser=chooser,
                    enforce_runtime=enforce_runtime,
                )
            )
    return rows


def simulate_requests_sync(
    requests: list[SampleRequest],
    *,
    chooser: Chooser = choose_action_with_rollouts_parallel,
    enforce_runtime: bool = True,
) -> list[dict[str, Any]]:
    return asyncio.run(
        simulate_requests(
            requests,
            chooser=chooser,
            enforce_runtime=enforce_runtime,
        )
    )
