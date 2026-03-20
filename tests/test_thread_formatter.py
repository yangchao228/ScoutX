from __future__ import annotations

import unittest

from scout_pipeline.models import TweetThread
from scout_pipeline.thread_formatter import normalize_text, normalize_thread_for_x, split_long_text


class ThreadFormatterTest(unittest.TestCase):
    def test_normalize_text_collapses_redundant_whitespace(self) -> None:
        text = "  hello   world  \n\n\n  next\tline  "
        self.assertEqual(normalize_text(text), "hello world\n\nnext line")

    def test_split_long_text_respects_max_length(self) -> None:
        text = "alpha beta gamma delta epsilon zeta eta theta"
        chunks = split_long_text(text, 12)
        self.assertTrue(chunks)
        self.assertTrue(all(len(chunk) <= 12 for chunk in chunks))
        self.assertEqual(" ".join(chunks), text)

    def test_split_long_text_splits_single_long_word(self) -> None:
        chunks = split_long_text("x" * 25, 10)
        self.assertEqual(chunks, ["x" * 10, "x" * 10, "x" * 5])

    def test_normalize_thread_for_x_filters_blank_tweets(self) -> None:
        thread = TweetThread(tweets=["", "  hello world  ", "x" * 25])
        normalized = normalize_thread_for_x(thread, 10)
        self.assertEqual(normalized.tweets, ["hello", "world", "x" * 10, "x" * 10, "x" * 5])


if __name__ == "__main__":
    unittest.main()
