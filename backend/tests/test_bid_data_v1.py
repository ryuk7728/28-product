from __future__ import annotations

import asyncio
from concurrent.futures import ProcessPoolExecutor

from app.engine.canonical_key import build_canonical_key_and_mapping
from app.bots.rollout_bot import _deterministic_batch_seed
from app.engine.cards_adapter import from_card_id
from app.engine.play_engine import compute_play_legal_actions
from app.legacy import minimax as legacy_minimax
from app.experiments.bid_data_v1 import (
    _full_deal_abort_reason,
    build_sample_request,
    canonical_catalog,
    load_contract,
    prepare_sample,
    simulate_prepared_sample,
)
from app.experiments.gcs_results import encode_rows, parse_gcs_uri, shard_object_name


def _first_zero_point_key_index() -> int:
    for entry in canonical_catalog():
        if sum(from_card_id(card_id).points for card_id in entry.physical_hands[0]) == 0:
            return entry.index
    raise AssertionError("Expected at least one zero-point canonical key.")


def test_contract_and_catalog_match_exhaustive_population() -> None:
    contract = load_contract()
    catalog = canonical_catalog()

    assert len(catalog) == contract["population"]["canonical_key_count"] == 2262
    assert sum(len(entry.physical_hands) for entry in catalog) == 35960
    assert len({entry.canonical_key_id for entry in catalog}) == len(catalog)


def test_rollout_batch_seeds_are_stable_and_distinct() -> None:
    first = [_deterministic_batch_seed(123456, index) for index in range(8)]
    second = [_deterministic_batch_seed(123456, index) for index in range(8)]

    assert first == second
    assert len(set(first)) == len(first)
    assert first != [_deterministic_batch_seed(654321, index) for index in range(8)]


def test_gcs_shard_names_and_compressed_payloads_are_deterministic() -> None:
    location = parse_gcs_uri("gs://example-bucket/raw/results/")
    assert location.bucket == "example-bucket"
    assert location.prefix == "raw/results"

    name = shard_object_name(
        prefix=location.prefix,
        run_id="run-v1",
        policy_id="baseline",
        key_index=12,
        canonical_key_id="abcdef0123456789",
        sample_start=25,
        sample_count=25,
    )
    assert name == (
        "raw/results/run-v1/baseline/key-0012-abcdef012345/"
        "samples-025-049.ndjson.gz"
    )
    rows = [{"result_id": "a", "status": "COMPLETED"}]
    assert encode_rows(rows) == encode_rows(rows)


def test_conditional_deal_is_deterministic_legal_and_maps_to_requested_key() -> None:
    request = build_sample_request(
        key_index=100,
        sample_index=17,
        root_seed="phase-2-test-seed",
    )

    first = prepare_sample(request)
    second = prepare_sample(request)

    assert first == second
    assert first.status == "READY"
    assert first.full_hand_card_ids_by_seat is not None
    assert first.visible_hand_card_ids_by_seat is not None

    all_cards = [card_id for hand in first.full_hand_card_ids_by_seat for card_id in hand]
    assert len(all_cards) == 32
    assert len(set(all_cards)) == 32
    assert [len(hand) for hand in first.full_hand_card_ids_by_seat] == [8, 8, 8, 8]
    assert [len(hand) for hand in first.visible_hand_card_ids_by_seat] == [7, 8, 8, 8]
    assert first.selected_trump_card_id in first.physical_first4_card_ids

    canonical = build_canonical_key_and_mapping(list(first.physical_first4_card_ids))
    assert canonical.canonical_groups == first.entry.canonical_key_lists()


def test_bid_positions_balance_and_only_opening_zero_point_slot_redeals() -> None:
    key_index = _first_zero_point_key_index()
    prepared = [
        prepare_sample(
            build_sample_request(
                key_index=key_index,
                sample_index=sample_index,
                root_seed="redeal-position-test",
            )
        )
        for sample_index in range(4)
    ]

    assert [sample.bid_position for sample in prepared] == [1, 2, 3, 4]
    assert [sample.starting_bidder_seat for sample in prepared] == [0, 3, 2, 1]
    assert prepared[0].status == "REDEAL"
    assert all(sample.status == "READY" for sample in prepared[1:])

    positions = [1 + (sample_index % 4) for sample_index in range(100)]
    assert {position: positions.count(position) for position in range(1, 5)} == {
        1: 25,
        2: 25,
        3: 25,
        4: 25,
    }


def test_full_deal_abort_rules_match_game_rules() -> None:
    four_jacks = (
        ("Clubs_Jack", "Diamonds_Jack", "Hearts_Jack", "Spades_Jack"),
        tuple(),
        tuple(),
        tuple(),
    )
    assert (
        _full_deal_abort_reason(four_jacks, bidder_seat=0, trump_suit="Clubs")
        == "ALL_FOUR_JACKS"
    )

    all_clubs_on_bidder_team = (
        ("Clubs_Jack", "Clubs_Nine", "Clubs_Ace", "Clubs_Ten"),
        tuple(),
        ("Clubs_King", "Clubs_Queen", "Clubs_Eight", "Clubs_Seven"),
        tuple(),
    )
    assert (
        _full_deal_abort_reason(
            all_clubs_on_bidder_team,
            bidder_seat=0,
            trump_suit="Clubs",
        )
        == "ALL_TRUMPS_ONE_SIDE"
    )


