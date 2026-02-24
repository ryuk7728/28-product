/**
 * GameArena - Main game table container
 *
 * Renders:
 * - Green felt background
 * - All 4 player positions with hands
 * - Center trick area
 * - UI panels (score, trump indicator)
 */

import React from "react";
import type { ReactNode } from "react";
import { PlayerAvatar } from "../player";
import { PLAYER_DIRECTIONS } from "../../config/constants";
import "../../styles/table.scss";

export interface PlayerData {
  seatIndex: number;
  isActive: boolean;
  isBidder: boolean;
  currentBid: number | null;
  isThinking: boolean;
  speechBubbleText?: string | null;
  handContent: ReactNode;
}

export interface GameArenaProps {
  players: PlayerData[];
  centerContent?: ReactNode;
  uiPanels?: ReactNode;  // Legacy - kept for backward compatibility
  uiPanelInfo?: ReactNode;  // Info panel (phase, trump, tricks)
  uiPanelScore?: ReactNode; // Score panel (scoreboard)
  overlay?: ReactNode;
}

export const GameArena: React.FC<GameArenaProps> = ({
  players,
  centerContent,
  uiPanels,
  uiPanelInfo,
  uiPanelScore,
  overlay,
}) => {
  return (
    <div className="game-arena">
      {/* Hands container */}
      <div className="hands-container">
        {players.map((player) => {
          const direction = PLAYER_DIRECTIONS[player.seatIndex];

          return (
            <div
              key={player.seatIndex}
              className={`player-area ${direction}`}
              data-seat={player.seatIndex}
            >
              {/* For South player, show hand first then avatar */}
              {direction === "south" ? (
                <>
                  {player.handContent}
                  <PlayerAvatar
                    seatIndex={player.seatIndex}
                    isActive={player.isActive}
                    isBidder={player.isBidder}
                    currentBid={player.currentBid}
                    isThinking={player.isThinking}
                    speechBubbleText={player.speechBubbleText}
                    speechBubbleDirection={
                      direction === "west" ? "left" : direction === "east" ? "right" : undefined
                    }
                  />
                </>
              ) : direction === "north" ? (
                <>
                  <PlayerAvatar
                    seatIndex={player.seatIndex}
                    isActive={player.isActive}
                    isBidder={player.isBidder}
                    currentBid={player.currentBid}
                    isThinking={player.isThinking}
                    speechBubbleText={player.speechBubbleText}
                    speechBubbleDirection={
                      direction === "west" ? "left" : direction === "east" ? "right" : undefined
                    }
                  />
                  {player.handContent}
                </>
              ) : (
                // East/West - avatar on top, cards below
                <>
                  <PlayerAvatar
                    seatIndex={player.seatIndex}
                    isActive={player.isActive}
                    isBidder={player.isBidder}
                    currentBid={player.currentBid}
                    isThinking={player.isThinking}
                    speechBubbleText={player.speechBubbleText}
                    speechBubbleDirection={
                      direction === "west" ? "left" : direction === "east" ? "right" : undefined
                    }
                  />
                  {player.handContent}
                </>
              )}
            </div>
          );
        })}
      </div>

      {/* Center trick area */}
      <div className="trick-area">
        <div className="trick-area-inner">{centerContent}</div>
      </div>

      {/* Legacy UI Panels (top-right) - for backward compatibility */}
      {uiPanels && <div className="ui-panels">{uiPanels}</div>}

      {/* Info Panel (phase, trump, tricks) - independently positioned */}
      {uiPanelInfo && <div className="ui-panel-info">{uiPanelInfo}</div>}

      {/* Score Panel (scoreboard) - independently positioned */}
      {uiPanelScore && <div className="ui-panel-score">{uiPanelScore}</div>}

      {/* Overlay (modals, game over, etc) */}
      {overlay}
    </div>
  );
};

export default GameArena;
