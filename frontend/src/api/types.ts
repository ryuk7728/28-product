export type Card = {
  cardId: string;
  suit: string;
  rank: string;
  points: number;
  order: number;
  label: string;
};

export type BidPolicyMode = "aggressive" | "optimal" | "custom";

export type BidThresholds = {
  opening15: number;
  opening16: number;
  laterBid: number;
  jumpTo16: number;
};

export type BidPolicy = {
  mode: BidPolicyMode;
  positionAware: boolean;
  thresholds?: BidThresholds;
};

export type KPolicyMode = "regular" | "aggressive";

export type KPolicy = {
  mode: KPolicyMode;
  kByCatch: number[];
};

export type GameState = {
  gameId: string;
  viewerSeatIndex?: number;
  playerNames?: string[];
  phase: string;
  startingBidderIndex: number;
  turnIndex: number;
  biddingOrder: number[];
  seatTypes: string[];
  players: Array<{
    seatIndex: number;
    cards: Card[];
    debugCards?: Card[];
    cardCount: number;
    team: number;
    isBidder: boolean;
  }>;
  drawPileCount: number;
  autoDeal: boolean;
  botBiddingPolicy?: BidPolicy & { thresholds: BidThresholds };
  botKPolicy?: KPolicy;
  botThinkTimeSeconds?: number | null;
  botThinking?: {
    seatIndex: number;
    startedAtEpochMs: number;
    deadlineEpochMs: number;
  } | null;
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
  selfPlay?: {
    enabled: boolean;
    resultLogged: boolean;
    bidderSeat: number | null;
    bidderTeam: number | null;
    first4CardIds: string[];
    canonicalKey: string[][];
    selectedTrumpCardId: string | null;
  };
};

export type RoomJoinResponse = {
  roomCode: string;
  gameId: string | null;
  seatIndex: number;
  seatName: string;
  playerToken: string;
  waitingForPlayer: boolean;
  playersJoined: number;
  targetHumanCount: number;
  seats: RoomSeat[];
};

export type RoomSeat = {
  seatIndex: number;
  team: 1 | 2;
  type: "human" | "bot";
  name: string;
  joined: boolean;
};

export type RoomStatusResponse = {
  roomCode: string;
  gameId: string | null;
  seatIndex: number | null;
  seatName?: string | null;
  waitingForPlayer: boolean;
  playersJoined: number;
  targetHumanCount: number;
  seats: RoomSeat[];
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
  | { type: "GAME_ABORTED"; reason: string }
  | RematchStatusMessage;

export type RematchStatusMessage = {
  type: "REMATCH_STATUS";
  status: "waiting" | "started";
  requestedBySeatIndex: number;
  readySeatIndices: number[];
  waitingForSeatIndices: number[];
  startingBidderIndex: number | null;
};
