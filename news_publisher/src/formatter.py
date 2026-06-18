import logging
from datetime import datetime
from typing import Optional

import pytz

from src.fetcher import Article

log = logging.getLogger(__name__)


class MessageFormatter:
    """Formats translated articles for WhatsApp and Facebook."""

    def __init__(self, config: dict):
        self.wa_cfg = config["formatting"]["whatsapp"]
        self.fb_fmt_cfg = config["formatting"]["facebook"]
        self.fb_cfg = config["facebook"]

    # ------------------------------------------------------------------ public

    def format_for_whatsapp(self, article: Article) -> str:
        cfg = self.wa_cfg
        tz = pytz.timezone(cfg.get("timezone", "Asia/Kolkata"))

        title = article.translated_title or article.title
        summary = article.translated_summary or article.summary

        max_summ = cfg.get("max_summary_chars", 500)
        if len(summary) > max_summ:
            summary = summary[:max_summ].rstrip() + "…"

        if cfg.get("include_publish_time") and article.published_at:
            dt_local = article.published_at.astimezone(tz)
        else:
            dt_local = datetime.now(tz)
        time_str = dt_local.strftime(cfg.get("date_format", "%d %B %Y, %I:%M %p"))

        header = cfg.get("header_emoji", "\U0001f4f0")
        footer = cfg.get("footer_emoji", "\U0001f517")
        sep = cfg.get("separator", "─" * 17)

        lines = [f"{header} *{title}*"]

        if summary and cfg.get("include_summary", True):
            lines.append("")
            lines.append(summary)

        meta_parts = []
        if cfg.get("include_source_name") and article.source_name:
            meta_parts.append(f"\U0001f4cc {article.source_name}")
        if cfg.get("include_publish_time"):
            meta_parts.append(time_str)
        if cfg.get("include_category_tag") and article.category:
            meta_parts.append(f"#{article.category}")

        if meta_parts:
            lines.append("")
            lines.append(sep)
            lines.append("  |  ".join(meta_parts))

        if cfg.get("include_url") and article.url:
            lines.append(f"{footer} {article.url}")

        message = "\n".join(lines)
        max_len = cfg.get("max_message_length", 4096)
        if len(message) > max_len:
            message = message[: max_len - 1] + "…"
        return message

    def format_for_facebook(self, article: Article) -> dict:
        cfg = self.fb_fmt_cfg

        title = article.translated_title or article.title
        summary = article.translated_summary or article.summary

        header = cfg.get("header_emoji", "\U0001f4f0")

        hashtags_list = list(cfg.get("default_hashtags", []))
        if cfg.get("add_hashtags"):
            cat_tags = cfg.get("category_hashtags", {}).get(article.category, [])
            hashtags_list.extend(cat_tags)
        hashtag_str = " ".join(dict.fromkeys(hashtags_list))  # dedupe, preserve order

        lines = [f"{header} {title}"]
        if summary:
            lines.append("")
            lines.append(summary)
        if hashtag_str and cfg.get("add_hashtags"):
            lines.append("")
            lines.append(hashtag_str)

        message = "\n".join(lines)
        max_len = cfg.get("max_post_length", 63206)
        if len(message) > max_len:
            message = message[: max_len - 1] + "…"

        post: dict = {"message": message}

        if cfg.get("include_url_in_post") and article.url:
            post["link"] = article.url

        if cfg.get("include_image_url") and article.image_url and not article.url:
            post["picture"] = article.image_url

        return post
