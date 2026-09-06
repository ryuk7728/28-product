# 28 Product

## Product promise

28 Product is the fastest, clearest way to start a solo game of Twenty-Eight against three strong bots. The player enters a name and the table opens immediately. The interface exposes the game, not the AI configuration.

This document is the source of truth for product, interaction, game-room, bot, testing, and deployment decisions.

## Non-negotiable product principles

1. **A game in seconds.** Enter a name and play. A solo game starts immediately.
2. **One human, four seats.** Twenty-Eight remains a two-team partnership game. The human receives one bot partner and faces two bot opponents.
3. **Local player at the bottom.** Every client rotates the same authoritative seat layout so its own cards are closest and easiest to reach.
4. **Large-screen play.** Primary actions have large targets, do not depend on hover, and work on desktops, laptops, and tablets. Phones receive a clear larger-screen message instead of the game.
5. **Progressive disclosure.** During play, show only the decision, cards, turn, contract, trump, and score needed now. Technical settings and debug controls never appear.
6. **Quiet continuity.** The player name is remembered on the device. Refreshing an active game restores it through a locally stored room token.
7. **Honest status.** Reconnecting, thinking, exiting, and game completion all have explicit human-readable states.

## Supported tables

| Humans | Experience | Human seat | Bot seats |
| --- | --- | --- | --- |
| 1 | Play now against three bots | 4 | 1, 2, 3 |

The starting bidder advances one seat clockwise on every rematch.

## Fixed bot policy

The backend owns this configuration and clients cannot override it:

- engine: strict Rust
- bidding data: pooled/all positions
- opening 15 threshold: 60%
- opening 16 threshold: 75%
- ordinary later raise threshold: 60%
- 14-to-16 jump threshold: 75%
- K policy by catch: `3,3,4,4,4,3,2,1`
- card-play thinking budget: 30 seconds
- on timeout: use the best result from every completed rollout; never substitute a random move merely because time expired

## End-to-end journey

### Home

- Brand and one-line value proposition.
- Name field, remembered on the device.
- A concise one-human/three-bot matchup explanation.
- One primary action: **Play now**.
- Rules/help is secondary and never blocks play.

### Play

- The local hand occupies the lower ergonomic zone.
- Other hands show counts, player name, team relationship, turn, bidder, and bot state without exposing cards.
- The center presents the current decision: bid, select trump, reveal choice, or trick.
- Play cards with one tap when unambiguous; destructive or rule-changing decisions remain explicit.
- Contract/trump and scores remain visible without exposing the internal room code.
- A compact **Exit game** control opens a confirmation dialog. Confirming clears the active session and returns home while preserving the remembered name.
- Connection loss shows a non-blocking reconnect banner and automatically retries.

### Result and rematch

- Result language is relative to the local player's team: **Your team won/lost**.
- Show contract, bidder, both team scores, and a concise reason.
- Solo rematch starts immediately on request.

## Visual direction

- Contemporary card-room atmosphere: deep green felt, warm ivory cards, restrained gold, crisp typography, and subtle depth.
- Avoid casino clutter, faux-luxury decoration, dense settings panels, and tiny controls.
- Tablet and desktop layouts preserve seat geometry and interaction order.
- Phone browsers show a focused larger-screen notice and cannot create or resume a game.
- Motion communicates dealing, turn changes, trump reveal, and trick collection; it must respect reduced-motion preferences.

## Room/API contract

### Create

`POST /rooms`

```json
{ "playerName": "Asha", "humanCount": 1 }
```

The server chooses the starting bidder and applies the fixed bot policy. Client-provided bot policy, K policy, or thinking-time fields are not accepted.

The public API accepts only `humanCount: 1`; values 2, 3, and 4 are rejected. Internal room identifiers and tokens remain implementation details and are never displayed.

WebSocket state includes authoritative `seatTypes` and `playerNames`. Room clients never infer bots from hard-coded seat numbers.

## Recovery and lifecycle

- Store the active `{roomCode, gameId, seatIndex, playerToken}` and the remembered player name locally after successful creation.
- A refresh restores an active game with its token before showing the home screen.
- Exiting clears the active session and room token but preserves the remembered name.
- Cloud Run uses one minimum and maximum instance initially because rooms live in process memory. This is an explicit first production constraint, not a load-balanced architecture.
- Future horizontal scaling requires shared room/game state or sticky routing; do not silently increase instances before that exists.

## Accessibility and responsive acceptance

- Minimum practical primary tap target: 44x44 CSS pixels.
- Visible keyboard focus, useful labels, semantic buttons, and non-color-only turn/team signals.
- A phone-class device at 320x568, 360x800, 390x844, or 412x915 shows only the larger-screen notice.
- Correct game layouts at 768x1024, 1024x768, 1366x768, and 1440x900.
- No horizontal page overflow; no important control obscured by the hand, browser chrome, or device notch.

## Verification gates

1. Backend unit tests verify immediate one-human creation, fixed bot policy, token restoration, and rejection of 2–4-human room requests.
2. Existing rules, trump-reveal, timed-rollout, and Rust parity tests remain green.
3. Frontend build and lint are clean.
4. Browser journey tests cover name entry, immediate solo creation, refresh recovery, confirmed exit, name persistence, and rematch.
5. Visual checks cover the desktop/tablet home and game, the exit confirmation, and the phone larger-screen notice.
6. Production smoke testing is required separately before deployment.

## Deployment isolation

- GitHub repository: `28-product`
- Vercel project: separate from 28 Superhuman UI
- Cloud Run service: separate service name and URL
- container image: separate Artifact Registry repository/path
- environment variables: the Vercel production deployment points only to the new Cloud Run HTTPS/WSS endpoint
- legacy 28 Superhuman UI, its local uncommitted voice work, Vercel project, Cloud Run service, and images are never modified by this project
