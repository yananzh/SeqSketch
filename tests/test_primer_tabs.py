"""Pytest regression tests for Primer Design tabs.

Covers PrimerDesignTab (qPCR Primer Design) and PrimerAnalysisTab (Primer Analysis).
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
)

from main_window import MainWindow
from modules.primer3_gui import PrimerDesignTab
from modules.primer_analysis_tab import (
    PrimerAnalysisTab,
    _gc_percent,
)

# ── Helpers ────────────────────────────────────────────────────────────────


def _fake_dimer(*, dg=0.0, tm=0.0, ascii_structure=""):
    """Return a SimpleNamespace mimicking a primer3 dimer result."""
    return SimpleNamespace(dg=dg, tm=tm, ascii_structure=ascii_structure)


def _mock_primer3_for_analysis(monkeypatch, **overrides):
    """Install mock primer3 functions for PrimerAnalysisTab tests."""
    defaults = {
        "fwd_tm": 60.0,
        "rev_tm": 60.5,
        "fwd_hairpin": _fake_dimer(dg=-1.5, tm=35.0),
        "rev_hairpin": _fake_dimer(dg=-0.8, tm=28.0),
        "fwd_homodimer": _fake_dimer(),
        "rev_homodimer": _fake_dimer(),
        "heterodimer": _fake_dimer(dg=-2.0, tm=25.0),
    }
    params = {**defaults, **overrides}

    call_count = {"tm": 0}

    def _mock_tm(seq, mv_conc=50, dv_conc=3):
        call_count["tm"] += 1
        return params["fwd_tm"] if call_count["tm"] == 1 else params["rev_tm"]

    monkeypatch.setattr(
        "modules.primer_analysis_tab.primer3.calc_tm",
        _mock_tm,
    )
    monkeypatch.setattr(
        "modules.primer_analysis_tab.primer3.calc_hairpin",
        lambda seq, mv_conc=50, dv_conc=3: params["fwd_hairpin"],
    )
    monkeypatch.setattr(
        "modules.primer_analysis_tab.primer3.calc_homodimer",
        lambda seq, mv_conc=50, dv_conc=3: params["fwd_homodimer"],
    )
    monkeypatch.setattr(
        "modules.primer_analysis_tab.primer3.calc_heterodimer",
        lambda fwd, rev, mv_conc=50, dv_conc=3: params["heterodimer"],
    )
    monkeypatch.setattr("modules.primer_analysis_tab._HAS_PRIMER3", True)


# ── _gc_percent ────────────────────────────────────────────────────────────


def test_gc_percent_empty():
    assert _gc_percent("") == 0.0


def test_gc_percent_pure_at():
    assert _gc_percent("ATATATATAT") == 0.0


def test_gc_percent_pure_gc():
    assert _gc_percent("GCGCGCGCGC") == 100.0


def test_gc_percent_mixed():
    assert _gc_percent("ATGC") == 50.0


def test_gc_percent_lowercase():
    assert _gc_percent("atgc") == 50.0


# ── PrimerAnalysisTab: UI setup ────────────────────────────────────────────


def test_analysis_tab_has_expected_widgets(qapp):
    tab = PrimerAnalysisTab()
    assert isinstance(tab.fwd_edit, QLineEdit)
    assert isinstance(tab.rev_edit, QLineEdit)
    assert isinstance(tab.results_text, QTextEdit)
    assert tab.run_btn.text() == "Run"
    assert tab.example_btn.text() == "Example"
    assert tab.clear_btn.text() == "Clear"
    assert tab.help_btn.text() == "Help"


def test_analysis_tab_example_loads_sequences(qapp):
    tab = PrimerAnalysisTab()
    tab.example_btn.click()
    assert len(tab.fwd_edit.text()) > 0
    assert len(tab.rev_edit.text()) > 0
    assert "primer_example" in tab.status_label.text()


def test_analysis_tab_clear_resets_all(qapp, monkeypatch):
    _mock_primer3_for_analysis(monkeypatch)
    tab = PrimerAnalysisTab()
    tab.fwd_edit.setText("ATCGATCGATCGATCGATCG")
    tab.rev_edit.setText("GCTAGCTAGCTAGCTAGCTA")
    tab.run_analysis()
    assert tab._last_results

    tab.clear_btn.click()
    assert tab.fwd_edit.text() == ""
    assert tab.rev_edit.text() == ""
    assert tab._last_results == ""
    assert "Cleared" in tab.status_label.text()


# ── PrimerAnalysisTab: input validation ─────────────────────────────────────


def test_analysis_tab_empty_input_shows_error(qapp):
    tab = PrimerAnalysisTab()
    tab.run_analysis()
    assert "both forward and reverse" in tab.results_text.toPlainText().lower()


def test_analysis_tab_short_primers_shows_error(qapp):
    tab = PrimerAnalysisTab()
    tab.fwd_edit.setText("ATCG")
    tab.rev_edit.setText("GCTA")
    tab.run_analysis()
    assert "too short" in tab.results_text.toPlainText().lower()


def test_analysis_tab_invalid_bases_shows_error(qapp):
    tab = PrimerAnalysisTab()
    tab.fwd_edit.setText("ATCGXATCGATCGATCGATCG")
    tab.rev_edit.setText("GCTAGCTAGCTAGCTAGCTA")
    tab.run_analysis()
    assert "invalid bases" in tab.results_text.toPlainText().lower()


def test_analysis_tab_no_primer3_shows_error(qapp, monkeypatch):
    monkeypatch.setattr("modules.primer_analysis_tab._HAS_PRIMER3", False)
    tab = PrimerAnalysisTab()
    tab.fwd_edit.setText("ATCGATCGATCGATCGATCG")
    tab.rev_edit.setText("GCTAGCTAGCTAGCTAGCTA")
    tab.run_analysis()
    assert "not installed" in tab.results_text.toPlainText().lower()


# ── PrimerAnalysisTab: live length display ──────────────────────────────────


def test_analysis_tab_live_length_updates_on_input(qapp):
    tab = PrimerAnalysisTab()
    assert tab.fwd_len_label.text() == "0 nt"
    assert tab.rev_len_label.text() == "0 nt"

    tab.fwd_edit.setText("ATCGATCG")
    assert tab.fwd_len_label.text() == "8 nt"

    tab.rev_edit.setText("GCTAGCTA")
    assert tab.rev_len_label.text() == "8 nt"

    # With whitespace and lowercase — normalized length
    tab.fwd_edit.setText("atc gat cga tcg")
    assert tab.fwd_len_label.text() == "12 nt"


# ── PrimerAnalysisTab: analysis results ─────────────────────────────────────


def test_analysis_tab_produces_html_results(qapp, monkeypatch):
    _mock_primer3_for_analysis(monkeypatch)
    tab = PrimerAnalysisTab()
    tab.fwd_edit.setText("ATCGATCGATCGATCGATCG")
    tab.rev_edit.setText("GCTAGCTAGCTAGCTAGCTA")
    tab.run_analysis()

    html = tab.results_text.toHtml()
    assert "Primer Pair Analysis Results" in html
    assert "Tm" in html
    assert "GC%" in html
    assert "Hairpin" in html
    assert "Fwd" in tab.status_label.text()


def test_analysis_tab_quality_all_pass(qapp, monkeypatch):
    _mock_primer3_for_analysis(
        monkeypatch,
        fwd_tm=60.0,
        rev_tm=60.5,
    )
    tab = PrimerAnalysisTab()
    # Use primers with ~50% GC (ATCGATCGATCGATCGATCG = 10 GC / 20 = 50%)
    tab.fwd_edit.setText("ATCGATCGATCGATCGATCG")
    tab.rev_edit.setText("CGATCGATCGATCGATCGAT")
    tab.run_analysis()

    html = tab.results_text.toHtml()
    assert "All checks passed" in html


def test_analysis_tab_quality_with_warnings(qapp, monkeypatch):
    _mock_primer3_for_analysis(
        monkeypatch,
        fwd_tm=55.0,
        rev_tm=62.0,  # large Tm diff
        fwd_homodimer=_fake_dimer(dg=-4.0, ascii_structure="ATC\n |||\n TAG"),
    )
    tab = PrimerAnalysisTab()
    # Use GC-rich primers to trigger GC% warning
    tab.fwd_edit.setText("GCGCGCGCGCGCGCGCGCGC")
    tab.rev_edit.setText("CGCGCGCGCGCGCGCGCGCG")
    tab.run_analysis()

    html = tab.results_text.toHtml()
    assert "Tm difference" in html
    assert "GC%" in html  # GC % out of range warning


# ── PrimerAnalysisTab: template binding ─────────────────────────────────────


def test_analysis_tab_template_binding_detected(qapp, monkeypatch):
    _mock_primer3_for_analysis(monkeypatch)
    tab = PrimerAnalysisTab()
    # Template containing both primers
    template = "NNNNNATCGATCGATCGATCGATCGNNNNNNGCTAGCTAGCTAGCTAGCTANNNNN"
    tab.template_edit.setPlainText(template)
    tab.fwd_edit.setText("ATCGATCGATCGATCGATCG")
    tab.rev_edit.setText("GCTAGCTAGCTAGCTAGCTA")
    tab.run_analysis()

    html = tab.results_text.toHtml()
    assert "Template Binding" in html


def test_analysis_tab_template_binding_not_found(qapp, monkeypatch):
    _mock_primer3_for_analysis(monkeypatch)
    tab = PrimerAnalysisTab()
    # Template must be >= len(fwd) + len(rev) = 40 for binding check to run
    tab.template_edit.setPlainText("A" * 50)
    tab.fwd_edit.setText("ATCGATCGATCGATCGATCG")
    tab.rev_edit.setText("GCTAGCTAGCTAGCTAGCTA")
    tab.run_analysis()

    html = tab.results_text.toHtml()
    assert "NOT FOUND" in html


# ── PrimerAnalysisTab: _find_binding ────────────────────────────────────────


def test_analysis_tab_find_binding_forward_match():
    tab = PrimerAnalysisTab()
    pos = tab._find_binding("NNNATCGNNN", "ATCG")
    assert pos == 4  # 1-based


def test_analysis_tab_find_binding_reverse_complement_match():
    tab = PrimerAnalysisTab()
    # CGAT is reverse complement of ATCG
    pos = tab._find_binding("NNNCGATNNN", "ATCG")
    assert pos == 4


def test_analysis_tab_find_binding_no_match():
    tab = PrimerAnalysisTab()
    pos = tab._find_binding("NNNNNNNNNN", "ATCG")
    assert pos == -1


# ── PrimerDesignTab: UI setup ───────────────────────────────────────────────


def test_design_tab_has_expected_widgets(qapp):
    tab = PrimerDesignTab()
    assert isinstance(tab.seq_input, QTextEdit)
    assert isinstance(tab.results_table, QTableWidget)
    assert tab.design_button.text() == "Run"
    assert tab.example_seq_btn.text() == "Example"
    assert tab.help_btn.text() == "Help"
    assert tab.open_folder_btn.text() == "Result Folder"
    assert not tab.open_folder_btn.isEnabled()


def test_design_tab_example_loads_hbb_exon1(qapp):
    tab = PrimerDesignTab()
    tab.example_seq_btn.click()
    text = tab.seq_input.toPlainText()
    assert "HBB_exon1" in text or "Homo sapiens" in text
    assert "hbb_exon1" in tab.status_label.text()


def test_design_tab_clear_resets_all(qapp):
    tab = PrimerDesignTab()
    tab.example_seq_btn.click()
    assert tab.seq_input.toPlainText()

    tab.clear_seq_btn.click()
    assert tab.seq_input.toPlainText() == ""
    assert tab.results_table.rowCount() == 0
    assert tab._current_template_seq == ""
    assert "cleared" in tab.status_label.text().lower()


def test_design_tab_export_csv_enables_result_folder(qapp, monkeypatch, tmp_path):
    tab = PrimerDesignTab()
    tab.results_table.setRowCount(1)
    tab.results_table.setItem(0, 0, QTableWidgetItem("1"))
    tab.results_table.setItem(0, 1, QTableWidgetItem("Fwd"))
    tab.results_table.setItem(0, 2, QTableWidgetItem("ACGT" * 5))

    out_file = tmp_path / "results.csv"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(out_file), ""))
    )
    tab.export_results_csv()
    assert out_file.is_file()
    assert tab.open_folder_btn.isEnabled()
    assert tab._last_export_dir == str(tmp_path)

    tab.clear_seq_btn.click()
    assert not tab.open_folder_btn.isEnabled()


# ── PrimerDesignTab: sequence validation ────────────────────────────────────


def test_design_tab_normalize_fasta():
    tab = PrimerDesignTab()
    raw = ">test\nATCG\nATCG\n"
    result = tab._normalize_sequence(raw)
    assert result == "ATCGATCG"


def test_design_tab_normalize_raw():
    tab = PrimerDesignTab()
    result = tab._normalize_sequence("  atc gat cga  \n tcg  ")
    assert result == "ATCGATCGATCG"


def test_design_tab_validate_valid_sequence():
    tab = PrimerDesignTab()
    assert tab._validate_sequence("ATCGATCG") is True
    assert tab._validate_sequence("ATCGNATCG") is True


def test_design_tab_validate_invalid_sequence():
    tab = PrimerDesignTab()
    assert tab._validate_sequence("ATCXATCG") is False
    assert tab._validate_sequence("") is False


def test_design_tab_refuses_empty_sequence(qapp, monkeypatch):
    tab = PrimerDesignTab()
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: warnings.append(args))
    tab.start_design_task()
    assert len(warnings) == 1
    assert warnings[0][1] == "Input Error"
    assert "valid DNA template" in warnings[0][2]
    assert tab.design_button.isEnabled()
    assert tab.results_table.rowCount() == 0


def test_design_tab_refuses_short_sequence(qapp, monkeypatch):
    tab = PrimerDesignTab()
    tab.seq_input.setPlainText("ATCG")
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: warnings.append(args))
    tab.start_design_task()
    assert len(warnings) == 1
    assert "too short" in warnings[0][2]
    assert tab.design_button.isEnabled()
    assert tab.results_table.rowCount() == 0


def test_design_tab_refuses_invalid_bases(qapp, monkeypatch):
    tab = PrimerDesignTab()
    tab.seq_input.setPlainText("ATCGX" * 20)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: warnings.append(args))
    tab.start_design_task()
    assert len(warnings) == 1
    assert "A/C/G/T/U/N only" in warnings[0][2]
    assert tab.design_button.isEnabled()
    assert tab.results_table.rowCount() == 0


# ── PrimerDesignTab: parameter validation ───────────────────────────────────


def test_design_tab_param_validation_length_order(qapp, monkeypatch):
    tab = PrimerDesignTab()
    tab.p_len_min.setValue(25)
    tab.p_len_opt.setValue(20)
    tab.p_len_max.setValue(18)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)
    assert tab._validate_parameter_ranges() is False


def test_design_tab_param_validation_tm_order(qapp, monkeypatch):
    tab = PrimerDesignTab()
    tab.p_tm_min.setValue(63.0)
    tab.p_tm_opt.setValue(60.0)
    tab.p_tm_max.setValue(57.0)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)
    assert tab._validate_parameter_ranges() is False


def test_design_tab_param_validation_gc_order(qapp, monkeypatch):
    tab = PrimerDesignTab()
    tab.p_gc_min.setValue(60.0)
    tab.p_gc_opt.setValue(50.0)
    tab.p_gc_max.setValue(40.0)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)
    assert tab._validate_parameter_ranges() is False


def test_design_tab_param_validation_product_size(qapp, monkeypatch):
    tab = PrimerDesignTab()
    tab.prod_size_min.setValue(200)
    tab.prod_size_max.setValue(100)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)
    assert tab._validate_parameter_ranges() is False


def test_design_tab_param_validation_passes_with_defaults(qapp):
    tab = PrimerDesignTab()
    assert tab._validate_parameter_ranges() is True


# ── PrimerDesignTab: apply_standard_presets ─────────────────────────────────


def test_design_tab_apply_presets_resets_all_values(qapp):
    tab = PrimerDesignTab()
    # Change values away from defaults
    tab.p_len_opt.setValue(30)
    tab.p_tm_opt.setValue(70.0)
    tab.p_gc_opt.setValue(70.0)
    tab.num_primers_spin.setValue(20)
    tab.salt_mono_spin.setValue(100.0)
    tab.mg_spin.setValue(5.0)

    tab.apply_standard_presets()

    assert tab.p_len_opt.value() == 20
    assert tab.p_tm_opt.value() == 60.0
    assert tab.p_gc_opt.value() == 50.0
    assert tab.num_primers_spin.value() == 5
    assert tab.salt_mono_spin.value() == 50.0
    assert tab.mg_spin.value() == 3.0


# ── MainWindow: menu wiring ─────────────────────────────────────────────────


def test_main_window_opens_primer_design_tab(qapp):
    window = MainWindow()
    window.open_primer_design_tab()
    assert window.tabs.count() == 1
    assert window.tabs.tabText(0) == "qPCR Primer Design"


def test_main_window_opens_primer_analysis_tab(qapp):
    window = MainWindow()
    window.open_primer_analysis_tab()
    assert window.tabs.count() == 1
    assert window.tabs.tabText(0) == "Primer Analysis"


def test_main_window_primer_design_single_instance(qapp):
    """PrimerDesignTab is a single-instance tab (reused on second open)."""
    window = MainWindow()
    window.open_primer_design_tab()
    first = window.tabs.widget(0)
    window.open_primer_design_tab()
    assert window.tabs.count() == 1
    assert window.tabs.widget(0) is first


def test_main_window_primer_analysis_single_instance(qapp):
    """PrimerAnalysisTab is a single-instance tab (reused on second open)."""
    window = MainWindow()
    window.open_primer_analysis_tab()
    first = window.tabs.widget(0)
    window.open_primer_analysis_tab()
    assert window.tabs.count() == 1
    assert window.tabs.widget(0) is first


def test_primer_design_menu_action_triggers_tab(qapp):
    window = MainWindow()
    menu_bar = window.menuBar()
    primer_menu = next(
        action.menu() for action in menu_bar.actions() if action.text() == "Primer Design"
    )
    design_action = next(a for a in primer_menu.actions() if a.text() == "qPCR Primer Design")
    design_action.trigger()
    assert window.tabs.count() == 1
    assert window.tabs.tabText(0) == "qPCR Primer Design"


def test_primer_analysis_menu_action_triggers_tab(qapp):
    window = MainWindow()
    menu_bar = window.menuBar()
    primer_menu = next(
        action.menu() for action in menu_bar.actions() if action.text() == "Primer Design"
    )
    analysis_action = next(a for a in primer_menu.actions() if a.text() == "Primer Analysis")
    analysis_action.trigger()
    assert window.tabs.count() == 1
    assert window.tabs.tabText(0) == "Primer Analysis"
