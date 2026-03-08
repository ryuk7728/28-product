import { useEffect, useMemo, useState } from "react";
import { http } from "../api/http";
import { PLAYER_NAMES } from "../config/constants";
import type { RoomJoinResponse, RoomStatusResponse } from "../api/types";
import "../styles/multiplayer-lobby.scss";

export type MultiplayerSession = {
  roomCode: string;
  gameId: string;
  seatIndex: number;
  playerToken: string;
};

type Props = {
  onReady: (session: MultiplayerSession) => void;
};

type WaitingState = {
  roomCode: string;
  seatIndex: number;
  playerToken: string;
  playersJoined: number;
};

function tokenStorageKey(roomCode: string): string {
  return `room_token_${roomCode.toUpperCase()}`;
}

export function MultiplayerLobbyPage({ onReady }: Props) {
  const [createPlayerName, setCreatePlayerName] = useState("");
  const [joinPlayerName, setJoinPlayerName] = useState("");
  const [joinCode, setJoinCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [waiting, setWaiting] = useState<WaitingState | null>(null);
  const [copied, setCopied] = useState(false);

  const normalizedJoinCode = useMemo(() => joinCode.trim().toUpperCase(), [joinCode]);
  const existingJoinToken = useMemo(() => {
    if (!normalizedJoinCode) return null;
    return localStorage.getItem(tokenStorageKey(normalizedJoinCode));
  }, [normalizedJoinCode]);

  const persistToken = (roomCode: string, playerToken: string) => {
    localStorage.setItem(tokenStorageKey(roomCode), playerToken);
  };

  const completeIfReady = (payload: {
    roomCode: string;
    gameId: string | null;
    seatIndex: number;
    playerToken: string;
  }) => {
    if (!payload.gameId) {
      return false;
    }
    onReady({
      roomCode: payload.roomCode,
      gameId: payload.gameId,
      seatIndex: payload.seatIndex,
      playerToken: payload.playerToken,
    });
    return true;
  };

  async function createRoom() {
    setError(null);
    setLoading(true);
    try {
      const res = await http.post<RoomJoinResponse>("/rooms", {
        startingBidderIndex: 0,
        playerName: createPlayerName.trim(),
      });
      const data = res.data;
      persistToken(data.roomCode, data.playerToken);

      if (completeIfReady(data)) return;

      setWaiting({
        roomCode: data.roomCode,
        seatIndex: data.seatIndex,
        playerToken: data.playerToken,
        playersJoined: data.playersJoined,
      });
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      const msg = err?.response?.data?.detail ?? err?.message ?? "Failed to create room";
      setError(String(msg));
    } finally {
      setLoading(false);
    }
  }

  async function joinRoom(useStoredToken: boolean) {
    if (!normalizedJoinCode) {
      setError("Enter a room code.");
      return;
    }
    if (!useStoredToken && !joinPlayerName.trim()) {
      setError("Enter your name.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await http.post<RoomJoinResponse>("/rooms/join", {
        roomCode: normalizedJoinCode,
        playerToken: useStoredToken ? existingJoinToken || null : null,
        playerName: useStoredToken ? null : joinPlayerName.trim(),
      });
      const data = res.data;
      persistToken(data.roomCode, data.playerToken);

      if (completeIfReady(data)) return;

      setWaiting({
        roomCode: data.roomCode,
        seatIndex: data.seatIndex,
        playerToken: data.playerToken,
        playersJoined: data.playersJoined,
      });
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      const msg = err?.response?.data?.detail ?? err?.message ?? "Failed to join room";
      setError(String(msg));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!waiting) return;
    setCopied(false);
    const interval = window.setInterval(async () => {
      try {
        const res = await http.get<RoomStatusResponse>(`/rooms/${waiting.roomCode}`, {
          params: { playerToken: waiting.playerToken },
        });
        const status = res.data;
        setWaiting((prev) =>
          prev
            ? {
                ...prev,
                playersJoined: status.playersJoined,
              }
            : prev
        );

        if (status.gameId) {
          onReady({
            roomCode: waiting.roomCode,
            gameId: status.gameId,
            seatIndex: waiting.seatIndex,
            playerToken: waiting.playerToken,
          });
        }
      } catch {
        // Silent retry while waiting.
      }
    }, 2000);

    return () => window.clearInterval(interval);
  }, [waiting, onReady]);

  async function copyRoomCode() {
    if (!waiting) return;

    try {
      await navigator.clipboard.writeText(waiting.roomCode);
    } catch {
      const el = document.createElement("textarea");
      el.value = waiting.roomCode;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
    }

    setCopied(true);
    window.setTimeout(() => setCopied(false), 2200);
  }

  if (waiting) {
    return (
      <div className="mp-shell">
        <div className="felt-bg" />
        <div className="table-ring" />
        <div className="floating-cards" aria-hidden>
          <div className="card-deco red" data-suit="♥">J</div>
          <div className="card-deco black" data-suit="♠">A</div>
          <div className="card-deco red" data-suit="♦">Q</div>
          <div className="card-deco black" data-suit="♣">K</div>
          <div className="card-deco black" data-suit="♣">9</div>
          <div className="card-deco red" data-suit="♥">10</div>
          <div className="card-deco red" data-suit="♦">8</div>
          <div className="card-deco black" data-suit="♠">7</div>
        </div>

        <div className="stage room-stage">
          <div className="ornament">
            <div className="ornament-line" />
            <span className="ornament-suit">♠</span>
            <div className="ornament-diamond" />
            <span className="ornament-suit">♥</span>
            <div className="ornament-line r" />
          </div>

          <div className="room-panel">
            <div className="panel-eyebrow">Waiting for Players</div>
            <div className="panel-title">Room Created</div>
            <p className="panel-sub">Share this code. Game starts when second human joins.</p>
            <div className="rule" />

            <div className="code-label">Room Code</div>
            <div className="code-display">{waiting.roomCode}</div>

            <button className={`btn-copy ${copied ? "copied" : ""}`} onClick={copyRoomCode}>
              <span className="label-default">Copy Code</span>
              <span className="label-copied">
                <span className="tick-circle">✓</span>
                Copied!
              </span>
            </button>

            <div className="info-block">
              <div className="info-row">
                <span className="info-key">Your Seat</span>
                <span className="info-val">
                  P{waiting.seatIndex + 1}{" "}
                  <span className="tag">
                    ({waiting.seatIndex % 2 === 0 ? PLAYER_NAMES[waiting.seatIndex] : "Human"})
                  </span>
                </span>
              </div>
              <div className="info-row">
                <span className="info-key">Players Joined</span>
                <div className="players-val">
                  <span className="info-val">{waiting.playersJoined}/2</span>
                  <div className="seat-dots">
                    <div className="dot filled" />
                    <div className={`dot ${waiting.playersJoined >= 2 ? "filled" : "waiting"}`} />
                  </div>
                </div>
              </div>
            </div>

            <button className="btn-back" onClick={() => setWaiting(null)}>
              <span className="back-arrow">←</span> Back
            </button>
          </div>

          <div className="suits-row" aria-hidden>
            <span className="suit-icon black">♠</span>
            <span className="suit-icon red">♥</span>
            <span className="suit-icon red">♦</span>
            <span className="suit-icon black">♣</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mp-shell">
      <div className="felt-bg" />
      <div className="table-ring" />
      <div className="floating-cards" aria-hidden>
        <div className="card-deco red" data-suit="♥">J</div>
        <div className="card-deco black" data-suit="♠">A</div>
        <div className="card-deco red" data-suit="♦">Q</div>
        <div className="card-deco black" data-suit="♣">K</div>
        <div className="card-deco black" data-suit="♣">9</div>
        <div className="card-deco red" data-suit="♥">10</div>
        <div className="card-deco red" data-suit="♦">8</div>
        <div className="card-deco black" data-suit="♠">7</div>
      </div>

      <div className="stage lobby-stage">
        <div className="ornament">
          <div className="ornament-line" />
          <span className="ornament-suit">♠</span>
          <div className="ornament-diamond" />
          <span className="ornament-suit">♥</span>
          <div className="ornament-line r" />
        </div>

        <h1 className="page-title">
          <span>28</span> Card Game
        </h1>
        <p className="page-sub">Create a room or join with a code</p>

        <div className="panels">
          <div className="panel">
            <div>
              <div className="panel-label">New Game</div>
              <div className="panel-heading">Create Room</div>
            </div>
            <div className="panel-rule" />

            <div className="field">
              <label className="field-label">Your Name</label>
              <input
                value={createPlayerName}
                onChange={(e) => setCreatePlayerName(e.target.value)}
                placeholder="Enter your name"
                maxLength={24}
                autoComplete="off"
              />
            </div>

            <button className="btn-create" onClick={createRoom} disabled={loading || !createPlayerName.trim()}>
              {loading ? "Creating..." : "Create Room"}
            </button>
          </div>

          <div className="divider-v" />

          <div className="panel">
            <div>
              <div className="panel-label">Existing Game</div>
              <div className="panel-heading">Join Room</div>
            </div>
            <div className="panel-rule right" />

            <div className="field">
              <label className="field-label">Room Code</label>
              <input
                value={joinCode}
                onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
                placeholder="· · · · · ·"
                className="code-input"
                maxLength={10}
                autoComplete="off"
              />
            </div>

            <div className="field">
              <label className="field-label">Your Name</label>
              <input
                value={joinPlayerName}
                onChange={(e) => setJoinPlayerName(e.target.value)}
                placeholder="Enter your name"
                maxLength={24}
                autoComplete="off"
              />
            </div>

            <button className="btn-join" onClick={() => joinRoom(false)} disabled={loading || !joinPlayerName.trim()}>
              {loading ? "Joining..." : "Join as New Player"}
            </button>

            {existingJoinToken && (
              <button className="btn-reconnect" onClick={() => joinRoom(true)} disabled={loading}>
                Reconnect Previous Seat
              </button>
            )}
          </div>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <div className="suits-row" aria-hidden>
          <span className="suit-icon black">♠</span>
          <span className="suit-icon red">♥</span>
          <span className="suit-icon red">♦</span>
          <span className="suit-icon black">♣</span>
        </div>
      </div>
    </div>
  );
}
