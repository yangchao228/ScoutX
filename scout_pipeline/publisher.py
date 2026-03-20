from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from scout_pipeline.config import PublisherConfig
from scout_pipeline.models import Item, TweetThread
from scout_pipeline.thread_formatter import normalize_thread_for_x
from scout_pipeline.utils import require_env


class Publisher(ABC):
    def __init__(self, config: PublisherConfig) -> None:
        self.config = config
        self.channel_name = config.dedup_channel

    @abstractmethod
    def publish(self, item: Item, thread: TweetThread) -> dict[str, Any]:
        raise NotImplementedError


class TypefullyPublisher(Publisher):
    def build_posts(self, thread: TweetThread) -> list[dict[str, str]]:
        normalized = normalize_thread_for_x(thread, self.config.max_post_length)
        return [{"text": tweet} for tweet in normalized.tweets]

    def build_draft_payload(self, thread: TweetThread) -> dict[str, Any]:
        posts = self.build_posts(thread)
        if not posts:
            raise RuntimeError("no publishable posts generated")

        payload: dict[str, Any] = {
            "platforms": {
                "x": {
                    "enabled": self.config.x_enabled,
                    "posts": posts,
                }
            },
        }
        if self.config.tags:
            payload["tags"] = self.config.tags
        if self.config.publish_mode != "draft":
            payload["publish_at"] = self.config.publish_mode
        return payload

    def _headers(self) -> dict[str, str]:
        api_key = require_env(self.config.api_key_env)
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    def list_social_sets(self) -> dict[str, Any]:
        response = requests.get(
            f"{str(self.config.api_base).rstrip('/')}/social-sets",
            headers=self._headers(),
            timeout=30,
        )
        if not response.ok:
            raise RuntimeError(f"Typefully social sets failed {response.status_code}: {response.text[:500]}")
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("Typefully social sets returned a non-object response")
        return data

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    def publish(self, item: Item, thread: TweetThread) -> dict[str, Any]:
        try:
            payload = self.build_draft_payload(thread)
        except RuntimeError as exc:
            raise RuntimeError(f"{exc} for {item.url}") from exc

        response = requests.post(
            f"{str(self.config.api_base).rstrip('/')}/social-sets/{self.config.social_set_id}/drafts",
            headers=self._headers(),
            json=payload,
            timeout=60,
        )
        if not response.ok:
            raise RuntimeError(f"Typefully publish failed {response.status_code}: {response.text[:500]}")
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("Typefully publish returned a non-object response")
        draft_id = data.get("id") or data.get("draft_id")
        print(
            "[publish] typefully draft created "
            f"(item={item.url}, mode={self.config.publish_mode}, draft_id={draft_id})"
        )
        return data


def build_publisher(config: PublisherConfig) -> Publisher | None:
    if not config.enabled:
        return None
    if config.provider == "typefully":
        return TypefullyPublisher(config)
    raise RuntimeError(f"Unsupported publisher provider: {config.provider}")
