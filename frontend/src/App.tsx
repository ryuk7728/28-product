import { useState } from "react";
import { SetupPage } from "./pages/SetupPage";
import { GameRoomPage } from "./pages/GameRoomPage";
import { RoomPage } from "./pages/RoomPage";
import { TestPage } from "./pages/TestPage";
import { TestArenaPage } from "./pages/TestArenaPage";

// Set to true to show the Phase 1 test page, false for normal app
const SHOW_TEST_PAGE = false;
// Set to true to show the new Arena test page (Step 2)
const SHOW_ARENA_TEST = true;
// Set to true to use the old debug RoomPage, false for new visual GameRoomPage
const USE_OLD_ROOM_PAGE = false;

export default function App() {
  const [gameId, setGameId] = useState<string | null>(null);

  // For testing Phase 1 components
  if (SHOW_TEST_PAGE) {
    return <TestPage />;
  }

  // For testing new Arena components (Step 2)
  if (SHOW_ARENA_TEST) {
    return <TestArenaPage />;
  }

  if (!gameId) {
    return <SetupPage onGameCreated={setGameId} />;
  }

  // Use new visual game room or old debug room
  if (USE_OLD_ROOM_PAGE) {
    return <RoomPage gameId={gameId} />;
  }

  return <GameRoomPage gameId={gameId} onGameEnd={() => setGameId(null)} />;
}