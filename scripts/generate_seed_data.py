from __future__ import annotations

import json
import math
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEED_ROOT = ROOT / "data" / "seed"
GENERATED_ROOT = ROOT / "data" / "generated"
RNG = random.Random(42)

REGIONS = ["us-east-1", "us-west-2", "eu-west-1", "ap-south-1"]
SERVICES = ["identity", "billing", "ledger", "orders", "analytics", "support"]
ENDPOINTS = [
    ("GET", "/api/v1/customers"),
    ("POST", "/api/v1/orders"),
    ("POST", "/api/v1/tokens/refresh"),
    ("GET", "/api/v1/billing/invoices"),
    ("POST", "/api/v1/ledger/entries"),
    ("PATCH", "/api/v1/users/{id}"),
    ("POST", "/api/v1/events/ingest"),
]
INTEGRATIONS = [
    ("FastAPI", "Framework"),
    ("Flask", "Framework"),
    ("Express", "Framework"),
    ("Django", "Framework"),
    ("OpenAPI", "Contract"),
    ("AWS", "Cloud"),
    ("GCP", "Cloud"),
]

EXAMPLES = [
    ("repair-401-missing-bearer-token", 401, "auth_drift", "Missing Bearer token header", "auth_missing_token"),
    ("repair-404-wrong-route-version", 404, "route_drift", "Client called deprecated v1 route", "wrong_route_version"),
    ("repair-422-invalid-payload-type", 422, "payload_drift", "Payload field `amount` sent as string", "invalid_payload_type"),
    ("repair-429-rate-limit-retry", 429, "rate_limit", "Burst exceeded tenant rate limit window", "rate_limit_retry"),
    ("repair-500-schema-drift", 500, "schema_drift", "Downstream schema removed `ledger_code`", "schema_drift"),
]


def iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def request_payload(method: str, endpoint: str, request_id: str) -> dict:
    if method == "GET":
        return {}
    if "orders" in endpoint:
        return {"order_id": request_id, "amount": RNG.randint(20, 1400), "currency": "USD"}
    if "ledger" in endpoint:
        return {"entry_id": request_id, "ledger_code": "REV-001", "amount": RNG.randint(100, 4000)}
    if "tokens" in endpoint:
        return {"tenant_id": f"tenant-{RNG.randint(10, 99)}"}
    if "events" in endpoint:
        return {"event_type": "invoice.created", "attempt": RNG.randint(1, 4)}
    return {"user_id": request_id, "status": RNG.choice(["active", "suspended"])}


def make_requests() -> list[dict]:
    now = datetime.now(UTC)
    rows = []
    for index in range(10_000):
        method, endpoint = RNG.choice(ENDPOINTS)
        region = RNG.choice(REGIONS)
        status_code = RNG.choices([200, 201, 202, 204, 400, 401, 404, 422, 429, 500], weights=[26, 12, 6, 4, 2, 1, 1, 1, 1, 1])[0]
        success = status_code < 400
        service = RNG.choice(SERVICES)
        timestamp = now - timedelta(seconds=index * 17)
        rows.append(
            {
                "request_id": f"req-{index:05d}",
                "timestamp": iso(timestamp),
                "endpoint": endpoint,
                "method": method,
                "latency_ms": RNG.randint(42, 980) if success else RNG.randint(240, 1800),
                "status_code": status_code,
                "region": region,
                "environment": RNG.choice(["prod", "staging"]),
                "service": service,
                "trace_id": f"trc-{RNG.randint(100000, 999999)}",
                "success": success,
            }
        )
    return rows


