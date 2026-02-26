from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "y", "on")


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    return int(val)


def _get_float(name: str, default: float) -> float:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    return float(val)


def _get_int_optional(name: str) -> int | None:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return None
    return int(val)


def _get_str(name: str, default: str) -> str:
    val = os.getenv(name)
    if val is None:
        return default
    return val


def _get_str_optional(name: str) -> str | None:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return None
    return val


@dataclass(frozen=True)
class Settings:
    app_dir: Path = Path(__file__).resolve().parent
    backend_dir: Path = app_dir.parent
    debug: bool = _get_bool("APP_DEBUG", True)

    # Rollout bot config
    rollouts: int = _get_int("APP_ROLLOUTS", 200)
    workers: int = _get_int("APP_WORKERS", 8)

    # NEW: retries for constraint-aware rollout dealing
    rollout_deal_retries: int = _get_int("APP_ROLLOUT_DEAL_RETRIES", 30)

    # Rollout metrics logging
    rollout_metrics: bool = _get_bool("APP_ROLLOUT_METRICS", False)
    rollout_metrics_interval: float = _get_float("APP_ROLLOUT_METRICS_INTERVAL", 10.0)

    max_concurrent_bot_thinking: int = _get_int(
        "APP_MAX_CONCURRENT_BOT_THINKING", 1
    )

    # Rollout backend (local or ray)
    rollout_backend: str = _get_str("APP_ROLLOUT_BACKEND", "local").strip().lower()
    ray_address: str | None = _get_str_optional("RAY_ADDRESS") or _get_str_optional(
        "APP_RAY_ADDRESS"
    )

    # k control
    k_override: int | None = _get_int_optional("APP_K_OVERRIDE")

    # Fixed-deck mode (for deterministic reproduction)
    fixed_deck_enabled: bool = _get_bool("APP_FIXED_DECK_ENABLED", False)
    fixed_deck_path: str = _get_str(
        "APP_FIXED_DECK_PATH",
        str((Path(__file__).resolve().parent.parent / "fixed_deck.txt").as_posix()),
    )
    room_ttl_seconds: int = _get_int("APP_ROOM_TTL_SECONDS", 24 * 60 * 60)

    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://28-superhuman-ui.vercel.app"
    )


settings = Settings()
