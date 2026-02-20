import { useEffect, useRef, useState, useCallback } from "react";
import type { GameState, LegalActions, WsMessage } from "../api/types";
import { connectGameWs } from "../api/ws";
import { GameTable } from "../components/GameTable";
import { PlayerHand } from "../components/PlayerHand";
import { CenterPlayArea } from "../components/CenterPlayArea";
import {
  PLAYER_NAMES,
  SEAT_TYPES,
  TEAM_HUMANS,
  TEAM_BOTS,
} from "../config/constants";

type Props = {
  gameId: string;
  onGameEnd?: () => void;
};

export function GameRoomPage({ gameId, onGameEnd }: Props) {
  const wsRef = useRef<WebSocket | null>(null);

  const [state, setState] = useState<GameState | null>(null);
  const [legal, setLegal] = useState<LegalActions | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [_status, setStatus] = useState<"connecting" | "open" | "closed">("connecting");

  // UI state
  const [showDebug, setShowDebug] = useState(false);
  const [showBotCards, setShowBotCards] = useState(false);
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null);

  // Cumulative scores (persisted across games - in real app would use localStorage)
  const [cumulativeScores, _setCumulativeScores] = useState({ humans: 0, bots: 0 });

  // WebSocket connection
  useEffect(() => {
    setError(null);
    setStatus("connecting");
    setState(null);
    setLegal(null);

    const ws = connectGameWs(gameId);
    wsRef.current = ws;

    let gotState = false;
    let disposed = false;

    const stateTimeout = window.setTimeout(() => {
      if (!disposed && !gotState) {
        setError("Timed out waiting for game state.");
      }
    }, 5000);

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as WsMessage;

        if (msg.type === "STATE_UPDATE") {
          gotState = true;
          setState(msg.state);
          return;
        }

        if (msg.type === "LEGAL_ACTIONS") {
          setLegal(msg.actions);
          return;
        }

        if (msg.type === "ERROR") {
          setError(msg.message);
          return;
        }

        if (msg.type === "GAME_ABORTED") {
          setError(`Game aborted: ${msg.reason}`);
          setTimeout(() => onGameEnd?.(), 2000);
          return;
        }
      } catch {
        console.warn("Non-JSON WS message received");
      }
    };

    ws.onopen = () => {
      setStatus("open");
      ws.send(JSON.stringify({ type: "GET_STATE" }));
    };

    ws.onerror = () => {
      if (!disposed) {
        console.warn("WebSocket error");
      }
    };

    ws.onclose = () => {
      setStatus("closed");
    };

    return () => {
      disposed = true;
      window.clearTimeout(stateTimeout);
      if (wsRef.current === ws) {
        wsRef.current = null;
      }
      ws.close();
    };
  }, [gameId, onGameEnd]);

  // WebSocket send helper
  const sendWs = useCallback((payload: unknown) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.warn("WebSocket not connected");
      return;
    }
    ws.send(JSON.stringify(payload));
  }, []);

  // Actions
  const onSubmitBid = useCallback(
    (seatIndex: number, bidValue: number) => {
      sendWs({ type: "SUBMIT_BID", seatIndex, bidValue });
    },
    [sendWs]
  );

  const onSelectTrump = useCallback(
    (seatIndex: number, cardId: string) => {
      sendWs({ type: "SELECT_TRUMP_CARD", seatIndex, cardId });
      setSelectedCardId(null);
    },
    [sendWs]
  );

  const onRevealChoice = useCallback(
    (seatIndex: number, reveal: boolean) => {
      sendWs({ type: "CHOOSE_REVEAL_TRUMP", seatIndex, reveal });
    },
    [sendWs]
  );

  const onPlayCard = useCallback(
    (seatIndex: number, cardId: string) => {
      sendWs({ type: "PLAY_CARD", seatIndex, cardId });
      setSelectedCardId(null);
    },
    [sendWs]
  );

  // Loading/error states
  if (error) {
    return (
      <div className="h-screen felt-background flex items-center justify-center">
        <div className="bg-white rounded-xl p-8 shadow-2xl max-w-md text-center">
          <div className="text-red-600 text-xl font-bold mb-4">Error</div>
          <div className="text-gray-700 mb-6">{error}</div>
          <button
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            onClick={() => onGameEnd?.()}
          >
            Back to Setup
          </button>
        </div>
      </div>
    );
  }

  if (!state) {
    return (
      <div className="h-screen felt-background flex items-center justify-center">
        <div className="bg-white/90 rounded-xl p-8 shadow-2xl">
          <div className="flex items-center gap-4">
            <div className="animate-spin h-8 w-8 border-4 border-blue-600 border-t-transparent rounded-full" />
            <span className="text-lg">Connecting to game...</span>
          </div>
        </div>
      </div>
    );
  }

  // Extract relevant state data
  const { phase, turnIndex, finalBidderSeat, finalBidValue, play, players } = state;

  // Calculate team scores
  const humanPoints = play.team2Points; // Team 2 is humans (seats 1, 3)
  const botPoints = play.team1Points; // Team 1 is bots (seats 0, 2)

  // Get current bids for display
  const playerBids = state.bidsR1.map((b, i) => (b > 0 ? b : state.bidsR2[i] > 0 ? state.bidsR2[i] : null));

  // Determine if bots are "thinking" (it's their turn)
  const thinkingPlayerIndex = SEAT_TYPES[turnIndex] === "bot" ? turnIndex : null;

  // Get legal card IDs for the current player action (for any human player)
  const legalCardIds: string[] = [];
  // Only some legal action types have seatIndex
  const legalSeatIndex: number = legal && "seatIndex" in legal && typeof legal.seatIndex === "number" ? legal.seatIndex : -1;
  const isHumanTurn = legalSeatIndex >= 0 && SEAT_TYPES[legalSeatIndex] === "human";
  if (legal && isHumanTurn) {
    if (legal.type === "PLAY_CARD") {
      legalCardIds.push(...legal.cardIds);
    } else if (legal.type === "SELECT_TRUMP_R1" || legal.type === "SELECT_TRUMP_R2") {
      legalCardIds.push(...legal.cardIds);
    }
  }

  // Determine the team bid for display
  const humanBid =
    finalBidderSeat !== null && TEAM_HUMANS.includes(finalBidderSeat) ? finalBidValue : null;
  const botBid =
    finalBidderSeat !== null && TEAM_BOTS.includes(finalBidderSeat) ? finalBidValue : null;

  // Render player hands
  const renderPlayerHand = (seatIndex: number) => {
    const player = players[seatIndex];
    const isBot = SEAT_TYPES[seatIndex] === "bot";
    const isHuman = SEAT_TYPES[seatIndex] === "human";
    const faceUp = isHuman || (isBot && showBotCards);

    // For human players, enable card clicks if it's their turn
    const isThisPlayersTurn = legal && "seatIndex" in legal && legal.seatIndex === seatIndex;
    const canInteract =
      isHuman &&
      isThisPlayersTurn &&
      (legal.type === "PLAY_CARD" || legal.type === "SELECT_TRUMP_R1" || legal.type === "SELECT_TRUMP_R2");

    return (
      <PlayerHand
        cards={player.cards}
        faceUp={faceUp}
        isHorizontal={seatIndex === 1 || seatIndex === 3}
        isCompact={seatIndex !== 1}
        highlightedCardIds={canInteract ? legalCardIds : []}
        selectedCardId={selectedCardId}
        disabled={!canInteract}
        onCardClick={
          canInteract
            ? (cardId) => {
                if (legal.type === "PLAY_CARD") {
                  onPlayCard(seatIndex, cardId);
                } else if (legal.type === "SELECT_TRUMP_R1" || legal.type === "SELECT_TRUMP_R2") {
                  onSelectTrump(seatIndex, cardId);
                }
              }
            : undefined
        }
      />
    );
  };

  // Render center area content
  const renderCenterArea = () => {
    // During PLAY phase, show trick cards
    if (phase === "PLAY" && play.trickCards.length > 0) {
      return <CenterPlayArea trickCards={play.trickCards} leaderIndex={play.leaderIndex} />;
    }

    // During bidding, show bidding panel
    if (
      (phase === "BIDDING_R1" || phase === "BIDDING_R2") &&
      legal &&
      (legal.type === "BID_R1" || legal.type === "BID_R2") &&
      SEAT_TYPES[legal.seatIndex] === "human"
    ) {
      return (
        <BiddingPanelInline
          legal={legal}
          phase={phase}
          onSubmitBid={onSubmitBid}
        />
      );
    }

    // During REVEAL_CHOICE, show reveal options
    if (
      phase === "PLAY" &&
      legal &&
      legal.type === "REVEAL_CHOICE" &&
      SEAT_TYPES[legal.seatIndex] === "human" &&
      play.trickCards.length < 4
    ) {
      return (
        <RevealChoicePanel
          seatIndex={legal.seatIndex}
          onRevealChoice={onRevealChoice}
        />
      );
    }

    // Show phase info
    return (
      <div className="text-white/60 text-center">
        <div className="text-sm">{getPhaseDisplayText(phase)}</div>
        {thinkingPlayerIndex !== null && (
          <div className="mt-2 flex items-center justify-center gap-2">
            <span className="text-sm">{PLAYER_NAMES[thinkingPlayerIndex]} is thinking</span>
            <div className="flex gap-1">
              <span className="w-2 h-2 bg-white/60 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="w-2 h-2 bg-white/60 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
              <span className="w-2 h-2 bg-white/60 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
            </div>
          </div>
        )}
      </div>
    );
  };

  // Render game over overlay
  const renderOverlay = () => {
    if (phase === "GAME_OVER" && play.winnerTeam !== null) {
      const humanWon = play.winnerTeam === 2;
      return (
        <div className="modal-overlay">
          <div className="modal-content">
            <h2 className={`text-3xl font-bold mb-4 ${humanWon ? "text-blue-600" : "text-red-600"}`}>
              {humanWon ? "You Win!" : "Bots Win!"}
            </h2>
            <div className="text-gray-600 mb-6">
              <div>Final Score: Humans {humanPoints} - Bots {botPoints}</div>
              <div className="text-sm mt-2">Bid: {finalBidValue}</div>
            </div>
            <div className="flex gap-4 justify-center">
              <button
                className="px-6 py-3 bg-green-600 text-white rounded-lg font-semibold hover:bg-green-700"
                onClick={() => onGameEnd?.()}
              >
                New Game
              </button>
            </div>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="h-screen game-table-container">
      {/* Debug toggle */}
      <div className="debug-toggle">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={showBotCards}
            onChange={(e) => setShowBotCards(e.target.checked)}
          />
          <span>Show Bot Cards</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer ml-4">
          <input
            type="checkbox"
            checked={showDebug}
            onChange={(e) => setShowDebug(e.target.checked)}
          />
          <span>Debug</span>
        </label>
      </div>

      <GameTable
        humanScore={cumulativeScores.humans}
        botScore={cumulativeScores.bots}
        humanBid={humanBid}
        botBid={botBid}
        trumpRevealed={play.trumpReveal}
        trumpSuit={play.trumpSuit}
        completedTricks={play.catchNumber}
        activePlayerIndex={turnIndex}
        bidderIndex={finalBidderSeat}
        thinkingPlayerIndex={thinkingPlayerIndex}
        playerBids={playerBids}
        bottomPlayer={renderPlayerHand(1)}
        topPlayer={renderPlayerHand(3)}
        leftPlayer={renderPlayerHand(2)}
        rightPlayer={renderPlayerHand(0)}
        centerArea={renderCenterArea()}
        overlay={renderOverlay()}
      />

      {/* Debug panel */}
      {showDebug && (
        <div className="fixed bottom-4 left-4 right-4 max-h-[40vh] overflow-auto bg-black/80 text-white text-xs p-4 rounded-lg">
          <div className="font-bold mb-2">Debug Info</div>
          <div>Phase: {phase}</div>
          <div>Turn: {turnIndex} ({PLAYER_NAMES[turnIndex]})</div>
          <div>Legal: {legal?.type}</div>
          <div className="mt-2">Event Log:</div>
          <ul className="list-disc pl-4">
            {state.eventLog.slice(-10).map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// Helper function to get phase display text
function getPhaseDisplayText(phase: string): string {
  const phaseTexts: Record<string, string> = {
    BIDDING_R1: "Round 1 Bidding",
    TRUMP_SELECT_R1: "Selecting Trump Card",
    MANUAL_DEAL_REST: "Dealing Remaining Cards",
    BIDDING_R2: "Round 2 Bidding",
    TRUMP_SELECT_R2: "Selecting New Trump",
    PLAY: "Playing",
    GAME_OVER: "Game Over",
  };
  return phaseTexts[phase] || phase;
}

// Inline bidding panel component
function BiddingPanelInline({
  legal,
  phase,
  onSubmitBid,
}: {
  legal: { type: "BID_R1" | "BID_R2"; seatIndex: number; minBidExclusive: number; maxBidInclusive: number; canPass: boolean; canRedeal?: boolean };
  phase: string;
  onSubmitBid: (seatIndex: number, bidValue: number) => void;
}) {
  const { seatIndex, minBidExclusive, maxBidInclusive, canPass, canRedeal } = legal;

  // Generate valid bid values
  const bidOptions: number[] = [];
  for (let b = minBidExclusive + 1; b <= maxBidInclusive; b++) {
    bidOptions.push(b);
  }

  const playerName = PLAYER_NAMES[seatIndex];

  return (
    <div className="bg-white/95 rounded-xl p-6 shadow-xl max-w-md">
      <div className="text-center mb-4">
        <div className="text-lg font-bold text-gray-800">
          {phase === "BIDDING_R1" ? "Round 1 Bidding" : "Round 2 Bidding"}
        </div>
        <div className="text-sm text-gray-600">{playerName}'s turn to bid</div>
      </div>

      <div className="flex flex-wrap gap-2 justify-center mb-4">
        {bidOptions.map((bid) => (
          <button
            key={bid}
            className="bid-button primary"
            onClick={() => onSubmitBid(seatIndex, bid)}
          >
            {bid}
          </button>
        ))}
      </div>

      <div className="flex gap-2 justify-center">
        {canPass && (
          <button
            className="bid-button pass px-4"
            onClick={() => onSubmitBid(seatIndex, 0)}
          >
            Pass
          </button>
        )}
        {canRedeal && (
          <button
            className="bid-button redeal px-4"
            onClick={() => onSubmitBid(seatIndex, -1)}
          >
            Redeal
          </button>
        )}
      </div>
    </div>
  );
}

// Reveal choice panel
function RevealChoicePanel({
  seatIndex,
  onRevealChoice,
}: {
  seatIndex: number;
  onRevealChoice: (seatIndex: number, reveal: boolean) => void;
}) {
  const playerName = PLAYER_NAMES[seatIndex];

  return (
    <div className="bg-white/95 rounded-xl p-6 shadow-xl">
      <div className="text-center mb-4">
        <div className="text-lg font-bold text-gray-800">Reveal Trump?</div>
        <div className="text-sm text-gray-600">
          {playerName} can reveal the trump suit now or keep it hidden
        </div>
      </div>

      <div className="flex gap-4 justify-center">
        <button
          className="px-6 py-3 bg-purple-600 text-white rounded-lg font-semibold hover:bg-purple-700"
          onClick={() => onRevealChoice(seatIndex, true)}
        >
          Reveal Trump
        </button>
        <button
          className="px-6 py-3 bg-gray-600 text-white rounded-lg font-semibold hover:bg-gray-700"
          onClick={() => onRevealChoice(seatIndex, false)}
        >
          Keep Hidden
        </button>
      </div>
    </div>
  );
}

export default GameRoomPage;