def make_failures(requests: list[dict]) -> list[dict]:
    now = datetime.now(UTC)
    failures = []
    for idx, example in enumerate(EXAMPLES):
        repair_id, status_code, scenario_type, root_cause, drift_class = example
        request = dict(requests[idx])
        request["status_code"] = status_code
        request["success"] = False
        failures.append(
            build_failure(
                failure_id=f"failure-{idx:04d}",
                request=request,
                timestamp=now - timedelta(minutes=idx * 3),
                status_code=status_code,
                scenario_type=scenario_type,
                root_cause=root_cause,
                drift_class=drift_class,
            )
        )

    cursor = 0
    while len(failures) < 1428:
        request = dict(requests[(cursor + len(EXAMPLES)) % len(requests)])
        scenario_type = RNG.choices(
            ["auth_drift", "route_drift", "payload_drift", "rate_limit", "schema_drift"],
            weights=[18, 22, 30, 14, 16],
        )[0]
        status_code = {
            "auth_drift": 401,
            "route_drift": 404,
            "payload_drift": RNG.choice([400, 422]),
            "rate_limit": 429,
            "schema_drift": 500,
        }[scenario_type]
        request["status_code"] = status_code
        request["success"] = False
        idx = len(failures)
        failures.append(
            build_failure(
                failure_id=f"failure-{idx:04d}",
                request=request,
                timestamp=now - timedelta(minutes=idx * 3),
                status_code=status_code,
                scenario_type=scenario_type,
                root_cause=ROOT_CAUSES[scenario_type][idx % 4],
                drift_class=DRIFT_CLASS[scenario_type],
            )
        )
        cursor += 1
    return failures


ROOT_CAUSES = {
    "auth_drift": [
        "Missing Bearer token header",
        "Tenant header omitted after gateway upgrade",
        "JWT format invalid after mobile patch",
        "Expired service credential propagated by worker",
    ],
    "route_drift": [
        "Client called deprecated v1 route",
        "Gateway rewrote path to stale version",
        "Method-path pair no longer exists in current contract",
        "Edge cache retained retired endpoint alias",
    ],
    "payload_drift": [
        "Payload field `amount` sent as string",
        "Enum value outside current OpenAPI contract",
        "Required field omitted during partner sync",
        "Nested object shape no longer matches schema",
    ],
    "rate_limit": [
        "Burst exceeded tenant rate limit window",
        "Retry-after header ignored by worker",
        "Concurrent job fan-out hit route quota",
        "Partner webhook replay created duplicate spike",
    ],
    "schema_drift": [
        "Downstream schema removed `ledger_code`",
        "Response contract changed after rollout",
        "Migration renamed field without client update",
        "Validation middleware now enforces stricter type checks",
    ],
}

DRIFT_CLASS = {
    "auth_drift": "auth_missing_token",
    "route_drift": "wrong_route_version",
    "payload_drift": "invalid_payload_type",
    "rate_limit": "retry_backoff",
    "schema_drift": "schema_drift",
}


def infer_scenario_type(status_code: int) -> str:
    if status_code == 401:
        return "auth_drift"
    if status_code == 404:
        return "route_drift"
    if status_code == 429:
        return "rate_limit"
    if status_code in {422, 400}:
        return "payload_drift"
    return "schema_drift"


def build_failure(
    *,
    failure_id: str,
    request: dict,
    timestamp: datetime,
    status_code: int,
    scenario_type: str,
    root_cause: str,
    drift_class: str,
) -> dict:
    method = request["method"]
    endpoint = request["endpoint"]
    failed_request = {
        "method": method,
        "url": endpoint,
        "headers": {
            "x-region": request["region"],
            "x-trace-id": request["trace_id"],
            "authorization": "" if status_code == 401 else "Bearer demo-redacted",
        },
        "payload": request_payload(method, endpoint, request["request_id"]),
    }
    return {
        "failure_id": failure_id,
        "request_id": request["request_id"],
        "timestamp": iso(timestamp),
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "error_type": f"HTTP {status_code}",
        "scenario_type": scenario_type,
        "drift_class": drift_class,
        "root_cause": root_cause,
        "payload_issue": root_cause if scenario_type in {"payload_drift", "schema_drift"} else None,
        "auth_issue": root_cause if scenario_type == "auth_drift" else None,
        "route_mismatch": endpoint if scenario_type == "route_drift" else None,
        "region": request["region"],
        "severity": "critical" if status_code in {500, 401} else "high",
        "request": failed_request,
    }


