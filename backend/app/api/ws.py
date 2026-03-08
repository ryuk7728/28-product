from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Awaitable, Callable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.bots.bidding_bot import plan_bid_and_trump_from_first4
from app.engine.bidding_engine import (
    compute_r1_turn_rules,
    compute_r2_turn_rules,
    validate_r1_bid_value,
    validate_r2_bid_value,
)
from app.engine.cards_adapter import from_card_id, to_card_id
from app.engine.game_manager import game_manager
from app.engine.legal_actions import get_legal_actions
from app.engine.room_manager import RoomNotFoundError, RoomTokenError, room_manager
from app.engine.play_engine import (
    init_play_state,
    apply_play_card,
    apply_reveal_choice,
    resolve_if_catch_complete,
)
from app.engine.bot_runner import advance_bots_until_human

router = APIRouter()

BOT_SEATS = {0, 2}

# Delay to display completed trick (4 cards visible)
TRICK_DISPLAY_DELAY_SECONDS = 3
# Pause duration for empty table between tricks
EMPTY_TABLE_PAUSE_SECONDS = 1

_ROOM_CONNECTIONS: dict[str, list[tuple[WebSocket, int | None, bool]]] = defaultdict(list)
_ROOM_REGISTRY_LOCK = asyncio.Lock()


async def _register_room_connection(
    room_code: str, websocket: WebSocket, viewer_seat: int | None, can_act: bool
) -> None:
    async with _ROOM_REGISTRY_LOCK:
        key = room_code.upper()
        _ROOM_CONNECTIONS[key].append((websocket, viewer_seat, can_act))


async def _unregister_room_connection(room_code: str, websocket: WebSocket) -> None:
    async with _ROOM_REGISTRY_LOCK:
        key = room_code.upper()
        conns = _ROOM_CONNECTIONS.get(key, [])
        _ROOM_CONNECTIONS[key] = [
            (ws, seat, can_act)
            for ws, seat, can_act in conns
            if ws is not websocket
        ]
        if not _ROOM_CONNECTIONS[key]:
            _ROOM_CONNECTIONS.pop(key, None)


async def _room_connections_snapshot(
    room_code: str,
) -> list[tuple[WebSocket, int | None, bool]]:
    async with _ROOM_REGISTRY_LOCK:
        return list(_ROOM_CONNECTIONS.get(room_code.upper(), []))


async def _send_state(websocket: WebSocket, state) -> None:
    await _send_state_for_viewer(websocket, state, viewer_seat=None, can_act=True)


def _filter_actions_for_viewer(
    actions: dict, viewer_seat: int | None, can_act: bool
) -> dict:
    if not can_act:
        return {"type": "NO_ACTION"}

    if viewer_seat is None:
        return actions

    action_type = actions.get("type")
    action_seat = actions.get("seatIndex")

    if action_type == "MANUAL_DEAL_REST":
        return {"type": "NO_ACTION", "seatIndex": viewer_seat}

    if isinstance(action_seat, int) and action_seat != viewer_seat:
        return {"type": "NO_ACTION", "seatIndex": viewer_seat}

    return actions


async def _send_state_for_viewer(
    websocket: WebSocket, state, viewer_seat: int | None, can_act: bool
) -> None:
    actions = get_legal_actions(state)
    state_payload = (
        state.to_public_dict()
        if viewer_seat is None
        else state.to_public_dict_for_viewer(viewer_seat)
    )
    filtered_actions = _filter_actions_for_viewer(actions, viewer_seat, can_act)
    await websocket.send_json({"type": "STATE_UPDATE", "state": state_payload})
    await websocket.send_json({"type": "LEGAL_ACTIONS", "actions": filtered_actions})


async def _broadcast_room_state(room_code: str, state) -> None:
    stale_sockets: list[WebSocket] = []
    for ws, viewer_seat, can_act in await _room_connections_snapshot(room_code):
        try:
            await _send_state_for_viewer(ws, state, viewer_seat, can_act)
        except Exception:
            stale_sockets.append(ws)

    for ws in stale_sockets:
        await _unregister_room_connection(room_code, ws)


