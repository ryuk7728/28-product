import type { GameState, LegalActions } from "../api/types";

type Props = {
  state: GameState;
  actions: LegalActions | null;
  onRevealChoice: (seatIndex: number, reveal: boolean) => void;
  onPlayCard: (seatIndex: number, cardId: string) => void;
};

export function PlayPanel({
  state,
  actions,
  onRevealChoice,
  onPlayCard,
}: Props) {
  if (state.phase !== "PLAY" && state.phase !== "GAME_OVER") return null;

  const actor = state.turnIndex;

  return (
    <div className="rounded border border-gray-200 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-semibold">
          Catch {state.play.catchNumber} — Turn: Player {actor + 1} (
          {state.seatTypes[actor]})
        </div>
        <div className="text-sm text-gray-700">
          Team1: {state.play.team1Points} | Team2: {state.play.team2Points}
        </div>
      </div>

      <div className="mt-2 text-sm text-gray-700">
        Current suit: {state.play.currentSuit || "(not set)"} | Trump:{" "}
        {state.play.trumpReveal ? state.play.trumpSuit : "(concealed)"}
      </div>

      <div className="mt-3">
        <div className="text-sm font-semibold">Current trick</div>
        <div className="mt-2 flex flex-wrap gap-2">
          {state.play.trickCards.length === 0 && (
            <div className="text-sm text-gray-500">(no cards played yet)</div>
          )}
          {state.play.trickCards.map((c, i) => (
            <div
              key={`${c.cardId}-${i}`}
              className="rounded border border-gray-300 bg-white px-2 py-1 text-sm"
              title={state.play.trumpIndice[i] === 1 ? "Trump-active" : ""}
            >
              {c.label}
            </div>
          ))}
        </div>
      </div>

      {state.phase === "GAME_OVER" && (
        <div className="mt-4 rounded border border-green-200 bg-green-50 p-2 text-sm">
          Game Over. Winner Team: {state.play.winnerTeam}
        </div>
      )}

      {state.phase === "PLAY" &&
        actions &&
        actions.type === "REVEAL_CHOICE" &&
        state.play.trickCards.length < 4 && (
        <div className="mt-4">
          <div className="text-sm font-semibold">
            Player {actions.seatIndex + 1}: Reveal trump?
          </div>
          <div className="mt-2 flex gap-2">
            {actions.options.map((opt) => (
              <button
                key={String(opt)}
                className="rounded border border-gray-300 px-3 py-2 text-sm"
                type="button"
                onClick={() => onRevealChoice(actions.seatIndex, opt)}
                disabled={state.seatTypes[actions.seatIndex] !== "human"}
                title={
                  state.seatTypes[actions.seatIndex] !== "human"
                    ? "Bot controls this seat"
                    : ""
                }
              >
                {opt ? "Reveal" : "Don't reveal"}
              </button>
            ))}
          </div>
        </div>
      )}

      {state.phase === "PLAY" && actions && actions.type === "PLAY_CARD" && (
        <div className="mt-4">
          <div className="text-sm font-semibold">
            Player {actions.seatIndex + 1}: Play a card
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {actions.cardIds.map((cid) => (
              <button
                key={cid}
                className="rounded border border-gray-300 px-2 py-1 text-sm"
                type="button"
                onClick={() => onPlayCard(actions.seatIndex, cid)}
                disabled={state.seatTypes[actions.seatIndex] !== "human"}
                title={
                  state.seatTypes[actions.seatIndex] !== "human"
                    ? "Bot controls this seat"
                    : ""
                }
              >
                {cid}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
