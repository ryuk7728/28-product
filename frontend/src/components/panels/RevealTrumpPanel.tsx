/**
 * RevealTrumpPanel - Panel for revealing hidden trump
 *
 * Features:
 * - Option to reveal trump (if player can't follow suit)
 * - Option to keep trump hidden
 */

import React from "react";
import "../../styles/panels.scss";

export interface RevealTrumpPanelProps {
  onReveal: () => void;
  onKeepHidden: () => void;
  message?: string;
}

export const RevealTrumpPanel: React.FC<RevealTrumpPanelProps> = ({
  onReveal,
  onKeepHidden,
  message = "You can't follow suit. Reveal trump?",
}) => {
  return (
    <div className="game-panel reveal-panel">
      <div className="panel-title">Reveal Trump?</div>
      <div className="panel-subtitle">{message}</div>

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
