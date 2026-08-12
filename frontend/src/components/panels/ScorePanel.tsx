import React from "react";
import "../../styles/panels.scss";

export interface ScorePanelProps {
  currentBid: number | null;
  biddingSide: "yours" | "theirs" | null;
  yourPoints: number;
  theirPoints: number;
  yourTeamLabel: string;
  theirTeamLabel: string;
}

export const ScorePanel: React.FC<ScorePanelProps> = ({
  currentBid,
  biddingSide,
  yourPoints,
  theirPoints,
  yourTeamLabel,
  theirTeamLabel,
}) => (
  <div className="game-panel score-panel">
    <table className="score-table">
      <thead><tr><th>Team</th><th>Points</th></tr></thead>
      <tbody>
        <tr>
          <td className="team-name team-humans">{yourTeamLabel}{biddingSide === "yours" && currentBid ? <span className="bid-value"> · {currentBid}</span> : null}</td>
          <td className="score-value team-humans">{yourPoints}</td>
        </tr>
        <tr>
          <td className="team-name team-bots">{theirTeamLabel}{biddingSide === "theirs" && currentBid ? <span className="bid-value"> · {currentBid}</span> : null}</td>
          <td className="score-value team-bots">{theirPoints}</td>
        </tr>
      </tbody>
    </table>
  </div>
);

export default ScorePanel;
