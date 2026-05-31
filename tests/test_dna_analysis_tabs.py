import os
from types import SimpleNamespace
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from main_window import MainWindow
from modules.alignment_format_converter_tab import AlignmentFormatConverterTab
from modules.complement_tab import ComplementTab
from modules.codon_usage_tab import CodonUsageTab
from modules.dotplot_tab import DotPlotTab
from modules.mafft_alignment_tab import MafftAlignmentTab, _MafftWorker
from modules.msa_visualization_tab import MSAVisualizationTab
from modules.multiple_sequence_alignment_tab import (
    MultipleSequenceAlignmentTab,
    _MuscleBatchWorker,
)
from modules.orf_tab import ORFTab
from modules.pairwise_alignment_tab import PairwiseAlignmentTab
from modules.rna_tab import RNATab
from modules.sanger_tab import SangerTab
from modules.sequence_logo_tab import SequenceLogoTab
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
    assert tab.export_btn.isHidden()
    assert tab.copy_btn.isHidden()
    assert not hasattr(tab, "rc_check")


def test_dotplot_tab_loads_files_without_showing_loaded_file_hint(
    qapp, monkeypatch, tmp_path
):
    tab = DotPlotTab()
    sample_text = ">seq1\nMKTFFVAG\n"
    sample_file = tmp_path / "protein.txt"
    sample_file.write_text(sample_text, encoding="utf-8")

    monkeypatch.setattr(
        "modules.dotplot_tab.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(sample_file), "Text files (*.txt)"),
    )

    tab.open_file()

    assert tab.input_text.toPlainText() == sample_text
    assert tab.input_hint.isHidden()
    assert tab.input_hint.text() == ""

    class _DummyUrl:
        def __init__(self, path):
            self._path = path

        def toLocalFile(self):
            return self._path

    class _DummyMimeData:
        def __init__(self, path):
            self._path = path

        def urls(self):
            return [_DummyUrl(self._path)]

    class _DummyEvent:
        def __init__(self, path):
            self._accepted = False
            self._path = path

        def mimeData(self):
            return _DummyMimeData(self._path)

        def acceptProposedAction(self):
            self._accepted = True

        def ignore(self):
            self._accepted = False

    tab.input_hint.setText("stale")
    event = _DummyEvent(str(sample_file))

    tab._drop_event(event)

    assert event._accepted is True
    assert tab.input_text.toPlainText() == sample_text
    assert tab.input_hint.isHidden()
    assert tab.input_hint.text() == ""


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
    assert tab.export_btn.isHidden()
    assert tab.input_hint.isHidden()
    assert tab.order_combo.currentText() == "Input sequence order"
    assert tab.output_file_edit.text() == ""


def test_msa_single_file_tab_adds_left_padding_inside_subpage(qapp):
    tab = MultipleSequenceAlignmentTab()
    single_page_layout = tab.mode_tabs.widget(0).layout()

    assert single_page_layout is not None
    assert single_page_layout.contentsMargins().left() >= 8


def test_msa_single_file_loads_input_without_showing_loaded_hint(
    qapp, monkeypatch, tmp_path
):
    tab = MultipleSequenceAlignmentTab()
    sample_text = ">seq1\nATG-C\n>seq2\nATGGC\n"
    sample_file = tmp_path / "msa_input.fasta"
    sample_file.write_text(sample_text, encoding="utf-8")

    monkeypatch.setattr(
        "modules.multiple_sequence_alignment_tab.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(sample_file), "FASTA files (*.fasta)"),
    )

    tab.open_file()

    assert tab.input_text.toPlainText() == sample_text
    assert tab.input_hint.isHidden()
    assert tab.input_hint.text() == ""

    class _DummyUrl:
        def __init__(self, path):
            self._path = path

        def toLocalFile(self):
            return self._path

    class _DummyMimeData:
        def __init__(self, path):
            self._path = path

        def urls(self):
            return [_DummyUrl(self._path)]

    class _DummyEvent:
        def __init__(self, path):
            self._accepted = False
            self._path = path

        def mimeData(self):
            return _DummyMimeData(self._path)

        def acceptProposedAction(self):
            self._accepted = True

        def ignore(self):
            self._accepted = False

    tab.input_hint.setText("stale")
    event = _DummyEvent(str(sample_file))

    tab.input_text.clear()
    tab.input_text.dropEvent(event)

    assert event._accepted is True
    assert tab.input_text.toPlainText() == sample_text
    assert tab.input_hint.isHidden()
    assert tab.input_hint.text() == ""


