from app.services.smart_editor_service import smart_editor_service


def test_sanitize_html_removes_script_and_javascript_href():
    dirty = '<h1>Title</h1><script>alert(1)</script><a href="javascript:alert(1)">x</a><p>ok</p>'
    clean = smart_editor_service.sanitize_html(dirty)
    assert "<script" not in clean.lower()
    assert "javascript:" not in clean.lower()
    assert "<h1>" in clean
    assert "<p>ok</p>" in clean


def test_build_diff_returns_add_remove_counts():
    diff = smart_editor_service.build_diff("line1\nline2", "line1\nline3")
    assert isinstance(diff.diff, str)
    assert diff.added >= 1
    assert diff.removed >= 1


def test_fact_check_report_blocks_low_confidence_claims():
    text = "قالت الجهة إن العدد بلغ 3 في 2026."
    report = smart_editor_service.fact_check_report(text=text, source_url=None, threshold=0.95)
    assert report["passed"] is False
    assert report["blocking_reasons"]
    assert report["claims"]


def test_quality_score_has_required_metrics():
    html = "<h1>عنوان</h1><p>قالت الوزارة إن الرقم 50 وتم الإعلان عنه اليوم في الجزائر.</p>"
    report = smart_editor_service.quality_score(title="عنوان", html=html, source_text="source")
    assert "score" in report
    assert "metrics" in report
    assert "clarity" in report["metrics"]
    assert "sources_attribution" in report["metrics"]

def test_fact_check_blocks_template_noise():
    noisy_text = "هذا نص فيه [اسم الجهة] و ??? ومثال يجب حذفه."
    report = smart_editor_service.fact_check_report(text=noisy_text, source_url=None, threshold=0.7)
    assert report["passed"] is False
    assert report["blocking_reasons"]
