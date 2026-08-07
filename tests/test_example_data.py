"""Tests for the example-data loader and per-tab Example buttons."""

import os

from utils.app_paths import user_data_dir
from utils.example_data import example_path, load_example_text, stage_example

# ── Loader tests (no GUI) ───────────────────────────────────────────────────


def test_example_path_exists_and_nonempty():
    p = example_path("phylo", "cytb_protein.fasta")
    assert os.path.isfile(p)
    assert os.path.getsize(p) > 0


def test_load_example_text_returns_fasta():
    text = load_example_text("phylo", "cytb_protein.fasta")
    assert text.startswith(">")
    assert text.count(">") == 8  # 8 species


def test_stage_example_copies_to_user_data_and_is_writable():
    out = stage_example("phylo", "cytb_protein.fasta")
    assert out is not None
    assert os.path.dirname(out) == os.path.join(user_data_dir(), "example_work")
    assert os.access(out, os.W_OK)
    with open(out, encoding="utf-8") as f:
        copy_text = f.read()
    assert copy_text == load_example_text("phylo", "cytb_protein.fasta")


def test_stage_example_overwrite_idempotent():
    out1 = stage_example("phylo", "cytb_protein.fasta")
    out2 = stage_example("phylo", "cytb_protein.fasta")  # second call overwrites
    assert out1 == out2
    assert os.path.isfile(out2)


def test_load_example_text_missing_returns_empty():
    text = load_example_text("phylo", "does_not_exist.fasta")
    assert text == ""


def test_stage_example_missing_returns_none():
    out = stage_example("phylo", "does_not_exist.fasta")
    assert out is None


# ── Per-tab Example button tests (GUI, offscreen) ───────────────────────────
# These use the shared qapp fixture from tests/conftest.py.


def _find_button(tab, text):
    from PyQt6.QtWidgets import QPushButton

    for btn in tab.findChildren(QPushButton):
        if btn.text() == text:
            return btn
    return None


def test_fasta_qc_example_fills_input_edit(qapp):
    from modules.sequence_statistics_tab import SequenceStatisticsTab

    tab = SequenceStatisticsTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "FASTA Statistics tab has no Example button"
    btn.click()
    assert tab.input_edit.text().strip() != ""
    assert os.path.isfile(tab.input_edit.text().strip())


def test_translate_example_fills_input_text(qapp):
    from modules.translate_tab import TranslateTab

    tab = TranslateTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "Translate tab has no Example button"
    btn.click()
    text = tab.input_text.toPlainText()
    assert text.startswith(">")
    assert text.count(">") == 2  # BRCA1 + EGFR CDS records


def test_physicochemical_example_fills_input_text(qapp):
    from modules.physicochemical_properties_tab import (
        PhysicochemicalPropertiesTab,
    )

    tab = PhysicochemicalPropertiesTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "Physicochemical tab has no Example button"
    btn.click()
    text = tab.input_text.toPlainText()
    assert text.startswith(">")
    assert "P02931" in text


def test_mafft_example_fills_input_text(qapp):
    from modules.mafft_alignment_tab import MafftAlignmentTab

    tab = MafftAlignmentTab()
    assert hasattr(tab, "example_btn"), "MAFFT tab has no Example button"
    tab.example_btn.click()
    text = tab.input_text.toPlainText()
    assert text.startswith(">")
    assert text.count(">") == 3


def test_trimal_example_adds_file_to_list(qapp):
    from modules.trimal_tab import AlignmentTrimmingTab

    tab = AlignmentTrimmingTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "trimAl tab has no Example button"
    btn.click()
    assert tab.file_list.count() >= 1
    item = tab.file_list.item(0)
    path = item.data(256)
    assert path and os.path.isfile(path)


def test_iqtree_example_fills_input_edit(qapp):
    from modules.iqtree_tab import IqTreeTab

    tab = IqTreeTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "IQ-TREE tab has no Example button"
    btn.click()
    assert tab._input_edit.text().strip() != ""
    assert os.path.isfile(tab._input_edit.text().strip())


