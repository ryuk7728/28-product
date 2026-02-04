/**
 * useGameWebSocket - WebSocket hook for game communication
 *
 * Handles:
 * - Connection to game WebSocket
 * - State updates from server
 * - Legal actions updates
 * - Sending player actions (bid, trump select, play card, reveal choice)
 */

import { useEffect, useRef, useCallback, useState } from "react";
import type { GameState, LegalActions, WsMessage } from "../api/types";

export interface UseGameWebSocketOptions {
  gameId: string;
  onStateUpdate?: (state: GameState) => void;
  onLegalActions?: (actions: LegalActions) => void;
  onError?: (message: string) => void;
  onGameAborted?: (reason: string) => void;
  onConnectionChange?: (connected: boolean) => void;
}

export interface UseGameWebSocketReturn {
  connected: boolean;
  gameState: GameState | null;
  legalActions: LegalActions | null;
  sendBid: (seatIndex: number, bidValue: number) => void;
  sendTrumpSelect: (seatIndex: number, cardId: string) => void;
  sendPlayCard: (seatIndex: number, cardId: string) => void;
  sendRevealChoice: (seatIndex: number, reveal: boolean) => void;
  requestState: () => void;
}

export function useGameWebSocket(
  options: UseGameWebSocketOptions
): UseGameWebSocketReturn {
  const { gameId } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [legalActions, setLegalActions] = useState<LegalActions | null>(null);

  // Store callbacks in refs to avoid triggering reconnections
  const callbacksRef = useRef(options);
  callbacksRef.current = options;

  // Connect to WebSocket - only depends on gameId
  useEffect(() => {
    if (!gameId) return;

    // Prevent duplicate connections
    if (wsRef.current?.readyState === WebSocket.OPEN ||
        wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.hostname;
    const port = 8000; // Backend port
    const wsUrl = `${protocol}//${host}:${port}/ws/games/${gameId}`;

    console.log("[WS] Connecting to:", wsUrl);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("[WS] Connected");
      setConnected(true);
      callbacksRef.current.onConnectionChange?.(true);
    };

    ws.onclose = () => {
      console.log("[WS] Disconnected");
      setConnected(false);
      callbacksRef.current.onConnectionChange?.(false);
    };

    ws.onerror = (error) => {
      console.error("[WS] Error:", error);
      callbacksRef.current.onError?.("WebSocket connection error");
    };

    ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        console.log("[WS] Message:", msg.type);

        switch (msg.type) {
          case "STATE_UPDATE":
            console.log("[WS] STATE_UPDATE: trickCards =", msg.state.play?.trickCards?.map((c: { cardId: string }) => c.cardId) || [], "catchNumber =", msg.state.play?.catchNumber);
            setGameState(msg.state);
            callbacksRef.current.onStateUpdate?.(msg.state);
            break;

          case "LEGAL_ACTIONS":
            setLegalActions(msg.actions);
            callbacksRef.current.onLegalActions?.(msg.actions);
            break;

          case "ERROR":
            console.error("[WS] Server error:", msg.message);
            callbacksRef.current.onError?.(msg.message);
            break;

          case "GAME_ABORTED":
            console.warn("[WS] Game aborted:", msg.reason);
            callbacksRef.current.onGameAborted?.(msg.reason);
            break;

          default:
            console.warn("[WS] Unknown message type:", msg);
        }
      } catch (e) {
        console.error("[WS] Failed to parse message:", e);
      }
    };

    return () => {
      console.log("[WS] Cleaning up connection");
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
      wsRef.current = null;
    };
  }, [gameId]); // Only reconnect when gameId changes

  // Send message helper
  const sendMessage = useCallback((msg: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
      console.log("[WS] Sent:", msg);
    } else {
      console.warn("[WS] Cannot send - not connected, state:", wsRef.current?.readyState);
    }
  }, []);

  // Action senders
  const sendBid = useCallback(
    (seatIndex: number, bidValue: number) => {
      sendMessage({
        type: "SUBMIT_BID",
        seatIndex,
        bidValue,
      });
    },
    [sendMessage]
  );

  const sendTrumpSelect = useCallback(
    (seatIndex: number, cardId: string) => {
      sendMessage({
        type: "SELECT_TRUMP_CARD",
        seatIndex,
        cardId,
      });
    },
    [sendMessage]
  );

  const sendPlayCard = useCallback(
    (seatIndex: number, cardId: string) => {
      sendMessage({
        type: "PLAY_CARD",
        seatIndex,
        cardId,
      });
    },
    [sendMessage]
  );

  const sendRevealChoice = useCallback(
    (seatIndex: number, reveal: boolean) => {
      sendMessage({
        type: "CHOOSE_REVEAL_TRUMP",
        seatIndex,
        reveal,
      });
    },
    [sendMessage]
  );

  const requestState = useCallback(() => {
    sendMessage({ type: "GET_STATE" });
  }, [sendMessage]);

  return {
    connected,
    gameState,
    legalActions,
    sendBid,
    sendTrumpSelect,
    sendPlayCard,
    sendRevealChoice,
    requestState,
  };
}

export default useGameWebSocket;
