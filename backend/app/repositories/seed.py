from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeVar

from app.models import (
    DashboardResponse,
    EnterpriseSnapshot,
    FailureRow,
    IncidentFeedItem,
    IntegrationCard,
    OverviewResponse,
    RepairRow,
    RequestRow,
    TrainingSnapshot,
)
from app.repositories.base import demo_root

T = TypeVar("T")


class SeedRepository:
    def __init__(self, data_root: Path | None = None) -> None:
        self._data_root = data_root or demo_root() / "data"
        self._seed_root = self._data_root / "seed"
        self._generated_root = self._data_root / "generated"

    def list_requests(self, *, page: int, page_size: int, region: str | None = None) -> tuple[list[RequestRow], int]:
        rows = self._read_jsonl(self._seed_root / "requests.jsonl", RequestRow)
        if region:
            rows = [row for row in rows if row.region == region]
        return self._paginate(rows, page=page, page_size=page_size)

    def list_failures(self, *, page: int, page_size: int) -> tuple[list[FailureRow], int]:
        rows = self._read_jsonl(self._seed_root / "failures.jsonl", FailureRow)
        return self._paginate(rows, page=page, page_size=page_size)

    def list_repairs(self, *, page: int, page_size: int) -> tuple[list[RepairRow], int]:
        rows = self._read_jsonl(self._seed_root / "repairs.jsonl", RepairRow)
        return self._paginate(rows, page=page, page_size=page_size)

    def get_repair(self, repair_id: str) -> RepairRow | None:
        repairs = self._read_jsonl(self._seed_root / "repairs.jsonl", RepairRow)
        return next((repair for repair in repairs if repair.repair_id == repair_id), None)

    def featured_examples(self) -> list[RepairRow]:
        repairs = self._read_jsonl(self._seed_root / "repairs.jsonl", RepairRow)
        featured_ids = {
            "repair-401-missing-bearer-token",
            "repair-404-wrong-route-version",
            "repair-422-invalid-payload-type",
            "repair-429-rate-limit-retry",
            "repair-500-schema-drift",
        }
        featured = [repair for repair in repairs if repair.repair_id in featured_ids]
        if featured:
            return featured
        return repairs[:5]

    def overview(self) -> OverviewResponse:
        return self._read_json(self._generated_root / "overview.json", OverviewResponse)

    def dashboard(self) -> DashboardResponse:
        return self._read_json(self._generated_root / "dashboard.json", DashboardResponse)

    def activity(self, *, limit: int = 12) -> list[IncidentFeedItem]:
        rows = self._read_jsonl(self._seed_root / "activity.jsonl", IncidentFeedItem)
        return rows[:limit]

    def snapshot(self) -> TrainingSnapshot:
        return self._read_json(self._generated_root / "training.json", TrainingSnapshot)

    def list_integrations(self) -> list[IntegrationCard]:
        return self._read_json_list(self._seed_root / "integrations.json", IntegrationCard)

    def enterprise_snapshot(self) -> EnterpriseSnapshot:
        return self._read_json(self._generated_root / "enterprise.json", EnterpriseSnapshot)

    def _paginate(self, rows: list[T], *, page: int, page_size: int) -> tuple[list[T], int]:
        safe_page = max(page, 1)
        safe_size = max(page_size, 1)
        start = (safe_page - 1) * safe_size
        end = start + safe_size
        return rows[start:end], len(rows)

    @staticmethod
    @lru_cache(maxsize=None)
    def _read_json(path: Path, model_type):
        payload = json.loads(path.read_text(encoding="utf-8"))
        return model_type.model_validate(payload)

    @staticmethod
    @lru_cache(maxsize=None)
    def _read_json_list(path: Path, model_type):
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [model_type.model_validate(item) for item in payload]

    @staticmethod
    @lru_cache(maxsize=None)
    def _read_jsonl(path: Path, model_type):
        rows: list[Any] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(model_type.model_validate(json.loads(line)))
        return rows
