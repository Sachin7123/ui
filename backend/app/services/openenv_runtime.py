"""Single-session ReMorph OpenEnv runtime for the Space UI (no Gradio).

Uses the vendored ``remorph_openenv`` package on PYTHONPATH. One shared
environment instance is enough for judge demos; training still uses TRL offline.
"""

from __future__ import annotations

import threading
from typing import Any

_lock = threading.Lock()
_env: Any = None


def import_ok() -> tuple[bool, str | None]:
    try:
        import remorph_openenv  # noqa: F401

        return True, None
    except ImportError as exc:
        return False, str(exc)


def _ensure_env() -> Any:
    global _env
    with _lock:
        if _env is not None:
            return _env
        from remorph_openenv.environment import ReMorphEnvironment

        _env = ReMorphEnvironment(
            seed=0,
            split="all",
            randomize=True,
            execution_mode="simulated",
        )
        return _env


def reset(*, seed: int | None = None, scenario_id: str | None = None) -> dict[str, Any]:
    env = _ensure_env()
    return env.reset(scenario_id=scenario_id, seed=seed)


def step(action: dict[str, Any]) -> dict[str, Any]:
    env = _ensure_env()
    observation, reward, done, info = env.step(action)
    return {
        "observation": observation,
        "reward": reward,
        "done": done,
        "info": info,
    }


def state() -> dict[str, Any]:
    env = _ensure_env()
    return env.state()
