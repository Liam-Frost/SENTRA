from __future__ import annotations

import os


def is_simulation_enabled() -> bool:
    return _read_bool("SENTRA_SIM_ENABLED", default=False)


def _read_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    value = str(raw).strip().lower()
    return value in {"1", "true", "yes", "on", "enable", "enabled"}
