from __future__ import annotations

import copy
from dataclasses import dataclass

from app.engine.cards_adapter import from_card_id, to_card_id
from app.engine.state import SUIT_MATRIX_INDEX
from app.legacy.cards import Cards
from app.legacy import minimax as legacy_minimax


@dataclass
class PlayLegalActions:
    type: str
    seatIndex: int
    options: list[bool] | None = None
    cardIds: list[str] | None = None


def current_actor_index(leader_index: int, s_len: int) -> int:
    return (leader_index + s_len) % 4


def _infer_void_if_failed_follow(
    state,
    *,
    seat_index: int,
    pre_trick_len: int,
    led_suit: str,
    played_suit: str,
) -> None:
    """
    Permanent inference:
    If a non-leader fails to follow the led suit, then that seat is void in that
    suit for the rest of the game (hand only shrinks).
    """
    if pre_trick_len <= 0:
        return
    if not led_suit:
        return
    if played_suit == led_suit:
        return

    row = SUIT_MATRIX_INDEX.get(led_suit)
    if row is None:
        return

    if state.suit_matrix[row][seat_index] != 0:
        state.suit_matrix[row][seat_index] = 0
        state.event_log.append(f"Inferred: P{seat_index+1} is void in {led_suit}.")


def _infer_bidder_non_trump_lead(
    state,
    *,
    seat_index: int,
    pre_trick_len: int,
    played_suit: str,
) -> None:
    """
    Pre-reveal concealed-trump inference:
    if the bidder leads a trick with a non-trump suit, that led suit cannot be the
    concealed trump suit. We only apply this on trick lead, for the bidder, before
    reveal. If the bidder was forced to lead actual trump, we skip the inference.
    """
    if pre_trick_len != 0:
        return
    if state.trumpReveal:
        return
    if state.final_bidder_seat is None or seat_index != state.final_bidder_seat:
        return
    if not state.trumpSuit:
        return
    if played_suit == state.trumpSuit:
        return

    row = SUIT_MATRIX_INDEX.get(played_suit)
    if row is None:
        return

    if state.trump_matrix[row][seat_index] != 0:
        state.trump_matrix[row][seat_index] = 0
        state.event_log.append(
            f"Inferred: P{seat_index+1}'s concealed trump is not {played_suit}."
        )


def init_play_state(state) -> None:
    if state.final_bidder_seat is None or state.final_bid_value is None:
        raise RuntimeError("final bidder not set; cannot init play state")

    bidder = state.final_bidder_seat

    state.finalBid = bidder + 1  # legacy expects 1-indexed
    state.finalBidValue = int(state.final_bid_value)

    state.trumpReveal = False
    state.known = False
    state.chose = False

    state.s = []
    state.currentSuit = ""
    state.trumpPlayed = False
    state.trumpIndice = [0, 0, 0, 0]

    state.catchNumber = 1
    state.team1Points = 0
    state.team2Points = 0
    state.team1Catches = []
    state.team2Catches = []

    state.leaderIndex = state.starting_bidder_index

    state.trumpSuit = state.player_trump.suit if state.player_trump else None

    # Reset suit knowledge at start of PLAY
    state.suit_matrix = [[1, 1, 1, 1] for _ in range(4)]
    state.trump_matrix = [[1, 1, 1, 1] for _ in range(4)]

    state.play_players = []
    for i in range(4):
        state.play_players.append(
            {
                "cards": state.players_cards[i],  # share list objects
                "isTrump": i == bidder,
                "team": 1 if i % 2 == 0 else 2,
                "trump": state.player_trump if i == bidder else None,
            }
        )

    state.event_log.append("Play initialized.")
    state.event_log.append(
        f"Leader for catch 1: P{state.leaderIndex + 1} (starting bidder)."
    )


def safe_legacy_actions(state) -> list[bool] | list[str]:
    """
    legacy_minimax.actions() can mutate players in some branches.
    We call it on deep copies and return safe action descriptors:
    - [False, True] (reveal decision)
    - list of card identity strings for playable cards
    """
    players_copy = copy.deepcopy(state.play_players)
    trump_indice_copy = copy.deepcopy(state.trumpIndice)
    s_copy = copy.deepcopy(state.s)

    acts = legacy_minimax.actions(
        s_copy,
        players_copy,
        state.trumpReveal,
        state.trumpSuit,
        state.currentSuit,
        state.chose,
        state.finalBid,
        state.player_trump,
        state.trumpPlayed,
        trump_indice_copy,
        -1,
        state.leaderIndex,
    )

    if not acts:
        return []

    if isinstance(acts[0], bool):
        return [bool(x) for x in acts]

    return [a.identity() for a in acts]


def compute_play_legal_actions(state) -> PlayLegalActions:
    seat = current_actor_index(state.leaderIndex, len(state.s))

    acts = safe_legacy_actions(state)
    if not acts:
        return PlayLegalActions(type="NO_ACTION", seatIndex=seat)

    if isinstance(acts[0], bool):
        return PlayLegalActions(
            type="REVEAL_CHOICE",
            seatIndex=seat,
            options=[bool(x) for x in acts],
        )

    # Map identity strings -> cardIds
    card_ids: list[str] = []
    for ident in acts:
        found = None
        for c in state.play_players[seat]["cards"]:
            if c.identity() == ident:
                found = c
                break

        if found is None and state.player_trump is not None:
            if state.player_trump.identity() == ident:
                found = state.player_trump

        if found is not None:
            card_ids.append(to_card_id(found))

    return PlayLegalActions(type="PLAY_CARD", seatIndex=seat, cardIds=card_ids)


