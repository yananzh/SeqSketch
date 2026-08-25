import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QPalette
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


def test_stylesheet_keeps_placeholder_text_gray(qapp):
    """QSS resets the PlaceholderText role to black; the app must restore gray."""
    MainWindow()  # constructor applies QSS then restores the gray placeholder role
    color = qapp.palette().color(QPalette.ColorRole.PlaceholderText)
    assert color.name() == "#888888", f"placeholder color is {color.name()}"


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

    assert "Run" in button_texts
    assert "Help" in button_texts


def test_alignment_trimming_file_buttons_add_before_example(qapp):
    tab = AlignmentTrimmingTab()
    texts = [btn.text() for btn in tab.findChildren(QPushButton)]

    assert texts.index("Add Files") < texts.index("Example")
    assert "Result Folder" in texts


def test_alignment_trimming_result_folder_button_opens_outdir(qapp, monkeypatch, tmp_path):
    tab = AlignmentTrimmingTab()
    opened = []
    monkeypatch.setattr(
        "modules.trimal_tab.QDesktopServices.openUrl",
        lambda url: opened.append(url.toString()),
    )

    tab._open_output_folder()
    assert tab.status_label.text() == "No output folder selected yet"

    outdir = tmp_path / "trimmed"
    tab.outdir_edit.setText(str(outdir))
    tab._open_output_folder()
    assert tab.status_label.text() == "Output folder does not exist yet"

    outdir.mkdir()
    tab._open_output_folder()
    assert opened == [QUrl.fromLocalFile(str(outdir)).toString()]


def test_alignment_trimming_nogaps_method_builds_flag(qapp):
    tab = AlignmentTrimmingTab()
    tab.rb_nogaps.setChecked(True)

    assert tab._selected_method_name() == "nogaps"
    assert tab._build_flags() == ["-nogaps"]


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
    assert "automated1" in log_text
    assert "Output format" in log_text
    assert "Output folder" in log_text
    assert str(exe_path) in log_text
    assert str(prepared_input) in log_text
    assert str(expected_output) in log_text
    assert "-automated1" in log_text


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
    assert tab.run_btn.text() == "Run"
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

        def hasUrls(self):
            return True

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

    tab.path_edit.dropEvent(event)

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
        output_path=str(tmp_path / "aligned.fasta"),
    )
    commands = []
    results = []

    class _FakePopen:
        def __init__(self, cmd, **kwargs):
            commands.append(cmd)
            self.returncode = 0
            self.pid = 0

        def poll(self):
            return self.returncode

        def communicate(self, timeout=None):
            return ">seq1\nATG-C\n>seq2\nATGTC\n", ""

        def wait(self, timeout=None):
            return self.returncode

    def fake_run(cmd, **kwargs):
        # Version probe — no real subprocess in tests
        return type("R", (), {"stdout": "", "stderr": ""})()

    monkeypatch.setattr("modules.mafft_alignment_tab.subprocess.Popen", _FakePopen)
    monkeypatch.setattr("modules.mafft_alignment_tab.subprocess.run", fake_run)
    worker.finished.connect(results.append)

    worker.run()

    assert commands
    assert commands[0][0] == str(mafft_exe)
    assert "--auto" in commands[0]
    assert "--thread" in commands[0]
    assert "--clustalout" not in commands[0]
    assert results == [">seq1\nATG-C\n>seq2\nATGTC\n"]

    # Reproducibility: run_log.txt lands next to the requested output
    from utils.run_provenance import RUN_LOG_FILENAME

    log_path = tmp_path / RUN_LOG_FILENAME
    assert log_path.is_file()
    content = log_path.read_text(encoding="utf-8")
    assert "Tool: MAFFT" in content
    assert "Command:" in content



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

        def hasUrls(self):
            return True

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
    tab.path_edit.dropEvent(event)

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
    # MSA entries are now nested under a "Multiple Sequence Alignment" submenu
    msa_submenu = next(
        action.menu() for action in alignment_menu.actions()
        if action.text() == "Multiple Sequence Alignment"
    )
    sub_texts = [action.text() for action in msa_submenu.actions() if action.text()]
    assert "MAFFT" in sub_texts
    assert "Muscle5" in sub_texts


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
        "modules.sequence_logo_tab.QFileDialog.getOpenFileName",
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

        def hasUrls(self):
            return True

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
    tab.path_edit.dropEvent(event)

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


