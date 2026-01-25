# import asyncio
# import itertools
# import os
# from concurrent.futures import ProcessPoolExecutor

# import pytest

# import app.bots.rollout_bot as rb
# from app.settings import Settings
# from app.engine.cards_adapter import from_card_id
# from app.engine.play_engine import (
#     apply_play_card,
#     apply_reveal_choice,
#     compute_play_legal_actions,
#     init_play_state,
#     resolve_if_catch_complete,
# )
# from app.engine.state import GameState

# #k policy has to be modified to 2 for the 4th catch to match the exact legacy conditions


# def _cid(suit: str, rank: str) -> str:
#     return f"{suit}_{rank}"


# def _set_env_for_workers() -> None:
#     """
#     Ensure subprocesses use the same rollout settings.
#     Important because ProcessPool workers import modules fresh.
#     """
#     os.environ["APP_DEBUG"] = "true"
#     os.environ["APP_ROLLOUTS"] = "500"
#     os.environ["APP_WORKERS"] = "20"
#     os.environ["APP_MAX_CONCURRENT_BOT_THINKING"] = "1"
#     os.environ["APP_ROLLOUT_DEAL_RETRIES"] = "0"
#     os.environ["APP_DUMP_ROLLOUT_CRASHES"] = "0"
#     os.environ["APP_RESULT_CALL_LOG_SIZE"] = "80"
#     os.environ["APP_K_OVERRIDE"] = ""

#     # Ensure backend/ is importable in spawned workers too.
#     backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
#     old = os.environ.get("PYTHONPATH", "")
#     if backend_dir not in old.split(os.pathsep):
#         os.environ["PYTHONPATH"] = backend_dir + (os.pathsep + old if old else "")


# def _make_state_for_this_game() -> GameState:
#     """
#     Seat mapping:
#       seat 0 = P1 (BOT)
#       seat 1 = P2 (HUMAN)
#       seat 2 = P3 (BOT)
#       seat 3 = P4 (HUMAN, bidder)

#     Game setup per request:
#       - P4 is final bidder, bid=15
#       - concealed trump indicator = Clubs_Nine (removed from P4 hand initially)
#       - P1 starts the game (leaderIndex=0)
#     """
#     p1 = [
#         _cid("Diamonds", "Jack"),
#         _cid("Diamonds", "Queen"),
#         _cid("Clubs", "Ace"),
#         _cid("Clubs", "Queen"),
#         _cid("Hearts", "King"),
#         _cid("Hearts", "Eight"),
#         _cid("Spades", "Ace"),
#         _cid("Spades", "Ten"),
#     ]

#     p2 = [
#         _cid("Diamonds", "Ten"),
#         _cid("Diamonds", "King"),
#         _cid("Diamonds", "Eight"),
#         _cid("Diamonds", "Seven"),
#         _cid("Hearts", "Jack"),
#         _cid("Spades", "Jack"),
#         _cid("Spades", "Queen"),
#         _cid("Clubs", "Eight"),
#     ]

#     p3 = [
#         _cid("Clubs", "Ten"),
#         _cid("Clubs", "King"),
#         _cid("Spades", "Nine"),
#         _cid("Spades", "King"),
#         _cid("Spades", "Eight"),
#         _cid("Spades", "Seven"),
#         _cid("Hearts", "Ace"),
#         _cid("Diamonds", "Nine"),
#     ]

#     p4 = [
#         _cid("Clubs", "Jack"),
#         _cid("Clubs", "Nine"),  # concealed trump indicator (removed initially)
#         _cid("Clubs", "Seven"),
#         _cid("Hearts", "Nine"),
#         _cid("Hearts", "Ten"),
#         _cid("Hearts", "Queen"),
#         _cid("Hearts", "Seven"),
#         _cid("Diamonds", "Ace"),
#     ]

#     p1_cards = [from_card_id(x) for x in p1]
#     p2_cards = [from_card_id(x) for x in p2]
#     p3_cards = [from_card_id(x) for x in p3]
#     p4_cards = [from_card_id(x) for x in p4]

