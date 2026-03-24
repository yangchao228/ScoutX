from __future__ import annotations

import unittest

from scout_pipeline.models import TweetThread
from scout_pipeline.x_payloads import build_x_post_payloads


class XPayloadsTest(unittest.TestCase):
    def test_build_x_post_payloads_creates_reply_chain(self) -> None:
        payloads = build_x_post_payloads(
            TweetThread(tweets=["first post", "second post", "third post"]),
            max_post_length=280,
        )
        self.assertEqual(payloads[0], {"text": "first post"})
        self.assertEqual(
            payloads[1],
            {
                "text": "second post",
                "reply": {"in_reply_to_tweet_id": "__PREVIOUS_POST_ID__"},
            },
        )
        self.assertEqual(
            payloads[2],
            {
                "text": "third post",
                "reply": {"in_reply_to_tweet_id": "__PREVIOUS_POST_ID__"},
            },
        )

    def test_build_x_post_payloads_splits_long_posts(self) -> None:
        payloads = build_x_post_payloads(TweetThread(tweets=["hello " * 60]), max_post_length=50)
        self.assertGreater(len(payloads), 1)
        self.assertTrue(all(len(payload["text"]) <= 50 for payload in payloads))


if __name__ == "__main__":
    unittest.main()