def _validate_manual_rest_deal(state, rest_hands: list[list[str]]) -> None:
    if len(rest_hands) != 4:
        raise ValueError("restHands must have 4 lists (one per player).")

    for i, h in enumerate(rest_hands):
        if len(h) != 4:
            raise ValueError(f"Player {i+1} must receive exactly 4 cards.")

    flat = [cid for h in rest_hands for cid in h]
    if len(flat) != 16:
        raise ValueError("Total restHands cards must be 16.")

    if len(set(flat)) != 16:
        raise ValueError("Duplicate cardIds found in restHands.")

    draw_ids = {to_card_id(c) for c in state.draw_pile}
    chosen_ids = set(flat)
    if draw_ids != chosen_ids:
        raise ValueError("restHands must use exactly the 16 remaining draw pile cards.")


def _partner_seat(seat: int) -> int:
    return seat ^ 2  # 0<->2, 1<->3


def _current_highest_r1(state) -> tuple[int, int | None]:
    max_bid = 0
    max_seat: int | None = None
    for seat, b in enumerate(state.bids_r1_by_seat):
        if b and b > max_bid:
            max_bid = b
            max_seat = seat
    return max_bid, max_seat


def _effective_hand_for_seat(state, seat: int) -> list:
    """
    During bidding/trump select, the concealed trump indicator card is removed from
    bidder's hand. For post-8-card checks, treat bidder as holding it.
    """
    cards = list(state.players_cards[seat])
    if state.final_bidder_seat == seat and state.player_trump is not None:
        cards.append(state.player_trump)
    return cards


def _abort_reason_after_full_deal(state) -> str | None:
    """
    Rule 2: any player has all 4 jacks in their 8-card holding
    Rule 3: bidding team has all 8 trumps, defenders have 0
    """
    # Rule 2: 4 jacks
    for seat in range(4):
        cards = _effective_hand_for_seat(state, seat)
        jack_count = sum(1 for c in cards if getattr(c, "rank", None) == "Jack")
        if jack_count == 4:
            return "ALL_FOUR_JACKS"

    # Rule 3: all 8 trumps in bidder team
    if state.final_bidder_seat is None or state.player_trump is None:
        return None

    trump_suit = state.player_trump.suit
    bidder_seat = state.final_bidder_seat
    bidder_team = 1 if bidder_seat % 2 == 0 else 2

    team1_trumps = 0
    team2_trumps = 0
    for seat in range(4):
        cards = _effective_hand_for_seat(state, seat)
        t = sum(1 for c in cards if getattr(c, "suit", None) == trump_suit)
        if seat % 2 == 0:
            team1_trumps += t
        else:
            team2_trumps += t

    bidder_trumps = team1_trumps if bidder_team == 1 else team2_trumps
    defender_trumps = team2_trumps if bidder_team == 1 else team1_trumps

    if bidder_trumps == 8 and defender_trumps == 0:
        return "ALL_TRUMPS_ONE_SIDE"

    return None


async def _abort_game(websocket: WebSocket, game_id: str, reason: str) -> None:
    await websocket.send_json({"type": "GAME_ABORTED", "reason": reason})
    await websocket.close()
    game_manager.delete_game(game_id)


def _apply_r1_bid(state, *, seat: int, bid_value: int) -> None:
    if seat != state.turn_index:
        raise ValueError("Not this seat's turn to bid (R1).")

    first4_points_by_seat = [
        sum(c.points for c in state.players_cards[i]) for i in range(4)
    ]
    rules = compute_r1_turn_rules(
        bidding_order=state.bidding_order,
        step=state.bidding_r1_step,
        bids_by_pos=state.bidding_r1_bids_by_pos,
        passes_by_pos=state.bidding_r1_passes_by_pos,
        final_pos=state.bidding_r1_final_pos,
        first4_points_by_seat=first4_points_by_seat,
    )

    validate_r1_bid_value(rules=rules, bid_value=bid_value)

    pos = state.bidding_r1_step
    state.bidding_r1_bids_by_pos[pos] = bid_value
    state.bids_r1_by_seat[seat] = bid_value

    if bid_value == 0:
        state.bidding_r1_passes_by_pos[pos] = True
        state.event_log.append(f"P{seat+1} passed.")
    else:
        state.bidding_r1_final_pos = pos
        state.event_log.append(f"P{seat+1} bid {bid_value}.")

    state.bidding_r1_step += 1

    if state.bidding_r1_step >= 4:
        winner_pos = state.bidding_r1_final_pos
        winner_seat = state.bidding_order[winner_pos]
        winner_bid = state.bidding_r1_bids_by_pos[winner_pos]

        state.round1_bidder_seat = winner_seat
        state.round1_bid_value = winner_bid
        state.final_bidder_seat = winner_seat
        state.final_bid_value = winner_bid

        state.phase = "TRUMP_SELECT_R1"
        state.event_log.append(
            f"R1 winner: P{winner_seat+1} with {winner_bid}. Select trump."
        )