#     trump_indicator = from_card_id(_cid("Clubs", "Nine"))

#     # Remove concealed indicator from bidder (P4) hand initially
#     removed = False
#     for i, c in enumerate(p4_cards):
#         if c.identity() == trump_indicator.identity():
#             p4_cards.pop(i)
#             removed = True
#             break
#     assert removed, "Failed to remove concealed trump indicator from P4 hand."

#     state = GameState(
#         game_id="test_bots_game_p4_bid_15_trump_clubs9",
#         phase="PLAY",
#         starting_bidder_index=0,  # P1 starts Round 1
#         bidding_order=[0, 1, 2, 3],
#         players_cards=[p1_cards, p2_cards, p3_cards, p4_cards],
#         draw_pile=[],
#         event_log=[],
#     )

#     state.final_bidder_seat = 3  # P4
#     state.final_bid_value = 15
#     state.player_trump = trump_indicator

#     init_play_state(state)
#     return state


# async def _bot_expect_play(
#     state: GameState,
#     pool: ProcessPoolExecutor,
#     *,
#     bot_seat: int,
#     expect_card_id: str,
# ) -> None:
#     assert state.turn_index == bot_seat, (
#         f"Expected bot seat {bot_seat} to act, but turn_index={state.turn_index}"
#     )

#     legal = compute_play_legal_actions(state)
#     assert legal.type == "PLAY_CARD", f"Expected PLAY_CARD, got {legal.type}"

#     action_type, payload = await rb.choose_action_with_rollouts_parallel(
#         state, bot_seat, pool
#     )

#     assert action_type == "PLAY", f"Expected bot PLAY, got {action_type}"
#     assert payload["seatIndex"] == bot_seat
#     assert payload["cardId"] == expect_card_id, (
#         f"Bot seat {bot_seat} played {payload['cardId']}, expected {expect_card_id}"
#     )

#     apply_play_card(state, bot_seat, str(payload["cardId"]))
#     resolve_if_catch_complete(state)


# async def _bot_expect_reveal_then_play(
#     state: GameState,
#     pool: ProcessPoolExecutor,
#     *,
#     bot_seat: int,
#     expect_reveal: bool,
#     expect_card_id: str,
# ) -> None:
#     """
#     For the transcript moment where P3 must choose reveal=True then play a card.
#     """
#     assert state.turn_index == bot_seat, (
#         f"Expected bot seat {bot_seat} to act, but turn_index={state.turn_index}"
#     )

#     legal1 = compute_play_legal_actions(state)
#     assert legal1.type == "REVEAL_CHOICE", f"Expected REVEAL_CHOICE, got {legal1.type}"

#     action_type, payload = await rb.choose_action_with_rollouts_parallel(
#         state, bot_seat, pool
#     )
#     assert action_type == "REVEAL", f"Expected bot REVEAL, got {action_type}"
#     assert payload["seatIndex"] == bot_seat
#     assert bool(payload["reveal"]) is expect_reveal, (
#         f"Expected reveal={expect_reveal}, got {payload['reveal']}"
#     )

#     apply_reveal_choice(state, bot_seat, bool(payload["reveal"]))
#     resolve_if_catch_complete(state)

#     # Reveal doesn't add to the trick; same actor must play next
#     assert state.turn_index == bot_seat, (
#         f"After reveal, expected bot seat {bot_seat} to act, "
#         f"but turn_index={state.turn_index}"
#     )

#     legal2 = compute_play_legal_actions(state)
#     assert legal2.type == "PLAY_CARD", f"Expected PLAY_CARD, got {legal2.type}"

#     action_type2, payload2 = await rb.choose_action_with_rollouts_parallel(
#         state, bot_seat, pool
#     )

#     assert action_type2 == "PLAY", f"Expected bot PLAY, got {action_type2}"
#     assert payload2["seatIndex"] == bot_seat
#     assert payload2["cardId"] == expect_card_id, (
#         f"Bot seat {bot_seat} played {payload2['cardId']}, expected {expect_card_id}"
#     )

