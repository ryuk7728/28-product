export type Card = {
  cardId: string;
  suit: string;
  rank: string;
  points: number;
  order: number;
  label: string;
};

export type GameState = {
  gameId: string;
  phase: string;
  startingBidderIndex: number;
  turnIndex: number;
  biddingOrder: number[];
  seatTypes: string[];
  players: Array<{
    seatIndex: number;
    cards: Card[];
    cardCount: number;
    team: number;
    isBidder: boolean;
  }>;
  drawPileCount: number;
  autoDeal: boolean;
  bidsR1: number[];
  bidsR2: number[];
  round1BidderSeat: number | null;
  round1BidValue: number | null;
  finalBidderSeat: number | null;
  finalBidValue: number | null;
  hasConcealedTrump: boolean;
  play: {
    leaderIndex: number;
    catchNumber: number;
    currentSuit: string;
    trumpReveal: boolean;
    trumpSuit: string | null;
    trumpCardId: string | null;
    trickCards: Card[];
    trumpIndice: number[];
    team1Points: number;
    team2Points: number;
    winnerTeam: number | null;
  };
  eventLog: string[];
};

export type LegalActions =
  | {
      type: "BID_R1";
      seatIndex: number;
      minBidExclusive: number;
      maxBidInclusive: number;
      canPass: boolean;
      canRedeal: boolean;
    }
  | { type: "SELECT_TRUMP_R1"; seatIndex: number; cardIds: string[] }
  | {
      type: "MANUAL_DEAL_REST";
      remainingCardIds: string[];
      neededPerSeat: number;
    }
  | {
      type: "BID_R2";
      seatIndex: number;
      minBidExclusive: number;
      maxBidInclusive: number;
      canPass: boolean;
    }
  | { type: "SELECT_TRUMP_R2"; seatIndex: number; cardIds: string[] }
  | { type: "REVEAL_CHOICE"; seatIndex: number; options: boolean[] }
  | { type: "PLAY_CARD"; seatIndex: number; cardIds: string[] }
  | { type: "GAME_OVER" }
  | { type: "NO_ACTION"; seatIndex?: number };

export type WsMessage =
  | { type: "STATE_UPDATE"; state: GameState }
  | { type: "LEGAL_ACTIONS"; actions: LegalActions }
  | { type: "ERROR"; message: string }
  | { type: "GAME_ABORTED"; reason: string };