def _apply_r2_bid(state, *, seat: int, bid_value: int) -> None:
    if seat != state.turn_index:
        raise ValueError("Not this seat's turn to bid (R2).")

    rules = compute_r2_turn_rules(
        bidding_order=state.bidding_order,
        step=state.bidding_r2_step,
        bids_so_far_by_pos=state.bidding_r2_bids_by_pos,
    )

    validate_r2_bid_value(rules=rules, bid_value=bid_value)

    pos = state.bidding_r2_step
    state.bidding_r2_bids_by_pos[pos] = bid_value
    state.bids_r2_by_seat[seat] = bid_value

    if bid_value == 0:
        state.event_log.append(f"P{seat+1} passed (R2).")
    else:
        state.event_log.append(f"P{seat+1} bid {bid_value} (R2).")

    state.bidding_r2_step += 1

    if state.bidding_r2_step >= 4:
        max_bid = max(state.bidding_r2_bids_by_pos)
        if max_bid == 0:
            state.final_bidder_seat = state.round1_bidder_seat
            state.final_bid_value = state.round1_bid_value
            state.phase = "PLAY"
            init_play_state(state)
            state.event_log.append("No further bids in R2. Entering PLAY.")
        else:
            max_pos = state.bidding_r2_bids_by_pos.index(max_bid)
            new_bidder_seat = state.bidding_order[max_pos]

            if state.player_trump is not None and state.round1_bidder_seat is not None:
                state.players_cards[state.round1_bidder_seat].append(state.player_trump)

            state.final_bidder_seat = new_bidder_seat
            state.final_bid_value = max_bid
            state.phase = "TRUMP_SELECT_R2"
            state.event_log.append(
                f"R2 winner: P{new_bidder_seat+1} with {max_bid}. Select new trump."
            )


def _apply_select_trump_card(state, *, seat: int, card_id: str) -> None:
    if state.phase not in ("TRUMP_SELECT_R1", "TRUMP_SELECT_R2"):
        raise ValueError("Not in trump selection phase.")
    if state.final_bidder_seat is None:
        raise ValueError("final_bidder_seat not set.")
    if seat != state.final_bidder_seat:
        raise ValueError("Not your trump selection turn.")

    chosen = from_card_id(card_id)
    hand = state.players_cards[seat]
    removed = False
    for i, c in enumerate(hand):
        if c.identity() == chosen.identity():
            state.player_trump = hand.pop(i)
            removed = True
            break

    if not removed:
        raise ValueError("Card not in hand.")

    state.event_log.append(f"P{seat+1} selected a concealed trump card.")

    if state.phase == "TRUMP_SELECT_R1":
        state.phase = "MANUAL_DEAL_REST"
        state.event_log.append(
            "Manual deal: assign the remaining 4 cards to each player."
        )
        return

    state.phase = "PLAY"
    init_play_state(state)
    state.event_log.append("Entering PLAY after R2 trump selection.")


