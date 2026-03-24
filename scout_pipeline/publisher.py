from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

try:
    from tenacity import retry, stop_after_attempt, wait_exponential
except ImportError:  # pragma: no cover - fallback for minimal smoke environments
    def retry(*_args, **_kwargs):
        def _decorator(func):
            return func

        return _decorator

    def stop_after_attempt(_attempts):
        return None

    def wait_exponential(**_kwargs):
        return None

from scout_pipeline.config import PublisherConfig
from scout_pipeline.models import Item, TweetThread
from scout_pipeline.oauth1 import build_oauth1_header
from scout_pipeline.thread_formatter import normalize_thread_for_x
from scout_pipeline.utils import require_env
from scout_pipeline.x_payloads import build_x_post_payloads


class Publisher(ABC):
    def __init__(self, config: PublisherConfig) -> None:
        self.config = config
        self.channel_name = config.dedup_channel

    def build_draft_payload(self, thread: TweetThread) -> dict[str, Any] | list[dict[str, Any]]:
        raise NotImplementedError

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
        import requests

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
        import requests

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


class XOfficialPublisher(Publisher):
    def __init__(self, config: PublisherConfig) -> None:
        super().__init__(config)
        self.channel_name = config.dedup_channel or "publisher:x_official"

    def build_post_payloads(self, thread: TweetThread) -> list[dict[str, Any]]:
        return build_x_post_payloads(thread, self.config.max_post_length)

    def build_draft_payload(self, thread: TweetThread) -> list[dict[str, Any]]:
        return self.build_post_payloads(thread)

    def _headers(self, url: str) -> dict[str, str]:
        consumer_key = require_env(self.config.x_consumer_key_env)
        consumer_secret = require_env(self.config.x_consumer_secret_env)
        access_token = require_env(self.config.x_access_token_env)
        access_token_secret = require_env(self.config.x_access_token_secret_env)
        return {
            "Authorization": build_oauth1_header(
                "POST",
                url,
                consumer_key=consumer_key,
                consumer_secret=consumer_secret,
                access_token=access_token,
                access_token_secret=access_token_secret,
            ),
            "Content-Type": "application/json",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    def publish(self, item: Item, thread: TweetThread) -> dict[str, Any]:
        import requests

        url = f"{str(self.config.x_api_base).rstrip('/')}/tweets"
        payloads = self.build_post_payloads(thread)
        created: list[dict[str, Any]] = []
        previous_post_id: str | None = None
        for payload in payloads:
            current_payload = dict(payload)
            if "reply" in current_payload:
                if not previous_post_id:
                    raise RuntimeError("missing previous post id while building thread reply")
                current_payload["reply"] = {"in_reply_to_tweet_id": previous_post_id}
            response = requests.post(
                url,
                headers=self._headers(url),
                json=current_payload,
                timeout=60,
            )
            if not response.ok:
                raise RuntimeError(f"X publish failed {response.status_code}: {response.text[:500]}")
            data = response.json()
            if not isinstance(data, dict):
                raise RuntimeError("X publish returned a non-object response")
            post_data = data.get("data") if isinstance(data.get("data"), dict) else data
            post_id = str(post_data.get("id") or "")
            if not post_id:
                raise RuntimeError(f"X publish response missing id: {data}")
            previous_post_id = post_id
            created.append(data)

        root_id = (
            str((created[0].get("data") or {}).get("id") or "")
            if created and isinstance(created[0].get("data"), dict)
            else None
        )
        print(f"[publish] x official thread created (item={item.url}, posts={len(created)}, root_id={root_id})")
        return {
            "provider": "x_official",
            "count": len(created),
            "root_id": root_id,
            "responses": created,
            "url": f"https://x.com/i/web/status/{root_id}" if root_id else None,
        }


def build_publisher(config: PublisherConfig) -> Publisher | None:
    if not config.enabled:
        return None
    if config.provider == "typefully":
        return TypefullyPublisher(config)
    if config.provider == "x_official":
        return XOfficialPublisher(config)
    raise RuntimeError(f"Unsupported publisher provider: {config.provider}")
