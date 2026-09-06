import { useState, type FormEvent } from "react";
import { http } from "../api/http";
import type { RoomJoinResponse } from "../api/types";
import "../styles/product-lobby.scss";

export type MultiplayerSession = {
  roomCode: string;
  gameId: string;
  seatIndex: number;
  playerToken: string;
};

type Props = { onReady: (session: MultiplayerSession) => void };

const NAME_KEY = "28_product_player_name";

function messageForError(error: unknown, fallback: string) {
  const typed = error as { response?: { data?: { detail?: string } }; message?: string };
  return String(typed.response?.data?.detail ?? typed.message ?? fallback);
}

export function MultiplayerLobbyPage({ onReady }: Props) {
  const [name, setName] = useState(() => localStorage.getItem(NAME_KEY) ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function createTable(event?: FormEvent) {
    event?.preventDefault();
    if (!name.trim()) return setError("Enter your name to continue.");
    setLoading(true);
    setError(null);
    try {
      const response = await http.post<RoomJoinResponse>("/rooms", {
        playerName: name.trim(),
        humanCount: 1,
      });
      const payload = response.data;
      if (!payload.gameId) throw new Error("The game could not be started.");
      localStorage.setItem(NAME_KEY, name.trim());
      onReady({
        roomCode: payload.roomCode,
        gameId: payload.gameId,
        seatIndex: payload.seatIndex,
        playerToken: payload.playerToken,
      });
    } catch (caught) {
      setError(messageForError(caught, "We couldn't start your game."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="product-shell">
      <div className="ambient ambient-one" /><div className="ambient ambient-two" />
      <header className="product-nav">
        <div className="product-brand"><span>28</span><b>Twenty-Eight</b></div>
        <span className="solo-label">Solo table</span>
      </header>
      <section className="hero-grid">
        <div className="hero-copy">
          <div className="eyebrow">THE CLASSIC PARTNERSHIP CARD GAME</div>
          <h1>Your table.<br /><em>Three worthy rivals.</em></h1>
          <p>Take your seat with a bot partner and face two capable opponents. No setup, no settings—just deal.</p>
          <div className="trust-row"><span>♠ 1 player</span><span>♦ 3 bots</span><span>♣ Instant play</span></div>
        </div>
        <form className="setup-card solo-setup-card" onSubmit={createTable}>
          <div className="setup-heading"><span>Start a game</span><small>Your name is remembered here</small></div>
          <label className="product-field"><span>Your name</span><input autoFocus value={name} maxLength={24} autoComplete="name" placeholder="What should we call you?" onChange={(event) => setName(event.target.value)} /></label>
          <button type="submit" className="primary-action wide" disabled={loading}>{loading ? "Setting the table…" : "Play now"}<span>→</span></button>
          {error && <div className="product-error" role="alert">{error}</div>}
          <div className="setup-foot">No account needed · Your name stays on this device</div>
        </form>
      </section>
      <footer className="product-footer"><span>Built for tablets, laptops, and desktops.</span><span>Strong Rust-powered opponents fill the other seats.</span></footer>
    </main>
  );
}
