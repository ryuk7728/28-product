import { useEffect, useMemo, useState } from "react";
import { http } from "../api/http";
import type { RoomJoinResponse, RoomSeat, RoomStatusResponse } from "../api/types";
import "../styles/product-lobby.scss";

export type MultiplayerSession = {
  roomCode: string;
  gameId: string;
  seatIndex: number;
  playerToken: string;
};

type Props = { onReady: (session: MultiplayerSession) => void };

type WaitingState = {
  roomCode: string;
  gameId: string | null;
  seatIndex: number;
  playerToken: string;
  playersJoined: number;
  targetHumanCount: number;
  seats: RoomSeat[];
};

const NAME_KEY = "28_product_player_name";

function tokenKey(code: string) {
  return `28_product_room_${code.toUpperCase()}`;
}

function normalizeCode(value: string) {
  return value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 6);
}

function messageForError(error: unknown, fallback: string) {
  const typed = error as { response?: { data?: { detail?: string } }; message?: string };
  return String(typed.response?.data?.detail ?? typed.message ?? fallback);
}

function TablePreview({ seats, ownSeat }: { seats: RoomSeat[]; ownSeat: number }) {
  return (
    <div className="seat-map" aria-label="Table seats and teams">
      {seats.map((seat) => (
        <div
          key={seat.seatIndex}
          className={`seat-card seat-${seat.seatIndex} ${seat.joined ? "filled" : "empty"}`}
        >
          <span className={`seat-avatar ${seat.type}`}>{seat.type === "bot" ? "✦" : seat.name[0]?.toUpperCase()}</span>
          <span className="seat-name">
            {seat.seatIndex === ownSeat ? "You" : seat.name}
          </span>
          <span className="seat-meta">Team {seat.team}</span>
        </div>
      ))}
      <div className="seat-map-center">
        <span>Partners sit</span>
        <strong>opposite</strong>
      </div>
    </div>
  );
}