def test_msa_single_file_alignment_done_writes_output_file_in_input_order(
    qapp, tmp_path
):
    tab = MultipleSequenceAlignmentTab()
    output_path = tmp_path / "aligned_output"
    aligned_fasta = ">seqA\nATG-C\n>seqB\nATGGC\n"

    tab.output_file_edit.setText(str(output_path))
    tab._input_sequence_order = ["seqB", "seqA"]

    tab._on_alignment_done(aligned_fasta)

    saved_path = output_path.with_suffix(".fasta")
    assert saved_path.exists()
    assert saved_path.read_text(encoding="utf-8") == ">seqB\nATGGC\n>seqA\nATG-C\n"


def test_msa_single_file_can_keep_muscle_output_order_when_selected(qapp, tmp_path):
    tab = MultipleSequenceAlignmentTab()
    output_path = tmp_path / "aligned_output_keep_order"
    aligned_fasta = ">seqA\nATG-C\n>seqB\nATGGC\n"

    tab.order_combo.setCurrentText("MUSCLE output order")
    tab.output_file_edit.setText(str(output_path))
    tab._input_sequence_order = ["seqB", "seqA"]

    tab._on_alignment_done(aligned_fasta)

    saved_path = output_path.with_suffix(".fasta")
    assert saved_path.exists()
    assert saved_path.read_text(encoding="utf-8") == aligned_fasta


def test_msa_batch_tab_defaults_to_input_order_without_index_placeholder(qapp):
    tab = MultipleSequenceAlignmentTab()

    assert tab.batch_name_pattern.text() == "{stem}_muscle5_{method}.{ext}"
    assert tab.batch_order_combo.currentText() == "Input sequence order"


def test_msa_batch_worker_can_restore_input_sequence_order():
    worker = _MuscleBatchWorker(
        input_files=[],
        output_dir="",
        method="accurate",
        threads=1,
        muscle_exe="muscle.exe",
        output_mode="FASTA (aligned)",
        naming_pattern="{stem}_muscle5_{method}.{ext}",
        overwrite=True,
    )
    worker.sequence_order = "Input sequence order"

    ordered = worker._apply_output_order(
        {"seqA": "ATG-C", "seqB": "ATGGC"},
        ["seqB", "seqA"],
    )

    assert list(ordered.keys()) == ["seqB", "seqA"]


def test_msa_visualization_tab_hides_save_figure_button(qapp):
    tab = MSAVisualizationTab()

    assert tab.export_btn.isHidden()


def test_mafft_worker_emits_aligned_fasta_with_auto_strategy(monkeypatch, tmp_path):
    mafft_exe = tmp_path / "mafft.bat"
    mafft_exe.write_text("@echo off\n", encoding="utf-8")
    worker = _MafftWorker(
        fasta_text=">seq1\nATGC\n>seq2\nATGT\n",
        strategy="Auto",
        threads=4,
        mafft_exe=str(mafft_exe),
        output_format="FASTA",
    )
    commands = []
    results = []

    def fake_run(cmd, *args, **kwargs):
        commands.append(cmd)
        return SimpleNamespace(
            returncode=0,
            stdout=">seq1\nATG-C\n>seq2\nATGTC\n",
            stderr="",
        )

    monkeypatch.setattr("modules.mafft_alignment_tab.subprocess.run", fake_run)
    worker.finished.connect(results.append)

    worker.run()

    assert commands
    assert commands[0][0] == str(mafft_exe)
    assert "--auto" in commands[0]
    assert "--thread" in commands[0]
    assert "--clustalout" not in commands[0]
    assert results == [">seq1\nATG-C\n>seq2\nATGTC\n"]


