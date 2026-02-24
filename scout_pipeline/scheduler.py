from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from croniter import croniter

CN_TZ = timezone(timedelta(hours=8))


def run_scheduler(cron_expr: str, job) -> None:
    base = datetime.now(CN_TZ)
    iterator = croniter(cron_expr, base)

    while True:
        next_time = iterator.get_next(datetime)
        sleep_seconds = max(0, (next_time - datetime.now(CN_TZ)).total_seconds())
        time.sleep(sleep_seconds)
        job()
