from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from third_two.api import create_app


class NewsFocusApiTests(unittest.TestCase):
    def test_internal_generation_passes_recent_fingerprints_and_returns_group_contract(self) -> None:
        generated = {
            "generatedAt": "2026-07-14T07:30:00+00:00",
            "sourceCount": 2,
            "candidateCount": 4,
            "groups": [{"key": "ai", "title": "AI", "items": [{"rank": 1, "title": "中文标题", "summary": "中文摘要", "tags": ["AI"], "source": "公开 RSS", "sourceUrl": "https://example.com", "publishedAt": "2026-07-14T07:00:00+00:00"}]}],
        }
        with patch("third_two.news_focus_router.generate_news_focus", new=AsyncMock(return_value=generated)) as mock_generate:
            client = TestClient(create_app())
            response = client.post("/internal/news-focus/generate", json={"recentFingerprints": ["title:old"], "hours": 24})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["groups"][0]["items"][0]["title"], "中文标题")
        mock_generate.assert_awaited_once_with(["title:old"], 24)

    def test_catalog_refresh_uses_internal_service(self) -> None:
        with patch("third_two.news_focus_router.refresh_news_focus_catalog", new=AsyncMock(return_value={"sourceCount": 123, "sourceErrors": []})):
            response = TestClient(create_app()).post("/internal/news-focus/sources/refresh")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sourceCount"], 123)


if __name__ == "__main__":
    unittest.main()
