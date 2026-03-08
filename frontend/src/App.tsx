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
      playerToken={session.playerToken}
      playerSeatIndex={session.seatIndex}
      controlledSeatIndices={[session.seatIndex]}
      onGameEnd={() => {
        setSession(null);
      }}
    />
  );
}
