import { useEffect, useState } from "react";
import { http } from "../api/http";
import { GamePage } from "./GamePage";

type Props = {
  onExit: () => void;
};

type CreateGameResponse = {
  gameId: string;
};

export function SelfPlayArenaPage({ onExit }: Props) {
  const [gameId, setGameId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function startSelfPlayGame() {
    setLoading(true);
    setError(null);
    try {
      const res = await http.post<CreateGameResponse>("/self-play/games");
      setGameId(res.data.gameId);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      setError(err?.response?.data?.detail ?? err?.message ?? "Failed to start self-play game");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void startSelfPlayGame();
  }, []);

  if (gameId) {
    return (
      <GamePage
        gameId={gameId}
        controlledSeatIndices={[]}
        spectateMode
        selfPlayMode
        onGameEnd={() => {
          setGameId(null);
          void startSelfPlayGame();
        }}
      />
    );
  }

  return (
    <div className="self-play-loading">
      <div className="self-play-panel">
        <div className="panel-title">Self Play Arena</div>
        <div className="panel-subtitle">
          Four bots will play a full game and store one result row when complete.
        </div>
        {error ? <div className="self-play-error">{error}</div> : null}
        <div className="self-play-actions">
          <button className="new-game-btn" onClick={startSelfPlayGame} disabled={loading}>
            {loading ? "Starting..." : "Start Self Play"}
          </button>
          <button className="btn-back" onClick={onExit}>
            Back
          </button>
        </div>
      </div>
    </div>
  );
}

export default SelfPlayArenaPage;