def test_tree_vis_example_fills_file_edit(qapp):
    from modules.tree_visualization_toytree_tab import ToytreeVisualizationTab

    tab = ToytreeVisualizationTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "Toytree tab has no Example button"
    btn.click()
    assert tab._file_edit.text().strip() != ""
    assert os.path.isfile(tab._file_edit.text().strip())


# ── DNA Analysis tabs Example buttons ───────────────────────────────────────


def test_rna_example_fills_input_text(qapp):
    from modules.rna_tab import RNATab

    tab = RNATab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "RNA tab has no Example button"
    btn.click()
    text = tab.input_text.toPlainText()
    assert text.startswith(">")
    assert "HBB" in text


def test_complement_example_fills_input_text(qapp):
    from modules.complement_tab import ComplementTab

    tab = ComplementTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "Complement tab has no Example button"
    btn.click()
    text = tab.input_text.toPlainText()
    assert text.startswith(">")
    assert text.count(">") == 2  # 27F + 1492R


def test_orf_example_fills_input_text(qapp):
    from modules.orf_tab import ORFTab

    tab = ORFTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "ORF tab has no Example button"
    btn.click()
    text = tab.input_text.toPlainText()
    assert text.startswith(">")
    assert "lambda" in text.lower()


def test_restriction_enzyme_example_fills_input_text(qapp):
    from modules.restriction_enzyme_tab import RestrictionEnzymeTab

    tab = RestrictionEnzymeTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "Restriction Enzyme tab has no Example button"
    btn.click()
    text = tab.input_text.toPlainText()
    assert text.startswith(">")
    assert "pBR322" in text


def test_gc_plot_example_fills_input_text(qapp):
    from modules.gc_plot_tab import GCPlotTab

    tab = GCPlotTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "GC Plot tab has no Example button"
    btn.click()
    text = tab.input_text.toPlainText()
    assert text.startswith(">")
    assert "NC_000913" in text or "complete genome" in text


def test_sanger_assembly_example_fills_both_inputs(qapp):
    from modules.sanger_tab import SangerTab

    tab = SangerTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "Sanger Assembly tab has no Example button"
    btn.click()
    fwd = tab.fwd_edit.text().strip()
    rev = tab.rev_edit.text().strip()
    assert fwd, "forward file path not filled"
    assert rev, "reverse file path not filled"
    assert fwd != rev
    assert os.path.isfile(fwd), f"staged forward file does not exist: {fwd}"
    assert os.path.isfile(rev), f"staged reverse file does not exist: {rev}"
    with open(fwd, encoding="utf-8") as fh:
        assert fh.read().startswith(">sanger_read_f"), "forward record missing"
    with open(rev, encoding="utf-8") as fh:
        assert fh.read().startswith(">sanger_read_r"), "reverse record missing"


def test_sanger_viewer_example_fills_file_edit(qapp):
    from modules.sanger_viewer_tab import SangerViewerTab

    tab = SangerViewerTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "Sanger Viewer tab has no Example button"
    btn.click()
    path = tab._file_edit.text().strip()
    assert path != "", "file path not filled"
    assert os.path.isfile(path), f"staged file does not exist: {path}"
    assert path.lower().endswith(".ab1")


# ── FASTA Tools tabs Example buttons ─────────────────────────────────────────


def test_simplify_headers_example_fills_input_edit(qapp):
    from modules.simplify_ids_tab import SimplifyIDsTab

    tab = SimplifyIDsTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "Simplify Headers tab has no Example button"
    btn.click()
    assert tab.input_edit.text().strip() != ""
    assert os.path.isfile(tab.input_edit.text().strip())


def test_filter_by_ids_example_fills_input_and_ids(qapp):
    from modules.extract_by_id_tab import ExtractByIDTab

    tab = ExtractByIDTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "Filter by IDs tab has no Example button"
    btn.click()
    assert tab.input_edit.text().strip() != ""
    assert os.path.isfile(tab.input_edit.text().strip())
    assert tab.id_edit.toPlainText().strip() != ""


