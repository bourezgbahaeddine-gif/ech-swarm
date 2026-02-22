"""
Echorouk Editorial OS — Audio Agent (المذيع الآلي)
==================================================
Produces automated audio news briefings using edge-tts.
Zero cost: Uses Microsoft's free TTS via edge-tts library.
"""

import asyncio
import subprocess
import os
from datetime import datetime
from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.ai_service import ai_service

logger = get_logger("agent.audio")
settings = get_settings()

AUDIO_TMP_DIR = "/tmp/audio"
os.makedirs(AUDIO_TMP_DIR, exist_ok=True)


class AudioAgent:
    """
    Audio News Agent — converts text articles into
    professional audio briefings (podcast/radio style).
    Cost: $0 using edge-tts + FFmpeg.
    """

    async def generate_briefing(self, articles: list[dict]) -> Optional[str]:
        """
        Generate a complete audio news briefing from articles.
        Returns the path to the final MP3 file.
        """
        if not articles:
            return None

        try:
            # ── Step 1: Generate Radio Script via AI ──
            script = await ai_service.generate_radio_script(articles)
            if not script:
                logger.warning("empty_radio_script")
                return None

            # ── Step 2: Text-to-Speech via edge-tts ──
            raw_audio = os.path.join(AUDIO_TMP_DIR, "raw_news.mp3")
            await self._text_to_speech(script, raw_audio)

            if not os.path.exists(raw_audio):
                logger.error("tts_no_output")
                return None

            # ── Step 3: Mix with intro/outro if available ──
            final_audio = os.path.join(
                AUDIO_TMP_DIR,
                f"briefing_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.mp3"
            )

            intro_path = os.path.join("data", "audio_assets", "intro.mp3")
            if os.path.exists(intro_path):
                await self._mix_audio(intro_path, raw_audio, final_audio)
            else:
                # No intro available, use raw audio
                os.rename(raw_audio, final_audio)

            logger.info("audio_briefing_generated", path=final_audio)
            return final_audio

        except Exception as e:
            logger.error("audio_generation_error", error=str(e))
            return None

    async def text_to_speech_simple(self, text: str, output_path: str) -> bool:
        """Simple TTS conversion for a single text."""
        return await self._text_to_speech(text, output_path)

    async def _text_to_speech(self, text: str, output_path: str) -> bool:
        """Convert text to speech using edge-tts."""
        try:
            import edge_tts

            communicate = edge_tts.Communicate(
                text,
                settings.tts_voice,
                rate=settings.tts_rate,
                pitch=settings.tts_pitch,
            )
            await communicate.save(output_path)

            logger.info("tts_complete",
                        output=output_path,
                        voice=settings.tts_voice,
                        text_len=len(text))
            return True

        except Exception as e:
            logger.error("tts_error", error=str(e))
            return False

    async def _mix_audio(self, intro: str, main: str, output: str) -> bool:
        """Mix intro + main audio using FFmpeg."""
        try:
            cmd = [
                "ffmpeg", "-y",
                "-i", intro,
                "-i", main,
                "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[out]",
                "-map", "[out]",
                output,
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info("audio_mixed", output=output)
                return True
            else:
                logger.error("ffmpeg_error", stderr=stderr.decode()[:500])
                return False

        except FileNotFoundError:
            logger.warning("ffmpeg_not_found", msg="FFmpeg not installed, skipping mixing")
            return False
        except Exception as e:
            logger.error("mix_error", error=str(e))
            return False

    def cleanup_temp_files(self):
        """Clean up temporary audio files."""
        try:
            for f in os.listdir(AUDIO_TMP_DIR):
                filepath = os.path.join(AUDIO_TMP_DIR, f)
                if os.path.isfile(filepath) and f.startswith("raw_"):
                    os.remove(filepath)
        except Exception as e:
            logger.warning("cleanup_error", error=str(e))


# Singleton
audio_agent = AudioAgent()