# ── Sequence Logo core logic ──────────────────────────────────────────────


def test_sequence_logo_pfm_probability_columns_sum_to_one(qapp):
    tab = SequenceLogoTab()
    pfm = tab.create_pfm(["ATGC", "ATGC", "ATGT"], "DNA")
    for idx in pfm.index:
        assert abs(float(pfm.loc[idx].sum()) - 1.0) < 1e-9


def test_sequence_logo_gap_only_column_contributes_zero(qapp):
    tab = SequenceLogoTab()
    # Column 3 is all gaps -> counts empty -> zero contribution
    pfm = tab.create_pfm(["ATG-", "ATG-", "ATG-"], "DNA")
    info = tab.pfm_to_information(pfm, "DNA")
    assert float(info.loc[3].sum()) == 0.0


def test_sequence_logo_conserved_column_near_max_information(qapp):
    tab = SequenceLogoTab()
    # Column 0 is all-A: entropy 0 -> information = 2 bits (DNA)
    pfm = tab.create_pfm(["AAAA", "AAAT"], "DNA")
    info = tab.pfm_to_information(pfm, "DNA")
    assert float(info.loc[0, "A"]) > 1.99


def test_sequence_logo_figure_widens_for_long_sequences(qapp):
    tab = SequenceLogoTab()
    seq = "ATGC" * 20  # 80 positions -> 80*0.35=28 -> capped at 15
    pfm = tab.create_pfm([seq, seq], "DNA")
    tab.generate_logo(pfm, "DNA", 2, "Probability")
    assert tab.figure.get_figwidth() == 15.0


def test_sequence_logo_title_contains_type_mode_and_counts(qapp):
    tab = SequenceLogoTab()
    pfm = tab.create_pfm(["ATGC", "ATGC"], "DNA")
    tab.generate_logo(pfm, "DNA", 2, "Information")
    title = tab.figure.axes[0].get_title()
    assert "DNA" in title
    assert "Information" in title
    assert "2 seqs" in title
    assert "4 pos" in title


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

    assert tab._stats_table.minimumHeight() >= 200
    assert tab._top10_table.minimumHeight() >= 190

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


def test_gc_plot_tab_generates_plot(qapp, tmp_path):
    from modules.gc_plot_tab import GCPlotTab

    tab = GCPlotTab()
    seq_file = tmp_path / "seq.fasta"
    seq_file.write_text(
        ">test_seq\n" + ("A" * 200) + ("G" * 200) + ("C" * 200) + ("T" * 200),
        encoding="utf-8",
    )
    tab.input_path_edit.setText(str(seq_file))

    tab.window_spin.setValue(101)
    tab.run()

    assert len(tab._figs[0].axes) == 1
    assert len(tab._figs[1].axes) == 1
    assert len(tab._figs[2].axes) == 1
    assert "800 bp" in str(tab.status_label.text())


def test_gc_plot_tab_clear_resets(qapp, tmp_path):
    from modules.gc_plot_tab import GCPlotTab

    tab = GCPlotTab()
    seq_file = tmp_path / "seq.fasta"
    seq_file.write_text(">test\n" + "ATGC" * 500, encoding="utf-8")
    tab.input_path_edit.setText(str(seq_file))
    tab.window_spin.setValue(101)
    tab.run()
    assert len(tab._figs[0].axes) == 1

    tab.clear()
    assert len(tab._figs[0].axes) == 1  # placeholder axis still present
    assert tab.input_path_edit.text() == ""


