import logging
import time

import requests

from src.fetcher import Article

log = logging.getLogger(__name__)


class FacebookPublisher:
    """Posts translated news articles to a Facebook Page via the Graph API."""

    def __init__(self, config: dict):
        self.fb_cfg = config["facebook"]
        self.session = requests.Session()

    # ------------------------------------------------------------------ public

    def publish(self, post_data: dict, article: Article) -> bool:
        if not self.fb_cfg.get("enabled", False):
            log.info("Facebook publishing disabled in config")
            return False

        url = (
            f"{self.fb_cfg.get('base_url', 'https://graph.facebook.com')}"
            f"/{self.fb_cfg.get('api_version', 'v18.0')}"
            f"/{self.fb_cfg['page_id']}/feed"
        )
        payload = {**post_data, "access_token": self.fb_cfg["access_token"]}
        max_retries = self.fb_cfg.get("max_retries", 3)
        retry_delay = self.fb_cfg.get("retry_delay_seconds", 5)

        for attempt in range(max_retries):
            try:
                resp = self.session.post(url, data=payload, timeout=15)
                resp.raise_for_status()
                post_id = resp.json().get("id", "unknown")
                log.info("Facebook post published: %s", post_id)
                return True
            except Exception as exc:
                log.error("Facebook attempt %d/%d failed: %s", attempt + 1, max_retries, exc)
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)

        return False
