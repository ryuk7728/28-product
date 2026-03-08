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
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Track previous card count to detect 4 → 0 transition
  const prevCardCountRef = useRef(cards.length);
  const [fadingOut, setFadingOut] = useState(false);
  const [displayCards, setDisplayCards] = useState<TrickCard[]>(cards);
  const [cardSize, setCardSize] = useState({
    width: CARD_WIDTH_SMALL,
    height: CARD_HEIGHT_SMALL,
  });

  // Make trick cards adapt to the available center zone.
  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;

    const CARD_RATIO = CARD_HEIGHT_SMALL / CARD_WIDTH_SMALL;
    const MIN_WIDTH = 46;
    const MAX_WIDTH = CARD_WIDTH_SMALL;

    const update = (width: number, height: number) => {
      const widthByZone = Math.floor(width * 0.26);
      const widthByHeight = Math.floor((height * 0.48) / CARD_RATIO);
      const nextWidth = Math.max(
        MIN_WIDTH,
        Math.min(MAX_WIDTH, widthByZone, widthByHeight)
      );
      const nextHeight = Math.round(nextWidth * CARD_RATIO);
      setCardSize((prev) =>
        prev.width === nextWidth && prev.height === nextHeight
          ? prev
          : { width: nextWidth, height: nextHeight }
      );
    };

    update(node.clientWidth, node.clientHeight);

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      update(entry.contentRect.width, entry.contentRect.height);
    });
    observer.observe(node);

    return () => observer.disconnect();
  }, []);

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
          width={cardSize.width}
          height={cardSize.height}
        />
        {trickCard.isWinning && <div className="winner-badge">★</div>}
      </div>
    );
  };

  return (
    <div
      ref={containerRef}
      className={`trick-container ${fadingOut ? "fade-out" : ""}`}
    >
      {/* Render cards for all 4 positions */}
      {[0, 1, 2, 3].map((seatIndex) => renderTrickCard(seatIndex))}
    </div>
  );
};

export default TrickArea;
