from __future__ import annotations

from app.engine.bidding_engine import compute_r1_turn_rules, compute_r2_turn_rules
from app.engine.cards_adapter import to_card_id
from app.engine.play_engine import compute_play_legal_actions
from app.engine.state import GameState


def get_legal_actions(state: GameState) -> dict:
    if state.phase == "BIDDING_R1":
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
        return {
            "type": "BID_R1",
            "seatIndex": rules.seat_index,
            "minBidExclusive": rules.min_bid_exclusive,
            "maxBidInclusive": rules.max_bid_inclusive,
            "canPass": rules.can_pass,
            "canRedeal": rules.can_redeal,
        }

    if state.phase == "TRUMP_SELECT_R1":
        seat = state.final_bidder_seat
        return {
            "type": "SELECT_TRUMP_R1",
            "seatIndex": seat,
            "cardIds": [to_card_id(c) for c in state.players_cards[seat]],
        }

    if state.phase == "MANUAL_DEAL_REST":
        return {
            "type": "MANUAL_DEAL_REST",
            "remainingCardIds": [to_card_id(c) for c in state.draw_pile],
            "neededPerSeat": 4,
        }

    if state.phase == "BIDDING_R2":
        rules = compute_r2_turn_rules(
            bidding_order=state.bidding_order,
            step=state.bidding_r2_step,
            bids_so_far_by_pos=state.bidding_r2_bids_by_pos,
        )
        return {
            "type": "BID_R2",
            "seatIndex": rules.seat_index,
            "minBidExclusive": rules.min_bid_exclusive,
            "maxBidInclusive": rules.max_bid_inclusive,
            "canPass": True,
        }

    if state.phase == "TRUMP_SELECT_R2":
        seat = state.final_bidder_seat
        return {
            "type": "SELECT_TRUMP_R2",
            "seatIndex": seat,
            "cardIds": [to_card_id(c) for c in state.players_cards[seat]],
        }

    if state.phase == "PLAY":
        # During trick persistence window (4 cards visible), suppress actions.
        # This prevents transient REVEAL/PLAY prompts before catch resolution.
        if len(state.s) == 4:
            return {"type": "NO_ACTION", "seatIndex": state.turn_index}

        legal = compute_play_legal_actions(state)
        if legal.type == "REVEAL_CHOICE":
            return {
                "type": "REVEAL_CHOICE",
                "seatIndex": legal.seatIndex,
                "options": legal.options,
            }
        if legal.type == "PLAY_CARD":
            return {"type": "PLAY_CARD", "seatIndex": legal.seatIndex, "cardIds": legal.cardIds}
        return {"type": "NO_ACTION", "seatIndex": legal.seatIndex}

    if state.phase == "GAME_OVER":
        return {"type": "GAME_OVER"}

    return {"type": "NO_ACTION"}
