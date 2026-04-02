from __future__ import annotations

from app.settings import settings


def compute_k(catch_number: int) -> int:
    """
    Priority:
    1) APP_K_OVERRIDE (constant k for all catches)
    2) APP_K_BY_CATCH map (per-catch k values)
    3) Fallback default policy in this branch
    """
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
