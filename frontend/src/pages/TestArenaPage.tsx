/**
 * TestArenaPage - Test page for the new UI components
 *
 * This page renders the GameArena with mock data to visualize
 * the layout without needing the backend.
 */

import React, { useState, useCallback } from "react";
import { GameArena } from "../components/table";
import { PlayerHand } from "../components/player";
import { TrickArea } from "../components/trick";
import type { TrickCard } from "../components/trick";
import {
  BiddingPanel,
  TrumpSelectPanel,
  ScorePanel,
  TrumpIndicator,
  TricksCounter,
  GameOverModal,
  PhaseIndicator,
} from "../components/panels";
import type { Card as CardType } from "../api/types";
import "../styles/index.scss";

// Mock cards for testing
const createMockCard = (suit: string, rank: string): CardType => ({
  cardId: `${suit}_${rank}`,
  suit,
  rank,
  points: rank === "Jack" ? 3 : rank === "Nine" ? 2 : rank === "Ace" || rank === "Ten" ? 1 : 0,
  order: 0,
  label: `${rank} of ${suit}`,
});

// Generate test hands
const createInitialHands = (): CardType[][] => [
  // Seat 0 (East - Bot T-1000)
  [
    createMockCard("Hearts", "Jack"),
    createMockCard("Hearts", "Nine"),
    createMockCard("Diamonds", "Ace"),
    createMockCard("Diamonds", "King"),
    createMockCard("Clubs", "Queen"),
    createMockCard("Spades", "Ten"),
    createMockCard("Spades", "Eight"),
    createMockCard("Spades", "Seven"),
  ],
  // Seat 1 (South - You)
  [
    createMockCard("Spades", "Jack"),
    createMockCard("Spades", "Nine"),
    createMockCard("Hearts", "Ace"),
    createMockCard("Hearts", "Ten"),
    createMockCard("Diamonds", "Queen"),
    createMockCard("Clubs", "King"),
    createMockCard("Clubs", "Eight"),
    createMockCard("Clubs", "Seven"),
  ],
  // Seat 2 (West - Bot Skynet)
  [
    createMockCard("Diamonds", "Jack"),
    createMockCard("Diamonds", "Nine"),
    createMockCard("Clubs", "Ace"),
    createMockCard("Clubs", "Ten"),
    createMockCard("Hearts", "Queen"),
    createMockCard("Hearts", "King"),
    createMockCard("Spades", "Queen"),
    createMockCard("Spades", "King"),
  ],
  // Seat 3 (North - Partner)
  [
    createMockCard("Clubs", "Jack"),
    createMockCard("Clubs", "Nine"),
    createMockCard("Spades", "Ace"),
    createMockCard("Hearts", "Eight"),
    createMockCard("Hearts", "Seven"),
    createMockCard("Diamonds", "Ten"),
    createMockCard("Diamonds", "Eight"),
    createMockCard("Diamonds", "Seven"),
  ],
];

type DemoPhase = "bidding" | "trump_select" | "play" | "game_over";

