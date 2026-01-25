import { useMemo, useState } from "react";
import { http } from "../api/http";
import { Card } from "../components/Card";
import { PLAYER_NAMES, SUITS, RANKS_ORDERED } from "../config/constants";

function cardId(suit: string, rank: string) {
  return `${suit}_${rank}`;
}

type Props = {
  onGameCreated: (gameId: string) => void;
};

export function SetupPage({ onGameCreated }: Props) {
  const [startingBidderIndex, setStartingBidderIndex] = useState(0);
  const [isAutoDeal, setIsAutoDeal] = useState(true);
  const [activePlayer, setActivePlayer] = useState(0);
  const [hands, setHands] = useState<string[][]>([[], [], [], []]);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const used = useMemo(() => {
    return new Set(hands.flat());
  }, [hands]);

  function addCardToActive(cid: string) {
    setHands((prev) => {
      const next = prev.map((h) => [...h]);
      // Check if card is already in active player's hand
      if (next[activePlayer].includes(cid)) return prev;
      // Check if active player already has 4 cards
      if (next[activePlayer].length >= 4) return prev;
      // Check if card is used by any other player (compute from prev state, not stale closure)
      const usedCards = new Set(prev.flat());
      if (usedCards.has(cid)) return prev;
      next[activePlayer].push(cid);
      return next;
    });
  }

  function removeCard(cid: string) {
    setHands((prev) => {
      const next = prev.map((h) => h.filter((x) => x !== cid));
      return next;
    });
  }

  function clearAllHands() {
    setHands([[], [], [], []]);
  }

  async function createGame() {
    setError(null);
    setCreating(true);

    try {
      if (isAutoDeal) {
        // Auto deal mode - just send starting bidder
        const res = await http.post("/games/auto", {
          startingBidderIndex,
        });
        onGameCreated(res.data.gameId as string);
      } else {
        // Manual deal mode - validate and send first 4 hands
        const ok = hands.every((h) => h.length === 4);
        if (!ok) {
          setError("Each player must have exactly 4 cards.");
          setCreating(false);
          return;
        }

        const res = await http.post("/games", {
          startingBidderIndex,
          first4Hands: hands,
        });
        onGameCreated(res.data.gameId as string);
      }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      const msg = err?.response?.data?.detail ?? err?.message ?? "Failed to create game";
      setError(String(msg));
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="min-h-screen felt-background py-8 px-4 overflow-auto">
      <div className="bg-white/95 rounded-2xl shadow-2xl max-w-4xl w-full p-8 mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-800 mb-2">28 Card Game</h1>
          <p className="text-gray-600">Setup your game</p>
        </div>

        {/* Mode Toggle */}
        <div className="flex justify-center mb-8">
          <div className="bg-gray-100 rounded-full p-1 flex">
            <button
              className={`px-6 py-2 rounded-full font-semibold transition-all ${
                isAutoDeal
                  ? "bg-blue-600 text-white shadow"
                  : "text-gray-600 hover:text-gray-800"
              }`}
              onClick={() => setIsAutoDeal(true)}
            >
              Auto Deal
            </button>
            <button
              className={`px-6 py-2 rounded-full font-semibold transition-all ${
                !isAutoDeal
                  ? "bg-blue-600 text-white shadow"
                  : "text-gray-600 hover:text-gray-800"
              }`}
              onClick={() => setIsAutoDeal(false)}
            >
              Manual Deal
            </button>
          </div>
        </div>

        {/* Starting Bidder Selection */}
        <div className="mb-6">
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

        {/* Manual Deal Section (only shown when not auto deal) */}
        {!isAutoDeal && (
          <div className="border-t border-gray-200 pt-6 mt-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-800">
                Assign First 4 Cards to Each Player
              </h2>
              <button
                className="text-sm text-red-600 hover:text-red-700 font-medium"
                onClick={clearAllHands}
              >
                Clear All
              </button>
            </div>

            {/* Active Player Selector */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Assigning cards to:
              </label>
              <div className="flex gap-2">
                {[0, 1, 2, 3].map((idx) => (
                  <button
                    key={idx}
                    className={`flex-1 py-2 px-3 rounded-lg border-2 transition-all ${
                      activePlayer === idx
                        ? "border-green-600 bg-green-50"
                        : "border-gray-200 hover:border-gray-400"
                    }`}
                    onClick={() => setActivePlayer(idx)}
                  >
                    <div className="font-medium text-sm">{PLAYER_NAMES[idx]}</div>
                    <div className="text-xs text-gray-500">{hands[idx].length}/4 cards</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Current Hands Display */}
            <div className="grid grid-cols-2 gap-4 mb-6">
              {hands.map((hand, playerIdx) => (
                <div
                  key={playerIdx}
                  className={`p-3 rounded-lg border-2 ${
                    activePlayer === playerIdx
                      ? "border-green-400 bg-green-50"
                      : "border-gray-200"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-semibold text-sm">{PLAYER_NAMES[playerIdx]}</span>
                    <span className="text-xs text-gray-500">{hand.length}/4</span>
                  </div>
                  <div className="flex gap-1 min-h-[60px] flex-wrap">
                    {hand.map((cid) => (
                      <Card
                        key={cid}
                        cardId={cid}
                        width={40}
                        height={56}
                        onClick={() => removeCard(cid)}
                        className="hover:opacity-70"
                      />
                    ))}
                    {hand.length === 0 && (
                      <div className="text-gray-400 text-sm flex items-center">
                        No cards assigned
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Card Picker */}
            <div className="bg-gray-50 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">
                Click a card to add to {PLAYER_NAMES[activePlayer]}
              </h3>
              <div className="space-y-3">
                {SUITS.map((suit) => (
                  <div key={suit} className="flex gap-1 flex-wrap items-center">
                    <span
                      className={`w-16 text-sm font-medium ${
                        suit === "Hearts" || suit === "Diamonds"
                          ? "text-red-600"
                          : "text-gray-800"
                      }`}
                    >
                      {suit}
                    </span>
                    {RANKS_ORDERED.map((rank) => {
                      const cid = cardId(suit, rank);
                      const isUsed = used.has(cid);
                      const isInActiveHand = hands[activePlayer].includes(cid);
                      const canAdd = !isUsed && hands[activePlayer].length < 4;

                      return (
                        <Card
                          key={cid}
                          cardId={cid}
                          width={45}
                          height={63}
                          disabled={isUsed && !isInActiveHand}
                          selected={isInActiveHand}
                          onClick={canAdd ? () => addCardToActive(cid) : undefined}
                          className={canAdd ? "hover:scale-105" : ""}
                        />
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {error}
          </div>
        )}

        {/* Start Game Button */}
        <div className="mt-8">
          <button
            className="w-full py-4 bg-gradient-to-r from-green-600 to-green-700 hover:from-green-700 hover:to-green-800 text-white font-bold text-lg rounded-xl shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={createGame}
            disabled={creating || (!isAutoDeal && hands.some((h) => h.length !== 4))}
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
        <div className="mt-4 text-center text-sm text-gray-500">
          {isAutoDeal ? (
            <p>Cards will be shuffled and dealt automatically to all players.</p>
          ) : (
            <p>
              Assign exactly 4 cards to each player. The remaining 16 cards will be dealt
              in the second round.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
