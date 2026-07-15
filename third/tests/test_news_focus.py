from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx

from third.news_focus.catalog import CHINA_FOCUS_SOURCES, FeedSource, parse_opml
from third.news_focus.service import (
    Candidate,
    PublicNewsCollector,
    _dedupe_key,
    _feed_datetime,
    _news_focus_http_client_kwargs,
    filter_candidates,
    generate_news_focus,
    group_candidates,
    select_ranked_items,
)


NOW = datetime(2026, 7, 14, 7, 30, tzinfo=timezone.utc)


class FakeStateStore:
    def __init__(self) -> None:
        self.failed: list[str] = []
        self.succeeded: list[str] = []
        self.blocked: set[str] = set()

    def source_available(self, feed_url: str, now: datetime) -> bool:
        return feed_url not in self.blocked

    def source_succeeded(self, feed_url: str) -> None:
        self.succeeded.append(feed_url)

    def source_failed(self, feed_url: str, now: datetime) -> None:
        self.failed.append(feed_url)
        self.blocked.add(feed_url)


class DynamicLlm:
    def invoke(self, prompt: str) -> SimpleNamespace:
        payload = json.loads(prompt.rsplit("候选数据如下：\n", 1)[1])
        items = [
            {
                "id": row["id"],
                "titleZh": f"中文：{row['title']}",
                "summaryZh": "仅依据 RSS 标题与摘要整理的中文信息。",
                "tags": ["每日热门"],
                "topicKey": row["title"],
            }
            for row in payload[:5]
        ]
        return SimpleNamespace(content=json.dumps({"items": items}, ensure_ascii=False))


