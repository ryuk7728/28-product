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
  GameOverModal,
  PhaseIndicator,
  TrumpRevealOverlay,
  type PlayedCardInfo,
} from "../components/panels";
import { useGameWebSocket } from "../hooks/useGameWebSocket";
import type { Card as CardType } from "../api/types";
import { PLAYER_NAMES, BOT_BID_BUBBLE_DELAY_MS } from "../config/constants";
import "../styles/index.scss";

const BOT_SEATS = new Set([0, 2]);
const BID_SOUND_URL = new URL("../../sounds/bid.mp3", import.meta.url).href;
const BOT_BID_EVENT_RE = /^P([1-4])\s+(bid\s+(\d+)|passed(?:\s+\(R2\))?)\.$/i;

function parseBotBidEvent(logLine: string): { seatIndex: number; text: string } | null {
  const match = logLine.match(BOT_BID_EVENT_RE);
  if (!match) return null;

  const seatIndex = Number(match[1]) - 1;
  if (!BOT_SEATS.has(seatIndex)) return null;

  const bidAmount = match[3];
  return {
    seatIndex,
    text: bidAmount ? `Bid ${bidAmount}` : "Pass",
  };
}

export interface GamePageProps {
  gameId: string;
  roomCode?: string;
  playerToken?: string;
  playerSeatIndex?: number;
  controlledSeatIndices?: number[];
  spectateMode?: boolean;
  onGameEnd?: () => void;
}

