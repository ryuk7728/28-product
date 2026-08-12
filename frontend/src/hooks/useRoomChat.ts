import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessage, ChatWsMessage } from "../api/types";

type RoomChatState = {
  connected: boolean;
  messages: ChatMessage[];
  error: string | null;
  sendChat: (text: string) => boolean;
};

function chatWebSocketUrl(roomCode: string, playerToken: string): string {
  const configured = (import.meta.env.VITE_WS_BASE_URL as string | undefined)?.replace(
    /\/$/,
    ""
  );
  const base = configured || `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.hostname}:8000`;
  return `${base}/ws/rooms/${encodeURIComponent(roomCode)}/chat?token=${encodeURIComponent(playerToken)}`;
}

export function useRoomChat(
  roomCode?: string,
  playerToken?: string
): RoomChatState {
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<number | null>(null);
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!roomCode || !playerToken) return;
    let disposed = false;

    const connect = () => {
      if (disposed) return;
      const ws = new WebSocket(chatWebSocketUrl(roomCode, playerToken));
      wsRef.current = ws;
      ws.onopen = () => {
        setConnected(true);
        setError(null);
      };
      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data) as ChatWsMessage;
        if (msg.type === "CHAT_HISTORY") {
          setMessages(msg.messages);
        } else if (msg.type === "CHAT_MESSAGE") {
          setMessages((current) =>
            current.some((item) => item.id === msg.message.id)
              ? current
              : [...current, msg.message].slice(-100)
          );
        } else if (msg.type === "ERROR") {
          setError(msg.message);
        }
      };
      ws.onerror = () => setError("Chat connection interrupted.");
      ws.onclose = () => {
        setConnected(false);
        if (!disposed) retryRef.current = window.setTimeout(connect, 1500);
      };
    };

    connect();
    return () => {
      disposed = true;
      if (retryRef.current !== null) window.clearTimeout(retryRef.current);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [roomCode, playerToken]);

  const sendChat = useCallback((text: string) => {
    const ws = wsRef.current;
    const cleaned = text.trim();
    if (!cleaned || !ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify({ type: "SEND_CHAT", text: cleaned }));
    return true;
  }, []);

  return { connected, messages, error, sendChat };
}
