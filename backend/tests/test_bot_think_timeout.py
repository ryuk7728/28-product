from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Future
from dataclasses import dataclass
from types import SimpleNamespace

import app.bots.rollout_bot as rb
import app.engine.play_engine as pe
import app.engine.bot_runner as bot_runner
from app.engine.cards_adapter import from_card_id
from app.settings import Settings


@dataclass
class _FakePool:
    plan: list[tuple[float, str]]
    _idx: int = 0

    def submit(self, _fn, _snapshot, n: int, _seed: int):
        fut: Future = Future()
        idx = self._idx
        self._idx += 1
        delay, token = self.plan[idx] if idx < len(self.plan) else self.plan[-1]

        def _complete() -> None:
            if fut.cancelled() or fut.done():
                return
            fut.set_result({token: n})

        timer = threading.Timer(delay, _complete)
        timer.daemon = True
        timer.start()
        return fut


@dataclass
class _MetadataPool:
    plan: list[tuple[float, dict[str, int], int]]
    _idx: int = 0

    def submit(self, _fn, _snapshot, _n: int, _seed: int):
        fut: Future = Future()
        delay, counts, completed = self.plan[self._idx]
        self._idx += 1

        def _complete() -> None:
            if not fut.done():
                fut.set_result(
                    {"counts": counts, "completedRollouts": completed}
                )

        timer = threading.Timer(delay, _complete)
        timer.daemon = True
        timer.start()
        return fut


def _mk_settings_for_timeout(*, timeout_seconds: float, batch_size: int) -> Settings:
    return Settings(
        debug=True,
        rollouts=20,
        workers=4,
        rollout_deal_retries=0,
        rollout_metrics=False,
        rollout_metrics_interval=10.0,
        max_concurrent_bot_thinking=1,
        bot_think_timeout_seconds=timeout_seconds,
        rollout_micro_batch_size=batch_size,
        rollout_backend="local",
        ray_address=None,
        k_override=None,
        fixed_deck_enabled=False,
        fixed_deck_path="",
        room_ttl_seconds=24 * 60 * 60,
        cors_origins=("http://localhost:5173",),
    )


def test_build_rollout_batch_sizes_timeout_mode() -> None:
    batches = rb._build_rollout_batch_sizes(
        total_rollouts=23,
        worker_count=4,
        timeout_enabled=True,
        micro_batch_size=5,
    )
    assert batches == [5, 5, 5, 5, 3]


def test_build_rollout_batch_sizes_non_timeout_mode_matches_legacy_split() -> None:
    batches = rb._build_rollout_batch_sizes(
        total_rollouts=500,
        worker_count=12,
        timeout_enabled=False,
        micro_batch_size=5,
    )
    assert len(batches) == 12
    assert sum(batches) == 500
    assert batches.count(42) == 8
    assert batches.count(41) == 4


def test_timeout_uses_partial_completed_batches(monkeypatch) -> None:
    legal_ids = ["Hearts_Seven", "Clubs_Seven"]
    fast_token = from_card_id("Hearts_Seven").identity()
    slow_token = from_card_id("Clubs_Seven").identity()

    rb.settings = _mk_settings_for_timeout(timeout_seconds=0.05, batch_size=5)

    monkeypatch.setattr(
        pe,
        "compute_play_legal_actions",
        lambda _state: SimpleNamespace(type="PLAY_CARD", seatIndex=0, cardIds=legal_ids),
    )
    monkeypatch.setattr(
        rb,
        "_build_snapshot",
        lambda _state, _bot_seat: {"botHandCardIds": legal_ids},
    )

    fake_pool = _FakePool(
        plan=[
            (0.01, fast_token),
            (0.01, fast_token),
            (0.20, slow_token),
            (0.20, slow_token),
        ]
    )
    state = SimpleNamespace(event_log=[])

    action_type, payload = asyncio.run(
        rb.choose_action_with_rollouts_parallel(state, bot_seat=0, pool=fake_pool)
    )

    assert action_type == "PLAY"
    assert payload["cardId"] == "Hearts_Seven"
    assert any("Bot think timeout hit" in x for x in state.event_log)


def test_timeout_with_no_completed_batches_falls_back(monkeypatch) -> None:
    legal_ids = ["Hearts_Seven", "Clubs_Seven"]
    slow_token = from_card_id("Clubs_Seven").identity()

    rb.settings = _mk_settings_for_timeout(timeout_seconds=0.01, batch_size=5)

    monkeypatch.setattr(
        pe,
        "compute_play_legal_actions",
        lambda _state: SimpleNamespace(type="PLAY_CARD", seatIndex=0, cardIds=legal_ids),
    )
    monkeypatch.setattr(
        rb,
        "_build_snapshot",
        lambda _state, _bot_seat: {"botHandCardIds": legal_ids},
    )

    fake_pool = _FakePool(plan=[(0.20, slow_token)])
    state = SimpleNamespace(event_log=[])

    action_type, payload = asyncio.run(
        rb.choose_action_with_rollouts_parallel(state, bot_seat=0, pool=fake_pool)
    )

    assert action_type == "PLAY"
    assert payload["cardId"] == "Hearts_Seven"
    assert any("Bot think timeout hit" in x for x in state.event_log)


