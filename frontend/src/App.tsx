import { useEffect, useState } from "react";
import { GamePage } from "./pages/GamePage";
import {
  MultiplayerLobbyPage,
  type MultiplayerSession,
} from "./pages/MultiplayerLobbyPage";

const ACTIVE_SESSION_KEY = "28_product_active_session";

function loadSession(): MultiplayerSession | null {
  try {
    const raw = localStorage.getItem(ACTIVE_SESSION_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as MultiplayerSession;
    if (
      value?.roomCode &&
      value?.playerToken &&
      typeof value.seatIndex === "number"
    ) {
      return value;
    }
  } catch {
    localStorage.removeItem(ACTIVE_SESSION_KEY);
  }
  return null;
}

export default function App() {
  const [session, setSession] = useState<MultiplayerSession | null>(loadSession);

  useEffect(() => {
    if (session) {
      localStorage.setItem(ACTIVE_SESSION_KEY, JSON.stringify(session));
    } else {
      localStorage.removeItem(ACTIVE_SESSION_KEY);
    }
  }, [session]);

  if (!session) {
    return <MultiplayerLobbyPage onReady={setSession} />;
  }

  return (
    <GamePage
      gameId={session.gameId}
      roomCode={session.roomCode}
      playerToken={session.playerToken}
      playerSeatIndex={session.seatIndex}
      controlledSeatIndices={[session.seatIndex]}
      onGameEnd={() => setSession(null)}
    />
  );
}