class NewsFocusTests(unittest.IsolatedAsyncioTestCase):
    def test_rss_proxy_is_scoped_to_real_news_clients(self) -> None:
        config = SimpleNamespace(news_focus_proxy_url="http://host.docker.internal:7891")
        transport = httpx.MockTransport(lambda _: httpx.Response(200))

        self.assertEqual(
            _news_focus_http_client_kwargs(config, None),
            {"proxy": "http://host.docker.internal:7891"},
        )
        self.assertEqual(
            _news_focus_http_client_kwargs(config, transport),
            {"transport": transport},
        )

    async def test_generation_groups_four_categories_without_visiting_article_urls(self) -> None:
        requested: list[str] = []
        sources = [
            FeedSource("AI Feed", "https://feeds.example.com/ai.xml", "test", ("ai",)),
            FeedSource("China Focus Feed", "https://feeds.example.com/china.xml", "test", ("china_focus",)),
            FeedSource("News Feed", "https://feeds.example.com/news.xml", "test", ("news",)),
            FeedSource("Open Source Feed", "https://feeds.example.com/open.xml", "test", ("programming",)),
        ]

        async def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            requested.append(url)
            name = url.rsplit("/", 1)[-1].replace(".xml", "")
            titles = {
                "ai": "Open AI model release",
                "china": "China major policy update",
                "news": "Breaking news report from public source",
                "open": "Open source project release",
            }
            if name in titles:
                article = f"https://article.example.com/{name}"
                xml = f"<rss><channel><item><title>{titles[name]}</title><link>{article}</link><pubDate>Tue, 14 Jul 2026 07:00:00 GMT</pubDate><description>metadata only</description></item></channel></rss>"
                return httpx.Response(200, text=xml)
            return httpx.Response(404)

        result = await generate_news_focus(
            now=NOW,
            transport=httpx.MockTransport(handler),
            llm=DynamicLlm(),
            catalog_sources=sources,
            state_store=FakeStateStore(),
        )

        self.assertEqual(result["sourceCount"], 4)
        self.assertEqual(sum(len(group["items"]) for group in result["groups"]), 4)
        self.assertEqual([group["key"] for group in result["groups"]], ["ai", "china_focus", "news", "open_source"])
        self.assertNotIn("score", result["groups"][0]["items"][0])
        self.assertTrue(all("article.example.com" not in url for url in requested))

    async def test_failed_source_enters_health_backoff_without_blocking_other_sources(self) -> None:
        state = FakeStateStore()
        sources = [
            FeedSource("Broken", "https://feeds.example.com/broken.xml", "test", ("news",)),
            FeedSource("Healthy", "https://feeds.example.com/healthy.xml", "test", ("news",)),
        ]

        async def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url).endswith("broken.xml"):
                return httpx.Response(503)
            return httpx.Response(200, text="<rss><channel></channel></rss>")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            collector = PublicNewsCollector(client, state, NOW)
            _, errors, _ = await collector.collect(sources)
            _, later_errors, _ = await collector.collect(sources)

        self.assertIn("https://feeds.example.com/broken.xml", state.failed)
        self.assertTrue(any("Broken" in error for error in errors))
        self.assertTrue(any("退避期" in error for error in later_errors))

    async def test_collector_accepts_large_catalog_with_bounded_source_requests(self) -> None:
        sources = [FeedSource(f"Source {index}", f"https://feeds.example.com/{index}.xml", "test", ("news",)) for index in range(2000)]

        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<rss><channel></channel></rss>")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            rows, errors, source_count = await PublicNewsCollector(client, FakeStateStore(), NOW).collect(sources)

        self.assertEqual(source_count, 2000)
        self.assertEqual(rows, [])
        self.assertEqual(errors, [])

    def test_filter_uses_title_fingerprint_and_grouping_falls_back_to_72_hours(self) -> None:
        items = [
            Candidate("old", "RSS", "https://example.com/old", "Old open source release", "", NOW - timedelta(hours=48), ("programming",)),
            Candidate("duplicate", "RSS", "https://another.example.com/duplicate", "Same title", "", NOW - timedelta(hours=1), ("news",)),
            Candidate("shown", "RSS", "https://example.com/shown", "Shown title", "", NOW - timedelta(hours=1), ("news",)),
        ]
        filtered = filter_candidates(items, NOW, 72, [_dedupe_key("Shown title")])
        groups, count = group_candidates(filtered, NOW, 24, [])

        self.assertEqual(count, 2)
        self.assertEqual([item.candidate_id for item in groups["open_source"]], ["old"])
        self.assertEqual([item.candidate_id for item in groups["news"]], ["duplicate"])

    def test_model_contract_rejects_unknown_and_keeps_score_out_of_output(self) -> None:
        candidate = Candidate("one", "RSS", "https://example.com/one", "open source release", "", NOW, ("programming",))
        self.assertEqual(select_ranked_items([candidate], '{"items":[{"id":"unknown"}]}'), [])
        output = select_ranked_items([candidate], json.dumps({"items": [{"id": "one", "titleZh": "中文标题", "summaryZh": "中文摘要", "tags": ["开源"], "topicKey": "项目"}]}))
        self.assertEqual(output[0]["rank"], 1)
        self.assertNotIn("score", output[0])

    def test_catalog_parser_excludes_proxy_and_podcast_sources(self) -> None:
        xml = """<opml><body><outline text="Programming"><outline text="Direct" xmlUrl="https://direct.example.com/feed.xml"/><outline text="Proxy" xmlUrl="https://api.xgo.ing/rss/user/abc"/></outline><outline text="Podcasts"><outline text="Podcast" xmlUrl="https://pod.example.com/feed.xml"/></outline></body></opml>"""
        sources = parse_opml(xml, "test", ("catalog",))
        self.assertEqual([source.name for source in sources], ["Direct"])

    def test_catalog_parser_tolerates_malformed_outline_titles(self) -> None:
        xml = '<opml><body><outline text="Research & Development" xmlUrl="https://direct.example.com/feed.xml"/></body></opml>'
        sources = parse_opml(xml, "test", ("news",))
        self.assertEqual(sources[0].feed_url, "https://direct.example.com/feed.xml")

    def test_china_focus_whitelist_has_fixed_direct_rss_sources(self) -> None:
        self.assertEqual(len(CHINA_FOCUS_SOURCES), 3)
        self.assertTrue(all(source.catalog == "china-focus" for source in CHINA_FOCUS_SOURCES))
        self.assertTrue(all("china_focus" in source.labels for source in CHINA_FOCUS_SOURCES))

    def test_feed_datetime_accepts_lowercase_pubdate(self) -> None:
        self.assertEqual(_feed_datetime({"pubdate": "2026-07-14T07:30:00Z"}), NOW)


if __name__ == "__main__":
    unittest.main()