async def _advance_bots_until_human_any_phase(
    state, pool, bot_sem, websocket: WebSocket, game_id: str, send_state_fn
) -> None:
    """
    Auto-advance bot seats (0,2) in:
      - BIDDING_R1: rules-based bid (and if starting bidder has canRedeal -> bot always redeals)
      - TRUMP_SELECT_R1: rules-based trump pick
      - BIDDING_R2: bots always pass
      - PLAY: rollout bot plays
    """
    while True:
        if state.phase == "BIDDING_R1":
            seat = state.turn_index
            if seat not in BOT_SEATS:
                return

            first4_points_by_seat = [
                sum(c.points for c in state.players_cards[i]) for i in range(4)
            ]
            rules = compute_r1_turn_rules(
                bidding_order=state.bidding_order,
                step=state.bidding_r1_step,
                bids_by_pos=state.bidding_r1_bids_by_pos,
                passes_by_pos=state.bidding_r1_passes_by_pos,
                final_pos=state.bidding_r1_final_pos,
                first4_points_by_seat=first4_points_by_seat,
            )

            # Rule 1: if bot is the first bidder and canRedeal => always redeal
            # (disabled in fixed deck mode to keep deterministic progression)
            if state.bidding_r1_step == 0 and rules.can_redeal and not state.fixed_deck_mode:
                state.event_log.append(f"P{seat+1} requested redeal.")
                game_manager.redeal_first4_in_place(state)
                continue

            plan = plan_bid_and_trump_from_first4(
                [to_card_id(c) for c in state.players_cards[seat]]
            )

            current_highest, highest_seat = _current_highest_r1(state)
            partner = _partner_seat(seat)

            if highest_seat == partner and highest_seat in BOT_SEATS:
                bid_value = 0
            else:
                bid_value = plan.bid if plan.bid > current_highest else 0

            if bid_value != 0:
                if bid_value <= rules.min_bid_exclusive or bid_value > rules.max_bid_inclusive:
                    bid_value = 0

            if bid_value == 0 and not rules.can_pass:
                bid_value = max(rules.min_bid_exclusive + 1, 14)

            _apply_r1_bid(state, seat=seat, bid_value=bid_value)
            continue

        if state.phase == "TRUMP_SELECT_R1":
            seat = state.final_bidder_seat
            if seat is None or seat not in BOT_SEATS:
                return

            plan = plan_bid_and_trump_from_first4(
                [to_card_id(c) for c in state.players_cards[seat]]
            )
            card_id = plan.trump_card_id

            legal_ids = [to_card_id(c) for c in state.players_cards[seat]]
            if card_id not in legal_ids and legal_ids:
                card_id = legal_ids[0]

            _apply_select_trump_card(state, seat=seat, card_id=card_id)
            continue

        if state.phase == "MANUAL_DEAL_REST":
            # If auto_deal mode, automatically deal the rest of the cards
            if state.auto_deal:
                game_manager.auto_deal_rest(state)

                # Check abort conditions after full deal
                reason = _abort_reason_after_full_deal(state)
                if reason:
                    state.event_log.append(f"GAME ABORTED: {reason}")
                    # Note: Caller must handle abort after this function returns
                    # We set a marker that will be checked
                    state.phase = "GAME_OVER"
                    state.winnerTeam = -1  # Marker for abort
                    return

                # Proceed to R2 bidding
                state.phase = "BIDDING_R2"
                state.bidding_r2_step = 0
                state.bidding_r2_bids_by_pos = [0, 0, 0, 0]
                state.bids_r2_by_seat = [0, 0, 0, 0]
                state.event_log.append("Auto-deal complete. Bidding Round 2 starts.")
                continue  # Continue advancing bots in R2
            return

        if state.phase == "BIDDING_R2":
            seat = state.turn_index
            if seat not in BOT_SEATS:
                return
            _apply_r2_bid(state, seat=seat, bid_value=0)
            continue

        if state.phase == "TRUMP_SELECT_R2":
            # Bots should not reach here because they always pass R2, but keep safe.
            seat = state.final_bidder_seat
            if seat is None or seat not in BOT_SEATS:
                return
            legal_ids = [to_card_id(c) for c in state.players_cards[seat]]
            if not legal_ids:
                return
            _apply_select_trump_card(state, seat=seat, card_id=legal_ids[0])
            continue

        if state.phase == "PLAY":
            await advance_bots_until_human(
                state, pool, bot_sem, websocket, send_state_fn
            )
            return

        return


