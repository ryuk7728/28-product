from __future__ import annotations

import json
import traceback
from pathlib import Path
import asyncio
import os
import time
import random
import threading
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from typing import Any

from app.engine.cards_adapter import from_card_id, to_card_id
from app.engine.k_policy import compute_k
from app.engine.state import SUIT_MATRIX_INDEX
from app.settings import settings
from app.legacy.cards import Cards
from app.legacy import minimax as legacy_minimax


# -----------------------------
# Worker-side helpers (picklable)
# -----------------------------

_ray_inited = False
_ray_rollout_remote = None

_rollout_metrics_lock = threading.Lock()
_rollout_metrics_count = 0
_rollout_metrics_last_ts: float | None = None


def _record_rollouts(n: int) -> None:
    if not settings.rollout_metrics:
        return

    global _rollout_metrics_count, _rollout_metrics_last_ts

    now = time.monotonic()
    interval = max(1.0, float(settings.rollout_metrics_interval))

    with _rollout_metrics_lock:
        if _rollout_metrics_last_ts is None:
            _rollout_metrics_last_ts = now

        _rollout_metrics_count += n
        elapsed = now - _rollout_metrics_last_ts

        if elapsed >= interval:
            rps = _rollout_metrics_count / elapsed if elapsed > 0 else 0.0
            print(
                f"[rollout-metrics] rollouts/sec={rps:.1f} "
                f"interval={elapsed:.1f}s total={_rollout_metrics_count}"
            )
            _rollout_metrics_last_ts = now
            _rollout_metrics_count = 0


def _ensure_ray():
    """
    Lazily initialize Ray for distributed rollouts.
    """
    global _ray_inited
    if _ray_inited:
        import ray

        return ray

    try:
        import ray
    except Exception as e:
        raise RuntimeError(
            "APP_ROLLOUT_BACKEND=ray but 'ray' is not installed."
        ) from e

    address = settings.ray_address
    if address:
        ray.init(address=address, ignore_reinit_error=True)
    else:
        ray.init(ignore_reinit_error=True)

    _ray_inited = True
    return ray


def _get_ray_rollout_remote():
    global _ray_rollout_remote
    ray = _ensure_ray()
    if _ray_rollout_remote is None:
        _ray_rollout_remote = ray.remote(rollout_worker)
    return ray, _ray_rollout_remote


def _full_deck_card_ids() -> list[str]:
    return [to_card_id(c) for c in Cards.packOf28()]


def _seed_entropy() -> int:
    # Non-deterministic seed with high diversity across workers
    return int.from_bytes(os.urandom(8), "little") ^ os.getpid() ^ time.time_ns()


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "y", "on")


def _dump_dir_backend_root() -> Path:
    # rollout_bot.py is: backend/app/bots/rollout_bot.py
    # parents: bots -> app -> backend
    backend_root = Path(__file__).resolve().parents[2]
    dump_dir = backend_root / "rollout_crash_dumps"
    dump_dir.mkdir(parents=True, exist_ok=True)
    return dump_dir


def _safe_card_id(x):
    try:
        if x is None:
            return None
        return to_card_id(x)
    except Exception:
        return None


def _players_to_cardids(players):
    out = []
    for i in range(4):
        out.append([_safe_card_id(c) for c in players[i]["cards"]])
    return out


def _find_none_positions(players):
    pos = []
    for i in range(4):
        idxs = [j for j, c in enumerate(players[i]["cards"]) if c is None]
        if idxs:
            pos.append({"seat": i, "indices": idxs})
    return pos


def _card_suit_from_id(card_id: str) -> str:
    # cardId is "Hearts_Jack" => suit is "Hearts"
    return card_id.split("_", 1)[0]


def _allowed_trump_indicator_ids(
    pool_ids: list[str],
    *,
    bidder_seat: int,
    trump_matrix: list[list[int]],
) -> list[str]:
    allowed: list[str] = []
    for cid in pool_ids:
        suit = _card_suit_from_id(cid)
        row = SUIT_MATRIX_INDEX.get(suit)
        if row is None:
            allowed.append(cid)
            continue
        try:
            if trump_matrix[row][bidder_seat] == 1:
                allowed.append(cid)
        except Exception:
            allowed.append(cid)
    return allowed


