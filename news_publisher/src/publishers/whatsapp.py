import logging
import time
from typing import List

import requests

from src.fetcher import Article

log = logging.getLogger(__name__)


class WhatsAppPublisher:
    """
    Sends messages via WhatsApp.

    Supported providers:
      - meta   : Meta WhatsApp Cloud API (official)
      - twilio : Twilio WhatsApp sandbox / production

    NOTE: The WhatsApp Business API does not allow sending messages directly
    into Groups. Use recipient_numbers to broadcast to individual contacts
    (all members of your group). Each contact must have opted-in first.
    """

    def __init__(self, config: dict):
        self.wa_cfg = config["whatsapp"]
        self.provider = self.wa_cfg.get("provider", "meta")
        self.session = requests.Session()

    # ------------------------------------------------------------------ public

    def publish(self, message: str, article: Article) -> bool:
        if not self.wa_cfg.get("enabled", False):
            log.info("WhatsApp publishing disabled in config")
            return False

        if self.provider == "meta":
            return self._send_meta(message)
        if self.provider == "twilio":
            return self._send_twilio(message)

        log.error("Unknown WhatsApp provider: %s", self.provider)
        return False

    # ----------------------------------------------------------------- private

    def _send_meta(self, message: str) -> bool:
        cfg = self.wa_cfg["meta"]
        url = (
            f"{cfg.get('base_url', 'https://graph.facebook.com')}"
            f"/{cfg.get('api_version', 'v18.0')}"
            f"/{cfg['phone_number_id']}/messages"
        )
        headers = {
            "Authorization": f"Bearer {cfg['access_token']}",
            "Content-Type": "application/json",
        }
        rate_delay = self.wa_cfg.get("rate_limit", {}).get("delay_between_recipients_seconds", 2)
        max_retries = cfg.get("max_retries", 3)
        retry_delay = cfg.get("retry_delay_seconds", 5)

        success = 0
        for recipient in cfg.get("recipient_numbers", []):
            payload = {
                "messaging_product": "whatsapp",
                "to": recipient.lstrip("+").replace(" ", ""),
                "type": "text",
                "text": {"preview_url": False, "body": message},
            }
            for attempt in range(max_retries):
                try:
                    resp = self.session.post(url, headers=headers, json=payload, timeout=15)
                    resp.raise_for_status()
                    log.info("WhatsApp (Meta) sent to %s", recipient)
                    success += 1
                    break
                except Exception as exc:
                    log.error("WhatsApp Meta attempt %d/%d failed: %s", attempt + 1, max_retries, exc)
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
            time.sleep(rate_delay)

        return success > 0

    def _send_twilio(self, message: str) -> bool:
        try:
            from twilio.rest import Client  # type: ignore
        except ImportError:
            log.error("Twilio SDK not installed. Run: pip install twilio")
            return False

        cfg = self.wa_cfg["twilio"]
        client = Client(cfg["account_sid"], cfg["auth_token"])
        rate_delay = self.wa_cfg.get("rate_limit", {}).get("delay_between_recipients_seconds", 2)
        max_retries = cfg.get("max_retries", 3)
        retry_delay = cfg.get("retry_delay_seconds", 5)

        success = 0
        for to_num in cfg.get("to_numbers", []):
            for attempt in range(max_retries):
                try:
                    client.messages.create(
                        from_=cfg["from_number"],
                        to=to_num,
                        body=message,
                    )
                    log.info("WhatsApp (Twilio) sent to %s", to_num)
                    success += 1
                    break
                except Exception as exc:
                    log.error("WhatsApp Twilio attempt %d/%d failed: %s", attempt + 1, max_retries, exc)
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
            time.sleep(rate_delay)

        return success > 0
