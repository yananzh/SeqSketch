"""SSR input validation and input-coordinate regression coverage."""

import csv

import pytest

from modules.ssr_finder_tab import (
    DEFAULT_THRESHOLDS,
    SsrFinderTab,
    _normalize_ssr_sequence,
    find_compound_ssrs,
    find_ssrs,
)


@pytest.mark.parametrize("base", list("NRYSWKMBDHV"))
def test_ambiguous_bases_never_form_or_bridge_perfect_repeats(base):
    assert find_ssrs(base * 20, DEFAULT_THRESHOLDS) == []
    hits = find_ssrs("A" * 6 + base + "A" * 6, DEFAULT_THRESHOLDS)
    assert hits == []


def test_whitespace_case_and_u_normalization_preserve_base_positions():
    seq = "n r y\n" + "au " * 6 + "\tNN"
    hits = find_ssrs(seq, DEFAULT_THRESHOLDS)
    assert len(hits) == 1
    assert (hits[0]["start"], hits[0]["end"], hits[0]["motif"]) == (3, 15, "AT")


@pytest.mark.parametrize("bad", ["-", ".", "1", "*", "?", "X"])
def test_invalid_characters_are_rejected_without_coordinate_deletion(bad):
    with pytest.raises(ValueError, match="position 4"):
        _normalize_ssr_sequence("ACG" + bad + "A" * 10)


def test_ambiguity_preserves_perfect_and_compound_coordinates():
    seq = "NN" + "A" * 10 + "RYS" + "CG" * 6
    hits = find_ssrs(seq, DEFAULT_THRESHOLDS)
    assert [(r["start"], r["end"]) for r in hits] == [(2, 12), (15, 27)]
    compound = find_compound_ssrs(hits, 3)
    assert len(compound) == 1
    assert (compound[0]["start"], compound[0]["end"], compound[0]["size"]) == (3, 27, 25)
    assert find_compound_ssrs(hits, 2) == []


def test_ui_and_csv_use_one_based_inclusive_input_coordinates(qapp, tmp_path, monkeypatch):
    path = tmp_path / "ssr.fasta"
    path.write_text(">sample\nNN rys\n" + "au " * 6 + "\n", encoding="utf-8")
    tab = SsrFinderTab()
    tab.input_path_edit.setText(str(path))
    tab.run()
    assert tab._records[0][1] == "NNRYS" + "AT" * 6
    assert tab._ssr_table.rowCount() == 1
    assert [tab._ssr_table.item(0, col).text() for col in (5, 6, 7)] == ["6", "17", "12"]
    out = tmp_path / "results.csv"
    monkeypatch.setattr(
        "modules.ssr_finder_tab.QFileDialog.getSaveFileName",
        lambda *args: (str(out), "CSV Files (*.csv)"),
    )
    tab._export_csv()
    with out.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    header = next(i for i, row in enumerate(rows) if row and row[0] == "Record")
    assert rows[header + 1][5:8] == ["6", "17", "12"]


@pytest.mark.parametrize("bad", ["-", ".", "1"])
def test_ui_reports_record_and_invalid_position(qapp, tmp_path, bad):
    path = tmp_path / "ssr.fasta"
    path.write_text(">good\n" + "A" * 10 + "\n>bad_record\nACG" + bad + "A" * 10)
    tab = SsrFinderTab()
    tab.input_path_edit.setText(str(path))
    messages = []
    tab.show_status = messages.append
    tab.run()
    assert "bad_record" in messages[-1]
    assert "position 4" in messages[-1]
    assert tab._ssr_table.rowCount() == 0


def test_result_filters_use_cached_run_and_preserve_full_ids(qapp, tmp_path, monkeypatch):
    name = "record_" + "long" * 15
    path = tmp_path / "multi.fasta"
    path.write_text(">" + name + "\n" + "A" * 10 + "NN" + "CG" * 6
                    + "\n>other\n" + "AT" * 6 + "\n")
    tab = SsrFinderTab()
    tab.input_path_edit.setText(str(path))
    tab.run()
    assert tab._ssr_table.rowCount() == 4
    assert tab._record_combo.itemText(1) == name
    assert tab._ssr_table.horizontalHeaderItem(0).text() == "Record"

    def unexpected_search(*args):
        raise AssertionError("Filtering must not rerun detection")

    monkeypatch.setattr("modules.ssr_finder_tab.find_ssrs", unexpected_search)
    tab._thresh_spins[1].setValue(100)
    tab._record_combo.setCurrentIndex(1)
    assert tab._ssr_table.rowCount() == 3
    tab._type_combo.setCurrentText("Perfect")
    assert tab._ssr_table.rowCount() == 2
    tab._search_edit.setText("cg")
    assert tab._ssr_table.rowCount() == 1
    assert tab._ssr_table.item(0, 0).text() == name
    assert tab._ssr_table.item(0, 2).text() == "(CG)6"
    tab._search_edit.setText("no match")
    assert tab._ssr_table.rowCount() == 0
    assert not tab._export_btn.isEnabled()
    tab._search_edit.clear()
    tab._type_combo.setCurrentText("Compound")
    assert tab._ssr_table.rowCount() == 1
    tab._record_combo.setCurrentIndex(2)
    assert tab._ssr_table.rowCount() == 0
    tab._type_combo.setCurrentText("All")
    assert tab._ssr_table.rowCount() == 1
    tab.clear()
    assert tab._all_results == []
    assert tab._search_edit.text() == ""
    assert tab._type_combo.currentText() == "All"
    assert tab._ssr_table.rowCount() == 0


def test_export_contains_only_filtered_rows(qapp, tmp_path, monkeypatch):
    path = tmp_path / "multi.fasta"
    path.write_text(">first\n" + "A" * 10 + "NN" + "CG" * 6
                    + "\n>second\n" + "AT" * 6 + "\n")
    tab = SsrFinderTab()
    tab.input_path_edit.setText(str(path))
    tab.run()
    tab._type_combo.setCurrentText("Perfect")
    tab._search_edit.setText("second")
    out = tmp_path / "filtered.csv"
    monkeypatch.setattr(
        "modules.ssr_finder_tab.QFileDialog.getSaveFileName",
        lambda *args: (str(out), "CSV Files (*.csv)"),
    )
    tab._export_csv()
    with out.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    header = next(i for i, row in enumerate(rows) if row and row[0] == "Record")
    assert len(rows[header + 1:]) == 1
    assert rows[header + 1][:3] == ["second", "Perfect", "(AT)6"]
    assert ["Perfect_SSRs", "1"] in rows[:header]
    assert ["Compound_SSRs", "0"] in rows[:header]
