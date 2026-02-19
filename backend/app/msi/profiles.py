"""MSI profiles loader."""

from __future__ import annotations

import json
from pathlib import Path

PROFILE_DIR = Path(__file__).resolve().parent / "profiles"


def _read_profile_json(path: Path) -> dict:
    # Accept UTF-8 files saved with BOM (common on Windows editors).
    return json.loads(path.read_text(encoding="utf-8-sig"))


def list_profiles() -> list[dict]:
    profiles: list[dict] = []
    for fp in sorted(PROFILE_DIR.glob("*.json")):
        try:
            data = _read_profile_json(fp)
            profiles.append(
                {
                    "id": data.get("id", fp.stem),
                    "display_name": data.get("display_name", fp.stem),
                    "description": data.get("description"),
                }
            )
        except Exception:
            continue
    return profiles


def load_profile(profile_id: str) -> dict:
    if not profile_id:
        raise ValueError("profile_id is required")

    normalized = profile_id.strip().lower()
    for fp in PROFILE_DIR.glob("*.json"):
        data = _read_profile_json(fp)
        if data.get("id", "").strip().lower() == normalized or fp.stem.lower() == normalized:
            return data
    raise FileNotFoundError(f"MSI profile not found: {profile_id}")
