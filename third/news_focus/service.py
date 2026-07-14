"""公开 RSS 元数据的四类每日热门收集、筛选与中文编辑。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import xml.etree.ElementTree as element_tree
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from third.agents.shared.config import ThirdServiceConfig, load_config
from third.agents.shared.openai_client import create_chat_openai

from .catalog import CATALOG_CACHE_KEY, FeedSource, decode_snapshot, encode_snapshot, import_snapshot


CATEGORY_ORDER = ("ai", "china_focus", "news", "open_source")
CATEGORY_TITLES = {"ai": "AI", "china_focus": "中国大事", "news": "新闻", "open_source": "开源"}
MAX_PER_FEED = 3
MAX_LLM_CANDIDATES_PER_CATEGORY = 20
MAX_ITEMS_PER_CATEGORY = 5
PRIMARY_HOURS = 24
FALLBACK_HOURS = 72
SOURCE_TIMEOUT_SECONDS = 6.0
SOURCE_CONCURRENCY = 16
MAX_REPORTED_ERRORS = 24

EXCLUDED_POLITICS_KEYWORDS = (
    "election", "president", "government", "parliament", "congress", "senate", "policy", "sanction",
    "diplomacy", "war", "military", "minister", "white house", "nato", "united nations",
    "选举", "总统", "政府", "议会", "国会", "政策", "制裁", "外交", "战争", "军事", "部长", "联合国",
)
AI_KEYWORDS = (
    "artificial intelligence", "machine learning", "deep learning", "large language", "llm", "model", "agent",
    "generative ai", "inference", "人工智能", "机器学习", "大模型", "语言模型", "智能体", "推理", "模型",
)
OPEN_SOURCE_KEYWORDS = (
    "open source", "opensource", "github", "gitlab", "release", "repository", "kernel", "kubernetes",
    "开源", "代码库", "版本发布", "项目发布", "发布版", "源码",
)
NEWS_KEYWORDS = (
    "breaking", "latest news", "headline", "report", "announces", "update", "新闻", "快讯", "报道", "通报",
)


class NewsFocusGenerationError(RuntimeError):
    """每日热门无法形成可展示结果时抛出。"""


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    source: str
    source_url: str
    title: str
    snippet: str
    published_at: datetime
    source_labels: tuple[str, ...] = ()


class NewsFocusStateStore:
    """third 私有 Redis 中的目录快照与源健康状态；Redis 不可用时自动降级。"""

    _process_catalog: list[FeedSource] = []

    def __init__(self, redis_url: str) -> None:
        self._client: Any | None = None
        try:
            from redis import Redis

            self._client = Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=0.5, socket_timeout=0.5)
        except Exception:
            self._client = None

    def catalog(self) -> list[FeedSource]:
        if self._client is not None:
            try:
                rows = decode_snapshot(self._client.get(CATALOG_CACHE_KEY))
                if rows:
                    self._process_catalog = rows
                    return rows
            except Exception:
                pass
        return list(self._process_catalog)

    def save_catalog(self, sources: list[FeedSource]) -> None:
        self._process_catalog = list(sources)
        if self._client is not None:
            try:
                self._client.set(CATALOG_CACHE_KEY, encode_snapshot(sources))
            except Exception:
                pass

    def source_available(self, feed_url: str, now: datetime) -> bool:
        state = self._health_state(feed_url)
        until = _iso_datetime(state.get("retryAfter")) if isinstance(state, dict) else None
        return until is None or until <= now

    def source_succeeded(self, feed_url: str) -> None:
        self._set_health_state(feed_url, None)

    def source_failed(self, feed_url: str, now: datetime) -> None:
        state = self._health_state(feed_url)
        failures = int(state.get("failures", 0)) + 1 if isinstance(state, dict) else 1
        payload: dict[str, Any] = {"failures": failures}
        if failures >= 2:
            minutes = min(12 * 60, 5 * (2 ** min(8, failures - 2)))
            payload["retryAfter"] = (now + timedelta(minutes=minutes)).isoformat()
        self._set_health_state(feed_url, payload)

    def _health_key(self, feed_url: str) -> str:
        return "news-focus:source-health:" + hashlib.sha256(feed_url.encode("utf-8")).hexdigest()

    def _health_state(self, feed_url: str) -> dict[str, Any]:
        if self._client is None:
            return {}
        try:
            value = self._client.get(self._health_key(feed_url))
            parsed = json.loads(value) if value else {}
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _set_health_state(self, feed_url: str, state: dict[str, Any] | None) -> None:
        if self._client is None:
            return
        try:
            key = self._health_key(feed_url)
            if state is None:
                self._client.delete(key)
            else:
                self._client.set(key, json.dumps(state, ensure_ascii=False), ex=24 * 60 * 60)
        except Exception:
            pass


class PublicNewsCollector:
    """仅请求来源 RSS/Atom；绝不访问候选文章的 source_url。"""

    def __init__(self, client: httpx.AsyncClient, state: NewsFocusStateStore, now: datetime) -> None:
        self.client = client
        self.state = state
        self.now = now

    async def collect(self, sources: Iterable[FeedSource]) -> tuple[list[Candidate], list[str], int]:
        source_list = list(sources)
        semaphore = asyncio.Semaphore(SOURCE_CONCURRENCY)
        skipped = 0

        async def fetch(source: FeedSource) -> tuple[list[Candidate], str | None, bool]:
            if not self.state.source_available(source.feed_url, self.now):
                return [], None, True
            try:
                async with semaphore:
                    response = await self.client.get(source.feed_url, headers={"Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml", "User-Agent": "for-mygirl-news-focus/2.0"})
                response.raise_for_status()
                self.state.source_succeeded(source.feed_url)
                return self._entries(source, response.text), None, False
            except Exception as exc:
                self.state.source_failed(source.feed_url, self.now)
                return [], f"RSS {source.name}: {str(exc)[:160]}", False

        results = await asyncio.gather(*(fetch(source) for source in source_list))
        candidates: list[Candidate] = []
        errors: list[str] = []
        for rows, error, was_skipped in results:
            candidates.extend(rows)
            skipped += int(was_skipped)
            if error and len(errors) < MAX_REPORTED_ERRORS:
                errors.append(error)
        if skipped:
            errors.append(f"{skipped} 个连续失败来源处于退避期。")
        return candidates, errors, len(source_list)

    def _entries(self, source: FeedSource, body: str) -> list[Candidate]:
        rows: list[Candidate] = []
        for entry in _parse_feed_entries(body)[:MAX_PER_FEED]:
            published_at = _feed_datetime(entry)
            source_url = str(entry.get("link") or "")
            title = _clean_text(entry.get("title"), 300)
            if not published_at or not source_url or not title:
                continue
            candidate_id = "rss-" + hashlib.sha256(f"{source.feed_url}|{source_url}".encode("utf-8")).hexdigest()[:20]
            rows.append(Candidate(
                candidate_id=candidate_id,
                source=source.name,
                source_url=source_url,
                title=title,
                snippet=_clean_text(entry.get("summary") or entry.get("description"), 700),
                published_at=published_at,
                source_labels=source.labels,
            ))
        return rows


async def refresh_news_focus_catalog(
    config: ThirdServiceConfig | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """显式刷新固定提交的 OPML 快照；日榜任务不会主动更新已存在的快照。"""
    active_config = config or load_config()
    timeout = httpx.Timeout(15.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, transport=transport) as client:
        sources, errors = await import_snapshot(client)
    if not sources:
        raise NewsFocusGenerationError("RSS 目录快照没有导入到可用来源。")
    NewsFocusStateStore(active_config.redis_url).save_catalog(sources)
    return {"sourceCount": len(sources), "sourceErrors": errors}


async def generate_news_focus(
    recent_fingerprints: Iterable[str] | None = None,
    hours: int = PRIMARY_HOURS,
    now: datetime | None = None,
    config: ThirdServiceConfig | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    llm: Any | None = None,
    catalog_sources: Iterable[FeedSource] | None = None,
    state_store: NewsFocusStateStore | None = None,
) -> dict[str, Any]:
    """从目录快照收集近时段元数据，按四类调用既有 LLM 编辑中文结果。"""
    generated_at = now or datetime.now(timezone.utc)
    active_config = config or load_config()
    state = state_store or NewsFocusStateStore(active_config.redis_url)
    timeout = httpx.Timeout(SOURCE_TIMEOUT_SECONDS, connect=3.0)
    limits = httpx.Limits(max_connections=SOURCE_CONCURRENCY, max_keepalive_connections=SOURCE_CONCURRENCY)
    async with httpx.AsyncClient(timeout=timeout, limits=limits, follow_redirects=True, transport=transport) as client:
        source_errors: list[str] = []
        sources = list(catalog_sources) if catalog_sources is not None else state.catalog()
        if not sources:
            sources, import_errors = await import_snapshot(client)
            source_errors.extend(import_errors)
            if sources:
                state.save_catalog(sources)
        if not sources:
            raise NewsFocusGenerationError("RSS 来源目录为空，无法生成每日热门。")
        collector = PublicNewsCollector(client, state, generated_at)
        collected, collect_errors, source_count = await collector.collect(sources)
    source_errors.extend(collect_errors)
    grouped, candidate_count = group_candidates(collected, generated_at, hours, recent_fingerprints or [])
    if not any(grouped.values()):
        return _empty_result(generated_at, source_count, candidate_count, source_errors)

    async def rank(category_key: str) -> tuple[str, list[dict[str, Any]], str | None]:
        candidates = grouped[category_key]
        if not candidates:
            return category_key, [], None
        try:
            model = llm or create_chat_openai(active_config, active_config.workflowagent_model, temperature=0)
            response = await asyncio.to_thread(model.invoke, _ranking_prompt(category_key, candidates))
            return category_key, select_ranked_items(candidates, str(getattr(response, "content", response) or "")), None
        except Exception as exc:
            return category_key, [], f"LLM {CATEGORY_TITLES[category_key]}: {str(exc)[:180]}"

    ranked = await asyncio.gather(*(rank(key) for key in CATEGORY_ORDER))
    groups: list[dict[str, Any]] = []
    for category_key, items, error in ranked:
        if error:
            source_errors.append(error)
        groups.append({"key": category_key, "title": CATEGORY_TITLES[category_key], "items": items})
    if not any(group["items"] for group in groups):
        raise NewsFocusGenerationError("每日热门模型没有返回符合契约的条目。")
    return {
        "generatedAt": generated_at.isoformat(),
        "sourceCount": source_count,
        "candidateCount": candidate_count,
        "sourceErrors": source_errors[:MAX_REPORTED_ERRORS],
        "groups": groups,
    }


def group_candidates(
    candidates: Iterable[Candidate],
    now: datetime,
    hours: int,
    recent_fingerprints: Iterable[str],
) -> tuple[dict[str, list[Candidate]], int]:
    """全局 URL/标题去重，再按分类优先近 24 小时并在不足时扩到 72 小时。"""
    # 每类始终先使用近 24 小时；不足五条时才从同一批近 72 小时候选补齐。
    maximum_hours = FALLBACK_HOURS
    filtered = filter_candidates(candidates, now, maximum_hours, recent_fingerprints)
    all_groups: dict[str, list[Candidate]] = {key: [] for key in CATEGORY_ORDER}
    for candidate in filtered:
        category = classify_candidate(candidate)
        if category:
            all_groups[category].append(candidate)
    for category in CATEGORY_ORDER:
        rows = sorted(all_groups[category], key=lambda item: item.published_at, reverse=True)
        current = [item for item in rows if item.published_at >= now - timedelta(hours=PRIMARY_HOURS)]
        fallback = [item for item in rows if item.published_at < now - timedelta(hours=PRIMARY_HOURS)]
        all_groups[category] = (current + fallback)[:MAX_LLM_CANDIDATES_PER_CATEGORY]
    return all_groups, len(filtered)


def filter_candidates(candidates: Iterable[Candidate], now: datetime, hours: int, recent_fingerprints: Iterable[str]) -> list[Candidate]:
    """按时间、URL、标题和 7 日展示指纹过滤，不访问候选链接。"""
    since = now - timedelta(hours=max(1, min(hours, FALLBACK_HOURS)))
    seen = {str(item) for item in recent_fingerprints if str(item).strip()}
    urls: dict[str, Candidate] = {}
    titles: set[str] = set()
    for candidate in sorted(candidates, key=lambda item: item.published_at, reverse=True):
        canonical = _canonical_url(candidate.source_url)
        title_key = _dedupe_key(candidate.title)
        if not candidate.title or not canonical or candidate.published_at < since or title_key in seen:
            continue
        if canonical in urls or title_key in titles:
            continue
        urls[canonical] = candidate
        titles.add(title_key)
    return list(urls.values())


def classify_candidate(candidate: Candidate) -> str | None:
    labels = " ".join(candidate.source_labels).casefold()
    text = f"{candidate.title} {candidate.snippet}".casefold()
    if "china_focus" in labels:
        return "china_focus"
    if _contains(text, EXCLUDED_POLITICS_KEYWORDS):
        return None
    if _contains(text, AI_KEYWORDS) or _contains(labels, AI_KEYWORDS):
        return "ai"
    if _contains(text, OPEN_SOURCE_KEYWORDS) or _contains(labels, ("programming", "backend", "dev", "tech teams", "web frontend", "开源")):
        return "open_source"
    if _contains(text, NEWS_KEYWORDS) or _contains(labels, ("news", "country")):
        return "news"
    return None


def select_ranked_items(candidates: list[Candidate], llm_content: str) -> list[dict[str, Any]]:
    """校验模型 JSON，按模型返回顺序和主题键去重，且不接受任何数值评分。"""
    parsed = _parse_json_object(llm_content)
    rows = parsed.get("items") if isinstance(parsed, dict) else None
    if not isinstance(rows, list):
        raise NewsFocusGenerationError("每日热门模型输出缺少 items 数组。")
    source_by_id = {item.candidate_id: item for item in candidates}
    topics: set[str] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        candidate = source_by_id.get(str(row.get("id") or ""))
        title = _clean_text(row.get("titleZh"), 160)
        summary = _clean_text(row.get("summaryZh"), 360)
        if not candidate or not title or not summary:
            continue
        topic = _topic_key(row.get("topicKey"), title)
        if topic in topics:
            continue
        topics.add(topic)
        tags = [_clean_text(tag, 24) for tag in row.get("tags", []) if _clean_text(tag, 24)][:4] if isinstance(row.get("tags"), list) else []
        result.append({
            "rank": len(result) + 1,
            "title": title,
            "summary": summary,
            "tags": tags,
            "source": candidate.source,
            "sourceUrl": candidate.source_url,
            "publishedAt": candidate.published_at.isoformat(),
            "dedupeKey": _dedupe_key(candidate.title),
        })
        if len(result) == MAX_ITEMS_PER_CATEGORY:
            break
    return result


def _ranking_prompt(category_key: str, candidates: list[Candidate]) -> str:
    payload = [{
        "id": item.candidate_id,
        "source": item.source,
        "title": item.title,
        "snippet": _clean_text(item.snippet, 480),
        "publishedAt": item.published_at.isoformat(),
    } for item in candidates]
    focus = "优先国家层面的政策、宏观经济、科技产业、公共事件与重要民生进展；排除普通社会琐事、评论和重复报道。" if category_key == "china_focus" else ""
    return (
        f"你是中文信息编辑。请只依据以下公开 RSS 元数据，为‘{CATEGORY_TITLES[category_key]}’挑选最多 5 条值得关注的信息。"
        + focus
        + "不得补充或声称阅读过原文页面；不返回分数。仅返回一个合法 JSON 对象，不要 Markdown。"
        "JSON 形状为："
        '{"items":[{"id":"候选 id","titleZh":"简明中文标题","summaryZh":"中文摘要，不超过120字，说明事实与价值","tags":["最多4个中文标签"],"topicKey":"用于同主题去重的简短中文键"}]}。'
        "每个 id 最多出现一次，不能输出候选以外的 id。候选数据如下：\n" + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )


def _empty_result(generated_at: datetime, source_count: int, candidate_count: int, errors: list[str]) -> dict[str, Any]:
    return {
        "generatedAt": generated_at.isoformat(),
        "sourceCount": source_count,
        "candidateCount": candidate_count,
        "sourceErrors": errors[:MAX_REPORTED_ERRORS],
        "groups": [{"key": key, "title": CATEGORY_TITLES[key], "items": []} for key in CATEGORY_ORDER],
    }


def _contains(text: str, keywords: Iterable[str]) -> bool:
    return any(keyword.casefold() in text for keyword in keywords)


def _parse_json_object(content: str) -> dict[str, Any]:
    normalized = content.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", normalized, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        normalized = fenced.group(1)
    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise NewsFocusGenerationError("每日热门模型输出不是合法 JSON。") from exc
    if not isinstance(parsed, dict):
        raise NewsFocusGenerationError("每日热门模型输出必须是 JSON 对象。")
    return parsed


def _canonical_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""
    query = urlencode(sorted((key, item) for key, item in parse_qsl(parsed.query, keep_blank_values=True) if not key.lower().startswith("utm_")))
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower().removeprefix("www."), parsed.path.rstrip("/"), query, ""))


def _dedupe_key(title: str) -> str:
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", "", title.casefold())[:360]
    return "title:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _timestamp_datetime(value: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _feed_datetime(entry: dict[str, str]) -> datetime | None:
    for key in ("published", "updated", "pubDate", "pubdate", "date"):
        value = entry.get(key)
        if not value:
            continue
        parsed = _iso_datetime(value)
        if parsed:
            return parsed
        try:
            parsed = parsedate_to_datetime(value)
            return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError, IndexError):
            continue
    return None


def _parse_feed_entries(body: str) -> list[dict[str, str]]:
    try:
        root = element_tree.fromstring(body)
    except element_tree.ParseError:
        return []
    entries: list[dict[str, str]] = []
    for node in [*root.findall(".//item"), *root.findall("{http://www.w3.org/2005/Atom}entry")]:
        entry: dict[str, str] = {}
        for child in list(node):
            name = child.tag.rsplit("}", 1)[-1]
            if name == "link":
                href = child.attrib.get("href") or child.text or ""
                if href and (not entry.get("link") or child.attrib.get("rel", "alternate") == "alternate"):
                    entry["link"] = href.strip()
            elif child.text:
                entry[name] = child.text.strip()
        entries.append(entry)
    return entries


def _clean_text(value: Any, limit: int) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit].strip()


def _topic_key(value: Any, title: str) -> str:
    return re.sub(r"\s+", "", _clean_text(value, 60) or title).casefold()[:60]