# ── CpG Island Finder / SSR Finder (new DNA tabs) ──────────────────────────


def test_dna_analysis_menu_includes_cpg_island_and_ssr(qapp):
    window = MainWindow()
    menu_bar = window.menuBar()
    dna_menu = next(
        action.menu() for action in menu_bar.actions() if action.text() == "DNA Analysis"
    )
    action_texts = [action.text() for action in dna_menu.actions() if action.text()]

    assert "CpG Island Finder" in action_texts
    assert "SSR / Microsatellite Finder" in action_texts


def test_main_window_opens_cpg_island_and_ssr_tabs(qapp):
    from modules.cpg_island_tab import CpGIslandTab
    from modules.ssr_finder_tab import SsrFinderTab

    window = MainWindow()
    window.open_cpg_island_tab()
    assert isinstance(window.tabs.widget(0), CpGIslandTab)
    window.open_ssr_finder_tab()
    assert isinstance(window.tabs.widget(1), SsrFinderTab)


def test_cpg_island_finder_detects_embedded_island(qapp, tmp_path):
    from modules.cpg_island_tab import CpGIslandTab, find_cpg_islands

    # 400 bp AT-rich flank + 260 bp pure-CG island + 400 bp AT-rich flank.
    # Windows partially overlapping the flanks still qualify, so the merged
    # island extends a bit beyond the pure-CG region (verified: 351-710).
    seq = "AT" * 200 + "CG" * 130 + "AT" * 200
    islands = find_cpg_islands(seq)
    assert len(islands) == 1
    island = islands[0]
    assert island["start"] == 351
    assert island["end"] == 710
    assert island["length"] == 360

    tab = CpGIslandTab()
    seq_file = tmp_path / "island.fasta"
    seq_file.write_text(">test\n" + seq, encoding="utf-8")
    tab.input_path_edit.setText(str(seq_file))
    tab.run()
    assert tab._island_table.rowCount() == 1
    assert tab._island_table.item(0, 1).text() == "351"
    assert "Found 1 CpG island(s), total 360 bp" in str(tab.status_label.text())


def test_cpg_island_tab_clear_resets(qapp, tmp_path):
    from modules.cpg_island_tab import CpGIslandTab

    tab = CpGIslandTab()
    seq_file = tmp_path / "seq.fasta"
    seq_file.write_text(">test\n" + "AT" * 200 + "CG" * 130 + "AT" * 200, encoding="utf-8")
    tab.input_path_edit.setText(str(seq_file))
    tab.run()
    assert tab._island_table.rowCount() == 1

    tab.clear()
    assert tab._island_table.rowCount() == 0
    assert tab.input_path_edit.text() == ""


def test_cpg_island_criteria_presets(qapp):
    from modules.cpg_island_tab import CpGIslandTab

    tab = CpGIslandTab()
    assert tab._criteria_combo.currentText() == "Gardiner-Garden & Frommer 1987"
    assert tab.window_spin.value() == 100
    assert tab.min_len_spin.value() == 200
    assert tab.gc_spin.value() == 50.0
    assert tab.oe_spin.value() == 0.6

    # Takai & Jones 2002 applies the stricter human-genome criteria.
    tab._criteria_combo.setCurrentText("Takai & Jones 2002")
    assert tab.min_len_spin.value() == 500
    assert tab.gc_spin.value() == 55.0
    assert tab.oe_spin.value() == 0.65

    # Manual spin edit switches the preset to Custom.
    tab.gc_spin.setValue(60.0)
    assert tab._criteria_combo.currentText() == "Custom"

    # Re-selecting a preset re-applies its values without tripping the guard.
    tab._criteria_combo.setCurrentText("Relaxed")
    assert tab.min_len_spin.value() == 100
    assert tab._criteria_combo.currentText() == "Relaxed"