def apply_reveal_choice(state, seat_index: int, reveal: bool) -> None:
    actor = current_actor_index(state.leaderIndex, len(state.s))
    if seat_index != actor:
        raise ValueError("Not your turn.")

    (
        state.currentSuit,
        state.s,
        state.trumpReveal,
        state.chose,
        state.player_trump,
        state.trumpPlayed,
        state.trumpIndice,
        state.play_players,
        state.trumpSuit,
        state.finalBid,
        _undo,
    ) = legacy_minimax.result(
        state.s,
        bool(reveal),
        state.currentSuit,
        state.trumpReveal,
        state.chose,
        state.player_trump,
        state.trumpPlayed,
        state.trumpIndice,
        state.play_players,
        state.trumpSuit,
        state.finalBid,
        state.leaderIndex,
    )

    if reveal:
        state.known = True
        state.event_log.append(f"P{seat_index+1} revealed trump.")
    else:
        state.event_log.append(f"P{seat_index+1} chose not to reveal trump.")


def _find_card_object_for_play(state, seat_index: int, card_id: str) -> Cards:
    desired = from_card_id(card_id)

    for c in state.play_players[seat_index]["cards"]:
        if c.identity() == desired.identity():
            return c

    if (
        state.player_trump is not None
        and state.player_trump.identity() == desired.identity()
    ):
        return state.player_trump

    raise ValueError("Card not found to play.")


def apply_play_card(state, seat_index: int, card_id: str) -> None:
    actor = current_actor_index(state.leaderIndex, len(state.s))
    if seat_index != actor:
        raise ValueError("Not your turn.")

    legal = compute_play_legal_actions(state)
    if legal.type != "PLAY_CARD" or not legal.cardIds:
        raise ValueError("Not expecting a card play right now.")
    if card_id not in legal.cardIds:
        raise ValueError("Illegal card.")

    pre_trick_len = len(state.s)
    led_suit = state.currentSuit

    card_obj = _find_card_object_for_play(state, seat_index, card_id)

    (
        state.currentSuit,
        state.s,
        state.trumpReveal,
        state.chose,
        state.player_trump,
        state.trumpPlayed,
        state.trumpIndice,
        state.play_players,
        state.trumpSuit,
        state.finalBid,
        _undo,
    ) = legacy_minimax.result(
        state.s,
        card_obj,
        state.currentSuit,
        state.trumpReveal,
        state.chose,
        state.player_trump,
        state.trumpPlayed,
        state.trumpIndice,
        state.play_players,
        state.trumpSuit,
        state.finalBid,
        state.leaderIndex,
    )

    _infer_void_if_failed_follow(
        state,
        seat_index=seat_index,
        pre_trick_len=pre_trick_len,
        led_suit=led_suit,
        played_suit=card_obj.suit,
    )
    _infer_bidder_non_trump_lead(
        state,
        seat_index=seat_index,
        pre_trick_len=pre_trick_len,
        played_suit=card_obj.suit,
    )

    state.event_log.append(f"P{seat_index+1} played {card_obj.identity()}.")


def resolve_if_catch_complete(state) -> None:
    if len(state.s) != 4:
        return

    winner_index, signed_points = legacy_minimax.checkwin_extended(
        state.s,
        state.trumpPlayed,
        state.s,
        state.trumpIndice,
        state.leaderIndex,
        state.play_players,
        state.currentSuit,
    )

    points = abs(signed_points)
    winner_team = state.play_players[winner_index]["team"]

    if winner_team == 1:
        state.team1Points += points
        state.team1Catches.append(list(state.s))
    else:
        state.team2Points += points
        state.team2Catches.append(list(state.s))

    state.event_log.append(
        f"Catch {state.catchNumber} won by P{winner_index+1} "
        f"(Team {winner_team}) for {points} points."
    )

    (
        state.currentSuit,
        state.s,
        state.trumpPlayed,
        state.trumpIndice,
        state.chose,
    ) = legacy_minimax.reset(
        state.currentSuit,
        state.s,
        state.trumpPlayed,
        state.trumpIndice,
        state.chose,
    )

    state.leaderIndex = winner_index
    state.catchNumber += 1

    if state.catchNumber >= 9:
        bidder_team = state.play_players[state.finalBid - 1]["team"]
        bidding_points = state.team1Points if bidder_team == 1 else state.team2Points

        if bidding_points >= state.finalBidValue:
            state.winnerTeam = bidder_team
            state.event_log.append(
                f"GAME OVER: Team {bidder_team} wins "
                f"({bidding_points} >= {state.finalBidValue})."
            )
        else:
            other_team = 2 if bidder_team == 1 else 1
            state.winnerTeam = other_team
            state.event_log.append(
                f"GAME OVER: Team {other_team} wins "
                f"({bidding_points} < {state.finalBidValue})."
            )

        state.phase = "GAME_OVER"
