/**
 * TricksCounter - Shows tricks won by each team
 *
 * Features:
 * - Displays tricks for humans and bots
 * - Updates in real-time as tricks are won
 */

import React from "react";
import "../../styles/panels.scss";

export interface TricksCounterProps {
  humanTricks: number;
  botTricks: number;
}

export const TricksCounter: React.FC<TricksCounterProps> = ({
  humanTricks,
  botTricks,
}) => {
  return (
    <div className="tricks-counter">
      <span className="tricks-icon">🃏</span>
      <span className="tricks-value">
        {humanTricks} - {botTricks}
      </span>
      <span className="tricks-label">Tricks</span>
    </div>
  );
};

export default TricksCounter;
