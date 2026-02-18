"""
Echorouk AI Swarm - Notification Service.
Multi-channel notifications (Telegram/Slack) with newsroom rules.
"""

import html
import re
from typing import Optional

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.settings_service import settings_service

logger = get_logger("notification_service")
settings = get_settings()


class NotificationService:
    """Send alerts to editorial team via Telegram/Slack."""

    @staticmethod
    def _clean_text(text: str, max_len: int = 600) -> str:
        if not text:
            return "-"
        normalized = re.sub(r"\s+", " ", text).strip()
        return html.escape(normalized[:max_len])

    @staticmethod
    def _category_label(category: str) -> str:
        labels = {
            "local_algeria": "محلي - الجزائر",
            "international": "دولي",
            "politics": "سياسة",
            "economy": "اقتصاد",
            "sports": "رياضة",
            "technology": "تكنولوجيا",
            "health": "صحة",
            "culture": "ثقافة",
            "environment": "بيئة",
            "society": "مجتمع",
            "general": "عام",
        }
        return labels.get((category or "").strip().lower(), category or "عام")

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
            "text": message[:4096],
            "parse_mode": parse_mode,
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    logger.info("telegram_sent", channel=chat_id)
                    return True
                logger.error("telegram_error", status=resp.status_code, body=resp.text)
                return False
        except Exception as e:
            logger.error("telegram_exception", error=str(e))
            return False

    async def send_slack(self, message: str, blocks: list | None = None) -> bool:
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
        """Send breaking news alerts (Telegram + Slack)."""
        safe_title = self._clean_text(title, 300)
        safe_summary = self._clean_text(summary, 700)
        safe_source = self._clean_text(source, 120)
        message = (
            f"🚨 <b>خبر عاجل</b>\n\n"
            f"<b>{safe_title}</b>\n\n"
            f"{safe_summary}\n\n"
            f"📰 المصدر: {safe_source}\n"
            f"🔗 <a href=\"{url}\">قراءة الخبر</a>"
        )

        channel_alerts = await settings_service.get_value(
            "TELEGRAM_CHANNEL_ALERTS",
            settings.telegram_channel_alerts,
        )
        channel_editors = await settings_service.get_value(
            "TELEGRAM_CHANNEL_EDITORS",
            settings.telegram_channel_editors,
        )

        telegram_targets: list[str] = []
        if channel_alerts:
            telegram_targets.append(channel_alerts)
        if channel_editors and channel_editors not in telegram_targets:
            telegram_targets.append(channel_editors)

        for channel in telegram_targets:
            await self.send_telegram(message, channel=channel)
        await self.send_slack(f"خبر عاجل: {title}\n{summary}\nالمصدر: {source}")

    async def send_candidate_for_review(
        self,
        article_id: int,
        title: str,
        summary: str,
        source: str,
        importance: int,
        category: str,
    ):
        """Candidate reviews are in-app/Slack only (no Telegram)."""
        safe_title = self._clean_text(title, 300)
        safe_summary = self._clean_text(summary, 900)
        safe_source = self._clean_text(source, 120)
        category_label = self._category_label(category)
        stars = "★" * min(max(importance // 2, 1), 5)
        message = (
            f"🗞️ <b>خبر مرشح للمراجعة</b> #{article_id}\n\n"
            f"<b>{safe_title}</b>\n\n"
            f"{safe_summary}\n\n"
            f"🏷️ التصنيف: {category_label}\n"
            f"⭐ الأهمية: {stars} ({importance}/10)\n"
            f"📰 المصدر: {safe_source}\n\n"
            f"✅ اعتماد: <code>approve {article_id}</code>\n"
            f"❌ رفض: <code>reject {article_id}</code>\n"
            f"✍️ إعادة صياغة: <code>rewrite {article_id}</code>"
        )
        await self.send_slack(message)

    async def send_daily_report(self, stats: dict):
        """Daily report is Slack only; Telegram reserved for breaking."""
        message = (
            f"📊 <b>التقرير اليومي - غرفة الشروق الذكية</b>\n\n"
            f"📰 إجمالي الأخبار: {stats.get('total', 0)}\n"
            f"🔁 المكررات: {stats.get('duplicates', 0)}\n"
            f"✅ المعتمدة: {stats.get('approved', 0)}\n"
            f"❌ المرفوضة: {stats.get('rejected', 0)}\n"
            f"📤 المنشورة: {stats.get('published', 0)}\n"
            f"🤖 استدعاءات الذكاء: {stats.get('ai_calls', 0)}\n"
            f"⏱️ متوسط المعالجة: {stats.get('avg_time_ms', 0)}ms\n"
            f"⚠️ الأخطاء: {stats.get('errors', 0)}"
        )
        await self.send_slack(message)

    async def send_policy_gate_alert(
        self,
        *,
        article_id: int,
        title: str,
        decision: str,
        reasons: list[str] | None = None,
    ) -> None:
        """
        Notify chief editor queue after editorial policy gate result.
        Telegram remains breaking-only, so this alert goes to Slack.
        """
        safe_title = self._clean_text(title, 300)
        reasons = reasons or []
        compact_reasons = " | ".join(self._clean_text(r, 120) for r in reasons[:3]) if reasons else "-"
        label = "مقبول من وكيل السياسة" if decision == "approved" else "تحفظات من وكيل السياسة"
        message = (
            f"🧭 <b>طلب اعتماد لرئيس التحرير</b>\n\n"
            f"#{article_id} — <b>{safe_title}</b>\n"
            f"الحالة: {label}\n"
            f"التحفظات: {compact_reasons}\n\n"
            f"الإجراء: افتح طابور اعتماد رئيس التحرير."
        )
        await self.send_slack(message)


notification_service = NotificationService()