def test_timeout_merges_every_worker_reported_completed_rollout(monkeypatch) -> None:
    legal_ids = ["Hearts_Seven", "Clubs_Seven"]
    hearts = from_card_id("Hearts_Seven").identity()
    clubs = from_card_id("Clubs_Seven").identity()
    rb.settings = _mk_settings_for_timeout(timeout_seconds=0.04, batch_size=5)
    monkeypatch.setattr(
        pe,
        "compute_play_legal_actions",
        lambda _state: SimpleNamespace(type="PLAY_CARD", seatIndex=0, cardIds=legal_ids),
    )
    monkeypatch.setattr(rb, "_build_snapshot", lambda _state, _seat: {})
    pool = _MetadataPool(
        plan=[
            (0.005, {hearts: 4}, 4),
            (0.010, {clubs: 5}, 5),
            # These workers return after the outer wait, as real Rust workers do
            # while unwinding. One preserves pre-deadline completed rollouts.
            (0.050, {clubs: 3}, 3),
            (0.050, {}, 0),
        ]
    )
    state = SimpleNamespace(event_log=[])

    action_type, payload = asyncio.run(
        rb.choose_action_with_rollouts_parallel(state, 0, pool)
    )

    assert action_type == "PLAY"
    assert payload["cardId"] == "Clubs_Seven"
    assert any("used 12/20 rollouts" in item for item in state.event_log)


def test_equal_rollout_counts_use_stable_action_order(monkeypatch) -> None:
    legal_ids = ["Hearts_Seven", "Clubs_Seven"]
    hearts = from_card_id("Hearts_Seven").identity()
    clubs = from_card_id("Clubs_Seven").identity()
    rb.settings = _mk_settings_for_timeout(timeout_seconds=0.1, batch_size=5)
    monkeypatch.setattr(
        pe,
        "compute_play_legal_actions",
        lambda _state: SimpleNamespace(type="PLAY_CARD", seatIndex=0, cardIds=legal_ids),
    )
    monkeypatch.setattr(rb, "_build_snapshot", lambda _state, _seat: {})

    expected_identity = min(hearts, clubs)
    expected_card = next(
        card_id
        for card_id in legal_ids
        if from_card_id(card_id).identity() == expected_identity
    )
    chosen = []
    for plan in (
        [(0.005, {hearts: 5}, 5), (0.010, {clubs: 5}, 5)],
        [(0.010, {hearts: 5}, 5), (0.005, {clubs: 5}, 5)],
    ):
        pool = _MetadataPool(plan=plan + [(0.20, {}, 0), (0.20, {}, 0)])
        _, payload = asyncio.run(
            rb.choose_action_with_rollouts_parallel(
                SimpleNamespace(event_log=[]), 0, pool
            )
        )
        chosen.append(payload["cardId"])

    assert chosen == [expected_card, expected_card]


def test_bot_runner_broadcasts_authoritative_deadline_and_clears_it(monkeypatch) -> None:
    state = SimpleNamespace(
        phase="PLAY",
        leaderIndex=0,
        s=[],
        bot_think_timeout_seconds=0.05,
        bot_thinking=None,
    )
    seen_calls: list[tuple[float, int]] = []
    broadcasts: list[dict[str, object] | None] = []

    monkeypatch.setattr(
        bot_runner,
        "compute_play_legal_actions",
        lambda _state: SimpleNamespace(type="PLAY_CARD"),
    )

    async def fake_choose(_state, _actor, _pool, **kwargs):
        seen_calls.append((kwargs["timeout_seconds"], kwargs["deadline_epoch_ms"]))
        assert _state.bot_thinking is not None
        return "PLAY", {"seatIndex": 0, "cardId": "Hearts_Seven"}

    def fake_play(current, _seat, _card):
        current.phase = "GAME_OVER"

    async def fake_send(_ws, current):
        broadcasts.append(
            dict(current.bot_thinking) if current.bot_thinking is not None else None
        )

    monkeypatch.setattr(bot_runner, "choose_action_with_rollouts_parallel", fake_choose)
    monkeypatch.setattr(bot_runner, "apply_play_card", fake_play)

    asyncio.run(
        bot_runner.advance_bots_until_human(
            state,
            pool=object(),
            bot_sem=asyncio.Semaphore(1),
            websocket=object(),
            send_state_fn=fake_send,
        )
    )

    assert seen_calls and seen_calls[0][0] == 0.05
    assert broadcasts[0] is not None
    assert broadcasts[0]["seatIndex"] == 0
    assert broadcasts[0]["deadlineEpochMs"] == seen_calls[0][1]
    assert state.bot_thinking is None
