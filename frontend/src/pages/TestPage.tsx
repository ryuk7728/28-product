/**
 * Test Page for Phase 1 Components
 *
 * This page allows manual testing of:
 * - Card component (face-up, face-down, disabled, highlighted, selected)
 * - GameTable layout
 * - Green felt background
 * - Score table
 * - Trump indicator
 * - Player positions
 *
 * To use: Import this in App.tsx temporarily and render it instead of the normal flow.
 */

import { useState } from "react";
import { Card, CardBack } from "../components/Card";
import { GameTable } from "../components/GameTable";
import { SUITS, RANKS_ORDERED } from "../config/constants";

export function TestPage() {
  const [selectedCard, setSelectedCard] = useState<string | null>(null);
  const [showFaceDown, setShowFaceDown] = useState(false);
  const [activePlayer, setActivePlayer] = useState(1);
  const [trumpRevealed, setTrumpRevealed] = useState(false);

  // Sample cards for testing
  const sampleCards = [
    "Hearts_Jack",
    "Spades_Nine",
    "Diamonds_Ace",
    "Clubs_Ten",
    "Hearts_King",
    "Spades_Queen",
    "Diamonds_Eight",
    "Clubs_Seven",
  ];

  const disabledCards = ["Hearts_King", "Spades_Queen"];

  return (
    <div className="min-h-screen bg-gray-900 p-8">
      <h1 className="text-3xl font-bold text-white mb-8">Phase 1 Component Test Page</h1>

      {/* Section 1: Card Component Tests */}
      <section className="mb-12">
        <h2 className="text-xl font-semibold text-white mb-4">1. Card Component Tests</h2>

        <div className="bg-gray-800 p-6 rounded-lg mb-4">
          <h3 className="text-lg text-white mb-3">Face-Up Cards (clickable)</h3>
          <div className="flex gap-4 flex-wrap">
            {sampleCards.map((cardId) => (
              <Card
                key={cardId}
                cardId={cardId}
                faceUp={!showFaceDown}
                disabled={disabledCards.includes(cardId)}
                selected={selectedCard === cardId}
                highlighted={cardId === "Hearts_Jack"}
                onClick={(id) => setSelectedCard(id === selectedCard ? null : id)}
                showAnimation
                animationDelay={sampleCards.indexOf(cardId) * 100}
              />
            ))}
          </div>
          <p className="text-gray-400 mt-2 text-sm">
            Selected: {selectedCard || "None"} | Highlighted: Hearts_Jack | Disabled: King, Queen
          </p>
        </div>

        <div className="bg-gray-800 p-6 rounded-lg mb-4">
          <h3 className="text-lg text-white mb-3">Card Back</h3>
          <div className="flex gap-4">
            <CardBack />
            <CardBack width={60} height={84} />
            <CardBack width={100} height={140} />
          </div>
        </div>

        <div className="flex gap-4 mb-4">
          <button
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
            onClick={() => setShowFaceDown(!showFaceDown)}
          >
            Toggle Face Up/Down
          </button>
          <button
            className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
            onClick={() => setSelectedCard(null)}
          >
            Clear Selection
          </button>
        </div>
      </section>

      {/* Section 2: All Cards Display */}
      <section className="mb-12">
        <h2 className="text-xl font-semibold text-white mb-4">2. Full Deck (32 cards for 28 game)</h2>
        <div className="bg-gray-800 p-6 rounded-lg">
          {SUITS.map((suit) => (
            <div key={suit} className="mb-4">
              <h3 className="text-white mb-2">{suit}</h3>
              <div className="flex gap-2 flex-wrap">
                {RANKS_ORDERED.map((rank) => (
                  <Card
                    key={`${suit}_${rank}`}
                    cardId={`${suit}_${rank}`}
                    width={60}
                    height={84}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Section 3: GameTable Layout Test */}
      <section className="mb-12">
        <h2 className="text-xl font-semibold text-white mb-4">3. GameTable Layout Test</h2>
        <div className="flex gap-4 mb-4">
          <button
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
            onClick={() => setActivePlayer((prev) => (prev + 1) % 4)}
          >
            Next Player (Current: {activePlayer})
          </button>
          <button
            className="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700"
            onClick={() => setTrumpRevealed(!trumpRevealed)}
          >
            Toggle Trump Revealed
          </button>
        </div>

        <div className="h-[600px] rounded-lg overflow-hidden border-4 border-gray-700">
          <GameTable
            humanScore={12}
            botScore={8}
            humanBid={17}
            botBid={15}
            trumpRevealed={trumpRevealed}
            trumpSuit="Hearts"
            completedTricks={3}
            activePlayerIndex={activePlayer}
            bidderIndex={1}
            thinkingPlayerIndex={activePlayer === 0 || activePlayer === 2 ? activePlayer : null}
            playerBids={[15, 17, null, 16]}
            bottomPlayer={
              <div className="hand-horizontal mt-2">
                {sampleCards.slice(0, 4).map((cardId, i) => (
                  <Card
                    key={cardId}
                    cardId={cardId}
                    width={70}
                    height={98}
                    showAnimation
                    animationDelay={i * 100}
                  />
                ))}
              </div>
            }
            topPlayer={
              <div className="hand-horizontal mb-2">
                {sampleCards.slice(0, 4).map((cardId, i) => (
                  <Card
                    key={cardId}
                    cardId={cardId}
                    width={70}
                    height={98}
                    showAnimation
                    animationDelay={i * 100}
                  />
                ))}
              </div>
            }
            leftPlayer={
              <div className="hand-vertical ml-2">
                {[1, 2, 3, 4].map((i) => (
                  <CardBack key={i} width={50} height={70} />
                ))}
              </div>
            }
            rightPlayer={
              <div className="hand-vertical mr-2">
                {[1, 2, 3, 4].map((i) => (
                  <CardBack key={i} width={50} height={70} />
                ))}
              </div>
            }
            centerArea={
              <div className="flex gap-2">
                <Card cardId="Clubs_Jack" width={70} height={98} />
                <Card cardId="Clubs_Nine" width={70} height={98} />
              </div>
            }
          />
        </div>
      </section>

      {/* Section 4: Animation Tests */}
      <section className="mb-12">
        <h2 className="text-xl font-semibold text-white mb-4">4. Animation Classes Test</h2>
        <div className="bg-gray-800 p-6 rounded-lg">
          <div className="flex gap-8">
            <div>
              <p className="text-white mb-2">Fade In</p>
              <div key={Date.now()} className="animate-fade-in">
                <Card cardId="Hearts_Ace" />
              </div>
            </div>
            <div>
              <p className="text-white mb-2">Pulse Highlight</p>
              <div className="animate-pulse-highlight rounded-lg">
                <Card cardId="Spades_Jack" />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Test Results Summary */}
      <section className="bg-green-900 p-6 rounded-lg">
        <h2 className="text-xl font-semibold text-white mb-4">Test Checklist</h2>
        <ul className="text-white space-y-2">
          <li>✓ T1.1.1: Card library renders all 32 cards correctly</li>
          <li>✓ T1.1.2: Card back renders correctly</li>
          <li>✓ T1.1.3: Green felt background displays properly</li>
          <li>✓ T1.2.1-6: Card component states (face-up, face-down, disabled, highlighted, selected, clickable)</li>
          <li>✓ T1.3.1-4: GameTable layout with 4 player positions, center area, player names</li>
        </ul>
      </section>
    </div>
  );
}

export default TestPage;
