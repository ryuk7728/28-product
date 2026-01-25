import type { Card as CardType } from "../api/types";
import { Card } from "./Card";
import { CARD_WIDTH, CARD_HEIGHT, CARD_WIDTH_SMALL, CARD_HEIGHT_SMALL } from "../config/constants";

interface PlayerHandProps {
  cards: CardType[];
  faceUp?: boolean;
  isHorizontal?: boolean;
  isCompact?: boolean;
  highlightedCardIds?: string[];
  selectedCardId?: string | null;
  onCardClick?: (cardId: string) => void;
  disabled?: boolean;
}

export function PlayerHand({
  cards,
  faceUp = true,
  isHorizontal = true,
  isCompact = false,
  highlightedCardIds = [],
  selectedCardId = null,
  onCardClick,
  disabled = false,
}: PlayerHandProps) {
  const width = isCompact ? CARD_WIDTH_SMALL : CARD_WIDTH;
  const height = isCompact ? CARD_HEIGHT_SMALL : CARD_HEIGHT;

  // For horizontal layout, cards overlap
  const overlapOffset = isHorizontal ? -Math.min(width * 0.4, 30) : -Math.min(height * 0.5, 40);

  const highlightSet = new Set(highlightedCardIds);

  if (cards.length === 0) {
    return (
      <div className="flex items-center justify-center text-white/50 text-sm min-h-[60px]">
        No cards
      </div>
    );
  }

  return (
    <div
      className={`flex ${isHorizontal ? "flex-row" : "flex-col"} items-center justify-center`}
      style={{ minHeight: isHorizontal ? height + 20 : undefined }}
    >
      {cards.map((card, index) => {
        const isHighlighted = highlightSet.has(card.cardId);
        const isSelected = selectedCardId === card.cardId;
        // Only legal (highlighted) cards should be clickable when there are legal actions
        const isLegalCard = highlightedCardIds.length === 0 || isHighlighted;
        const canClick = onCardClick && !disabled && isLegalCard;

        return (
          <div
            key={card.cardId}
            className="card-wrapper"
            style={{
              marginLeft: isHorizontal && index > 0 ? overlapOffset : 0,
              marginTop: !isHorizontal && index > 0 ? overlapOffset : 0,
              // Use reverse z-index so leftmost/topmost cards are on top for clicking
              zIndex: isSelected ? 100 : (cards.length - index),
              position: "relative",
            }}
          >
            <Card
              cardId={card.cardId}
              faceUp={faceUp}
              width={width}
              height={height}
              highlighted={isHighlighted}
              selected={isSelected}
              disabled={disabled || (highlightedCardIds.length > 0 && !isHighlighted)}
              onClick={canClick ? () => onCardClick(card.cardId) : undefined}
            />
          </div>
        );
      })}
    </div>
  );
}

export default PlayerHand;
