import { useState } from "react";
import { http } from "../api/http";
import { PLAYER_NAMES } from "../config/constants";

type Props = {
  onGameCreated: (gameId: string) => void;
};

export function SetupPage({ onGameCreated }: Props) {
  const [startingBidderIndex, setStartingBidderIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  async function createGame() {
    setError(null);
    setCreating(true);

    try {
      // Auto deal mode - just send starting bidder
      const res = await http.post("/games/auto", {
        startingBidderIndex,
      });
      onGameCreated(res.data.gameId as string);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      const msg = err?.response?.data?.detail ?? err?.message ?? "Failed to create game";
      setError(String(msg));
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="min-h-screen felt-background flex items-start justify-center px-4 py-8 overflow-auto">
      <div className="bg-white/95 rounded-2xl shadow-2xl max-w-4xl w-full p-10 min-h-[360px]">
        {/* Header */}
        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold text-gray-800 mb-2">28 Card Game</h1>
          <p className="text-gray-600">Setup your game</p>
        </div>

        {/* Starting Bidder Selection */}
        <div className="mb-8">
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Starting Bidder
          </label>
          <div className="grid grid-cols-4 gap-2">
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
                <div className="text-xs text-gray-500">
                  {idx % 2 === 0 ? "Bot" : "Human"}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {error}
          </div>
        )}

        {/* Start Game Button */}
        <div className="mt-10">
          <button
            className="w-full py-4 bg-gradient-to-r from-green-600 to-green-700 hover:from-green-700 hover:to-green-800 text-white font-bold text-lg rounded-xl shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={createGame}
            disabled={creating}
          >
            {creating ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                    fill="none"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Creating Game...
              </span>
            ) : (
              "Start Game"
            )}
          </button>
        </div>

        {/* Info Text */}
        <div className="mt-6 text-center text-sm text-gray-500">
          <p>Cards will be shuffled and dealt automatically to all players.</p>
        </div>
      </div>
    </div>
  );
}
