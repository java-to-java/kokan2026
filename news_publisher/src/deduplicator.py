import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import List

from src.fetcher import Article

log = logging.getLogger(__name__)


class Deduplicator:
    """
    Tracks which articles have already been published so we never
    send the same story twice within the configured window.
    """

    def __init__(self, config: dict):
        self.cfg = config["storage"]
        self.enabled = self.cfg.get("dedup_enabled", True)
        self.db_file = self.cfg.get("published_db_file", "data/published_articles.json")
        self.window_hours = self.cfg.get("dedup_window_hours", 48)
        self.max_entries = self.cfg.get("max_db_entries", 10_000)
        self._db: dict = self._load()

    # ------------------------------------------------------------------ public

    def filter_new(self, articles: List[Article]) -> List[Article]:
        if not self.enabled:
            return articles
        return [a for a in articles if a.id not in self._db]

    def mark_published(self, article_id: str, title: str = "") -> None:
        self._db[article_id] = {
            "published_at": datetime.now(timezone.utc).isoformat(),
            "title": title,
        }
        self._trim()
        self._save()

    # ----------------------------------------------------------------- private

    def _load(self) -> dict:
        if not self.enabled or not os.path.exists(self.db_file):
            return {}
        try:
            with open(self.db_file, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception as exc:
            log.warning("Could not load dedup DB (%s): %s", self.db_file, exc)
            return {}

    def _save(self) -> None:
        if not self.enabled:
            return
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
        with open(self.db_file, "w", encoding="utf-8") as fh:
            json.dump(self._db, fh, indent=2, ensure_ascii=False)

    def _trim(self) -> None:
        if len(self._db) <= self.max_entries:
            return
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.window_hours)
        stale = [
            k for k, v in self._db.items()
            if datetime.fromisoformat(v["published_at"]) < cutoff
        ]
        for k in stale:
            del self._db[k]
        log.debug("Dedup DB trimmed %d stale entries", len(stale))
