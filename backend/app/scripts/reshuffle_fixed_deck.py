from __future__ import annotations

import argparse
from pathlib import Path

from app.engine.fixed_deck import format_fixed_deck_text, reshuffle_fixed_deck
from app.settings import settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reshuffle the fixed deck file used by deterministic auto-deal mode."
    )
    parser.add_argument(
        "--path",
        default=settings.fixed_deck_path,
        help="Path to fixed deck file (default: APP_FIXED_DECK_PATH).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional random seed for reproducible reshuffles.",
    )
    args = parser.parse_args()

    seat_cards = reshuffle_fixed_deck(seed=args.seed)
    output = format_fixed_deck_text(seat_cards)

    target = Path(args.path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(output, encoding="utf-8")

    print(f"Fixed deck rewritten: {target}")
    if args.seed is not None:
        print(f"Seed: {args.seed}")


if __name__ == "__main__":
    main()

