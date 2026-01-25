import type { Card as CardType } from "../api/types";
import { Card } from "./Card";
import { CARD_WIDTH, CARD_HEIGHT, PLAYER_DIRECTIONS } from "../config/constants";

interface CenterPlayAreaProps {
  trickCards: CardType[];
  leaderIndex: number;
}

// Position offsets for played cards based on which player played them
const CARD_POSITIONS: Record<string, { x: number; y: number; rotate: number }> = {
  bottom: { x: 0, y: 40, rotate: 0 },
  top: { x: 0, y: -40, rotate: 180 },
  left: { x: -60, y: 0, rotate: 90 },
  right: { x: 60, y: 0, rotate: -90 },
};

export function CenterPlayArea({ trickCards, leaderIndex }: CenterPlayAreaProps) {
  if (trickCards.length === 0) {
    return (
      <div className="flex items-center justify-center w-full h-full">
        <div className="text-white/30 text-sm">Play area</div>
      </div>
    );
  }

  // Calculate which seat played each card based on leader and order
  return (
    <div className="relative w-[300px] h-[200px]">
      {trickCards.map((card, index) => {
        // Calculate the seat index of who played this card
        const seatIndex = (leaderIndex + index) % 4;
        const position = PLAYER_DIRECTIONS[seatIndex];
        const { x, y, rotate } = CARD_POSITIONS[position];

        return (
          <div
            key={card.cardId}
            className="absolute left-1/2 top-1/2 transition-all duration-300 ease-out"
            style={{
              transform: `translate(-50%, -50%) translate(${x}px, ${y}px) rotate(${rotate}deg)`,
              zIndex: index + 1,
            }}
          >
            <Card
              cardId={card.cardId}
              faceUp={true}
              width={CARD_WIDTH * 0.9}
              height={CARD_HEIGHT * 0.9}
            />
          </div>
        );
      })}
    </div>
  );
}

export default CenterPlayArea;
