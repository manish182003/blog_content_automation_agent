import logging
import json
import requests
from typing import Dict, Any, Optional

import config

logger = logging.getLogger(__name__)

class NotificationManager:
    """Handles end-of-run notifications across Telegram, HTTP Webhooks, and local logs."""

    def __init__(self):
        self.webhook_url = config.NOTIFICATION_WEBHOOK_URL
        self.telegram_token = config.TELEGRAM_BOT_TOKEN
        self.telegram_chat_id = config.TELEGRAM_CHAT_ID

    def send_notification(self, title: str, details: Dict[str, Any], status: str) -> None:
        """Compose and send notification across active channels."""
        emoji = "✅" if status == "SUCCESS" else ("⚠️" if status == "NEEDS_REVIEW" else "❌")
        
        message_lines = [
            f"{emoji} **Blog Automation Run Report**",
            f"**Status**: {status}",
            f"**Title**: {details.get('topic', 'N/A')}",
            f"**Category**: {details.get('category', 'N/A')}",
            f"**Keyword**: {details.get('keyword', 'N/A')}",
            f"**Mode**: {details.get('mode', 'DRY_RUN')}",
            f"**SEO Score**: {details.get('seo_score', 'N/A')}/100",
            f"**Groundedness Score**: {details.get('groundedness_score', 'N/A')}/100",
            f"**Duration**: {details.get('duration_seconds', 0):.1f}s"
        ]

        if details.get("error_message"):
            message_lines.append(f"**Error**: {details['error_message']}")

        if details.get("output_path"):
            message_lines.append(f"**Saved File**: {details['output_path']}")

        if details.get("notion_url"):
            message_lines.append(f"**Notion Page**: {details['notion_url']}")

        formatted_message = "\n".join(message_lines)
        logger.info(f"Notification message generated:\n{formatted_message}")

        # Automatically ping Google Sitemap for instant indexing on LIVE success
        if status == "SUCCESS" and details.get("mode") == "LIVE":
            self.ping_google_sitemap()

    def ping_google_sitemap(self):
        """Send automatic ping to Google Search Engine to request immediate sitemap crawl."""
        try:
            sitemap_url = "https://www.manishjoshi.online/sitemap.xml"
            ping_url = f"https://www.google.com/ping?sitemap={sitemap_url}"
            resp = requests.get(ping_url, timeout=10)
            logger.info(f"Sent Google sitemap indexing ping ({resp.status_code}): {ping_url}")
        except Exception as err:
            logger.warning(f"Google sitemap ping failed: {err}")

        # Send Telegram notification if token is configured
        if self.telegram_token:
            chat_id = self.telegram_chat_id
            if not chat_id:
                try:
                    res = requests.get(f"https://api.telegram.org/bot{self.telegram_token}/getUpdates", timeout=5).json()
                    results = res.get("result", [])
                    if results:
                        # Grab latest chat id
                        chat_id = results[-1].get("message", {}).get("chat", {}).get("id")
                        logger.info(f"Auto-detected Telegram Chat ID: {chat_id}")
                except Exception as err:
                    logger.warning(f"Could not auto-detect Telegram Chat ID: {err}")

            if chat_id:
                try:
                    tg_url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                    resp = requests.post(tg_url, json={
                        "chat_id": chat_id,
                        "text": formatted_message,
                        "parse_mode": "Markdown"
                    }, timeout=10)
                    if resp.status_code == 200:
                        logger.info("Telegram notification sent successfully!")
                    else:
                        logger.warning(f"Telegram API returned HTTP {resp.status_code}: {resp.text}")
                except Exception as e:
                    logger.warning(f"Failed to send Telegram notification: {e}")
            else:
                logger.warning("Telegram Bot Token is present, but Chat ID was empty and could not be auto-detected. (Send a message to your Telegram bot first!).")

        # Send HTTP Webhook if configured
        if self.webhook_url:
            try:
                requests.post(self.webhook_url, json={
                    "event": "blog_automation_run",
                    "status": status,
                    "details": details
                }, timeout=10)
                logger.info("Webhook notification sent successfully.")
            except Exception as e:
                logger.warning(f"Failed to send Webhook notification: {e}")