def _deal_unknown_with_suit_constraints(
    *,
    rng: random.Random,
    pool_ids: list[str],
    seats_to_fill: list[int],
    hand_sizes: list[int],
    suit_matrix: list[list[int]],
) -> dict[int, list[str]] | None:
    """
    Greedy constrained deal:
      - repeatedly pick most constrained seat (smallest allowed pool)
      - randomly sample 'need' cards from allowed
      - remove chosen from pool
    Returns seat->cardIds, or None if this attempt can't satisfy constraints.
    """
    remaining_pool = pool_ids[:]
    remaining_seats = seats_to_fill[:]
    dealt: dict[int, list[str]] = {s: [] for s in seats_to_fill}

    def is_allowed(cid: str, seat: int) -> bool:
        suit = _card_suit_from_id(cid)
        row = SUIT_MATRIX_INDEX.get(suit)
        if row is None:
            return True
        try:
            return suit_matrix[row][seat] == 1
        except Exception:
            # If matrix malformed, don't block
            return True

    def void_count(seat: int) -> int:
        cnt = 0
        for row in range(min(4, len(suit_matrix))):
            try:
                if suit_matrix[row][seat] == 0:
                    cnt += 1
            except Exception:
                continue
        return cnt

    while remaining_seats:
        seat_infos: list[tuple[int, int, int, int, list[str]]] = []
        for seat in remaining_seats:
            need = hand_sizes[seat]
            allowed = [cid for cid in remaining_pool if is_allowed(cid, seat)]
            seat_infos.append(
                (
                    len(allowed),  # primary: smallest allowed pool first
                    -void_count(seat),  # tie: more void suits first
                    -need,  # tie: higher need first
                    seat,  # stable tie-breaker
                    allowed,
                )
            )

        seat_infos.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
        allowed_len, _neg_voids, _neg_need, seat, allowed = seat_infos[0]
        need = hand_sizes[seat]

        if allowed_len < need:
            return None

        chosen = rng.sample(allowed, need) if need > 0 else []
        dealt[seat] = chosen

        chosen_set = set(chosen)
        remaining_pool = [cid for cid in remaining_pool if cid not in chosen_set]
        remaining_seats = [s for s in remaining_seats if s != seat]

    return dealt


