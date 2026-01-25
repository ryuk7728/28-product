/**
 * TrumpSelectPanel - Panel for selecting trump card after winning bid
 *
 * Features:
 * - Shows player's cards to select from
 * - Only allows selecting from valid cards
 * - Shows hint about trump selection
 */

import React from "react";
import { Card } from "../card/Card";
import type { Card as CardType } from "../../api/types";
import { CARD_WIDTH_SMALL, CARD_HEIGHT_SMALL } from "../../config/constants";
import "../../styles/panels.scss";

export interface TrumpSelectPanelProps {
  cards: CardType[];
  onSelect: (cardId: string) => void;
}

export const TrumpSelectPanel: React.FC<TrumpSelectPanelProps> = ({
  cards,
  onSelect,
}) => {
  return (
    <div className="game-panel trump-select-panel">
      <div className="panel-title">Select Trump Card</div>
      <div className="panel-subtitle">Choose a card to set as trump</div>
      <div className="trump-hint">
        The suit of this card will be the hidden trump
      </div>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 8,
          justifyContent: "center",
          maxWidth: 360,
        }}
      >
        {cards.map((card) => (
          <Card
            key={card.cardId}
            cardId={card.cardId}
            faceUp={true}
            width={CARD_WIDTH_SMALL}
            height={CARD_HEIGHT_SMALL}
            clickable={true}
            highlighted={true}
            onClick={() => onSelect(card.cardId)}
          />
        ))}
      </div>
    </div>
  );
};

export default TrumpSelectPanel;