def make_repairs(failures: list[dict]) -> list[dict]:
    repairs = []
    success_cutoff = 1173
    abstain_cutoff = 1288
    now = datetime.now(UTC)

    for idx, failure in enumerate(failures):
        status = "success" if idx < success_cutoff else "abstained" if idx < abstain_cutoff else "failed"
        scenario_type = failure["scenario_type"]
        safe_abstained = status == "abstained"
        suggestion = repair_suggestion(scenario_type, safe_abstained=safe_abstained)
        result_summary = (
            "Replayed request completed successfully"
            if status == "success"
            else "Agent abstained because credentials could not be synthesized"
            if status == "abstained"
            else "Retry still failed after contract-guided repair"
        )
        repaired_url = healed_url(failure["request"]["url"], scenario_type)
        repaired_headers = dict(failure["request"]["headers"])
        if scenario_type == "auth_drift" and status == "success":
            repaired_headers["authorization"] = "Bearer ey.demo.healed"
            repaired_headers["x-tenant-id"] = "tenant-42"
        healed_payload = dict(failure["request"]["payload"] or {})
        if scenario_type in {"payload_drift", "schema_drift"} and healed_payload:
            healed_payload["amount"] = int(healed_payload.get("amount", 100))
            healed_payload.setdefault("ledger_code", "REV-001")

        repair_id = EXAMPLES[idx][0] if idx < len(EXAMPLES) else f"repair-{idx:04d}"
        repairs.append(
            {
                "repair_id": repair_id,
                "failure_id": failure["failure_id"],
                "timestamp": iso(now - timedelta(minutes=idx * 2)),
                "repair_type": repair_type(scenario_type, safe_abstained=safe_abstained),
                "status": status,
                "confidence": round(0.68 + (idx % 20) * 0.013, 2) if status != "failed" else round(0.41 + (idx % 7) * 0.03, 2),
                "retry_latency_ms": RNG.randint(120, 950),
                "safe_abstained": safe_abstained,
                "policy_name": "adaptive_reference" if idx % 5 else "trained_policy",
                "policy_version": f"v{2 + idx % 3}.{idx % 10}",
                "root_cause": failure["root_cause"],
                "suggestion": suggestion,
                "result_summary": result_summary,
                "request": failure["request"],
                "healed_request": None
                if safe_abstained
                else {
                    "method": failure["request"]["method"] if scenario_type != "route_drift" else "POST",
                    "url": repaired_url,
                    "headers": repaired_headers,
                    "payload": healed_payload,
                },
            }
        )
    return repairs


def repair_type(scenario_type: str, *, safe_abstained: bool) -> str:
    if safe_abstained:
        return "safe_abstain"
    return {
        "auth_drift": "auth_rewrite",
        "route_drift": "route_rewrite",
        "payload_drift": "payload_rewrite",
        "rate_limit": "retry_with_backoff",
        "schema_drift": "combined_rewrite",
    }[scenario_type]


def repair_suggestion(scenario_type: str, *, safe_abstained: bool) -> str:
    if safe_abstained:
        return "Do not fabricate credentials; surface a safe abstain and request valid tenant secrets."
    return {
        "auth_drift": "Inject tenant header and refresh bearer token from contract-backed auth policy.",
        "route_drift": "Rewrite request to the currently published versioned endpoint.",
        "payload_drift": "Coerce invalid field types and append missing required attributes.",
        "rate_limit": "Honor retry-after signal and replay with exponential backoff.",
        "schema_drift": "Map payload to the latest schema and remove retired fields.",
    }[scenario_type]


def healed_url(url: str, scenario_type: str) -> str:
    if scenario_type == "route_drift":
        return url.replace("/api/v1/", "/api/v2/")
    return url


def make_activity(repairs: list[dict]) -> list[dict]:
    rows = []
    for idx, repair in enumerate(repairs[:60]):
        rows.append(
            {
                "id": f"incident-{idx:03d}",
                "timestamp": repair["timestamp"],
                "title": f"{repair['repair_type']} on {repair['request']['url']}",
                "detail": repair["result_summary"],
                "level": "critical" if repair["status"] == "failed" else "high" if repair["safe_abstained"] else "medium",
                "action": repair["suggestion"],
            }
        )
    return rows


def make_metric_cards() -> list[dict]:
    return [
        {"id": "requests", "label": "Requests Today", "value": "52,381", "delta": "+12.4%", "direction": "up", "hint": "Global request volume across production regions"},
        {"id": "failures", "label": "Failures Detected", "value": "1,428", "delta": "-4.2%", "direction": "down", "hint": "Drift, auth, payload, and transient edge failures"},
        {"id": "healed", "label": "Auto-Healed", "value": "1,173", "delta": "+9.8%", "direction": "up", "hint": "Requests repaired without operator intervention"},
        {"id": "success", "label": "Success Rate", "value": "82.1%", "delta": "+3.1 pts", "direction": "up", "hint": "Adaptive policy win rate on detected failures"},
        {"id": "hours", "label": "Hours Saved", "value": "314h", "delta": "+27h", "direction": "up", "hint": "Estimated incident-response time reclaimed"},
    ]