def _extract_authorized_seat(msg: dict, viewer_seat: int | None) -> int:
    raw = msg.get("seatIndex")
    if viewer_seat is None:
        if raw is None:
            raise ValueError("seatIndex is required.")
        return int(raw)
    if raw is None:
        return viewer_seat
    requested = int(raw)
    if requested != viewer_seat:
        raise ValueError("You can only act for your assigned seat.")
    return viewer_seat


async def _run_ws_session(
    websocket: WebSocket,
    *,
    game_id: str,
    state,
    viewer_seat: int | None,
    can_act: bool = True,
    broadcast_state: Callable[[object], Awaitable[None]] | None = None,
) -> None:
    app = websocket.scope["app"]
    pool = app.state.process_pool
    bot_sem = app.state.bot_sem

    async def send_state_current() -> None:
        if broadcast_state is not None:
            await broadcast_state(state)
            return
        await _send_state_for_viewer(websocket, state, viewer_seat, can_act)

    async def send_state_fn(ws: WebSocket, current_state) -> None:
        if broadcast_state is not None:
            await broadcast_state(current_state)
            return
        await _send_state_for_viewer(ws, current_state, viewer_seat, can_act)

    await _advance_bots_until_human_any_phase(
        state, pool, bot_sem, websocket, game_id, send_state_fn
    )

    if state.phase == "GAME_OVER" and state.winnerTeam == -1:
        reason = "UNKNOWN"
        for log in reversed(state.event_log):
            if "ALL_FOUR_JACKS" in log:
                reason = "ALL_FOUR_JACKS"
                break
            if "ALL_TRUMPS_ONE_SIDE" in log:
                reason = "ALL_TRUMPS_ONE_SIDE"
                break
        await _abort_game(websocket, game_id, reason)
        return

    await send_state_current()

    try:
        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type")

            if msg_type == "GET_STATE":
                await send_state_current()
                continue

            if not can_act:
                await websocket.send_json(
                    {"type": "ERROR", "message": "Spectator connection is read-only."}
                )
                continue

            if msg_type == "SUBMIT_BID":
                try:
                    seat = _extract_authorized_seat(msg, viewer_seat)
                except ValueError as e:
                    await websocket.send_json({"type": "ERROR", "message": str(e)})
                    continue
                bid_value = int(msg.get("bidValue"))

                if state.phase == "BIDDING_R1":
                    if seat != state.turn_index:
                        await websocket.send_json(
                            {"type": "ERROR", "message": f"Not P{seat+1}'s turn to bid."}
                        )
                        continue

                    first4_points_by_seat = [
                        sum(c.points for c in state.players_cards[i]) for i in range(4)
                    ]
                    rules = compute_r1_turn_rules(
                        bidding_order=state.bidding_order,
                        step=state.bidding_r1_step,
                        bids_by_pos=state.bidding_r1_bids_by_pos,
                        passes_by_pos=state.bidding_r1_passes_by_pos,
                        final_pos=state.bidding_r1_final_pos,
                        first4_points_by_seat=first4_points_by_seat,
                    )

                    try:
                        validate_r1_bid_value(rules=rules, bid_value=bid_value)
                    except ValueError as e:
                        await websocket.send_json({"type": "ERROR", "message": str(e)})
                        continue

                    if bid_value == -1:
                        if state.bidding_r1_step != 0 or not rules.can_redeal:
                            await websocket.send_json(
                                {"type": "ERROR", "message": "Redeal not allowed now."}
                            )
                            continue

                        state.event_log.append(f"P{seat+1} requested redeal.")
                        game_manager.redeal_first4_in_place(state)

                        await _advance_bots_until_human_any_phase(
                            state, pool, bot_sem, websocket, game_id, send_state_fn
                        )
                        await send_state_current()
                        continue

                    _apply_r1_bid(state, seat=seat, bid_value=bid_value)

                    await _advance_bots_until_human_any_phase(
                        state, pool, bot_sem, websocket, game_id, send_state_fn
                    )
                    await send_state_current()
                    continue

                if state.phase == "BIDDING_R2":
                    if seat != state.turn_index:
                        await websocket.send_json(
                            {"type": "ERROR", "message": f"Not P{seat+1}'s turn to bid."}
                        )
                        continue

                    try:
                        validate_r2_bid_value(
                            rules=compute_r2_turn_rules(
                                bidding_order=state.bidding_order,
                                step=state.bidding_r2_step,
                                bids_so_far_by_pos=state.bidding_r2_bids_by_pos,
                            ),
                            bid_value=bid_value,
                        )
                    except ValueError as e:
                        await websocket.send_json({"type": "ERROR", "message": str(e)})
                        continue

                    _apply_r2_bid(state, seat=seat, bid_value=bid_value)
                    await _send_state(websocket, state)

                    await _advance_bots_until_human_any_phase(
                        state, pool, bot_sem, websocket, game_id, send_state_fn
                    )
                    await send_state_current()
                    continue

                await websocket.send_json(
                    {"type": "ERROR", "message": "Not in a bidding phase."}
                )
                continue

            if msg_type == "SELECT_TRUMP_CARD":
                try:
                    seat = _extract_authorized_seat(msg, viewer_seat)
                except ValueError as e:
                    await websocket.send_json({"type": "ERROR", "message": str(e)})
                    continue
                card_id = str(msg.get("cardId"))

                try:
                    _apply_select_trump_card(state, seat=seat, card_id=card_id)
                except ValueError as e:
                    await websocket.send_json({"type": "ERROR", "message": str(e)})
                    continue

                await _advance_bots_until_human_any_phase(
                    state, pool, bot_sem, websocket, game_id, send_state_fn
                )
                await send_state_current()
                continue

            if msg_type == "SUBMIT_REST_DEAL":
                if viewer_seat is not None:
                    await websocket.send_json(
                        {"type": "ERROR", "message": "Manual deal is not allowed here."}
                    )
                    continue

                if state.phase != "MANUAL_DEAL_REST":
                    await websocket.send_json(
                        {"type": "ERROR", "message": "Not in MANUAL_DEAL_REST phase."}
                    )
                    continue

                rest_hands = msg.get("restHands")
                try:
                    if not isinstance(rest_hands, list):
                        raise ValueError("restHands must be a list.")
                    _validate_manual_rest_deal(state, rest_hands)

                    for seat in range(4):
                        for cid in rest_hands[seat]:
                            state.players_cards[seat].append(from_card_id(cid))

                    state.draw_pile.clear()

                    reason = _abort_reason_after_full_deal(state)
                    if reason:
                        state.event_log.append(f"GAME ABORTED: {reason}")
                        await _abort_game(websocket, game_id, reason)
                        return

                    state.phase = "BIDDING_R2"
                    state.bidding_r2_step = 0
                    state.bidding_r2_bids_by_pos = [0, 0, 0, 0]
                    state.bids_r2_by_seat = [0, 0, 0, 0]
                    state.event_log.append("Manual deal complete. Bidding Round 2 starts.")

                    await _advance_bots_until_human_any_phase(
                        state, pool, bot_sem, websocket, game_id, send_state_fn
                    )
                    await send_state_current()
                except ValueError as e:
                    await websocket.send_json({"type": "ERROR", "message": str(e)})

                continue

            if msg_type == "CHOOSE_REVEAL_TRUMP":
                try:
                    seat = _extract_authorized_seat(msg, viewer_seat)
                except ValueError as e:
                    await websocket.send_json({"type": "ERROR", "message": str(e)})
                    continue
                reveal = bool(msg.get("reveal"))

                if state.phase != "PLAY":
                    await websocket.send_json(
                        {"type": "ERROR", "message": "Not in PLAY phase."}
                    )
                    continue

                if len(state.s) == 4:
                    await websocket.send_json(
                        {
                            "type": "ERROR",
                            "message": "Trick is resolving. Wait for next turn.",
                        }
                    )
                    continue

                try:
                    apply_reveal_choice(state, seat, reveal)
                    await send_state_current()

                    if len(state.s) == 4:
                        await asyncio.sleep(TRICK_DISPLAY_DELAY_SECONDS)
                        resolve_if_catch_complete(state)
                        await send_state_current()
                        await asyncio.sleep(EMPTY_TABLE_PAUSE_SECONDS)
                    else:
                        resolve_if_catch_complete(state)

                    await _advance_bots_until_human_any_phase(
                        state, pool, bot_sem, websocket, game_id, send_state_fn
                    )
                except ValueError as e:
                    await websocket.send_json({"type": "ERROR", "message": str(e)})
                    continue

                await send_state_current()
                continue

            if msg_type == "PLAY_CARD":
                try:
                    seat = _extract_authorized_seat(msg, viewer_seat)
                except ValueError as e:
                    await websocket.send_json({"type": "ERROR", "message": str(e)})
                    continue
                card_id = str(msg.get("cardId"))

                if state.phase != "PLAY":
                    await websocket.send_json(
                        {"type": "ERROR", "message": "Not in PLAY phase."}
                    )
                    continue

                if len(state.s) == 4:
                    await websocket.send_json(
                        {
                            "type": "ERROR",
                            "message": "Trick is resolving. Wait for next turn.",
                        }
                    )
                    continue

                try:
                    apply_play_card(state, seat, card_id)
                    await send_state_current()

                    if len(state.s) == 4:
                        await asyncio.sleep(TRICK_DISPLAY_DELAY_SECONDS)
                        resolve_if_catch_complete(state)
                        await send_state_current()
                        await asyncio.sleep(EMPTY_TABLE_PAUSE_SECONDS)
                    else:
                        resolve_if_catch_complete(state)

                    await _advance_bots_until_human_any_phase(
                        state, pool, bot_sem, websocket, game_id, send_state_fn
                    )
                except ValueError as e:
                    await websocket.send_json({"type": "ERROR", "message": str(e)})
                    continue

                await send_state_current()
                continue

            await websocket.send_json(
                {"type": "ERROR", "message": f"Unknown message type: {msg_type}"}
            )

    except WebSocketDisconnect:
        return


