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
import type {
  GameState,
  LegalActions,
  RematchStatusMessage,
  WsMessage,
} from "../api/types";

export interface UseGameWebSocketOptions {
  gameId?: string;
  roomCode?: string;
  playerToken?: string;
  spectateMode?: boolean;
  onStateUpdate?: (state: GameState) => void;
  onLegalActions?: (actions: LegalActions) => void;
  onError?: (message: string) => void;
  onGameAborted?: (reason: string) => void;
  onRematchStatus?: (message: RematchStatusMessage) => void;
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
  requestNewGame: () => void;
  requestState: () => void;
}

export function useGameWebSocket(
  options: UseGameWebSocketOptions
): UseGameWebSocketReturn {
  const { gameId, roomCode, playerToken, spectateMode = false } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [legalActions, setLegalActions] = useState<LegalActions | null>(null);
  const [reconnectTick, setReconnectTick] = useState(0);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const shouldReconnectRef = useRef(true);
  const latestStateSeqRef = useRef(-1);

  // Store callbacks in refs to avoid triggering reconnections
  const callbacksRef = useRef(options);
  callbacksRef.current = options;

  const scheduleReconnect = useCallback(() => {
    if (!shouldReconnectRef.current) return;
    if (reconnectTimerRef.current !== null) return;

    const attempt = reconnectAttemptsRef.current + 1;
    reconnectAttemptsRef.current = attempt;
    const delayMs = Math.min(10000, 500 * Math.pow(2, Math.min(attempt - 1, 5)));

    reconnectTimerRef.current = window.setTimeout(() => {
      reconnectTimerRef.current = null;
      setReconnectTick((v) => v + 1);
    }, delayMs);
  }, []);

  useEffect(() => {
    // Reset stale-state guard when switching connection identity.
    latestStateSeqRef.current = -1;
    reconnectAttemptsRef.current = 0;
  }, [gameId, roomCode, playerToken, spectateMode]);

  // Connect to WebSocket - only depends on gameId
  useEffect(() => {
    if (!gameId && !roomCode) return;
    shouldReconnectRef.current = true;

    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    // Prevent duplicate connections
    if (wsRef.current?.readyState === WebSocket.OPEN ||
        wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    const wsBase = import.meta.env.VITE_WS_BASE_URL as string | undefined;
    let wsUrl: string;
    if (wsBase && wsBase.trim() !== "") {
      const trimmed = wsBase.replace(/\/$/, "");
      if (roomCode) {
        if (spectateMode) {
          wsUrl = `${trimmed}/ws/rooms/${encodeURIComponent(roomCode)}?spectator=1`;
        } else {
          const tokenQuery = playerToken
            ? `?token=${encodeURIComponent(playerToken)}`
            : "";
          wsUrl = `${trimmed}/ws/rooms/${encodeURIComponent(roomCode)}${tokenQuery}`;
        }
      } else {
        wsUrl = `${trimmed}/ws/games/${gameId}`;
      }
    } else {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.hostname;
      const port = 8000; // Backend port
      if (roomCode) {
        if (spectateMode) {
          wsUrl = `${protocol}//${host}:${port}/ws/rooms/${encodeURIComponent(roomCode)}?spectator=1`;
        } else {
          const tokenQuery = playerToken
            ? `?token=${encodeURIComponent(playerToken)}`
            : "";
          wsUrl = `${protocol}//${host}:${port}/ws/rooms/${encodeURIComponent(roomCode)}${tokenQuery}`;
        }
      } else {
        wsUrl = `${protocol}//${host}:${port}/ws/games/${gameId}`;
      }
    }

    console.log("[WS] Connecting to:", wsUrl);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("[WS] Connected");
      setConnected(true);
      reconnectAttemptsRef.current = 0;
      callbacksRef.current.onConnectionChange?.(true);
      try {
        ws.send(JSON.stringify({ type: "GET_STATE" }));
      } catch {
        // Ignore transport race errors.
      }
    };

    ws.onclose = () => {
      console.log("[WS] Disconnected");
      setConnected(false);
      callbacksRef.current.onConnectionChange?.(false);
      scheduleReconnect();
    };

    ws.onerror = (error) => {
      console.error("[WS] Error:", error);
      callbacksRef.current.onError?.("WebSocket connection error");
      if (ws.readyState !== WebSocket.OPEN) {
        scheduleReconnect();
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        console.log("[WS] Message:", msg.type);

        switch (msg.type) {
          case "STATE_UPDATE":
            if (typeof msg.stateSeq === "number") {
              if (msg.stateSeq <= latestStateSeqRef.current) {
                console.warn("[WS] Ignoring stale STATE_UPDATE seq:", msg.stateSeq);
                break;
              }
              latestStateSeqRef.current = msg.stateSeq;
            }
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

          case "REMATCH_STATUS":
            callbacksRef.current.onRematchStatus?.(msg);
            break;

          default:
            console.warn("[WS] Unknown message type:", msg);
        }
      } catch (e) {
        console.error("[WS] Failed to parse message:", e);
      }
    };

    return () => {
      shouldReconnectRef.current = false;
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      console.log("[WS] Cleaning up connection");
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
      wsRef.current = null;
    };
  }, [gameId, roomCode, playerToken, spectateMode, reconnectTick, scheduleReconnect]); // Reconnect when identity/tick changes

  useEffect(() => {
    const resyncOnReturn = () => {
      if (document.visibilityState === "hidden") {
        return;
      }
      const ws = wsRef.current;
      if (ws?.readyState === WebSocket.OPEN) {
        try {
          ws.send(JSON.stringify({ type: "GET_STATE" }));
        } catch {
          // Ignore transient send issues.
        }
        return;
      }
      if (gameId || roomCode) {
        setReconnectTick((v) => v + 1);
      }
    };

    document.addEventListener("visibilitychange", resyncOnReturn);
    window.addEventListener("focus", resyncOnReturn);

    return () => {
      document.removeEventListener("visibilitychange", resyncOnReturn);
      window.removeEventListener("focus", resyncOnReturn);
    };
  }, [gameId, roomCode]);

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

  const requestNewGame = useCallback(() => {
    sendMessage({ type: "REQUEST_NEW_GAME" });
  }, [sendMessage]);

  return {
    connected,
    gameState,
    legalActions,
    sendBid,
    sendTrumpSelect,
    sendPlayCard,
    sendRevealChoice,
    requestNewGame,
    requestState,
  };
}

export default useGameWebSocket;