def test_cpg_island_multirecord_all_and_single_modes(qapp, tmp_path):
    from modules.cpg_island_tab import CpGIslandTab

    seq_file = tmp_path / "multi.fasta"
    seq_file.write_text(
        ">island_rec\n" + "AT" * 200 + "CG" * 130 + "AT" * 200 + "\n"
        ">no_island\n" + "AT" * 300 + "\n",
        encoding="utf-8",
    )
    tab = CpGIslandTab()
    tab.input_path_edit.setText(str(seq_file))
    tab.run()

    # Default: all-records mode -> Record column.
    assert tab._record_combo.count() == 3
    assert tab._all_records_mode
    assert tab._island_table.columnCount() == 9
    assert tab._island_table.rowCount() == 1
    assert tab._island_table.item(0, 8).text() == "island_rec"
    assert "across 2 sequences" in str(tab.status_label.text())

    # Switch to the no-island record -> empty result with 8 columns.
    tab._record_combo.setCurrentIndex(2)  # no_island
    assert not tab._all_records_mode
    assert tab._island_table.columnCount() == 8
    assert tab._island_table.rowCount() == 0
    assert "No CpG islands found" in str(tab.status_label.text())
    assert not tab._export_btn.isEnabled()

    # Back to the island record -> per-record status text.
    tab._record_combo.setCurrentIndex(1)  # island_rec
    assert tab._island_table.rowCount() == 1
    assert "island_rec" in str(tab.status_label.text())
    assert "Found 1 CpG island(s)" in str(tab.status_label.text())


def test_cpg_island_table_sorts_numerically_by_start(qapp, tmp_path):
    from modules.cpg_island_tab import CpGIslandTab

    # Two islands of different sizes at different positions.
    seq = "AT" * 50 + "CG" * 130 + "AT" * 50 + "AT" * 50 + "CG" * 200 + "AT" * 50
    tab = CpGIslandTab()
    seq_file = tmp_path / "seq.fasta"
    seq_file.write_text(">test\n" + seq, encoding="utf-8")
    tab.input_path_edit.setText(str(seq_file))
    tab.run()

    assert tab._island_table.isSortingEnabled()
    assert tab._island_table.rowCount() == 2
    starts = [int(tab._island_table.item(r, 1).text()) for r in range(2)]
    assert starts == sorted(starts), f"rows not sorted by start: {starts}"

    # Sorting by a different numeric column compares values, not text.
    tab._island_table.sortItems(3, Qt.SortOrder.DescendingOrder)
    lengths = [int(tab._island_table.item(r, 3).text()) for r in range(2)]
    assert lengths == sorted(lengths, reverse=True), f"lengths not sorted: {lengths}"


def test_cpg_island_export_csv_with_statistics(qapp, tmp_path, monkeypatch):
    from modules.cpg_island_tab import CpGIslandTab

    seq_file = tmp_path / "seq.fasta"
    seq_file.write_text(">test\n" + "AT" * 200 + "CG" * 130 + "AT" * 200, encoding="utf-8")
    tab = CpGIslandTab()
    tab.input_path_edit.setText(str(seq_file))
    tab.run()
    assert tab._export_btn.isEnabled()

    out = tmp_path / "out.csv"
    monkeypatch.setattr(
        "modules.cpg_island_tab.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **k: (str(out), "CSV Files (*.csv)")),
    )
    tab._export_csv()
    lines = out.read_text(encoding="utf-8-sig").strip().splitlines()
    assert lines[0] == "== Statistics =="
    header_idx = next(i for i, ln in enumerate(lines) if ln.startswith("#,Start"))
    assert any(ln.startswith("CpG_islands,1") for ln in lines[:header_idx])
    assert any(ln.startswith("Island_coverage_pct,") for ln in lines[:header_idx])
    assert any(ln.startswith("Genome_CpG_o/e,") for ln in lines[:header_idx])
    data = [ln for ln in lines[header_idx + 1 :] if ln]
    assert len(data) == 1
    assert data[0].startswith("1,351,")

    tab.clear()
    assert not tab._export_btn.isEnabled()