def test_mafft_single_file_tab_hides_output_panel_and_uses_mode_subtabs(qapp):
    tab = MafftAlignmentTab()

    assert tab.mode_tabs.count() == 2
    assert [tab.mode_tabs.tabText(i) for i in range(tab.mode_tabs.count())] == [
        "Single-file",
        "Batch Multi-file",
    ]
    assert tab.output_label.isHidden()
    assert tab.output_text.isHidden()
    assert tab.copy_btn.isHidden()
    assert tab.export_btn.isHidden()
    assert tab.input_hint.isHidden()
    assert tab.output_file_edit.text() == ""


def test_mafft_single_file_tab_adds_left_padding_inside_subpage(qapp):
    tab = MafftAlignmentTab()
    single_page_layout = tab.mode_tabs.widget(0).layout()

    assert single_page_layout is not None
    assert single_page_layout.contentsMargins().left() >= 8


def test_mafft_batch_tab_defaults_to_input_order_with_mafft_pattern(qapp):
    tab = MafftAlignmentTab()

    assert tab.batch_name_pattern.text() == "{stem}_mafft_{method}.{ext}"
    assert tab.batch_order_combo.currentText() == "Input sequence order"


def test_msa_visualization_tab_loads_input_without_showing_loaded_hint(
    qapp, monkeypatch, tmp_path
):
    tab = MSAVisualizationTab()
    sample_text = ">seq_alpha\nATGCATGC\n>seq_beta\nATGCATGC\n"
    sample_file = tmp_path / "aligned_input.fasta"
    sample_file.write_text(sample_text, encoding="utf-8")

    monkeypatch.setattr(
        "modules.msa_visualization_tab.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(sample_file), "FASTA files (*.fasta)"),
    )

    tab.open_file()

    assert tab.input_text.toPlainText() == sample_text
    assert tab.input_hint.isHidden()
    assert tab.input_hint.text() == ""

    class _DummyUrl:
        def __init__(self, path):
            self._path = path

        def toLocalFile(self):
            return self._path

    class _DummyMimeData:
        def __init__(self, path):
            self._path = path

        def urls(self):
            return [_DummyUrl(self._path)]

    class _DummyEvent:
        def __init__(self, path):
            self._accepted = False
            self._path = path

        def mimeData(self):
            return _DummyMimeData(self._path)

        def acceptProposedAction(self):
            self._accepted = True

        def ignore(self):
            self._accepted = False

    tab.input_hint.setText("stale")
    event = _DummyEvent(str(sample_file))

    tab.input_text.clear()
    tab.input_text.dropEvent(event)

    assert event._accepted is True
    assert tab.input_text.toPlainText() == sample_text
    assert tab.input_hint.isHidden()
    assert tab.input_hint.text() == ""


def test_msa_visualization_keeps_sequence_labels_visible_with_default_dpi(qapp):
    tab = MSAVisualizationTab()
    headers = ["seq_alpha", "seq_beta"]
    tab.input_text.setPlainText(
        ">seq_alpha\nATGCATGCATGCATGC\n>seq_beta\nATGCATGCATGCATGC\n"
    )

    assert tab.title == "MSA Visualization (pyMSAviz)"
    assert tab.dpi_spin.value() == 300

    tab.run()

    assert tab._current_figure is not None

    fig = tab._current_figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    texts = [text for ax in fig.axes for text in ax.texts if text.get_text() in headers]

    assert texts
    assert min(text.get_window_extent(renderer).x0 for text in texts) >= 0


def test_main_window_and_menu_use_msa_visualization_pymsaviz_label(qapp):
    window = MainWindow()

    window.open_msa_visualization_tab()

    assert (
        window.tabs.tabText(window.tabs.currentIndex())
        == "MSA Visualization (pyMSAviz)"
    )

    menu_bar = window.menuBar()
    alignment_menu = next(
        action.menu() for action in menu_bar.actions() if action.text() == "Alignment"
    )
    action_texts = [
        action.text() for action in alignment_menu.actions() if action.text()
    ]

    assert "MSA Visualization (pyMSAviz)" in action_texts
    assert "MSA Visualization" not in action_texts


