import type { ReactNode } from "react";
import { PLAYER_NAMES, PLAYER_DIRECTIONS, SEAT_TYPES } from "../config/constants";

interface PlayerPositionProps {
  seatIndex: number;
  isActive?: boolean;
  isBidder?: boolean;
  currentBid?: number | null;
  isThinking?: boolean;
  children?: ReactNode;
}

// Explicit position styles to ensure correct placement
const POSITION_STYLES: Record<string, React.CSSProperties> = {
  bottom: { position: "absolute", bottom: "20px", left: "50%", transform: "translateX(-50%)", zIndex: 20 },
  top: { position: "absolute", top: "20px", left: "50%", transform: "translateX(-50%)" },
  left: { position: "absolute", left: "20px", top: "50%", transform: "translateY(-50%)" },
  right: { position: "absolute", right: "20px", top: "50%", transform: "translateY(-50%)" },
};

function PlayerPosition({
  seatIndex,
  isActive = false,
  isBidder = false,
  currentBid,
  isThinking = false,
  children,
}: PlayerPositionProps) {
  const position = PLAYER_DIRECTIONS[seatIndex];
  const name = PLAYER_NAMES[seatIndex];
  const isBot = SEAT_TYPES[seatIndex] === "bot";

  return (
    <div
      className={`player-position ${position} ${isActive ? "player-active" : ""}`}
      data-seat={seatIndex}
      style={POSITION_STYLES[position]}
    >
      {/* Player name tag */}
      <div className={`player-name-tag ${isBot ? "bot" : "human"}`}>
        <span>{name}</span>
        {isBidder && <span className="ml-2 text-xs opacity-80">(Bidder)</span>}
      </div>

      {/* Current bid display */}
      {currentBid !== undefined && currentBid !== null && (
        <div className="text-white text-sm font-semibold bg-black/50 px-2 py-1 rounded">
          Bid: {currentBid}
        </div>
      )}

      {/* Thinking indicator for bots */}
      {isThinking && isBot && (
        <div className="thinking-indicator">
          <span>Thinking</span>
          <span className="dot"></span>
          <span className="dot"></span>
          <span className="dot"></span>
        </div>
      )}

      {/* Card hand area - rendered by parent */}
      {children}
    </div>
  );
}

interface ScoreTableProps {
  humanScore: number;
  botScore: number;
  humanBid: number | null;
  botBid: number | null;
}

function ScoreTable({ humanScore, botScore, humanBid, botBid }: ScoreTableProps) {
  return (
    <table className="score-table">
      <thead>
        <tr>
          <th>Team</th>
          <th>Score</th>
          <th>Bid</th>
        </tr>
      </thead>
      <tbody>
        <tr className="team-human">
          <td className="font-semibold text-blue-600">Humans</td>
          <td className="font-bold text-lg">{humanScore}</td>
          <td>{humanBid !== null ? humanBid : "-"}</td>
        </tr>
        <tr className="team-bot">
          <td className="font-semibold text-red-600">Bots</td>
          <td className="font-bold text-lg">{botScore}</td>
          <td>{botBid !== null ? botBid : "-"}</td>
        </tr>
      </tbody>
    </table>
  );
}

interface TrumpIndicatorProps {
  revealed: boolean;
  suit: string | null;
}

function TrumpIndicator({ revealed, suit }: TrumpIndicatorProps) {
  const getSuitSymbol = (s: string): string => {
    const symbols: Record<string, string> = {
      Hearts: "♥",
      Diamonds: "♦",
      Clubs: "♣",
      Spades: "♠",
    };
    return symbols[s] || "?";
  };

  const getSuitColorClass = (s: string): string => {
    if (s === "Hearts" || s === "Diamonds") return "hearts";
    return "spades";
  };

  return (
    <div className="trump-indicator">
      <span className="text-sm font-semibold text-gray-700">Trump:</span>
      {revealed && suit ? (
        <span className={`suit-icon ${getSuitColorClass(suit)}`}>{getSuitSymbol(suit)}</span>
      ) : (
        <span className="suit-icon text-gray-400">?</span>
      )}
    </div>
  );
}

interface DiscardPileProps {
  trickCount: number;
}