def test_ssr_finder_detects_known_repeats(qapp, tmp_path):
    from modules.ssr_finder_tab import SsrFinderTab

    seq = (
        "A" * 5
        + "AT" * 9
        + "C" * 5
        + "AAT" * 6
        + "G" * 5
        + "GT" * 8
        + "C" * 5
        + "CTTA" * 5
        + "A" * 5
    )
    tab = SsrFinderTab()
    seq_file = tmp_path / "ssr.fasta"
    seq_file.write_text(">test\n" + seq, encoding="utf-8")
    tab.input_path_edit.setText(str(seq_file))
    tab.run()

    rows = tab._ssr_table.rowCount()
    motifs = [tab._ssr_table.item(r, 2).text() for r in range(rows)]
    types = [tab._ssr_table.item(r, 1).text() for r in range(rows)]
    assert "(AT)9" in motifs
    assert "(AAT)6" in motifs
    assert "(GT)8" in motifs
    assert "(CTTA)5" in motifs
    assert types.count("Perfect") == 4
    assert "Compound" in types
    assert "Found 4 perfect SSR(s), 1 compound" in str(tab.status_label.text())


def test_ssr_finder_tab_clear_resets(qapp, tmp_path):
    from modules.ssr_finder_tab import SsrFinderTab

    tab = SsrFinderTab()
    seq_file = tmp_path / "ssr.fasta"
    seq_file.write_text(">test\n" + "AT" * 12, encoding="utf-8")
    tab.input_path_edit.setText(str(seq_file))
    tab.run()
    assert tab._ssr_table.rowCount() == 1

    tab.clear()
    assert tab._ssr_table.rowCount() == 0
    assert tab.input_path_edit.text() == ""


def test_ssr_finder_threshold_presets(qapp):
    from modules.ssr_finder_tab import SsrFinderTab

    tab = SsrFinderTab()
    assert tab._preset_combo.currentText() == "MISA default"

    # All six threshold spin boxes share one uniform width.
    widths = {sp.minimumWidth() for sp in tab._thresh_spins.values()}
    assert len(widths) == 1
    assert widths.pop() == 80

    # Preset selection applies values to all six spin boxes.
    tab._preset_combo.setCurrentText("Stringent")
    assert tab._thresh_spins[1].value() == 12
    assert tab._thresh_spins[2].value() == 8
    assert tab._thresh_spins[6].value() == 6

    # Manual spin edit switches the preset to Custom.
    tab._thresh_spins[3].setValue(3)
    assert tab._preset_combo.currentText() == "Custom"

    # Re-selecting a preset re-applies its values without tripping the guard.
    tab._preset_combo.setCurrentText("Relaxed")
    assert tab._thresh_spins[1].value() == 8
    assert tab._thresh_spins[4].value() == 4
    assert tab._preset_combo.currentText() == "Relaxed"


def test_ssr_finder_table_sorts_numerically_by_start(qapp, tmp_path):
    from modules.ssr_finder_tab import SsrFinderTab

    seq = (
        "A" * 5
        + "AT" * 9
        + "C" * 5
        + "AAT" * 6
        + "G" * 5
        + "GT" * 8
        + "C" * 5
        + "CTTA" * 5
        + "A" * 5
    )
    tab = SsrFinderTab()
    seq_file = tmp_path / "ssr.fasta"
    seq_file.write_text(">test\n" + seq, encoding="utf-8")
    tab.input_path_edit.setText(str(seq_file))
    tab.run()

    assert tab._ssr_table.isSortingEnabled()
    starts = [int(tab._ssr_table.item(r, 5).text()) for r in range(tab._ssr_table.rowCount())]
    assert starts == sorted(starts), f"rows not sorted by start: {starts}"

    # Sorting by a different numeric column also compares values, not text.
    tab._ssr_table.sortItems(4, Qt.SortOrder.DescendingOrder)
    repeats = [int(tab._ssr_table.item(r, 4).text()) for r in range(tab._ssr_table.rowCount())]
    assert repeats == sorted(repeats, reverse=True), f"repeats not sorted: {repeats}"


