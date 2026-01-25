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
#     This matters because ProcessPool workers import modules fresh.
#     """
#     os.environ["APP_DEBUG"] = "true"
#     os.environ["APP_ROLLOUTS"] = "500"
#     os.environ["APP_WORKERS"] = "20"
#     os.environ["APP_MAX_CONCURRENT_BOT_THINKING"] = "1"
#     os.environ["APP_ROLLOUT_DEAL_RETRIES"] = "0"
#     os.environ["APP_DUMP_ROLLOUT_CRASHES"] = "0"
#     os.environ["APP_RESULT_CALL_LOG_SIZE"] = "80"
#     os.environ["APP_K_OVERRIDE"] = ""

#     backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
#     old = os.environ.get("PYTHONPATH", "")
#     if backend_dir not in old.split(os.pathsep):
#         os.environ["PYTHONPATH"] = backend_dir + (os.pathsep + old if old else "")


# def _make_state_for_this_game() -> GameState:
#     """
#     Seat mapping:
#       seat 0 = P1 (BOT)
#       seat 1 = P2 (HUMAN, bidder)
#       seat 2 = P3 (BOT)
#       seat 3 = P4 (HUMAN)

#     Game setup:
#       - P2 is bidder
#       - bid value = 15
#       - concealed trump indicator = Hearts_Eight (removed from bidder hand initially)
#       - leader for trick 1 is P2 (seat 1)
#     """
#     p1 = [
#         _cid("Clubs", "Jack"),
#         _cid("Clubs", "Ace"),
#         _cid("Clubs", "Ten"),
#         _cid("Spades", "Ten"),
#         _cid("Spades", "Eight"),
#         _cid("Spades", "Seven"),
#         _cid("Diamonds", "Ace"),
#         _cid("Diamonds", "Seven"),
#     ]

#     p2 = [
#         _cid("Hearts", "Jack"),
#         _cid("Hearts", "Nine"),
#         _cid("Hearts", "King"),
#         _cid("Spades", "Nine"),
#         _cid("Spades", "King"),
#         _cid("Diamonds", "Ten"),
#         _cid("Diamonds", "Eight"),
#         _cid("Hearts", "Eight"),  # concealed trump indicator card
#     ]

#     p3 = [
#         _cid("Diamonds", "Jack"),
#         _cid("Diamonds", "King"),
#         _cid("Diamonds", "Queen"),
#         _cid("Hearts", "Ace"),
#         _cid("Hearts", "Seven"),
#         _cid("Clubs", "Nine"),
#         _cid("Clubs", "King"),
#         _cid("Clubs", "Queen"),
#     ]

#     p4 = [
#         _cid("Spades", "Jack"),
#         _cid("Spades", "Ace"),
#         _cid("Spades", "Queen"),
#         _cid("Clubs", "Eight"),
#         _cid("Clubs", "Seven"),
#         _cid("Diamonds", "Nine"),
#         _cid("Hearts", "Ten"),
#         _cid("Hearts", "Queen"),
#     ]

#     # Convert to Cards objects
#     p1_cards = [from_card_id(x) for x in p1]
#     p2_cards = [from_card_id(x) for x in p2]
#     p3_cards = [from_card_id(x) for x in p3]
#     p4_cards = [from_card_id(x) for x in p4]

#     # Remove the concealed trump indicator from bidder hand initially
#     trump_indicator = from_card_id(_cid("Hearts", "Eight"))
#     removed = False
#     for i, c in enumerate(p2_cards):
#         if c.identity() == trump_indicator.identity():
#             p2_cards.pop(i)
#             removed = True
#             break
#     assert removed, "Failed to remove trump indicator from P2 hand."

#     state = GameState(
#         game_id="test_bots_known_game",
#         phase="PLAY",
#         starting_bidder_index=1,  # P2 leads Round 1
#         bidding_order=[0, 1, 2, 3],
#         players_cards=[p1_cards, p2_cards, p3_cards, p4_cards],
#         draw_pile=[],
#         event_log=[],
#     )

#     # Contract / bidder config
#     state.final_bidder_seat = 1  # P2
#     state.final_bid_value = 15
#     state.player_trump = trump_indicator  # concealed

