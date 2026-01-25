/**
 * TrumpIndicator - Shows the current trump suit
 *
 * Features:
 * - Shows trump suit symbol when revealed
 * - Shows "?" when trump is hidden
 * - Color-coded for suit
 */

import React from "react";
import { SUIT_SYMBOLS } from "../../config/constants";
import "../../styles/panels.scss";

export interface TrumpIndicatorProps {
  trumpSuit: string | null;
  isRevealed: boolean;
}

export const TrumpIndicator: React.FC<TrumpIndicatorProps> = ({
  trumpSuit,
  isRevealed,
}) => {
  const suitSymbol = trumpSuit ? SUIT_SYMBOLS[trumpSuit] : null;
  const suitClass = trumpSuit?.toLowerCase() || "";

  return (
    <div className="trump-indicator">
      <span className="trump-label">Trump:</span>
      {isRevealed && suitSymbol ? (
        <span className={`trump-suit ${suitClass}`}>{suitSymbol}</span>
      ) : (
        <span className="trump-hidden">?</span>
      )}
    </div>
  );
};

export default TrumpIndicator;
