import { useEffect, useMemo, useState } from "react";
import { http } from "../api/http";
import { PLAYER_NAMES } from "../config/constants";
import type {
  BidPolicy,
  BidPolicyMode,
  BidThresholds,
  KPolicyMode,
  RoomJoinResponse,
  RoomStatusResponse,
} from "../api/types";
import "../styles/multiplayer-lobby.scss";

export type MultiplayerSession =
  | {
      roomCode: string;
      gameId: string;
      mode: "player";
      seatIndex: number;
      playerToken: string;
    }
  | {
      roomCode: string;
      gameId: string;
      mode: "spectator";
    };

type Props = {
  onReady: (session: MultiplayerSession) => void;
  onSelfPlay?: () => void;
};

type WaitingState = {
  roomCode: string;
  mode: "player" | "spectator";
  seatIndex?: number;
  playerToken?: string;
  playersJoined: number;
  biddingPolicy?: BidPolicy;
  kPolicy?: KPolicyMode;
  botThinkTimeSeconds?: number;
};

const BID_POLICY_STORAGE_KEY = "bot_bidding_policy_v1";
const K_POLICY_STORAGE_KEY = "bot_k_policy_v1";
const BOT_THINK_TIME_STORAGE_KEY = "bot_think_time_seconds_v1";
const DEFAULT_CUSTOM_THRESHOLDS: BidThresholds = {
  opening15: 67,
  opening16: 70,
  laterBid: 67,
  jumpTo16: 75,
};

function loadBidPolicy(): BidPolicy {
  try {
    const stored = JSON.parse(
      localStorage.getItem(BID_POLICY_STORAGE_KEY) || "null"
    ) as BidPolicy | null;
    if (
      stored &&
      ["aggressive", "optimal", "custom"].includes(stored.mode) &&
      typeof stored.positionAware === "boolean"
    ) {
      return {
        mode: stored.mode,
        positionAware: stored.positionAware,
        thresholds: { ...DEFAULT_CUSTOM_THRESHOLDS, ...stored.thresholds },
      };
    }
  } catch {
    // Ignore malformed local preferences and restore the safe default.
  }
  return {
    mode: "aggressive",
    positionAware: false,
    thresholds: DEFAULT_CUSTOM_THRESHOLDS,
  };
}

function loadKPolicy(): KPolicyMode {
  const stored = localStorage.getItem(K_POLICY_STORAGE_KEY);
  return stored === "aggressive" ? "aggressive" : "regular";
}

function loadBotThinkTime(): number {
  const stored = Number(localStorage.getItem(BOT_THINK_TIME_STORAGE_KEY));
  return Number.isFinite(stored) && stored >= 1 && stored <= 120 ? stored : 30;
}

function tokenStorageKey(roomCode: string): string {
  return `room_token_${roomCode.toUpperCase()}`;
}

