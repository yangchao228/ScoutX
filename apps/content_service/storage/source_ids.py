from __future__ import annotations

import hashlib


def compute_source_id(name: str) -> str:
    digest = hashlib.md5(name.strip().encode("utf-8")).hexdigest()
    return f"src_{digest}"
