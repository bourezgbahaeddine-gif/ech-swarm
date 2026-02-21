"""Media Logger service.

Transcribes long audio/video sources and extracts newsroom-ready quotes.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from hashlib import sha1
from pathlib import Path
from typing import Any

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.core.logging import get_logger
from app.models import (
    MediaLoggerHighlight,
    MediaLoggerJobEvent,
    MediaLoggerRun,
    MediaLoggerSegment,
)
from app.models.user import User
from app.services.ai_service import ai_service

logger = get_logger("media_logger.service")


class MediaLoggerService:
    def __init__(self) -> None:
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._whisper_model = None
        self._workdir = Path(os.getenv("MEDIA_LOGGER_WORKDIR", "/tmp/media_logger"))
        self._workdir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _json_safe(value: Any) -> Any:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))

    @staticmethod
    def _normalize_language(language_hint: str | None) -> str:
        value = (language_hint or "ar").strip().lower()
        if value in {"ar", "en", "fr", "auto"}:
            return value
        return "ar"

    @staticmethod
    def _build_url_idempotency(url: str, language_hint: str, actor_id: int | None) -> str:
        raw = f"url|{url.strip().lower()}|{language_hint}|{actor_id or 0}"
        return sha1(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _build_upload_idempotency(filename: str, payload: bytes, language_hint: str, actor_id: int | None) -> str:
        raw = f"upload|{filename.strip().lower()}|{language_hint}|{actor_id or 0}".encode("utf-8")
        return sha1(raw + payload).hexdigest()

    @staticmethod
    def _run_id(seed: str) -> str:
        suffix = abs(hash((seed, datetime.utcnow().isoformat()))) % 10_000_000
        return f"MLG-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{suffix:07d}"

    async def create_run_from_url(
        self,
        db: AsyncSession,
        *,
        media_url: str,
        language_hint: str,
        actor: User | None,
        idempotency_key: str | None = None,
    ) -> MediaLoggerRun:
        norm_lang = self._normalize_language(language_hint)
        idem = idempotency_key or self._build_url_idempotency(media_url, norm_lang, actor.id if actor else None)

        existing_row = await db.execute(
            select(MediaLoggerRun)
            .where(MediaLoggerRun.idempotency_key == idem)
            .order_by(MediaLoggerRun.created_at.desc())
            .limit(1)
        )
        existing = existing_row.scalar_one_or_none()
        if existing and existing.status in {"queued", "running", "completed"}:
            return existing

        run = MediaLoggerRun(
            run_id=self._run_id(media_url),
            source_type="url",
            source_ref=media_url.strip(),
            source_label=media_url.strip(),
            language_hint=norm_lang,
            status="queued",
            idempotency_key=idem,
            created_by_user_id=actor.id if actor else None,
            created_by_username=actor.username if actor else "system",
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        return run

    async def create_run_from_upload(
        self,
        db: AsyncSession,
        *,
        filename: str,
        payload: bytes,
        language_hint: str,
        actor: User | None,
        idempotency_key: str | None = None,
    ) -> MediaLoggerRun:
        norm_lang = self._normalize_language(language_hint)
        safe_name = self._safe_filename(filename)
        idem = idempotency_key or self._build_upload_idempotency(safe_name, payload, norm_lang, actor.id if actor else None)

        existing_row = await db.execute(
            select(MediaLoggerRun)
            .where(MediaLoggerRun.idempotency_key == idem)
            .order_by(MediaLoggerRun.created_at.desc())
            .limit(1)
        )
        existing = existing_row.scalar_one_or_none()
        if existing and existing.status in {"queued", "running", "completed"}:
            return existing

        run_id = self._run_id(safe_name)
        source_path = self._workdir / f"{run_id}-source-{safe_name}"
        source_path.write_bytes(payload)

        run = MediaLoggerRun(
            run_id=run_id,
            source_type="upload",
            source_ref=str(source_path),
            source_label=safe_name,
            language_hint=norm_lang,
            status="queued",
            idempotency_key=idem,
            created_by_user_id=actor.id if actor else None,
            created_by_username=actor.username if actor else "system",
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        return run

    async def start_run_task(self, run_id: str) -> None:
        if run_id in self._running_tasks and not self._running_tasks[run_id].done():
            return
        task = asyncio.create_task(self.execute_run(run_id))
        self._running_tasks[run_id] = task

    async def execute_run(self, run_id: str) -> None:
        async with async_session() as db:
            row = await db.execute(select(MediaLoggerRun).where(MediaLoggerRun.run_id == run_id))
            run = row.scalar_one_or_none()
            if not run:
                return

            run.status = "running"
            run.error = None
            await db.commit()
            await self._emit_event(db, run_id, "runner", "started", {"status": "running"})

            temp_paths: list[Path] = []
            try:
                source_path = await self._prepare_source(run)
                temp_paths.append(source_path)
                await self._emit_event(db, run_id, "prepare_source", "state_update", {"path": str(source_path)})

                audio_path = await asyncio.to_thread(self._extract_audio_wav, source_path, run_id)
                temp_paths.append(audio_path)
                await self._emit_event(db, run_id, "extract_audio", "state_update", {"audio_path": str(audio_path)})

                segments, detected_language, duration = await asyncio.to_thread(
                    self._transcribe_audio,
                    audio_path,
                    run.language_hint,
                )
                await self._emit_event(
                    db,
                    run_id,
                    "transcribe",
                    "state_update",
                    {
                        "segments": len(segments),
                        "language": detected_language,
                        "duration_seconds": round(duration, 2),
                    },
                )
                if not segments:
                    raise RuntimeError("No transcript segments produced")

                highlights = self._extract_highlights(segments, limit=12)
                transcript_text = self._build_transcript_text(segments)

                await db.execute(delete(MediaLoggerSegment).where(MediaLoggerSegment.run_id == run_id))
                await db.execute(delete(MediaLoggerHighlight).where(MediaLoggerHighlight.run_id == run_id))
                await db.commit()

                db.add_all(
                    [
                        MediaLoggerSegment(
                            run_id=run_id,
                            segment_index=item["segment_index"],
                            start_sec=item["start_sec"],
                            end_sec=item["end_sec"],
                            text=item["text"],
                            confidence=item.get("confidence"),
                            speaker=item.get("speaker"),
                        )
                        for item in segments
                    ]
                )
                db.add_all(
                    [
                        MediaLoggerHighlight(
                            run_id=run_id,
                            rank=h["rank"],
                            quote=h["quote"],
                            reason=h.get("reason"),
                            start_sec=h["start_sec"],
                            end_sec=h["end_sec"],
                            confidence=h.get("confidence"),
                        )
                        for h in highlights
                    ]
                )

                run.transcript_language = detected_language
                run.transcript_text = transcript_text
                run.duration_seconds = duration
                run.segments_count = len(segments)
                run.highlights_count = len(highlights)
                run.status = "completed"
                run.finished_at = datetime.utcnow()
                run.error = None
                await db.commit()

                await self._emit_event(
                    db,
                    run_id,
                    "persist",
                    "finished",
                    {
                        "segments": len(segments),
                        "highlights": len(highlights),
                        "status": "completed",
                    },
                )
                await self._emit_event(db, run_id, "runner", "finished", {"status": "completed"})
            except Exception as exc:  # noqa: BLE001
                logger.error("media_logger_run_failed", run_id=run_id, error=str(exc))
                await db.rollback()
                failed_row = await db.execute(select(MediaLoggerRun).where(MediaLoggerRun.run_id == run_id))
                failed = failed_row.scalar_one_or_none()
                if failed:
                    failed.status = "failed"
                    failed.finished_at = datetime.utcnow()
                    failed.error = str(exc)[:2000]
                    await db.commit()
                await self._emit_event(db, run_id, "runner", "failed", {"status": "failed", "error": str(exc)})
            finally:
                self._cleanup_temp_files(temp_paths)

    async def get_run_status(self, db: AsyncSession, run_id: str) -> MediaLoggerRun | None:
        row = await db.execute(select(MediaLoggerRun).where(MediaLoggerRun.run_id == run_id))
        return row.scalar_one_or_none()

    async def get_result(self, db: AsyncSession, run_id: str) -> dict | None:
        run = await self.get_run_status(db, run_id)
        if not run:
            return None

        highlights_rows = await db.execute(
            select(MediaLoggerHighlight)
            .where(MediaLoggerHighlight.run_id == run_id)
            .order_by(MediaLoggerHighlight.rank.asc())
            .limit(30)
        )
        segment_rows = await db.execute(
            select(MediaLoggerSegment)
            .where(MediaLoggerSegment.run_id == run_id)
            .order_by(MediaLoggerSegment.segment_index.asc())
            .limit(5000)
        )
        highlights = [
            {
                "rank": h.rank,
                "quote": h.quote,
                "reason": h.reason,
                "start_sec": h.start_sec,
                "end_sec": h.end_sec,
                "confidence": h.confidence,
            }
            for h in highlights_rows.scalars().all()
        ]
        segments = [
            {
                "segment_index": s.segment_index,
                "start_sec": s.start_sec,
                "end_sec": s.end_sec,
                "text": s.text,
                "confidence": s.confidence,
                "speaker": s.speaker,
            }
            for s in segment_rows.scalars().all()
        ]
        return {
            "run_id": run.run_id,
            "status": run.status,
            "source_type": run.source_type,
            "source_label": run.source_label,
            "language_hint": run.language_hint,
            "transcript_language": run.transcript_language,
            "transcript_text": run.transcript_text or "",
            "duration_seconds": run.duration_seconds,
            "segments_count": run.segments_count,
            "highlights_count": run.highlights_count,
            "highlights": highlights,
            "segments": segments,
            "created_at": run.created_at,
            "finished_at": run.finished_at,
        }

    async def ask_question(self, db: AsyncSession, run_id: str, question: str) -> dict | None:
        run = await self.get_run_status(db, run_id)
        if not run:
            return None
        if run.status != "completed":
            raise RuntimeError("Run is not completed yet")

        rows = await db.execute(
            select(MediaLoggerSegment)
            .where(MediaLoggerSegment.run_id == run_id)
            .order_by(MediaLoggerSegment.segment_index.asc())
        )
        segments = rows.scalars().all()
        if not segments:
            raise RuntimeError("No segments available")

        ranked = self._rank_segments_for_question(question, segments)
        top = ranked[0]
        context_segments = ranked[:5]

        ai_answer = await self._ai_answer_with_context(question, context_segments)
        if ai_answer:
            best = next((s for s in segments if s.segment_index == int(ai_answer.get("segment_index", -1))), None)
            if best:
                return {
                    "run_id": run_id,
                    "answer": ai_answer.get("answer") or best.text,
                    "quote": ai_answer.get("quote") or best.text,
                    "start_sec": float(best.start_sec),
                    "end_sec": float(best.end_sec),
                    "confidence": float(ai_answer.get("confidence", 0.72)),
                    "context": [
                        {
                            "segment_index": s.segment_index,
                            "start_sec": float(s.start_sec),
                            "end_sec": float(s.end_sec),
                            "text": s.text,
                            "confidence": s.confidence,
                            "speaker": s.speaker,
                        }
                        for s in context_segments
                    ],
                }

        answer = f"الاقتباس الأقرب للسؤال: {top.text}"
        return {
            "run_id": run_id,
            "answer": answer,
            "quote": top.text,
            "start_sec": float(top.start_sec),
            "end_sec": float(top.end_sec),
            "confidence": 0.68,
            "context": [
                {
                    "segment_index": s.segment_index,
                    "start_sec": float(s.start_sec),
                    "end_sec": float(s.end_sec),
                    "text": s.text,
                    "confidence": s.confidence,
                    "speaker": s.speaker,
                }
                for s in context_segments
            ],
        }

    async def get_recent_runs(
        self,
        db: AsyncSession,
        *,
        limit: int = 20,
        status: str | None = None,
    ) -> list[dict]:
        query = select(MediaLoggerRun).order_by(desc(MediaLoggerRun.created_at)).limit(limit)
        if status:
            query = query.where(MediaLoggerRun.status == status)
        rows = await db.execute(query)
        return [
            {
                "run_id": r.run_id,
                "status": r.status,
                "source_type": r.source_type,
                "source_label": r.source_label,
                "language_hint": r.language_hint,
                "segments_count": r.segments_count,
                "highlights_count": r.highlights_count,
                "created_at": r.created_at,
                "finished_at": r.finished_at,
            }
            for r in rows.scalars().all()
        ]

    async def get_events_since(
        self,
        db: AsyncSession,
        *,
        run_id: str,
        last_id: int = 0,
        limit: int = 100,
    ) -> list[MediaLoggerJobEvent]:
        rows = await db.execute(
            select(MediaLoggerJobEvent)
            .where(MediaLoggerJobEvent.run_id == run_id, MediaLoggerJobEvent.id > last_id)
            .order_by(MediaLoggerJobEvent.id.asc())
            .limit(limit)
        )
        return rows.scalars().all()

    async def _emit_event(self, db: AsyncSession, run_id: str, node: str, event_type: str, payload: dict) -> None:
        db.add(
            MediaLoggerJobEvent(
                run_id=run_id,
                node=node,
                event_type=event_type,
                payload_json=self._json_safe(payload or {}),
            )
        )
        await db.commit()

    async def _prepare_source(self, run: MediaLoggerRun) -> Path:
        if run.source_type == "upload":
            source = Path(run.source_ref)
            if not source.exists():
                raise FileNotFoundError("Uploaded source file is missing")
            return source
        return await asyncio.to_thread(self._download_from_url, run.source_ref, run.run_id)

    def _download_from_url(self, media_url: str, run_id: str) -> Path:
        output_template = self._workdir / f"{run_id}-download.%(ext)s"
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--quiet",
            "--no-warnings",
            "--print",
            "after_move:filepath",
            "-f",
            "bestaudio/best",
            "-o",
            str(output_template),
            media_url,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"yt-dlp failed: {(proc.stderr or proc.stdout).strip()[:400]}")
        output = (proc.stdout or "").strip().splitlines()
        if not output:
            raise RuntimeError("yt-dlp did not return downloaded file path")
        path = Path(output[-1].strip())
        if not path.exists():
            raise FileNotFoundError("Downloaded media file not found")
        return path

    def _extract_audio_wav(self, source_path: Path, run_id: str) -> Path:
        output = self._workdir / f"{run_id}-audio.wav"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(source_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(output),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {(proc.stderr or proc.stdout).strip()[:500]}")
        if not output.exists():
            raise FileNotFoundError("Converted WAV file was not created")
        return output

    def _get_whisper_model(self):
        if self._whisper_model is not None:
            return self._whisper_model
        try:
            from faster_whisper import WhisperModel
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("faster-whisper is not installed. Run: pip install faster-whisper") from exc
        model_size = os.getenv("MEDIA_LOGGER_MODEL_SIZE", "small")
        compute_type = os.getenv("MEDIA_LOGGER_COMPUTE_TYPE", "int8")
        self._whisper_model = WhisperModel(model_size, compute_type=compute_type)
        return self._whisper_model

    def _transcribe_audio(self, audio_path: Path, language_hint: str) -> tuple[list[dict], str, float]:
        model = self._get_whisper_model()
        lang = None if language_hint == "auto" else language_hint
        beam_size = int(os.getenv("MEDIA_LOGGER_BEAM_SIZE", "5"))
        segments_iter, info = model.transcribe(
            str(audio_path),
            language=lang,
            vad_filter=True,
            beam_size=beam_size,
            word_timestamps=False,
        )

        segments: list[dict] = []
        duration = 0.0
        for idx, item in enumerate(segments_iter):
            text = (item.text or "").strip()
            if not text:
                continue
            start_sec = float(item.start or 0.0)
            end_sec = float(item.end or start_sec)
            duration = max(duration, end_sec)
            confidence = None
            avg_logprob = getattr(item, "avg_logprob", None)
            if avg_logprob is not None:
                confidence = max(0.0, min(1.0, 1.0 + float(avg_logprob)))
            segments.append(
                {
                    "segment_index": idx,
                    "start_sec": start_sec,
                    "end_sec": end_sec,
                    "text": text,
                    "confidence": confidence,
                }
            )

        detected = (getattr(info, "language", None) or language_hint or "ar").strip().lower()
        if detected not in {"ar", "fr", "en"}:
            detected = "ar"
        return segments, detected, duration

    def _build_transcript_text(self, segments: list[dict]) -> str:
        lines = []
        for item in segments:
            start = self._format_timestamp(float(item["start_sec"]))
            lines.append(f"[{start}] {item['text']}")
        return "\n".join(lines)

    @staticmethod
    def _safe_filename(filename: str) -> str:
        value = (filename or "upload").strip().replace("\\", "_").replace("/", "_")
        value = re.sub(r"\s+", "_", value)
        value = re.sub(r"[^A-Za-z0-9._-]", "", value)
        return value[:120] or "upload.bin"

    def _extract_highlights(self, segments: list[dict], limit: int = 12) -> list[dict]:
        trigger_words = {
            "أكد": 2.2,
            "أعلن": 2.1,
            "صرح": 2.0,
            "كشف": 2.0,
            "قال": 1.4,
            "أشار": 1.2,
            "قرار": 1.4,
            "إجراء": 1.2,
            "سكن": 1.3,
            "اقتصاد": 1.2,
            "ميزانية": 1.2,
        }

        scored: list[tuple[float, dict]] = []
        for seg in segments:
            text = seg["text"]
            score = min(len(text) / 160.0, 1.2)
            for word, weight in trigger_words.items():
                if word in text:
                    score += weight
            if re.search(r"\d{2,}", text):
                score += 0.8
            if len(text) > 45:
                score += 0.5
            scored.append((score, seg))

        scored.sort(key=lambda x: x[0], reverse=True)
        selected = scored[: max(1, limit)]
        highlights = []
        for rank, (score, seg) in enumerate(selected, start=1):
            reason = "تصريح مباشر عالي الأهمية" if score >= 3.5 else "مقطع مهم للنشر"
            highlights.append(
                {
                    "rank": rank,
                    "quote": seg["text"],
                    "reason": reason,
                    "start_sec": float(seg["start_sec"]),
                    "end_sec": float(seg["end_sec"]),
                    "confidence": round(min(0.99, 0.45 + score / 8.0), 2),
                }
            )
        return highlights

    async def _ai_answer_with_context(self, question: str, segments: list[MediaLoggerSegment]) -> dict | None:
        context = "\n".join(
            [
                f"- segment_index={s.segment_index} | {self._format_timestamp(float(s.start_sec))} -> {self._format_timestamp(float(s.end_sec))} | {s.text}"
                for s in segments
            ]
        )
        prompt = (
            "أنت مساعد غرفة أخبار. استخدم المقاطع المرفقة فقط.\n"
            "أعد JSON فقط بالمفاتيح التالية:\n"
            '{"answer":"...","quote":"...","segment_index":0,"confidence":0.0}\n'
            "إذا لا يوجد جواب واضح أعد أفضل اقتباس متاح من السياق.\n\n"
            f"السؤال:\n{question}\n\n"
            f"المقاطع:\n{context}\n"
        )
        try:
            data = await ai_service.generate_json(prompt)
            if isinstance(data, dict) and "segment_index" in data:
                return data
        except Exception:  # noqa: BLE001
            return None
        return None

    def _rank_segments_for_question(self, question: str, segments: list[MediaLoggerSegment]) -> list[MediaLoggerSegment]:
        q_tokens = self._tokenize(question)
        target_minute = self._extract_requested_minute(question)
        target_sec = target_minute * 60 if target_minute is not None else None

        scored: list[tuple[float, MediaLoggerSegment]] = []
        for seg in segments:
            text_tokens = self._tokenize(seg.text)
            overlap = len(q_tokens.intersection(text_tokens)) / max(1, len(q_tokens))
            score = overlap * 2.4

            if target_sec is not None:
                midpoint = (float(seg.start_sec) + float(seg.end_sec)) / 2.0
                diff = abs(midpoint - target_sec)
                score += max(0.0, 1.8 - min(diff / 240.0, 1.8))

            if re.search(r"(قال|أعلن|أكد|صرح|كشف)", seg.text):
                score += 0.5

            scored.append((score, seg))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [s for _, s in scored]

    @staticmethod
    def _extract_requested_minute(question: str) -> int | None:
        match = re.search(r"(?:دقيقة|الدقيقة|minute)\s*[:\-]?\s*(\d{1,3})", question, flags=re.IGNORECASE)
        if not match:
            return None
        value = int(match.group(1))
        if value < 0:
            return None
        return value

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        normalized = MediaLoggerService._normalize_ar_text(text)
        tokens = re.split(r"[^\w\u0600-\u06FF]+", normalized)
        return {token for token in tokens if token and len(token) >= 2}

    @staticmethod
    def _normalize_ar_text(text: str) -> str:
        value = (text or "").lower()
        value = re.sub(r"[\u064b-\u065f\u0670]", "", value)  # remove Arabic diacritics
        value = value.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
        value = value.replace("ة", "ه").replace("ى", "ي")
        return value

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        total = max(0, int(seconds))
        m, s = divmod(total, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _cleanup_temp_files(self, paths: list[Path]) -> None:
        for path in paths:
            try:
                if not path:
                    continue
                if path.is_file() and path.parent == self._workdir:
                    path.unlink(missing_ok=True)
            except Exception:
                continue
        # clean stale dirs from interrupted runs
        if self._workdir.exists():
            for child in self._workdir.iterdir():
                try:
                    if child.is_dir():
                        shutil.rmtree(child, ignore_errors=True)
                except Exception:
                    continue


media_logger_service = MediaLoggerService()
