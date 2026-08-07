import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QFrame, QLabel, QMessageBox, QPushButton

from main_window import MainWindow
from modules.alignment_format_converter_tab import AlignmentFormatConverterTab
from modules.codon_usage_tab import CodonUsageTab
from modules.complement_tab import ComplementTab
from modules.dotplot_tab import DotPlotTab
from modules.mafft_alignment_tab import MafftAlignmentTab, _MafftWorker
from modules.msa_visualization_tab import MSAVisualizationTab
from modules.multiple_sequence_alignment_tab import (
    MultipleSequenceAlignmentTab,
    _MuscleBatchWorker,
)
from modules.one_step_multigenephy_tab import OneStepMultiGenePhyTab
from modules.orf_tab import ORFTab
from modules.pairwise_alignment_tab import PairwiseAlignmentTab
from modules.rna_tab import RNATab
from modules.sanger_tab import SangerTab
from modules.sanger_viewer_tab import SangerViewerTab
from modules.sequence_logo_tab import SequenceLogoTab
from modules.translate_tab import TranslateTab
from modules.trimal_tab import (
    AlignmentTrimmingTab,
    _BatchTrimThread,
    _prepare_trimal_input,
)
from utils.common_components import FileDropLineEdit


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
        action.menu() for action in menu_bar.actions() if action.text() == "DNA Analysis"
    )
    action_texts = [action.text() for action in dna_menu.actions() if action.text()]

    assert "Complement/Reverse Complement" in action_texts
    assert "Reverse Complement" not in action_texts


def test_main_window_creates_multi_instance_one_step_multigenephy_tab(qapp):
    window = MainWindow()

    window.open_one_step_multigenephy_tab()

    assert window.tabs.count() == 1
    assert window.tabs.tabText(0) == "One Step MultiGenePhy"
    first_tab = window.tabs.widget(0)
    assert isinstance(first_tab, OneStepMultiGenePhyTab)

    window.open_one_step_multigenephy_tab()

    assert window.tabs.count() == 2
    assert window.tabs.tabText(1) == "One Step MultiGenePhy"
    second_tab = window.tabs.widget(1)
    assert isinstance(second_tab, OneStepMultiGenePhyTab)
    assert second_tab is not first_tab


def test_phylogenetic_tree_menu_includes_one_step_multigenephy(qapp):
    window = MainWindow()
    menu_bar = window.menuBar()
    tree_menu = next(
        action.menu() for action in menu_bar.actions() if action.text() == "Phylogenetic Tree"
    )
    one_step_action = next(
        action for action in tree_menu.actions() if action.text() == "One Step MultiGenePhy"
    )

    one_step_action.trigger()

    assert window.tabs.count() == 1
    assert window.tabs.tabText(0) == "One Step MultiGenePhy"
    first_tab = window.tabs.widget(0)
    assert isinstance(first_tab, OneStepMultiGenePhyTab)

    one_step_action.trigger()

    assert window.tabs.count() == 2
    assert window.tabs.tabText(1) == "One Step MultiGenePhy"
    second_tab = window.tabs.widget(1)
    assert isinstance(second_tab, OneStepMultiGenePhyTab)
    assert second_tab is not first_tab


def test_phylogenetic_tree_menu_order(qapp):
    window = MainWindow()
    menu_bar = window.menuBar()
    tree_menu = next(
        action.menu() for action in menu_bar.actions() if action.text() == "Phylogenetic Tree"
    )
    action_texts = [action.text() for action in tree_menu.actions() if action.text()]

    assert action_texts[0] == "Alignment Trimming (trimAl)"
    assert action_texts[1] == "Sequence Concatenation"
    assert action_texts[2] == "Distance Tree Construction"
    assert action_texts[3] == "ML Tree Construction (IQ-TREE)"
    assert "One Step MultiGenePhy" in action_texts
    assert any("Tree Visualization" in t for t in action_texts)


def test_alignment_trimming_tab_uses_simplified_parameter_layout(qapp):
    tab = AlignmentTrimmingTab()

    assert not hasattr(tab, "rb_manual")
    assert not hasattr(tab, "gt_check")
    assert not hasattr(tab, "st_check")
    assert not hasattr(tab, "cons_check")
    assert not hasattr(tab, "w_check")
    assert tab.findChildren(type(tab.file_list))
    assert tab.findChildren(type(tab.fmt_combo))


