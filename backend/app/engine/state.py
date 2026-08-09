from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Any, Final

from app.bots.bid_policy import BidPolicyConfig
from app.legacy.cards import Cards
from app.settings import settings


Phase = Literal[
    "BIDDING_R1",
    "TRUMP_SELECT_R1",
    "MANUAL_DEAL_REST",
    "BIDDING_R2",
    "TRUMP_SELECT_R2",
    "PLAY",
    "GAME_OVER",
]

# Suit knowledge matrix order (rows):
# Hearts, Diamonds, Spades, Clubs
SUIT_MATRIX_SUITS: Final[tuple[str, ...]] = (
    "Hearts",
    "Diamonds",
    "Spades",
    "Clubs",
)

SUIT_MATRIX_INDEX: Final[dict[str, int]] = {
    s: i for i, s in enumerate(SUIT_MATRIX_SUITS)
}


def _default_suit_matrix() -> list[list[int]]:
    # 4 suits x 4 seats, all initially possible
    return [[1, 1, 1, 1] for _ in range(4)]


def _default_trump_matrix() -> list[list[int]]:
    # 4 suits x 4 seats, all initially possible concealed-trump suits
    return [[1, 1, 1, 1] for _ in range(4)]


@dataclass
class GameState:
    game_id: str
    phase: Phase

    starting_bidder_index: int
    bidding_order: list[int]

    bidding_r1_step: int = 0
    bidding_r2_step: int = 0

    bidding_r1_bids_by_pos: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    bidding_r1_passes_by_pos: list[bool] = field(
        default_factory=lambda: [False, False, False, False]
    )
    bidding_r1_final_pos: int = 0

    bidding_r2_bids_by_pos: list[int] = field(default_factory=lambda: [0, 0, 0, 0])

    bids_r1_by_seat: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    bids_r2_by_seat: list[int] = field(default_factory=lambda: [0, 0, 0, 0])

    round1_bidder_seat: int | None = None
    round1_bid_value: int | None = None

    final_bidder_seat: int | None = None
    final_bid_value: int | None = None

    # Hands (shared lists)
    players_cards: list[list[Cards]] = field(default_factory=lambda: [[], [], [], []])
    draw_pile: list[Cards] = field(default_factory=list)

    # Concealed trump indicator card (removed from bidder hand)
    player_trump: Cards | None = None

    # Auto-deal mode flag (if True, skip MANUAL_DEAL_REST phase)
    auto_deal: bool = False
    # Deterministic fixed deck mode (cards loaded from file)
    fixed_deck_mode: bool = False

    # NEW: Suit void knowledge (persistent during PLAY; void stays void)
    # Rows: Hearts, Diamonds, Spades, Clubs; Cols: seat 0..3
    suit_matrix: list[list[int]] = field(default_factory=_default_suit_matrix)
    # Concealed trump-suit knowledge before reveal.
    # Rows: Hearts, Diamonds, Spades, Clubs; Cols: seat 0..3
    trump_matrix: list[list[int]] = field(default_factory=_default_trump_matrix)

    # --- PLAY STATE (initialized when entering PLAY) ---
    seat_types: list[str] = field(
        default_factory=lambda: ["bot", "human", "bot", "human"]
    )
    player_names: list[str] = field(
        default_factory=lambda: ["T-1000", "You", "Skynet", "Partner"]
    )

    # legacy expects:
    finalBid: int = 0  # 1-indexed bidder seat
    finalBidValue: int = 0

    trumpSuit: str | None = None
    trumpReveal: bool = False
    known: bool = False
    chose: bool = False

    leaderIndex: int = 0
    catchNumber: int = 1

    s: list[Cards] = field(default_factory=list)
    currentSuit: str = ""
    trumpPlayed: bool = False
    trumpIndice: list[int] = field(default_factory=lambda: [0, 0, 0, 0])

    team1Points: int = 0
    team2Points: int = 0
    team1Catches: list[list[Cards]] = field(default_factory=list)
    team2Catches: list[list[Cards]] = field(default_factory=list)

    play_players: list[dict[str, Any]] = field(default_factory=list)

    winnerTeam: int | None = None

    event_log: list[str] = field(default_factory=list)

    # Immutable per-game empirical bidding experiment selected by the host.
    bot_bidding_policy: BidPolicyConfig = field(default_factory=BidPolicyConfig.aggressive)

    # Self-play data-generation metadata. These fields are unused in normal
    # human/multiplayer games.
    self_play: bool = False
    self_play_result_logged: bool = False
    self_play_bidder_seat: int | None = None
    self_play_bidder_team: int | None = None
    self_play_first4_card_ids: list[str] = field(default_factory=list)
    self_play_canonical_key: list[list[str]] = field(default_factory=list)
    self_play_selected_trump_card_id: str | None = None

    @property
    def turn_index(self) -> int:
        if self.phase == "BIDDING_R1":
            return self.bidding_order[self.bidding_r1_step]
        if self.phase == "BIDDING_R2":
            return self.bidding_order[self.bidding_r2_step]
        if self.phase in ("TRUMP_SELECT_R1", "TRUMP_SELECT_R2"):
            return -1 if self.final_bidder_seat is None else self.final_bidder_seat
        if self.phase == "PLAY":
            return (self.leaderIndex + len(self.s)) % 4
        return -1

    def to_public_dict(self) -> dict:
        from app.engine.serializer import serialize_card
        from app.engine.cards_adapter import to_card_id

        trump_suit_visible = self.trumpSuit if self.trumpReveal else None
        # Only expose trump card ID when revealed
        trump_card_id_visible = (
            to_card_id(self.player_trump)
            if self.trumpReveal and self.player_trump is not None
            else None
        )

        suit_knowledge = {
            "Hearts": self.suit_matrix[0],
            "Diamonds": self.suit_matrix[1],
            "Spades": self.suit_matrix[2],
            "Clubs": self.suit_matrix[3],
        }
        trump_knowledge = {
            "Hearts": self.trump_matrix[0],
            "Diamonds": self.trump_matrix[1],
            "Spades": self.trump_matrix[2],
            "Clubs": self.trump_matrix[3],
        }

        return {
            "gameId": self.game_id,
            "phase": self.phase,
            "startingBidderIndex": self.starting_bidder_index,
            "turnIndex": self.turn_index,
            "biddingOrder": self.bidding_order,
            "seatTypes": self.seat_types,
            "playerNames": self.player_names,
            "players": [
                {
                    "seatIndex": i,
                    "cards": [serialize_card(c) for c in hand],
                    "cardCount": len(hand),
                    "team": 1 if i % 2 == 0 else 2,
                    "isBidder": self.final_bidder_seat == i,
                }
                for i, hand in enumerate(self.players_cards)
            ],
            "drawPileCount": len(self.draw_pile),
            "autoDeal": self.auto_deal,
            "fixedDeckMode": self.fixed_deck_mode,
            "botBiddingPolicy": self.bot_bidding_policy.to_public_dict(),
            "bidsR1": self.bids_r1_by_seat,
            "bidsR2": self.bids_r2_by_seat,
            "round1BidderSeat": self.round1_bidder_seat,
            "round1BidValue": self.round1_bid_value,
            "finalBidderSeat": self.final_bidder_seat,
            "finalBidValue": self.final_bid_value,
            "hasConcealedTrump": self.player_trump is not None,
            # Debug-friendly exposure of suit knowledge
            "suitKnowledge": suit_knowledge,
            "suitMatrix": self.suit_matrix,
            "trumpKnowledge": trump_knowledge,
            "trumpMatrix": self.trump_matrix,
            "play": {
                "leaderIndex": self.leaderIndex,
                "catchNumber": self.catchNumber,
                "currentSuit": self.currentSuit,
                "trumpReveal": self.trumpReveal,
                "trumpSuit": trump_suit_visible,
                "trumpCardId": trump_card_id_visible,
                "trickCards": [serialize_card(c) for c in self.s],
                "trumpIndice": self.trumpIndice,
                "team1Points": self.team1Points,
                "team2Points": self.team2Points,
                "winnerTeam": self.winnerTeam,
            },
            "eventLog": self.event_log,
            "selfPlay": {
                "enabled": self.self_play,
                "resultLogged": self.self_play_result_logged,
                "bidderSeat": self.self_play_bidder_seat,
                "bidderTeam": self.self_play_bidder_team,
                "first4CardIds": self.self_play_first4_card_ids,
                "canonicalKey": self.self_play_canonical_key,
                "selectedTrumpCardId": self.self_play_selected_trump_card_id,
            },
        }

    def to_public_dict_for_viewer(self, viewer_seat_index: int) -> dict:
        """
        Public state tailored for one connected human:
        - The viewer sees their own cards.
        - All other hands are hidden (only card counts preserved).
        """
        from app.engine.serializer import serialize_card

        data = self.to_public_dict()
        data["viewerSeatIndex"] = viewer_seat_index

        for p in data["players"]:
            if p["seatIndex"] == viewer_seat_index:
                continue

            if settings.debug:
                seat_index = p["seatIndex"]
                p["debugCards"] = [
                    serialize_card(c) for c in self.players_cards[seat_index]
                ]

            hidden_cards = [
                {
                    "cardId": f"HIDDEN_{p['seatIndex']}_{i}",
                    "suit": "Hidden",
                    "rank": "Hidden",
                    "points": 0,
                    "order": 0,
                    "label": "Hidden card",
                }
                for i in range(p["cardCount"])
            ]
            p["cards"] = hidden_cards

        return data
