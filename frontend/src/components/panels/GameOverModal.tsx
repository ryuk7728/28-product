import React from "react";
import "../../styles/panels.scss";

export interface GameOverModalProps {
  didWin: boolean;
  yourPoints: number;
  theirPoints: number;
  bidValue: number;
  bidderName: string;
  contractMade: boolean;
  onNewGame: () => void;
  newGameDisabled?: boolean;
  newGameLabel?: string;
  statusMessage?: string | null;
}

export const GameOverModal: React.FC<GameOverModalProps> = ({
  didWin,
  yourPoints,
  theirPoints,
  bidValue,
  bidderName,
  contractMade,
  onNewGame,
  newGameDisabled = false,
  newGameLabel = "Play again",
  statusMessage,
}) => (
  <div className="game-over-overlay">
    <div className="game-over-modal">
      <div className="result-kicker">GAME COMPLETE</div>
      <div className={`result-title ${didWin ? "win" : "lose"}`}>
        {didWin ? "Your team won" : "Your team lost"}
      </div>
      <div className="result-score"><strong>{yourPoints}</strong><span>—</span><strong>{theirPoints}</strong></div>
      <div className="result-details">
        <div className="score-line">{bidderName} {contractMade ? "made" : "missed"} the {bidValue} contract.</div>
      </div>
      {statusMessage ? <div className="rematch-status">{statusMessage}</div> : null}
      <button className="new-game-btn" onClick={onNewGame} disabled={newGameDisabled}>{newGameLabel}</button>
    </div>
  </div>
);

export default GameOverModal;
