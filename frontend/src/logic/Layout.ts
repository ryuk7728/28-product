/**
 * VISUAL LOGIC: Calculates the X/Y coordinates for card positioning.
 *
 * Ported from Bridge reference project, adapted for 28 card game (8 cards per hand).
 *
 * - South/North (seats 1, 3): Cards fan out horizontally, centered
 * - West/East (seats 2, 0): Cards stack vertically, centered
 */

export interface PositionInfo {
  horizonOffset: number;    // Horizontal overlap between cards
  verticalOffset: number;   // Vertical overlap between cards (for side players)
  cardWidth: number;
  cardHeight: number;
  width: number;            // Container width
  height: number;           // Container height
  playerTagHeight: number;  // Height of player name tag
}

export interface HandStyle {
  top?: number;
  left?: number;
  width?: number;
  height?: number;
}

export interface CardPosition {
  x: number;
  y: number;
  zIndex: number;
}

/**
 * Layout calculator for 4-player card game
 *
 * Seat positions:
 * - 0: East (right side, vertical stack)
 * - 1: South (bottom, horizontal fan) - Main player "You"
 * - 2: West (left side, vertical stack)
 * - 3: North (top, horizontal fan) - Partner
 */
export default class Layout {
  private cardCounts: number[];
  private posInfo: PositionInfo;

  constructor(cardCounts: number[], posInfo: PositionInfo) {
    this.cardCounts = cardCounts; // [seat0Count, seat1Count, seat2Count, seat3Count]
    this.posInfo = posInfo;
  }

  /**
   * Get the container style for each player's hand
   * Returns array of 4 style objects (one per seat)
   */
  getContainerStyles(): HandStyle[] {
    return this.cardCounts.map((count, seatIndex) => {
      // Seats 1 & 3 are horizontal (South/North)
      if (seatIndex === 1 || seatIndex === 3) {
        return {
          left: this.getHorizontalPosition(count),
          width: this.getHorizontalWidth(count),
        };
      }
      // Seats 0 & 2 are vertical (East/West)
      return {
        top: this.getVerticalPosition(count),
        height: this.getVerticalHeight(count),
      };
    });
  }

  /**
   * Calculate X position for horizontal hands (centering logic)
   */
  private getHorizontalPosition(cardCount: number): number {
    const { horizonOffset, width, cardWidth } = this.posInfo;
    const totalWidth = (cardCount - 1) * horizonOffset + cardWidth;
    return (width - totalWidth) / 2;
  }

  /**
   * Calculate width needed for horizontal hand container
   */
  private getHorizontalWidth(cardCount: number): number {
    const { horizonOffset, cardWidth } = this.posInfo;
    const minWidth = cardWidth + 20;
    const calculatedWidth = (cardCount - 1) * horizonOffset + cardWidth;
    return Math.max(calculatedWidth, minWidth);
  }

  /**
   * Calculate Y position for vertical hands (centering logic)
   */
  private getVerticalPosition(cardCount: number): number {
    const { verticalOffset, height, cardHeight, playerTagHeight } = this.posInfo;
    const totalHeight = (cardCount - 1) * verticalOffset + cardHeight;
    return (height - totalHeight - playerTagHeight) / 2;
  }

  /**
   * Calculate height needed for vertical hand container
   */
  private getVerticalHeight(cardCount: number): number {
    const { verticalOffset, cardHeight } = this.posInfo;
    const minHeight = cardHeight + 20;
    const calculatedHeight = (cardCount - 1) * verticalOffset + cardHeight;
    return Math.max(calculatedHeight, minHeight);
  }

  /**
   * Get individual card positions within a hand
   * @param seatIndex - Which player (0-3)
   * @param cardIndex - Which card in hand (0-7 for 28 game)
   * @param totalCards - Total cards in this hand
   */
  getCardPosition(seatIndex: number, cardIndex: number, _totalCards: number): CardPosition {
    const { horizonOffset, verticalOffset } = this.posInfo;
    const isHorizontal = seatIndex === 1 || seatIndex === 3;

    if (isHorizontal) {
      return {
        x: cardIndex * horizonOffset,
        y: 0,
        zIndex: cardIndex, // Later cards on top for horizontal
      };
    } else {
      return {
        x: 0,
        y: cardIndex * verticalOffset,
        zIndex: cardIndex,
      };
    }
  }

  /**
   * Static helper to get default position info based on screen size
   */
  static getDefaultPositionInfo(
    containerWidth: number,
    containerHeight: number,
    isCompact: boolean = false
  ): PositionInfo {
    const cardWidth = isCompact ? 70 : 90;
    const cardHeight = isCompact ? 98 : 126;

    return {
      horizonOffset: isCompact ? 25 : 35,  // How much cards overlap horizontally
      verticalOffset: isCompact ? 30 : 40, // How much cards overlap vertically
      cardWidth,
      cardHeight,
      width: containerWidth,
      height: containerHeight,
      playerTagHeight: 50,
    };
  }
}
