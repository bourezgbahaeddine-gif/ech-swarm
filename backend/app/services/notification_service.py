"""
Echorouk AI Swarm - Notification Service
========================================
Multi-channel notification delivery (Telegram, Slack).
"""

import httpx
from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.settings_service import settings_service

logger = get_logger("notification_service")
settings = get_settings()


class NotificationService:
    """Send alerts to editorial team via Telegram/Slack."""

    async def send_telegram(
        self,
        message: str,
        channel: Optional[str] = None,
        parse_mode: str = "HTML",
    ) -> bool:
        """Send a message to Telegram channel."""
        token = await settings_service.get_value("TELEGRAM_BOT_TOKEN", settings.telegram_bot_token)
        if not token:
            logger.warning("telegram_not_configured")
            return False

        chat_id = channel or await settings_service.get_value(
            "TELEGRAM_CHANNEL_EDITORS",
            settings.telegram_channel_editors,
        )
        if not chat_id:
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message[:4096],  # Telegram limit
            "parse_mode": parse_mode,
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    logger.info("telegram_sent", channel=chat_id)
                    return True
                else:
                    logger.error("telegram_error", status=resp.status_code, body=resp.text)
                    return False
        except Exception as e:
            logger.error("telegram_exception", error=str(e))
            return False

    async def send_slack(self, message: str, blocks: list = None) -> bool:
        """Send a message to Slack via webhook."""
        webhook = await settings_service.get_value("SLACK_WEBHOOK_URL", settings.slack_webhook_url)
        if not webhook:
            return False

        payload = {"text": message}
        if blocks:
            payload["blocks"] = blocks

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(webhook, json=payload, timeout=10)
                return resp.status_code == 200
        except Exception as e:
            logger.error("slack_exception", error=str(e))
            return False

    async def send_breaking_alert(self, title: str, summary: str, source: str, url: str):
        """Send a breaking news alert to all channels."""
        message = (
            f"?? <b>????</b>\n\n"
            f"<b>{title}</b>\n\n"
            f"{summary}\n\n"
            f"?? ??????: {source}\n"
            f"?? <a href=\"{url}\">??????</a>"
        )

        channel_alerts = await settings_service.get_value(
            "TELEGRAM_CHANNEL_ALERTS",
            settings.telegram_channel_alerts,
        )
        await self.send_telegram(message, channel=channel_alerts)
        await self.send_slack(f"?? ????: {title}\n{summary}\n??????: {source}")

    async def send_candidate_for_review(
        self,
        article_id: int,
        title: str,
        summary: str,
        source: str,
        importance: int,
        category: str,
    ):
        """Send a candidate article to editors for review."""
        stars = "?" * min(importance, 5)
        message = (
            f"?? <b>??? ????? ?????</b> #{article_id}\n\n"
            f"<b>{title}</b>\n\n"
            f"{summary}\n\n"
            f"?? ?????: {category}\n"
            f"?? ???????: {stars} ({importance}/10)\n"
            f"?? ??????: {source}\n\n"
            f"? ????????: <code>approve {article_id}</code>\n"
            f"? ?????: <code>reject {article_id}</code>\n"
            f"?? ?????? ???????: <code>rewrite {article_id}</code>"
        )

        await self.send_telegram(message)

    async def send_daily_report(self, stats: dict):
        """Send daily pipeline statistics report."""
        message = (
            f"?? <b>????? ???? - ???? ?????? ??????</b>\n\n"
            f"?? ??????? ???????: {stats.get('total', 0)}\n"
            f"?? ??????: {stats.get('duplicates', 0)}\n"
            f"? ??? ????????: {stats.get('approved', 0)}\n"
            f"? ?? ?????: {stats.get('rejected', 0)}\n"
            f"?? ?? ?????: {stats.get('published', 0)}\n"
            f"?? ????????? AI: {stats.get('ai_calls', 0)}\n"
            f"? ????? ????????: {stats.get('avg_time_ms', 0)}ms\n"
            f"?? ?????: {stats.get('errors', 0)}"
        )

        await self.send_telegram(message)


# Singleton
notification_service = NotificationService()