def make_series() -> tuple[list[dict], list[dict], list[dict]]:
    now = datetime.now(UTC)
    requests_points = []
    failure_points = []
    reward_points = []
    for hour in range(24):
        point_time = now - timedelta(hours=23 - hour)
        requests_value = 1500 + int(380 * math.sin(hour / 3)) + RNG.randint(-80, 80)
        failure_value = 42 + int(12 * math.sin(hour / 5 + 0.2)) + RNG.randint(-4, 5)
        heal_rate = 78 + math.sin(hour / 6) * 6 + RNG.random() * 2
        reward_value = 0.62 + (hour / 24) * 0.21 + math.sin(hour / 4) * 0.02
        requests_points.append({"timestamp": iso(point_time), "value": requests_value})
        failure_points.append({"timestamp": iso(point_time), "value": max(18, failure_value)})
        reward_points.append({"timestamp": iso(point_time), "value": round(min(0.91, reward_value), 3)})

    request_series = [
        {"id": "requests", "label": "Requests", "color": "#7c3aed", "points": requests_points},
        {"id": "failures", "label": "Failures", "color": "#f97316", "points": failure_points},
    ]
    success_series = [
        {
            "id": "heal_rate",
            "label": "Auto-heal rate",
            "color": "#14b8a6",
            "points": [{"timestamp": point["timestamp"], "value": round(78 + idx * 0.22 + RNG.random() * 1.2, 2)} for idx, point in enumerate(requests_points)],
        }
    ]
    reward_series = [{"id": "reward", "label": "Reward score", "color": "#38bdf8", "points": reward_points}]
    return request_series, success_series, reward_series


def make_training_snapshot() -> dict:
    reward_curve = []
    loss_curve = []
    success_curve = []
    for step in range(1, 81):
        reward_curve.append(
            {
                "step": step,
                "reward": round(0.22 + step * 0.008 + math.sin(step / 7) * 0.02, 3),
                "baseline": round(0.31 + math.sin(step / 10) * 0.01, 3),
                "adaptive": round(0.63 + math.sin(step / 8) * 0.02, 3),
                "trained": round(0.41 + step * 0.0055 + math.sin(step / 6) * 0.025, 3),
                "win_rate": round(0.48 + step * 0.004, 3),
            }
        )
        loss_curve.append({"step": step, "loss": round(max(0.11, 1.14 - step * 0.012 + math.sin(step / 5) * 0.03), 3)})
        success_curve.append(
            {
                "step": step,
                "baseline": round(0.54 + math.sin(step / 10) * 0.01, 3),
                "adaptive": round(0.82 + math.sin(step / 9) * 0.015, 3),
                "trained": round(0.61 + step * 0.003 + math.sin(step / 8) * 0.01, 3),
            }
        )
    return {
        "policy_version": "v4.7.2",
        "trainer": "hf_trl_structured_policy",
        "last_updated": iso(datetime.now(UTC)),
        "reward_curve": reward_curve,
        "loss_curve": loss_curve,
        "success_curve": success_curve,
        "summary_cards": [
            {"id": "train-win", "label": "Trained Policy Win Rate", "value": "76.4%", "delta": "+11.2 pts", "direction": "up", "hint": "Compared to frozen baseline policy"},
            {"id": "reward-peak", "label": "Peak Reward", "value": "0.88", "delta": "+0.19", "direction": "up", "hint": "Best evaluation reward over held-out episodes"},
            {"id": "loss-final", "label": "Final Loss", "value": "0.12", "delta": "-0.96", "direction": "down", "hint": "Cross-episode structured action loss"},
            {"id": "abstain-precision", "label": "Safe Abstain Precision", "value": "97.1%", "delta": "+4.0 pts", "direction": "up", "hint": "Unrecoverable auth scenarios handled safely"},
        ],
    }


