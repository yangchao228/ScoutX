from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MediaAsset:
    url: str
    media_type: str
    local_path: Optional[str] = None


@dataclass
class Item:
    source: str
    title: str
    url: str
    description: str
    published_at: Optional[str] = None
    comments: List[str] = field(default_factory=list)
    media: List[MediaAsset] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


@dataclass
class LLMFilterResult:
    passed: bool
    score: float
    rationale: str


@dataclass
class TweetThread:
    tweets: List[str]
