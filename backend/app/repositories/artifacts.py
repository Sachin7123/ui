from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.repositories.base import project_root


class ArtifactRepository:
    def __init__(self, repo_root: Path | None = None) -> None:
        self._repo_root = repo_root or project_root()

    def runtime_summary(self) -> dict[str, Any]:
        path = self._repo_root / "runtime" / "telemetry" / "healing_summary.json"
        return self._read_json(path)

    def runtime_events(self, *, limit: int = 10) -> list[dict[str, Any]]:
        path = self._repo_root / "runtime" / "telemetry" / "healing_events.jsonl"
        return self._read_jsonl(path)[:limit]

    def submission_training_summary(self) -> dict[str, Any]:
        path = (
            self._repo_root
            / "remorph-openenv-submission"
            / "artifacts"
            / "submission"
            / "training_run"
            / "training_summary.json"
        )
        return self._read_json(path)

    def submission_reward_history(self) -> list[dict[str, Any]]:
        path = (
            self._repo_root
            / "remorph-openenv-submission"
            / "artifacts"
            / "submission"
            / "training_run"
            / "reward_history.json"
        )
        return self._read_json(path, default=[])

    def submission_loss_history(self) -> list[dict[str, Any]]:
        path = (
            self._repo_root
            / "remorph-openenv-submission"
            / "artifacts"
            / "submission"
            / "training_run"
            / "loss_history.json"
        )
        return self._read_json(path, default=[])

    def submission_eval_summary(self) -> dict[str, Any]:
        path = (
            self._repo_root
            / "remorph-openenv-submission"
            / "artifacts"
            / "submission"
            / "training_run"
            / "eval_summary.json"
        )
        return self._read_json(path)

    def submission_dataset_stats(self) -> dict[str, Any]:
        path = (
            self._repo_root
            / "remorph-openenv-submission"
            / "artifacts"
            / "submission"
            / "training_run"
            / "dataset_stats.json"
        )
        return self._read_json(path)

    def submission_model_config(self) -> dict[str, Any]:
        path = (
            self._repo_root
            / "remorph-openenv-submission"
            / "artifacts"
            / "submission"
            / "training_run"
            / "model_config.json"
        )
        return self._read_json(path)

    def submission_checkpoint_metadata(self) -> dict[str, Any]:
        path = (
            self._repo_root
            / "remorph-openenv-submission"
            / "artifacts"
            / "submission"
            / "training_run"
            / "checkpoint_metadata.json"
        )
        return self._read_json(path)

    def submission_trl_dataset(self, *, limit: int | None = 6) -> list[dict[str, Any]]:
        path = (
            self._repo_root
            / "remorph-openenv-submission"
            / "artifacts"
            / "submission"
            / "training_run"
            / "trl_dataset.jsonl"
        )
        rows = self._read_jsonl(path)
        if limit is None:
            return rows
        return rows[:limit]

    def submission_rollouts(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        path = (
            self._repo_root
            / "remorph-openenv-submission"
            / "artifacts"
            / "submission"
            / "telemetry"
            / "rollouts.jsonl"
        )
        rows = self._read_jsonl(path)
        if limit is None:
            return rows
        return rows[:limit]

    def benchmark_report(self) -> dict[str, Any]:
        path = (
            self._repo_root
            / "remorph-openenv-submission"
            / "artifacts"
            / "submission"
            / "benchmark_report.json"
        )
        return self._read_json(path)

    def eval_topline(self) -> dict[str, Any]:
        path = self._repo_root / "artifacts" / "sprint4" / "eval_validation" / "adaptive" / "topline.json"
        return self._read_json(path)

    def _read_json(self, path: Path, default: Any | None = None) -> Any:
        if not path.exists():
            return {} if default is None else default
        return json.loads(path.read_text(encoding="utf-8"))

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
        return rows
