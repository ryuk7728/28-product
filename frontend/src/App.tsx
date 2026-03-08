import { useState } from "react";
import { GamePage } from "./pages/GamePage";
import { MultiplayerLobbyPage, type MultiplayerSession } from "./pages/MultiplayerLobbyPage";

export default function App() {
  const [session, setSession] = useState<MultiplayerSession | null>(null);

  if (!session) {
    return <MultiplayerLobbyPage onReady={setSession} />;
  }

  return (
    <GamePage
      gameId={session.gameId}
      roomCode={session.roomCode}
      playerToken={session.mode === "player" ? session.playerToken : undefined}
      playerSeatIndex={session.mode === "player" ? session.seatIndex : undefined}
      controlledSeatIndices={session.mode === "player" ? [session.seatIndex] : []}
      spectateMode={session.mode === "spectator"}
      onGameEnd={() => {
        setSession(null);
      }}
    />
  );
}
