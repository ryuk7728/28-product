from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.engine.cards_adapter import to_card_id
from app.settings import settings


RESULTS_PATH = settings.backend_dir / "data" / "self_play_results.jsonl"


def _canonical_key_text(groups: list[list[str]]) -> str:
    return json.dumps(groups, separators=(",", ":"))


def build_self_play_result_row(state) -> dict[str, Any]:
    bidder_seat = state.self_play_bidder_seat
    bidder_team = state.self_play_bidder_team
    if bidder_seat is None or bidder_team is None:
        raise ValueError("self-play bidder metadata is missing")

    team1_points = int(state.team1Points)
    team2_points = int(state.team2Points)
    bidder_team_points = team1_points if bidder_team == 1 else team2_points

    players_card_ids = [
        [to_card_id(c) for c in state.players_cards[seat]] for seat in range(4)
    ]

    return {
        "gameId": state.game_id,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "bidderSeat": bidder_seat,
        "bidderTeam": bidder_team,
        "startingBidderIndex": state.starting_bidder_index,
        "first4CardIds": state.self_play_first4_card_ids,
        "canonicalKey": state.self_play_canonical_key,
        "canonicalKeyText": _canonical_key_text(state.self_play_canonical_key),
        "selectedTrumpCardId": state.self_play_selected_trump_card_id,
        "selectedTrumpSuit": state.trumpSuit,
        "team1Points": team1_points,
        "team2Points": team2_points,
        "bidderTeamPoints": bidder_team_points,
        "winnerTeam": state.winnerTeam,
        "playersCardIdsAtEnd": players_card_ids,
        "eventLog": list(state.event_log),
    }


def append_self_play_result(state, path: Path = RESULTS_PATH) -> dict[str, Any] | None:
    """
    Append one JSONL row for a completed self-play game.

    Aborted/redeal games are intentionally skipped for this milestone.
    """
    if not state.self_play:
        return None
    if state.self_play_result_logged:
        return None
    if state.phase != "GAME_OVER":
        return None
    if state.winnerTeam == -1:
        return None

    row = build_self_play_result_row(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")

    state.self_play_result_logged = True
    state.event_log.append(f"Self-play result stored: {path.as_posix()}")
    return row
