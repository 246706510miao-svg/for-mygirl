"""固定版本 RSS 目录的导入、缓存与来源白名单。"""

from __future__ import annotations

import asyncio
import html
import json
import re
import xml.etree.ElementTree as element_tree
from dataclasses import asdict, dataclass
from typing import Any, Iterable
from urllib.parse import quote, urlsplit

import httpx


CATALOG_CACHE_KEY = "news-focus:catalog:v3"
CATALOG_SCHEMA_VERSION = 3
XIANGYU_REPOSITORY = "xiangyugongzuoliu/awesome-rss-feeds-list"
XIANGYU_COMMIT = "2ab3b9b167853aca17b85d5bc820ca512b27e9f0"
PLENARY_REPOSITORY = "plenaryapp/awesome-rss-feeds"
PLENARY_COMMIT = "3a7a9e28943d28b8acb6d9197fb168a8be5267f6"

PLENARY_RECOMMENDED = (
    "Programming",
    "Tech",
    "Startups",
    "Cyber security",
    "Science",
    "News",
)
PLENARY_COUNTRIES = (
    "Australia", "Bangladesh", "Brazil", "Canada", "France", "Germany", "Hong Kong SAR China",
    "India", "Indonesia", "Iran", "Ireland", "Italy", "Japan", "Mexico", "Myanmar (Burma)",
    "Nigeria", "Pakistan", "Philippines", "Poland", "Russia", "South Africa", "Spain", "Ukraine",
    "United Kingdom", "United States",
)

BLOCKED_HOST_PARTS = (
    "api.xgo.ing", "wechat2rss", "rsshub", "rss-bridge", "rss.app", "feedly.com",
    "twitter.com", "x.com", "t.co", "youtube.com", "podcasts.apple.com", "spotify.com",
    "nytimes.com", "wsj.com", "ft.com", "bloomberg.com", "economist.com", "theinformation.com",
    "scmp.com", "patreon.com", "substack.com", "medium.com",
)
BLOCKED_CATEGORY_PARTS = (
    "podcast", "lifestyle", "fashion", "food", "music", "movie", "television", "sports", "travel",
    "beauty", "photography", "gaming", "funny", "memes", "cricket", "football", "tennis",
)


@dataclass(frozen=True)
class FeedSource:
    name: str
    feed_url: str
    catalog: str
    labels: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["labels"] = list(self.labels)
        return payload

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "FeedSource":
        return cls(
            name=str(value.get("name") or "公开 RSS"),
            feed_url=str(value.get("feed_url") or ""),
            catalog=str(value.get("catalog") or ""),
            labels=tuple(str(item) for item in value.get("labels", []) if str(item).strip()),
        )


CHINA_FOCUS_CATALOG_VERSION = "2026-07-14-v2"
CHINA_FOCUS_SOURCES = (
    FeedSource("中国新闻网国内", "https://www.chinanews.com.cn/rss/china.xml", "china-focus", ("manual", "china_focus", "china", "authoritative")),
    FeedSource("中国新闻网财经", "https://www.chinanews.com.cn/rss/finance.xml", "china-focus", ("manual", "china_focus", "china", "authoritative")),
    FeedSource("中国日报 China News", "http://www.chinadaily.com.cn/rss/china_rss.xml", "china-focus", ("manual", "china_focus", "china", "authoritative")),
)


def snapshot_metadata() -> dict[str, str]:
    return {
        "schemaVersion": str(CATALOG_SCHEMA_VERSION),
        "xiangyu": f"{XIANGYU_REPOSITORY}@{XIANGYU_COMMIT}",
        "plenary": f"{PLENARY_REPOSITORY}@{PLENARY_COMMIT}",
        "chinaFocus": CHINA_FOCUS_CATALOG_VERSION,
    }


def snapshot_documents() -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """返回固定提交中的 OPML 文件，不依赖仓库分支的后续变更。"""
    documents: list[tuple[str, str, tuple[str, ...]]] = [
        (
            "xiangyu",
            f"https://raw.githubusercontent.com/{XIANGYU_REPOSITORY}/{XIANGYU_COMMIT}/feeds.opml",
            ("catalog", "xiangyu"),
        )
    ]
    for category in PLENARY_RECOMMENDED:
        documents.append((
            "plenary",
            f"https://raw.githubusercontent.com/{PLENARY_REPOSITORY}/{PLENARY_COMMIT}/recommended/without_category/{quote(category)}.opml",
            ("recommended", category),
        ))
    for country in PLENARY_COUNTRIES:
        documents.append((
            "plenary",
            f"https://raw.githubusercontent.com/{PLENARY_REPOSITORY}/{PLENARY_COMMIT}/countries/without_category/{quote(country)}.opml",
            ("country", country, "news"),
        ))
    return tuple(documents)