def test_filter_by_length_example_fills_input_edit(qapp):
    from modules.filter_by_length_tab import FilterByLengthTab

    tab = FilterByLengthTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "Filter by Length tab has no Example button"
    btn.click()
    assert tab.input_edit.text().strip() != ""
    assert os.path.isfile(tab.input_edit.text().strip())


def test_regex_filter_example_fills_input_and_regex(qapp):
    from modules.extract_by_regex_tab import ExtractByRegexTab

    tab = ExtractByRegexTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "Regex Filter tab has no Example button"
    btn.click()
    assert tab.input_edit.text().strip() != ""
    assert os.path.isfile(tab.input_edit.text().strip())
    # Example should also pre-fill a regex matching the UniProt header
    assert tab.regex_edit.text().strip() != ""


def test_ncbi_download_example_fills_acc_edit(qapp):
    from modules.download_from_ncbi_tab import DownloadFromNCBITab

    tab = DownloadFromNCBITab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "NCBI Download tab has no Example button"
    btn.click()
    acc_text = tab.acc_edit.toPlainText().strip()
    assert acc_text != ""
    assert "NM_" in acc_text


def test_rename_ids_example_fills_input_edit(qapp):
    from modules.batch_rename_ids_tab import BatchRenameIDsTab

    tab = BatchRenameIDsTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "Rename IDs tab has no Example button"
    btn.click()
    assert tab.input_edit.text().strip() != ""
    assert os.path.isfile(tab.input_edit.text().strip())


def test_deduplicate_example_fills_input_edit(qapp):
    from modules.deduplicate_tab import DeduplicateTab

    tab = DeduplicateTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "Deduplicate tab has no Example button"
    btn.click()
    assert tab.input_edit.text().strip() != ""
    assert os.path.isfile(tab.input_edit.text().strip())


def test_concat_fasta_example_fills_file_list(qapp):
    from PyQt6.QtCore import Qt

    from modules.concat_fasta_tab import ConcatFastaTab

    tab = ConcatFastaTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "Concatenate FASTA tab has no Example button"
    btn.click()
    assert tab.file_list.count() >= 2
    path = tab.file_list.item(0).data(Qt.ItemDataRole.UserRole)
    assert os.path.isfile(path)


def test_split_fasta_example_fills_input_edit(qapp):
    from modules.split_fasta_tab import SplitFastaTab

    tab = SplitFastaTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "Split FASTA tab has no Example button"
    btn.click()
    assert tab.input_edit.text().strip() != ""
    assert os.path.isfile(tab.input_edit.text().strip())


def test_sort_fasta_example_fills_input_edit(qapp):
    from modules.sort_fasta_tab import SortFastaTab

    tab = SortFastaTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "Sort FASTA tab has no Example button"
    btn.click()
    assert tab.input_edit.text().strip() != ""
    assert os.path.isfile(tab.input_edit.text().strip())


def test_fasta_to_table_example_fills_input_edit(qapp):
    from modules.fasta_table_converter_tab import FastaTableConverterTab

    tab = FastaTableConverterTab()
    tab.direction_combo.setCurrentIndex(0)  # FASTA → Table
    btn = _find_button(tab, "Example")
    assert btn is not None, "FASTA ↔ Table tab has no Example button"
    btn.click()
    assert tab.input_edit.text().strip() != ""
    assert os.path.isfile(tab.input_edit.text().strip())


def test_table_to_fasta_example_fills_input_edit(qapp):
    from modules.fasta_table_converter_tab import FastaTableConverterTab

    tab = FastaTableConverterTab()
    tab.direction_combo.setCurrentIndex(1)  # Table → FASTA
    btn = _find_button(tab, "Example")
    assert btn is not None, "FASTA ↔ Table tab has no Example button"
    btn.click()
    path = tab.input_edit.text().strip()
    assert path != ""
    assert os.path.isfile(path)
    assert path.endswith(".csv")