export const GamePage: React.FC<GamePageProps> = ({
  gameId,
  roomCode,
  playerToken,
  playerSeatIndex = 1,
  controlledSeatIndices,
  spectateMode = false,
  onGameEnd,
}) => {
  const [selectedCard, setSelectedCard] = useState<string | null>(null);
  const [abortReason, setAbortReason] = useState<string | null>(null);
  const [botBidBubble, setBotBidBubble] = useState<{
    seatIndex: number;
    text: string;
  } | null>(null);
  const [isBotBidDelayActive, setIsBotBidDelayActive] = useState(false);
  const botBidDelayTimerRef = useRef<number | null>(null);
  const processedBotBidEventIndexRef = useRef<number>(-1);
  const bidAudioRef = useRef<HTMLAudioElement | null>(null);
  const wasHumanBidPanelVisibleRef = useRef(false);
  const isHumanBidPanelVisibleRef = useRef(false);
  const pendingBidPromptSoundRef = useRef(false);

  const [showTrumpRevealOverlay, setShowTrumpRevealOverlay] = useState(false);
  const [prevTrumpRevealed, setPrevTrumpRevealed] = useState(false);
  const [revealedTrumpInfo, setRevealedTrumpInfo] = useState<{ suit: string; cardId?: string } | null>(null);

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
    roomCode,
    playerToken,
    spectateMode,
    onError: () => {},
    onGameAborted: (reason) => {
      setAbortReason(reason);
    },
  });

  const phase = gameState?.phase || "";
  const turnIndex = gameState?.turnIndex ?? -1;
  const finalBidderSeat = gameState?.finalBidderSeat;
  const finalBidValue = gameState?.finalBidValue;
  const playerNamesFromState = gameState?.playerNames ?? PLAYER_NAMES;

  const effectiveControlledSeats = useMemo(() => {
    const raw = spectateMode
      ? []
      : controlledSeatIndices && controlledSeatIndices.length > 0
      ? controlledSeatIndices
      : [1, 3];
    const dedup = Array.from(new Set(raw.map((s) => Number(s))));
    return dedup.filter((s) => s >= 0 && s <= 3);
  }, [controlledSeatIndices, spectateMode]);

  const controlledSeatSet = useMemo(
    () => new Set(effectiveControlledSeats),
    [effectiveControlledSeats]
  );

  const primarySeat = effectiveControlledSeats[0] ?? playerSeatIndex;
  const isSingleControlledSeat = effectiveControlledSeats.length === 1;

  const mapSeatToRenderSeat = useCallback(
    (seatIndex: number): number => {
      if (!isSingleControlledSeat) {
        return seatIndex;
      }
      if (primarySeat === 3) {
        return seatIndex ^ 2;
      }
      return seatIndex;
    },
    [isSingleControlledSeat, primarySeat]
  );

  const getSeatDisplayName = useCallback(
    (seatIndex: number): string => {
      const resolved = playerNamesFromState?.[seatIndex];
      if (resolved && String(resolved).trim()) {
        return String(resolved).trim();
      }
      return PLAYER_NAMES[seatIndex] ?? `P${seatIndex + 1}`;
    },
    [playerNamesFromState]
  );

  const isHumanTurn = controlledSeatSet.has(turnIndex);

  const getPlayerCards = useCallback(
    (seatIndex: number): CardType[] => {
      return gameState?.players[seatIndex]?.cards || [];
    },
    [gameState]
  );

  const trickCards: TrickCard[] = useMemo(() => {
    if (!gameState?.play?.trickCards) {
      return [];
    }

    const leaderIndex = gameState.play.leaderIndex;
    return gameState.play.trickCards.map((card, idx) => ({
      cardId: card.cardId,
      seatIndex: mapSeatToRenderSeat((leaderIndex + idx) % 4),
      isWinning: false,
    }));
  }, [gameState?.play?.trickCards, gameState?.play?.leaderIndex, mapSeatToRenderSeat]);

  useEffect(() => {
    const currentTrumpRevealed = gameState?.play?.trumpReveal || false;
    const trumpSuit = gameState?.play?.trumpSuit;
    const trumpCardId = gameState?.play?.trumpCardId;

    if (currentTrumpRevealed && !prevTrumpRevealed && trumpSuit) {
      setRevealedTrumpInfo({ suit: trumpSuit, cardId: trumpCardId || undefined });
      setShowTrumpRevealOverlay(true);
    }

    setPrevTrumpRevealed(currentTrumpRevealed);
  }, [gameState?.play?.trumpReveal, gameState?.play?.trumpSuit, gameState?.play?.trumpCardId, prevTrumpRevealed]);

  useEffect(() => {
    if (!gameState || !legalActions) return;

    const isBiddingPhase = phase === "BIDDING_R1" || phase === "BIDDING_R2";
    const isHumanBidTurn =
      isBiddingPhase &&
      (legalActions.type === "BID_R1" || legalActions.type === "BID_R2") &&
      controlledSeatSet.has(legalActions.seatIndex);

    if (!isHumanBidTurn) {
      return;
    }

    const logs = gameState.eventLog || [];
    const lastIndex = logs.length - 1;
    if (lastIndex < 0 || processedBotBidEventIndexRef.current === lastIndex) {
      return;
    }

    const parsed = parseBotBidEvent(logs[lastIndex]);
    if (!parsed) return;

    processedBotBidEventIndexRef.current = lastIndex;
    setBotBidBubble({ seatIndex: parsed.seatIndex, text: parsed.text });
    setIsBotBidDelayActive(true);

    if (botBidDelayTimerRef.current !== null) {
      window.clearTimeout(botBidDelayTimerRef.current);
    }
    botBidDelayTimerRef.current = window.setTimeout(() => {
      setIsBotBidDelayActive(false);
      setBotBidBubble(null);
      botBidDelayTimerRef.current = null;
    }, BOT_BID_BUBBLE_DELAY_MS);
  }, [gameState, legalActions, phase, controlledSeatSet]);

  useEffect(() => {
    return () => {
      if (botBidDelayTimerRef.current !== null) {
        window.clearTimeout(botBidDelayTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const audio = new Audio(BID_SOUND_URL);
    audio.preload = "auto";
    bidAudioRef.current = audio;

    return () => {
      audio.pause();
      audio.src = "";
      bidAudioRef.current = null;
    };
  }, []);

  useEffect(() => {
    const retryPendingBidPromptSound = () => {
      if (!pendingBidPromptSoundRef.current) return;
      if (!isHumanBidPanelVisibleRef.current) return;

      const audio = bidAudioRef.current;
      if (!audio) return;

      try {
        audio.currentTime = 0;
        void audio.play().then(() => {
          pendingBidPromptSoundRef.current = false;
        }).catch(() => {
          // Keep pending true; next interaction can retry.
        });
      } catch {
        // Ignore runtime errors and keep pending true for next interaction.
      }
    };

    window.addEventListener("pointerdown", retryPendingBidPromptSound, true);
    window.addEventListener("keydown", retryPendingBidPromptSound, true);

    return () => {
      window.removeEventListener("pointerdown", retryPendingBidPromptSound, true);
      window.removeEventListener("keydown", retryPendingBidPromptSound, true);
    };
  }, []);

  useEffect(() => {
    const logs = gameState?.eventLog || [];
    const lastIndex = logs.length - 1;
    const unprocessedBotBidEventExists =
      lastIndex >= 0 &&
      parseBotBidEvent(logs[lastIndex]) !== null &&
      processedBotBidEventIndexRef.current < lastIndex;

    const isHumanBidPanelVisible =
      (phase === "BIDDING_R1" || phase === "BIDDING_R2") &&
      (legalActions?.type === "BID_R1" || legalActions?.type === "BID_R2") &&
      controlledSeatSet.has(legalActions.seatIndex) &&
      !isBotBidDelayActive &&
      !unprocessedBotBidEventExists;

    isHumanBidPanelVisibleRef.current = isHumanBidPanelVisible;
    if (!isHumanBidPanelVisible) {
      pendingBidPromptSoundRef.current = false;
    }

    const shouldPlay =
      isHumanBidPanelVisible && !wasHumanBidPanelVisibleRef.current;
    wasHumanBidPanelVisibleRef.current = isHumanBidPanelVisible;
    if (!shouldPlay) return;

    const audio = bidAudioRef.current;
    if (!audio) return;

    try {
      audio.currentTime = 0;
      void audio.play().then(() => {
        pendingBidPromptSoundRef.current = false;
      }).catch(() => {
        pendingBidPromptSoundRef.current = true;
      });
    } catch {
      pendingBidPromptSoundRef.current = true;
    }
  }, [phase, legalActions, isBotBidDelayActive, gameState?.eventLog, controlledSeatSet]);

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

  const handlePass = useCallback(() => {
    if (
      !isBotBidDelayActive &&
      (legalActions?.type === "BID_R1" || legalActions?.type === "BID_R2")
    ) {
      sendBid(legalActions.seatIndex, 0);
    }
  }, [isBotBidDelayActive, legalActions, sendBid]);

  const handleRedeal = useCallback(() => {
    if (
      !isBotBidDelayActive &&
      legalActions?.type === "BID_R1" &&
      legalActions.canRedeal
    ) {
      sendBid(legalActions.seatIndex, -1);
    }
  }, [isBotBidDelayActive, legalActions, sendBid]);

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

  const handleNewGame = useCallback(() => {
    onGameEnd?.();
  }, [onGameEnd]);

  const legalCardIds = useMemo(() => {
    if (legalActions?.type === "PLAY_CARD") {
      return legalActions.cardIds || [];
    }
    return [];
  }, [legalActions]);

  const getCurrentBidInfo = useCallback(() => {
    if (!gameState) return { highBid: null, highBidder: null };

    const bidsR1 = gameState.bidsR1 || [0, 0, 0, 0];
    const bidsR2 = gameState.bidsR2 || [0, 0, 0, 0];

    let highBid = 0;
    let highBidder: string | null = null;

    const currentBids = phase === "BIDDING_R2" ? bidsR2 : bidsR1;
    for (let i = 0; i < 4; i++) {
      if (currentBids[i] > highBid) {
        highBid = currentBids[i];
        highBidder = getSeatDisplayName(i);
      }
    }

    if (phase === "BIDDING_R2" && highBid === 0 && gameState.round1BidValue) {
      highBid = gameState.round1BidValue;
      highBidder =
        gameState.round1BidderSeat !== null
          ? getSeatDisplayName(gameState.round1BidderSeat)
          : null;
    }

    return {
      highBid: highBid > 0 ? highBid : null,
      highBidder,
    };
  }, [gameState, phase, getSeatDisplayName]);

  const biddingTeam = useMemo((): "humans" | "bots" | null => {
    if (finalBidderSeat === null || finalBidderSeat === undefined) return null;
    return BOT_SEATS.has(finalBidderSeat) ? "bots" : "humans";
  }, [finalBidderSeat]);

  const humanBidPromptSeat = useMemo<number | null>(() => {
    const isHumanBidPanelVisible =
      (phase === "BIDDING_R1" || phase === "BIDDING_R2") &&
      (legalActions?.type === "BID_R1" || legalActions?.type === "BID_R2") &&
      controlledSeatSet.has(legalActions.seatIndex) &&
      !isBotBidDelayActive;

    return isHumanBidPanelVisible ? legalActions.seatIndex : null;
  }, [phase, legalActions, controlledSeatSet, isBotBidDelayActive]);

  const displayedBidInfo = useMemo<{ seat: number | null; value: number | null }>(() => {
    if (!gameState) {
      return { seat: null, value: null };
    }

    if (finalBidderSeat !== null && finalBidderSeat !== undefined && (finalBidValue ?? 0) > 0) {
      return { seat: finalBidderSeat, value: finalBidValue ?? null };
    }

    if (phase === "BIDDING_R2") {
      let highSeat: number | null = null;
      let highValue = 0;
      for (let i = 0; i < 4; i++) {
        const bid = gameState.bidsR2[i] || 0;
        if (bid > highValue) {
          highValue = bid;
          highSeat = i;
        }
      }
      if (highValue > 0 && highSeat !== null) {
        return { seat: highSeat, value: highValue };
      }
      if ((gameState.round1BidValue ?? 0) > 0 && gameState.round1BidderSeat !== null) {
        return { seat: gameState.round1BidderSeat, value: gameState.round1BidValue };
      }
      return { seat: null, value: null };
    }

    if (phase === "BIDDING_R1") {
      let highSeat: number | null = null;
      let highValue = 0;
      for (let i = 0; i < 4; i++) {
        const bid = gameState.bidsR1[i] || 0;
        if (bid > highValue) {
          highValue = bid;
          highSeat = i;
        }
      }
      if (highValue > 0 && highSeat !== null) {
        return { seat: highSeat, value: highValue };
      }
    }

    return { seat: null, value: null };
  }, [gameState, finalBidderSeat, finalBidValue, phase]);

  const players = useMemo(() => {
    if (!gameState) return [];

    return [0, 1, 2, 3].map((seatIndex) => {
      const isBot = BOT_SEATS.has(seatIndex);
      const isLocalSeat = controlledSeatSet.has(seatIndex);
      const renderSeatIndex = mapSeatToRenderSeat(seatIndex);
      const isHorizontal = renderSeatIndex === 1 || renderSeatIndex === 3;
      const isActive = turnIndex === seatIndex;
      const isBidder = finalBidderSeat === seatIndex;

      const canInteract =
        isLocalSeat &&
        isActive &&
        phase === "PLAY" &&
        legalActions?.type === "PLAY_CARD";

      const cards = getPlayerCards(seatIndex);
      const playerBid = displayedBidInfo.seat === seatIndex ? displayedBidInfo.value : null;
      const isBidGlow = humanBidPromptSeat === seatIndex && isLocalSeat;

      const speechBubbleText =
        botBidBubble && botBidBubble.seatIndex === seatIndex
          ? botBidBubble.text
          : null;

      return {
        seatIndex,
        renderSeatIndex,
        displayName: getSeatDisplayName(seatIndex),
        isBot,
        isActive,
        isBidGlow,
        isBidder,
        currentBid: playerBid !== null && playerBid > 0 ? playerBid : null,
        isThinking: isBot && isActive,
        speechBubbleText,
        handContent: (
          <PlayerHand
            cards={cards}
            faceUp={spectateMode || isLocalSeat}
            isHorizontal={isHorizontal}
            isCompact={renderSeatIndex !== 1}
            noOverlap={isLocalSeat}
            highlightedCardIds={canInteract ? legalCardIds : []}
            selectedCardId={selectedCard}
            disabled={!canInteract}
            onCardClick={canInteract ? handleCardClick : undefined}
            className={isBidGlow ? "bid-turn-glow-hand" : ""}
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
    legalCardIds,
    selectedCard,
    botBidBubble,
    controlledSeatSet,
    mapSeatToRenderSeat,
    getPlayerCards,
    displayedBidInfo,
    humanBidPromptSeat,
    getSeatDisplayName,
    handleCardClick,
    spectateMode,
  ]);

  const renderCenterContent = () => {
    if (
      legalActions?.type === "REVEAL_CHOICE" &&
      isHumanTurn &&
      trickCards.length < 4
    ) {
      const canReveal = legalActions.options?.includes(true);
      const canKeepHidden = legalActions.options?.includes(false);
      const isBidder = legalActions.seatIndex === finalBidderSeat;

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

      let message = "You can't follow suit. Reveal trump?";

      if (isBidder) {
        message =
          "You can't follow suit. Reveal your trump card to play it, or play another card.";
      }

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

    if (
      isBotBidDelayActive &&
      (phase === "BIDDING_R1" || phase === "BIDDING_R2") &&
      (legalActions?.type === "BID_R1" || legalActions?.type === "BID_R2") &&
      controlledSeatSet.has(legalActions.seatIndex)
    ) {
      return (
        <div className="game-panel" style={{ textAlign: "center", padding: 24 }}>
          <div className="panel-title">Waiting...</div>
          <div className="panel-subtitle">
            {botBidBubble
              ? `${getSeatDisplayName(botBidBubble.seatIndex)}: ${botBidBubble.text}`
              : "Bot made a call"}
          </div>
        </div>
      );
    }

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

    if (
      (phase === "TRUMP_SELECT_R1" || phase === "TRUMP_SELECT_R2") &&
      (legalActions?.type === "SELECT_TRUMP_R1" ||
        legalActions?.type === "SELECT_TRUMP_R2") &&
      isHumanTurn
    ) {
      const cards = getPlayerCards(legalActions.seatIndex);
      return <TrumpSelectPanel cards={cards} onSelect={handleTrumpSelect} />;
    }

    if (
      (phase === "BIDDING_R1" || phase === "BIDDING_R2") &&
      !isHumanTurn
    ) {
      return (
        <div className="game-panel" style={{ textAlign: "center", padding: 24 }}>
          <div className="panel-title">
            {getSeatDisplayName(turnIndex)} is thinking...
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
            {getSeatDisplayName(turnIndex)} is selecting trump...
          </div>
        </div>
      );
    }

    if (phase === "MANUAL_DEAL_REST") {
      return (
        <div className="game-panel" style={{ textAlign: "center", padding: 24 }}>
          <div className="panel-title">Dealing remaining cards...</div>
          <div className="panel-subtitle">Please wait</div>
        </div>
      );
    }

    if (phase === "PLAY") {
      return (
        <TrickArea
          cards={trickCards}
          leadSeatIndex={
            gameState?.play?.leaderIndex !== undefined
              ? mapSeatToRenderSeat(gameState.play.leaderIndex)
              : undefined
          }
        />
      );
    }

    return null;
  };

  const renderGameOver = () => {
    if (phase !== "GAME_OVER" || !gameState?.play) return null;

    const winnerTeam = gameState.play.winnerTeam;
    const didWin = winnerTeam === 2;

    return (
      <GameOverModal
        didWin={didWin}
        humanScore={0}
        botScore={0}
        humanPoints={gameState.play.team2Points}
        botPoints={gameState.play.team1Points}
        bidValue={finalBidValue || 0}
        biddingTeam={biddingTeam || "bots"}
        onNewGame={handleNewGame}
      />
    );
  };

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
      <GameArena
        players={players}
        centerContent={renderCenterContent()}
        uiPanelInfo={
          <>
            <PhaseIndicator
              phase={phase}
              currentPlayerSeat={turnIndex}
              currentPlayerName={turnIndex >= 0 ? getSeatDisplayName(turnIndex) : null}
            />
            <TrumpIndicator
              trumpSuit={gameState.play?.trumpSuit || null}
              trumpCardId={gameState.play?.trumpCardId}
              isRevealed={gameState.play?.trumpReveal || false}
            />
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
            humanTeamLabel={`${getSeatDisplayName(1)} & ${getSeatDisplayName(3)}`}
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
