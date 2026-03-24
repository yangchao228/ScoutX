from __future__ import annotations

import unittest

from scout_pipeline.oauth1 import build_oauth1_header


class OAuth1Test(unittest.TestCase):
    def test_build_oauth1_header_contains_required_fields(self) -> None:
        header = build_oauth1_header(
            "POST",
            "https://api.x.com/2/tweets",
            consumer_key="consumer-key",
            consumer_secret="consumer-secret",
            access_token="access-token",
            access_token_secret="access-token-secret",
        )
        self.assertTrue(header.startswith("OAuth "))
        self.assertIn('oauth_consumer_key="consumer-key"', header)
        self.assertIn('oauth_token="access-token"', header)
        self.assertIn('oauth_signature_method="HMAC-SHA1"', header)
        self.assertIn('oauth_signature="', header)
        self.assertIn('oauth_timestamp="', header)
        self.assertIn('oauth_nonce="', header)


if __name__ == "__main__":
    unittest.main()
