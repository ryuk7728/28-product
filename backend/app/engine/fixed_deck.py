from __future__ import annotations

import re
from pathlib import Path
from random import Random

from app.engine.cards_adapter import from_card_id, to_card_id
from app.legacy.cards import Cards

SEAT_LABELS = ("P1", "P2", "P3", "P4")
CARD_ID_RE = re.compile(r"^[A-Za-z]+_[A-Za-z]+$")


def _tokens(raw: str) -> list[str]:
    return [t for t in raw.replace(",", " ").split() if t]


def parse_fixed_deck_ids(text: str) -> list[list[str]]:
    seat_cards: list[list[str]] = [[] for _ in range(4)]
    current_seat: int | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        m = re.match(r"^(P[1-4])\s*:\s*(.*)$", line)
        if m:
            current_seat = int(m.group(1)[1]) - 1
            trailing = m.group(2).strip()
            if trailing:
                seat_cards[current_seat].extend(_tokens(trailing))
            continue

        if current_seat is None:
            raise ValueError(
                "Invalid fixed deck format: expected 'P1:' / 'P2:' / 'P3:' / 'P4:' headers."
            )
        seat_cards[current_seat].extend(_tokens(line))

    for i, cards in enumerate(seat_cards):
        if len(cards) != 8:
            raise ValueError(
                f"{SEAT_LABELS[i]} must have exactly 8 cards. Found {len(cards)}."
            )

    all_ids = [cid for cards in seat_cards for cid in cards]
    if len(all_ids) != 32:
        raise ValueError(f"Fixed deck must contain 32 cards. Found {len(all_ids)}.")
    if len(set(all_ids)) != 32:
        raise ValueError("Fixed deck contains duplicate card IDs.")

    # Validate IDs and exact deck coverage
    for cid in all_ids:
        if not CARD_ID_RE.match(cid):
            raise ValueError(f"Invalid card token: {cid}")
        from_card_id(cid)

    full_deck_ids = {to_card_id(c) for c in Cards.packOf28()}
    provided_ids = set(all_ids)
    if provided_ids != full_deck_ids:
        missing = sorted(full_deck_ids - provided_ids)
        extra = sorted(provided_ids - full_deck_ids)
        raise ValueError(
            "Fixed deck must match full 28-card deck exactly. "
            f"Missing={missing}, Extra={extra}"
        )

    return seat_cards


def load_fixed_deck_cards(path: str | Path) -> list[list[Cards]]:
    p = Path(path)
    if not p.exists():
        raise ValueError(f"Fixed deck file not found: {p}")
    ids = parse_fixed_deck_ids(p.read_text(encoding="utf-8"))
    return [[from_card_id(cid) for cid in hand] for hand in ids]


def format_fixed_deck_text(seat_cards: list[list[str]]) -> str:
    lines: list[str] = [
        "# Fixed deck format: use backend card IDs (e.g., Hearts_Jack).",
        "# Exactly 8 cards per seat and all 32 unique cards across P1..P4.",
    ]
    for i, cards in enumerate(seat_cards):
        lines.append(f"{SEAT_LABELS[i]}:")
        lines.extend(cards)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def reshuffle_fixed_deck(seed: int | None = None) -> list[list[str]]:
    rng = Random(seed)
    deck_ids = [to_card_id(c) for c in Cards.packOf28()]
    rng.shuffle(deck_ids)
    return [
        deck_ids[0:8],
        deck_ids[8:16],
        deck_ids[16:24],
        deck_ids[24:32],
    ]

