import os
from pathlib import Path
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
    assert window.tabs.tabText(0) == "Complement Tools"

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

    assert "Complement Tools" in action_texts
    assert "Reverse Complement" not in action_texts


def test_translate_and_orf_warn_that_only_single_sequence_is_supported(qapp):
    translate_tab = TranslateTab()
    orf_tab = ORFTab()

    assert "single sequence only" in translate_tab.input_hint.text().lower()
    assert "single sequence only" in orf_tab.input_hint.text().lower()


def test_orf_finder_uses_file_inputs_and_defaults_to_both_strands(qapp, tmp_path: Path):
    tab = ORFTab()

    assert hasattr(tab, "input_edit")
    assert hasattr(tab, "output_edit")
    assert tab.chain_box.currentText() == "Both strands"


def test_orf_finder_runs_from_fasta_file_and_writes_report(qapp, tmp_path: Path):
    input_path = tmp_path / "orf_input.fasta"
    output_path = tmp_path / "orf_report.txt"
    input_path.write_text(
        ">seq1\nATGAAACCCGGGTTTAAATAG\n",
        encoding="utf-8",
    )
    tab = ORFTab()

    tab.input_edit.setText(str(input_path))
    tab.output_edit.setText(str(output_path))
    tab.min_len_box.setValue(18)
    tab.run_orf_finder()

    assert output_path.exists()
    report_text = output_path.read_text(encoding="utf-8")
    assert "ORF #1" in report_text
    assert "Frame:" in report_text
    assert tab.status_label.text().startswith("Found")


def test_orf_finder_gene_map_can_be_saved_as_png_and_pdf(qapp, tmp_path: Path):
    input_path = tmp_path / "orf_input.fasta"
    report_path = tmp_path / "orf_report.txt"
    png_path = tmp_path / "orf_map.png"
    pdf_path = tmp_path / "orf_map.pdf"
    input_path.write_text(
        ">seq1\nATGAAACCCGGGTTTAAATAG\n",
        encoding="utf-8",
    )
    tab = ORFTab()

    tab.input_edit.setText(str(input_path))
    tab.output_edit.setText(str(report_path))
    tab.min_len_box.setValue(18)
    tab.run_orf_finder()

    assert tab.save_gene_map(str(png_path)) is True
    assert tab.save_gene_map(str(pdf_path)) is True
    assert png_path.exists()
    assert pdf_path.exists()