@router.websocket("/ws/games/{game_id}")
async def ws_game(websocket: WebSocket, game_id: str) -> None:
    await websocket.accept()

    state = game_manager.get_game(game_id)
    if not state:
        await websocket.send_json({"type": "ERROR", "message": "Game not found"})
        await websocket.close()
        return

    await _run_ws_session(websocket, game_id=game_id, state=state, viewer_seat=None)


@router.websocket("/ws/rooms/{room_code}")
async def ws_room(websocket: WebSocket, room_code: str) -> None:
    await websocket.accept()

    spectator_query = websocket.query_params.get("spectator", "").strip().lower()
    is_spectator = spectator_query in {"1", "true", "yes", "on"}

    viewer_seat: int | None = None
    game_id: str | None = None
    can_act = not is_spectator

    if is_spectator:
        try:
            status = room_manager.get_room_status(room_code=room_code)
        except RoomNotFoundError:
            await websocket.send_json({"type": "ERROR", "message": "Room not found."})
            await websocket.close()
            return
        game_id = status.get("gameId")
    else:
        player_token = websocket.query_params.get("token", "").strip()
        if not player_token:
            await websocket.send_json({"type": "ERROR", "message": "Missing room token."})
            await websocket.close()
            return

        try:
            room, viewer_seat = room_manager.validate_player(
                room_code=room_code, player_token=player_token
            )
            game_id = room.game_id
        except RoomNotFoundError:
            await websocket.send_json({"type": "ERROR", "message": "Room not found."})
            await websocket.close()
            return
        except RoomTokenError:
            await websocket.send_json({"type": "ERROR", "message": "Invalid room token."})
            await websocket.close()
            return

    if game_id is None:
        await websocket.send_json(
            {"type": "ERROR", "message": "Waiting for second player to join room."}
        )
        await websocket.close()
        return

    state = game_manager.get_game(game_id)
    if not state:
        await websocket.send_json({"type": "ERROR", "message": "Game not found."})
        await websocket.close()
        return

    await _register_room_connection(room_code, websocket, viewer_seat, can_act)
    try:
        await _run_ws_session(
            websocket,
            game_id=game_id,
            state=state,
            viewer_seat=viewer_seat,
            can_act=can_act,
            broadcast_state=lambda current_state: _broadcast_room_state(
                room_code, current_state
            ),
        )
    finally:
        await _unregister_room_connection(room_code, websocket)
