from datetime import datetime

from app.msi.nodes import MsiGraphNodes
from app.msi.service import MsiMonitorService


def test_msi_level_mapping():
    assert MsiGraphNodes._msi_level(90) == "GREEN"
    assert MsiGraphNodes._msi_level(70) == "YELLOW"
    assert MsiGraphNodes._msi_level(50) == "ORANGE"
    assert MsiGraphNodes._msi_level(20) == "RED"


def test_js_divergence_zero_when_equal():
    d = {"سياسة": 0.5, "اقتصاد": 0.5}
    value = MsiGraphNodes._js_divergence(d, d)
    assert value == 0.0


def test_compute_window_daily_default_is_24h():
    service = MsiMonitorService()
    start, end = service.compute_window("daily")
    delta = end - start
    assert 23 <= delta.total_seconds() / 3600 <= 25


def test_compute_window_custom_range_is_preserved():
    service = MsiMonitorService()
    custom_start = datetime(2026, 2, 1, 0, 0, 0)
    custom_end = datetime(2026, 2, 8, 0, 0, 0)
    start, end = service.compute_window("weekly", start=custom_start, end=custom_end)
    assert start == custom_start
    assert end == custom_end