def test_ssr_finder_multirecord_all_and_single_modes(qapp, tmp_path):
    from modules.ssr_finder_tab import SsrFinderTab

    seq_file = tmp_path / "multi.fasta"
    seq_file.write_text(
        ">rec_one\n" + "A" * 5 + "AT" * 8 + "A" * 5 + "\n"
        ">rec_two\n" + "C" * 5 + "GT" * 7 + "C" * 5 + "\n",
        encoding="utf-8",
    )
    tab = SsrFinderTab()
    tab.input_path_edit.setText(str(seq_file))
    tab.run()

    # Default: all-records mode -> Record column.
    assert tab._record_combo.count() == 3
    assert tab._all_records_mode
    assert tab._ssr_table.columnCount() == 9
    assert tab._ssr_table.rowCount() == 2
    assert "across 2 sequences" in str(tab.status_label.text())
    records = {tab._ssr_table.item(r, 8).text() for r in range(2)}
    assert records == {"rec_one", "rec_two"}

    # Switch to a single record -> no Record column, per-record status.
    tab._record_combo.setCurrentIndex(2)  # rec_two
    assert not tab._all_records_mode
    assert tab._ssr_table.columnCount() == 8
    assert tab._ssr_table.rowCount() == 1
    assert "rec_two" in str(tab.status_label.text())
    assert tab._ssr_table.item(0, 2).text() == "(GT)7"

    # Switch back to all records.
    tab._record_combo.setCurrentIndex(0)
    assert tab._all_records_mode
    assert tab._ssr_table.columnCount() == 9


def test_ssr_finder_single_record_combo_has_one_option(qapp, tmp_path):
    from modules.ssr_finder_tab import SsrFinderTab

    tab = SsrFinderTab()
    # Empty combo shows a placeholder hint before any file is loaded.
    assert tab._record_combo.count() == 0
    assert tab._record_combo.placeholderText() == (
        "Run first, then select a record to view (multi-record files)"
    )

    seq_file = tmp_path / "single.fasta"
    seq_file.write_text(">only_one\n" + "A" * 5 + "AT" * 8 + "A" * 5 + "\n", encoding="utf-8")
    tab.input_path_edit.setText(str(seq_file))
    tab.run()

    # A single-record file must not offer the redundant "All records (1)" entry.
    assert tab._record_combo.count() == 1
    assert tab._record_combo.itemText(0) == "only_one"
    assert not tab._all_records_mode
    assert tab._ssr_table.columnCount() == 8
    assert tab._ssr_table.rowCount() == 1
    assert "only_one" in str(tab.status_label.text())

    tab.clear()
    assert tab._record_combo.count() == 0
    assert tab._record_combo.placeholderText() == (
        "Run first, then select a record to view (multi-record files)"
    )


def test_ssr_finder_export_csv(qapp, tmp_path, monkeypatch):
    from modules.ssr_finder_tab import SsrFinderTab

    seq = (
        "A" * 5
        + "AT" * 9
        + "C" * 5
        + "AAT" * 6
        + "G" * 5
        + "GT" * 8
        + "C" * 5
        + "CTTA" * 5
        + "A" * 5
    )
    tab = SsrFinderTab()
    seq_file = tmp_path / "ssr.fasta"
    seq_file.write_text(">test\n" + seq, encoding="utf-8")
    tab.input_path_edit.setText(str(seq_file))
    tab.run()
    assert tab._export_btn.isEnabled()

    out = tmp_path / "out.csv"
    monkeypatch.setattr(
        "modules.ssr_finder_tab.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **k: (str(out), "CSV Files (*.csv)")),
    )
    tab._export_csv()
    assert out.is_file()
    lines = out.read_text(encoding="utf-8-sig").strip().splitlines()
    assert lines[0] == "== Statistics =="
    header_idx = next(i for i, ln in enumerate(lines) if ln.startswith("#,Type,Motif"))
    assert any(ln.startswith("Perfect_SSRs,4") for ln in lines[:header_idx])
    assert any(ln.startswith("Compound_SSRs,1") for ln in lines[:header_idx])
    assert any(ln.startswith("SSR_density_per_Mb,") for ln in lines[:header_idx])
    assert any(ln.startswith("SSRs_Di,") for ln in lines[:header_idx])
    data = lines[header_idx + 1 :]
    assert sum(1 for ln in data if "Perfect" in ln) == 4
    assert any("(CTTA)5" in ln for ln in data)
    assert "Exported" in str(tab.status_label.text())

    tab.clear()
    assert not tab._export_btn.isEnabled()