def rollout_worker(snapshot: dict[str, Any], n: int, seed: int) -> dict[Any, int]:
    """
    Runs n rollouts and returns a Counter-like dict mapping:
      - bool -> count
      - card_identity_string -> count
    This function MUST be top-level for Windows spawn pickling.
    """
    rng = random.Random(seed)

    bot_seat: int = snapshot["botSeat"]
    finalBid: int = snapshot["finalBid"]  # 1-indexed
    bidder_seat: int = snapshot["bidderSeat"]

    leaderIndex: int = snapshot["leaderIndex"]
    catchNumber: int = snapshot["catchNumber"]
    k: int = snapshot["k"]

    trumpReveal: bool = snapshot["trumpReveal"]
    chose: bool = snapshot["chose"]
    currentSuit: str = snapshot["currentSuit"]
    trumpPlayed: bool = snapshot["trumpPlayed"]
    trumpIndice: list[int] = snapshot["trumpIndice"]

    s_card_ids: list[str] = snapshot["sCardIds"]
    s_cards = [from_card_id(cid) for cid in s_card_ids]
    s_set = set(s_card_ids)

    bot_hand = [from_card_id(cid) for cid in snapshot["botHandCardIds"]]
    hand_sizes: list[int] = snapshot["handSizes"]

    played_set = set(snapshot["playedCardIds"])
    deck_ids = _full_deck_card_ids()

    # Suit constraints matrix (rows: H, D, S, C; cols: seat 0..3)
    suit_matrix = snapshot.get("suitMatrix") or [[1, 1, 1, 1] for _ in range(4)]
    trump_matrix = snapshot.get("trumpMatrix") or [[1, 1, 1, 1] for _ in range(4)]
    max_deal_retries = max(0, int(settings.rollout_deal_retries))

    # Base known set for this bot (own hand + played)
    base_known = set(snapshot["botHandCardIds"]) | played_set

    # Concealed trump indicator card id (should remain stable in your new legacy)
    concealed_trump_card_id = snapshot.get("concealedTrumpCardId")

    # Only the bidder knows the concealed trump before reveal.
    # (After reveal, we enforce "indicator must be in bidder's hand" explicitly below.)
    if concealed_trump_card_id and bot_seat == bidder_seat:
        base_known.add(concealed_trump_card_id)

    # If trump is already revealed, suit is known for all
    known_trump_suit = snapshot.get("knownTrumpSuit") if trumpReveal else None

    counts: Counter = Counter()

    for _ in range(n):
        # Build unknown pool
        base_pool_ids = [cid for cid in deck_ids if cid not in base_known]
        pool_ids = base_pool_ids[:]

        # Determine sim_player_trump and sim_trump_suit
        sim_player_trump = None
        sim_trump_suit = None
        trump_sample_constrained = False

        # If trump is revealed, the suit is known.
        # Keep playerTrump non-None for legacy logic.
        if trumpReveal:
            sim_trump_suit = known_trump_suit

            if concealed_trump_card_id is not None:
                found = None
                for c in bot_hand:
                    if to_card_id(c) == concealed_trump_card_id:
                        found = c
                        break
                sim_player_trump = (
                    found
                    if found is not None
                    else from_card_id(concealed_trump_card_id)
                )

        else:
            if bot_seat == bidder_seat:
                if concealed_trump_card_id is None:
                    raise RuntimeError(
                        "Invariant violated: bidder rollouts before reveal require "
                        "concealedTrumpCardId, but it is None."
                    )

                # bidder knows true concealed trump
                found = None
                for c in bot_hand:
                    if to_card_id(c) == concealed_trump_card_id:
                        found = c
                        break
                sim_player_trump = (
                    found
                    if found is not None
                    else from_card_id(concealed_trump_card_id)
                )
                sim_trump_suit = sim_player_trump.suit
            else:
                # non-bidder: trump unknown -> sample from pool, honoring bidder-led
                # pre-reveal trump impossibility when possible.
                allowed_indicator_ids = _allowed_trump_indicator_ids(
                    base_pool_ids,
                    bidder_seat=bidder_seat,
                    trump_matrix=trump_matrix,
                )
                candidate_ids = (
                    allowed_indicator_ids if allowed_indicator_ids else base_pool_ids
                )
                trump_sample_constrained = (
                    bool(allowed_indicator_ids)
                    and len(allowed_indicator_ids) < len(base_pool_ids)
                )
                idx = rng.randrange(len(candidate_ids))
                sampled = candidate_ids[idx]
                pool_ids = [cid for cid in base_pool_ids if cid != sampled]
                sim_player_trump = from_card_id(sampled)
                sim_trump_suit = sim_player_trump.suit

        # Shuffle pool for distribution
        rng.shuffle(pool_ids)

        # Build hands
        hands: list[list] = [[], [], [], []]
        hands[bot_seat] = bot_hand[:]  # keep bot's real hand

        # Per-rollout mutable copy (we may decrement needs)
        need_sizes = list(hand_sizes)

        # ------------------------------------------------------------
        # FIX: If trump is already revealed for this rollout AND this bot
        # is NOT the bidder, then the concealed trump indicator card is
        # public information and must be in the bidder's hand (unless it
        # has already been played).
        # ------------------------------------------------------------
        if (
            trumpReveal
            and bot_seat != bidder_seat
            and concealed_trump_card_id is not None
            and concealed_trump_card_id not in played_set
        ):
            if sim_player_trump is None:
                sim_player_trump = from_card_id(concealed_trump_card_id)

            already_in_bidder_hand = any(
                to_card_id(c) == concealed_trump_card_id for c in hands[bidder_seat]
            )
            if not already_in_bidder_hand:
                hands[bidder_seat].append(sim_player_trump)
                need_sizes[bidder_seat] -= 1
                if need_sizes[bidder_seat] < 0:
                    # Defensive guard: snapshot handSizes should include the
                    # indicator in bidder's hand when trumpReveal=True.
                    need_sizes[bidder_seat] = 0

            # Ensure it cannot be dealt to anyone else
            pool_ids = [cid for cid in pool_ids if cid != concealed_trump_card_id]

        # ------------------------------------------------------------
        # NEW CONSTRAINT (heuristic):
        # If this is the first time the led suit has appeared in the game
        # (excluding the current trick), and everyone has followed led suit
        # so far this trick, and the Jack of the led suit is unknown, then
        # assume seats that already played did NOT have that Jack.
        # Force-assign the Jack to a seat yet to play in this trick AFTER
        # the current actor (the bot).
        #
        # Trigger applies even if len(s_card_ids) == 1.
        # ------------------------------------------------------------
        try:
            if len(s_card_ids) >= 1 and currentSuit:
                led_suit = currentSuit

                # All played-in-trick cards must match led suit
                if all(_card_suit_from_id(cid) == led_suit for cid in s_card_ids):
                    # Suit must not have appeared earlier (exclude current trick)
                    prior_played = [cid for cid in played_set if cid not in s_set]
                    if all(_card_suit_from_id(cid) != led_suit for cid in prior_played):
                        jack_id = f"{led_suit}_Jack"

                        # Jack must be truly unknown (in pool)
                        if jack_id in pool_ids:
                            actor = (leaderIndex + len(s_card_ids)) % 4
                            if actor == bot_seat:
                                # Seats still to play after the actor in this trick
                                remaining_after_actor = [
                                    (leaderIndex + i) % 4
                                    for i in range(len(s_card_ids) + 1, 4)
                                ]

                                row = SUIT_MATRIX_INDEX.get(led_suit)
                                candidates: list[int] = []
                                for seat in remaining_after_actor:
                                    if need_sizes[seat] <= 0:
                                        continue
                                    if row is not None and suit_matrix[row][seat] == 0:
                                        continue
                                    candidates.append(seat)

                                if candidates:
                                    target = rng.choice(candidates)

                                    already = any(
                                        to_card_id(c) == jack_id for c in hands[target]
                                    )
                                    if not already:
                                        hands[target].append(from_card_id(jack_id))
                                        need_sizes[target] -= 1
                                        if need_sizes[target] < 0:
                                            need_sizes[target] = 0

                                    # Remove from pool so it can't be dealt elsewhere
                                    pool_ids = [cid for cid in pool_ids if cid != jack_id]
        except Exception:
            # Safety: never crash rollouts due to heuristic constraints
            pass

        seats_to_fill = [s for s in range(4) if s != bot_seat]

        dealt_map: dict[int, list[str]] | None = None
        retry_limit = max_deal_retries
        if trump_sample_constrained and not trumpReveal and bot_seat != bidder_seat:
            retry_limit = max(retry_limit, 50)

        if retry_limit > 0:
            for _attempt in range(retry_limit):
                current_pool_ids = pool_ids[:]
                current_hands = [cards[:] for cards in hands]
                current_need_sizes = list(need_sizes)
                current_sim_player_trump = sim_player_trump
                current_sim_trump_suit = sim_trump_suit

                if trump_sample_constrained and not trumpReveal and bot_seat != bidder_seat:
                    retry_pool_ids = base_pool_ids[:]
                    allowed_indicator_ids = _allowed_trump_indicator_ids(
                        retry_pool_ids,
                        bidder_seat=bidder_seat,
                        trump_matrix=trump_matrix,
                    )
                    if not allowed_indicator_ids:
                        break

                    sampled = rng.choice(allowed_indicator_ids)
                    current_sim_player_trump = from_card_id(sampled)
                    current_sim_trump_suit = current_sim_player_trump.suit
                    current_pool_ids = [cid for cid in retry_pool_ids if cid != sampled]
                    rng.shuffle(current_pool_ids)
                    current_hands = [[], [], [], []]
                    current_hands[bot_seat] = bot_hand[:]
                    current_need_sizes = list(hand_sizes)

                    try:
                        if len(s_card_ids) >= 1 and currentSuit:
                            led_suit = currentSuit
                            if all(
                                _card_suit_from_id(cid) == led_suit for cid in s_card_ids
                            ):
                                prior_played = [
                                    cid for cid in played_set if cid not in s_set
                                ]
                                if all(
                                    _card_suit_from_id(cid) != led_suit
                                    for cid in prior_played
                                ):
                                    jack_id = f"{led_suit}_Jack"
                                    if jack_id in current_pool_ids:
                                        actor = (leaderIndex + len(s_card_ids)) % 4
                                        if actor == bot_seat:
                                            remaining_after_actor = [
                                                (leaderIndex + i) % 4
                                                for i in range(len(s_card_ids) + 1, 4)
                                            ]

                                            row = SUIT_MATRIX_INDEX.get(led_suit)
                                            candidates: list[int] = []
                                            for seat in remaining_after_actor:
                                                if current_need_sizes[seat] <= 0:
                                                    continue
                                                if (
                                                    row is not None
                                                    and suit_matrix[row][seat] == 0
                                                ):
                                                    continue
                                                candidates.append(seat)

                                            if candidates:
                                                target = rng.choice(candidates)
                                                current_hands[target].append(
                                                    from_card_id(jack_id)
                                                )
                                                current_need_sizes[target] -= 1
                                                if current_need_sizes[target] < 0:
                                                    current_need_sizes[target] = 0
                                                current_pool_ids = [
                                                    cid
                                                    for cid in current_pool_ids
                                                    if cid != jack_id
                                                ]
                    except Exception:
                        pass

                dealt_map = _deal_unknown_with_suit_constraints(
                    rng=rng,
                    pool_ids=current_pool_ids,
                    seats_to_fill=seats_to_fill,
                    hand_sizes=current_need_sizes,
                    suit_matrix=suit_matrix,
                )
                if dealt_map is not None:
                    sim_player_trump = current_sim_player_trump
                    sim_trump_suit = current_sim_trump_suit
                    hands = current_hands
                    need_sizes = current_need_sizes
                    pool_ids = current_pool_ids
                    break

        if dealt_map is None and trump_sample_constrained and not trumpReveal and bot_seat != bidder_seat:
            sampled = rng.choice(base_pool_ids)
            sim_player_trump = from_card_id(sampled)
            sim_trump_suit = sim_player_trump.suit
            pool_ids = [cid for cid in base_pool_ids if cid != sampled]
            rng.shuffle(pool_ids)
            hands = [[], [], [], []]
            hands[bot_seat] = bot_hand[:]
            need_sizes = list(hand_sizes)

            try:
                if len(s_card_ids) >= 1 and currentSuit:
                    led_suit = currentSuit
                    if all(_card_suit_from_id(cid) == led_suit for cid in s_card_ids):
                        prior_played = [cid for cid in played_set if cid not in s_set]
                        if all(_card_suit_from_id(cid) != led_suit for cid in prior_played):
                            jack_id = f"{led_suit}_Jack"
                            if jack_id in pool_ids:
                                actor = (leaderIndex + len(s_card_ids)) % 4
                                if actor == bot_seat:
                                    remaining_after_actor = [
                                        (leaderIndex + i) % 4
                                        for i in range(len(s_card_ids) + 1, 4)
                                    ]

                                    row = SUIT_MATRIX_INDEX.get(led_suit)
                                    candidates: list[int] = []
                                    for seat in remaining_after_actor:
                                        if need_sizes[seat] <= 0:
                                            continue
                                        if row is not None and suit_matrix[row][seat] == 0:
                                            continue
                                        candidates.append(seat)

                                    if candidates:
                                        target = rng.choice(candidates)
                                        hands[target].append(from_card_id(jack_id))
                                        need_sizes[target] -= 1
                                        if need_sizes[target] < 0:
                                            need_sizes[target] = 0
                                        pool_ids = [cid for cid in pool_ids if cid != jack_id]
            except Exception:
                pass

            if max_deal_retries > 0:
                for _attempt in range(max_deal_retries):
                    rng.shuffle(pool_ids)
                    dealt_map = _deal_unknown_with_suit_constraints(
                        rng=rng,
                        pool_ids=pool_ids,
                        seats_to_fill=seats_to_fill,
                        hand_sizes=need_sizes,
                        suit_matrix=suit_matrix,
                    )
                    if dealt_map is not None:
                        break

        if dealt_map is not None:
            for seat in seats_to_fill:
                # Preserve any pre-assigned cards (trump indicator / jack constraint)
                existing = hands[seat]
                hands[seat] = existing + [from_card_id(cid) for cid in dealt_map[seat]]
        else:
            # Fallback: unconstrained slice dealing
            pool_idx = 0
            for seat in range(4):
                if seat == bot_seat:
                    continue
                need = need_sizes[seat]
                slice_ids = pool_ids[pool_idx : pool_idx + need]
                pool_idx += need
                existing = hands[seat]
                hands[seat] = existing + [from_card_id(cid) for cid in slice_ids]

        # Build legacy players structure
        players = []
        for i in range(4):
            players.append(
                {
                    "cards": hands[i],
                    "isTrump": i == bidder_seat,
                    "team": 1 if i % 2 == 0 else 2,
                    "trump": sim_player_trump if i == bidder_seat else None,
                }
            )

        reward_distribution: list[tuple[object, float]] = []

        dump_enabled = _env_bool("APP_DUMP_ROLLOUT_CRASHES", False)
        call_log_max = int(os.getenv("APP_RESULT_CALL_LOG_SIZE", "80"))
        result_call_log = []

        orig_result = legacy_minimax.result

        def traced_result(
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
            none_pos = _find_none_positions(players)
            if none_pos:
                raise RuntimeError(f"None already present in players hands: {none_pos}")

            actor = (playerChance + len(s)) % 4

            entry = {
                "actor": actor,
                "leaderIndex_playerChance": playerChance,
                "sLenBefore": len(s),
                "currentSuit": currentSuit,
                "trumpReveal": trumpReveal,
                "chose": chose,
                "finalBid": finalBid,
                "playerTrumpCardId": _safe_card_id(playerTrump),
                "action": (
                    {"type": "bool", "value": a}
                    if isinstance(a, bool)
                    else {
                        "type": "card",
                        "cardId": _safe_card_id(a),
                        "isNone": a is None,
                    }
                ),
                "playersHandSizes": [len(players[i]["cards"]) for i in range(4)],
            }
            result_call_log.append(entry)
            if len(result_call_log) > call_log_max:
                result_call_log.pop(0)

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
                _tr2,
                _ch2,
                _pt2,
                _tp2,
                _ti2,
                players2,
                _ts2,
                _fb2,
                _undo,
            ) = out

            none_pos2 = _find_none_positions(players2)
            if none_pos2:
                raise RuntimeError(f"None introduced into players hands: {none_pos2}")

            return out

        if dump_enabled:
            legacy_minimax.result = traced_result

        try:
            legacy_minimax.minimax_extended(
                s_cards[:],
                True,
                True,
                trumpPlayed,
                s_cards[:],
                trumpIndice[:],
                leaderIndex,
                players,
                currentSuit,
                trumpReveal,
                sim_trump_suit,
                chose,
                finalBid,
                sim_player_trump,
                -1,
                reward_distribution,
                0,
                0,
                k,
            )
        except Exception as e:
            if dump_enabled:
                dump = {
                    "kind": "rollout_crash_dump",
                    "pid": os.getpid(),
                    "seed": seed,
                    "n": n,
                    "exception": {
                        "type": type(e).__name__,
                        "message": str(e),
                        "traceback": traceback.format_exc(),
                    },
                    "snapshot": snapshot,
                    "simulated": {
                        "simPlayerTrumpCardId": _safe_card_id(sim_player_trump),
                        "simTrumpSuit": sim_trump_suit,
                        "sCardIds": [_safe_card_id(c) for c in s_cards],
                        "playersCardsCardIds": _players_to_cardids(players),
                    },
                    "minimaxCall": {
                        "sCardIds": [_safe_card_id(c) for c in s_cards],
                        "first": True,
                        "secondary": True,
                        "trumpPlayed": trumpPlayed,
                        "trumpIndice": list(trumpIndice),
                        "leaderIndex_playerChance": leaderIndex,
                        "currentSuit": currentSuit,
                        "trumpReveal": trumpReveal,
                        "trumpSuit": sim_trump_suit,
                        "chose": chose,
                        "finalBid": finalBid,
                        "playerTrumpCardId": _safe_card_id(sim_player_trump),
                        "k": k,
                    },
                    "resultCallLogTail": result_call_log,
                }

                fn = f"crash_{int(time.time()*1000)}_pid{os.getpid()}_seed{seed}.json"
                path = _dump_dir_backend_root() / fn
                path.write_text(json.dumps(dump, indent=2), encoding="utf-8")

                raise RuntimeError(f"ROLL_OUT_CRASH_DUMP={str(path)}") from e

            raise
        finally:
            legacy_minimax.result = orig_result

        for a, _v in reward_distribution:
            counts[a] += 1

    return dict(counts)


