import os
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from main_window import MainWindow
from modules.complement_tab import ComplementTab
from modules.codon_usage_tab import CodonUsageTab
from modules.orf_tab import ORFTab
from modules.rna_tab import RNATab
from modules.sanger_tab import SangerTab
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


def test_dna_analysis_sequence_editors_use_shared_border_style(qapp):
    sequence_tabs = [RNATab(), ComplementTab(), TranslateTab(), ORFTab()]

    for tab in sequence_tabs:
        for editor in (tab.input_text, tab.output_text):
            assert editor.property("sequenceEditorStyled") is True
            assert "border-radius" in editor.styleSheet()
            assert "border: 1px solid #94a3b8;" in editor.styleSheet()
            assert not editor.styleSheet().lstrip().startswith("QTextEdit")

    sanger_tab = SangerTab()
    for editor in (
        sanger_tab.fwd_edit,
        sanger_tab.rev_edit,
        sanger_tab.assembly_result,
    ):
        assert editor.property("sequenceEditorStyled") is True
        assert "border-radius" in editor.styleSheet()
        assert "border: 1px solid #94a3b8;" in editor.styleSheet()
        assert not editor.styleSheet().lstrip().startswith("QTextEdit")


def test_codon_usage_summary_tables_are_taller_and_rscu_labels_are_tighter(qapp):
    tab = CodonUsageTab()

    assert tab._stats_table.minimumHeight() >= 280
    assert tab._top10_table.minimumHeight() >= 260

    tab._draw_rscu_chart({
        "header": "Example",
        "rows": [
            {"codon": "AAA", "rscu": 1.2},
            {"codon": "AAG", "rscu": 0.8},
            {"codon": "ATG", "rscu": 1.0},
            {"codon": "TAA", "rscu": 0.4},
        ],
    })

    ax = tab._rscu_fig.axes[0]
    aa_label_ys = [text.get_position()[1] for text in ax.texts]

    assert aa_label_ys
    assert max(aa_label_ys) >= -0.18
