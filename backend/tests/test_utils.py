"""
Echorouk AI Swarm — Tests
"""

import pytest
from app.utils.hashing import (
    normalize_text,
    generate_unique_hash,
    is_duplicate_title,
    generate_content_hash,
)
from app.utils.text_processing import sanitize_input, extract_clean_text


# ── Hashing Tests ──

class TestNormalizeText:
    def test_removes_arabic_diacritics(self):
        text = "اَلْجَزَائِرُ"
        result = normalize_text(text)
        assert "َ" not in result
        assert "ِ" not in result

    def test_removes_noise_words(self):
        text = "عاجل: انفجار في الجزائر العاصمة"
        result = normalize_text(text)
        assert "عاجل" not in result

    def test_strips_special_chars(self):
        text = "Hello! @World #2024"
        result = normalize_text(text)
        assert "@" not in result
        assert "#" not in result

    def test_empty_string(self):
        assert normalize_text("") == ""
        assert normalize_text(None) == ""


class TestGenerateUniqueHash:
    def test_deterministic(self):
        h1 = generate_unique_hash("APS", "https://aps.dz/1", "خبر مهم")
        h2 = generate_unique_hash("APS", "https://aps.dz/1", "خبر مهم")
        assert h1 == h2

    def test_different_inputs_different_hash(self):
        h1 = generate_unique_hash("APS", "https://aps.dz/1", "خبر أول")
        h2 = generate_unique_hash("APS", "https://aps.dz/2", "خبر ثاني")
        assert h1 != h2


class TestIsDuplicateTitle:
    def test_exact_match(self):
        titles = ["انتخابات رئاسية في الجزائر"]
        assert is_duplicate_title("انتخابات رئاسية في الجزائر", titles)

    def test_similar_match(self):
        titles = ["ارتفاع أسعار النفط في الأسواق العالمية"]
        assert is_duplicate_title("أسعار النفط ترتفع في الأسواق العالمية", titles)

    def test_different_no_match(self):
        titles = ["انتخابات رئاسية"]
        assert not is_duplicate_title("زلزال يضرب المنطقة الشرقية", titles)

    def test_empty_list(self):
        assert not is_duplicate_title("خبر جديد", [])


# ── Sanitization Tests ──

class TestSanitizeInput:
    def test_removes_script_tags(self):
        text = "Hello <script>alert('xss')</script> World"
        result = sanitize_input(text)
        assert "<script>" not in result
        assert "alert" not in result

    def test_removes_html_tags(self):
        text = "<p>Hello <b>World</b></p>"
        result = sanitize_input(text)
        assert "<p>" not in result
        assert "<b>" not in result
        assert "Hello" in result

    def test_removes_javascript_protocol(self):
        text = "javascript:alert(1)"
        result = sanitize_input(text)
        assert "javascript:" not in result

    def test_empty_string(self):
        assert sanitize_input("") == ""
        assert sanitize_input(None) == ""


class TestExtractCleanText:
    def test_removes_nav_footer(self):
        html = "<nav>menu</nav><p>Article content</p><footer>copyright</footer>"
        result = extract_clean_text(html)
        assert "menu" not in result
        assert "copyright" not in result
        assert "Article content" in result
