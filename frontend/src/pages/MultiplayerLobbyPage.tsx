import { useEffect, useMemo, useState } from "react";
import { http } from "../api/http";
import { PLAYER_NAMES } from "../config/constants";
import type { RoomJoinResponse, RoomStatusResponse } from "../api/types";

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
  const [startingBidderIndex, setStartingBidderIndex] = useState(0);
  const [createPlayerName, setCreatePlayerName] = useState("");
  const [joinPlayerName, setJoinPlayerName] = useState("");
  const [joinCode, setJoinCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [waiting, setWaiting] = useState<WaitingState | null>(null);

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
        startingBidderIndex,
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

  if (waiting) {
    return (
      <div className="min-h-screen felt-background flex items-start justify-center px-4 py-8 overflow-auto">
        <div className="bg-white/95 rounded-2xl shadow-2xl max-w-3xl w-full p-10">
          <h1 className="text-4xl font-bold text-gray-800 mb-2 text-center">Room Created</h1>
          <p className="text-gray-600 text-center mb-8">
            Share this code. Game starts when second human joins.
          </p>

          <div className="bg-gray-100 rounded-xl p-6 text-center mb-6">
            <div className="text-sm text-gray-500 mb-2">Room Code</div>
            <div className="text-4xl font-extrabold tracking-widest text-gray-900 mb-4">
              {waiting.roomCode}
            </div>
            <button
              className="px-4 py-2 rounded-lg bg-blue-600 text-white font-semibold"
              onClick={() => navigator.clipboard.writeText(waiting.roomCode)}
            >
              Copy Code
            </button>
          </div>

          <div className="text-center text-gray-700 mb-2">
            Your seat: <span className="font-semibold">P{waiting.seatIndex + 1}</span> (
            {waiting.seatIndex % 2 === 0 ? PLAYER_NAMES[waiting.seatIndex] : "Human"})
          </div>
          <div className="text-center text-gray-700 mb-8">
            Players joined: {waiting.playersJoined}/2
          </div>

          <div className="flex justify-center">
            <button
              className="px-5 py-2 rounded-lg border border-gray-300 text-gray-700"
              onClick={() => setWaiting(null)}
            >
              Back
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen felt-background flex items-start justify-center px-4 py-8 overflow-auto">
      <div className="bg-white/95 rounded-2xl shadow-2xl max-w-4xl w-full p-10">
        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold text-gray-800 mb-2">28 Card Game</h1>
          <p className="text-gray-600">Create a room or join with code</p>
        </div>

        <div className="grid md:grid-cols-2 gap-8">
          <div className="border border-gray-200 rounded-xl p-6">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">Create Room</h2>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Your Name
            </label>
            <input
              value={createPlayerName}
              onChange={(e) => setCreatePlayerName(e.target.value)}
              placeholder="Enter your name"
              className="w-full px-4 py-3 rounded-lg border border-gray-300 mb-4"
              maxLength={24}
            />
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Starting Bidder
            </label>
            <div className="grid grid-cols-2 gap-2 mb-6">
              {[0, 1, 2, 3].map((idx) => (
                <button
                  key={idx}
                  className={`p-3 rounded-lg border-2 transition-all ${
                    startingBidderIndex === idx
                      ? "border-blue-600 bg-blue-50"
                      : "border-gray-200 hover:border-gray-400"
                  }`}
                  onClick={() => setStartingBidderIndex(idx)}
                >
                  <div className="font-semibold">{PLAYER_NAMES[idx]}</div>
                  <div className="text-xs text-gray-500">{idx % 2 === 0 ? "Bot" : "Human"}</div>
                </button>
              ))}
            </div>
            <button
              className="w-full py-3 rounded-xl bg-green-600 hover:bg-green-700 text-white font-bold disabled:opacity-50"
              onClick={createRoom}
              disabled={loading || !createPlayerName.trim()}
            >
              {loading ? "Creating..." : "Create Room"}
            </button>
          </div>

          <div className="border border-gray-200 rounded-xl p-6">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">Join Room</h2>
            <label className="block text-sm font-semibold text-gray-700 mb-2">Room Code</label>
            <input
              value={joinCode}
              onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
              placeholder="Enter 6-character code"
              className="w-full px-4 py-3 rounded-lg border border-gray-300 mb-6 tracking-widest font-semibold uppercase"
              maxLength={10}
            />
            <label className="block text-sm font-semibold text-gray-700 mb-2">Your Name</label>
            <input
              value={joinPlayerName}
              onChange={(e) => setJoinPlayerName(e.target.value)}
              placeholder="Enter your name"
              className="w-full px-4 py-3 rounded-lg border border-gray-300 mb-6"
              maxLength={24}
            />
            <button
              className="w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold disabled:opacity-50"
              onClick={() => joinRoom(false)}
              disabled={loading || !joinPlayerName.trim()}
            >
              {loading ? "Joining..." : "Join as New Player"}
            </button>
            {existingJoinToken && (
              <button
                className="w-full mt-3 py-3 rounded-xl border border-blue-300 text-blue-700 font-semibold disabled:opacity-50"
                onClick={() => joinRoom(true)}
                disabled={loading}
              >
                Reconnect Previous Seat
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="mt-8 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
