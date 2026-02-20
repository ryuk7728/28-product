from __future__ import annotations

import random
import uuid

from app.engine.cards_adapter import from_card_id
from app.engine.fixed_deck import load_fixed_deck_cards
from app.engine.state import GameState
from app.engine.validator import validate_first4_hands
from app.settings import settings
from app.legacy.cards import Cards


class GameManager:
    def __init__(self) -> None:
        self._games: dict[str, GameState] = {}

    def create_game_auto_deal(
        self,
        *,
        starting_bidder_index: int,
    ) -> GameState:
        """
        Create a new game with automatic card distribution.
        Shuffles the deck, deals 4 cards to each player, stores remaining 16 in draw pile.
        """
        if starting_bidder_index < 0 or starting_bidder_index > 3:
            raise ValueError("startingBidderIndex must be in 0..3")

        fixed_mode = settings.fixed_deck_enabled
        if fixed_mode:
            seat_hands = load_fixed_deck_cards(settings.fixed_deck_path)
            players_cards = [hand[:4] for hand in seat_hands]
            # Keep seat order so auto_deal_rest can append exact remaining 4 per seat.
            remaining = (
                seat_hands[0][4:8]
                + seat_hands[1][4:8]
                + seat_hands[2][4:8]
                + seat_hands[3][4:8]
            )
        else:
            deck = Cards.packOf28()  # 32 cards
            random.shuffle(deck)

            # Deal first 4 cards to each player
            players_cards = [
                deck[0:4],
                deck[4:8],
                deck[8:12],
                deck[12:16],
            ]
            remaining = deck[16:32]

        bidding_order = [(starting_bidder_index + i) % 4 for i in range(4)]

        game_id = str(uuid.uuid4())
        state = GameState(
            game_id=game_id,
            phase="BIDDING_R1",
            starting_bidder_index=starting_bidder_index,
            bidding_order=bidding_order,
            players_cards=[list(h) for h in players_cards],
            draw_pile=list(remaining),
            auto_deal=True,  # Flag to indicate auto-deal mode
            fixed_deck_mode=fixed_mode,
            event_log=[
                "Game created (auto-deal)."
                if not fixed_mode
                else "Game created (auto-deal, fixed deck mode).",
                f"Starting bidder: P{starting_bidder_index + 1}",
            ],
        )

        self._games[game_id] = state
        return state

    def auto_deal_rest(self, state: GameState) -> None:
        """
        Automatically distribute the remaining 16 cards (4 to each player).
        Used when auto_deal mode is enabled.
        """
        if len(state.draw_pile) != 16:
            raise ValueError(f"Expected 16 cards in draw pile, got {len(state.draw_pile)}")

        # Shuffle only in normal mode. In fixed deck mode draw_pile is seat-ordered.
        if not state.fixed_deck_mode:
            random.shuffle(state.draw_pile)

        # Deal 4 cards to each player
        for seat in range(4):
            for _ in range(4):
                card = state.draw_pile.pop(0)
                state.players_cards[seat].append(card)

        state.event_log.append(
            "Auto-deal: remaining 16 cards distributed."
            if not state.fixed_deck_mode
            else "Auto-deal: remaining 16 cards distributed from fixed deck."
        )

    def create_game_manual_first4(
        self,
        *,
        starting_bidder_index: int,
        first4_hands: list[list[str]],
    ) -> GameState:
        if starting_bidder_index < 0 or starting_bidder_index > 3:
            raise ValueError("startingBidderIndex must be in 0..3")

        validate_first4_hands(first4_hands)

        players_cards = [[from_card_id(cid) for cid in hand] for hand in first4_hands]

        used_identities = {c.identity() for hand in players_cards for c in hand}
        full_deck = Cards.packOf28()  # 32 cards
        remaining = [c for c in full_deck if c.identity() not in used_identities]
        random.shuffle(remaining)

        bidding_order = [(starting_bidder_index + i) % 4 for i in range(4)]

        game_id = str(uuid.uuid4())
        state = GameState(
            game_id=game_id,
            phase="BIDDING_R1",
            starting_bidder_index=starting_bidder_index,
            bidding_order=bidding_order,
            players_cards=players_cards,
            draw_pile=remaining,
            fixed_deck_mode=False,
            event_log=[
                "Game created (manual first-4).",
                f"Starting bidder: P{starting_bidder_index + 1}",
            ],
        )

        self._games[game_id] = state
        return state

    def get_game(self, game_id: str) -> GameState | None:
        return self._games.get(game_id)

    def delete_game(self, game_id: str) -> None:
        self._games.pop(game_id, None)

    def redeal_first4_in_place(self, state: GameState) -> None:
        """
        In-place redeal (same gameId):
          - shuffle a fresh 32-card deck
          - deal 4 cards each (16 total)
          - set draw_pile to the remaining 16
          - reset bidding state to BIDDING_R1 step 0
          - clear any previously chosen concealed trump etc.
        """
        if state.fixed_deck_mode:
            seat_hands = load_fixed_deck_cards(settings.fixed_deck_path)
            new_players = [hand[:4] for hand in seat_hands]
            new_draw = (
                seat_hands[0][4:8]
                + seat_hands[1][4:8]
                + seat_hands[2][4:8]
                + seat_hands[3][4:8]
            )
        else:
            deck = Cards.packOf28()
            random.shuffle(deck)

            new_players = [deck[0:4], deck[4:8], deck[8:12], deck[12:16]]
            new_draw = deck[16:32]

        state.players_cards = [list(h) for h in new_players]
        state.draw_pile = list(new_draw)

        # Reset bidding (R1)
        state.phase = "BIDDING_R1"
        state.bidding_r1_step = 0
        state.bidding_r1_bids_by_pos = [0, 0, 0, 0]
        state.bidding_r1_passes_by_pos = [False, False, False, False]
        state.bidding_r1_final_pos = 0
        state.bids_r1_by_seat = [0, 0, 0, 0]

        # Reset bidding (R2)
        state.bidding_r2_step = 0
        state.bidding_r2_bids_by_pos = [0, 0, 0, 0]
        state.bids_r2_by_seat = [0, 0, 0, 0]

        # Reset bidder / trump selection artifacts
        state.round1_bidder_seat = None
        state.round1_bid_value = None
        state.final_bidder_seat = None
        state.final_bid_value = None
        state.player_trump = None

        # Reset any play state (safety)
        state.finalBid = 0
        state.finalBidValue = 0
        state.trumpSuit = None
        state.trumpReveal = False
        state.known = False
        state.chose = False
        state.leaderIndex = state.starting_bidder_index
        state.catchNumber = 1
        state.s = []
        state.currentSuit = ""
        state.trumpPlayed = False
        state.trumpIndice = [0, 0, 0, 0]
        state.team1Points = 0
        state.team2Points = 0
        state.team1Catches = []
        state.team2Catches = []
        state.play_players = []
        state.winnerTeam = None

        state.event_log.append(
            "Redeal performed (first-4 re-dealt)."
            if not state.fixed_deck_mode
            else "Redeal performed from fixed deck file (first-4 re-dealt)."
        )


game_manager = GameManager()