#     apply_play_card(state, bot_seat, str(payload2["cardId"]))
#     resolve_if_catch_complete(state)


# def _human_play_card(state: GameState, *, seat: int, card_id: str) -> None:
#     """
#     Apply a forced human play. If engine demands REVEAL_CHOICE first,
#     we auto pick reveal=False (should not occur in this transcript before
#     P3 reveals in Round 2; after that trumpReveal=True so no reveal choices).
#     """
#     assert state.turn_index == seat, (
#         f"Expected human seat {seat} to act, but turn_index={state.turn_index}"
#     )

#     legal = compute_play_legal_actions(state)
#     if legal.type == "REVEAL_CHOICE":
#         apply_reveal_choice(state, seat, False)
#         resolve_if_catch_complete(state)

#         assert state.turn_index == seat
#         legal = compute_play_legal_actions(state)

#     assert legal.type == "PLAY_CARD", f"Expected PLAY_CARD, got {legal.type}"
#     assert legal.cardIds and card_id in legal.cardIds, (
#         f"Card {card_id} not legal for seat {seat}. Legal: {legal.cardIds}"
#     )

#     apply_play_card(state, seat, card_id)
#     resolve_if_catch_complete(state)


# @pytest.mark.slow
# def test_bots_reproduce_known_game_p4_bid15_trump_clubs9(monkeypatch) -> None:
#     """
#     Replays the provided transcript and asserts bot plays match exactly.

#     Uses:
#       - 500 rollouts
#       - ProcessPoolExecutor multiprocessing (20 workers)
#       - deterministic seeds to stabilize CI runs
#     """
#     _set_env_for_workers()

#     # Ensure main-process rollout settings match required config
#     rb.settings = Settings(
#         debug=True,
#         rollouts=500,
#         workers=20,
#         rollout_deal_retries=30,
#         max_concurrent_bot_thinking=1,
#         k_override=None,
#         cors_origins=("http://localhost:5173", "http://127.0.0.1:5173"),
#     )

#     # Make rollouts deterministic (seed per worker task)
#     seed_iter = itertools.count(200_000)
#     monkeypatch.setattr(rb, "_seed_entropy", lambda: next(seed_iter))

#     state = _make_state_for_this_game()

#     async def run() -> None:
#         with ProcessPoolExecutor(max_workers=20) as pool:
#             # -------------------------
#             # ROUND 1 (P1 starts)
#             # 1) JD, 2) TD, 3) 9D, 4) AD
#             # -------------------------
#             assert state.catchNumber == 1
#             assert state.leaderIndex == 0

#             await _bot_expect_play(
#                 state, pool, bot_seat=0, expect_card_id=_cid("Diamonds", "Jack")
#             )
#             _human_play_card(state, seat=1, card_id=_cid("Diamonds", "Ten"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=2, expect_card_id=_cid("Diamonds", "Nine")
#             )
#             _human_play_card(state, seat=3, card_id=_cid("Diamonds", "Ace"))

#             # Next leader: P1
#             assert state.catchNumber == 2
#             assert state.leaderIndex == 0

#             # -------------------------
#             # ROUND 2 (P1 starts)
#             # 1) QD, 2) KD, 3) True, 3) TC, 4) 9C
#             # -------------------------
#             await _bot_expect_play(
#                 state, pool, bot_seat=0, expect_card_id=_cid("Diamonds", "Queen")
#             )
#             _human_play_card(state, seat=1, card_id=_cid("Diamonds", "King"))

#             # P3 must reveal True, then play Ten of Clubs
#             await _bot_expect_reveal_then_play(
#                 state,
#                 pool,
#                 bot_seat=2,
#                 expect_reveal=True,
#                 expect_card_id=_cid("Clubs", "Ten"),
#             )

#             # P4 plays Clubs_Nine (this was the concealed indicator card)
#             _human_play_card(state, seat=3, card_id=_cid("Clubs", "Nine"))

