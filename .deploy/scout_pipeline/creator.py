from __future__ import annotations

from scout_pipeline.config import LLMConfig
from scout_pipeline.models import Item, TweetThread
from scout_pipeline.analyst import call_llm


def create_thread(config: LLMConfig, item: Item) -> TweetThread:
    prompt = config.creator_user_prompt.format(
        title=item.title,
        url=item.url,
        description=item.description,
        comments="\n".join(item.comments),
    )
    text = call_llm(config, config.creator_system_prompt, prompt)
    tweets = [t.strip() for t in text.split("\n\n") if t.strip()]
    return TweetThread(tweets=tweets)
