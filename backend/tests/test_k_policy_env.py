from __future__ import annotations

import importlib


def _reload_k_policy_modules():
    import app.settings as settings_module
    import app.engine.k_policy as k_policy_module

    importlib.reload(settings_module)
    importlib.reload(k_policy_module)
    return k_policy_module


def test_k_by_catch_map_is_applied(monkeypatch) -> None:
    monkeypatch.setenv("APP_K_OVERRIDE", "")
    monkeypatch.setenv("APP_K_BY_CATCH", "1:3,2:3,3:4,4:4,5:4,6:3,7:2,8:1")
    k_policy = _reload_k_policy_modules()

    got = [k_policy.compute_k(i) for i in range(1, 9)]
    assert got == [3, 3, 4, 4, 4, 3, 2, 1]


def test_k_override_takes_precedence_over_k_by_catch(monkeypatch) -> None:
    monkeypatch.setenv("APP_K_OVERRIDE", "5")
    monkeypatch.setenv("APP_K_BY_CATCH", "1:1,2:1,3:1,4:1")
    k_policy = _reload_k_policy_modules()

    got = [k_policy.compute_k(i) for i in range(1, 9)]
    assert got == [5, 5, 5, 5, 5, 5, 5, 5]


def test_fallback_default_policy_when_k_by_catch_missing_entry(monkeypatch) -> None:
    monkeypatch.setenv("APP_K_OVERRIDE", "")
    monkeypatch.setenv("APP_K_BY_CATCH", "1:9")
    k_policy = _reload_k_policy_modules()

    # catch 1 is from map, others from branch fallback in k_policy.py
    assert k_policy.compute_k(1) == 9
    assert k_policy.compute_k(2) == 3
    assert k_policy.compute_k(3) == 4
    assert k_policy.compute_k(5) == 4
    assert k_policy.compute_k(8) == 1

