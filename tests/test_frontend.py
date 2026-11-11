"""The Streamlit demo renders without errors even when the API is down (no API, no model needed)."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "frontend" / "app.py"


def test_demo_ui_renders_and_reports_unreachable_api(monkeypatch):
    monkeypatch.setenv("P14_URL", "http://127.0.0.1:9")  # nothing listens there
    at = AppTest.from_file(str(APP), default_timeout=30)
    at.run()
    assert not at.exception
    assert any("not reachable" in e.value for e in at.sidebar.error)
    assert not at.sidebar.code and not at.sidebar.help  # no stray "magic" output
    assert "employee" in at.sidebar.selectbox[0].options