export function MultiplayerLobbyPage({ onReady, onSelfPlay }: Props) {
  const [createPlayerName, setCreatePlayerName] = useState("");
  const [joinPlayerName, setJoinPlayerName] = useState("");
  const [joinCode, setJoinCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [waiting, setWaiting] = useState<WaitingState | null>(null);
  const [copied, setCopied] = useState(false);
  const [biddingPolicy, setBiddingPolicy] = useState<BidPolicy>(loadBidPolicy);
  const [kPolicy, setKPolicy] = useState<KPolicyMode>(loadKPolicy);
  const [botThinkTimeSeconds, setBotThinkTimeSeconds] = useState(loadBotThinkTime);

  useEffect(() => {
    localStorage.setItem(BID_POLICY_STORAGE_KEY, JSON.stringify(biddingPolicy));
  }, [biddingPolicy]);

  useEffect(() => {
    localStorage.setItem(K_POLICY_STORAGE_KEY, kPolicy);
  }, [kPolicy]);

  useEffect(() => {
    localStorage.setItem(BOT_THINK_TIME_STORAGE_KEY, String(botThinkTimeSeconds));
  }, [botThinkTimeSeconds]);

  const setPolicyMode = (mode: BidPolicyMode) => {
    setBiddingPolicy((current) => ({ ...current, mode }));
  };

  const setCustomThreshold = (field: keyof BidThresholds, rawValue: string) => {
    const value = Math.max(0, Math.min(100, Number(rawValue) || 0));
    setBiddingPolicy((current) => ({
      ...current,
      thresholds: {
        ...DEFAULT_CUSTOM_THRESHOLDS,
        ...current.thresholds,
        [field]: value,
      },
    }));
  };

  const policyLabel = `${
    biddingPolicy.mode[0].toUpperCase() + biddingPolicy.mode.slice(1)
  } bid · ${kPolicy === "aggressive" ? "Aggressive" : "Regular"} play · ${botThinkTimeSeconds}s`;

  const normalizedJoinCode = useMemo(() => joinCode.trim().toUpperCase(), [joinCode]);
  const existingJoinToken = useMemo(() => {
    if (!normalizedJoinCode) return null;
    return localStorage.getItem(tokenStorageKey(normalizedJoinCode));
  }, [normalizedJoinCode]);

  const persistToken = (roomCode: string, playerToken: string) => {
    localStorage.setItem(tokenStorageKey(roomCode), playerToken);
  };

  const completePlayerIfReady = (payload: {
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
      mode: "player",
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
        playerName: createPlayerName.trim(),
        biddingPolicy,
        kPolicy,
        botThinkTimeSeconds,
      });
      const data = res.data;
      persistToken(data.roomCode, data.playerToken);

      if (completePlayerIfReady(data)) return;

      setWaiting({
        roomCode: data.roomCode,
        mode: "player",
        seatIndex: data.seatIndex,
        playerToken: data.playerToken,
        playersJoined: data.playersJoined,
        biddingPolicy,
        kPolicy,
        botThinkTimeSeconds,
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

      if (completePlayerIfReady(data)) return;

      setWaiting({
        roomCode: data.roomCode,
        mode: "player",
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

  async function spectateRoom() {
    if (!normalizedJoinCode) {
      setError("Enter a room code.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await http.get<RoomStatusResponse>(`/rooms/${normalizedJoinCode}`);
      const status = res.data;

      if (status.gameId) {
        onReady({
          roomCode: normalizedJoinCode,
          gameId: status.gameId,
          mode: "spectator",
        });
        return;
      }

      setWaiting({
        roomCode: normalizedJoinCode,
        mode: "spectator",
        playersJoined: status.playersJoined,
      });
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      const msg = err?.response?.data?.detail ?? err?.message ?? "Failed to spectate room";
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
        const params =
          waiting.mode === "player" && waiting.playerToken
            ? { playerToken: waiting.playerToken }
            : undefined;
        const res = await http.get<RoomStatusResponse>(`/rooms/${waiting.roomCode}`, {
          params,
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
          if (waiting.mode === "player" && waiting.seatIndex !== undefined && waiting.playerToken) {
            onReady({
              roomCode: waiting.roomCode,
              gameId: status.gameId,
              mode: "player",
              seatIndex: waiting.seatIndex,
              playerToken: waiting.playerToken,
            });
          } else {
            onReady({
              roomCode: waiting.roomCode,
              gameId: status.gameId,
              mode: "spectator",
            });
          }
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
            <p className="panel-sub">
              {waiting.mode === "player"
                ? "Share this code. Game starts when second human joins."
                : "Waiting for both players. Spectator view unlocks once the game starts."}
            </p>
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
              {waiting.mode === "player" && waiting.seatIndex !== undefined ? (
                <div className="info-row">
                  <span className="info-key">Your Seat</span>
                  <span className="info-val">
                    P{waiting.seatIndex + 1}{" "}
                    <span className="tag">
                      ({waiting.seatIndex % 2 === 0 ? PLAYER_NAMES[waiting.seatIndex] : "Human"})
                    </span>
                  </span>
                </div>
              ) : (
                <div className="info-row">
                  <span className="info-key">Mode</span>
                  <span className="info-val">Spectator</span>
                </div>
              )}
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
              {waiting.biddingPolicy ? (
                <div className="info-row">
                  <span className="info-key">Bot Settings</span>
                  <span className="info-val policy-value">
                    {waiting.biddingPolicy.mode} ·{" "}
                    {waiting.biddingPolicy.positionAware ? "position" : "pooled"} ·{" "}
                    {waiting.kPolicy || "regular"} play
                    {waiting.botThinkTimeSeconds
                      ? ` · ${waiting.botThinkTimeSeconds}s`
                      : ""}
                  </span>
                </div>
              ) : null}
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

        {onSelfPlay ? (
          <button className="btn-self-play" onClick={onSelfPlay}>
            Open Self Play Arena
          </button>
        ) : null}

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

            <details className="bid-settings">
              <summary>
                <span>
                  <strong>Bot settings</strong>
                  <small>Bidding and play strength</small>
                </span>
                <span className="policy-summary">{policyLabel}</span>
              </summary>

              <div className="bid-settings-body">
                <div className="settings-section-label">Bidding style</div>
                <div className="policy-modes" role="group" aria-label="Bidding preset">
                  {(["aggressive", "optimal", "custom"] as BidPolicyMode[]).map((mode) => (
                    <button
                      type="button"
                      key={mode}
                      className={biddingPolicy.mode === mode ? "active" : ""}
                      onClick={() => setPolicyMode(mode)}
                    >
                      {mode}
                    </button>
                  ))}
                </div>

                <label className="position-toggle">
                  <span>
                    <strong>Use bid position</strong>
                    <small>25 games per hand and position</small>
                  </span>
                  <input
                    type="checkbox"
                    checked={biddingPolicy.positionAware}
                    onChange={(event) =>
                      setBiddingPolicy((current) => ({
                        ...current,
                        positionAware: event.target.checked,
                      }))
                    }
                  />
                  <i aria-hidden />
                </label>

                {biddingPolicy.mode === "custom" ? (
                  <div className="threshold-grid">
                    {(
                      [
                        ["opening15", "Opening 15"],
                        ["opening16", "Opening 16"],
                        ["laterBid", "Later bid"],
                        ["jumpTo16", "14→16 jump"],
                      ] as Array<[keyof BidThresholds, string]>
                    ).map(([field, label]) => (
                      <label key={field}>
                        <span>{label}</span>
                        <span className="percent-input">
                          <input
                            type="number"
                            min="0"
                            max="100"
                            inputMode="numeric"
                            value={(biddingPolicy.thresholds || DEFAULT_CUSTOM_THRESHOLDS)[field]}
                            onChange={(event) => setCustomThreshold(field, event.target.value)}
                          />
                          <b>%</b>
                        </span>
                      </label>
                    ))}
                  </div>
                ) : (
                  <p className="preset-note">
                    {biddingPolicy.mode === "aggressive"
                      ? "Open 15 ≥61% · open 16 ≥66% · later ≥61% · jump ≥71%"
                      : "Open 15 ≥67% · open 16 ≥70% · later ≥67% · jump ≥75%"}
                  </p>
                )}

                <div className="settings-divider" />
                <div className="play-policy-heading">
                  <span>
                    <strong>Play strength</strong>
                    <small>Controls Rust search breadth</small>
                  </span>
                </div>
                <div
                  className="policy-modes play-policy-modes"
                  role="group"
                  aria-label="Play search strength"
                >
                  {(["regular", "aggressive"] as KPolicyMode[]).map((mode) => (
                    <button
                      type="button"
                      key={mode}
                      className={kPolicy === mode ? "active" : ""}
                      onClick={() => setKPolicy(mode)}
                    >
                      <span>{mode}</span>
                      <small>
                        {mode === "regular" ? "2·2·3·3·4·3·2·1" : "3·3·4·4·4·3·2·1"}
                      </small>
                    </button>
                  ))}
                </div>
                <p className="preset-note play-note">
                  Aggressive explores more moves and may take longer.
                </p>

                <div className="settings-divider" />
                <div className="play-policy-heading">
                  <span>
                    <strong>Thinking time</strong>
                    <small>Maximum time for each bot card play</small>
                  </span>
                </div>
                <div
                  className="think-time-presets"
                  role="group"
                  aria-label="Bot thinking time"
                >
                  {[10, 30, 60].map((seconds) => (
                    <button
                      type="button"
                      key={seconds}
                      className={botThinkTimeSeconds === seconds ? "active" : ""}
                      onClick={() => setBotThinkTimeSeconds(seconds)}
                    >
                      {seconds}s
                    </button>
                  ))}
                  <label>
                    <input
                      aria-label="Custom bot thinking seconds"
                      type="number"
                      min="1"
                      max="120"
                      inputMode="numeric"
                      value={botThinkTimeSeconds}
                      onChange={(event) => {
                        const value = Number(event.target.value);
                        if (Number.isFinite(value)) {
                          setBotThinkTimeSeconds(Math.max(1, Math.min(120, value)));
                        }
                      }}
                    />
                    <span>s</span>
                  </label>
                </div>
                <p className="preset-note play-note">
                  Plays the best result from every rollout completed in time.
                </p>
              </div>
            </details>

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

            <button className="btn-spectate" onClick={spectateRoom} disabled={loading || !normalizedJoinCode}>
              {loading ? "Checking..." : "Spectate Room"}
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
