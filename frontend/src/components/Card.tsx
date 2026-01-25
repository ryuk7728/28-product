import type { CSSProperties, MouseEvent } from "react";
import { useCallback } from "react";
// @ts-expect-error - no type declarations for this package
import * as deck from "@letele/playing-cards";
import { CARD_WIDTH, CARD_HEIGHT, SUIT_SYMBOLS, SUIT_COLORS } from "../config/constants";

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

interface CardProps {
  cardId?: string; // Format: "Hearts_Jack", "Spades_Nine", etc.
  faceUp?: boolean;
  disabled?: boolean;
  highlighted?: boolean;
  selected?: boolean;
  onClick?: (cardId: string) => void;
  onMouseDown?: (cardId: string) => void;
  onMouseUp?: (cardId: string) => void;
  width?: number;
  height?: number;
  className?: string;
  style?: CSSProperties;
  animationDelay?: number;
  showAnimation?: boolean;
}

// Convert our cardId format to library component name
function getCardComponentName(cardId: string): string {
  const [suit, rank] = cardId.split("_");
  const suitLetter = SUIT_MAP[suit];
  const rankLetter = RANK_MAP[rank];

  if (!suitLetter || !rankLetter) {
    console.warn(`Invalid cardId: ${cardId}`);
    return "B1"; // Return card back as fallback
  }

  return `${suitLetter}${rankLetter}`;
}

// Parse cardId to get suit and rank
export function parseCardId(cardId: string): { suit: string; rank: string } {
  const [suit, rank] = cardId.split("_");
  return { suit, rank };
}

// Get suit symbol for display
export function getSuitSymbol(suit: string): string {
  return SUIT_SYMBOLS[suit] || "?";
}

// Get suit color
export function getSuitColor(suit: string): string {
  return SUIT_COLORS[suit] || "#1f2937";
}

export function Card({
  cardId,
  faceUp = true,
  disabled = false,
  highlighted = false,
  selected = false,
  onClick,
  onMouseDown,
  onMouseUp,
  width = CARD_WIDTH,
  height = CARD_HEIGHT,
  className = "",
  style = {},
  animationDelay = 0,
  showAnimation = false,
}: CardProps) {
  const handleClick = useCallback(
    (e: MouseEvent) => {
      e.stopPropagation();
      if (!disabled && onClick && cardId) {
        onClick(cardId);
      }
    },
    [disabled, onClick, cardId]
  );

  const handleMouseDown = useCallback(
    (e: MouseEvent) => {
      e.stopPropagation();
      if (onMouseDown && cardId) {
        onMouseDown(cardId);
      }
    },
    [onMouseDown, cardId]
  );

  const handleMouseUp = useCallback(
    (e: MouseEvent) => {
      e.stopPropagation();
      if (onMouseUp && cardId) {
        onMouseUp(cardId);
      }
    },
    [onMouseUp, cardId]
  );

  // Get the appropriate card component
  let CardComponent: React.ComponentType<{ style?: CSSProperties }>;

  if (!faceUp || !cardId) {
    // Show card back
    CardComponent = (deck as Record<string, React.ComponentType<{ style?: CSSProperties }>>)["B1"];
  } else {
    const componentName = getCardComponentName(cardId);
    CardComponent = (deck as Record<string, React.ComponentType<{ style?: CSSProperties }>>)[
      componentName
    ];

    if (!CardComponent) {
      console.warn(`Card component not found: ${componentName}`);
      CardComponent = (deck as Record<string, React.ComponentType<{ style?: CSSProperties }>>)["B1"];
    }
  }

  // Build class names
  const containerClasses = [
    "card-container",
    disabled && "card-disabled",
    highlighted && "card-highlighted",
    selected && "card-selected",
    showAnimation && "animate-card-deal",
    !disabled && onClick && "cursor-pointer",
  ]
    .filter(Boolean)
    .join(" ");

  // Build inline styles
  const containerStyle: CSSProperties = {
    width: `${width}px`,
    height: `${height}px`,
    position: "relative",
    flexShrink: 0,
    animationDelay: showAnimation ? `${animationDelay}ms` : undefined,
    ...style,
  };

  return (
    <div
      className={`${containerClasses} ${className}`}
      style={containerStyle}
      onClick={handleClick}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      role={onClick && !disabled ? "button" : undefined}
      tabIndex={onClick && !disabled ? 0 : undefined}
      aria-label={cardId ? `${cardId.replace("_", " of ")}` : "Card back"}
      aria-disabled={disabled}
    >
      {/* pointer-events: none ensures clicks pass through to the wrapper div */}
      <CardComponent style={{ width: "100%", height: "100%", pointerEvents: "none" }} />
    </div>
  );
}

// Card Back component for convenience
export function CardBack({
  width = CARD_WIDTH,
  height = CARD_HEIGHT,
  className = "",
  style = {},
}: {
  width?: number;
  height?: number;
  className?: string;
  style?: CSSProperties;
}) {
  return <Card faceUp={false} width={width} height={height} className={className} style={style} />;
}

export default Card;
