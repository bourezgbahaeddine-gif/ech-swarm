from __future__ import annotations

import copy
import json
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.script import ScriptOutputFormat, ScriptProject, ScriptProjectStatus, ScriptProjectType
from app.repositories.script_repository import script_repository
from app.services.ai_service import ai_service
from app.services.audit_service import audit_service
from app.services.script_studio_service import script_studio_service


def _deep_copy_json(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False))
    except Exception:
        return copy.deepcopy(value)


class ScriptVideoWorkspaceService:
    PROFILE_DEFAULTS: dict[str, dict[str, Any]] = {
        "short_vertical": {
            "target_platform": "instagram_reels",
            "editorial_objective": "hook_fast",
            "length_seconds": 45,
            "hook_target_seconds": 5,
        },
        "news_package": {
            "target_platform": "youtube",
            "editorial_objective": "inform",
            "length_seconds": 90,
            "hook_target_seconds": 8,
        },
        "explainer": {
            "target_platform": "youtube",
            "editorial_objective": "explain",
            "length_seconds": 120,
            "hook_target_seconds": 7,
        },
        "breaking_clip": {
            "target_platform": "x",
            "editorial_objective": "breaking",
            "length_seconds": 35,
            "hook_target_seconds": 4,
        },
        "voiceover_package": {
            "target_platform": "youtube_shorts",
            "editorial_objective": "voiceover",
            "length_seconds": 60,
            "hook_target_seconds": 5,
        },
        "document_explainer": {
            "target_platform": "youtube",
            "editorial_objective": "document_explainer",
            "length_seconds": 100,
            "hook_target_seconds": 6,
        },
    }

    def _latest_output_json(self, project: ScriptProject) -> dict[str, Any]:
        outputs = sorted(list(project.outputs or []), key=lambda row: row.version, reverse=True)
        latest = outputs[0] if outputs else None
        payload = latest.content_json if latest and isinstance(latest.content_json, dict) else {}
        return self._materialize_video_payload(project, payload)

    def _profile_name(self, project: ScriptProject, payload: dict[str, Any]) -> str:
        if isinstance(payload.get("video_profile"), str) and payload.get("video_profile"):
            return str(payload["video_profile"])
        params = project.params_json if isinstance(project.params_json, dict) else {}
        if isinstance(params.get("video_profile"), str) and params.get("video_profile"):
            return str(params["video_profile"])
        return "news_package"

    def _profile_defaults(self, profile: str) -> dict[str, Any]:
        return dict(self.PROFILE_DEFAULTS.get(profile, self.PROFILE_DEFAULTS["news_package"]))

    def _normalize_scenes(self, scenes: list[dict[str, Any]] | None, profile: str) -> list[dict[str, Any]]:
        defaults = self._profile_defaults(profile)
        normalized: list[dict[str, Any]] = []
        for idx, raw in enumerate(scenes or [], start=1):
            item = raw if isinstance(raw, dict) else {}
            normalized.append(
                {
                    "idx": idx,
                    "duration_s": max(1, int(item.get("duration_s") or defaults["length_seconds"] // max(1, len(scenes or [1])))),
                    "scene_type": str(item.get("scene_type") or ("hook" if idx == 1 else "body")),
                    "priority": str(item.get("priority") or ("high" if idx == 1 else "medium")),
                    "visual": str(item.get("visual") or "").strip(),
                    "on_screen_text": str(item.get("on_screen_text") or "").strip(),
                    "vo_line": str(item.get("vo_line") or "").strip(),
                    "asset_status": str(item.get("asset_status") or "missing"),
                    "source_reference": str(item.get("source_reference") or "").strip() or None,
                    "locked": bool(item.get("locked", False)),
                }
            )
        return normalized

    def _build_caption_lines(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        lines = payload.get("captions_lines")
        if isinstance(lines, list) and lines:
            normalized: list[dict[str, Any]] = []
            for idx, item in enumerate(lines, start=1):
                if not isinstance(item, dict):
                    continue
                normalized.append(
                    {
                        "idx": idx,
                        "start_s": float(item.get("start_s") or 0),
                        "end_s": float(item.get("end_s") or 0),
                        "text": str(item.get("text") or "").strip(),
                    }
                )
            if normalized:
                return normalized

        scenes = payload.get("scenes") if isinstance(payload.get("scenes"), list) else []
        caption_lines: list[dict[str, Any]] = []
        cursor = 0.0
        for idx, scene in enumerate(scenes, start=1):
            if not isinstance(scene, dict):
                continue
            duration = float(scene.get("duration_s") or 0)
            text = str(scene.get("on_screen_text") or scene.get("vo_line") or "").strip()
            caption_lines.append(
                {
                    "idx": idx,
                    "start_s": round(cursor, 2),
                    "end_s": round(cursor + max(1.0, duration), 2),
                    "text": text,
                }
            )
            cursor += max(1.0, duration)
        return caption_lines

    def _render_srt(self, caption_lines: list[dict[str, Any]]) -> str:
        def fmt(seconds: float) -> str:
            total_ms = max(0, int(seconds * 1000))
            hours = total_ms // 3_600_000
            minutes = (total_ms % 3_600_000) // 60_000
            secs = (total_ms % 60_000) // 1000
            millis = total_ms % 1000
            return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

        chunks: list[str] = []
        for idx, line in enumerate(caption_lines, start=1):
            chunks.append(
                "\n".join(
                    [
                        str(idx),
                        f"{fmt(float(line.get('start_s') or 0))} --> {fmt(float(line.get('end_s') or 0))}",
                        str(line.get("text") or "").strip() or "...",
                    ]
                )
            )
        return "\n\n".join(chunks)

    def _materialize_video_payload(self, project: ScriptProject, payload: dict[str, Any] | None) -> dict[str, Any]:
        base = _deep_copy_json(payload or {})
        params = project.params_json if isinstance(project.params_json, dict) else {}
        profile = self._profile_name(project, base)
        defaults = self._profile_defaults(profile)
        scenes = self._normalize_scenes(base.get("scenes") if isinstance(base.get("scenes"), list) else [], profile)
        total_duration = sum(int(scene.get("duration_s") or 0) for scene in scenes)
        caption_lines = self._build_caption_lines({**base, "scenes": scenes})
        assets = base.get("assets_list") if isinstance(base.get("assets_list"), list) else []
        normalized_assets: list[dict[str, Any]] = []
        for idx, asset in enumerate(assets, start=1):
            item = asset if isinstance(asset, dict) else {}
            normalized_assets.append(
                {
                    "idx": idx,
                    "type": str(item.get("type") or "archive"),
                    "hint": str(item.get("hint") or "").strip(),
                    "scene_idx": int(item.get("scene_idx") or idx if idx <= len(scenes) else 0) or None,
                    "status": str(item.get("status") or "missing"),
                }
            )

        delivery = base.get("delivery") if isinstance(base.get("delivery"), dict) else {}
        document = {
            "video_profile": profile,
            "target_platform": str(base.get("target_platform") or params.get("target_platform") or defaults["target_platform"]),
            "editorial_objective": str(
                base.get("editorial_objective") or params.get("editorial_objective") or defaults["editorial_objective"]
            ),
            "total_duration_s": total_duration or int(base.get("total_duration_s") or params.get("length_seconds") or defaults["length_seconds"]),
            "hook_strength": float(base.get("hook_strength") or 0),
            "pace_notes": str(base.get("pace_notes") or ""),
            "delivery_status": str(base.get("delivery_status") or delivery.get("status") or "draft"),
            "vo_script": str(base.get("vo_script") or "").strip(),
            "hook": str(base.get("hook") or ""),
            "closing": str(base.get("closing") or ""),
            "scenes": scenes,
            "captions_lines": caption_lines,
            "captions_srt": str(base.get("captions_srt") or self._render_srt(caption_lines)),
            "assets_list": normalized_assets,
            "thumbnail_ideas": [str(item).strip() for item in (base.get("thumbnail_ideas") or []) if str(item).strip()],
            "delivery": {
                "title": str(delivery.get("title") or project.title or "").strip(),
                "thumbnail_line": str(delivery.get("thumbnail_line") or ""),
                "social_copy": str(delivery.get("social_copy") or ""),
                "shot_list": delivery.get("shot_list") if isinstance(delivery.get("shot_list"), list) else [],
                "source_references": delivery.get("source_references")
                if isinstance(delivery.get("source_references"), list)
                else [],
                "status": str(delivery.get("status") or base.get("delivery_status") or "draft"),
                "exported_at": delivery.get("exported_at"),
            },
        }
        return document

    def workspace_summary(self, project: ScriptProject) -> dict[str, Any]:
        if project.type != ScriptProjectType.video_script:
            return {}
        payload = self._latest_output_json(project)
        latest_output = sorted(list(project.outputs or []), key=lambda row: row.version, reverse=True)[0] if project.outputs else None
        issues = latest_output.quality_issues_json if latest_output and isinstance(latest_output.quality_issues_json, list) else []
        blockers = [item for item in issues if isinstance(item, dict) and item.get("severity") == "blocker"]
        warnings = [item for item in issues if isinstance(item, dict) and item.get("severity") in {"warn", "warning"}]
        next_action = "راجِع المشاهد"
        if blockers:
            next_action = "عالج العوائق أولًا"
        elif any(scene.get("asset_status") == "missing" for scene in payload["scenes"]):
            next_action = "اربط الأصول البصرية"
        elif project.status == ScriptProjectStatus.ready_for_review:
            next_action = "اتخذ قرار الاعتماد"
        elif project.status == ScriptProjectStatus.approved:
            next_action = "صدّر حزمة التسليم"
        return {
            "video_profile": payload["video_profile"],
            "target_platform": payload["target_platform"],
            "editorial_objective": payload["editorial_objective"],
            "total_duration_s": payload["total_duration_s"],
            "delivery_status": payload["delivery_status"],
            "next_action": next_action,
            "blockers": blockers,
            "warnings": warnings,
            "missing_assets": sum(1 for scene in payload["scenes"] if scene.get("asset_status") == "missing"),
        }

    async def save_manual_video_version(
        self,
        db: AsyncSession,
        *,
        project: ScriptProject,
        content_json: dict[str, Any],
        actor_username: str | None,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> ScriptProject:
        if project.type != ScriptProjectType.video_script:
            raise ValueError("video_workspace_only")

        payload = self._materialize_video_payload(project, content_json)
        quality = script_studio_service.run_quality_gates(
            project_type=ScriptProjectType.video_script,
            output_json=payload,
            params=project.params_json if isinstance(project.params_json, dict) else {},
        )
        version = await script_repository.get_next_output_version(db, project.id)
        await script_repository.create_output(
            db,
            script_id=project.id,
            version=version,
            content_json=payload,
            content_text=script_studio_service._render_text_output(ScriptProjectType.video_script, payload),
            output_format=ScriptOutputFormat.json,
            quality_issues_json=quality["issues"],
        )
        previous_status = project.status.value if project.status else None
        project.status = ScriptProjectStatus.ready_for_review
        project.updated_by = actor_username
        await audit_service.log_action(
            db,
            action=action,
            entity_type="script_project",
            entity_id=project.id,
            actor=None,
            from_state=previous_status,
            to_state=project.status.value,
            details=details or {},
        )
        await db.commit()
        refreshed = await script_repository.get_project_by_id(db, project.id)
        if not refreshed:
            raise RuntimeError("script_project_not_found")
        return refreshed

    def payload_from_project(self, project: ScriptProject) -> dict[str, Any]:
        return self._latest_output_json(project)

    async def regenerate_single_scene(
        self,
        db: AsyncSession,
        *,
        project: ScriptProject,
        scene_idx: int,
        actor_username: str | None,
    ) -> ScriptProject:
        payload = self._latest_output_json(project)
        scenes = payload["scenes"]
        if scene_idx < 1 or scene_idx > len(scenes):
            raise ValueError("scene_not_found")

        scene = scenes[scene_idx - 1]
        if scene.get("locked"):
            raise ValueError("scene_locked")

        params = project.params_json if isinstance(project.params_json, dict) else {}
        prompt = {
            "instruction": "Regenerate only one video scene for a newsroom script. Return JSON with duration_s, visual, on_screen_text, vo_line, scene_type, priority, asset_status.",
            "profile": payload["video_profile"],
            "platform": payload["target_platform"],
            "objective": payload["editorial_objective"],
            "scene": scene,
            "vo_script": payload["vo_script"],
            "style_constraints": params.get("style_constraints") or [],
        }
        replacement: dict[str, Any]
        try:
            generated = await ai_service.generate_json(json.dumps(prompt, ensure_ascii=False))
            replacement = generated if isinstance(generated, dict) else {}
        except Exception:
            replacement = {}

        merged = {
            **scene,
            "duration_s": int(replacement.get("duration_s") or scene.get("duration_s") or 6),
            "visual": str(replacement.get("visual") or scene.get("visual") or "").strip(),
            "on_screen_text": str(replacement.get("on_screen_text") or scene.get("on_screen_text") or "").strip(),
            "vo_line": str(replacement.get("vo_line") or scene.get("vo_line") or "").strip(),
            "scene_type": str(replacement.get("scene_type") or scene.get("scene_type") or "body"),
            "priority": str(replacement.get("priority") or scene.get("priority") or "medium"),
            "asset_status": str(replacement.get("asset_status") or "missing"),
        }
        scenes[scene_idx - 1] = merged
        payload["scenes"] = scenes
        payload["captions_lines"] = self._build_caption_lines(payload)
        payload["captions_srt"] = self._render_srt(payload["captions_lines"])
        return await self.save_manual_video_version(
            db,
            project=project,
            content_json=payload,
            actor_username=actor_username,
            action="script_video_scene_regenerated",
            details={"scene_idx": scene_idx},
        )

    def export_bundle(self, project: ScriptProject) -> dict[str, Any]:
        payload = self._latest_output_json(project)
        delivery = payload["delivery"]
        return {
            "script_id": project.id,
            "title": delivery.get("title") or project.title,
            "video_profile": payload["video_profile"],
            "target_platform": payload["target_platform"],
            "editorial_objective": payload["editorial_objective"],
            "vo_script": payload["vo_script"],
            "total_duration_s": payload["total_duration_s"],
            "scenes": payload["scenes"],
            "captions_srt": payload["captions_srt"],
            "captions_lines": payload["captions_lines"],
            "assets_list": payload["assets_list"],
            "thumbnail_ideas": payload["thumbnail_ideas"],
            "thumbnail_line": delivery.get("thumbnail_line"),
            "social_copy": delivery.get("social_copy"),
            "shot_list": delivery.get("shot_list"),
            "source_references": delivery.get("source_references"),
            "delivery_status": delivery.get("status"),
        }


script_video_workspace_service = ScriptVideoWorkspaceService()
