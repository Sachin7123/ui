from __future__ import annotations

from pathlib import Path


def demo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def project_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "runtime").exists() or (candidate / "remorph-openenv-submission").exists():
            return candidate
        sibling_remorph = candidate / "ReMorph"
        if (sibling_remorph / "runtime").exists() or (sibling_remorph / "remorph-openenv-submission").exists():
            return sibling_remorph
    return demo_root()


def runtime_root() -> Path:
    root = demo_root() / "data" / "runtime"
    root.mkdir(parents=True, exist_ok=True)
    return root


def database_path() -> Path:
    return runtime_root() / "observability.db"


def event_log_path() -> Path:
    return runtime_root() / "event_stream.jsonl"
