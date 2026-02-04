/**
 * TrumpRevealOverlay - Full-screen overlay showing the revealed trump card
 *
 * Features:
 * - Shows the trump card prominently in the center
 * - Displays for 5 seconds before auto-dismissing
 * - Dramatic animation for reveal
 */

import React, { useEffect, useState } from "react";
import { Card } from "../card/Card";
import { SUIT_SYMBOLS, TRUMP_REVEAL_DISPLAY_MS, CARD_WIDTH, CARD_HEIGHT } from "../../config/constants";
import "../../styles/panels.scss";

export interface TrumpRevealOverlayProps {
  trumpSuit: string;
  trumpCardId?: string; // Optional - if we know the exact card
  onComplete: () => void;
}

// Parse card ID to get rank (e.g., "Hearts_Jack" -> "Jack")
const parseCardRank = (cardId: string): string | null => {
  const parts = cardId.split("_");
  if (parts.length === 2) {
    return parts[1];
  }
  return null;
};

export const TrumpRevealOverlay: React.FC<TrumpRevealOverlayProps> = ({
  trumpSuit,
  trumpCardId,
  onComplete,
}) => {
  const [fadeOut, setFadeOut] = useState(false);

  useEffect(() => {
    // Start fade out before completion
    const fadeTimer = setTimeout(() => {
      setFadeOut(true);
    }, TRUMP_REVEAL_DISPLAY_MS - 500);

    // Complete after full display time
    const completeTimer = setTimeout(() => {
      onComplete();
    }, TRUMP_REVEAL_DISPLAY_MS);

    return () => {
      clearTimeout(fadeTimer);
      clearTimeout(completeTimer);
    };
  }, [onComplete]);

  const suitSymbol = SUIT_SYMBOLS[trumpSuit] || trumpSuit;
  const isRed = trumpSuit === "Hearts" || trumpSuit === "Diamonds";
  const cardRank = trumpCardId ? parseCardRank(trumpCardId) : null;

  return (
    <div className={`trump-reveal-overlay ${fadeOut ? "fade-out" : ""}`}>
      <div className="trump-reveal-content">
        <div className="trump-reveal-title">Trump Revealed!</div>

        <div className="trump-reveal-card-container">
          {trumpCardId ? (
            <Card
              cardId={trumpCardId}
              faceUp={true}
              width={CARD_WIDTH * 1.8}
              height={CARD_HEIGHT * 1.8}
            />
          ) : (
            <div className={`trump-suit-display ${isRed ? "red" : "black"}`}>
              {suitSymbol}
            </div>
          )}
        </div>

        <div className={`trump-suit-name ${isRed ? "red" : "black"}`}>
          {cardRank ? `${cardRank} of ${trumpSuit}` : `${suitSymbol} ${trumpSuit}`}
        </div>

        <div className="trump-reveal-hint">
          Game continues in a moment...
        </div>
      </div>
    </div>
  );
};

export default TrumpRevealOverlay;
