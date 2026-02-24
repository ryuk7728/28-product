/**
 * GamePage - Main game page with full WebSocket integration
 *
 * This is the production game page that:
 * - Connects to the backend via WebSocket
 * - Handles all game phases (bidding, trump select, play)
 * - Renders the new UI components
 */

import React, { useState, useCallback, useMemo, useEffect, useRef } from "react";
import { GameArena } from "../components/table";
import { PlayerHand } from "../components/player";
import { TrickArea } from "../components/trick";
import type { TrickCard } from "../components/trick";
import {
  BiddingPanel,
  TrumpSelectPanel,
  RevealTrumpPanel,
  ScorePanel,
  TrumpIndicator,
  TricksCounter,
  GameOverModal,
  PhaseIndicator,
  TrumpRevealOverlay,
  type PlayedCardInfo,
} from "../components/panels";
import { useGameWebSocket } from "../hooks/useGameWebSocket";
import type { Card as CardType } from "../api/types";
import { PLAYER_NAMES, BOT_BID_BUBBLE_DELAY_MS } from "../config/constants";
import "../styles/index.scss";

// Human seats (You = 1, Partner = 3)
const HUMAN_SEATS = new Set([1, 3]);
const BOT_SEATS = new Set([0, 2]);

export interface GamePageProps {
  gameId: string;
  onGameEnd?: () => void;
}

