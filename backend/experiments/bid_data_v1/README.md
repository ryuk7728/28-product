# Bid Data Experiment v1

This directory is the Phase 1 contract for the first production bid-data collection run. The machine-readable source of truth is [`experiment.json`](experiment.json). Phase 2 code should consume or validate against it rather than duplicating constants invisibly.

## Milestone

Collect reproducible estimates of bidder-team points conditional on the bidder's canonical first-four-card key. The experiment collects raw outcomes; it does not yet decide whether the eventual bid recommendation should use a mean, clipped mean, quantile, or another estimator.

## Verified repository facts

An exhaustive enumeration using the current `build_canonical_key_and_mapping` implementation gives:

| Quantity | Count |
| --- | ---: |
| Physical four-card hands | 35,960 |
| Canonical keys | 2,262 |
| Zero-point physical hands | 1,820 |
| Zero-point canonical keys | 133 |

Canonical-key physical multiplicities are:

| Physical hands per key | Number of keys |
| ---: | ---: |
| 1 | 8 |
| 4 | 126 |
| 6 | 56 |
| 12 | 1,218 |
| 24 | 854 |

The experiment must therefore sample physical hands uniformly *within* the requested key before uniformly dealing the remaining 28 cards. Choosing one arbitrary suit realization per key would not implement the desired conditional distribution.

## Statistical unit

A sample slot is identified by `(canonical_key_id, sample_index)`, with `sample_index` in `0..99`. The target player is normalized to seat 0; card-game symmetry makes the physical seat label irrelevant, while the target's position relative to the opening bidder remains meaningful.

The 100 slots are exactly balanced across bidding positions:

```text
bid_position = 1 + (sample_index mod 4)
```

This produces 25 slots for each of positions 1 through 4. Play is intentionally conditional on the target being the final bidder. The numerical auction is not simulated because it would reintroduce the heuristic bid policy that this dataset is meant to replace.

## Redeals and aborted full deals

The implemented family rule is position-specific: only the opening bidder may request a redeal, and only when the first four cards contain zero points. Consequently, a zero-point canonical key is not globally called a redeal key.

- At bid position 1, a zero-point key produces a deterministic `REDEAL` classification and no played game.
- At bid positions 2 through 4, the same key remains a play-sampling stratum because the opening-bidder redeal rule does not apply there.
- Full-deal aborts (`ALL_FOUR_JACKS` and `ALL_TRUMPS_ONE_SIDE`) are properties of the randomized rest of the deal. They are counted, after which the remaining 28 cards are resampled until the requested sample slot completes or the retry limit is exhausted.

Deterministic classifications are stored once per requested sample slot. They have unique sample and deal identities, make reconciliation exact, and are explicitly excluded from played-sample statistics.

With 133 zero-point keys, this gives 3,325 deterministic opening-redeal slots. The canonical key containing all four Jacks contributes another 100 deterministic abort slots because no rest-of-deal resampling can make it playable. The resulting production target is 222,775 played samples before probabilistic full-deal abort retries.

## Search policies

K is indexed by the repository's one-based `catchNumber`, from catch 1 through catch 8:

| Policy | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | Rollouts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline | 3 | 3 | 4 | 4 | 4 | 3 | 2 | 1 | 500 |
| Option A | 2 | 2 | 3 | 3 | 4 | 3 | 2 | 1 | 500 |

The baseline is tested first on GCP. Option A is tested only if the baseline misses the performance/reliability gate, and it must use the identical deal IDs. The run does not automatically reduce the rollout count.

## Rust requirement

`APP_MINIMAX_BACKEND=rust` currently fails when the extension cannot be imported, but `minimax_extended` catches exceptions raised *during* a Rust call and falls back to Python. That behavior is useful for the interactive application but violates this experiment's provenance requirement.

Phase 2 must provide a strict production-run mode that fails the sample on any Rust import or execution failure. Every row must report the active backend, extension version, build identity, Git commit, and container digest.

## Result meaning

The principal outcome is `bidder_team_points`. `winnerTeam` is not a valid target because these simulations deliberately have no numerical final bid. The raw row retains both team scores, rules and engine provenance, timing data, selected heuristic trump, deterministic seed information, and abort-attempt statistics.

## Performance and cost gates

The primary performance gate is p95 headless simulation time at or below 30 seconds in the 100-game stratified GCP pilot. Container startup and persistence are measured separately.

The production run uses gross GCP usage before credits:

- notifications at INR 8,000 and INR 12,000;
- operational stop at INR 14,000;
- planning ceiling at INR 16,000.

The operational stop is deliberately below the ceiling because billing notifications can lag. Production is launched in bounded waves, and workers check a shared stop flag between samples.

## Phase 1 boundaries

This phase does not modify the current arena self-play implementation, provision cloud resources, run paid simulations, or choose a bid estimator. Its output is this locked contract. Any later deviation must increment the schema/experiment version or be recorded as a versioned run-manifest override.

## Phase 2 headless runner

Phase 2 implements the contract in `app.experiments.bid_data_v1`. The entry point configures strict Rust mode before importing the game engine:

```powershell
cd backend
.\venv\Scripts\python.exe -m app.scripts.run_bid_data `
  --key-index 0 `
  --sample-index 0 `
  --count 1 `
  --root-seed pilot-v1 `
  --policy baseline `
  --workers 8 `
  --output data/pilot.ndjson
```

The command refuses Python minimax fallback, executes a Rust-core startup smoke call, fixes rollout count at 500, installs the selected K schedule through environment configuration, and appends compact NDJSON rows. `--canonical-key-id` can replace `--key-index`. A single command may process only sample indexes `0..99` for one key.

When `--key-index` is omitted, the command uses Cloud Run's `CLOUD_RUN_TASK_INDEX`. Production maps four 25-sample task shards to every canonical key, for 9,048 tasks total. `APP_ROOT_SEED`, `APP_RUN_ID`, `APP_SAMPLES_PER_TASK`, and `APP_GCS_OUTPUT_PREFIX` can replace command-line arguments without shell interpolation.

The same container still defaults to the FastAPI server; a Cloud Run Job will override its command with this module during the cloud phases. The Docker image includes the versioned experiment contract at `/app/experiments/bid_data_v1/experiment.json`.
