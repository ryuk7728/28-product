/**
 * Game Constants - All configuration values for the 28 Card Game UI
 */

// =============================================================================
// CARD DIMENSIONS
// =============================================================================

export const CARD_WIDTH = 90;
export const CARD_HEIGHT = 126;
export const CARD_WIDTH_SMALL = 70;
export const CARD_HEIGHT_SMALL = 98;

// Card overlap (negative margin for fan effect)
export const CARD_OVERLAP_HORIZONTAL = 35; // How much cards overlap horizontally
export const CARD_OVERLAP_VERTICAL = 40;   // How much cards overlap vertically
export const CARD_OVERLAP_SMALL_H = 25;
export const CARD_OVERLAP_SMALL_V = 30;

// =============================================================================
// PLAYER CONFIGURATION
// =============================================================================

export const PLAYER_NAMES: Record<number, string> = {
  0: "T-1000",   // Bot (East/right)
  1: "You",      // Human (South/bottom) - Main player
  2: "Skynet",   // Bot (West/left)
  3: "Partner",  // Human (North/top)
};

// Direction mapping for CSS classes
export const PLAYER_DIRECTIONS: Record<number, "south" | "north" | "east" | "west"> = {
  0: "east",   // Bot T-1000 (right side)
  1: "south",  // Human You (bottom)
  2: "west",   // Bot Skynet (left side)
  3: "north",  // Human Partner (top)
};

// Seat types
export const SEAT_TYPES = ["bot", "human", "bot", "human"] as const;

// Team configuration
export const TEAM_HUMANS = [1, 3]; // Seat indices for human team
export const TEAM_BOTS = [0, 2];   // Seat indices for bot team

// =============================================================================
// LAYOUT CONFIGURATION
// =============================================================================

// Whether each seat uses horizontal (true) or vertical (false) card layout
export const SEAT_HORIZONTAL: Record<number, boolean> = {
  0: false,  // East - vertical
  1: true,   // South - horizontal
  2: false,  // West - vertical
  3: true,   // North - horizontal
};

// =============================================================================
// TIMING CONSTANTS (milliseconds)
// =============================================================================

export const TRICK_DISPLAY_DELAY_MS = 3000;     // Time to show completed trick (3 seconds)
export const TRUMP_REVEAL_DISPLAY_MS = 5000;    // Time to show revealed trump (5 seconds)
export const DEAL_CARD_DELAY_MS = 80;           // Delay between dealing each card
export const BOT_THINKING_DELAY_MS = 500;       // Fake thinking time for bots
export const CARD_ANIMATION_DURATION_MS = 300;  // Duration of card movement

// =============================================================================
// CARD SUITS AND RANKS
// =============================================================================

export const SUIT_SYMBOLS: Record<string, string> = {
  Hearts: "♥",
  Diamonds: "♦",
  Clubs: "♣",
  Spades: "♠",
};

export const SUIT_COLORS: Record<string, string> = {
  Hearts: "#dc2626",
  Diamonds: "#dc2626",
  Clubs: "#1f2937",
  Spades: "#1f2937",
};

export const RANK_DISPLAY: Record<string, string> = {
  Jack: "J",
  Nine: "9",
  Ace: "A",
  Ten: "10",
  King: "K",
  Queen: "Q",
  Eight: "8",
  Seven: "7",
};

// All valid ranks in 28 game order (high to low)
export const RANKS_ORDERED = ["Jack", "Nine", "Ace", "Ten", "King", "Queen", "Eight", "Seven"];

// All valid suits
export const SUITS = ["Hearts", "Diamonds", "Clubs", "Spades"];

// =============================================================================
// SCORING RULES
// =============================================================================

export const SCORING_RULES = {
  LOW_BID_MAX: 19,
  MID_BID_MAX: 24,
  LOW_BID_WIN: 1,
  LOW_BID_LOSE: -2,
  MID_BID_WIN: 2,
  MID_BID_LOSE: -3,
  HIGH_BID_WIN: 3,
  HIGH_BID_LOSE: -4,
} as const;

// Calculate game points based on bid value and whether team won
export function calculateGamePoints(bidValue: number, didWin: boolean): number {
  if (bidValue <= SCORING_RULES.LOW_BID_MAX) {
    return didWin ? SCORING_RULES.LOW_BID_WIN : SCORING_RULES.LOW_BID_LOSE;
  } else if (bidValue <= SCORING_RULES.MID_BID_MAX) {
    return didWin ? SCORING_RULES.MID_BID_WIN : SCORING_RULES.MID_BID_LOSE;
  } else {
    return didWin ? SCORING_RULES.HIGH_BID_WIN : SCORING_RULES.HIGH_BID_LOSE;
  }
}

// =============================================================================
// GAME PHASES (for reference)
// =============================================================================

export const GAME_PHASES = {
  BIDDING_R1: "BIDDING_R1",
  TRUMP_SELECT_R1: "TRUMP_SELECT_R1",
  MANUAL_DEAL_REST: "MANUAL_DEAL_REST",
  BIDDING_R2: "BIDDING_R2",
  TRUMP_SELECT_R2: "TRUMP_SELECT_R2",
  PLAY: "PLAY",
  GAME_OVER: "GAME_OVER",
} as const;

export const PHASE_DISPLAY_TEXT: Record<string, string> = {
  BIDDING_R1: "Round 1 Bidding",
  TRUMP_SELECT_R1: "Selecting Trump Card",
  MANUAL_DEAL_REST: "Dealing Remaining Cards",
  BIDDING_R2: "Round 2 Bidding",
  TRUMP_SELECT_R2: "Selecting Trump Card",
  PLAY: "Playing",
  GAME_OVER: "Game Over",
};
