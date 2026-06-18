import logging

from src.deduplicator import Deduplicator
from src.fetcher import NewsFetcher
from src.formatter import MessageFormatter
from src.publishers.facebook import FacebookPublisher
from src.publishers.whatsapp import WhatsAppPublisher
from src.translator import Translator

log = logging.getLogger(__name__)


class NewsPipeline:
    """
    Orchestrates the full pipeline:
      Fetch  →  Deduplicate  →  Translate  →  Format  →  Publish
    """

    def __init__(self, config: dict, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run
        self.fetcher = NewsFetcher(config)
        self.dedup = Deduplicator(config)
        self.translator = Translator(config)
        self.formatter = MessageFormatter(config)
        self.whatsapp = WhatsAppPublisher(config)
        self.facebook = FacebookPublisher(config)

    def run(self) -> None:
        log.info("=" * 50)
        log.info("Pipeline run started%s", " [DRY RUN]" if self.dry_run else "")

        articles = self.fetcher.fetch_all()
        if not articles:
            log.info("No articles fetched — nothing to do")
            return

        articles = self.dedup.filter_new(articles)
        log.info("%d new articles after deduplication", len(articles))
        if not articles:
            log.info("All articles already published — nothing to do")
            return

        articles = self.translator.translate_articles(articles)

        published = 0
        for article in articles:
            wa_msg = self.formatter.format_for_whatsapp(article)
            fb_post = self.formatter.format_for_facebook(article)

            if self.dry_run:
                log.info("[DRY RUN] %s", article.translated_title or article.title)
                log.info("--- WhatsApp preview ---\n%s\n", wa_msg[:300])
                published += 1
                continue

            wa_ok = self.whatsapp.publish(wa_msg, article)
            fb_ok = self.facebook.publish(fb_post, article)

            if wa_ok or fb_ok:
                self.dedup.mark_published(article.id, article.title)
                published += 1
                log.info("Published: %s", article.translated_title or article.title)
            else:
                log.warning("Failed to publish: %s", article.title)

        log.info("Pipeline complete — %d/%d articles published", published, len(articles))
        log.info("=" * 50)
