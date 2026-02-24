/**
 * PlayerAvatar - Name tag with avatar and active turn indicator
 *
 * Features:
 * - Colored avatar (blue for humans, red for bots)
 * - Active player "breathing" animation
 * - Bidder badge
 * - Current bid display
 * - Thinking indicator for bots
 */

import React from "react";
import { PLAYER_NAMES, SEAT_TYPES } from "../../config/constants";
import "../../styles/player.scss";

export interface PlayerAvatarProps {
  seatIndex: number;
  isActive?: boolean;
  isBidder?: boolean;
  currentBid?: number | null;
  isThinking?: boolean;
  speechBubbleText?: string | null;
  speechBubbleDirection?: "left" | "right";
}

export const PlayerAvatar: React.FC<PlayerAvatarProps> = ({
  seatIndex,
  isActive = false,
  isBidder = false,
  currentBid,
  isThinking = false,
  speechBubbleText = null,
  speechBubbleDirection,
}) => {
  const name = PLAYER_NAMES[seatIndex];
  const isBot = SEAT_TYPES[seatIndex] === "bot";
  const initial = name.charAt(0).toUpperCase();

  return (
    <div className="player-info">
      {speechBubbleText && speechBubbleDirection && (
        <div className={`speech-bubble ${speechBubbleDirection}`}>
          {speechBubbleText}
        </div>
      )}

      {/* Main player tag */}
      <div className={`player-tag ${isActive ? "active" : ""}`}>
        {isActive ? (
          <div className="player-tag-inner">
            <div className={`player-avatar ${isBot ? "bot" : "human"}`}>
              {initial}
            </div>
            <span className="player-name">{name}</span>
            {isBidder && <span className="bidder-badge">Bidder</span>}
          </div>
        ) : (
          <>
            <div className={`player-avatar ${isBot ? "bot" : "human"}`}>
              {initial}
            </div>
            <span className="player-name">{name}</span>
            {isBidder && <span className="bidder-badge">Bidder</span>}
          </>
        )}
      </div>

      {/* Current bid display */}
      {currentBid !== undefined && currentBid !== null && currentBid > 0 && (
        <div className="player-bid">Bid: {currentBid}</div>
      )}

      {/* Thinking indicator for bots */}
      {isThinking && isBot && (
        <div className="thinking-indicator">
          <span>Thinking</span>
          <div className="thinking-dots">
            <span className="dot" />
            <span className="dot" />
            <span className="dot" />
          </div>
        </div>
      )}
    </div>
  );
};

export default PlayerAvatar;
