from __future__ import annotations

import os
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


def remorph_openenv_submission_dir() -> Path:
    """Root of the OpenEnv submission package (contains `openenv.yaml` and `artifacts/`).

    Resolution order:
    1. `REMORPH_OPENENV_SUBMISSION_PATH` — absolute path to the `remorph-openenv-submission` folder
    2. `remorph-openenv-submission/` next to this demo repo (vendored copy for Hugging Face Spaces)
    3. `remorph-openenv-submission/` under `project_root()` (monorepo / sibling checkout)
    """

    override = os.getenv("REMORPH_OPENENV_SUBMISSION_PATH", "").strip()
    if override:
        return Path(override).expanduser().resolve()

    embedded = demo_root() / "remorph-openenv-submission"
    if embedded.is_dir() and (embedded / "openenv.yaml").is_file():
        return embedded.resolve()

    sibling = project_root() / "remorph-openenv-submission"
    if sibling.is_dir() and (sibling / "openenv.yaml").is_file():
        return sibling.resolve()

    return embedded.resolve()