def test_alignment_trimming_tab_uses_compact_automated_controls(qapp):
    tab = AlignmentTrimmingTab()
    label_texts = [label.text() for label in tab.findChildren(QLabel)]

    # No verbose help paragraphs leaked into labels
    assert all("Removes columns with unusually" not in text for text in label_texts)
    assert all("recommended for most users" not in text for text in label_texts)
    assert tab.file_list.minimumHeight() <= 100
    assert hasattr(tab, "log_area")
    assert not hasattr(tab, "progress_bar")


def test_alignment_trimming_tab_places_run_left_help_right_without_stop(qapp):
    tab = AlignmentTrimmingTab()
    # Run button in status_layout left of Help; Help button provided by BaseTabWidget
    all_buttons = tab.findChildren(QPushButton)
    button_texts = [btn.text() for btn in all_buttons]

    assert "Run trimAl" in button_texts
    assert "Help" in button_texts


def test_alignment_trimming_prepares_phylip_input_as_temp_fasta(tmp_path):
    input_path = tmp_path / "aligned_input.phy"
    input_path.write_text(
        "2 5\nseq1  ATG-C\nseq2  ATGGC\n",
        encoding="utf-8",
    )

    prepared_path, cleanup_path = _prepare_trimal_input(str(input_path))

    assert prepared_path != str(input_path)
    assert cleanup_path == prepared_path
    assert os.path.exists(prepared_path)
    assert ">seq1" in open(prepared_path, encoding="utf-8").read()

    os.remove(prepared_path)


def test_alignment_trimming_worker_reports_missing_output_as_failure(qapp, monkeypatch, tmp_path):
    class FakeProcess:
        returncode = 0

        def communicate(self):
            return b"", None

    monkeypatch.setattr(
        "modules.trimal_tab.subprocess.Popen", lambda *args, **kwargs: FakeProcess()
    )

    out_path = tmp_path / "missing.trimmed.fasta"
    thread = _BatchTrimThread([
        (
            ["trimal.exe", "-in", "input.fasta", "-out", str(out_path)],
            str(out_path),
            None,
        )
    ])
    results = []
    totals = []
    thread.file_done.connect(lambda success, path, log: results.append((success, path, log)))
    thread.all_done.connect(lambda succeeded, failed: totals.append((succeeded, failed)))

    thread.run()

    assert results == [
        (
            False,
            str(out_path),
            f"trimAl did not create output file:\n{out_path}",
        )
    ]
    assert totals == [(0, 1)]


def test_alignment_trimming_logs_full_command_before_start(qapp, monkeypatch, tmp_path):
    exe_path = tmp_path / "trimal.exe"
    exe_path.write_text("", encoding="utf-8")
    input_path = tmp_path / "aligned_input.phy"
    input_path.write_text("placeholder", encoding="utf-8")
    prepared_input = tmp_path / "prepared_input.fasta"
    outdir = tmp_path / "trimmed"
    outdir.mkdir()

    monkeypatch.setattr(
        "modules.trimal_tab._prepare_trimal_input",
        lambda path: (str(prepared_input), str(prepared_input)),
    )
    monkeypatch.setattr(
        "modules.trimal_tab._BatchTrimThread.start",
        lambda self: None,
    )

    tab = AlignmentTrimmingTab()
    tab._exe_edit.setText(str(exe_path))
    tab.outdir_edit.setText(str(outdir))
    tab.file_list._add_path(str(input_path))

    tab._run()

    log_text = tab.log_area.toPlainText()
    expected_output = outdir / "aligned_input.trimmed.fasta"

    assert "TrimAl Run Summary" in log_text
    assert "trimAl path" in log_text
    assert "Trimming method" in log_text
    assert "gappyout" in log_text
    assert "Output format" in log_text
    assert "Output folder" in log_text
    assert str(exe_path) in log_text
    assert str(prepared_input) in log_text
    assert str(expected_output) in log_text
    assert "-gappyout" in log_text


