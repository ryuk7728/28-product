/**
 * PlayerHand - Renders a player's cards with proper positioning
 *
 * Uses the Layout engine for card positioning.
 * Supports horizontal (South/North) and vertical (East/West) layouts.
 */

import React from "react";
import type { Card as CardType } from "../../api/types";
import { Card } from "../card/Card";
import {
  CARD_WIDTH,
  CARD_HEIGHT,
  CARD_WIDTH_SMALL,
  CARD_HEIGHT_SMALL,
  CARD_OVERLAP_HORIZONTAL,
  CARD_OVERLAP_VERTICAL,
  CARD_OVERLAP_SMALL_H,
  CARD_OVERLAP_SMALL_V,
} from "../../config/constants";
import "../../styles/card.scss";

export interface PlayerHandProps {
  cards: CardType[];
  faceUp?: boolean;
  isHorizontal?: boolean;
  isCompact?: boolean;
  noOverlap?: boolean; // If true, cards are fully spread with no overlap (for human players)
  highlightedCardIds?: string[];
  selectedCardId?: string | null;
  disabled?: boolean;
  onCardClick?: (cardId: string) => void;
  dealAnimation?: boolean;
  className?: string;
}

export const PlayerHand: React.FC<PlayerHandProps> = ({
  cards,
  faceUp = true,
  isHorizontal = true,
  isCompact = false,
  noOverlap = false,
  highlightedCardIds = [],
  selectedCardId = null,
  disabled = false,
  onCardClick,
  dealAnimation = false,
  className = "",
}) => {
  // Card dimensions based on compact mode
  const cardWidth = isCompact ? CARD_WIDTH_SMALL : CARD_WIDTH;
  const cardHeight = isCompact ? CARD_HEIGHT_SMALL : CARD_HEIGHT;

  // Gap between cards (for no overlap mode, add small gap; for overlap mode use negative margin effect)
  const cardGap = 8; // Gap between cards when no overlap

  // Spacing: full card width + gap for no overlap, or overlap values for bots
  const spacingH = noOverlap ? cardWidth + cardGap : (isCompact ? CARD_OVERLAP_SMALL_H : CARD_OVERLAP_HORIZONTAL);
  const spacingV = noOverlap ? cardHeight + cardGap : (isCompact ? CARD_OVERLAP_SMALL_V : CARD_OVERLAP_VERTICAL);

  const highlightSet = new Set(highlightedCardIds);

  if (cards.length === 0) {
    return (
      <div
        className="hand-container"
        style={{
          minWidth: cardWidth,
          minHeight: cardHeight,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <span style={{ color: "rgba(255,255,255,0.4)", fontSize: "13px" }}>
          No cards
        </span>
      </div>
    );
  }

  // Calculate container dimensions
  const containerWidth = isHorizontal
    ? (cards.length - 1) * spacingH + cardWidth
    : cardWidth;
  const containerHeight = isHorizontal
    ? cardHeight
    : (cards.length - 1) * spacingV + cardHeight;

  return (
    <div
      className={`hand-container ${isHorizontal ? "horizontal" : "vertical"} ${className}`.trim()}
      style={{
        width: containerWidth,
        height: containerHeight,
        position: "relative",
      }}
    >
      {cards.map((card, index) => {
        const isHighlighted = highlightSet.has(card.cardId);
        const isSelected = selectedCardId === card.cardId;

        // Only highlighted cards are clickable when there are legal actions
        const isLegalCard = highlightedCardIds.length === 0 || isHighlighted;
        const canClick = onCardClick && !disabled && isLegalCard;
        const isCardDisabled = disabled || (highlightedCardIds.length > 0 && !isHighlighted);

        // Calculate position
        const x = isHorizontal ? index * spacingH : 0;
        const y = isHorizontal ? 0 : index * spacingV;

        // Z-index: selected cards on top, then reverse order so first cards are clickable
        let zIndex = cards.length - index;
        if (isSelected) zIndex = 100;
        if (isHighlighted && !isSelected) zIndex = 50 + (cards.length - index);

        return (
          <div
            key={card.cardId}
            className={`card-slot ${dealAnimation ? `deal-animation deal-delay-${index}` : ""}`}
            style={{
              position: "absolute",
              left: isHorizontal ? x : "50%",
              top: isHorizontal ? 0 : y,
              transform: isHorizontal ? undefined : "translateX(-50%)",
              zIndex,
            }}
          >
            <Card
              cardId={card.cardId}
              faceUp={faceUp}
              width={cardWidth}
              height={cardHeight}
              highlighted={isHighlighted}
              selected={isSelected}
              disabled={isCardDisabled}
              clickable={canClick}
              onClick={canClick ? onCardClick : undefined}
            />
          </div>
        );
      })}
    </div>
  );
};

export default PlayerHand;