# -----------------------------
# Main-process async chooser
# -----------------------------


def _build_snapshot(state, bot_seat: int) -> dict[str, Any]:
    # played cards include completed catches + current trick
    played_cards = []
    for c in state.team1Catches:
        played_cards.extend(c)
    for c in state.team2Catches:
        played_cards.extend(c)
    played_cards.extend(state.s)

    played_ids = [to_card_id(c) for c in played_cards]
    bot_hand_ids = [to_card_id(c) for c in state.play_players[bot_seat]["cards"]]

    bidder_seat = state.finalBid - 1

    concealed_id = None
    if state.player_trump is not None:
        if bot_seat == bidder_seat or state.trumpReveal:
            concealed_id = to_card_id(state.player_trump)

    snap: dict[str, Any] = {
        "botSeat": bot_seat,
        "finalBid": state.finalBid,
        "bidderSeat": bidder_seat,
        "leaderIndex": state.leaderIndex,
        "catchNumber": state.catchNumber,
        "k": compute_k(state.catchNumber),
        "trumpReveal": state.trumpReveal,
        "knownTrumpSuit": state.trumpSuit if state.trumpReveal else None,
        "chose": state.chose,
        "currentSuit": state.currentSuit,
        "trumpPlayed": state.trumpPlayed,
        "trumpIndice": list(state.trumpIndice),
        "sCardIds": [to_card_id(c) for c in state.s],
        "botHandCardIds": bot_hand_ids,
        "handSizes": [len(state.play_players[i]["cards"]) for i in range(4)],
        "playedCardIds": played_ids,
        "concealedTrumpCardId": concealed_id,
        # NEW: suit knowledge matrix for constraint-aware dealing
        "suitMatrix": state.suit_matrix,
        "trumpMatrix": state.trump_matrix,
    }

    return snap


