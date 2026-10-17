"""Theme switching, lazy widgets and persisted user preferences."""

import json

import pytest
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QLabel

from config.settings import Settings
from main_window import MainWindow
from utils.themes import theme_manager


@pytest.fixture
def theme_settings(qapp, monkeypatch, tmp_path):
    path = tmp_path / "config.json"
    monkeypatch.setattr("main_window.Settings", lambda: Settings(str(path)))
    theme_manager().apply("light")
    yield path
    theme_manager().apply("light")


def test_menu_switch_preserves_sequence_and_restores_light(qapp, theme_settings):
    window = MainWindow()
    window.open_complement_tab()
    tab = window.tabs.currentWidget()
    tab.input_text.setPlainText(">example\nATGC")
    original = tab.input_text.styleSheet()
    window.theme_actions["dark"].trigger()

    assert window.current_theme == "dark"
    assert window.theme_actions["dark"].isChecked()
    assert not window.theme_actions["light"].isChecked()
    assert tab.input_text.toPlainText() == ">example\nATGC"
    assert "#171c24" in tab.input_text.styleSheet()
    assert qapp.palette().color(QPalette.ColorRole.Text).name() == "#e2e8f0"
    assert Settings(str(theme_settings)).get("window.theme") == "dark"

    window.theme_actions["light"].trigger()
    assert tab.input_text.styleSheet() == original
    assert qapp.palette().color(QPalette.ColorRole.PlaceholderText).name() == "#888888"
    window.close()


def test_dark_theme_handles_new_tabs_and_local_style_changes(qapp, theme_settings):
    window = MainWindow()
    window.set_theme("dark")
    window.open_filter_by_length_tab()
    window.show()
    qapp.processEvents()
    tab = window.tabs.currentWidget()
    assert "#171c24" in tab.log_area.styleSheet()
    assert "#e2e8f0" in tab.log_area.styleSheet()

    window.open_complement_tab()
    qapp.processEvents()
    sequence_tab = window.tabs.currentWidget()
    assert "border: none;" in sequence_tab.input_text.styleSheet()
    assert "border: 1px" not in sequence_tab.input_text.styleSheet()

    hint = QLabel("Hint", tab)
    hint.setStyleSheet("color: #888; background: #ffffff;")
    hint.ensurePolished()
    assert "#a0adbe" in hint.styleSheet()
    assert "#171c24" in hint.styleSheet()
    hint.setStyleSheet("color: #333; background: #f7f9fc;")
    assert "#e2e8f0" in hint.styleSheet()
    window.set_theme("light")
    assert hint.styleSheet() == "color: #333; background: #f7f9fc;"
    window.close()


def test_saved_theme_loaded_on_next_window(qapp, theme_settings):
    window = MainWindow()
    window.set_theme("dark")
    window.close()
    restored = MainWindow()
    assert restored.current_theme == "dark"
    assert restored.theme_actions["dark"].isChecked()
    assert qapp.palette().color(QPalette.ColorRole.Base).name() == "#171c24"
    restored.close()


@pytest.mark.parametrize(
    "saved",
    [
        {"window": {"theme": "missing"}},
        {"window": {"theme": []}},
        {"window": None},
        [],
        None,
    ],
)
def test_invalid_preferences_fall_back_to_light(qapp, theme_settings, saved):
    theme_settings.write_text(json.dumps(saved), encoding="utf-8")
    window = MainWindow()
    assert window.current_theme == "light"
    assert window.theme_actions["light"].isChecked()
    window.close()


def test_theme_recolor_keeps_white_button_text(qapp, theme_settings):
    manager = theme_manager()
    manager.name = "dark"
    style = manager.recolor("background: #ffffff; color: #ffffff;")
    assert style == "background: #171c24; color: #ffffff;"
