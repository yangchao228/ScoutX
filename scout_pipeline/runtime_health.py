from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _minutes_since(now: datetime, timestamp: str | None) -> int | None:
    dt = parse_timestamp(timestamp)
    if dt is None:
        return None
    return max(0, int((now - dt).total_seconds() // 60))


@dataclass(frozen=True)
class HealthCheckResult:
    name: str
    status: str
    message: str


def evaluate_runtime_health(
    provider_status: dict[str, Any],
    consumer_status: dict[str, Any],
    *,
    now: datetime,
    max_failed_sources: int = 3,
    max_slow_sources: int = 1,
    max_provider_lag_minutes: int = 120,
    max_checkpoint_lag_minutes: int = 120,
    require_report_today: bool = False,
) -> dict[str, Any]:
    checks: list[HealthCheckResult] = []

    provider_data = provider_status.get("data") or {}
    provider_run = provider_data.get("latest_scheduler_run") or {}
    provider_sources = provider_data.get("sources") or {}

    run_age = _minutes_since(now, provider_run.get("time"))
    if run_age is None:
        checks.append(
            HealthCheckResult(
                name="provider_scheduler_run",
                status="fail",
                message="content-service missing latest_scheduler_run",
            )
        )
    elif run_age > max_provider_lag_minutes:
        checks.append(
            HealthCheckResult(
                name="provider_scheduler_run",
                status="fail",
                message=(
                    f"content-service latest scheduler run is stale: {run_age}m "
                    f"(threshold {max_provider_lag_minutes}m)"
                ),
            )
        )
    else:
        checks.append(
            HealthCheckResult(
                name="provider_scheduler_run",
                status="ok",
                message=f"content-service latest scheduler run age={run_age}m",
            )
        )

    failed_sources = int(provider_sources.get("failed") or 0)
    recent_failures = list(provider_sources.get("recent_failures") or [])
    failure_names = [
        str(item.get("name") or "").strip()
        for item in recent_failures
        if str(item.get("name") or "").strip()
    ]
    failure_summary = ", ".join(failure_names[:5])
    if failed_sources > max_failed_sources:
        checks.append(
            HealthCheckResult(
                name="provider_failed_sources",
                status="fail",
                message=(
                    f"content-service has {failed_sources} failed sources "
                    f"(threshold {max_failed_sources})"
                    + (f": {failure_summary}" if failure_summary else "")
                ),
            )
        )
    elif failed_sources > 0:
        checks.append(
            HealthCheckResult(
                name="provider_failed_sources",
                status="warn",
                message=(
                    f"content-service has {failed_sources} failed sources"
                    + (f": {failure_summary}" if failure_summary else "")
                ),
            )
        )
    else:
        checks.append(
            HealthCheckResult(
                name="provider_failed_sources",
                status="ok",
                message="content-service has no failed sources",
            )
        )

    slow_sources = int(provider_sources.get("slow") or 0)
    recent_slow_sources = list(provider_sources.get("recent_slow_sources") or [])
    slow_summary = ", ".join(
        [
            f"{str(item.get('name') or '').strip()}({int(item.get('last_duration_ms') or 0)}ms)"
            for item in recent_slow_sources
            if str(item.get("name") or "").strip()
        ][:5]
    )
    if slow_sources > max_slow_sources:
        checks.append(
            HealthCheckResult(
                name="provider_slow_sources",
                status="fail",
                message=(
                    f"content-service has {slow_sources} slow sources "
                    f"(threshold {max_slow_sources})"
                    + (f": {slow_summary}" if slow_summary else "")
                ),
            )
        )
    elif slow_sources > 0:
        checks.append(
            HealthCheckResult(
                name="provider_slow_sources",
                status="warn",
                message=(
                    f"content-service has {slow_sources} slow sources"
                    + (f": {slow_summary}" if slow_summary else "")
                ),
            )
        )
    else:
        checks.append(
            HealthCheckResult(
                name="provider_slow_sources",
                status="ok",
                message="content-service has no slow sources",
            )
        )

    sync_states = consumer_status.get("sync_states") or []
    content_sync_states = [state for state in sync_states if str(state.get("provider") or "") == "content_service"]
    if not content_sync_states:
        checks.append(
            HealthCheckResult(
                name="consumer_checkpoint",
                status="fail",
                message="ScoutX has no content_service sync_state checkpoint",
            )
        )
    else:
        newest_state = max(
            content_sync_states,
            key=lambda state: parse_timestamp(state.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc),
        )
        checkpoint_age = _minutes_since(now, newest_state.get("updated_at"))
        if checkpoint_age is None:
            checks.append(
                HealthCheckResult(
                    name="consumer_checkpoint",
                    status="fail",
                    message="ScoutX content_service checkpoint timestamp is invalid",
                )
            )
        elif checkpoint_age > max_checkpoint_lag_minutes:
            checks.append(
                HealthCheckResult(
                    name="consumer_checkpoint",
                    status="fail",
                    message=(
                        f"ScoutX checkpoint is stale: {checkpoint_age}m "
                        f"(threshold {max_checkpoint_lag_minutes}m)"
                    ),
                )
            )
        else:
            checks.append(
                HealthCheckResult(
                    name="consumer_checkpoint",
                    status="ok",
                    message=f"ScoutX checkpoint age={checkpoint_age}m key={newest_state.get('state_key')}",
                )
            )

    latest_report_date = str((consumer_status.get("reports") or {}).get("latest_report_date") or "").strip() or None
    if require_report_today:
        today = now.astimezone(timezone.utc).date().isoformat()
        if latest_report_date != today:
            checks.append(
                HealthCheckResult(
                    name="consumer_latest_report_date",
                    status="fail",
                    message=f"ScoutX latest_report_date={latest_report_date or 'none'} expected={today}",
                )
            )
        else:
            checks.append(
                HealthCheckResult(
                    name="consumer_latest_report_date",
                    status="ok",
                    message=f"ScoutX latest_report_date={today}",
                )
            )

    overall_status = "ok"
    if any(check.status == "fail" for check in checks):
        overall_status = "fail"
    elif any(check.status == "warn" for check in checks):
        overall_status = "warn"

    return {
        "status": overall_status,
        "checked_at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "provider_recent_failures": recent_failures,
        "provider_recent_slow_sources": recent_slow_sources,
        "checks": [
            {
                "name": check.name,
                "status": check.status,
                "message": check.message,
            }
            for check in checks
        ],
    }
