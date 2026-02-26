import { useState } from "react";
import { GamePage } from "./pages/GamePage";
import { MultiplayerLobbyPage, type MultiplayerSession } from "./pages/MultiplayerLobbyPage";
import { SetupPage } from "./pages/SetupPage";

export default function App() {
  const [mode, setMode] = useState<"single" | "multi" | null>(null);
  const [singleGameId, setSingleGameId] = useState<string | null>(null);
  const [session, setSession] = useState<MultiplayerSession | null>(null);

  if (mode === null) {
    return (
      <div className="min-h-screen felt-background flex items-center justify-center px-4 py-8">
        <div className="bg-white/95 rounded-2xl shadow-2xl max-w-xl w-full p-10">
          <h1 className="text-4xl font-bold text-gray-800 mb-2 text-center">28 Card Game</h1>
          <p className="text-gray-600 text-center mb-8">Choose game mode</p>
          <div className="space-y-4">
            <button
              className="w-full py-4 rounded-xl bg-green-600 hover:bg-green-700 text-white font-bold text-lg"
              onClick={() => setMode("single")}
            >
              Single Player
            </button>
            <button
              className="w-full py-4 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-lg"
              onClick={() => setMode("multi")}
            >
              Multiplayer (Room Code)
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (mode === "single") {
    if (!singleGameId) {
      return (
        <div>
          <div style={{ position: "fixed", top: 12, left: 12, zIndex: 50 }}>
            <button
              className="px-4 py-2 rounded-lg bg-black/70 text-white"
              onClick={() => setMode(null)}
            >
              Back
            </button>
          </div>
          <SetupPage onGameCreated={setSingleGameId} />
        </div>
      );
    }

    return (
      <GamePage
        gameId={singleGameId}
        controlledSeatIndices={[1, 3]}
        onGameEnd={() => {
          setSingleGameId(null);
          setMode(null);
        }}
      />
    );
  }

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
        setMode(null);
      }}
    />
  );
}
