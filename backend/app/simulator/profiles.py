"""Policy and persona profiles for Audience Simulator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SIMULATOR_DIR = Path(__file__).resolve().parent
PROFILES_DIR = SIMULATOR_DIR / "profiles"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def load_personas_pack(profile_id: str = "personas_dz_v1") -> dict[str, Any]:
    path = PROFILES_DIR / f"{profile_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Personas profile not found: {profile_id}")
    data = _load_json(path)
    if "personas" not in data or not isinstance(data["personas"], list):
        raise ValueError("Invalid personas profile format")
    return data


def load_policy_profile(profile_id: str = "dz_newsroom_v1") -> dict[str, Any]:
    personas = load_personas_pack("personas_dz_v1")
    return {
        "id": profile_id,
        "display_name": "محاكي الجمهور - غرفة الشروق",
        "brand_voice": {
            "tone": "professional_objective",
            "avoid": ["clickbait_misleading", "incitement", "defamation"],
        },
        "policy_rules": {
            "no_hate": True,
            "no_political_judgment": True,
            "no_private_data": True,
            "human_gate_high_risk_threshold": 8.0,
            "human_gate_recommended_threshold": 5.0,
        },
        "weights": {
            "risk": {"clickbait": 0.2, "legal": 0.3, "values": 0.2, "polarization": 0.15, "misinfo": 0.15},
            "virality": {"emotion": 0.25, "clarity": 0.25, "novelty": 0.2, "meme": 0.15, "simplicity": 0.15},
        },
        "personas": personas["personas"],
    }