def test_ssr_finder_export_csv_includes_record_column(qapp, tmp_path, monkeypatch):
    from modules.ssr_finder_tab import SsrFinderTab

    seq_file = tmp_path / "multi.fasta"
    seq_file.write_text(
        ">rec_one\n" + "A" * 5 + "AT" * 8 + "A" * 5 + "\n"
        ">rec_two\n" + "C" * 5 + "GT" * 7 + "C" * 5 + "\n",
        encoding="utf-8",
    )
    tab = SsrFinderTab()
    tab.input_path_edit.setText(str(seq_file))
    tab.run()

    out = tmp_path / "out.csv"
    monkeypatch.setattr(
        "modules.ssr_finder_tab.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **k: (str(out), "CSV Files (*.csv)")),
    )
    tab._export_csv()
    lines = out.read_text(encoding="utf-8-sig").strip().splitlines()
    header_idx = next(i for i, ln in enumerate(lines) if ln.startswith("#,Type,Motif"))
    assert lines[header_idx].endswith("Record")
    assert any(ln.startswith("Sequences,2") for ln in lines[:header_idx])
    data = [ln for ln in lines[header_idx + 1 :] if ln]
    assert all(ln.endswith("rec_one") or ln.endswith("rec_two") for ln in data)


def test_phylo_tabs_status_bar_button_sizes_unified(qapp):
    """All Phylogenetic Tree tabs use consistent status-bar button widths:
    narrow for one-word labels, wider for two-word labels."""
    from modules.distance_tree_tab import DistanceTreeTab
    from modules.iqtree_tab import IqTreeTab
    from modules.one_step_multigenephy_tab import OneStepMultiGenePhyTab
    from modules.partition_concat_tab import PartitionConcatTab
    from modules.tree_visualization_toytree_tab import ToytreeVisualizationTab
    from modules.trimal_tab import AlignmentTrimmingTab
    from utils.common_components import (
        STATUS_BUTTON_WIDTH_DOUBLE,
        STATUS_BUTTON_WIDTH_SINGLE,
    )

    tabs = [
        AlignmentTrimmingTab(),
        PartitionConcatTab(),
        DistanceTreeTab(),
        IqTreeTab(),
        OneStepMultiGenePhyTab(),
        ToytreeVisualizationTab(),
    ]
    for tab in tabs:
        for i in range(tab.status_layout.count()):
            widget = tab.status_layout.itemAt(i).widget()
            if isinstance(widget, QPushButton):
                expected = (
                    STATUS_BUTTON_WIDTH_DOUBLE
                    if len(widget.text().split()) > 1
                    else STATUS_BUTTON_WIDTH_SINGLE
                )
                assert (widget.minimumWidth(), widget.maximumWidth()) == (expected, expected), (
                    type(tab).__name__,
                    widget.text(),
                )


