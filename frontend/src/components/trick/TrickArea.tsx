/**
 * TrickArea - Center table showing current trick's 4 cards
 *
 * Features:
 * - Shows cards played in current trick by position (N/S/E/W)
 * - Animate card entry when played
 * - Fade out animation when trick completes
 * - Winner highlight
 */

import React, { useEffect, useState } from "react";
import { Card } from "../card/Card";
import {
  PLAYER_DIRECTIONS,
  CARD_WIDTH_SMALL,
  CARD_HEIGHT_SMALL,
  TRICK_DISPLAY_DELAY_MS,
} from "../../config/constants";
import "../../styles/trick.scss";

export interface TrickCard {
  cardId: string;
  seatIndex: number;
  isWinning?: boolean;
}

export interface TrickAreaProps {
  cards: TrickCard[];
  trickComplete?: boolean;
  onTrickComplete?: () => void;
  leadSeatIndex?: number;
}

export const TrickArea: React.FC<TrickAreaProps> = ({
  cards,
  trickComplete = false,
  onTrickComplete,
  leadSeatIndex,
}) => {
  const [fadeOut, setFadeOut] = useState(false);

  // Handle trick completion animation
  useEffect(() => {
    if (trickComplete && cards.length === 4) {
      // Start fade out after a delay to let users see the completed trick
      const timer = setTimeout(() => {
        setFadeOut(true);
        // Notify parent after fade animation completes
        const fadeTimer = setTimeout(() => {
          onTrickComplete?.();
          setFadeOut(false);
        }, 500); // Match animation duration
        return () => clearTimeout(fadeTimer);
      }, TRICK_DISPLAY_DELAY_MS);
      return () => clearTimeout(timer);
    }
  }, [trickComplete, cards.length, onTrickComplete]);

  // Get card by seat position
  const getCardForSeat = (seatIndex: number): TrickCard | undefined => {
    return cards.find((c) => c.seatIndex === seatIndex);
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
    <div className={`trick-container ${fadeOut ? "fade-out" : ""}`}>
      {/* Render cards for all 4 positions */}
      {[0, 1, 2, 3].map((seatIndex) => renderTrickCard(seatIndex))}

      {/* Empty state when no cards played */}
      {cards.length === 0 && (
        <div className="trick-empty">
          <span>Play a card</span>
        </div>
      )}
    </div>
  );
};

export default TrickArea;
