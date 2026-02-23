"""
Echorouk Editorial OS - Notification Service.
Multi-channel notifications (Telegram/Slack) with newsroom rules.
"""

import hashlib
import html
import re
from datetime import timedelta
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.cache_service import cache_service
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
    def _normalize_for_signature(value: str) -> str:
        return re.sub(r"\s+", " ", (value or "").strip().lower())

    @staticmethod
    def _normalize_url_for_signature(url: str) -> str:
        raw = (url or "").strip()
        if not raw:
            return ""
        try:
            parsed = urlparse(raw)
            filtered_query = [
                (k, v)
                for k, v in parse_qsl(parsed.query, keep_blank_values=False)
                if not k.lower().startswith("utm_")
                and k.lower() not in {"fbclid", "gclid", "igshid", "oc", "hl", "gl", "ceid"}
            ]
            normalized = parsed._replace(
                scheme=(parsed.scheme or "https").lower(),
                netloc=parsed.netloc.lower(),
                query=urlencode(filtered_query, doseq=True),
                fragment="",
            )
            return urlunparse(normalized).rstrip("/")
        except Exception:
            return raw.lower().rstrip("/")

    @staticmethod
    def _topic_signature(title: str) -> str:
        normalized = NotificationService._normalize_for_signature(title)
        tokens = re.findall(r"[\u0600-\u06FFa-z0-9]{3,}", normalized)
        stop_words = {
            "هذا",
            "هذه",
            "ذلك",
            "اليوم",
            "عاجل",
            "هام",
            "latest",
            "breaking",
            "news",
            "update",
        }
        filtered = [token for token in tokens if token not in stop_words][:6]
        if not filtered:
            return hashlib.sha1(normalized.encode("utf-8")).hexdigest()
        return hashlib.sha1("|".join(filtered).encode("utf-8")).hexdigest()

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
            f"📊 <b>التقرير اليومي - نظام التشغيل الذكي لسير العمل التحريري</b>\n\n"
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

    async def send_published_quality_alert(self, report: dict) -> None:
        """
        Send Telegram alert when published-content quality monitor detects weak items.
        This is newsroom-critical, so it goes to the alerts channel.
        """
        weak_items = report.get("items", [])
        weak_items = [item for item in weak_items if int(item.get("score", 0)) < int(settings.published_monitor_alert_threshold)]
        if not weak_items:
            return

        # Prevent alert spam by suppressing repeated alerts for the same topic.
        dedup_ttl = timedelta(hours=18)
        topic_ttl = timedelta(hours=8)
        new_weak_items: list[dict] = []
        for item in weak_items:
            normalized_url = self._normalize_url_for_signature(item.get("url", ""))
            normalized_title = self._normalize_for_signature(item.get("title", ""))
            signature_raw = f"{normalized_url}|{normalized_title}"
            signature_hash = hashlib.sha1(signature_raw.encode("utf-8")).hexdigest()
            dedup_key = f"published_quality_alert:item:{signature_hash}"
            already_sent = await cache_service.get(dedup_key)
            if already_sent:
                continue

            topic_hash = self._topic_signature(item.get("title", ""))
            topic_key = f"published_quality_alert:topic:{topic_hash}"
            topic_sent = await cache_service.get(topic_key)
            if topic_sent:
                continue

            await cache_service.set(dedup_key, "1", ttl=dedup_ttl)
            await cache_service.set(topic_key, "1", ttl=topic_ttl)
            new_weak_items.append(item)

        if not new_weak_items:
            logger.info("published_quality_alert_suppressed_all_duplicates")
            return

        avg_score = report.get("average_score", 0)
        executed_at = report.get("executed_at", "-")
        threshold = settings.published_monitor_alert_threshold

        lines = [
            "🚨 <b>إنذار جودة المحتوى المنشور</b>",
            f"🕒 وقت الفحص: {self._clean_text(str(executed_at), 60)}",
            f"📉 المعدل العام: <b>{avg_score}</b> / 100",
            f"⚠️ عناصر جديدة تحت العتبة ({threshold}): <b>{len(new_weak_items)}</b>",
            "",
        ]

        for item in new_weak_items[:5]:
            title = self._clean_text(item.get("title", "بدون عنوان"), 120)
            score = item.get("score", 0)
            grade = self._clean_text(item.get("grade", "-"), 20)
            url = item.get("url", "")
            issue = self._clean_text(", ".join((item.get("issues") or [])[:2]), 180)
            lines.append(f"• <b>{title}</b>")
            lines.append(f"  - الدرجة: {score} ({grade})")
            if issue and issue != "-":
                lines.append(f"  - الملاحظات: {issue}")
            if url:
                lines.append(f"  - <a href=\"{url}\">فتح الرابط</a>")
            lines.append("")

        message = "\n".join(lines)[:4000]
        alert_channel = await settings_service.get_value(
            "TELEGRAM_CHANNEL_ALERTS",
            settings.telegram_channel_alerts,
        )
        fallback_editors = await settings_service.get_value(
            "TELEGRAM_CHANNEL_EDITORS",
            settings.telegram_channel_editors,
        )
        await self.send_telegram(message, channel=alert_channel or fallback_editors)


notification_service = NotificationService()
