import logging
import time
from typing import List, Optional

import requests

from src.fetcher import Article

log = logging.getLogger(__name__)


class Translator:
    """Translates article titles and summaries to Marathi."""

    def __init__(self, config: dict):
        self.cfg = config["translation"]
        self.service = self.cfg.get("service", "google_free")
        self.target = self.cfg.get("target_language", "mr")
        self.source = self.cfg.get("source_language", "auto")
        self.session = requests.Session()

    # ------------------------------------------------------------------ public

    def translate_articles(self, articles: List[Article]) -> List[Article]:
        if not self.cfg.get("enabled", True):
            for art in articles:
                art.translated_title = art.title
                art.translated_summary = art.summary
            return articles

        delay = self.cfg.get("google_free", {}).get("delay_between_requests_seconds", 0.5)

        for art in articles:
            # Skip if the source is already Marathi
            if self.cfg.get("skip_already_marathi") and art.language == "mr":
                art.translated_title = art.title
                art.translated_summary = art.summary
                continue

            try:
                if self.cfg.get("translate_title", True) and art.title:
                    art.translated_title = self._translate(art.title)
                    time.sleep(delay)

                if self.cfg.get("translate_summary", True) and art.summary:
                    max_chars = self.cfg.get("max_chars_per_request", 5000)
                    art.translated_summary = self._translate(art.summary[:max_chars])
                    time.sleep(delay)

                log.debug("Translated: %s", (art.translated_title or "")[:60])

            except Exception as exc:
                log.error("Translation failed for '%s': %s", art.title[:50], exc)
                if self.cfg.get("fallback_to_original_on_error", True):
                    art.translated_title = art.translated_title or art.title
                    art.translated_summary = art.translated_summary or art.summary

        return articles

    # ----------------------------------------------------------------- private

    def _translate(self, text: str) -> str:
        if not text or not text.strip():
            return text
        if self.service == "google_free":
            return self._google_free(text)
        if self.service == "google_cloud":
            return self._google_cloud(text)
        if self.service == "deepl":
            return self._deepl(text)
        raise ValueError(f"Unknown translation service: {self.service}")

    def _google_free(self, text: str) -> str:
        """Unofficial free endpoint — good for low-volume use."""
        cfg = self.cfg.get("google_free", {})
        endpoint = cfg.get("endpoint", "https://translate.googleapis.com/translate_a/single")
        params = {
            "client": "gtx",
            "sl": self.source if self.source != "auto" else "auto",
            "tl": self.target,
            "dt": "t",
            "q": text,
        }
        resp = self.session.get(endpoint, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return "".join(part[0] for part in data[0] if part[0])

    def _google_cloud(self, text: str) -> str:
        cfg = self.cfg["google_cloud"]
        endpoint = cfg.get("endpoint", "https://translation.googleapis.com/language/translate/v2")
        payload: dict = {
            "q": text,
            "target": self.target,
            "format": "text",
        }
        if self.source and self.source != "auto":
            payload["source"] = self.source
        resp = self.session.post(
            endpoint, params={"key": cfg["api_key"]}, json=payload, timeout=10
        )
        resp.raise_for_status()
        return resp.json()["data"]["translations"][0]["translatedText"]

    def _deepl(self, text: str) -> str:
        cfg = self.cfg["deepl"]
        headers = {"Authorization": f"DeepL-Auth-Key {cfg['api_key']}"}
        payload: dict = {"text": [text], "target_lang": self.target.upper()}
        if self.source and self.source != "auto":
            payload["source_lang"] = self.source.upper()
        resp = self.session.post(cfg["api_url"], headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()["translations"][0]["text"]