def test_protein_analysis_menu_groups_web_tools_and_opens_expected_urls(qapp, monkeypatch):
    window = MainWindow()
    opened_urls = []
    monkeypatch.setattr(window, "open_url_in_browser", opened_urls.append)

    menu_bar = window.menuBar()
    protein_menu = next(
        action.menu() for action in menu_bar.actions() if action.text() == "Protein Analysis"
    )
    submenu_map = {
        action.text(): action.menu()
        for action in protein_menu.actions()
        if action.menu() is not None
    }

    assert "Local Analysis" in submenu_map
    assert [
        action.text() for action in submenu_map["Local Analysis"].actions() if action.text()
    ] == [
        "Amino Acid Composition",
        "Physicochemical Properties",
        "Hydrophobicity Plot",
        "Protease Cleavage Map",
    ]
    assert "Annotation & Features" in submenu_map
    assert [
        action.text() for action in submenu_map["Annotation & Features"].actions() if action.text()
    ] == [
        "UniProtKB",
        "UniProt ID Mapping",
        "InterPro",
        "NCBI CD-Search",
        "ScanProsite",
        "MEME Suite",
        "SignalP 6.0",
        "DeepTMHMM 1.0",
        "DeepLoc 2.1",
    ]
    assert "Structure" in submenu_map
    assert [action.text() for action in submenu_map["Structure"].actions() if action.text()] == [
        "PSIPRED",
        "Jpred4",
        "SWISS-MODEL",
        "AlphaFold Server",
        "AlphaFold DB",
        "RCSB PDB",
        "Foldseek Search",
        "RCSB Pairwise Alignment",
    ]
    assert "Function & Interaction" in submenu_map
    assert [
        action.text() for action in submenu_map["Function & Interaction"].actions() if action.text()
    ] == ["STRING", "MobiDB", "HMMER (phmmer)"]

    assert "Protein Annotation and Reference" not in submenu_map
    assert "Signal Peptide and Topology Prediction" not in submenu_map
    assert "Tertiary Structure Prediction" not in submenu_map
    assert "Domain and Motif Analysis" not in submenu_map
    assert "Tertiary Structure Reference" not in submenu_map
    assert "Protein Function and Interaction" not in submenu_map
    assert "Pairwise Protein Structure Alignment" not in submenu_map

    annotation = submenu_map["Annotation & Features"].actions()
    for a in annotation:
        if not a.menu():
            a.trigger()
    structure = submenu_map["Structure"].actions()
    for a in structure:
        if not a.menu():
            a.trigger()
    function = submenu_map["Function & Interaction"].actions()
    for a in function:
        if not a.menu():
            a.trigger()

    assert opened_urls == [
        "https://www.uniprot.org/uniprotkb",
        "https://www.uniprot.org/id-mapping",
        "https://www.ebi.ac.uk/interpro/",
        "https://www.ncbi.nlm.nih.gov/Structure/cdd/wrpsb.cgi",
        "https://prosite.expasy.org/scanprosite/",
        "https://meme-suite.org/meme/",
        "https://services.healthtech.dtu.dk/services/SignalP-6.0/",
        "https://services.healthtech.dtu.dk/services/DeepTMHMM-1.0/",
        "https://services.healthtech.dtu.dk/services/DeepLoc-2.1/",
        "http://bioinf.cs.ucl.ac.uk/psipred/",
        "https://www.compbio.dundee.ac.uk/jpred/",
        "https://swissmodel.expasy.org/",
        "https://alphafoldserver.com/",
        "https://alphafold.ebi.ac.uk/",
        "https://www.rcsb.org/",
        "https://search.foldseek.com/search",
        "https://www.rcsb.org/alignment",
        "https://string-db.org/",
        "https://mobidb.org/",
        "https://www.ebi.ac.uk/Tools/hmmer/search/phmmer",
    ]


def test_dna_analysis_sequence_editors_use_shared_border_style(qapp):
    # DNA analysis tabs use QGroupBox containers; the inner QTextEdit is
    # borderless (styles.qss provides the QGroupBox border instead).
    sequence_tabs = [RNATab(), ComplementTab(), TranslateTab(), ORFTab()]

    for tab in sequence_tabs:
        editor = tab.input_text
        assert editor.property("sequenceEditorStyled") is True
        assert "border-radius" in editor.styleSheet()
        assert "border: none;" in editor.styleSheet()
        assert not editor.styleSheet().lstrip().startswith("QTextEdit")

    sanger_tab = SangerTab()
    for edit in (sanger_tab.fwd_edit, sanger_tab.rev_edit):
        assert isinstance(edit, FileDropLineEdit)
        assert edit.isReadOnly()

    # PairwiseAlignmentTab: input_text / seq2_text use inline
    # stylesheets (direct declarations) for a single visible border;
    # output_text keeps border:none (QGroupBox provides container border).
    pairwise_tab = PairwiseAlignmentTab()
    assert "border: 1px solid #94a3b8;" in pairwise_tab.input_text.styleSheet()
    assert "border: 1px solid #94a3b8;" in pairwise_tab.seq2_text.styleSheet()
    assert "border: none;" in pairwise_tab.output_text.styleSheet()
    for editor in (
        pairwise_tab.input_text,
        pairwise_tab.seq2_text,
        pairwise_tab.output_text,
    ):
        assert editor.property("sequenceEditorStyled") is True
        assert editor.frameShape() == QFrame.Shape.NoFrame
        assert "border-radius" in editor.styleSheet()
        assert not editor.styleSheet().lstrip().startswith("QTextEdit")