def test_target_first_four_jacks_is_a_deterministic_abort() -> None:
    entry = next(
        entry
        for entry in canonical_catalog()
        if entry.canonical_key_lists() == [["J"], ["J"], ["J"], ["J"]]
    )
    prepared = prepare_sample(
        build_sample_request(
            key_index=entry.index,
            sample_index=0,
            root_seed="four-jacks-test",
        )
    )

    assert prepared.status == "ABORT"
    assert prepared.full_deal_attempt_count == 1
    assert prepared.abort_reason_counts == {"ALL_FOUR_JACKS": 1}
    assert prepared.full_hand_card_ids_by_seat is None


def test_headless_runner_completes_without_websocket_or_display_delays() -> None:
    async def deterministic_legal_chooser(state, actor, _pool, **kwargs):
        assert kwargs["strict"] is True
        assert isinstance(kwargs["rollout_seed_base"], int)
        legal = compute_play_legal_actions(state)
        if legal.type == "REVEAL_CHOICE":
            reveal = False if False in legal.options else True
            return "REVEAL", {"seatIndex": actor, "reveal": reveal}
        return "PLAY", {"seatIndex": actor, "cardId": legal.cardIds[0]}

    prepared = prepare_sample(
        build_sample_request(
            key_index=0,
            sample_index=1,
            root_seed="headless-completion-test",
        )
    )

    async def run():
        with ProcessPoolExecutor(max_workers=1) as pool:
            return await simulate_prepared_sample(
                prepared,
                pool=pool,
                chooser=deterministic_legal_chooser,
                enforce_runtime=False,
            )

    row = asyncio.run(run())

    assert row["status"] == "COMPLETED"
    assert row["team1_points"] + row["team2_points"] == 28
    assert row["bidder_team_points"] in {row["team1_points"], row["team2_points"]}
    assert 32 <= row["decision_count"] <= 64
    assert row["simulation_seconds"] < 1
    assert row["deal_id"] == prepared.deal_id
    assert row["minimax_backend"] in {"rust", "rust_unavailable", "python"}


def test_deal_identity_is_shared_across_paired_policy_comparison() -> None:
    baseline = prepare_sample(
        build_sample_request(
            key_index=42,
            sample_index=9,
            root_seed="paired-policy-test",
            policy_name="baseline",
        )
    )
    option_a = prepare_sample(
        build_sample_request(
            key_index=42,
            sample_index=9,
            root_seed="paired-policy-test",
            policy_name="option_a",
        )
    )

    assert baseline.deal_id == option_a.deal_id
    assert baseline.physical_first4_card_ids == option_a.physical_first4_card_ids
    assert baseline.full_hand_card_ids_by_seat == option_a.full_hand_card_ids_by_seat


def test_strict_rust_mode_never_uses_python_fallback(monkeypatch) -> None:
    class FailingRustExtension:
        @staticmethod
        def minimax_extended_core(_payload: str) -> str:
            raise RuntimeError("synthetic Rust failure")

    fallback_called = {"value": False}

    def fake_python_fallback(*_args, **_kwargs):
        fallback_called["value"] = True
        return 0

    monkeypatch.setattr(legacy_minimax, "_MINIMAX_BACKEND_REQUESTED", "rust")
    monkeypatch.setattr(legacy_minimax, "_MINIMAX_BACKEND_ACTIVE", "rust")
    monkeypatch.setattr(legacy_minimax, "_RUST_MINIMAX_AVAILABLE", True)
    monkeypatch.setattr(legacy_minimax, "_STRICT_RUST_MINIMAX", True)
    monkeypatch.setattr(legacy_minimax, "_rl428_minimax_rust", FailingRustExtension())
    monkeypatch.setattr(legacy_minimax, "_minimax_extended_python", fake_python_fallback)

    players = [
        {"cards": [], "isTrump": seat == 0, "team": 1 if seat % 2 == 0 else 2}
        for seat in range(4)
    ]

    try:
        legacy_minimax.minimax_extended(
            [],
            True,
            True,
            False,
            [],
            [0, 0, 0, 0],
            0,
            players,
            "",
            False,
            "Clubs",
            False,
            1,
            None,
            -1,
            [],
            0,
            0,
            1,
        )
    except RuntimeError as exc:
        assert "Strict Rust minimax execution failed" in str(exc)
    else:
        raise AssertionError("Strict Rust failure should propagate.")

    assert fallback_called["value"] is False


def test_installed_rust_extension_executes_startup_smoke(monkeypatch) -> None:
    monkeypatch.setattr(legacy_minimax, "_MINIMAX_BACKEND_REQUESTED", "rust")
    info = legacy_minimax.strict_rust_smoke_test()

    assert info["active"] == "rust"
    assert info["rustAvailable"] is True
    assert info["strictRust"] is True
    assert isinstance(info["smokeValue"], int)
