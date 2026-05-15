import os
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from main_window import MainWindow
from modules.complement_tab import ComplementTab
from modules.orf_tab import ORFTab
from modules.translate_tab import TranslateTab


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app = cast(QApplication, app)
    app.setQuitOnLastWindowClosed(False)
    return app


def test_complement_tools_switches_between_modes(qapp):
    tab = ComplementTab()

    assert hasattr(tab, "mode_combo")

    tab.input_text.setPlainText("ATGC")
    tab.mode_combo.setCurrentText("Complement")
    tab.run()
    assert tab.output_text.toPlainText() == "TACG"

    tab.mode_combo.setCurrentText("Reverse Complement")
    tab.run()
    assert tab.output_text.toPlainText() == "GCAT"


def test_main_window_reuses_single_complement_tools_tab(qapp):
    window = MainWindow()

    window.open_complement_tab()

    assert window.tabs.count() == 1
    assert window.tabs.tabText(0) == "Complement/Reverse Complement"

    first_tab = window.tabs.widget(0)
    window.open_reverse_complement_tab()

    assert window.tabs.count() == 1
    assert window.tabs.currentWidget() is first_tab
    assert first_tab.mode_combo.currentText() == "Reverse Complement"


def test_dna_analysis_menu_uses_single_complement_tools_entry(qapp):
    window = MainWindow()
    menu_bar = window.menuBar()
    dna_menu = next(
        action.menu()
        for action in menu_bar.actions()
        if action.text() == "DNA Analysis"
    )
    action_texts = [action.text() for action in dna_menu.actions() if action.text()]

    assert "Complement/Reverse Complement" in action_texts
    assert "Reverse Complement" not in action_texts


def test_translate_and_orf_warn_that_only_single_sequence_is_supported(qapp):
    translate_tab = TranslateTab()
    orf_tab = ORFTab()

    assert "multi-sequence" in translate_tab.input_hint.text().lower()
    assert "single sequence only" in orf_tab.input_hint.text().lower()