def _build_rollout_batch_sizes(
    *,
    total_rollouts: int,
    worker_count: int,
    timeout_enabled: bool,
    micro_batch_size: int,
) -> list[int]:
    if total_rollouts <= 0:
        return []

    if timeout_enabled:
        if micro_batch_size > 0:
            batch_size = micro_batch_size
        else:
            # Auto-size for reliable partial completions under timeout mode.
            # Creates many small chunks by default.
            batch_size = max(1, min(25, total_rollouts // max(1, worker_count * 8)))

        batches: list[int] = []
        remaining = total_rollouts
        while remaining > 0:
            n = min(batch_size, remaining)
            batches.append(n)
            remaining -= n
        return batches

    base = total_rollouts // worker_count
    rem = total_rollouts % worker_count
    return [base + (1 if i < rem else 0) for i in range(worker_count)]


async def choose_action_with_rollouts_parallel(
    state,
    bot_seat: int,
    pool: ProcessPoolExecutor,
) -> tuple[str, dict]:
    """
    Returns:
      ("REVEAL", {"seatIndex": bot_seat, "reveal": bool})
      or
      ("PLAY", {"seatIndex": bot_seat, "cardId": "Hearts_Jack"})
    """
    from app.engine.play_engine import compute_play_legal_actions

    legal = compute_play_legal_actions(state)
    if legal.type == "NO_ACTION":
        raise RuntimeError("Bot has no legal action.")

    total_rollouts = max(1, int(settings.rollouts))
    worker_count = max(1, min(int(settings.workers), total_rollouts))
    timeout_seconds = max(0.0, float(settings.bot_think_timeout_seconds))
    timeout_enabled = timeout_seconds > 0.0

    snapshot = _build_snapshot(state, bot_seat)

    batch_sizes = _build_rollout_batch_sizes(
        total_rollouts=total_rollouts,
        worker_count=worker_count,
        timeout_enabled=timeout_enabled,
        micro_batch_size=max(0, int(settings.rollout_micro_batch_size)),
    )

    use_ray = settings.rollout_backend == "ray"
    completed_rollouts = 0

    try:
        if use_ray:
            ray, remote_fn = _get_ray_rollout_remote()
            if not timeout_enabled:
                refs = []
                for n in batch_sizes:
                    seed = _seed_entropy()
                    refs.append(remote_fn.remote(snapshot, n, seed))
                results = await asyncio.to_thread(ray.get, refs)
                completed_rollouts = sum(batch_sizes)
            else:
                results = []
                deadline = time.monotonic() + timeout_seconds

                next_batch_idx = 0
                in_flight: dict[Any, int] = {}

                def _submit_one() -> bool:
                    nonlocal next_batch_idx
                    if next_batch_idx >= len(batch_sizes):
                        return False
                    n = batch_sizes[next_batch_idx]
                    next_batch_idx += 1
                    seed = _seed_entropy()
                    ref = remote_fn.remote(snapshot, n, seed)
                    in_flight[ref] = n
                    return True

                for _ in range(min(worker_count, len(batch_sizes))):
                    if not _submit_one():
                        break

                while in_flight:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break

                    ready_refs, _ = await asyncio.to_thread(
                        ray.wait,
                        list(in_flight.keys()),
                        1,
                        remaining,
                    )
                    if not ready_refs:
                        break

                    for ref in ready_refs:
                        n = in_flight.pop(ref, 0)
                        res = await asyncio.to_thread(ray.get, ref)
                        results.append(res)
                        completed_rollouts += n
                        _submit_one()

                for ref in list(in_flight.keys()):
                    try:
                        await asyncio.to_thread(ray.cancel, ref, False)
                    except Exception:
                        pass
        else:
            loop = asyncio.get_running_loop()
            if not timeout_enabled:
                tasks = []
                for n in batch_sizes:
                    seed = _seed_entropy()
                    fut = pool.submit(rollout_worker, snapshot, n, seed)
                    tasks.append(asyncio.wrap_future(fut, loop=loop))
                results = await asyncio.gather(*tasks)
                completed_rollouts = sum(batch_sizes)
            else:
                results = []
                deadline = time.monotonic() + timeout_seconds

                next_batch_idx = 0
                in_flight: dict[asyncio.Future, tuple[Any, int]] = {}

                def _submit_one() -> bool:
                    nonlocal next_batch_idx
                    if next_batch_idx >= len(batch_sizes):
                        return False
                    n = batch_sizes[next_batch_idx]
                    next_batch_idx += 1
                    seed = _seed_entropy()
                    cfut = pool.submit(rollout_worker, snapshot, n, seed)
                    afut = asyncio.wrap_future(cfut, loop=loop)
                    in_flight[afut] = (cfut, n)
                    return True

                for _ in range(min(worker_count, len(batch_sizes))):
                    if not _submit_one():
                        break

                while in_flight:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break

                    done, _ = await asyncio.wait(
                        set(in_flight.keys()),
                        timeout=remaining,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if not done:
                        break

                    for afut in done:
                        _cfut, n = in_flight.pop(afut)
                        res = afut.result()
                        results.append(res)
                        completed_rollouts += n
                        _submit_one()

                for _afut, (cfut, _n) in list(in_flight.items()):
                    try:
                        cfut.cancel()
                    except Exception:
                        pass
    except Exception as e:
        msg = str(e)
        if "ROLL_OUT_CRASH_DUMP=" in msg:
            dump_path = msg.split("ROLL_OUT_CRASH_DUMP=", 1)[1].strip()
            try:
                state.event_log.append(f"BOT CRASH DUMP: {dump_path}")
            except Exception:
                pass
            print("BOT CRASH DUMP:", dump_path)
        else:
            print("Bot rollout crashed:", repr(e))

        if legal.type == "REVEAL_CHOICE":
            return ("REVEAL", {"seatIndex": bot_seat, "reveal": False})
        return ("PLAY", {"seatIndex": bot_seat, "cardId": legal.cardIds[0]})

    if timeout_enabled and completed_rollouts < total_rollouts:
        timeout_msg = (
            f"Bot think timeout hit: used {completed_rollouts}/{total_rollouts} rollouts "
            f"in {timeout_seconds:.2f}s."
        )
        print(timeout_msg)
        try:
            state.event_log.append(timeout_msg)
        except Exception:
            pass

    if completed_rollouts > 0:
        _record_rollouts(completed_rollouts)

    merged: Counter = Counter()
    for d in results:
        merged.update(d)

    if not merged:
        if legal.type == "REVEAL_CHOICE":
            return ("REVEAL", {"seatIndex": bot_seat, "reveal": False})
        return ("PLAY", {"seatIndex": bot_seat, "cardId": legal.cardIds[0]})

    best_action, _ = merged.most_common(1)[0]

    # bool => reveal choice
    if isinstance(best_action, bool):
        return ("REVEAL", {"seatIndex": bot_seat, "reveal": bool(best_action)})

    # string => card identity
    if isinstance(best_action, str):
        if legal.type != "PLAY_CARD" or not legal.cardIds:
            return ("REVEAL", {"seatIndex": bot_seat, "reveal": False})

        for cid in legal.cardIds:
            if from_card_id(cid).identity() == best_action:
                return ("PLAY", {"seatIndex": bot_seat, "cardId": cid})

        return ("PLAY", {"seatIndex": bot_seat, "cardId": legal.cardIds[0]})

    if legal.type == "REVEAL_CHOICE":
        return ("REVEAL", {"seatIndex": bot_seat, "reveal": False})
    return ("PLAY", {"seatIndex": bot_seat, "cardId": legal.cardIds[0]})