async def import_snapshot(client: httpx.AsyncClient) -> tuple[list[FeedSource], list[str]]:
    """只在目录为空或明确刷新时下载固定 OPML 快照。"""
    documents = snapshot_documents()
    semaphore = asyncio.Semaphore(8)

    async def fetch(document: tuple[str, str, tuple[str, ...]]) -> tuple[list[FeedSource], str | None]:
        catalog, url, labels = document
        try:
            async with semaphore:
                response = await client.get(url, headers={"Accept": "application/xml, text/xml", "User-Agent": "for-mygirl-news-focus/2.0"})
            response.raise_for_status()
            return parse_opml(response.text, catalog, labels), None
        except Exception as exc:
            return [], f"目录 {url.rsplit('/', 1)[-1]}: {str(exc)[:160]}"

    rows = await asyncio.gather(*(fetch(document) for document in documents))
    sources: dict[str, FeedSource] = {}
    errors: list[str] = []
    for loaded, error in rows:
        if error:
            errors.append(error)
        for source in loaded:
            sources.setdefault(source.feed_url, source)
    # 中国大事的固定白名单优先覆盖目录中的同 URL 条目，确保会进入专属分类。
    for source in CHINA_FOCUS_SOURCES:
        sources[source.feed_url] = source
    return sorted(sources.values(), key=lambda item: (item.catalog, item.name.casefold(), item.feed_url)), errors


def parse_opml(body: str, catalog: str, labels: Iterable[str]) -> list[FeedSource]:
    rows: list[FeedSource] = []

    try:
        root = element_tree.fromstring(body)
    except element_tree.ParseError:
        # 少量第三方 OPML 把标题中的 & 或 < 原样写入。容错时只读取 outline 属性，
        # 仍不会请求任何文章链接，也不会把不在属性中的文本当作来源。
        return _parse_outline_attributes(body, catalog, labels)

    def visit(node: element_tree.Element, inherited: tuple[str, ...]) -> None:
        name = (node.attrib.get("text") or node.attrib.get("title") or "").strip()
        feed_url = (node.attrib.get("xmlUrl") or node.attrib.get("xmlurl") or "").strip()
        path = inherited + ((name,) if name else ())
        if feed_url and source_is_allowed(feed_url, path):
            rows.append(FeedSource(
                name=name or _display_name(feed_url),
                feed_url=feed_url,
                catalog=catalog,
                labels=tuple(dict.fromkeys((*labels, *path))),
            ))
        for child in node.findall("outline"):
            visit(child, path)

    body_node = root.find("body")
    for outline in (body_node.findall("outline") if body_node is not None else root.findall(".//outline")):
        visit(outline, tuple(str(item) for item in labels if str(item).strip()))
    return rows


def _parse_outline_attributes(body: str, catalog: str, labels: Iterable[str]) -> list[FeedSource]:
    rows: list[FeedSource] = []
    outline_pattern = re.compile(r"<outline\b(?:[^\"'>]|\"[^\"]*\"|'[^']*')*>", flags=re.IGNORECASE)
    attribute_pattern = re.compile(r"([:\w-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)')")
    base_labels = tuple(str(item) for item in labels if str(item).strip())
    for tag in outline_pattern.findall(body):
        attributes = {key.casefold(): html.unescape(double or single or "") for key, double, single in attribute_pattern.findall(tag)}
        feed_url = attributes.get("xmlurl", "").strip()
        name = (attributes.get("text") or attributes.get("title") or "").strip()
        if feed_url and source_is_allowed(feed_url, (*base_labels, name)):
            rows.append(FeedSource(
                name=name or _display_name(feed_url),
                feed_url=feed_url,
                catalog=catalog,
                labels=base_labels,
            ))
    return rows


def source_is_allowed(feed_url: str, labels: Iterable[str]) -> bool:
    parsed = urlsplit(feed_url)
    host = parsed.netloc.lower().removeprefix("www.")
    text = " ".join(str(item).lower() for item in labels)
    if parsed.scheme not in {"http", "https"} or not host:
        return False
    if any(part in host for part in BLOCKED_HOST_PARTS):
        return False
    return not any(part in text for part in BLOCKED_CATEGORY_PARTS)


def encode_snapshot(sources: Iterable[FeedSource]) -> str:
    return json.dumps({"metadata": snapshot_metadata(), "sources": [source.to_dict() for source in sources]}, ensure_ascii=False, separators=(",", ":"))


def decode_snapshot(value: str | bytes | None) -> list[FeedSource]:
    if not value:
        return []
    try:
        payload = json.loads(value.decode("utf-8") if isinstance(value, bytes) else value)
        metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
        if str(metadata.get("schemaVersion")) != str(CATALOG_SCHEMA_VERSION):
            return []
        rows = payload.get("sources", []) if isinstance(payload, dict) else []
        return [FeedSource.from_dict(item) for item in rows if isinstance(item, dict) and item.get("feed_url")]
    except (TypeError, ValueError):
        return []


def _display_name(feed_url: str) -> str:
    return urlsplit(feed_url).netloc.removeprefix("www.") or "公开 RSS"
