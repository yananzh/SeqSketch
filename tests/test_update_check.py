"""Update check: pure version helpers, GitHub fetch, and About-dialog wiring."""

import json
import os
import time
import urllib.error

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QDialog, QMessageBox, QPushButton

from main_window import MainWindow, UpdateCheckWorker
from utils.app_version import APP_VERSION
from utils.update_check import fetch_latest_version, is_newer_version, parse_version


class _FakeResponse:
    def __init__(self, payload):
        self._data = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_parse_version_extracts_numeric_tuple():
    assert parse_version("v1.2.3") == (1, 2, 3)
    assert parse_version("1.10.0") == (1, 10, 0)
    assert parse_version("v2.0.0-beta") == (2, 0, 0)
    assert parse_version("") == ()
    assert parse_version(None) == ()


def test_is_newer_version_compares_numerically():
    assert is_newer_version("1.0.0", "v1.0.1")
    assert is_newer_version("1.0.0", "1.1")
    assert not is_newer_version("1.0.0", "1.0.0")
    assert not is_newer_version("1.0.0", "v0.9.0")
    assert not is_newer_version("1.10.0", "1.9.9")


def test_fetch_latest_version_reads_tag_and_sends_user_agent(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout=None):
        requests.append(request)
        return _FakeResponse({"tag_name": "v1.2.3"})

    monkeypatch.setattr("utils.update_check.urllib.request.urlopen", fake_urlopen)

    assert fetch_latest_version(timeout=1.0) == "1.2.3"
    user_agent = requests[0].headers.get("User-agent", "")
    assert user_agent.startswith("SeqSketch/")
    assert requests[0].full_url.startswith("https://api.github.com/repos/")


def test_fetch_latest_version_falls_back_to_name(monkeypatch):
    monkeypatch.setattr(
        "utils.update_check.urllib.request.urlopen",
        lambda request, timeout=None: _FakeResponse({"name": "v3.2.1"}),
    )
    assert fetch_latest_version() == "3.2.1"


def test_fetch_latest_version_raises_without_tag(monkeypatch):
    monkeypatch.setattr(
        "utils.update_check.urllib.request.urlopen",
        lambda request, timeout=None: _FakeResponse({"info": "none"}),
    )
    try:
        fetch_latest_version()
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for payload without tag_name")


def test_worker_emits_latest_version(qapp, monkeypatch):
    monkeypatch.setattr(
        "main_window.fetch_latest_version", lambda timeout=5.0: "9.9.9"
    )
    worker = UpdateCheckWorker()
    results = []
    worker.finished.connect(results.append)
    worker.run()
    assert results == ["9.9.9"]


def test_worker_emits_error_on_network_failure(qapp, monkeypatch):
    def boom(timeout=5.0):
        raise urllib.error.URLError("no network")

    monkeypatch.setattr("main_window.fetch_latest_version", boom)
    worker = UpdateCheckWorker()
    errors = []
    worker.error.connect(errors.append)
    worker.run()
    assert len(errors) == 1
    assert "no network" in errors[0]


def test_settings_menu_has_no_check_for_updates_entry(qapp):
    window = MainWindow()
    settings_menu = next(
        action.menu()
        for action in window.menuBar().actions()
        if action.text() == "Settings"
    )
    texts = [action.text() for action in settings_menu.actions() if action.text()]
    assert "Check for Updates" not in texts
    assert "About" in texts


def test_about_dialog_contains_check_for_updates_button(qapp, monkeypatch):
    window = MainWindow()
    captured = {}
    monkeypatch.setattr(QDialog, "exec", lambda self: captured.setdefault("dlg", self))

    window.show_about_dialog()

    buttons = captured["dlg"].findChildren(QPushButton)
    assert [b.text() for b in buttons] == ["Check for Updates"]


def test_check_for_updates_reports_up_to_date(qapp, monkeypatch):
    monkeypatch.setattr(
        "main_window.fetch_latest_version", lambda timeout=5.0: APP_VERSION
    )
    shown = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args, **kwargs: shown.append(args)
    )
    window = MainWindow()

    window.check_for_updates()
    deadline = time.time() + 5
    while window._update_worker is not None and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    qapp.processEvents()

    assert window._update_worker is None
    assert window._update_thread is None
    assert len(shown) == 1
    assert f"v{APP_VERSION} is up to date" in shown[0][2]


def test_check_for_updates_ignores_concurrent_clicks(qapp, monkeypatch):
    def slow_fetch(timeout=5.0):
        time.sleep(0.3)
        return APP_VERSION

    monkeypatch.setattr("main_window.fetch_latest_version", slow_fetch)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    window = MainWindow()

    window.check_for_updates()
    assert window._update_worker is not None
    window.check_for_updates()  # second click while the first check runs

    deadline = time.time() + 5
    while window._update_worker is not None and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    qapp.processEvents()

    assert window._update_worker is None
