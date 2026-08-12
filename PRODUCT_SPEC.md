# 28 Product

## Product promise

28 Product is the fastest, clearest way to start a proper game of Twenty-Eight with any mix of one to four people. A host chooses how many humans are playing, shares one short invite, and the table fills the remaining seats with strong bots. The interface exposes the game, not the AI configuration.

This document is the source of truth for product, interaction, game-room, bot, testing, and deployment decisions.

## Non-negotiable product principles

1. **A game in seconds.** Name, player count, create. A solo game starts immediately; multiplayer rooms need one obvious share action.
2. **One table, four seats.** Twenty-Eight remains a two-team partnership game. Seats 1 and 3 are one team; seats 2 and 4 are the other. Human count changes who occupies seats, never the rules.
3. **Local player at the bottom.** Every client rotates the same authoritative seat layout so its own cards are closest and easiest to reach.
4. **Touch first.** Primary actions have large targets, do not depend on hover, respect safe areas, and fit common small iPhone and Android portrait widths without horizontal scrolling.
5. **Progressive disclosure.** During play, show only the decision, cards, turn, contract, trump, and score needed now. Technical settings and debug controls never appear.
6. **Resilient invitations.** Every waiting room offers Copy link, Copy code, and native Share where supported. Opening an invite pre-fills the code. Refreshing or reopening restores the player through a locally stored room token.
7. **Honest status.** Waiting, reconnecting, thinking, illegal/expired invites, and game completion all have explicit human-readable states.

## Supported tables

| Humans | Experience | Human seats at first deal | Bot seats |
| --- | --- | --- | --- |
| 1 | Play now against three bots | 4 | 1, 2, 3 |
| 2 | Human partners versus two bots | 2, 4 | 1, 3 |
| 3 | Three humans and one bot in normal 2v2 partnerships | 2, 3, 4 | 1 |
| 4 | Four-human table | 1, 2, 3, 4 | none |

For three-human rooms, the bot seat advances clockwise on each rematch. Human seat assignments rotate with it so the bot partnership is shared fairly. Player identity is tied to the room token, not permanently to a seat. Every state and action resolves the token's current seat.

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
- Four large choices: Solo, 2 players, 3 players, 4 players.
- Primary action reads **Play now** for solo and **Create table** otherwise.
- Secondary join path accepts a six-character room code. An invite URL opens directly into this join path with the code pre-filled.
- Rules/help is secondary and never blocks play.

### Host waiting room

- Shows the room code in a large, readable grouped treatment.
- Primary action: **Share invite** on supported phones, with **Copy link** and **Copy code** always visible.
- Shows `joined / required` people and a four-seat team diagram. Empty human seats say **Waiting...**; bot seats are already filled.
- Explains teams in plain language, especially for three-player games.
- Starts automatically when the required number of humans have joined.

### Guest join

- Invite URL retains `?room=CODE` through the name step.
- Guest enters a name and taps **Join table**. No mode selection is required because the room owns it.
- Full, missing, invalid, or expired rooms produce a useful recovery action, never a raw server error.

### Play

- The local hand occupies the lower ergonomic zone.
- Other hands show counts, player name, team relationship, turn, bidder, and bot state without exposing cards.
- The center presents the current decision: bid, select trump, reveal choice, or trick.
- Play cards with one tap when unambiguous; destructive or rule-changing decisions remain explicit.
- A compact top bar contains room code, contract/trump, and scores. Sharing is available from a small room menu, not permanently expanded.
- Connection loss shows a non-blocking reconnect banner and automatically retries.

### Result and rematch

- Result language is relative to the local player's team: **Your team won/lost**.
- Show contract, bidder, both team scores, and a concise reason.
- Solo rematch starts immediately on request.
- Multiplayer rematch shows who is ready and starts when every human is ready.
- Seat/team changes for a three-human rematch are previewed before the next deal.

## Visual direction

- Contemporary card-room atmosphere: deep green felt, warm ivory cards, restrained gold, crisp typography, and subtle depth.
- Avoid casino clutter, faux-luxury decoration, dense settings panels, and tiny controls.
- Portrait mobile is a deliberate composition, not a scaled desktop board: opponents occupy compact top/side zones, the trick stays central, and the hand/action sheet owns the bottom.
- Landscape and desktop expand spacing while preserving seat geometry and interaction order.
- Motion communicates dealing, turn changes, trump reveal, and trick collection; it must respect reduced-motion preferences.

## Room/API contract

### Create

`POST /rooms`

```json
{ "playerName": "Asha", "humanCount": 3 }
```

The server chooses the starting bidder and applies the fixed bot policy. Client-provided bot policy, K policy, or thinking-time fields are not accepted.

### Join or restore

`POST /rooms/join`

```json
{ "roomCode": "AB12CD", "playerName": "Dev", "playerToken": null }
```

A valid token restores the same player identity and current seat. A new player receives an available seat according to the room plan.

### Status

Status and join responses include the room code, game id, current seat, token (join only), target human count, joined humans, complete seat roster, team number for each seat, waiting state, and whether the game can begin.

WebSocket state includes authoritative `seatTypes` and `playerNames`. Room clients never infer bots from hard-coded seat numbers.

## Recovery and lifecycle

- Store `{roomCode, playerToken, playerName}` locally after successful create/join.
- A refresh restores with the token before showing the home screen.
- A room invite never contains the private token.
- In-progress rooms reject new identities once the requested human count is filled, while valid tokens may always reconnect until room expiry.
- Cloud Run uses one minimum and maximum instance initially because rooms live in process memory. This is an explicit first production constraint, not a load-balanced architecture.
- Future horizontal scaling requires shared room/game state or sticky routing; do not silently increase instances before that exists.

## Accessibility and responsive acceptance

- Minimum practical primary tap target: 44x44 CSS pixels.
- Visible keyboard focus, useful labels, semantic buttons, and non-color-only turn/team signals.
- Correct layouts at 320x568, 360x800, 390x844, 412x915, 768x1024, 1366x768, and 1440x900.
- Respect `env(safe-area-inset-*)` and on-screen keyboard resizing.
- No horizontal page overflow; no important control obscured by the hand, browser chrome, or device notch.

## Verification gates

1. Backend unit tests for all four human counts, seat assignment, full/invalid rooms, token restore, seat-scoped actions, bot advancement, rematch readiness, starting-bidder rotation, and three-human bot-partner rotation.
2. Existing rules, trump-reveal, timed-rollout, and Rust parity tests remain green.
3. Frontend build and lint are clean.
4. Browser journey tests cover host/create/share metadata, invite join, auto-start, refresh recovery, each player-count mode, and rematch.
5. Visual screenshots at the target phone and desktop sizes are inspected for home, waiting, bidding, play, and result states.
6. Production smoke test creates and joins a room through the Vercel origin, establishes secure WebSockets to the new Cloud Run service, plays at least one authorized action, verifies recovery, and confirms old deployments are untouched.

## Deployment isolation

- GitHub repository: `28-product`
- Vercel project: separate from 28 Superhuman UI
- Cloud Run service: separate service name and URL
- container image: separate Artifact Registry repository/path
- environment variables: the Vercel production deployment points only to the new Cloud Run HTTPS/WSS endpoint
- legacy 28 Superhuman UI, its local uncommitted voice work, Vercel project, Cloud Run service, and images are never modified by this project

