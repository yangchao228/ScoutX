from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from urllib.parse import parse_qsl, quote, urlparse


def _percent_encode(value: str) -> str:
    return quote(value, safe="~-._")


def build_oauth1_header(
    method: str,
    url: str,
    *,
    consumer_key: str,
    consumer_secret: str,
    access_token: str,
    access_token_secret: str,
) -> str:
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    oauth_params = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }

    signature_params: list[tuple[str, str]] = list(parse_qsl(parsed.query, keep_blank_values=True))
    signature_params.extend(oauth_params.items())
    normalized_param_string = "&".join(
        f"{_percent_encode(key)}={_percent_encode(value)}"
        for key, value in sorted(signature_params)
    )
    signature_base_string = "&".join(
        [
            method.upper(),
            _percent_encode(base_url),
            _percent_encode(normalized_param_string),
        ]
    )
    signing_key = f"{_percent_encode(consumer_secret)}&{_percent_encode(access_token_secret)}"
    signature = base64.b64encode(
        hmac.new(
            signing_key.encode("utf-8"),
            signature_base_string.encode("utf-8"),
            hashlib.sha1,
        ).digest()
    ).decode("utf-8")

    oauth_params["oauth_signature"] = signature
    return "OAuth " + ", ".join(
        f'{_percent_encode(key)}="{_percent_encode(value)}"'
        for key, value in sorted(oauth_params.items())
    )