export const GamePage: React.FC<GamePageProps> = ({ gameId, onGameEnd }) => {

  // Local UI state
  const [showBotCards, setShowBotCards] = useState(false);
  const [selectedCard, setSelectedCard] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [abortReason, setAbortReason] = useState<string | null>(null);
  const [botBidBubble, setBotBidBubble] = useState<{
    seatIndex: number;
    text: string;
  } | null>(null);
  const [isBotBidDelayActive, setIsBotBidDelayActive] = useState(false);
  const botBidDelayTimerRef = useRef<number | null>(null);
  const processedBotBidEventIndexRef = useRef<number>(-1);

  // Trump reveal overlay state
  const [showTrumpRevealOverlay, setShowTrumpRevealOverlay] = useState(false);
  const [prevTrumpRevealed, setPrevTrumpRevealed] = useState(false);
  const [revealedTrumpInfo, setRevealedTrumpInfo] = useState<{ suit: string; cardId?: string } | null>(null);

  // WebSocket connection
  const {
    connected,
    gameState,
    legalActions,
    sendBid,
    sendTrumpSelect,
    sendPlayCard,
    sendRevealChoice,
  } = useGameWebSocket({
    gameId: gameId || "",
    onError: (msg) => {
      setErrorMessage(msg);
      setTimeout(() => setErrorMessage(null), 3000);
    },
    onGameAborted: (reason) => {
      setAbortReason(reason);
    },
  });

  // Derived state
  const phase = gameState?.phase || "";
  const turnIndex = gameState?.turnIndex ?? -1;
  const finalBidderSeat = gameState?.finalBidderSeat;
  const finalBidValue = gameState?.finalBidValue;

  // Check if it's a human's turn
  const isHumanTurn = HUMAN_SEATS.has(turnIndex);

  // Get current player's cards
  const getPlayerCards = useCallback(
    (seatIndex: number): CardType[] => {
      return gameState?.players[seatIndex]?.cards || [];
    },
    [gameState]
  );

  // Build trick cards from game state
  // Backend now handles the 5-second delay before clearing completed tricks,
  // so we can simply use the trickCards directly from the state
  const trickCards: TrickCard[] = useMemo(() => {
    if (!gameState?.play?.trickCards) {
      return [];
    }

    const leaderIndex = gameState.play.leaderIndex;
    return gameState.play.trickCards.map((card, idx) => ({
      cardId: card.cardId,
      seatIndex: (leaderIndex + idx) % 4,
      isWinning: false,
    }));
  }, [gameState?.play?.trickCards, gameState?.play?.leaderIndex]);

  // Detect trump reveal transition
  useEffect(() => {
    const currentTrumpRevealed = gameState?.play?.trumpReveal || false;
    const trumpSuit = gameState?.play?.trumpSuit;
    const trumpCardId = gameState?.play?.trumpCardId;

    // If trump just got revealed (was hidden, now revealed)
    if (currentTrumpRevealed && !prevTrumpRevealed && trumpSuit) {
      setRevealedTrumpInfo({ suit: trumpSuit, cardId: trumpCardId || undefined });
      setShowTrumpRevealOverlay(true);
    }

    setPrevTrumpRevealed(currentTrumpRevealed);
  }, [gameState?.play?.trumpReveal, gameState?.play?.trumpSuit, gameState?.play?.trumpCardId, prevTrumpRevealed]);

  // Show bot bid/pass speech bubble and delay human bidding panel for natural pacing.
  useEffect(() => {
    if (!gameState || !legalActions) return;

    const isBiddingPhase = phase === "BIDDING_R1" || phase === "BIDDING_R2";
    const isHumanBidTurn =
      isBiddingPhase &&
      (legalActions.type === "BID_R1" || legalActions.type === "BID_R2") &&
      HUMAN_SEATS.has(legalActions.seatIndex);

    if (!isHumanBidTurn) {
      return;
    }

    const logs = gameState.eventLog || [];
    const lastIndex = logs.length - 1;
    if (lastIndex < 0 || processedBotBidEventIndexRef.current === lastIndex) {
      return;
    }

    const lastLog = logs[lastIndex];
    const m = lastLog.match(/^P([1-4])\s+(bid\s+(\d+)|passed(?:\s+\(R2\))?)\.$/i);
    if (!m) return;

    const seatIndex = Number(m[1]) - 1;
    if (!BOT_SEATS.has(seatIndex)) return;

    const bidAmount = m[3];
    const bubbleText = bidAmount ? `Bid ${bidAmount}` : "Pass";

    processedBotBidEventIndexRef.current = lastIndex;
    setBotBidBubble({ seatIndex, text: bubbleText });
    setIsBotBidDelayActive(true);

    if (botBidDelayTimerRef.current !== null) {
      window.clearTimeout(botBidDelayTimerRef.current);
    }
    botBidDelayTimerRef.current = window.setTimeout(() => {
      setIsBotBidDelayActive(false);
      setBotBidBubble(null);
      botBidDelayTimerRef.current = null;
    }, BOT_BID_BUBBLE_DELAY_MS);
  }, [gameState, legalActions, phase]);

  useEffect(() => {
    return () => {
      if (botBidDelayTimerRef.current !== null) {
        window.clearTimeout(botBidDelayTimerRef.current);
      }
    };
  }, []);

  // Handle bid submission
  const handleBid = useCallback(
    (value: number) => {
      if (
        !isBotBidDelayActive &&
        (legalActions?.type === "BID_R1" || legalActions?.type === "BID_R2")
      ) {
        sendBid(legalActions.seatIndex, value);
      }
    },
    [isBotBidDelayActive, legalActions, sendBid]
  );

  // Handle pass (bid 0)
  const handlePass = useCallback(() => {
    if (
      !isBotBidDelayActive &&
      (legalActions?.type === "BID_R1" || legalActions?.type === "BID_R2")
    ) {
      sendBid(legalActions.seatIndex, 0);
    }
  }, [isBotBidDelayActive, legalActions, sendBid]);

  // Handle redeal (bid -1)
  const handleRedeal = useCallback(() => {
    if (
      !isBotBidDelayActive &&
      legalActions?.type === "BID_R1" &&
      legalActions.canRedeal
    ) {
      sendBid(legalActions.seatIndex, -1);
    }
  }, [isBotBidDelayActive, legalActions, sendBid]);

  // Handle trump card selection
  const handleTrumpSelect = useCallback(
    (cardId: string) => {
      if (
        legalActions?.type === "SELECT_TRUMP_R1" ||
        legalActions?.type === "SELECT_TRUMP_R2"
      ) {
        sendTrumpSelect(legalActions.seatIndex, cardId);
      }
    },
    [legalActions, sendTrumpSelect]
  );

  // Handle card play
  const handleCardClick = useCallback(
    (cardId: string) => {
      if (legalActions?.type === "PLAY_CARD") {
        setSelectedCard(cardId);
        setTimeout(() => {
          sendPlayCard(legalActions.seatIndex, cardId);
          setSelectedCard(null);
        }, 150);
      }
    },
    [legalActions, sendPlayCard]
  );

  // Handle reveal trump choice
  const handleRevealChoice = useCallback(
    (reveal: boolean) => {
      if (
        legalActions?.type === "REVEAL_CHOICE" &&
        (gameState?.play?.trickCards?.length ?? 0) < 4
      ) {
        sendRevealChoice(legalActions.seatIndex, reveal);
      }
    },
    [legalActions, gameState?.play?.trickCards?.length, sendRevealChoice]
  );

  // Handle new game
  const handleNewGame = useCallback(() => {
    onGameEnd?.();
  }, [onGameEnd]);

  // Get legal card IDs for current player
  const legalCardIds = useMemo(() => {
    if (legalActions?.type === "PLAY_CARD") {
      return legalActions.cardIds || [];
    }
    return [];
  }, [legalActions]);

  // Get current bid info for bidding panel
  const getCurrentBidInfo = useCallback(() => {
    if (!gameState) return { highBid: null, highBidder: null };

    // Check R1 bids first
    const bidsR1 = gameState.bidsR1 || [0, 0, 0, 0];
    const bidsR2 = gameState.bidsR2 || [0, 0, 0, 0];

    let highBid = 0;
    let highBidder: string | null = null;

    // Find highest bid in current round
    const currentBids = phase === "BIDDING_R2" ? bidsR2 : bidsR1;
    for (let i = 0; i < 4; i++) {
      if (currentBids[i] > highBid) {
        highBid = currentBids[i];
        highBidder = PLAYER_NAMES[i];
      }
    }

    // For R2, also consider R1 winner
    if (phase === "BIDDING_R2" && highBid === 0 && gameState.round1BidValue) {
      highBid = gameState.round1BidValue;
      highBidder =
        gameState.round1BidderSeat !== null
          ? PLAYER_NAMES[gameState.round1BidderSeat]
          : null;
    }

    return {
      highBid: highBid > 0 ? highBid : null,
      highBidder,
    };
  }, [gameState, phase]);

  // Determine which team is bidding
  const biddingTeam = useMemo((): "humans" | "bots" | null => {
    if (finalBidderSeat === null || finalBidderSeat === undefined) return null;
    return HUMAN_SEATS.has(finalBidderSeat) ? "humans" : "bots";
  }, [finalBidderSeat]);

  // Calculate tricks won (approximate based on catch number)
  const humanTricks = useMemo(() => {
    if (!gameState?.play) return 0;
    const totalCatches = (gameState.play.catchNumber || 1) - 1;
    // This is approximate - for accurate count we'd need to track catches
    return Math.floor(totalCatches / 2);
  }, [gameState?.play]);

  const botTricks = useMemo(() => {
    const totalCatches = (gameState?.play?.catchNumber || 1) - 1;
    return totalCatches - humanTricks;
  }, [gameState?.play?.catchNumber, humanTricks]);

  // Build player data for GameArena
  const players = useMemo(() => {
    if (!gameState) return [];

    return [0, 1, 2, 3].map((seatIndex) => {
      const isBot = !HUMAN_SEATS.has(seatIndex);
      const isHuman = HUMAN_SEATS.has(seatIndex);
      const isHorizontal = seatIndex === 1 || seatIndex === 3;
      const isActive = turnIndex === seatIndex;
      const isBidder = finalBidderSeat === seatIndex;

      // Can interact if human, their turn, and in play phase with PLAY_CARD action
      const canInteract =
        isHuman &&
        isActive &&
        phase === "PLAY" &&
        legalActions?.type === "PLAY_CARD";

      // Get cards for this player
      const cards = getPlayerCards(seatIndex);

      // Get current bid for this player
      const playerBid =
        phase === "BIDDING_R2"
          ? gameState.bidsR2[seatIndex]
          : gameState.bidsR1[seatIndex];

      const speechBubbleText =
        botBidBubble && botBidBubble.seatIndex === seatIndex
          ? botBidBubble.text
          : null;

      return {
        seatIndex,
        isActive,
        isBidder,
        currentBid: playerBid > 0 ? playerBid : null,
        isThinking: isBot && isActive,
        speechBubbleText,
        handContent: (
          <PlayerHand
            cards={cards}
            faceUp={isHuman || showBotCards}
            isHorizontal={isHorizontal}
            isCompact={seatIndex !== 1}
            noOverlap={isHuman}
            highlightedCardIds={canInteract ? legalCardIds : []}
            selectedCardId={selectedCard}
            disabled={!canInteract}
            onCardClick={canInteract ? handleCardClick : undefined}
          />
        ),
      };
    });
  }, [
    gameState,
    turnIndex,
    finalBidderSeat,
    phase,
    legalActions,
    showBotCards,
    legalCardIds,
    selectedCard,
    botBidBubble,
    getPlayerCards,
    handleCardClick,
  ]);

  // Render center content based on phase
  const renderCenterContent = () => {
    // Handle reveal choice - this takes priority during PLAY phase
    if (
      legalActions?.type === "REVEAL_CHOICE" &&
      isHumanTurn &&
      trickCards.length < 4
    ) {
      const canReveal = legalActions.options?.includes(true);
      const canKeepHidden = legalActions.options?.includes(false);
      const isBidder = legalActions.seatIndex === finalBidderSeat;

      // If only True is available - this is the last trick case where bidder must reveal
      if (canReveal && !canKeepHidden) {
        return (
          <div className="game-panel reveal-panel">
            <div className="panel-title">Final Trick</div>
            <div className="panel-subtitle">
              You must reveal your trump card to play the final trick.
            </div>
            <div className="reveal-btns">
              <button
                className="reveal-btn"
                onClick={() => handleRevealChoice(true)}
              >
                Reveal Trump
              </button>
            </div>
          </div>
        );
      }

      // Both options available - player can choose
      // Determine the message based on who is asking
      let message = "You can't follow suit. Reveal trump?";

      if (isBidder) {
        // Bidder can reveal to play the trump card, or play a different suit
        message =
          "You can't follow suit. Reveal your trump card to play it, or play another card.";
      }

      // Build played cards info for the panel
      const playedCards: PlayedCardInfo[] = trickCards.map((tc) => ({
        cardId: tc.cardId,
        seatIndex: tc.seatIndex,
      }));

      return (
        <RevealTrumpPanel
          message={message}
          onReveal={() => handleRevealChoice(true)}
          onKeepHidden={() => handleRevealChoice(false)}
          playedCards={playedCards}
          currentSuit={gameState?.play?.currentSuit}
        />
      );
    }

    // Bidding delay: keep natural pacing after bot call/pass before enabling human input.
    if (
      isBotBidDelayActive &&
      (phase === "BIDDING_R1" || phase === "BIDDING_R2") &&
      (legalActions?.type === "BID_R1" || legalActions?.type === "BID_R2") &&
      HUMAN_SEATS.has(legalActions.seatIndex)
    ) {
      return (
        <div className="game-panel" style={{ textAlign: "center", padding: 24 }}>
          <div className="panel-title">Waiting...</div>
          <div className="panel-subtitle">
            {botBidBubble
              ? `${PLAYER_NAMES[botBidBubble.seatIndex]}: ${botBidBubble.text}`
              : "Bot made a call"}
          </div>
        </div>
      );
    }

    // Bidding phases
    if (phase === "BIDDING_R1" && legalActions?.type === "BID_R1" && isHumanTurn) {
      const { highBid, highBidder } = getCurrentBidInfo();
      return (
        <BiddingPanel
          minBid={legalActions.minBidExclusive + 1}
          maxBid={legalActions.maxBidInclusive}
          currentHighBid={highBid}
          currentBidder={highBidder}
          canPass={legalActions.canPass}
          canRedeal={legalActions.canRedeal}
          onBid={handleBid}
          onPass={handlePass}
          onRedeal={handleRedeal}
          isRound2={false}
        />
      );
    }

    if (phase === "BIDDING_R2" && legalActions?.type === "BID_R2" && isHumanTurn) {
      const { highBid, highBidder } = getCurrentBidInfo();
      return (
        <BiddingPanel
          minBid={legalActions.minBidExclusive + 1}
          maxBid={legalActions.maxBidInclusive}
          currentHighBid={highBid}
          currentBidder={highBidder}
          canPass={true}
          canRedeal={false}
          onBid={handleBid}
          onPass={handlePass}
          isRound2={true}
        />
      );
    }

    // Trump selection phases
    if (
      (phase === "TRUMP_SELECT_R1" || phase === "TRUMP_SELECT_R2") &&
      (legalActions?.type === "SELECT_TRUMP_R1" ||
        legalActions?.type === "SELECT_TRUMP_R2") &&
      isHumanTurn
    ) {
      const cards = getPlayerCards(legalActions.seatIndex);
      return <TrumpSelectPanel cards={cards} onSelect={handleTrumpSelect} />;
    }

    // Waiting states
    if (
      (phase === "BIDDING_R1" || phase === "BIDDING_R2") &&
      !isHumanTurn
    ) {
      return (
        <div className="game-panel" style={{ textAlign: "center", padding: 24 }}>
          <div className="panel-title">
            {PLAYER_NAMES[turnIndex]} is thinking...
          </div>
          <div className="panel-subtitle">Waiting for bid</div>
        </div>
      );
    }

    if (
      (phase === "TRUMP_SELECT_R1" || phase === "TRUMP_SELECT_R2") &&
      !isHumanTurn
    ) {
      return (
        <div className="game-panel" style={{ textAlign: "center", padding: 24 }}>
          <div className="panel-title">
            {PLAYER_NAMES[turnIndex]} is selecting trump...
          </div>
        </div>
      );
    }

    // Manual deal phase (auto-deal mode handles this automatically)
    if (phase === "MANUAL_DEAL_REST") {
      return (
        <div className="game-panel" style={{ textAlign: "center", padding: 24 }}>
          <div className="panel-title">Dealing remaining cards...</div>
          <div className="panel-subtitle">Please wait</div>
        </div>
      );
    }

    // Play phase - show trick area
    // Backend handles the 5-second delay, so we use trickCards directly
    if (phase === "PLAY") {
      return (
        <TrickArea
          cards={trickCards}
          leadSeatIndex={gameState?.play?.leaderIndex}
        />
      );
    }

    // Default empty state
    return null;
  };

  // Render game over modal
  const renderGameOver = () => {
    if (phase !== "GAME_OVER" || !gameState?.play) return null;

    const winnerTeam = gameState.play.winnerTeam;
    const didWin = winnerTeam === 2; // Team 2 is humans

    return (
      <GameOverModal
        didWin={didWin}
        humanScore={0} // Would need cumulative tracking
        botScore={0}
        humanPoints={gameState.play.team2Points}
        botPoints={gameState.play.team1Points}
        bidValue={finalBidValue || 0}
        biddingTeam={biddingTeam || "bots"}
        onNewGame={handleNewGame}
      />
    );
  };

  // Render abort modal
  const renderAbortModal = () => {
    if (!abortReason) return null;

    const reasonText =
      abortReason === "ALL_FOUR_JACKS"
        ? "A player has all four Jacks. Redealing..."
        : abortReason === "ALL_TRUMPS_ONE_SIDE"
        ? "One team has all trumps. Redealing..."
        : `Game aborted: ${abortReason}`;

    return (
      <div className="game-over-overlay">
        <div className="game-over-modal">
          <div className="result-title" style={{ color: "#f59e0b" }}>
            Game Aborted
          </div>
          <div className="result-details">
            <p>{reasonText}</p>
          </div>
          <button className="new-game-btn" onClick={handleNewGame}>
            Start New Game
          </button>
        </div>
      </div>
    );
  };

  // Loading state
  if (!gameId) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "100vh",
          background: "#1a5f2a",
          color: "white",
        }}
      >
        <div>No game ID provided</div>
      </div>
    );
  }

  if (!connected || !gameState) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "100vh",
          background: "#1a5f2a",
          color: "white",
          flexDirection: "column",
          gap: 16,
        }}
      >
        <div style={{ fontSize: 24 }}>Connecting to game...</div>
        <div style={{ fontSize: 14, opacity: 0.7 }}>Game ID: {gameId}</div>
      </div>
    );
  }

  return (
    <div>
      {/* Debug controls */}
      <div className="debug-controls">
        <label>
          <input
            type="checkbox"
            checked={showBotCards}
            onChange={(e) => setShowBotCards(e.target.checked)}
          />
          Show Bot Cards
        </label>
        <span style={{ marginLeft: 16 }}>
          Phase: {phase} | Turn: {PLAYER_NAMES[turnIndex] || "N/A"}
        </span>
        {errorMessage && (
          <span style={{ marginLeft: 16, color: "#ef4444" }}>{errorMessage}</span>
        )}
      </div>

      {/* Game Arena */}
      <GameArena
        players={players}
        centerContent={renderCenterContent()}
        uiPanelInfo={
          <>
            <PhaseIndicator phase={phase} currentPlayerSeat={turnIndex} />
            <TrumpIndicator
              trumpSuit={gameState.play?.trumpSuit || null}
              trumpCardId={gameState.play?.trumpCardId}
              isRevealed={gameState.play?.trumpReveal || false}
            />
            <TricksCounter humanTricks={humanTricks} botTricks={botTricks} />
          </>
        }
        uiPanelScore={
          <ScorePanel
            humanScore={0}
            botScore={0}
            currentBid={finalBidValue ?? null}
            biddingTeam={biddingTeam}
            humanPoints={gameState.play?.team2Points || 0}
            botPoints={gameState.play?.team1Points || 0}
          />
        }
        overlay={
          showTrumpRevealOverlay && revealedTrumpInfo ? (
            <TrumpRevealOverlay
              trumpSuit={revealedTrumpInfo.suit}
              trumpCardId={revealedTrumpInfo.cardId}
              onComplete={() => setShowTrumpRevealOverlay(false)}
            />
          ) : (
            renderGameOver() || renderAbortModal()
          )
        }
      />
    </div>
  );
};

export default GamePage;