export const TestArenaPage: React.FC = () => {
  const [hands, setHands] = useState<CardType[][]>(createInitialHands);
  const [activePlayer, setActivePlayer] = useState(1); // Start with "You"
  const [showBotCards, setShowBotCards] = useState(false);
  const [selectedCard, setSelectedCard] = useState<string | null>(null);
  const [trickCards, setTrickCards] = useState<TrickCard[]>([]);
  const [trickComplete, setTrickComplete] = useState(false);
  const [leadSeatIndex, setLeadSeatIndex] = useState<number | undefined>(undefined);

  // Demo state for panels
  const [demoPhase, setDemoPhase] = useState<DemoPhase>("play");
  const [currentBid, setCurrentBid] = useState<number | null>(null);
  const [trumpSuit, setTrumpSuit] = useState<string | null>(null);
  const [trumpRevealed, setTrumpRevealed] = useState(false);
  const [humanTricks, setHumanTricks] = useState(0);
  const [botTricks, setBotTricks] = useState(0);
  const [showGameOver, setShowGameOver] = useState(false);

  // Mock legal cards (all cards of the active human player for testing)
  const legalCardIds =
    activePlayer === 1 || activePlayer === 3
      ? hands[activePlayer].map((c) => c.cardId)
      : [];

  // Handle trick completion - clear cards and move to next trick
  const handleTrickComplete = useCallback(() => {
    // Randomly assign trick to a team
    if (Math.random() > 0.5) {
      setHumanTricks((prev) => prev + 1);
    } else {
      setBotTricks((prev) => prev + 1);
    }
    setTrickCards([]);
    setTrickComplete(false);
    setLeadSeatIndex(undefined);
  }, []);

  // Play a card (for both human and bot)
  const playCard = useCallback(
    (seatIndex: number, cardId: string) => {
      // Remove card from hand
      setHands((prev) => {
        const newHands = [...prev];
        newHands[seatIndex] = newHands[seatIndex].filter((c) => c.cardId !== cardId);
        return newHands;
      });

      // Add to trick
      setTrickCards((prev) => {
        const newCards = [...prev, { cardId, seatIndex }];

        // If trick is complete (4 cards), mark the last card as winner and set complete flag
        if (newCards.length === 4) {
          // Randomly pick a winner for demo
          const winnerIdx = Math.floor(Math.random() * 4);
          newCards[winnerIdx].isWinning = true;
          setTimeout(() => setTrickComplete(true), 300);
        }

        return newCards;
      });

      // Set lead if first card
      if (trickCards.length === 0) {
        setLeadSeatIndex(seatIndex);
      }

      // Move to next player
      const nextPlayer = (seatIndex + 1) % 4;
      setActivePlayer(nextPlayer);

      // If next player is a bot, auto-play after delay
      if (nextPlayer === 0 || nextPlayer === 2) {
        setTimeout(() => {
          const botHand = hands[nextPlayer];
          if (botHand.length > 0) {
            const randomCard = botHand[Math.floor(Math.random() * botHand.length)];
            playCard(nextPlayer, randomCard.cardId);
          }
        }, 800);
      }
    },
    [hands, trickCards.length]
  );

  const handleCardClick = (cardId: string) => {
    if (demoPhase !== "play") return;

    console.log("Card clicked:", cardId);
    setSelectedCard(cardId);

    // Play the card after a short delay
    setTimeout(() => {
      setSelectedCard(null);
      playCard(activePlayer, cardId);
    }, 200);
  };

  // Demo handlers
  const handleBid = (value: number) => {
    console.log("Bid:", value);
    setCurrentBid(value);
    setDemoPhase("trump_select");
  };

  const handlePass = () => {
    console.log("Passed");
  };

  const handleTrumpSelect = (cardId: string) => {
    const suit = cardId.split("_")[0];
    console.log("Trump selected:", suit);
    setTrumpSuit(suit);
    setDemoPhase("play");
  };

  // Reset game
  const resetGame = () => {
    setHands(createInitialHands());
    setActivePlayer(1);
    setTrickCards([]);
    setTrickComplete(false);
    setLeadSeatIndex(undefined);
    setSelectedCard(null);
    setDemoPhase("play");
    setCurrentBid(null);
    setTrumpSuit(null);
    setTrumpRevealed(false);
    setHumanTricks(0);
    setBotTricks(0);
    setShowGameOver(false);
  };

  // Build player data
  const players = [0, 1, 2, 3].map((seatIndex) => {
    const isBot = seatIndex === 0 || seatIndex === 2;
    const isHuman = !isBot;
    const isHorizontal = seatIndex === 1 || seatIndex === 3;
    const isActive = activePlayer === seatIndex;
    const canInteract = isHuman && isActive && !trickComplete && demoPhase === "play";

    return {
      seatIndex,
      isActive,
      isBidder: seatIndex === 0, // Mock: T-1000 is bidder
      currentBid: seatIndex === 0 ? 15 : null,
      isThinking: isBot && isActive,
      handContent: (
        <PlayerHand
          cards={hands[seatIndex]}
          faceUp={isHuman || showBotCards}
          isHorizontal={isHorizontal}
          isCompact={seatIndex !== 1}
          noOverlap={isHuman} // Human players get fully spread cards, no overlap
          highlightedCardIds={canInteract ? legalCardIds : []}
          selectedCardId={selectedCard}
          disabled={!canInteract}
          onCardClick={canInteract ? handleCardClick : undefined}
        />
      ),
    };
  });

  // Center content based on phase
  const getCenterContent = () => {
    switch (demoPhase) {
      case "bidding":
        return (
          <BiddingPanel
            minBid={14}
            currentHighBid={currentBid}
            currentBidder={currentBid ? "T-1000" : null}
            canPass={true}
            canRedeal={true}
            onBid={handleBid}
            onPass={handlePass}
            onRedeal={resetGame}
          />
        );
      case "trump_select":
        return (
          <TrumpSelectPanel
            cards={hands[1].slice(0, 4)} // First 4 cards
            onSelect={handleTrumpSelect}
          />
        );
      case "play":
      default:
        return (
          <TrickArea
            cards={trickCards}
            trickComplete={trickComplete}
            onTrickComplete={handleTrickComplete}
            leadSeatIndex={leadSeatIndex}
          />
        );
    }
  };

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
        <label>
          Phase:
          <select
            value={demoPhase}
            onChange={(e) => setDemoPhase(e.target.value as DemoPhase)}
            style={{ marginLeft: 8, padding: "4px 8px" }}
          >
            <option value="bidding">Bidding</option>
            <option value="trump_select">Trump Select</option>
            <option value="play">Play</option>
          </select>
        </label>
        <button
          onClick={() => setTrumpRevealed(!trumpRevealed)}
          style={{
            padding: "4px 12px",
            marginLeft: 8,
            cursor: "pointer",
            borderRadius: 4,
            border: "1px solid #555",
            background: "#333",
            color: "white",
          }}
        >
          {trumpRevealed ? "Hide Trump" : "Reveal Trump"}
        </button>
        <button
          onClick={() => setShowGameOver(true)}
          style={{
            padding: "4px 12px",
            marginLeft: 8,
            cursor: "pointer",
            borderRadius: 4,
            border: "1px solid #555",
            background: "#333",
            color: "white",
          }}
        >
          Show Game Over
        </button>
        <button
          onClick={resetGame}
          style={{
            padding: "4px 12px",
            marginLeft: 8,
            cursor: "pointer",
            borderRadius: 4,
            border: "1px solid #555",
            background: "#333",
            color: "white",
          }}
        >
          Reset
        </button>
      </div>

      {/* Game Arena */}
      <GameArena
        players={players}
        centerContent={getCenterContent()}
        uiPanels={
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <PhaseIndicator phase="PLAY" currentPlayerSeat={activePlayer} />
            <TrumpIndicator trumpSuit={trumpSuit} isRevealed={trumpRevealed} />
            <TricksCounter humanTricks={humanTricks} botTricks={botTricks} />
            <ScorePanel
              humanScore={2}
              botScore={1}
              currentBid={currentBid || 16}
              biddingTeam="bots"
              humanPoints={12}
              botPoints={8}
            />
          </div>
        }
        overlay={
          showGameOver ? (
            <GameOverModal
              didWin={true}
              humanScore={3}
              botScore={1}
              humanPoints={18}
              botPoints={10}
              bidValue={16}
              biddingTeam="humans"
              onNewGame={() => {
                setShowGameOver(false);
                resetGame();
              }}
            />
          ) : undefined
        }
      />
    </div>
  );
};

export default TestArenaPage;
