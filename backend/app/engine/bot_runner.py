from __future__ import annotations

import asyncio
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Callable, Any

from app.bots.rollout_bot import choose_action_with_rollouts_parallel
from app.engine.play_engine import (
    apply_play_card,
    apply_reveal_choice,
    compute_play_legal_actions,
    resolve_if_catch_complete,
)
from app.settings import settings

# Delay to display completed trick (4 cards visible)
TRICK_DISPLAY_DELAY_SECONDS = 3
# Pause duration for empty table between tricks
EMPTY_TABLE_PAUSE_SECONDS = 1

BOT_SEATS = {0, 2}


async def advance_bots_until_human(
    state,
    pool: ProcessPoolExecutor,
    bot_sem,
    websocket: Any,
    send_state_fn: Callable,
    bot_seats: set[int] | None = None,
) -> None:
    """
    Runs bot turns (seats 0 and 2) until current actor is human (1 or 3) or game ends.
    Uses multiprocessing rollouts to decide bot actions.

    When a bot completes a trick (4 cards), sends state to frontend and waits
    before clearing, so the completed trick is visible for 5 seconds.
    """
    active_bot_seats = BOT_SEATS if bot_seats is None else bot_seats

    while state.phase == "PLAY":
        actor = (state.leaderIndex + len(state.s)) % 4
        if actor not in active_bot_seats:
            return

        legal = compute_play_legal_actions(state)
        if (
            legal.type == "NO_ACTION"
            and getattr(state, "self_play", False)
            and state.player_trump is not None
            and actor == state.finalBid - 1
            and not state.trumpReveal
            and len(state.play_players[actor]["cards"]) == 0
        ):
            apply_reveal_choice(state, actor, True)
            continue

        # Limit concurrent bot computations globally
        async with bot_sem:
            timeout_seconds = getattr(state, "bot_think_timeout_seconds", None)
            if timeout_seconds is None:
                timeout_seconds = max(0.0, float(settings.bot_think_timeout_seconds))
            deadline_epoch_ms = (
                int((time.time() + timeout_seconds) * 1000)
                if timeout_seconds > 0
                else None
            )
            state.bot_thinking = (
                {
                    "seatIndex": actor,
                    "startedAtEpochMs": int(time.time() * 1000),
                    "deadlineEpochMs": deadline_epoch_ms,
                }
                if deadline_epoch_ms is not None
                else None
            )
            if state.bot_thinking is not None:
                await send_state_fn(websocket, state)
            try:
                action_type, payload = await choose_action_with_rollouts_parallel(
                    state,
                    actor,
                    pool,
                    timeout_seconds=timeout_seconds,
                    deadline_epoch_ms=deadline_epoch_ms,
                )
            finally:
                state.bot_thinking = None

        if action_type == "REVEAL":
            apply_reveal_choice(state, payload["seatIndex"], bool(payload["reveal"]))
        else:
            apply_play_card(state, payload["seatIndex"], str(payload["cardId"]))

        # If trick is complete (4 cards), send state to frontend and wait
        # before clearing, so the completed trick is visible
        if len(state.s) == 4:
            await send_state_fn(websocket, state)
            await asyncio.sleep(TRICK_DISPLAY_DELAY_SECONDS)
            # Clear the trick and send empty state for smooth transition
            resolve_if_catch_complete(state)
            await send_state_fn(websocket, state)
            await asyncio.sleep(EMPTY_TABLE_PAUSE_SECONDS)
        else:
            resolve_if_catch_complete(state)
