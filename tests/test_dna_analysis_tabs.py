import os
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from main_window import MainWindow
from modules.complement_tab import ComplementTab
from modules.codon_usage_tab import CodonUsageTab
from modules.dotplot_tab import DotPlotTab
from modules.multiple_sequence_alignment_tab import MultipleSequenceAlignmentTab
from modules.orf_tab import ORFTab
from modules.pairwise_alignment_tab import PairwiseAlignmentTab
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


def test_protein_analysis_menu_groups_web_tools_and_opens_expected_urls(
    qapp, monkeypatch
):
    window = MainWindow()
    opened_urls = []
    monkeypatch.setattr(window, "open_url_in_browser", opened_urls.append)

    menu_bar = window.menuBar()
    protein_menu = next(
        action.menu()
        for action in menu_bar.actions()
        if action.text() == "Protein Analysis"
    )
    submenu_map = {
        action.text(): action.menu()
        for action in protein_menu.actions()
        if action.menu() is not None
    }

    assert "Protein Annotation and Reference" in submenu_map
    assert [
        action.text()
        for action in submenu_map["Protein Annotation and Reference"].actions()
        if action.text()
    ] == ["UniProtKB", "UniProt ID Mapping"]
    assert "Signal Peptide and Topology Prediction" in submenu_map
    assert [
        action.text()
        for action in submenu_map["Signal Peptide and Topology Prediction"].actions()
        if action.text()
    ] == ["SignalP 6.0", "DeepTMHMM 1.0"]
    assert "Tertiary Structure Prediction" in submenu_map
    assert [
        action.text()
        for action in submenu_map["Tertiary Structure Prediction"].actions()
        if action.text()
    ] == ["SWISS-MODEL", "AlphaFold Server"]
    assert "Domain and Motif Analysis" in submenu_map
    assert [
        action.text()
        for action in submenu_map["Domain and Motif Analysis"].actions()
        if action.text()
    ] == ["InterPro", "MEME Suite", "ScanProsite", "NCBI CD-Search"]
    assert "Tertiary Structure Reference" in submenu_map
    assert [
        action.text()
        for action in submenu_map["Tertiary Structure Reference"].actions()
        if action.text()
    ] == ["AlphaFold DB", "RCSB PDB"]
    assert "Protein Function and Interaction" in submenu_map
    assert [
        action.text()
        for action in submenu_map["Protein Function and Interaction"].actions()
        if action.text()
    ] == ["STRING", "MobiDB"]
    assert "Pairwise Protein Structure Alignment" in submenu_map
    assert [
        action.text()
        for action in submenu_map["Pairwise Protein Structure Alignment"].actions()
        if action.text()
    ] == ["RCSB Pairwise Structure Alignment"]
    assert "Signal Peptide" not in submenu_map
    assert "Transmembrane Helices" not in submenu_map
    assert "Domain Prediction" not in submenu_map
    assert "Signal & Topology" not in submenu_map
    assert "Domain & Motif" not in submenu_map
    assert "Pairwise Structure Alignment" not in submenu_map

    submenu_map["Protein Annotation and Reference"].actions()[0].trigger()
    submenu_map["Protein Annotation and Reference"].actions()[1].trigger()
    submenu_map["Signal Peptide and Topology Prediction"].actions()[0].trigger()
    submenu_map["Signal Peptide and Topology Prediction"].actions()[1].trigger()
    submenu_map["Domain and Motif Analysis"].actions()[0].trigger()
    submenu_map["Domain and Motif Analysis"].actions()[1].trigger()
    submenu_map["Domain and Motif Analysis"].actions()[2].trigger()
    submenu_map["Domain and Motif Analysis"].actions()[3].trigger()
    submenu_map["Tertiary Structure Reference"].actions()[0].trigger()
    submenu_map["Tertiary Structure Reference"].actions()[1].trigger()
    submenu_map["Protein Function and Interaction"].actions()[0].trigger()
    submenu_map["Protein Function and Interaction"].actions()[1].trigger()
    submenu_map["Pairwise Protein Structure Alignment"].actions()[0].trigger()

    assert opened_urls == [
        "https://www.uniprot.org/uniprotkb",
        "https://www.uniprot.org/id-mapping",
        "https://services.healthtech.dtu.dk/services/SignalP-6.0/",
        "https://services.healthtech.dtu.dk/services/DeepTMHMM-1.0/",
        "https://www.ebi.ac.uk/interpro/",
        "https://meme-suite.org/meme/",
        "https://prosite.expasy.org/scanprosite/",
        "https://www.ncbi.nlm.nih.gov/Structure/cdd/wrpsb.cgi",
        "https://alphafold.ebi.ac.uk/",
        "https://www.rcsb.org/",
        "https://string-db.org/",
        "https://mobidb.org/",
        "https://www.rcsb.org/alignment",
    ]


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

    pairwise_tab = PairwiseAlignmentTab()
    for editor in (
        pairwise_tab.input_text,
        pairwise_tab.seq2_text,
        pairwise_tab.output_text,
    ):
        assert editor.property("sequenceEditorStyled") is True
        assert "border-radius" in editor.styleSheet()
        assert "border: 1px solid #94a3b8;" in editor.styleSheet()
        assert not editor.styleSheet().lstrip().startswith("QTextEdit")


def test_dotplot_tab_hides_output_panel_and_removes_reverse_complement_option(qapp):
    tab = DotPlotTab()

    assert tab.output_label.isHidden()
    assert tab.output_text.isHidden()
    assert tab.copy_btn.isHidden()
    assert not hasattr(tab, "rc_check")


def test_pairwise_alignment_defaults_gap_open_penalty_to_ten_for_both_modes(qapp):
    tab = PairwiseAlignmentTab()

    assert tab.mode_combo.currentText() == "Global (Needleman–Wunsch)"
    assert tab.gap_open_spin.value() == 10.0

    tab.mode_combo.setCurrentText("Local (Smith–Waterman)")

    assert tab.gap_open_spin.value() == 10.0


def test_msa_single_file_tab_hides_output_panel_and_locks_export_to_fasta(qapp):
    tab = MultipleSequenceAlignmentTab()

    assert tab.output_label.isHidden()
    assert tab.output_text.isHidden()
    assert tab.copy_btn.isHidden()
    assert tab.fmt_combo.count() == 1
    assert tab.fmt_combo.currentText() == "FASTA (aligned)"
    assert not tab.fmt_combo.isEnabled()
    assert not tab.export_btn.isEnabled()


def test_msa_single_file_export_writes_aligned_fasta_only(qapp, monkeypatch, tmp_path):
    tab = MultipleSequenceAlignmentTab()
    aligned_fasta = ">seq1\nATG-C\n>seq2\nATGGC\n"
    export_path = tmp_path / "aligned_output"

    tab._on_alignment_done(aligned_fasta)

    monkeypatch.setattr(
        "modules.multiple_sequence_alignment_tab.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(export_path), "FASTA files (*.fasta *.fa)"),
    )

    tab.export_result()

    saved_path = export_path.with_suffix(".fasta")
    assert saved_path.exists()
    assert saved_path.read_text(encoding="utf-8") == aligned_fasta


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
