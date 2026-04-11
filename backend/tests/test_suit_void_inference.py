from app.engine.cards_adapter import from_card_id
from app.engine.play_engine import (
    apply_play_card,
    apply_reveal_choice,
    init_play_state,
)
from app.engine.state import GameState, SUIT_MATRIX_INDEX


def _make_min_play_state() -> GameState:
    """
    Create a minimal but valid GameState that can be used with legacy actions/result.
    We keep hands small; legacy logic is fine with that for these tests.
    """
    state = GameState(
        game_id="test",
        phase="PLAY",
        starting_bidder_index=0,
        bidding_order=[0, 1, 2, 3],
        players_cards=[
            [from_card_id("Clubs_Ace")],  # P1
            [
                from_card_id("Clubs_Seven"),
                from_card_id("Diamonds_Seven"),
            ],  # P2 (no Hearts)
            [from_card_id("Spades_Ace")],  # P3 (bidder)
            [from_card_id("Diamonds_Ace")],  # P4
        ],
        draw_pile=[],
        event_log=[],
    )
    state.final_bidder_seat = 2
    state.final_bid_value = 14

    # Provide a concealed trump indicator so trumpSuit isn't None.
    # (Not required for the test logic, but keeps legacy paths realistic.)
    state.player_trump = from_card_id("Spades_Jack")

    init_play_state(state)
    return state


def test_void_inference_sets_matrix_when_player_fails_to_follow() -> None:
    state = _make_min_play_state()

    # Simulate: trick already started, lead suit is Hearts, and it's P2's turn.
    state.leaderIndex = 0
    state.s = [from_card_id("Hearts_Ace")]
    state.currentSuit = "Hearts"
    state.trumpReveal = False
    state.chose = False

    before = [row[:] for row in state.suit_matrix]

    # Because P2 cannot follow Hearts and trump isn't revealed and chose==False,
    # legacy will require a REVEAL_CHOICE before allowing a card play.
    apply_reveal_choice(state, seat_index=1, reveal=False)

    # Now P2 is allowed to play any card; play a non-Hearts card.
    apply_play_card(state, seat_index=1, card_id="Clubs_Seven")

    hearts_row = SUIT_MATRIX_INDEX["Hearts"]
    assert state.suit_matrix[hearts_row][1] == 0

    # No other entries should change
    for r in range(4):
        for c in range(4):
            if r == hearts_row and c == 1:
                continue
            assert state.suit_matrix[r][c] == before[r][c]


def test_leader_play_does_not_mark_void() -> None:
    state = _make_min_play_state()

    # Make P2 the leader of a new trick
    state.leaderIndex = 1
    state.s = []
    state.currentSuit = ""
    state.trumpReveal = False
    state.chose = False

    before = [row[:] for row in state.suit_matrix]

    # Leader can play any card; this must NOT infer void.
    apply_play_card(state, seat_index=1, card_id="Clubs_Seven")

    assert state.suit_matrix == before


def _make_trump_inference_state(*, starting_bidder_index: int = 2) -> GameState:
    state = GameState(
        game_id="test-trump",
        phase="PLAY",
        starting_bidder_index=starting_bidder_index,
        bidding_order=[0, 1, 2, 3],
        players_cards=[
            [from_card_id("Clubs_Seven")],
            [from_card_id("Hearts_Ace")],
            [
                from_card_id("Spades_Ace"),
                from_card_id("Diamonds_Ace"),
            ],
            [from_card_id("Clubs_Ace")],
        ],
        draw_pile=[],
        event_log=[],
    )
    state.final_bidder_seat = 2
    state.final_bid_value = 14
    state.player_trump = from_card_id("Clubs_Jack")
    init_play_state(state)
    return state


def test_bidder_lead_marks_spade_impossible_for_concealed_trump() -> None:
    state = _make_trump_inference_state(starting_bidder_index=2)

    apply_play_card(state, seat_index=2, card_id="Spades_Ace")

    spades_row = SUIT_MATRIX_INDEX["Spades"]
    assert state.trump_matrix[spades_row][2] == 0


def test_non_bidder_lead_does_not_mark_concealed_trump_matrix() -> None:
    state = _make_trump_inference_state(starting_bidder_index=1)
    before = [row[:] for row in state.trump_matrix]

    apply_play_card(state, seat_index=1, card_id="Hearts_Ace")

    assert state.trump_matrix == before



