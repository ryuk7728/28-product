/**
 * Card Component - Renders a playing card using @letele/playing-cards
 *
 * Features:
 * - Flip animation (face up / face down)
 * - Hover effects for interactive cards
 * - Highlighted state for legal moves
 * - Disabled state for non-playable cards
 */

import React, { useCallback } from "react";
import type { CSSProperties, MouseEvent } from "react";
// @ts-expect-error - no type declarations for this package
import * as deck from "@letele/playing-cards";
import "../../styles/card.scss";

// Map our cardId format (e.g., "Hearts_Jack") to library format (e.g., "Hj")
const SUIT_MAP: Record<string, string> = {
  Hearts: "H",
  Diamonds: "D",
  Clubs: "C",
  Spades: "S",
};

const RANK_MAP: Record<string, string> = {
  Ace: "a",
  Two: "2",
  Three: "3",
  Four: "4",
  Five: "5",
  Six: "6",
  Seven: "7",
  Eight: "8",
  Nine: "9",
  Ten: "10",
  Jack: "j",
  Queen: "q",
  King: "k",
};

function getCardComponentName(cardId: string): string {
  const [suit, rank] = cardId.split("_");
  const suitLetter = SUIT_MAP[suit];
  const rankLetter = RANK_MAP[rank];

  if (!suitLetter || !rankLetter) {
    console.warn(`Invalid cardId: ${cardId}`);
    return "B1"; // Card back as fallback
  }

  return `${suitLetter}${rankLetter}`;
}

export interface CardProps {
  cardId?: string;
  faceUp?: boolean;
  disabled?: boolean;
  highlighted?: boolean;
  selected?: boolean;
  clickable?: boolean;
  onClick?: (cardId: string) => void;
  width?: number;
  height?: number;
  className?: string;
  style?: CSSProperties;
}

export const Card: React.FC<CardProps> = ({
  cardId,
  faceUp = true,
  disabled = false,
  highlighted = false,
  selected = false,
  clickable = false,
  onClick,
  width = 90,
  height = 126,
  className = "",
  style = {},
}) => {
  const handleClick = useCallback(
    (e: MouseEvent) => {
      e.stopPropagation();
      if (!disabled && onClick && cardId && clickable) {
        onClick(cardId);
      }
    },
    [disabled, onClick, cardId, clickable]
  );

  // Get the card component from the library
  let CardSvg: React.ComponentType<{ style?: CSSProperties }>;

  if (!faceUp || !cardId) {
    CardSvg = (deck as Record<string, React.ComponentType<{ style?: CSSProperties }>>)["B1"];
  } else {
    const componentName = getCardComponentName(cardId);
    CardSvg = (deck as Record<string, React.ComponentType<{ style?: CSSProperties }>>)[componentName];
    if (!CardSvg) {
      console.warn(`Card component not found: ${componentName}`);
      CardSvg = (deck as Record<string, React.ComponentType<{ style?: CSSProperties }>>)["B1"];
    }
  }

  // Build class names
  const containerClasses = [
    "card",
    faceUp ? "flip-up" : "flip-down",
    disabled && "card-disabled",
    highlighted && "card-highlighted",
    selected && "card-selected",
    clickable && !disabled && "card-clickable",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={containerClasses}
      style={{
        width: `${width}px`,
        height: `${height}px`,
        ...style,
      }}
      onClick={handleClick}
      role={clickable && !disabled ? "button" : undefined}
      tabIndex={clickable && !disabled ? 0 : undefined}
      aria-label={cardId ? `${cardId.replace("_", " of ")}` : "Card back"}
      aria-disabled={disabled}
    >
      <div className="card-inner">
        <CardSvg style={{ width: "100%", height: "100%", pointerEvents: "none" }} />
      </div>
    </div>
  );
};

/**
 * Card Back component for convenience
 */
export const CardBack: React.FC<{
  width?: number;
  height?: number;
  className?: string;
  style?: CSSProperties;
}> = ({ width = 90, height = 126, className = "", style = {} }) => {
  return (
    <Card
      faceUp={false}
      width={width}
      height={height}
      className={className}
      style={style}
    />
  );
};

export default Card;
