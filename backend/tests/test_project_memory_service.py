from app.services.project_memory_service import ProjectMemoryService


def test_normalize_tags_deduplicates_and_limits():
    svc = ProjectMemoryService()
    tags = svc._normalize_tags(["  Auth ", "auth", "telegram", "", "  memory "])
    assert tags == ["auth", "telegram", "memory"]


def test_normalize_text_compacts_spaces():
    svc = ProjectMemoryService()
    assert svc._normalize_text("  hello   world \n  test ") == "hello world test"
