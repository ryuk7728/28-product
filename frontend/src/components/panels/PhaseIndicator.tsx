/**
 * PhaseIndicator - Shows current game phase
 *
 * Features:
 * - Displays current phase name
 * - Shows whose turn it is
 */

import React from "react";
import { PHASE_DISPLAY_TEXT, PLAYER_NAMES } from "../../config/constants";
import "../../styles/panels.scss";

export interface PhaseIndicatorProps {
  phase: string;
  currentPlayerSeat?: number;
  currentPlayerName?: string | null;
}

export const PhaseIndicator: React.FC<PhaseIndicatorProps> = ({
  phase,
  currentPlayerSeat,
  currentPlayerName,
}) => {
  const phaseText = PHASE_DISPLAY_TEXT[phase] || phase;
  const playerName =
    currentPlayerName ??
    (currentPlayerSeat !== undefined ? PLAYER_NAMES[currentPlayerSeat] : null);

  return (
    <div
      style={{
        background: "rgba(0, 0, 0, 0.6)",
        color: "white",
        padding: "8px 16px",
        borderRadius: 8,
        fontSize: 13,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 2,
      }}
    >
      <span style={{ fontWeight: 600 }}>{phaseText}</span>
      {playerName && (
        <span style={{ fontSize: 11, opacity: 0.8 }}>
          {playerName}'s turn
        </span>
      )}
    </div>
  );
};

export default PhaseIndicator;
