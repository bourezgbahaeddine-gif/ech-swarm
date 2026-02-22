"""Utilities for strict JSON extraction/repair from LLM outputs."""

from __future__ import annotations

import json
import re
from typing import Any


_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _strip_code_fences(text: str) -> str:
    value = (text or "").strip()
    if not value.startswith("```"):
        return value
    value = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", value)
    value = re.sub(r"\s*```$", "", value)
    return value.strip()


def _sanitize_controls(text: str) -> str:
    return _CONTROL_CHARS_RE.sub("", (text or "").replace("\ufeff", ""))


def _extract_balanced_json(text: str) -> str:
    value = _sanitize_controls(_strip_code_fences(text))
    start_candidates = [i for i in [value.find("{"), value.find("[")] if i >= 0]
    if not start_candidates:
        return value.strip()

    start = min(start_candidates)
    stack: list[str] = []
    in_string = False
    escape = False
    for idx in range(start, len(value)):
        ch = value[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch in "{[":
            stack.append(ch)
            continue
        if ch in "}]":
            if not stack:
                continue
            opening = stack[-1]
            if (opening == "{" and ch == "}") or (opening == "[" and ch == "]"):
                stack.pop()
                if not stack:
                    return value[start : idx + 1].strip()
    return value[start:].strip()


def parse_llm_json(raw_text: str) -> dict[str, Any]:
    """Parse JSON from potentially noisy LLM text with strict validation."""
    text = _extract_balanced_json(raw_text)
    if not text:
        raise ValueError("empty_json_payload")

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        repaired = text
        repaired = repaired.replace("“", '"').replace("”", '"').replace("’", "'")
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
        data = json.loads(repaired)

    if not isinstance(data, dict):
        raise ValueError("json_root_must_be_object")
    return data
