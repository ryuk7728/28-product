from __future__ import annotations

from app.settings import settings


def compute_k(catch_number: int) -> int:
    """
    Your required policy:
    - First 2 catches: k=2
    - After that: k = tricks left including current
      catch 5 -> 4, 6 -> 3, 7 -> 2, 8 -> 1
    """
    if settings.k_override is not None:
        return settings.k_override

    if catch_number <= 2:
        return 2
    elif catch_number <= 4:
        return 3
    else:
        return max(1, 9 - catch_number)