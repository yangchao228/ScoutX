from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


LATEST_SCHEDULER_RUN_KEY = "latest_scheduler_run"


@dataclass
class RuntimeStateRepository:
    session: Session

    def ensure_table(self) -> None:
        self.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS runtime_state (
                    state_key TEXT PRIMARY KEY,
                    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )

    def save_latest_scheduler_run(self, payload: dict[str, Any]) -> None:
        self.ensure_table()
        self.session.execute(
            text(
                """
                INSERT INTO runtime_state (state_key, payload_json, updated_at)
                VALUES (:state_key, CAST(:payload_json AS jsonb), :updated_at)
                ON CONFLICT (state_key) DO UPDATE SET
                    payload_json = CAST(EXCLUDED.payload_json AS jsonb),
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "state_key": LATEST_SCHEDULER_RUN_KEY,
                "payload_json": __import__("json").dumps(payload, ensure_ascii=False),
                "updated_at": datetime.now(timezone.utc),
            },
        )

    def load_latest_scheduler_run(self) -> dict[str, Any] | None:
        self.ensure_table()
        row = self.session.execute(
            text(
                """
                SELECT payload_json
                FROM runtime_state
                WHERE state_key = :state_key
                """
            ),
            {"state_key": LATEST_SCHEDULER_RUN_KEY},
        ).scalar_one_or_none()
        return dict(row) if row is not None else None
