/**
 * GameOverModal - End of game overlay
 *
 * Features:
 * - Shows win/lose result
 * - Final scores and points
 * - New game button
 */

import React from "react";
import "../../styles/panels.scss";

export interface GameOverModalProps {
  didWin: boolean;
  humanScore: number;
  botScore: number;
  humanPoints: number;
  botPoints: number;
  bidValue: number;
  biddingTeam: "humans" | "bots";
  onNewGame: () => void;
}

export const GameOverModal: React.FC<GameOverModalProps> = ({
  didWin,
  humanScore,
  botScore,
  humanPoints,
  botPoints,
  bidValue,
  biddingTeam,
  onNewGame,
}) => {
  const bidderWon =
    (biddingTeam === "humans" && humanPoints >= bidValue) ||
    (biddingTeam === "bots" && botPoints >= bidValue);

  return (
    <div className="game-over-overlay">
      <div className="game-over-modal">
        <div className={`result-title ${didWin ? "win" : "lose"}`}>
          {didWin ? "You Win!" : "You Lose"}
        </div>

        <div className="result-details">
          <div className="score-line">
            <strong>Final Score:</strong> You {humanScore} - {botScore} Bots
          </div>
          <div className="score-line">
            <strong>Points:</strong> You {humanPoints} - {botPoints} Bots
          </div>
          <div className="score-line">
            <strong>Bid:</strong> {bidValue} by {biddingTeam === "humans" ? "You" : "Bots"}
            {" - "}
            {bidderWon ? "Made!" : "Failed!"}
          </div>
        </div>

        <button className="new-game-btn" onClick={onNewGame}>
          New Game
        </button>
      </div>
    </div>
  );
};

export default GameOverModal;
