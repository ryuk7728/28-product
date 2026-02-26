/**
 * ScorePanel - Shows game score and current bid info
 *
 * Features:
 * - Team scores (Humans vs Bots)
 * - Current bid and bidding team
 * - Points collected in current round
 */

import React from "react";
import "../../styles/panels.scss";

export interface ScorePanelProps {
  humanScore: number;
  botScore: number;
  currentBid: number | null;
  biddingTeam: "humans" | "bots" | null;
  humanPoints: number;
  botPoints: number;
  humanTeamLabel?: string;
}

export const ScorePanel: React.FC<ScorePanelProps> = ({
  humanScore,
  botScore,
  currentBid,
  biddingTeam,
  humanPoints,
  botPoints,
  humanTeamLabel = "You & Partner",
}) => {
  return (
    <div className="game-panel score-panel">
      <table className="score-table">
        <thead>
          <tr>
            <th>Team</th>
            <th>Score</th>
            <th>Points</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td className="team-name team-humans">
              {humanTeamLabel}
              {biddingTeam === "humans" && currentBid && (
                <span className="bid-value"> (Bid: {currentBid})</span>
              )}
            </td>
            <td className="score-value team-humans">{humanScore}</td>
            <td>{humanPoints}</td>
          </tr>
          <tr>
            <td className="team-name team-bots">
              Bots
              {biddingTeam === "bots" && currentBid && (
                <span className="bid-value"> (Bid: {currentBid})</span>
              )}
            </td>
            <td className="score-value team-bots">{botScore}</td>
            <td>{botPoints}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
};

export default ScorePanel;
