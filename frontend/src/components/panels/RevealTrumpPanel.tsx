/**
 * RevealTrumpPanel - Panel for revealing hidden trump
 *
 * Features:
 * - Option to reveal trump (if player can't follow suit)
 * - Option to keep trump hidden
 * - Shows cards already played in the current trick
 */

import React from "react";
import { Card } from "../card/Card";
import { PLAYER_NAMES, SUIT_SYMBOLS, CARD_WIDTH_SMALL, CARD_HEIGHT_SMALL } from "../../config/constants";
import "../../styles/panels.scss";

export interface PlayedCardInfo {
  cardId: string;
  seatIndex: number;
}

export interface RevealTrumpPanelProps {
  onReveal: () => void;
  onKeepHidden: () => void;
  message?: string;
  playedCards?: PlayedCardInfo[];
  currentSuit?: string;
}

export const RevealTrumpPanel: React.FC<RevealTrumpPanelProps> = ({
  onReveal,
  onKeepHidden,
  message = "You can't follow suit. Reveal trump?",
  playedCards = [],
  currentSuit,
}) => {
  return (
    <div className="game-panel reveal-panel">
      <div className="panel-title">Reveal Trump?</div>
      <div className="panel-subtitle">{message}</div>

      {/* Show cards played so far in this trick */}
      {playedCards.length > 0 && (
        <div className="played-cards-section">
          <div className="played-cards-label">
            Cards played this trick ({currentSuit ? `Lead: ${SUIT_SYMBOLS[currentSuit] || currentSuit}` : ""}):
          </div>
          <div className="played-cards-list">
            {playedCards.map((pc, idx) => (
              <div key={idx} className="played-card-item">
                <span className="player-name">{PLAYER_NAMES[pc.seatIndex]}:</span>
                <Card
                  cardId={pc.cardId}
                  faceUp={true}
                  width={CARD_WIDTH_SMALL * 0.8}
                  height={CARD_HEIGHT_SMALL * 0.8}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="reveal-btns">
        <button className="reveal-btn" onClick={onReveal}>
          Reveal Trump
        </button>
        <button className="keep-btn" onClick={onKeepHidden}>
          Keep Hidden
        </button>
      </div>
    </div>
  );
};

export default RevealTrumpPanel;
