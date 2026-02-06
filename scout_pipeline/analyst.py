from __future__ import annotations

import json
from typing import Tuple

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from scout_pipeline.config import LLMConfig
from scout_pipeline.models import Item, LLMFilterResult
from scout_pipeline.utils import require_env


def _build_prompt(config: LLMConfig, item: Item) -> str:
    return config.filter_user_prompt.format(
        title=item.title,
        url=item.url,
        description=item.description,
        comments="\n".join(item.comments),
    )


def _parse_filter_response(text: str) -> Tuple[bool, float, str]:
    normalized = text.strip()
    upper = normalized.upper()
    if "FALSE" in upper and "TRUE" not in upper:
        passed = False
    else:
        passed = "TRUE" in upper

    score = 0.0
    for token in normalized.replace("/", " ").split():
        try:
            score = float(token)
            break
        except ValueError:
            continue
    return passed, score, normalized


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def call_llm(config: LLMConfig, system_prompt: str, user_prompt: str) -> str:
    api_key = require_env(config.api_key_env)
    url = f"{config.api_base}/chat/completions"
    payload = {
        "model": config.model,
        "temperature": config.temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
    if not response.ok:
        raise RuntimeError(f"LLM request failed {response.status_code}: {response.text[:500]}")
    data = response.json()
    return data["choices"][0]["message"]["content"]


def filter_item(config: LLMConfig, item: Item) -> LLMFilterResult:
    user_prompt = _build_prompt(config, item)
    text = call_llm(config, config.filter_system_prompt, user_prompt)
    passed, score, rationale = _parse_filter_response(text)
    return LLMFilterResult(passed=passed, score=score, rationale=rationale)
