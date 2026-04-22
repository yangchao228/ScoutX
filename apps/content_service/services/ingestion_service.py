from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import time

from sqlalchemy.orm import Session

from apps.content_service.normalizers.content_normalizer import normalize_content_item
from apps.content_service.services.source_loader import load_source_config
from apps.content_service.settings import load_settings
from apps.content_service.storage.content_repository import ContentRepository, UpsertStats
from apps.content_service.storage.runtime_state_repository import RuntimeStateRepository
from apps.content_service.storage.source_repository import SourceRepository
from apps.content_service.storage.source_snapshot_repository import SourceSnapshotRepository
from scout_pipeline.collector import collect_html, collect_json_feed, collect_rss
from scout_pipeline.config import HTMLSource, JSONFeedSource, RSSSource


@dataclass(frozen=True)
class IngestionResult:
    collected: int
    normalized: int
    created: int
    updated: int
    failed_sources: int
    source_runs: list["SourceRunResult"]


@dataclass(frozen=True)
class SourceRunResult:
    name: str
    source_type: str
    status: str
    collected: int
    normalized: int
    created: int
    updated: int
    duration_ms: int
    error: str | None = None


@dataclass(frozen=True)
class CollectedSourceBatch:
    items: list
    fetched_from_url: str | None = None
    snapshot_payload: dict | None = None


@dataclass
class IngestionService:
    session: Session

    def run_once(self) -> IngestionResult:
        config = load_source_config()
        settings = load_settings()
        source_repository = SourceRepository(self.session)
        snapshot_repository = SourceSnapshotRepository(self.session)
        source_repository.sync_source_configs(
            [source.model_dump(mode="json") for source in config.sources],
            schedule=config.schedule.cron,
        )
        repository = ContentRepository(self.session)
        collected_count = 0
        normalized_count = 0
        created = 0
        updated = 0
        failed_sources = 0
        slow_sources = 0
        source_runs: list[SourceRunResult] = []

        for source in config.sources:
            started = time.monotonic()
            try:
                batch = self._collect_single_source(source)
                items = batch.items
                normalized_items = [normalize_content_item(item) for item in items if item.title or item.url]
                stats = repository.upsert_items(normalized_items)
                if batch.snapshot_payload is not None:
                    snapshot_repository.save_latest_snapshot(
                        source_name=source.name,
                        fetched_from_url=batch.fetched_from_url,
                        item_count=len(items),
                        payload_json=batch.snapshot_payload,
                    )
                duration_ms = int((time.monotonic() - started) * 1000)
                collected_count += len(items)
                normalized_count += len(normalized_items)
                created += stats.created
                updated += stats.updated
                if duration_ms >= _effective_slow_threshold_ms(
                    source=source,
                    default_threshold_ms=settings.slow_source_threshold_ms,
                ):
                    slow_sources += 1
                source_repository.mark_run_result(source.name, status="success", duration_ms=duration_ms)
                source_runs.append(
                    SourceRunResult(
                        name=source.name,
                        source_type=source.type,
                        status="success",
                        collected=len(items),
                        normalized=len(normalized_items),
                        created=stats.created,
                        updated=stats.updated,
                        duration_ms=duration_ms,
                    )
                )
            except Exception as exc:
                duration_ms = int((time.monotonic() - started) * 1000)
                failed_sources += 1
                source_repository.mark_run_result(
                    source.name,
                    status="failed",
                    error=str(exc),
                    duration_ms=duration_ms,
                )
                source_runs.append(
                    SourceRunResult(
                        name=source.name,
                        source_type=source.type,
                        status="failed",
                        collected=0,
                        normalized=0,
                        created=0,
                        updated=0,
                        duration_ms=duration_ms,
                        error=str(exc),
                    )
                )

        self.session.commit()
        RuntimeStateRepository(self.session).save_latest_scheduler_run(
            {
                "time": utc_now_text(),
                "collected": collected_count,
                "normalized": normalized_count,
                "created": created,
                "updated": updated,
                "failed_sources": failed_sources,
                "slow_sources": slow_sources,
            }
        )
        self.session.commit()
        return IngestionResult(
            collected=collected_count,
            normalized=normalized_count,
            created=created,
            updated=updated,
            failed_sources=failed_sources,
            source_runs=source_runs,
        )

    def _collect_single_source(self, source: RSSSource | HTMLSource | JSONFeedSource) -> CollectedSourceBatch:
        if isinstance(source, RSSSource):
            return CollectedSourceBatch(items=collect_rss(source))
        if isinstance(source, JSONFeedSource):
            result = collect_json_feed(source)
            return CollectedSourceBatch(
                items=result.items,
                fetched_from_url=result.fetched_from_url,
                snapshot_payload=result.snapshot_payload,
            )
        return CollectedSourceBatch(items=collect_html(source))


def utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _effective_slow_threshold_ms(
    *,
    source: RSSSource | HTMLSource | JSONFeedSource,
    default_threshold_ms: int,
) -> int:
    configured = getattr(source, "slow_threshold_ms", None)
    if isinstance(configured, int) and configured > 0:
        return configured
    return default_threshold_ms