def test_main_window_and_menu_use_mafft_label(qapp):
    window = MainWindow()

    window.open_mafft_alignment_tab()

    assert (
        window.tabs.tabText(window.tabs.currentIndex())
        == "Multiple Sequence Alignment (MAFFT)"
    )

    menu_bar = window.menuBar()
    alignment_menu = next(
        action.menu() for action in menu_bar.actions() if action.text() == "Alignment"
    )
    action_texts = [
        action.text() for action in alignment_menu.actions() if action.text()
    ]

    assert "Multiple Sequence Alignment (MAFFT)" in action_texts


def test_sequence_logo_tab_hides_save_figure_button_and_uses_logomaker_title(qapp):
    tab = SequenceLogoTab()

    assert tab.export_btn.isHidden()
    assert tab.title == "Sequence Logo (Logomaker)"


def test_sequence_logo_tab_loads_input_without_showing_loaded_hint(
    qapp, monkeypatch, tmp_path
):
    tab = SequenceLogoTab()
    sample_text = ">seq1\nATGC\n>seq2\nATGC\n"
    sample_file = tmp_path / "sequence_logo_input.fasta"
    sample_file.write_text(sample_text, encoding="utf-8")

    monkeypatch.setattr(
        "utils.common_components.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(sample_file), "FASTA files (*.fasta)"),
    )

    tab.open_file()

    assert tab.input_text.toPlainText() == sample_text
    assert tab.input_hint.isHidden()
    assert tab.input_hint.text() == ""

    class _DummyUrl:
        def __init__(self, path):
            self._path = path

        def toLocalFile(self):
            return self._path

    class _DummyMimeData:
        def __init__(self, path):
            self._path = path

        def urls(self):
            return [_DummyUrl(self._path)]

    class _DummyEvent:
        def __init__(self, path):
            self._accepted = False
            self._path = path

        def mimeData(self):
            return _DummyMimeData(self._path)

        def acceptProposedAction(self):
            self._accepted = True

        def ignore(self):
            self._accepted = False

    tab.input_hint.setText("stale")
    event = _DummyEvent(str(sample_file))

    tab.input_text.clear()
    tab.input_text.dropEvent(event)

    assert tab.input_text.toPlainText() == sample_text
    assert tab.input_hint.isHidden()
    assert tab.input_hint.text() == ""


def test_main_window_and_menu_use_sequence_logo_logomaker_label(qapp):
    window = MainWindow()

    window.open_sequence_logo_tab()

    assert (
        window.tabs.tabText(window.tabs.currentIndex()) == "Sequence Logo (Logomaker)"
    )

    menu_bar = window.menuBar()
    alignment_menu = next(
        action.menu() for action in menu_bar.actions() if action.text() == "Alignment"
    )
    action_texts = [
        action.text() for action in alignment_menu.actions() if action.text()
    ]

    assert "Sequence Logo (Logomaker)" in action_texts
    assert "Sequence Logo" not in action_texts


def test_alignment_format_converter_happy_path(qapp, tmp_path):
    input_path = tmp_path / "aligned_input.fasta"
    output_path = tmp_path / "aligned_output.aln"
    input_path.write_text(
        ">seq1\nATG-C\n>seq2\nATGGC\n",
        encoding="utf-8",
    )
    tab = AlignmentFormatConverterTab()

    tab.input_edit.setText(str(input_path))
    tab.output_edit.setText(str(output_path))
    tab.input_format_combo.setCurrentText("FASTA")
    tab.output_format_combo.setCurrentText("CLUSTAL")
    tab.run_conversion()

    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8").startswith("CLUSTAL")
    assert "Converted 1 alignment(s)" in tab.log_area.toPlainText()
    assert tab.status_label.text() == "Ready"


def test_main_window_and_menu_use_alignment_format_converter_label(qapp):
    window = MainWindow()

    window.open_alignment_format_converter_tab()

    assert (
        window.tabs.tabText(window.tabs.currentIndex()) == "Alignment Format Converter"
    )

    menu_bar = window.menuBar()
    alignment_menu = next(
        action.menu() for action in menu_bar.actions() if action.text() == "Alignment"
    )
    action_texts = [
        action.text() for action in alignment_menu.actions() if action.text()
    ]

    assert "Alignment Format Converter" in action_texts


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
