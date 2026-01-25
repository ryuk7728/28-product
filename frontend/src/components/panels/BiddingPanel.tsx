/**
 * BiddingPanel - Panel for placing bids during bidding rounds
 *
 * Features:
 * - Grid of bid values (14-28)
 * - Pass button
 * - Redeal button (if applicable)
 * - Shows minimum bid and current high bid
 */

import React from "react";
import "../../styles/panels.scss";

export interface BiddingPanelProps {
  minBid: number;
  maxBid?: number;
  currentHighBid: number | null;
  currentBidder: string | null;
  canPass: boolean;
  canRedeal: boolean;
  onBid: (value: number) => void;
  onPass: () => void;
  onRedeal?: () => void;
  isRound2?: boolean;
}

export const BiddingPanel: React.FC<BiddingPanelProps> = ({
  minBid,
  maxBid = 28,
  currentHighBid,
  currentBidder,
  canPass,
  canRedeal,
  onBid,
  onPass,
  onRedeal,
  isRound2 = false,
}) => {
  // Generate bid values from minBid to maxBid
  const bidValues: number[] = [];
  for (let i = minBid; i <= maxBid; i++) {
    bidValues.push(i);
  }

  return (
    <div className="game-panel bidding-panel">
      <div className="panel-title">
        {isRound2 ? "Round 2 Bidding" : "Place Your Bid"}
      </div>
      <div className="panel-subtitle">
        {currentHighBid && currentBidder
          ? `Current: ${currentHighBid} by ${currentBidder}`
          : "No bids yet"}
      </div>

      <div className="bid-grid">
        {bidValues.map((value) => (
          <button
            key={value}
            className="bid-btn"
            onClick={() => onBid(value)}
            disabled={currentHighBid !== null && value <= currentHighBid}
          >
            {value}
          </button>
        ))}
      </div>

      <div className="action-btns">
        {canPass && (
          <button className="pass-btn" onClick={onPass}>
            Pass
          </button>
        )}
        {canRedeal && onRedeal && (
          <button className="redeal-btn" onClick={onRedeal}>
            Redeal
          </button>
        )}
      </div>
    </div>
  );
};

export default BiddingPanel;
