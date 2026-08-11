from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.settings import settings


KPolicyMode = Literal["regular", "aggressive"]
REGULAR_K_BY_CATCH: tuple[int, ...] = (2, 2, 3, 3, 4, 3, 2, 1)
AGGRESSIVE_K_BY_CATCH: tuple[int, ...] = (3, 3, 4, 4, 4, 3, 2, 1)


@dataclass(frozen=True)
class KPolicyConfig:
    mode: KPolicyMode = "regular"

    def __post_init__(self) -> None:
        if self.mode not in ("regular", "aggressive"):
            raise ValueError("K policy mode must be regular or aggressive.")

    @property
    def values(self) -> tuple[int, ...]:
        return (
            AGGRESSIVE_K_BY_CATCH
            if self.mode == "aggressive"
            else REGULAR_K_BY_CATCH
        )

    def k_for_catch(self, catch_number: int) -> int:
        if not 1 <= catch_number <= 8:
            raise ValueError("catch_number must be in 1..8.")
        return self.values[catch_number - 1]

    def to_public_dict(self) -> dict[str, object]:
        return {"mode": self.mode, "kByCatch": list(self.values)}


def compute_k(catch_number: int, *, policy: KPolicyConfig | None = None) -> int:
    """
    Priority:
    1) APP_K_OVERRIDE (constant k for all catches)
    2) APP_K_BY_CATCH map (per-catch k values)
    3) Fallback default policy in this branch
    """
    if policy is not None:
        return policy.k_for_catch(catch_number)

    if settings.k_override is not None:
        return settings.k_override

    mapped = settings.k_by_catch.get(catch_number)
    if mapped is not None:
        return mapped

    if catch_number <= 2:
        return 3
    elif catch_number <= 4:
        return 4
    else:
        return max(1, 9 - catch_number)