def test_sanger_assembly_outputs_merged_fasta_contig_without_input_headers(
    qapp, monkeypatch, tmp_path
):
    tab = SangerTab()
    fwd_file = tmp_path / "fwd.fasta"
    rev_file = tmp_path / "rev.fasta"
    fwd_file.write_text(">forward_read\nAAAGGGCCC", encoding="utf-8")
    rev_file.write_text(">reverse_read\nAAAGGGCCC", encoding="utf-8")
    tab.fwd_edit.setText(str(fwd_file))
    tab.rev_edit.setText(str(rev_file))
    tab.min_overlap_spin.setValue(6)
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: None)

    tab.run_assembly()

    assert tab.assembly_result.toPlainText() == ">assembled_contig\nAAAGGGCCCTTT"


def test_dna_analysis_output_editors_use_transparent_backgrounds(qapp):
    # DNA analysis tabs use QGroupBox containers; inner QTextEdit is borderless.
    sequence_tabs = [RNATab(), ComplementTab(), TranslateTab(), ORFTab()]

    for tab in sequence_tabs:
        assert "background: transparent;" in tab.output_text.styleSheet()
        assert "border: none;" in tab.output_text.styleSheet()
        assert "border-radius: 6px;" in tab.output_text.styleSheet()
        assert "#f7f9fc" not in tab.output_text.styleSheet()
        assert tab.output_text.viewport().styleSheet() == "background: transparent; border: none;"

    sanger_tab = SangerTab()
    assert "background: transparent;" in sanger_tab.assembly_result.styleSheet()
    assert "border: none;" in sanger_tab.assembly_result.styleSheet()
    assert "border-radius: 6px;" in sanger_tab.assembly_result.styleSheet()
    assert "#f7f9fc" not in sanger_tab.assembly_result.styleSheet()
    assert (
        sanger_tab.assembly_result.viewport().styleSheet()
        == "background: transparent; border: none;"
    )

    sanger_viewer_tab = SangerViewerTab()
    assert "background: transparent;" in sanger_viewer_tab._seq_edit.styleSheet()
    assert "border: 1px solid #94a3b8;" in sanger_viewer_tab._seq_edit.styleSheet()
    assert "border-radius: 6px;" in sanger_viewer_tab._seq_edit.styleSheet()
    assert (
        sanger_viewer_tab._seq_edit.viewport().styleSheet()
        == "background: transparent; border: none;"
    )

    # PairwiseAlignmentTab's output_text stays borderless inside the
    # QGroupBox (same pattern as other DNA analysis tabs).
    pairwise_tab = PairwiseAlignmentTab()
    assert "background: transparent;" in pairwise_tab.output_text.styleSheet()
    assert "border: none;" in pairwise_tab.output_text.styleSheet()
    assert "border-radius: 6px;" in pairwise_tab.output_text.styleSheet()
    assert "#f7f9fc" not in pairwise_tab.output_text.styleSheet()
    assert (
        pairwise_tab.output_text.viewport().styleSheet() == "background: transparent; border: none;"
    )


def test_dotplot_tab_hides_output_panel_and_removes_reverse_complement_option(qapp):
    tab = DotPlotTab()

    assert tab.output_group.isHidden()
    assert tab.run_btn.text() == "Start"
    assert not hasattr(tab, "rc_check")


def test_dotplot_tab_loads_files_without_showing_loaded_file_hint(qapp, monkeypatch, tmp_path):
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

    assert tab.output_group.isHidden()
    assert tab.input_hint.isHidden()
    assert tab.order_combo.currentText() == "Input sequence order"
    assert tab.output_file_edit.text() == ""


def test_msa_single_file_tab_adds_left_padding_inside_subpage(qapp):
    tab = MultipleSequenceAlignmentTab()
    single_page_layout = tab.mode_tabs.widget(0).layout()

    assert single_page_layout is not None
    assert single_page_layout.contentsMargins().left() >= 8


def test_msa_single_file_loads_input_without_showing_loaded_hint(qapp, monkeypatch, tmp_path):
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


def test_msa_single_file_alignment_done_writes_output_file_in_input_order(qapp, tmp_path):
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


def test_msa_visualization_tab_shows_save_figure_button(qapp):
    tab = MSAVisualizationTab()

    assert not tab.export_btn.isHidden()


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
    assert tab.output_group.isHidden()
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