#     init_play_state(state)
#     return state


# async def _bot_expect_reveal_then_play(
#     state: GameState,
#     pool: ProcessPoolExecutor,
#     *,
#     bot_seat: int,
#     expect_reveal: bool,
#     expect_card_id: str,
# ) -> None:
#     """
#     For the special "REVEAL_CHOICE then PLAY_CARD" double-step (Round 3 for P3).
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

#     # Same bot acts again (reveal doesn't add a card to the trick)
#     assert state.turn_index == bot_seat, (
#         f"After reveal, expected same bot seat {bot_seat} to act, "
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


# def _human_play_card(
#     state: GameState,
#     *,
#     seat: int,
#     card_id: str,
# ) -> None:
#     """
#     Applies a forced human action. If the engine demands a REVEAL_CHOICE first
#     (void + trump not revealed), we automatically choose reveal=False once.
#     (This occurs in your transcript in Round 2 for P4.)
#     """
#     assert state.turn_index == seat, (
#         f"Expected human seat {seat} to act, but turn_index={state.turn_index}"
#     )

#     legal = compute_play_legal_actions(state)
#     if legal.type == "REVEAL_CHOICE":
#         # Transcript doesn't list it, but legacy engine requires it.
#         apply_reveal_choice(state, seat, False)
#         resolve_if_catch_complete(state)

#         assert state.turn_index == seat, (
#             "After reveal=False, expected same seat to still act."
#         )
#         legal = compute_play_legal_actions(state)

#     assert legal.type == "PLAY_CARD", f"Expected PLAY_CARD, got {legal.type}"
#     assert legal.cardIds and card_id in legal.cardIds, (
#         f"Card {card_id} not legal for seat {seat}. Legal: {legal.cardIds}"
#     )

#     apply_play_card(state, seat, card_id)
#     resolve_if_catch_complete(state)


# @pytest.mark.slow
# def test_bots_reproduce_known_game_with_rollouts_and_multiprocessing(
#     monkeypatch,
# ) -> None:
#     """
#     Replays the exact transcript and asserts bot seats (0 and 2) match.
#     Uses 500 rollouts and multiprocessing workers like production.
#     """
#     _set_env_for_workers()

#     # Ensure main-process rollout settings match requirement
#     rb.settings = Settings(
#         debug=True,
#         rollouts=500,
#         workers=20,
#         rollout_deal_retries=30,
#         max_concurrent_bot_thinking=1,
#         k_override=None,
#         cors_origins=("http://localhost:5173", "http://127.0.0.1:5173"),
#     )

#     # Make rollout seeds deterministic (stabilizes this test)
#     seed_iter = itertools.count(100_000)
#     monkeypatch.setattr(rb, "_seed_entropy", lambda: next(seed_iter))

#     state = _make_state_for_this_game()

#     async def run() -> None:
#         with ProcessPoolExecutor(max_workers=20) as pool:
#             # -------------------------
#             # ROUND 1 (P2 starts / seat1)
#             # -------------------------
#             assert state.leaderIndex == 1

#             _human_play_card(state, seat=1, card_id=_cid("Diamonds", "Eight"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=2, expect_card_id=_cid("Diamonds", "Jack")
#             )
#             _human_play_card(state, seat=3, card_id=_cid("Diamonds", "Nine"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=0, expect_card_id=_cid("Diamonds", "Ace")
#             )

#             # After Round 1, transcript says Round 2 starts with P3 (seat2)
#             assert state.catchNumber == 2
#             assert state.leaderIndex == 2

#             # -------------------------
#             # ROUND 2 (P3 starts / seat2)
#             # -------------------------
#             await _bot_expect_play(
#                 state, pool, bot_seat=2, expect_card_id=_cid("Diamonds", "King")
#             )
#             _human_play_card(state, seat=3, card_id=_cid("Clubs", "Eight"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=0, expect_card_id=_cid("Diamonds", "Seven")
#             )
#             _human_play_card(state, seat=1, card_id=_cid("Diamonds", "Ten"))

