"""
Echorouk Editorial OS — Text Processing Utilities
================================================
Input sanitization and text cleaning (Rule #2: Zero Trust).
"""

import re
import html
from typing import Optional


def sanitize_input(text: str) -> str:
    """
    Input Guard: Clean text from malicious scripts and unwanted content.
    Zero Trust Security — treat every input as a potential attack.
    """
    if not text:
        return ""

    # Remove HTML tags
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)

    # Decode HTML entities
    text = html.unescape(text)

    # Remove dangerous patterns
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)
    text = re.sub(r'data:', '', text, flags=re.IGNORECASE)

    # Remove null bytes
    text = text.replace('\x00', '')

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def extract_clean_text(html_content: str) -> str:
    """Extract readable text from HTML, removing boilerplate."""
    if not html_content:
        return ""

    # Remove common boilerplate patterns
    patterns_to_remove = [
        r'<nav[^>]*>.*?</nav>',
        r'<footer[^>]*>.*?</footer>',
        r'<header[^>]*>.*?</header>',
        r'<aside[^>]*>.*?</aside>',
        r'<!--.*?-->',
        r'<div[^>]*class="[^"]*ad[^"]*"[^>]*>.*?</div>',
    ]

    for pattern in patterns_to_remove:
        html_content = re.sub(pattern, '', html_content, flags=re.DOTALL | re.IGNORECASE)

    # Use sanitize_input for the rest
    return sanitize_input(html_content)


def truncate_text(text: str, max_length: int = 500) -> str:
    """Truncate text to max_length, ending at a word boundary."""
    if not text or len(text) <= max_length:
        return text or ""
    truncated = text[:max_length]
    last_space = truncated.rfind(' ')
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated + "..."


def count_words(text: str) -> int:
    """Count words in text (supports Arabic)."""
    if not text:
        return 0
    return len(text.split())


def extract_numbers(text: str) -> list[str]:
    """Extract all numbers from text for fact-checking purposes."""
    if not text:
        return []
    return re.findall(r'\d+[\d,.]*', text)