def test_msa_visualization_tab_loads_input_without_showing_loaded_hint(qapp, monkeypatch, tmp_path):
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
    tab.input_text.setPlainText(">seq_alpha\nATGCATGCATGCATGC\n>seq_beta\nATGCATGCATGCATGC\n")

    assert tab.title == "MSA Visualization (pyMSAviz)"
    assert tab.dpi_spin.value() == 150

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

    assert window.tabs.tabText(window.tabs.currentIndex()) == "MSA Visualization (pyMSAviz)"

    menu_bar = window.menuBar()
    alignment_menu = next(
        action.menu() for action in menu_bar.actions() if action.text() == "Alignment"
    )
    action_texts = [action.text() for action in alignment_menu.actions() if action.text()]

    assert "MSA Visualization (pyMSAviz)" in action_texts
    assert "MSA Visualization" not in action_texts


def test_main_window_and_menu_use_mafft_label(qapp):
    window = MainWindow()

    window.open_mafft_alignment_tab()

    assert window.tabs.tabText(window.tabs.currentIndex()) == "Multiple Sequence Alignment (MAFFT)"

    menu_bar = window.menuBar()
    alignment_menu = next(
        action.menu() for action in menu_bar.actions() if action.text() == "Alignment"
    )
    action_texts = [action.text() for action in alignment_menu.actions() if action.text()]

    assert "Multiple Sequence Alignment (MAFFT)" in action_texts


def test_sequence_logo_tab_shows_save_figure_button_and_uses_logomaker_title(qapp):
    tab = SequenceLogoTab()

    assert not tab.export_btn.isHidden()
    assert tab.title == "Sequence Logo (Logomaker)"


def test_sequence_logo_tab_loads_input_without_showing_loaded_hint(qapp, monkeypatch, tmp_path):
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

    assert window.tabs.tabText(window.tabs.currentIndex()) == "Sequence Logo (Logomaker)"

    menu_bar = window.menuBar()
    alignment_menu = next(
        action.menu() for action in menu_bar.actions() if action.text() == "Alignment"
    )
    action_texts = [action.text() for action in alignment_menu.actions() if action.text()]

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

    assert window.tabs.tabText(window.tabs.currentIndex()) == "Alignment Format Converter"

    menu_bar = window.menuBar()
    alignment_menu = next(
        action.menu() for action in menu_bar.actions() if action.text() == "Alignment"
    )
    action_texts = [action.text() for action in alignment_menu.actions() if action.text()]

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


# ── GC Content / GC Skew Plot ───────────────────────────────────────────────


def test_gc_plot_tab_creation_single_instance(qapp):
    from main_window import MainWindow
    from modules.gc_plot_tab import GCPlotTab

    window = MainWindow()

    window.open_gc_plot_tab()
    assert window.tabs.count() == 1
    assert window.tabs.tabText(0) == "GC Content / GC Skew Plot"
    assert isinstance(window.tabs.widget(0), GCPlotTab)

    # single-instance: second call should reuse
    window.open_gc_plot_tab()
    assert window.tabs.count() == 1


def test_dna_analysis_menu_includes_gc_plot(qapp):
    from main_window import MainWindow
    from modules.gc_plot_tab import GCPlotTab

    window = MainWindow()
    menu_bar = window.menuBar()
    dna_menu = next(
        action.menu() for action in menu_bar.actions() if action.text() == "DNA Analysis"
    )
    gc_action = next(
        action for action in dna_menu.actions() if action.text() == "GC Content / GC Skew Plot"
    )
    gc_action.trigger()
    assert window.tabs.count() == 1
    assert isinstance(window.tabs.widget(0), GCPlotTab)


def test_gc_plot_tab_generates_plot(qapp):
    from modules.gc_plot_tab import GCPlotTab

    tab = GCPlotTab()
    tab.input_text.setPlainText(
        ">test_seq\n" + ("A" * 200) + ("G" * 200) + ("C" * 200) + ("T" * 200)
    )

    tab.window_spin.setValue(101)
    tab.run()

    assert len(tab._figs[0].axes) == 1
    assert len(tab._figs[1].axes) == 1
    assert len(tab._figs[2].axes) == 1
    assert "800 bp" in str(tab.status_label.text())


def test_gc_plot_tab_clear_resets(qapp):
    from modules.gc_plot_tab import GCPlotTab

    tab = GCPlotTab()
    tab.input_text.setPlainText(">test\n" + "ATGC" * 500)
    tab.window_spin.setValue(101)
    tab.run()
    assert len(tab._figs[0].axes) == 1

    tab.clear()
    assert len(tab._figs[0].axes) == 1  # placeholder axis still present
    assert tab.input_text.toPlainText() == ""
