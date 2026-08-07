from __future__ import annotations

from app.engine.cards_adapter import from_card_id
from app.engine.play_engine import (
    apply_play_card,
    apply_reveal_choice,
    init_play_state,
    resolve_if_catch_complete,
)
from app.engine.state import GameState
from app.legacy import minimax as legacy_minimax


def _players(card_ids_by_seat: list[list[str]]) -> list[dict]:
    return [
        {
            "cards": [from_card_id(card_id) for card_id in card_ids],
            "isTrump": seat == 3,
            "team": 1 if seat % 2 == 0 else 2,
        }
        for seat, card_ids in enumerate(card_ids_by_seat)
    ]


def test_reveal_activates_all_matching_cards_and_undo_restores_state() -> None:
    trick = [
        from_card_id("Clubs_Seven"),
        from_card_id("Hearts_Ace"),
        from_card_id("Clubs_Jack"),
    ]
    players = _players([[], [], [], []])
    indicator = from_card_id("Clubs_Ace")
    trump_indice = [0, 0, 0, 0]
    original_trick = [card.identity() for card in trick]
    original_players = [[card.identity() for card in p["cards"]] for p in players]

    (
        current_suit,
        _trick,
        trump_reveal,
        chose,
        player_trump,
        trump_played,
        returned_trump_indice,
        _players_after,
        _trump_suit,
        _final_bid,
        undo,
    ) = legacy_minimax.result(
        trick,
        True,
        "Clubs",
        False,
        False,
        indicator,
        False,
        trump_indice,
        players,
        "Clubs",
        4,
        0,
    )

    assert trump_reveal is True
    assert chose is True
    assert trump_played is True
    assert returned_trump_indice is trump_indice
    assert trump_indice == [1, 0, 1, 0]

    (
        current_suit,
        trump_reveal,
        chose,
        player_trump,
        trump_played,
        returned_trump_indice,
    ) = legacy_minimax.undo_result(
        trick,
        undo,
        current_suit,
        trump_reveal,
        chose,
        player_trump,
        trump_played,
        trump_indice,
        players,
    )

    assert current_suit == "Clubs"
    assert trump_reveal is False
    assert chose is False
    assert player_trump is indicator
    assert trump_played is False
    assert returned_trump_indice is trump_indice
    assert trump_indice == [0, 0, 0, 0]
    assert [card.identity() for card in trick] == original_trick
    assert [[card.identity() for card in p["cards"]] for p in players] == original_players


def test_reveal_without_prior_matching_card_does_not_set_trump_played() -> None:
    trick = [from_card_id("Hearts_Seven"), from_card_id("Diamonds_Ace")]
    players = _players([[], [], [], []])
    trump_indice = [0, 0, 0, 0]

    result = legacy_minimax.result(
        trick,
        True,
        "Hearts",
        False,
        False,
        from_card_id("Clubs_Ace"),
        False,
        trump_indice,
        players,
        "Clubs",
        4,
        1,
    )

    assert result[5] is False
    assert result[6] == [0, 0, 0, 0]


def test_declining_reveal_does_not_activate_prior_matching_card() -> None:
    trick = [from_card_id("Hearts_Seven"), from_card_id("Clubs_Jack")]
    players = _players([[], [], [], []])
    trump_indice = [0, 0, 0, 0]

    result = legacy_minimax.result(
        trick,
        False,
        "Hearts",
        False,
        False,
        from_card_id("Clubs_Ace"),
        False,
        trump_indice,
        players,
        "Clubs",
        4,
        1,
    )

    assert result[2] is False
    assert result[5] is False
    assert result[6] == [0, 0, 0, 0]


def test_authoritative_play_counts_stronger_pre_reveal_trump() -> None:
    state = GameState(
        game_id="retroactive-trump",
        phase="PLAY",
        starting_bidder_index=0,
        bidding_order=[0, 1, 2, 3],
        players_cards=[
            [from_card_id("Hearts_Seven")],
            [from_card_id("Clubs_Jack")],
            [from_card_id("Clubs_Seven")],
            [from_card_id("Hearts_Jack")],
        ],
        draw_pile=[],
        event_log=[],
    )
    state.final_bidder_seat = 0
    state.final_bid_value = 14
    state.player_trump = from_card_id("Clubs_Ace")
    init_play_state(state)

    apply_play_card(state, seat_index=0, card_id="Hearts_Seven")
    apply_reveal_choice(state, seat_index=1, reveal=False)
    apply_play_card(state, seat_index=1, card_id="Clubs_Jack")

    apply_reveal_choice(state, seat_index=2, reveal=True)
    assert state.trumpPlayed is True
    assert state.trumpIndice == [0, 1, 0, 0]

    apply_play_card(state, seat_index=2, card_id="Clubs_Seven")
    apply_play_card(state, seat_index=3, card_id="Hearts_Jack")
    assert state.trumpIndice == [0, 1, 1, 0]

    winner, _points = legacy_minimax.checkwin_extended(
        state.s,
        state.trumpPlayed,
        state.s,
        state.trumpIndice,
        state.leaderIndex,
        state.play_players,
        state.currentSuit,
    )
    assert winner == 1

    resolve_if_catch_complete(state)
    assert state.team1Points == 0
    assert state.team2Points == 6
    assert state.leaderIndex == 1