def test_every_tab_status_bar_button_sizes_unified(qapp):
    """Every tab in the app follows the one-word/two-word status button width
    rule, not just the phylogenetic tabs."""
    import importlib
    import inspect
    import pkgutil

    import modules
    from modules.codon_usage_tab import CodonUsageTab
    from modules.favorites_manager import BookmarkManager
    from modules.primer3_gui import PrimerDesignTab
    from modules.primer_analysis_tab import PrimerAnalysisTab
    from modules.sanger_tab import SangerTab
    from modules.sanger_viewer_tab import SangerViewerTab
    from utils.common_components import (
        STATUS_BUTTON_WIDTH_DOUBLE,
        STATUS_BUTTON_WIDTH_SINGLE,
        BaseTabWidget,
    )

    def instantiable_no_args(cls) -> bool:
        try:
            params = list(inspect.signature(cls.__init__).parameters.values())[1:]
        except (TypeError, ValueError):
            return False
        return all(
            p.default is not inspect.Parameter.empty
            or p.kind
            in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
            for p in params
        )

    tab_classes = {
        SangerTab,
        SangerViewerTab,
        PrimerDesignTab,
        PrimerAnalysisTab,
        CodonUsageTab,
        BookmarkManager,
    }
    for mod_info in pkgutil.iter_modules(modules.__path__):
        mod = importlib.import_module(f"modules.{mod_info.name}")
        for obj in vars(mod).values():
            if (
                inspect.isclass(obj)
                and issubclass(obj, BaseTabWidget)
                and obj.__module__ == mod.__name__
                and instantiable_no_args(obj)
            ):
                tab_classes.add(obj)

    assert len(tab_classes) > 20, "tab discovery unexpectedly found few tabs"

    checked = 0
    for cls in sorted(tab_classes, key=lambda c: c.__name__):
        tab = cls()
        for i in range(tab.status_layout.count()):
            widget = tab.status_layout.itemAt(i).widget()
            if isinstance(widget, QPushButton):
                expected = (
                    STATUS_BUTTON_WIDTH_DOUBLE
                    if len(widget.text().split()) > 1
                    else STATUS_BUTTON_WIDTH_SINGLE
                )
                assert (
                    widget.minimumWidth(),
                    widget.maximumWidth(),
                ) == (expected, expected), (
                    cls.__name__,
                    widget.text(),
                )
                checked += 1
    assert checked > 80, f"only {checked} status buttons checked"


def test_msa_rejects_duplicate_input_headers_before_alignment(qapp, monkeypatch):
    # Duplicate headers must fail loudly instead of the dict parser silently
    # keeping only the last copy of each sequence.
    from modules.multiple_sequence_alignment_tab import (
        _find_duplicate_headers,
        _reject_duplicate_headers,
    )

    dup_text = ">seqA\nATGC\n>seqB\nTTTT\n>seqA\nGGGG\n"
    assert _find_duplicate_headers(dup_text) == ["seqA"]
    assert _find_duplicate_headers(">seqA\nATGC\n>seqB\nTTTT\n") == []

    with pytest.raises(ValueError, match="duplicate sequence header"):
        _reject_duplicate_headers(dup_text, "input.fasta")

    # Unique input passes
    _reject_duplicate_headers(">seqA\nATGC\n>seqB\nTTTT\n", "input.fasta")


def test_msa_batch_worker_rejects_duplicate_headers(tmp_path):
    from modules.multiple_sequence_alignment_tab import _MuscleBatchWorker

    dup = tmp_path / "dup.fasta"
    dup.write_text(">seqA\nATGC\n>seqB\nTTTT\n>seqA\nGGGG\n", encoding="utf-8")
    # Batch mode summarizes per-file failures in its finished message, so the
    # exe never runs — a marker file is enough to pass the isfile check.
    muscle_exe = tmp_path / "muscle.exe"
    muscle_exe.write_text("", encoding="utf-8")

    worker = _MuscleBatchWorker(
        input_files=[str(dup)],
        output_dir=str(tmp_path / "out"),
        method="fast",
        threads=1,
        muscle_exe=str(muscle_exe),
        output_mode="FASTA (aligned)",
        naming_pattern="{stem}_{method}.{ext}",
        overwrite=True,
    )
    messages = []
    worker.batch_finished.connect(messages.append)
    worker.run()

    assert messages and "duplicate sequence header" in messages[0]
    assert "seqA" in messages[0]
