from __future__ import annotations

import json

from app.engine.game_manager import GameManager
from app.engine.self_play_results import append_self_play_result


def test_create_self_play_game_enters_play_with_metadata() -> None:
    manager = GameManager()

    state = manager.create_self_play_game()

    assert state.self_play is True
    assert state.phase == "PLAY"
    assert state.seat_types == ["bot", "bot", "bot", "bot"]
    assert state.final_bidder_seat in {0, 1, 2, 3}
    assert state.final_bid_value == 0
    assert state.player_trump is not None
    assert len(state.self_play_first4_card_ids) == 4
    assert state.self_play_canonical_key
    assert state.self_play_selected_trump_card_id is not None


def test_append_self_play_result_writes_one_jsonl_row(tmp_path) -> None:
    manager = GameManager()
    state = manager.create_self_play_game()
    path = tmp_path / "self_play_results.jsonl"

    state.phase = "GAME_OVER"
    state.team1Points = 16
    state.team2Points = 12
    state.winnerTeam = 1

    row = append_self_play_result(state, path=path)
    second = append_self_play_result(state, path=path)

    assert row is not None
    assert second is None
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    payload = json.loads(lines[0])
    assert payload["gameId"] == state.game_id
    assert payload["canonicalKey"] == state.self_play_canonical_key
    assert payload["bidderTeamPoints"] in {12, 16}
