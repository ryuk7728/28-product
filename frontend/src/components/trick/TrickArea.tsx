/**
 * TrickArea - Center table showing current trick's 4 cards
 *
 * Features:
 * - Shows cards played in current trick by position (N/S/E/W)
 * - Animate card entry when played
 * - Smooth fade-out animation when trick completes
 * - Winner highlight
 *
 * Note: The backend handles the delay before clearing completed tricks,
 * so this component simply displays whatever cards are in the current state.
 */

import React, { useState, useEffect, useRef } from "react";
import { Card } from "../card/Card";
import {
  PLAYER_DIRECTIONS,
  CARD_WIDTH_SMALL,
  CARD_HEIGHT_SMALL,
} from "../../config/constants";
import "../../styles/trick.scss";

// Duration of fade-out animation in ms (should match CSS animation duration)
const FADE_OUT_DURATION_MS = 500;

export interface TrickCard {
  cardId: string;
  seatIndex: number;
  isWinning?: boolean;
}

export interface TrickAreaProps {
  cards: TrickCard[];
  leadSeatIndex?: number;
}

export const TrickArea: React.FC<TrickAreaProps> = ({
  cards,
  leadSeatIndex,
}) => {
  // Track previous card count to detect 4 → 0 transition
  const prevCardCountRef = useRef(cards.length);
  const [fadingOut, setFadingOut] = useState(false);
  const [displayCards, setDisplayCards] = useState<TrickCard[]>(cards);

  useEffect(() => {
    const prevCount = prevCardCountRef.current;
    const currentCount = cards.length;

    // Detect transition from 4 cards to 0 (trick completed and cleared)
    if (prevCount === 4 && currentCount === 0) {
      // Start fade-out animation, keep displaying the old cards
      setFadingOut(true);

      // After animation completes, clear display and reset
      const timer = setTimeout(() => {
        setFadingOut(false);
        setDisplayCards([]);
      }, FADE_OUT_DURATION_MS);

      prevCardCountRef.current = currentCount;
      return () => clearTimeout(timer);
    }

    // Normal update - just update display cards
    setDisplayCards(cards);
    prevCardCountRef.current = currentCount;
  }, [cards]);

  // Get card by seat position
  const getCardForSeat = (seatIndex: number): TrickCard | undefined => {
    return displayCards.find((c) => c.seatIndex === seatIndex);
  };

  // Render a single trick card
  const renderTrickCard = (seatIndex: number) => {
    const trickCard = getCardForSeat(seatIndex);
    const direction = PLAYER_DIRECTIONS[seatIndex];
    const isLead = leadSeatIndex === seatIndex;

    if (!trickCard) {
      return null;
    }

    return (
      <div
        key={seatIndex}
        className={`trick-card ${direction}-card ${trickCard.isWinning ? "winning" : ""} ${isLead ? "lead" : ""}`}
      >
        <Card
          cardId={trickCard.cardId}
          faceUp={true}
          width={CARD_WIDTH_SMALL}
          height={CARD_HEIGHT_SMALL}
        />
        {trickCard.isWinning && <div className="winner-badge">★</div>}
      </div>
    );
  };

  return (
    <div className={`trick-container ${fadingOut ? "fade-out" : ""}`}>
      {/* Render cards for all 4 positions */}
      {[0, 1, 2, 3].map((seatIndex) => renderTrickCard(seatIndex))}

      {/* Empty state when no cards played and not fading out */}
      {displayCards.length === 0 && !fadingOut && (
        <div className="trick-empty">
          <span>Play a card</span>
        </div>
      )}
    </div>
  );
};

export default TrickArea;