def make_integrations() -> list[dict]:
    rows = []
    for idx, (name, category) in enumerate(INTEGRATIONS):
        rows.append(
            {
                "id": f"integration-{idx}",
                "name": name,
                "category": category,
                "status": "Ready",
                "setup_time": f"{5 + idx * 2} min",
                "description": f"Connect ReMorph healing workflows to {name} APIs and contract telemetry.",
                "features": [
                    "Schema-aware retries",
                    "Telemetry export",
                    "Policy-driven recovery",
                ],
            }
        )
    return rows


def make_enterprise() -> dict:
    members = []
    api_keys = []
    audit_logs = []
    base_time = datetime.now(UTC)
    for idx in range(8):
        members.append(
            {
                "id": f"member-{idx}",
                "name": ["Ava Shah", "Noah Kim", "Mila Patel", "Arjun Rao", "Liam Chen", "Sara Khan", "Ivy Lin", "Zara Ali"][idx],
                "role": ["Platform Lead", "ML Engineer", "SRE", "Security", "Backend", "Product", "Solutions", "Finance"][idx],
                "team": ["Core", "Training", "Reliability", "Security", "Platform", "Growth", "Enterprise", "Ops"][idx],
                "status": "online" if idx < 5 else "idle",
                "last_active": iso(base_time - timedelta(minutes=idx * 11)),
            }
        )
    for idx in range(5):
        api_keys.append(
            {
                "id": f"key-{idx}",
                "name": f"prod-gateway-{idx + 1}",
                "scope": ["read:telemetry", "repair:execute", "admin:org", "billing:read", "audit:read"][idx],
                "last_used": iso(base_time - timedelta(hours=idx * 6)),
                "status": "active" if idx < 4 else "rotating",
            }
        )
    for idx in range(12):
        audit_logs.append(
            {
                "id": f"audit-{idx}",
                "timestamp": iso(base_time - timedelta(minutes=idx * 14)),
                "actor": members[idx % len(members)]["name"],
                "action": RNG.choice(["Created policy rollout", "Rotated API key", "Changed routing rule", "Reviewed abstain event"]),
                "resource": RNG.choice(["workspace/prod", "policy/v4.7.2", "key/prod-gateway-2", "org/acme-payments"]),
                "outcome": RNG.choice(["success", "approved", "logged"]),
            }
        )
    return {
        "members": members,
        "api_keys": api_keys,
        "audit_logs": audit_logs,
        "billing": {
            "plan_name": "Enterprise Annual",
            "monthly_spend": "$18,420",
            "projected_savings": "$41,300",
            "seat_count": 32,
            "request_budget_utilization": 0.74,
        },
    }


def main() -> None:
    requests = make_requests()
    failures = make_failures(requests)
    repairs = make_repairs(failures)
    activity = make_activity(repairs)
    metric_cards = make_metric_cards()
    request_series, success_series, reward_series = make_series()
    training = make_training_snapshot()
    integrations = make_integrations()
    enterprise = make_enterprise()

    overview = {
        "headline": "Your APIs heal themselves.",
        "tagline": "AI-powered detection, repair, retry, telemetry, and policy learning for drift-prone production APIs.",
        "stats": metric_cards,
        "incidents": activity[:6],
        "reward_trend": reward_series[0],
    }
    dashboard = {
        "stats": metric_cards,
        "requests_series": request_series,
        "success_series": success_series,
        "reward_series": reward_series,
        "incidents": activity[:10],
        "generated_at": iso(datetime.now(UTC)),
    }

    write_jsonl(SEED_ROOT / "requests.jsonl", requests)
    write_jsonl(SEED_ROOT / "failures.jsonl", failures)
    write_jsonl(SEED_ROOT / "repairs.jsonl", repairs)
    write_jsonl(SEED_ROOT / "activity.jsonl", activity)
    write_json(SEED_ROOT / "integrations.json", integrations)
    write_json(GENERATED_ROOT / "overview.json", overview)
    write_json(GENERATED_ROOT / "dashboard.json", dashboard)
    write_json(GENERATED_ROOT / "training.json", training)
    write_json(GENERATED_ROOT / "training_metrics.json", {"summary_cards": training["summary_cards"]})
    write_json(GENERATED_ROOT / "reward_curve.json", training["reward_curve"])
    write_json(GENERATED_ROOT / "loss_curve.json", training["loss_curve"])
    write_json(GENERATED_ROOT / "enterprise.json", enterprise)


if __name__ == "__main__":
    main()
