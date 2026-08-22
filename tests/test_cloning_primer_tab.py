"""Pytest regression tests for the Cloning Primer Design tab."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QComboBox, QGroupBox, QSizePolicy, QTableWidget, QTextEdit

import modules.cloning_primer_tab as tab_module
from main_window import MainWindow
from modules.cloning_primer_tab import (
    CLONING_ENZYMES,
    CloningPrimerTab,
    count_fasta_records,
    design_cloning_primers,
    find_site_positions,
    gc_percent,
    normalize_sequence,
    reverse_complement,
)

_ENZ = {e[0]: e for e in CLONING_ENZYMES}


# ── Core helpers (no GUI) ────────────────────────────────────────────────────


def test_normalize_sequence_strips_fasta_and_uppercases():
    assert normalize_sequence(">hdr\natg cga\ntgc\n") == "ATGCGATGC"
    assert normalize_sequence("  aTc  gAa   ") == "ATCGAA"


def test_reverse_complement():
    assert reverse_complement("ATGCAT") == "ATGCAT"
    assert reverse_complement("ATCG") == "CGAT"
    assert reverse_complement(reverse_complement("GATTACA")) == "GATTACA"


def test_gc_percent():
    assert abs(gc_percent("ATAT") - 0.0) < 1e-9
    assert abs(gc_percent("GCGC") - 100.0) < 1e-9
    assert abs(gc_percent("ATgC") - 50.0) < 1e-9


def test_find_site_positions_forward():
    site = _ENZ["EcoRI"][1]  # GAATTC
    hits = find_site_positions("AAAGAATTCCC", site)
    assert (3, "fwd") in hits
    assert (3, "rev") in hits  # palindrome site detected on both strands


def test_find_site_positions_absent():
    assert find_site_positions("ATCGATCGATGCTAGCTA", _ENZ["BamHI"][1]) == []


def test_iupac_regex_handles_ambiguity():
    # "N" in a site tiles any base: site GNNGG matches "GGAGG".
    hits = find_site_positions("GGAGG", "GNNGG")
    assert (0, "fwd") in hits


def test_count_fasta_records():
    assert count_fasta_records("ATGC") == 0
    assert count_fasta_records(">seq1\nATGC") == 1
    assert count_fasta_records(">a\nA\n>b\nC\n") == 2


# ── design_cloning_primers (primers, frames, overhangs) ─────────────────────


@pytest.fixture
def no_primer3(monkeypatch):
    """Force the deterministic Wallace-rule Tm fallback for the design tests."""
    monkeypatch.setattr(tab_module, "_HAS_PRIMER3", False)
    monkeypatch.setattr(tab_module, "_primer3", None)


SEQ = "ATGGCCAAGCTTCGATCGATCGATCGATCGGGGCCGCCCCCGGGTAATAGC" + "GTAC" * 10


def test_design_builds_fwd_and_rev_cores(no_primer3):
    design = design_cloning_primers(SEQ, _ENZ["EcoRI"], _ENZ["BamHI"], core_len=20)
    fwd, rev = design["fwd"], design["rev"]
    # Forward core starts at insert base 1.
    assert fwd["full"].endswith(SEQ[: len(fwd["core"])])
    assert fwd["full"].startswith("GG" + "GAATTC")  # protection + EcoRI site
    # Reverse core covers the 3' end; 3' end order primer is 5'->3'.
    assert reverse_complement(rev["core"]) == SEQ[len(SEQ) - len(rev["core"]) :]
    assert rev["full"].startswith("GG" + "GGATCC")


def test_design_overhang_uses_protection_bases(no_primer3):
    design = design_cloning_primers(SEQ, _ENZ["SalI"], _ENZ["NotI"], core_len=20)
    assert design["fwd"]["overhang"].startswith("G" * 4 + "GTCGAC")
    assert design["rev"]["overhang"].startswith("G" * 4 + "GCGGCCGC")


def test_design_preserve_frame_adds_bases(no_primer3):
    # EcoRI remnant len 5 -> 1 added base; PstI remnant len 1 -> 2 added.
    eco = design_cloning_primers(
        SEQ, _ENZ["EcoRI"], None, core_len=20, preserve_frame=True
    )
    assert eco["fwd"]["overhang"] == "GG" + "GAATTC" + "A"
    assert "1 frame base" in eco["fwd"]["flags"][0]

    pst = design_cloning_primers(
        SEQ, _ENZ["PstI"], None, core_len=20, preserve_frame=True
    )
    assert pst["fwd"]["overhang"] == "GGG" + "CTGCAG" + "AA"
    assert "2 frame base" in pst["fwd"]["flags"][0]


def test_design_no_added_bases_when_frame_ok(no_primer3):
    # SmaI remnant len 3 already divisible by 3 -> no added bases.
    sma = design_cloning_primers(
        SEQ, _ENZ["SmaI"], None, core_len=20, preserve_frame=True
    )
    assert sma["fwd"]["overhang"] == "GGG" + "CCCGGG"


def test_design_without_enzymes_adds_no_overhang(no_primer3):
    design = design_cloning_primers(SEQ, None, None, core_len=20)
    assert design["fwd"]["overhang"] == ""
    assert design["rev"]["overhang"] == ""
    assert design["fwd"]["full"] == design["fwd"]["core"]
    assert design["rev"]["full"] == design["rev"]["core"]


def test_design_too_short_sequence(no_primer3):
    with pytest.raises(ValueError):
        design_cloning_primers("ATG" * 5, _ENZ["EcoRI"], _ENZ["BamHI"], core_len=20)


def test_design_flags_internal_cut_site(no_primer3):
    # An extra internal EcoRI site should be reported as a warning; a clean
    # sequence (no GAATTC/GGATCC) should not.
    dirty = "ATG" + "GAATTC" + SEQ[3:]
    design = design_cloning_primers(dirty, _ENZ["EcoRI"], _ENZ["BamHI"], core_len=20)
    assert any("EcoRI cuts inside the insert" in w for w in design["warnings"])

    clean = design_cloning_primers(SEQ, _ENZ["EcoRI"], _ENZ["BamHI"], core_len=20)
    assert clean["warnings"] == []


# ── Tab UI (offscreen GUI) ───────────────────────────────────────────────────


def test_tab_has_expected_widgets(qapp):
    tab = CloningPrimerTab()
    assert isinstance(tab.input_text, QTextEdit)
    assert isinstance(tab.results_table, QTableWidget)
    assert isinstance(tab.enz5_combo, QComboBox)
    assert tab.enz5_combo.currentText() == "EcoRI"
    assert tab.enz3_combo.currentText() == "BamHI"
    assert tab.example_btn.text() == "Example"


def test_tab_example_loads_insert(qapp):
    tab = CloningPrimerTab()
    tab.example_btn.click()
    assert tab.input_text.toPlainText().strip().startswith(">")
    assert "ATG" in tab.input_text.toPlainText()
    assert "example" in tab.status_label.text().lower()


def test_tab_run_fills_table(qapp, monkeypatch):
    monkeypatch.setattr(tab_module, "_HAS_PRIMER3", False)
    monkeypatch.setattr(tab_module, "_primer3", None)
    tab = CloningPrimerTab()
    tab.example_btn.click()
    tab.run()
    assert tab.results_table.rowCount() == 2
    assert tab.results_table.item(0, 0).text().startswith("Fwd")
    assert tab.results_table.item(1, 0).text().startswith("Rev")
    assert tab.results_table.item(0, 1).text().startswith("GGGAATTC")
    assert "Designed" in tab.status_label.text()


def test_tab_hides_output_result_group(qapp):
    tab = CloningPrimerTab()
    assert tab.output_group.isHidden()


def test_tab_parameter_row_fills_width_in_equal_quarters(qapp):
    """The single-row parameter area fills the group box at the app's default
    window width: each control expands past the old 90px fixed width, the four
    quarters share the row evenly, and the row reaches the right edge."""
    tab = CloningPrimerTab()
    tab.resize(920, 700)  # MainWindow's default and minimum size
    tab.show()
    qapp.processEvents()

    controls = [tab.enz5_combo, tab.enz3_combo, tab.core_len_spin, tab.target_tm_spin]
    widths = [c.width() for c in controls]
    assert all(w > 100 for w in widths), f"controls did not expand: {widths}"
    assert max(widths) - min(widths) <= 30, f"quarters uneven: {widths}"

    grp = next(
        g for g in tab.findChildren(QGroupBox) if "Cloning Parameters" in g.title()
    )
    tm = tab.target_tm_spin
    right_edge = tm.mapTo(grp, tm.rect().topLeft()).x() + tm.width()
    assert right_edge >= grp.width() - 40, "parameter row does not reach the right edge"


def test_tab_example_and_upload_share_bottom_row(qapp):
    tab = CloningPrimerTab()
    # Both buttons live in the input group on one row, expanding to fill it.
    assert tab.example_btn.parent() is tab.input_group
    assert tab.upload_btn.parent() is tab.input_group
    assert (
        tab.example_btn.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    )
    assert (
        tab.upload_btn.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    )
    # Buttons share one row, which is the last item in the group layout
    # (pinned to the bottom edge).
    layout = tab.input_group.layout()
    row = layout.itemAt(layout.count() - 1).layout()
    assert row.count() == 2
    assert row.itemAt(0).widget() is tab.example_btn
    assert row.itemAt(1).widget() is tab.upload_btn


def test_tab_run_empty_input_shows_status(qapp):
    tab = CloningPrimerTab()
    tab.run()
    assert "paste" in tab.status_label.text().lower()


def test_tab_run_rejects_multi_sequence_input(qapp, monkeypatch):
    monkeypatch.setattr(tab_module, "_HAS_PRIMER3", False)
    monkeypatch.setattr(tab_module, "_primer3", None)
    tab = CloningPrimerTab()
    tab.input_text.setPlainText(">seq1\nATGC\n>seq2\nGGCC\n")
    tab.run()
    assert tab.results_table.rowCount() == 0
    assert "one" in tab.status_label.text().lower()


def _patch_messagebox(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "modules.cloning_primer_tab.QMessageBox.warning",
        lambda *a, **k: calls.append(a) or None,
    )
    return calls


def test_tab_run_warns_internal_cut_site(qapp, monkeypatch):
    monkeypatch.setattr(tab_module, "_HAS_PRIMER3", False)
    monkeypatch.setattr(tab_module, "_primer3", None)
    calls = _patch_messagebox(monkeypatch)
    tab = CloningPrimerTab()
    # Insert with an internal EcoRI site (GAATTC at position 4).
    tab.input_text.setPlainText("ATGGAATTC" + "G" * 100 + "TAA")
    tab.run()
    assert tab.results_table.rowCount() == 2
    assert any("EcoRI" in str(c) for c in calls)


def test_tab_run_clean_sequence_no_cut_site_popup(qapp, monkeypatch):
    monkeypatch.setattr(tab_module, "_HAS_PRIMER3", False)
    monkeypatch.setattr(tab_module, "_primer3", None)
    calls = _patch_messagebox(monkeypatch)
    tab = CloningPrimerTab()
    tab.example_btn.click()  # example has no internal EcoRI/BamHI sites
    tab.run()
    assert calls == []


def test_tab_open_file_rejects_multi_record_file(qapp, monkeypatch, tmp_path):
    path = tmp_path / "multi.fasta"
    path.write_text(">seq1\nATGC\n>seq2\nGGCC\n", encoding="utf-8")
    monkeypatch.setattr(
        "modules.cloning_primer_tab.QFileDialog.getOpenFileName",
        lambda *a, **k: (str(path), "FASTA/TXT (*.fasta)"),
    )
    monkeypatch.setattr(
        "modules.cloning_primer_tab.QMessageBox.warning", lambda *a, **k: None
    )
    tab = CloningPrimerTab()
    tab.open_file()
    assert tab.input_text.toPlainText() == ""


def test_tab_run_no_enzyme_designs_blunt_primers(qapp, monkeypatch):
    monkeypatch.setattr(tab_module, "_HAS_PRIMER3", False)
    monkeypatch.setattr(tab_module, "_primer3", None)
    tab = CloningPrimerTab()
    tab.input_text.setPlainText("ATG" + "G" * 200)
    tab.enz5_combo.setCurrentIndex(tab.enz5_combo.count() - 1)  # None
    tab.enz3_combo.setCurrentIndex(tab.enz3_combo.count() - 1)  # None
    tab.run()
    assert tab.results_table.rowCount() == 2
    assert tab.results_table.item(0, 3).text() == ""  # no overhang
    assert "Designed" in tab.status_label.text()


def test_tab_run_same_enzyme_warns(qapp, monkeypatch):
    monkeypatch.setattr(tab_module, "_HAS_PRIMER3", False)
    monkeypatch.setattr(tab_module, "_primer3", None)
    tab = CloningPrimerTab()
    tab.input_text.setPlainText("ATG" + "G" * 200)
    tab.enz3_combo.setCurrentIndex(0)  # same enzyme (EcoRI) on both ends
    tab.run()
    assert tab.results_table.rowCount() == 2
    assert "Designed" in tab.status_label.text()


def test_tab_clear_resets_table(qapp):
    tab = CloningPrimerTab()
    tab.clear()
    assert tab.results_table.rowCount() == 0
    assert tab._last_design is None


# ── Export Table ─────────────────────────────────────────────────────────────


def test_export_delimited_writes_tsv(tmp_path):
    path = tmp_path / "out.tsv"
    headers = ["Primer", "Full Sequence (5'→3')", "Tm (°C)"]
    rows = [["Fwd (EcoRI)", "GGGAATTCATGC", "60.0"]]
    CloningPrimerTab._export_delimited(str(path), headers, rows, "\t")
    lines = path.read_text(encoding="utf-8-sig").strip().splitlines()
    assert lines[0].split("\t") == headers
    assert lines[1].split("\t") == rows[0]


def test_export_delimited_writes_csv(tmp_path):
    path = tmp_path / "out.csv"
    headers = ["Primer", "Tm (°C)"]
    rows = [["Rev (BamHI)", "60.0"]]
    CloningPrimerTab._export_delimited(str(path), headers, rows, ",")
    lines = path.read_text(encoding="utf-8-sig").strip().splitlines()
    assert lines[1].split(",") == rows[0]


def test_export_excel_writes_rows(tmp_path):
    path = tmp_path / "out.xlsx"
    headers = ["Primer", "GC (%)"]
    rows = [["Fwd (EcoRI)", "42.9"], ["Rev (BamHI)", "36.4"]]
    CloningPrimerTab._export_excel(str(path), headers, rows)
    import pandas as pd

    df = pd.read_excel(str(path))
    assert list(df.columns) == headers
    assert len(df) == 2
    assert df.iloc[0]["Primer"] == "Fwd (EcoRI)"


def test_export_table_button_creates_file(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(tab_module, "_HAS_PRIMER3", False)
    monkeypatch.setattr(tab_module, "_primer3", None)
    out = str(tmp_path / "primers.csv")
    monkeypatch.setattr(
        "modules.cloning_primer_tab.QFileDialog.getSaveFileName",
        lambda *a, **k: (out, "CSV (*.csv)"),
    )
    tab = CloningPrimerTab()
    tab.example_btn.click()
    tab.run()
    tab.export_table_btn.click()
    assert os.path.isfile(out)
    text = open(out, encoding="utf-8-sig").read()
    assert "Fwd (EcoRI)" in text
    assert "Full Sequence (5'→3')" in text
    assert "Exported" in tab.status_label.text()


def test_export_table_empty_shows_status(qapp, monkeypatch):
    monkeypatch.setattr(
        "modules.cloning_primer_tab.QFileDialog.getSaveFileName",
        lambda *a, **k: ("x.csv", "CSV (*.csv)"),
    )
    tab = CloningPrimerTab()
    tab.export_table_btn.click()
    assert "Nothing to export" in tab.status_label.text()


# ── MainWindow wiring ────────────────────────────────────────────────────────


def test_main_window_opens_cloning_primer_tab(qapp):
    window = MainWindow()
    window.open_cloning_primer_tab()
    assert window.tabs.count() == 1
    assert window.tabs.tabText(0) == "Cloning Primer Design"


def test_main_window_cloning_primer_single_instance(qapp):
    window = MainWindow()
    window.open_cloning_primer_tab()
    first = window.tabs.widget(0)
    window.open_cloning_primer_tab()
    assert window.tabs.count() == 1
    assert window.tabs.widget(0) is first


def test_cloning_primer_menu_action_triggers_tab(qapp):
    window = MainWindow()
    menu_bar = window.menuBar()
    primer_menu = next(
        action.menu() for action in menu_bar.actions() if action.text() == "Primer Design"
    )
    action = next(a for a in primer_menu.actions() if a.text() == "Cloning Primer Design")
    action.trigger()
    assert window.tabs.count() == 1
    assert window.tabs.tabText(0) == "Cloning Primer Design"
