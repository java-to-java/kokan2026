import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import feedparser
import requests

log = logging.getLogger(__name__)


@dataclass
class Article:
    id: str
    title: str
    summary: str
    url: str
    source_name: str
    language: str
    category: str
    published_at: Optional[datetime] = None
    image_url: Optional[str] = None
    # Filled by Translator
    translated_title: Optional[str] = None
    translated_summary: Optional[str] = None


class NewsFetcher:
    """Fetches articles from RSS feeds and optionally from NewsAPI."""

    def __init__(self, config: dict):
        self.cfg = config["news"]
        self.session = requests.Session()
        self.session.headers["User-Agent"] = self.cfg.get(
            "user_agent", "NewsPublisherBot/1.0"
        )

    # ------------------------------------------------------------------ public

    def fetch_all(self) -> List[Article]:
        articles: List[Article] = []

        for feed in self.cfg.get("rss_feeds", []):
            if not feed.get("enabled", True):
                continue
            try:
                batch = self._fetch_rss(feed)
                log.info("%-40s  fetched %d articles", feed["name"], len(batch))
                articles.extend(batch)
            except Exception as exc:
                log.error("RSS fetch failed [%s]: %s", feed["name"], exc)

        if self.cfg.get("newsapi", {}).get("enabled", False):
            try:
                batch = self._fetch_newsapi()
                log.info("NewsAPI fetched %d articles", len(batch))
                articles.extend(batch)
            except Exception as exc:
                log.error("NewsAPI fetch failed: %s", exc)

        articles = self._filter(articles)
        limit = self.cfg.get("max_articles_per_run", 10)
        articles = articles[:limit]
        log.info("Total articles after filter + limit: %d", len(articles))
        return articles

    # ----------------------------------------------------------------- private

    def _fetch_rss(self, feed_cfg: dict) -> List[Article]:
        timeout = self.cfg.get("fetch_timeout_seconds", 15)
        resp = self.session.get(feed_cfg["url"], timeout=timeout)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
        per_source = self.cfg.get("max_articles_per_source", 5)
        return [
            art
            for entry in parsed.entries[:per_source]
            for art in [self._entry_to_article(entry, feed_cfg)]
            if art is not None
        ]

    def _entry_to_article(self, entry, feed_cfg: dict) -> Optional[Article]:
        title = getattr(entry, "title", "").strip()
        url = getattr(entry, "link", "").strip()
        if not title or not url:
            return None

        summary = re.sub(r"<[^>]+>", "", getattr(entry, "summary", "")).strip()

        published_at: Optional[datetime] = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass

        image_url: Optional[str] = None
        if hasattr(entry, "media_content") and entry.media_content:
            image_url = entry.media_content[0].get("url")
        elif hasattr(entry, "enclosures"):
            for enc in entry.enclosures:
                if (enc.get("type") or "").startswith("image/"):
                    image_url = enc.get("href")
                    break

        return Article(
            id=hashlib.md5(url.encode()).hexdigest(),
            title=title,
            summary=summary,
            url=url,
            source_name=feed_cfg["name"],
            language=feed_cfg.get("language", "en"),
            category=feed_cfg.get("category", "general"),
            published_at=published_at,
            image_url=image_url,
        )

    def _fetch_newsapi(self) -> List[Article]:
        na = self.cfg["newsapi"]
        base_params = {
            "country": na.get("country", "in"),
            "language": na.get("language", "en"),
            "pageSize": na.get("page_size", 10),
            "sortBy": na.get("sort_by", "publishedAt"),
            "apiKey": na["api_key"],
        }
        articles: List[Article] = []
        endpoint = na.get("endpoint", "https://newsapi.org/v2/top-headlines")
        timeout = self.cfg.get("fetch_timeout_seconds", 15)

        for category in na.get("categories", ["general"]):
            try:
                resp = self.session.get(
                    endpoint,
                    params={**base_params, "category": category},
                    timeout=timeout,
                )
                resp.raise_for_status()
                for item in resp.json().get("articles", []):
                    art = self._newsapi_item_to_article(item, category)
                    if art:
                        articles.append(art)
            except Exception as exc:
                log.error("NewsAPI category '%s' failed: %s", category, exc)

        return articles

    def _newsapi_item_to_article(self, item: dict, category: str) -> Optional[Article]:
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        if not title or not url or "[Removed]" in title:
            return None

        published_at: Optional[datetime] = None
        if ts := item.get("publishedAt"):
            try:
                published_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                pass

        return Article(
            id=hashlib.md5(url.encode()).hexdigest(),
            title=title,
            summary=(item.get("description") or "").strip(),
            url=url,
            source_name=(item.get("source") or {}).get("name", "NewsAPI"),
            language="en",
            category=category,
            published_at=published_at,
            image_url=item.get("urlToImage"),
        )

    def _filter(self, articles: List[Article]) -> List[Article]:
        max_age = self.cfg.get("max_article_age_hours", 24)
        min_len = self.cfg.get("min_article_length_chars", 80)
        include_kw = [k.lower() for k in self.cfg.get("keywords_include", [])]
        exclude_kw = [k.lower() for k in self.cfg.get("keywords_exclude", [])]
        enabled_cats = set(self.cfg.get("categories_enabled", []))
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age)

        seen: set = set()
        result: List[Article] = []

        for art in articles:
            if art.id in seen:
                continue
            seen.add(art.id)

            if len(art.summary) < min_len and len(art.title) < 15:
                continue
            if art.published_at and art.published_at < cutoff:
                continue

            text = (art.title + " " + art.summary).lower()
            if include_kw and not any(k in text for k in include_kw):
                continue
            if any(k in text for k in exclude_kw):
                continue
            if enabled_cats and art.category not in enabled_cats:
                continue

            result.append(art)

        return result
