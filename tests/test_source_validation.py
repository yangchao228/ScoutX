from __future__ import annotations

import unittest
from unittest.mock import patch

from apps.content_service.schemas.source import HTMLSourceValidationRequest, RSSSourceValidationRequest
from apps.content_service.services.source_validation import validate_source_payload
from scout_pipeline.models import Item


class SourceValidationTest(unittest.TestCase):
    def test_validate_rss_success(self) -> None:
        request = RSSSourceValidationRequest(
            type="rss",
            name="jiqizhixin_rss",
            url="https://www.jiqizhixin.com/rss",
        )
        items = [
            Item(
                source="jiqizhixin_rss",
                title="Example title",
                url="https://example.com/a",
                description="summary",
            )
        ]
        with patch("apps.content_service.services.source_validation._collect_rss_items", return_value=items):
            result = validate_source_payload(request)

        self.assertTrue(result.ok)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.item_count, 1)
        self.assertEqual(result.sample_titles, ["Example title"])

    def test_validate_html_http_error(self) -> None:
        request = HTMLSourceValidationRequest(
            type="html",
            name="example_html",
            url="https://example.com/list",
            list_selector=".item",
            fields={},
        )
        error = RuntimeError("403 Client Error")
        error.response = type("Response", (), {"status_code": 403})()
        with patch("apps.content_service.services.source_validation._collect_html_items", side_effect=error):
            result = validate_source_payload(request)

        self.assertFalse(result.ok)
        self.assertEqual(result.status_code, 403)
        self.assertEqual(result.item_count, 0)
        self.assertIn("403", result.message or "")


if __name__ == "__main__":
    unittest.main()
