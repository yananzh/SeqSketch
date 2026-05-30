import os
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QPushButton

from main_window import MainWindow
from modules.blast_local_tab import BlastLocalTab


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app = cast(QApplication, app)
    app.setQuitOnLastWindowClosed(False)
    return app


def test_local_blast_tab_uses_step_by_step_copy_and_shared_query_editor_style(
    qapp, monkeypatch
):
    monkeypatch.setattr(
        "modules.blast_local_tab.get_blast_bin_dir", lambda: r"C:\blast\bin"
    )

    tab = BlastLocalTab()

    assert [tab._inner.tabText(i) for i in range(tab._inner.count())] == [
        "Step 1: Build Database",
        "Step 2: Run Query",
    ]

    assert tab.path_row.count() >= 4
    assert tab.blast_path_edit.text() == r"C:\blast\bin"
    assert tab.blast_path_edit.placeholderText() == "Select BLAST+ bin directory"

    assert not hasattr(tab._build_tab, "hero_title")
    assert not hasattr(tab._build_tab, "hero_body")
    assert not hasattr(tab._build_tab, "workflow_tip")
    assert tab._build_tab.fasta_edit.placeholderText() == "Select FASTA file"
    assert tab._build_tab.name_edit.placeholderText() == "my_reference_db"

    assert tab._run_tab.query_edit.property("sequenceEditorStyled") is True
    assert not hasattr(tab._run_tab, "hero_title")
    assert not hasattr(tab._run_tab, "hero_body")
    assert not hasattr(tab._run_tab, "workflow_tip")
    assert tab._run_tab.query_edit.minimumHeight() <= 140
    assert tab._run_tab.query_edit.placeholderText().startswith(
        "Paste FASTA query here"
    )
    assert "drag and drop" in tab._run_tab.query_edit.placeholderText().lower()
    assert "Protein example:" not in tab._run_tab.query_edit.placeholderText()
    assert "Load FASTA File" not in [
        button.text() for button in tab._run_tab.findChildren(QPushButton)
    ]
    assert not hasattr(tab._run_tab, "prog_tip_lbl")
    assert tab._run_tab.search_top_row.count() >= 4
    assert tab._run_tab.parameter_row.count() >= 6
    assert tab._run_tab.output_row.count() >= 4


def test_blast_menu_uses_single_local_blast_action(qapp, monkeypatch):
    monkeypatch.setattr(
        "modules.blast_local_tab.get_blast_bin_dir", lambda: r"C:\blast\bin"
    )

    window = MainWindow()
    menu_bar = window.menuBar()
    blast_menu = next(
        action.menu() for action in menu_bar.actions() if action.text() == "BLAST"
    )

    local_blast_action = next(
        action for action in blast_menu.actions() if action.text() == "Local BLAST"
    )

    assert local_blast_action.menu() is None
    assert "1. Build BLAST Database..." not in [
        action.text() for action in blast_menu.actions() if action.text()
    ]
    assert "2. Run BLAST Query..." not in [
        action.text() for action in blast_menu.actions() if action.text()
    ]

    local_blast_action.trigger()

    assert window.tabs.count() == 1
    assert window.tabs.tabText(0) == "Local BLAST"
    assert isinstance(window.tabs.widget(0), BlastLocalTab)
