from __future__ import annotations

import time
from datetime import datetime

from croniter import croniter


def run_scheduler(cron_expr: str, job) -> None:
    base = datetime.now()
    iterator = croniter(cron_expr, base)

    while True:
        next_time = iterator.get_next(datetime)
        sleep_seconds = max(0, (next_time - datetime.now()).total_seconds())
        time.sleep(sleep_seconds)
        job()