function DiscardPile({ trickCount }: DiscardPileProps) {
  return (
    <div className="discard-pile">
      {/* Stack of card backs representing completed tricks */}
      {Array.from({ length: Math.min(trickCount, 8) }).map((_, i) => (
        <div
          key={i}
          className="stacked-card card-back"
          style={{
            width: "60px",
            height: "84px",
            transform: `translateY(${i * -2}px) rotate(${(i % 2 === 0 ? 1 : -1) * 2}deg)`,
            zIndex: i,
          }}
        />
      ))}
      {trickCount > 0 && (
        <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 text-white text-xs bg-black/50 px-2 py-0.5 rounded">
          {trickCount} {trickCount === 1 ? "trick" : "tricks"}
        </div>
      )}
    </div>
  );
}

interface PlayAreaProps {
  children?: ReactNode;
}

function PlayArea({ children }: PlayAreaProps) {
  return <div className="play-area">{children}</div>;
}

interface GameTableProps {
  // Score data
  humanScore?: number;
  botScore?: number;
  humanBid?: number | null;
  botBid?: number | null;

  // Trump data
  trumpRevealed?: boolean;
  trumpSuit?: string | null;

  // Discard pile
  completedTricks?: number;

  // Active player
  activePlayerIndex?: number;

  // Bidder
  bidderIndex?: number | null;

  // Thinking state
  thinkingPlayerIndex?: number | null;

  // Player current bids (for display during bidding)
  playerBids?: (number | null)[];

  // Children for each position
  bottomPlayer?: ReactNode;
  topPlayer?: ReactNode;
  leftPlayer?: ReactNode;
  rightPlayer?: ReactNode;
  centerArea?: ReactNode;

  // Additional overlay content (modals, etc.)
  overlay?: ReactNode;
}

export function GameTable({
  humanScore = 0,
  botScore = 0,
  humanBid = null,
  botBid = null,
  trumpRevealed = false,
  trumpSuit = null,
  completedTricks = 0,
  activePlayerIndex,
  bidderIndex = null,
  thinkingPlayerIndex = null,
  playerBids = [null, null, null, null],
  bottomPlayer,
  topPlayer,
  leftPlayer,
  rightPlayer,
  centerArea,
  overlay,
}: GameTableProps) {
  return (
    <div className="felt-background w-full h-full relative" style={{ minHeight: "100vh" }}>
      {/* Top-right info panel */}
      <div className="absolute top-4 right-4 z-10 flex flex-col gap-3">
        <ScoreTable
          humanScore={humanScore}
          botScore={botScore}
          humanBid={humanBid}
          botBid={botBid}
        />
        <TrumpIndicator revealed={trumpRevealed} suit={trumpSuit} />
        {completedTricks > 0 && <DiscardPile trickCount={completedTricks} />}
      </div>

      {/* Player positions */}
      {/* Bottom - P1 (Human "You") */}
      <PlayerPosition
        seatIndex={1}
        isActive={activePlayerIndex === 1}
        isBidder={bidderIndex === 1}
        currentBid={playerBids[1]}
        isThinking={thinkingPlayerIndex === 1}
      >
        {bottomPlayer}
      </PlayerPosition>

      {/* Top - P3 (Human "Partner") */}
      <PlayerPosition
        seatIndex={3}
        isActive={activePlayerIndex === 3}
        isBidder={bidderIndex === 3}
        currentBid={playerBids[3]}
        isThinking={thinkingPlayerIndex === 3}
      >
        {topPlayer}
      </PlayerPosition>

      {/* Left - P2 (Bot "Skynet") */}
      <PlayerPosition
        seatIndex={2}
        isActive={activePlayerIndex === 2}
        isBidder={bidderIndex === 2}
        currentBid={playerBids[2]}
        isThinking={thinkingPlayerIndex === 2}
      >
        {leftPlayer}
      </PlayerPosition>

      {/* Right - P0 (Bot "T-1000") */}
      <PlayerPosition
        seatIndex={0}
        isActive={activePlayerIndex === 0}
        isBidder={bidderIndex === 0}
        currentBid={playerBids[0]}
        isThinking={thinkingPlayerIndex === 0}
      >
        {rightPlayer}
      </PlayerPosition>

      {/* Center play area */}
      <PlayArea>{centerArea}</PlayArea>

      {/* Overlay content (modals, game over, etc.) */}
      {overlay}
    </div>
  );
}

export default GameTable;
