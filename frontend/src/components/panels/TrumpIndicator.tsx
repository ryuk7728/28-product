/**
 * TrumpIndicator - Shows the current trump suit
 *
 * Features:
 * - Shows trump suit symbol and rank when revealed
 * - Shows "?" when trump is hidden
 * - Color-coded for suit
 */

import React from "react";
import { SUIT_SYMBOLS } from "../../config/constants";
import "../../styles/panels.scss";

export interface TrumpIndicatorProps {
  trumpSuit: string | null;
  trumpCardId?: string | null;
  isRevealed: boolean;
}

// Parse card ID to get short rank (e.g., "Hearts_Jack" -> "J")
const getShortRank = (cardId: string): string | null => {
  const parts = cardId.split("_");
  if (parts.length === 2) {
    const rank = parts[1];
    switch (rank) {
      case "Jack": return "J";
      case "Nine": return "9";
      case "Ace": return "A";
      case "Ten": return "10";
      case "King": return "K";
      case "Queen": return "Q";
      case "Eight": return "8";
      case "Seven": return "7";
      default: return rank;
    }
  }
  return null;
};

export const TrumpIndicator: React.FC<TrumpIndicatorProps> = ({
  trumpSuit,
  trumpCardId,
  isRevealed,
}) => {
  const suitSymbol = trumpSuit ? SUIT_SYMBOLS[trumpSuit] : null;
  const suitClass = trumpSuit?.toLowerCase() || "";
  const shortRank = trumpCardId ? getShortRank(trumpCardId) : null;

  return (
    <div className="trump-indicator">
      <span className="trump-label">Trump:</span>
      {isRevealed && suitSymbol ? (
        <span className={`trump-suit ${suitClass}`}>
          {shortRank ? `${shortRank} ${suitSymbol}` : suitSymbol}
        </span>
      ) : (
        <span className="trump-hidden">?</span>
      )}
    </div>
  );
};

export default TrumpIndicator;