export function MultiplayerLobbyPage({ onReady }: Props) {
  const inviteCode = useMemo(
    () => normalizeCode(new URLSearchParams(window.location.search).get("room") ?? ""),
    []
  );
  const [name, setName] = useState(() => localStorage.getItem(NAME_KEY) ?? "");
  const [humanCount, setHumanCount] = useState(1);
  const [joinCode, setJoinCode] = useState(inviteCode);
  const [view, setView] = useState<"home" | "join">(inviteCode ? "join" : "home");
  const [waiting, setWaiting] = useState<WaitingState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<"code" | "link" | null>(null);

  const finish = (payload: WaitingState) => {
    if (!payload.gameId) return false;
    onReady({
      roomCode: payload.roomCode,
      gameId: payload.gameId,
      seatIndex: payload.seatIndex,
      playerToken: payload.playerToken,
    });
    return true;
  };

  const remember = (payload: RoomJoinResponse) => {
    localStorage.setItem(NAME_KEY, name.trim());
    localStorage.setItem(
      tokenKey(payload.roomCode),
      JSON.stringify({ token: payload.playerToken, name: payload.seatName })
    );
    const next: WaitingState = payload;
    if (!finish(next)) setWaiting(next);
  };

  async function createTable() {
    if (!name.trim()) return setError("Enter your name to continue.");
    setLoading(true);
    setError(null);
    try {
      const response = await http.post<RoomJoinResponse>("/rooms", {
        playerName: name.trim(),
        humanCount,
      });
      remember(response.data);
    } catch (caught) {
      setError(messageForError(caught, "We couldn't create the table."));
    } finally {
      setLoading(false);
    }
  }

  async function joinTable() {
    const code = normalizeCode(joinCode);
    if (code.length !== 6) return setError("Enter the six-character table code.");
    if (!name.trim()) return setError("Enter your name to continue.");
    setLoading(true);
    setError(null);
    try {
      let saved: { token?: string } | null = null;
      try {
        saved = JSON.parse(localStorage.getItem(tokenKey(code)) ?? "null");
      } catch {
        localStorage.removeItem(tokenKey(code));
      }
      const response = await http.post<RoomJoinResponse>("/rooms/join", {
        roomCode: code,
        playerName: name.trim(),
        playerToken: saved?.token ?? null,
      });
      remember(response.data);
    } catch (caught) {
      setError(messageForError(caught, "We couldn't join that table."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!waiting) return;
    const poll = window.setInterval(async () => {
      try {
        const response = await http.get<RoomStatusResponse>(`/rooms/${waiting.roomCode}`, {
          params: { playerToken: waiting.playerToken },
        });
        const next: WaitingState = {
          ...waiting,
          ...response.data,
          seatIndex: response.data.seatIndex ?? waiting.seatIndex,
        };
        if (!finish(next)) setWaiting(next);
      } catch (caught) {
        setError(messageForError(caught, "The table is no longer available."));
      }
    }, 1200);
    return () => window.clearInterval(poll);
    // `waiting` intentionally drives the polling lifecycle; `finish` is a small
    // render-local adapter whose behavior is represented by `onReady`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [waiting, onReady]);

  const inviteLink = waiting
    ? `${window.location.origin}${window.location.pathname}?room=${waiting.roomCode}`
    : "";

  async function copy(value: string, type: "code" | "link") {
    await navigator.clipboard.writeText(value);
    setCopied(type);
    window.setTimeout(() => setCopied(null), 1600);
  }

  async function share() {
    if (!waiting) return;
    if (navigator.share) {
      await navigator.share({
        title: "Join my Twenty-Eight table",
        text: `Join my Twenty-Eight game. Table code: ${waiting.roomCode}`,
        url: inviteLink,
      });
    } else {
      await copy(inviteLink, "link");
    }
  }

  if (waiting) {
    return (
      <main className="product-shell waiting-shell">
        <div className="ambient ambient-one" />
        <section className="waiting-card">
          <header className="product-brand compact"><span>28</span><b>Twenty-Eight</b></header>
          <div className="waiting-kicker">Your table is ready</div>
          <button className="room-code" onClick={() => copy(waiting.roomCode, "code")}>
            <span>Table code</span>
            <strong>{waiting.roomCode.slice(0, 3)} {waiting.roomCode.slice(3)}</strong>
            <small>{copied === "code" ? "Copied" : "Tap to copy"}</small>
          </button>
          <div className="share-actions">
            <button className="primary-action" onClick={share}>Share invite</button>
            <button className="quiet-action" onClick={() => copy(inviteLink, "link")}>
              {copied === "link" ? "Link copied" : "Copy link"}
            </button>
            <button className="quiet-action" onClick={() => copy(waiting.roomCode, "code")}>Copy code</button>
          </div>
          <div className="waiting-progress">
            <div><strong>{waiting.playersJoined} of {waiting.targetHumanCount}</strong><span>players joined</span></div>
            <div className="progress-track"><i style={{ width: `${(waiting.playersJoined / waiting.targetHumanCount) * 100}%` }} /></div>
            <p>{waiting.playersJoined === waiting.targetHumanCount ? "Starting the game…" : "The game starts automatically when everyone arrives."}</p>
          </div>
          <TablePreview seats={waiting.seats} ownSeat={waiting.seatIndex} />
          {waiting.targetHumanCount === 3 && (
            <p className="partnership-note">This is still a 2 vs 2 game. The bot partners one player, then rotates fairly on rematches.</p>
          )}
          {error && <div className="product-error" role="alert">{error}</div>}
          <button className="text-action" onClick={() => setWaiting(null)}>Leave table</button>
        </section>
      </main>
    );
  }

  return (
    <main className="product-shell">
      <div className="ambient ambient-one" /><div className="ambient ambient-two" />
      <header className="product-nav">
        <div className="product-brand"><span>28</span><b>Twenty-Eight</b></div>
        <button className="nav-join" onClick={() => setView(view === "join" ? "home" : "join")}>
          {view === "join" ? "Create a table" : "Join a table"}
        </button>
      </header>
      <section className="hero-grid">
        <div className="hero-copy">
          <div className="eyebrow">THE CLASSIC PARTNERSHIP CARD GAME</div>
          <h1>Your table.<br /><em>Ready when you are.</em></h1>
          <p>Play Twenty-Eight with friends, capable bots, or both. No setup, no settings—just share and deal.</p>
          <div className="trust-row"><span>♠ 2 teams</span><span>♦ 4 seats</span><span>♣ 1 invite</span></div>
        </div>
        <div className="setup-card">
          {view === "home" ? (
            <>
              <div className="setup-heading"><span>Start a game</span><small>About two taps away</small></div>
              <label className="product-field"><span>Your name</span><input autoFocus value={name} maxLength={24} autoComplete="name" placeholder="What should we call you?" onChange={(event) => setName(event.target.value)} /></label>
              <fieldset className="player-count"><legend>How many people are playing?</legend><div className="count-grid">
                {[1,2,3,4].map((count) => <button type="button" key={count} className={humanCount === count ? "selected" : ""} onClick={() => setHumanCount(count)}><strong>{count}</strong><span>{count === 1 ? "Just me" : `${count} people`}</span><small>{4-count ? `${4-count} bot${4-count > 1 ? "s" : ""}` : "No bots"}</small></button>)}
              </div></fieldset>
              <button className="primary-action wide" disabled={loading} onClick={createTable}>{loading ? "Setting the table…" : humanCount === 1 ? "Play now" : "Create table"}<span>→</span></button>
            </>
          ) : (
            <>
              <div className="setup-heading"><span>{inviteCode ? "You've been invited" : "Join a table"}</span><small>Enter the code your friend shared</small></div>
              <label className="product-field"><span>Table code</span><input autoFocus className="join-code-input" value={joinCode} maxLength={6} inputMode="text" autoCapitalize="characters" placeholder="ABC 123" onChange={(event) => setJoinCode(normalizeCode(event.target.value))} /></label>
              <label className="product-field"><span>Your name</span><input value={name} maxLength={24} autoComplete="name" placeholder="What should we call you?" onChange={(event) => setName(event.target.value)} /></label>
              <button className="primary-action wide" disabled={loading} onClick={joinTable}>{loading ? "Joining…" : "Join table"}<span>→</span></button>
            </>
          )}
          {error && <div className="product-error" role="alert">{error}</div>}
          <div className="setup-foot">Private room · No account needed</div>
        </div>
      </section>
      <footer className="product-footer"><span>Built for phones, tablets, and desktops.</span><span>Strong Rust-powered opponents fill empty seats.</span></footer>
    </main>
  );
}