#             # After Round 2, transcript says Round 3 starts with P2 (seat1)
#             assert state.catchNumber == 3
#             assert state.leaderIndex == 1

#             # -------------------------
#             # ROUND 3 (P2 starts / seat1)
#             # -------------------------
#             _human_play_card(state, seat=1, card_id=_cid("Spades", "King"))

#             # P3 must reveal True, then play Ace of Hearts
#             await _bot_expect_reveal_then_play(
#                 state,
#                 pool,
#                 bot_seat=2,
#                 expect_reveal=True,
#                 expect_card_id=_cid("Hearts", "Ace"),
#             )

#             _human_play_card(state, seat=3, card_id=_cid("Spades", "Queen"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=0, expect_card_id=_cid("Spades", "Ten")
#             )

#             # After Round 3, transcript says Round 4 starts with P3 (seat2)
#             assert state.catchNumber == 4
#             assert state.leaderIndex == 2
#             assert state.trumpReveal is True, "Trump should be revealed after Round 3."

#             # -------------------------
#             # ROUND 4 (P3 starts / seat2)
#             # -------------------------
#             await _bot_expect_play(
#                 state, pool, bot_seat=2, expect_card_id=_cid("Hearts", "Seven")
#             )
#             _human_play_card(state, seat=3, card_id=_cid("Hearts", "Queen"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=0, expect_card_id=_cid("Spades", "Eight")
#             )
#             _human_play_card(state, seat=1, card_id=_cid("Hearts", "King"))

#             # After Round 4, transcript says Round 5 starts with P2 (seat1)
#             assert state.catchNumber == 5
#             assert state.leaderIndex == 1

#             # -------------------------
#             # ROUND 5 (P2 starts / seat1)
#             # -------------------------
#             _human_play_card(state, seat=1, card_id=_cid("Hearts", "Jack"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=2, expect_card_id=_cid("Diamonds", "Queen")
#             )
#             _human_play_card(state, seat=3, card_id=_cid("Hearts", "Ten"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=0, expect_card_id=_cid("Spades", "Seven")
#             )

#             # After Round 5, transcript says Round 6 starts with P2 (seat1)
#             assert state.catchNumber == 6
#             assert state.leaderIndex == 1

#             # -------------------------
#             # ROUND 6 (P2 starts / seat1)
#             # -------------------------
#             _human_play_card(state, seat=1, card_id=_cid("Hearts", "Nine"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=2, expect_card_id=_cid("Clubs", "King")
#             )
#             _human_play_card(state, seat=3, card_id=_cid("Spades", "Ace"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=0, expect_card_id=_cid("Clubs", "Ace")
#             )

#             # After Round 6, transcript says Round 7 starts with P2 (seat1)
#             assert state.catchNumber == 7
#             assert state.leaderIndex == 1

#             # -------------------------
#             # ROUND 7 (P2 starts / seat1)
#             # -------------------------
#             # Note: Hearts_Eight was the concealed trump indicator and should
#             # have been added to P2 hand when P3 revealed in Round 3.
#             _human_play_card(state, seat=1, card_id=_cid("Hearts", "Eight"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=2, expect_card_id=_cid("Clubs", "Queen")
#             )
#             _human_play_card(state, seat=3, card_id=_cid("Clubs", "Seven"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=0, expect_card_id=_cid("Clubs", "Ten")
#             )

#             # After Round 7, transcript says Round 8 starts with P2 (seat1)
#             assert state.catchNumber == 8
#             assert state.leaderIndex == 1

#             # -------------------------
#             # ROUND 8 (P2 starts / seat1)
#             # -------------------------
#             _human_play_card(state, seat=1, card_id=_cid("Spades", "Nine"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=2, expect_card_id=_cid("Clubs", "Nine")
#             )
#             _human_play_card(state, seat=3, card_id=_cid("Spades", "Jack"))
#             await _bot_expect_play(
#                 state, pool, bot_seat=0, expect_card_id=_cid("Clubs", "Jack")
#             )

#             # Game should end after 8 tricks
#             assert state.phase == "GAME_OVER"
#             assert state.winnerTeam in (1, 2)

#     asyncio.run(run())


