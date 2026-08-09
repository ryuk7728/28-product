import { useState } from "react";
import { GamePage } from "./pages/GamePage";
import { MultiplayerLobbyPage, type MultiplayerSession } from "./pages/MultiplayerLobbyPage";
import { SelfPlayArenaPage } from "./pages/SelfPlayArenaPage";

export default function App() {
  const [session, setSession] = useState<MultiplayerSession | null>(null);
  const [showSelfPlay, setShowSelfPlay] = useState(false);

  if (showSelfPlay) {
    return <SelfPlayArenaPage onExit={() => setShowSelfPlay(false)} />;
  }

  if (!session) {
    return (
      <MultiplayerLobbyPage
        onReady={setSession}
        onSelfPlay={() => setShowSelfPlay(true)}
      />
    );
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
