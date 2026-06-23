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
    assert btn is not None, "FASTA QC tab has no Example button"
    btn.click()
    assert tab.input_edit.text().strip() != ""
    assert os.path.isfile(tab.input_edit.text().strip())


def test_translate_example_fills_input_text_first_record(qapp):
    from modules.translate_tab import TranslateTab

    tab = TranslateTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "Translate tab has no Example button"
    btn.click()
    text = tab.input_text.toPlainText()
    assert text.startswith(">")
    assert text.count(">") == 1  # first record only


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
    assert text.count(">") == 8


def test_mafft_example_fills_input_text(qapp):
    from modules.mafft_alignment_tab import MafftAlignmentTab

    tab = MafftAlignmentTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "MAFFT tab has no Example button"
    btn.click()
    text = tab.input_text.toPlainText()
    assert text.startswith(">")
    assert text.count(">") == 8
