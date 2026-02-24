from __future__ import annotations

from scout_pipeline.models import TweetThread


class Publisher:
    def publish(self, thread: TweetThread) -> None:
        raise NotImplementedError("接入 X API 或 Typefully API")