#             # Next leader: P4 (won with higher trump)
#             assert state.catchNumber == 3
#             assert state.leaderIndex == 3
#             assert state.trumpReveal is True

#             # -------------------------
#             # ROUND 3 (P4 starts)
#             # 4) 7H, 1) KH, 2) JH, 3) AH
#             # -------------------------
#             _human_play_card(state, seat=3, card_id=_cid("Hearts", "Seven"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=0, expect_card_id=_cid("Hearts", "King")
#             )
#             _human_play_card(state, seat=1, card_id=_cid("Hearts", "Jack"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=2, expect_card_id=_cid("Hearts", "Ace")
#             )

#             # Next leader: P2
#             assert state.catchNumber == 4
#             assert state.leaderIndex == 1

#             # -------------------------
#             # ROUND 4 (P2 starts)
#             # 2) JS, 3) KS, 4) 9H, 1) AS
#             # -------------------------
#             _human_play_card(state, seat=1, card_id=_cid("Spades", "Jack"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=2, expect_card_id=_cid("Spades", "King")
#             )
#             _human_play_card(state, seat=3, card_id=_cid("Hearts", "Nine"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=0, expect_card_id=_cid("Spades", "Ace")
#             )

#             # Next leader: P2
#             assert state.catchNumber == 5
#             assert state.leaderIndex == 1

#             # -------------------------
#             # ROUND 5 (P2 starts)
#             # 2) QS, 3) 9S, 4) 7C, 1) TS
#             # -------------------------
#             _human_play_card(state, seat=1, card_id=_cid("Spades", "Queen"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=2, expect_card_id=_cid("Spades", "Nine")
#             )
#             _human_play_card(state, seat=3, card_id=_cid("Clubs", "Seven"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=0, expect_card_id=_cid("Spades", "Ten")
#             )

#             # Next leader: P4 (trumped)
#             assert state.catchNumber == 6
#             assert state.leaderIndex == 3

#             # -------------------------
#             # ROUND 6 (P4 starts)
#             # 4) QH, 1) 8H, 2) 8D, 3) KC
#             # -------------------------
#             _human_play_card(state, seat=3, card_id=_cid("Hearts", "Queen"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=0, expect_card_id=_cid("Hearts", "Eight")
#             )
#             _human_play_card(state, seat=1, card_id=_cid("Diamonds", "Eight"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=2, expect_card_id=_cid("Clubs", "King")
#             )

#             # Next leader: P3 (trumped)
#             assert state.catchNumber == 7
#             assert state.leaderIndex == 2

#             # -------------------------
#             # ROUND 7 (P3 starts)
#             # 3) 8S, 4) TH, 1) AC, 2) 7D
#             # -------------------------
#             await _bot_expect_play(
#                 state, pool, bot_seat=2, expect_card_id=_cid("Spades", "Eight")
#             )
#             _human_play_card(state, seat=3, card_id=_cid("Hearts", "Ten"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=0, expect_card_id=_cid("Clubs", "Ace")
#             )
#             _human_play_card(state, seat=1, card_id=_cid("Diamonds", "Seven"))

#             # Next leader: P1 (trumped with AC)
#             assert state.catchNumber == 8
#             assert state.leaderIndex == 0

#             # -------------------------
#             # ROUND 8 (P1 starts)
#             # 1) QC, 2) 8C, 3) 7S, 4) JC
#             # -------------------------
#             await _bot_expect_play(
#                 state, pool, bot_seat=0, expect_card_id=_cid("Clubs", "Queen")
#             )
#             _human_play_card(state, seat=1, card_id=_cid("Clubs", "Eight"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=2, expect_card_id=_cid("Spades", "Seven")
#             )
#             _human_play_card(state, seat=3, card_id=_cid("Clubs", "Jack"))

#             assert state.phase == "GAME_OVER"
#             assert state.winnerTeam in (1, 2)

#     asyncio.run(run())