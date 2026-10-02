import os

from PyQt6.QtCore import QElapsedTimer, Qt, QThread, QTimer
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTabWidget,
)

from menus import create_menus
from utils.app_paths import resource_path
from utils.app_version import APP_VERSION
from utils.common_components import BaseWorker, park_qthread
from utils.task_lifecycle import (
    mark_closing,
    request_task_stop,
    skip_when_closing,
    task_objects,
    tasks_running,
)
from utils.update_check import (
    RELEASES_PAGE_URL,
    fetch_latest_version,
    is_newer_version,
)

# A window close waits for running tasks to stop, but never forever: after
# this deadline, still-running threads are parked and the close proceeds.
_CLOSE_DEADLINE_MS = 10_000


class UpdateCheckWorker(BaseWorker):
    """Fetch the latest release version off the GUI thread."""

    def __init__(self, timeout=5.0):
        super().__init__()
        self.timeout = timeout

    def run(self):
        try:
            latest = fetch_latest_version(timeout=self.timeout)
        except Exception as exc:
            self.emit_error(f"{type(exc).__name__}: {exc}")
            return
        self.emit_finished(latest)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SeqSketch")
        self.resize(920, 700)
        # Lock the default size as the minimum: some tabs (e.g. the MSA tabs'
        # batch page) carry a large minimumSizeHint that would otherwise
        # silently inflate the window beyond its default height.
        self.setMinimumSize(920, 700)
        self._init_width = 920
        icon_path = resource_path("window_logo.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.child_windows = []
        self._update_worker = None
        self._update_thread = None
        self._update_button = None
        self._update_dialog = None
        self._closing_tabs = []
        self._closing_requested = False
        self._close_elapsed = QElapsedTimer()
        self._close_timer = QTimer(self)
        self._close_timer.setInterval(25)
        self._close_timer.timeout.connect(self._finish_closing_tasks)
        self._init_ui()
        self._load_style()

    def _init_ui(self):
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.setCentralWidget(self.tabs)
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        create_menus(self)

    def _load_style(self, dark=False):
        qss_path = resource_path("styles.qss")
        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                qss = f.read()
            self.setStyleSheet(qss)
        except Exception as e:
            print("QSS load failed:", e)
            return
        # Applying a stylesheet resets the PlaceholderText palette role to
        # black (indistinguishable from real input). Restore a muted gray so
        # placeholder hints stay visually distinct — must run after setStyleSheet.
        from PyQt6.QtGui import QColor, QPalette

        app = QApplication.instance()
        if app is not None:
            pal = app.palette()
            pal.setColor(QPalette.ColorRole.PlaceholderText, QColor("#888888"))
            app.setPalette(pal)

    def show_message(self, text, error=False):
        if error:
            QMessageBox.critical(self, "Error", text)
        else:
            self.status.showMessage(text, 5000)

    def _find_or_open(self, tab_class, title, factory=None, reuse=True):
        """Reuse an existing tab of *tab_class*, or create a new one.

        Args:
            tab_class: tab class used for the isinstance reuse check.
            title: tab title text.
            factory: callable returning a new tab; defaults to tab_class().
            reuse: when True, focus an existing tab instead of creating a new one.
        """
        if reuse:
            for i in range(self.tabs.count()):
                if isinstance(self.tabs.widget(i), tab_class):
                    self.tabs.setCurrentIndex(i)
                    return None
        tab = (factory or tab_class)()
        self.tabs.addTab(tab, title)
        self.tabs.setCurrentWidget(tab)
        # Prevent wider tabs from expanding the main window
        if hasattr(self, "_init_width"):
            self.resize(self._init_width, self.height())
        return tab

    def close_tab(self, index):
        widget = self.tabs.widget(index)
        if widget is None:
            return
        mark_closing(widget)
        objects = task_objects(widget)
        self.tabs.removeTab(index)
        self._closing_tabs.append((widget, objects))
        for obj in objects:
            request_task_stop(obj)
        self._close_timer.start()
        self._finish_closing_tasks()

    def _finish_closing_tasks(self):
        for widget, objects in list(self._closing_tabs):
            if tasks_running(objects):
                continue
            shutdown = getattr(widget, "shutdown", None)
            if callable(shutdown):
                shutdown()
            widget.deleteLater()
            self._closing_tabs.remove((widget, objects))
        if self._closing_tabs or tasks_running(task_objects(self)):
            if self._closing_requested and self._close_deadline_exceeded():
                self._abandon_closing_tasks()
                QTimer.singleShot(0, self.close)
            return
        self._close_timer.stop()
        if self._closing_requested:
            QTimer.singleShot(0, self.close)

    def _close_deadline_exceeded(self):
        return (
            self._close_elapsed.isValid()
            and self._close_elapsed.elapsed() >= _CLOSE_DEADLINE_MS
        )

    def _abandon_closing_tasks(self):
        """Give up waiting for tasks that ignore their stop request.

        Running QThreads are parked (detached and destroyed on their native
        finished signal) so closing never destroys a live thread; the owner
        widgets are left for process exit.
        """
        for widget, objects in list(self._closing_tabs):
            for obj in objects:
                park_qthread(obj)
            self._closing_tabs.remove((widget, objects))
        for obj in task_objects(self):
            park_qthread(obj)
        self._close_timer.stop()

    def closeEvent(self, event):
        if not self._closing_requested:
            self._closing_requested = True
            self._close_elapsed.start()
            mark_closing(self)
            self.tabs.setEnabled(False)
            self.menuBar().setEnabled(False)
            while self.tabs.count():
                self.close_tab(0)
            for obj in task_objects(self):
                request_task_stop(obj)
        if self._closing_tabs or tasks_running(task_objects(self)):
            if self._close_deadline_exceeded():
                self._abandon_closing_tasks()
                event.accept()
                return
            event.ignore()
            self.status.showMessage("Stopping background tasks before closing...")
            self._close_timer.start()
        else:
            event.accept()

    # ── FASTA Tools ──────────────────────────────────────────────────────

    def open_sequence_statistics_tab(self):
        from modules.sequence_statistics_tab import SequenceStatisticsTab

        self._find_or_open(SequenceStatisticsTab, "FASTA Statistics")

    def open_simplify_ids_tab(self):
        from modules.simplify_ids_tab import SimplifyIDsTab

        self._find_or_open(SimplifyIDsTab, "Simplify Headers")

    def open_extract_by_id_tab(self):
        from modules.extract_by_id_tab import ExtractByIDTab

        self._find_or_open(ExtractByIDTab, "Filter by IDs")

    def open_extract_by_regex_tab(self):
        from modules.extract_by_regex_tab import ExtractByRegexTab

        self._find_or_open(ExtractByRegexTab, "Regex Filter")

    def open_download_from_ncbi_tab(self):
        from modules.download_from_ncbi_tab import DownloadFromNCBITab

        self._find_or_open(DownloadFromNCBITab, "NCBI Download")

    def open_batch_rename_ids_tab(self):
        from modules.batch_rename_ids_tab import BatchRenameIDsTab

        self._find_or_open(BatchRenameIDsTab, "Rename IDs")

    def open_deduplicate_tab(self):
        from modules.deduplicate_tab import DeduplicateTab

        self._find_or_open(DeduplicateTab, "Deduplicate")

    def open_filter_by_length_tab(self):
        from modules.filter_by_length_tab import FilterByLengthTab

        self._find_or_open(FilterByLengthTab, "Filter by Length")

    def open_concat_fasta_tab(self):
        from modules.concat_fasta_tab import ConcatFastaTab

        self._find_or_open(ConcatFastaTab, "Concatenate FASTA")

    def open_split_fasta_tab(self):
        from modules.split_fasta_tab import SplitFastaTab

        self._find_or_open(SplitFastaTab, "Split FASTA")

    def open_sort_fasta_tab(self):
        from modules.sort_fasta_tab import SortFastaTab

        self._find_or_open(SortFastaTab, "Sort FASTA")

    def open_fasta_table_converter_tab(self):
        from modules.fasta_table_converter_tab import FastaTableConverterTab

        self._find_or_open(FastaTableConverterTab, "FASTA \u2194 Table")

    # ── DNA Analysis ─────────────────────────────────────────────────────

    def open_rna_tab(self):
        from modules.rna_tab import RNATab

        self._find_or_open(RNATab, "Convert to RNA", reuse=False)

    def _open_complement_tools_tab(self, mode: str):
        from modules.complement_tab import ComplementTab

        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, ComplementTab):
                widget.set_mode(mode)
                self.tabs.setCurrentIndex(i)
                return
        tab = ComplementTab()
        tab.set_mode(mode)
        self.tabs.addTab(tab, "Complement/Reverse Complement")
        self.tabs.setCurrentWidget(tab)

    def open_complement_tab(self):
        self._open_complement_tools_tab("Complement")

    def open_reverse_complement_tab(self):
        self._open_complement_tools_tab("Reverse Complement")

    def open_translate_tab(self):
        from modules.translate_tab import TranslateTab

        self._find_or_open(TranslateTab, "Translate", reuse=False)

    def open_orf_tab(self):
        from modules.orf_tab import ORFTab

        self._find_or_open(ORFTab, "ORF Finder", reuse=False)

    def open_sanger_tab(self):
        from modules.sanger_tab import SangerTab

        self._find_or_open(SangerTab, "Sanger Sequence Assembly", reuse=False)

    def open_sanger_viewer_tab(self):
        from modules.sanger_viewer_tab import SangerViewerTab

        self._find_or_open(SangerViewerTab, "Sanger Chromatogram Viewer", reuse=False)

    def open_codon_usage_tab(self):
        from modules.codon_usage_tab import CodonUsageTab

        self._find_or_open(
            CodonUsageTab,
            "Codon Usage Analysis",
            factory=lambda: CodonUsageTab(),
        )

    def open_restriction_enzyme_tab(self):
        from modules.restriction_enzyme_tab import RestrictionEnzymeTab

        self._find_or_open(RestrictionEnzymeTab, "Restriction Enzyme Analysis", reuse=False)

    def open_gc_plot_tab(self):
        from modules.gc_plot_tab import GCPlotTab

        self._find_or_open(GCPlotTab, "GC Content / GC Skew Plot")

    def open_cpg_island_tab(self):
        from modules.cpg_island_tab import CpGIslandTab

        self._find_or_open(CpGIslandTab, "CpG Island Finder", reuse=False)

    def open_ssr_finder_tab(self):
        from modules.ssr_finder_tab import SsrFinderTab

        self._find_or_open(SsrFinderTab, "SSR / Microsatellite Finder", reuse=False)

    # ── Protein Analysis ─────────────────────────────────────────────────

    def open_amino_acid_composition_tab(self):
        from modules.amino_acid_composition_tab import AminoAcidCompositionTab

        self._find_or_open(AminoAcidCompositionTab, "Amino Acid Composition")

    def open_physicochemical_properties_tab(self):
        from modules.physicochemical_properties_tab import PhysicochemicalPropertiesTab

        self._find_or_open(PhysicochemicalPropertiesTab, "Physicochemical Properties")

    def open_hydrophobicity_plot_tab(self):
        from modules.hydrophobicity_plot_tab import HydrophobicityPlotTab

        self._find_or_open(HydrophobicityPlotTab, "Hydrophobicity Plot")

    def open_protease_cleavage_tab(self):
        from modules.protease_cleavage_tab import ProteaseCleavageTab

        self._find_or_open(ProteaseCleavageTab, "Protease Cleavage Map")

    # ── Alignment ────────────────────────────────────────────────────────

    def open_pairwise_alignment_tab(self):
        from modules.pairwise_alignment_tab import PairwiseAlignmentTab

        self._find_or_open(PairwiseAlignmentTab, "Pairwise Sequence Alignment")

    def open_dotplot_tab(self):
        from modules.dotplot_tab import DotPlotTab

        self._find_or_open(DotPlotTab, "DotPlot")

    def open_multiple_sequence_alignment_tab(self):
        from modules.multiple_sequence_alignment_tab import MultipleSequenceAlignmentTab

        self._find_or_open(MultipleSequenceAlignmentTab, "Multiple Sequence Alignment (Muscle5)")

    def open_mafft_alignment_tab(self):
        from modules.mafft_alignment_tab import MafftAlignmentTab

        self._find_or_open(MafftAlignmentTab, "Multiple Sequence Alignment (MAFFT)")

    def open_alignment_format_converter_tab(self):
        from modules.alignment_format_converter_tab import AlignmentFormatConverterTab

        self._find_or_open(AlignmentFormatConverterTab, "Alignment Format Converter")

    def open_msa_visualization_tab(self):
        from modules.msa_visualization_tab import MSAVisualizationTab

        self._find_or_open(MSAVisualizationTab, "MSA Visualization (pyMSAviz)")

    def open_sequence_logo_tab(self):
        from modules.sequence_logo_tab import SequenceLogoTab

        self._find_or_open(SequenceLogoTab, "Sequence Logo (Logomaker)")

    # ── BLAST ────────────────────────────────────────────────────────────

    def open_ncbi_blast_web(self):
        import webbrowser

        webbrowser.open_new_tab("https://blast.ncbi.nlm.nih.gov/Blast.cgi")

    def _open_blast_local_tab(self, sub_index: int = 0):
        """Open (or focus) the Local BLAST tab and switch to sub_index."""
        from modules.blast_local_tab import BlastLocalTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), BlastLocalTab):
                self.tabs.setCurrentIndex(i)
                self.tabs.widget(i).switch_to(sub_index)
                return

        tab = BlastLocalTab(
            status_callback=self.status.showMessage,
        )
        self.tabs.addTab(tab, "Local BLAST")
        self.tabs.setCurrentWidget(tab)
        tab.switch_to(sub_index)

    def open_blast_local_tab(self):
        self._open_blast_local_tab(sub_index=0)

    def open_blast_make_db_dialog(self):
        self._open_blast_local_tab(sub_index=0)

    def open_blast_run_dialog(self):
        self._open_blast_local_tab(sub_index=1)

    # ── Primer Design ────────────────────────────────────────────────────

    def open_primer_design_tab(self):
        from modules.primer3_gui import PrimerDesignTab

        self._find_or_open(PrimerDesignTab, "qPCR Primer Design")

    def open_primer_analysis_tab(self):
        from modules.primer_analysis_tab import PrimerAnalysisTab

        self._find_or_open(PrimerAnalysisTab, "Primer Analysis")

    def open_cloning_primer_tab(self):
        from modules.cloning_primer_tab import CloningPrimerTab

        self._find_or_open(CloningPrimerTab, "Cloning Primer Design")

    # ── Phylogenetic Tree ────────────────────────────────────────────────

    def open_distance_tree_tab(self):
        from modules.distance_tree_tab import DistanceTreeTab

        self._find_or_open(DistanceTreeTab, "Distance Tree Construction")

    def open_iqtree_tab(self):
        from modules.iqtree_tab import IqTreeTab

        self._find_or_open(IqTreeTab, "ML Tree Construction (IQ-TREE)")

    def open_partition_concat_tab(self):
        from modules.partition_concat_tab import PartitionConcatTab

        self._find_or_open(
            PartitionConcatTab,
            "Sequence Concatenation",
            factory=lambda: PartitionConcatTab(status_callback=self.status.showMessage),
        )

    def open_one_step_multigenephy_tab(self):
        from modules.one_step_multigenephy_tab import OneStepMultiGenePhyTab

        self._find_or_open(
            OneStepMultiGenePhyTab,
            "One Step MultiGenePhy",
            reuse=False,
        )

    def open_toytree_visualization_tab(self):
        from modules.tree_visualization_toytree_tab import ToytreeVisualizationTab

        self._find_or_open(ToytreeVisualizationTab, "Tree Visualization (Toytree)")

    def open_alignment_trimming_tab(self):
        from modules.trimal_tab import AlignmentTrimmingTab

        self._find_or_open(AlignmentTrimmingTab, "Alignment Trimming (trimAl)")

    # ── Bookmarks ────────────────────────────────────────────────────────

    def open_favorites_manager_tab(self):
        from modules.favorites_manager import BookmarkManager

        self._find_or_open(BookmarkManager, "Bookmarks")

    # ── Misc ─────────────────────────────────────────────────────────────

    def open_url_in_browser(self, url):
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl(url))

    def _remove_child_window(self, window):
        if window in self.child_windows:
            self.child_windows.remove(window)

    def check_for_updates(self):
        if self._update_worker is not None:
            return
        if self._update_button is not None:
            self._update_button.setEnabled(False)
            self._update_button.setText("Checking...")
        self._update_thread = QThread(self)
        self._update_worker = UpdateCheckWorker()
        self._update_worker.moveToThread(self._update_thread)
        self._update_thread.started.connect(self._update_worker.run)
        self._update_worker.finished.connect(self._on_update_check_finished)
        self._update_worker.error.connect(self._on_update_check_failed)
        # The QThread event loop runs until quit() — end it when the worker
        # reports back, then _finish_update_check cleans up via thread.finished.
        self._update_worker.finished.connect(self._update_thread.quit)
        self._update_worker.error.connect(self._update_thread.quit)
        self._update_thread.finished.connect(self._finish_update_check)
        self._update_thread.start()

    def _update_result_parent(self):
        dialog = self._update_dialog
        if dialog is not None and dialog.isVisible():
            return dialog
        return self

    @skip_when_closing
    def _on_update_check_finished(self, latest_version):
        parent = self._update_result_parent()
        if not is_newer_version(APP_VERSION, latest_version):
            QMessageBox.information(
                parent,
                "Check for Updates",
                f"SeqSketch v{APP_VERSION} is up to date.",
            )
            return
        box = QMessageBox(parent)
        box.setWindowTitle("Update Available")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(
            f"A new version v{latest_version} is available "
            f"(current: v{APP_VERSION})."
        )
        open_button = box.addButton(
            "Open Download Page", QMessageBox.ButtonRole.AcceptRole
        )
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        if box.clickedButton() is open_button:
            self.open_url_in_browser(RELEASES_PAGE_URL)

    @skip_when_closing
    def _on_update_check_failed(self, message):
        QMessageBox.warning(
            self._update_result_parent(),
            "Check for Updates",
            "Could not check for updates:\n"
            f"{message}\n\n"
            f"You can check manually at:\n{RELEASES_PAGE_URL}",
        )

    def _finish_update_check(self):
        park_qthread(self._update_thread)
        self._update_thread = None
        self._update_worker = None
        button = self._update_button
        dialog = self._update_dialog
        if button is not None:
            button.setEnabled(True)
            button.setText("Check for Updates")
        # Keep the refs only while the About dialog is still open and may be
        # used for another check; the post-exec cleanup in show_about_dialog
        # is the backstop when the check outlives the dialog.
        if dialog is None or not dialog.isVisible():
            self._update_button = None
            self._update_dialog = None

    def show_about_dialog(self):
        about_text = """
<div style="text-align:center;">
<h2 style="color:#2c7fb8; font-size:26px; margin-bottom:6px;">SeqSketch</h2>
<p style="color:#888; font-size:14px; margin:0 0 16px 0;">Sequence Analysis &amp; Visualization Toolkit</p>

<p style="font-size:14px; color:#555; margin:0; line-height:1.8;">
<b>Version {version}</b><br>
yananzh &middot; GPL-3.0
</p>

<p style="font-size:13px; color:#999; margin:12px 0 0 0;">
Built with Python &middot; PyQt6 &middot; Biopython &middot; Matplotlib
</p>

<p style="margin:16px 0 0 0; font-size:14px;">
<a href="https://github.com/yananzh/SeqSketch" style="color:#2c7fb8; text-decoration:none;">github.com/yananzh/SeqSketch</a>
</p>
</div>
        """.format(version=APP_VERSION)
        from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout

        dlg = QDialog(self)
        dlg.setWindowTitle("About SeqSketch")
        dlg.setFixedSize(340, 280)
        dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(28, 24, 28, 24)
        label = QLabel(about_text)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        layout.addWidget(label)

        button_row = QHBoxLayout()
        self._update_button = QPushButton("Check for Updates")
        self._update_button.clicked.connect(self.check_for_updates)
        self._update_dialog = dlg
        button_row.addStretch()
        button_row.addWidget(self._update_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        dlg.exec()
        # Drop the refs unless a check is still running (its slots may still
        # need the dialog as a message-box parent); _finish_update_check
        # clears them otherwise.
        if self._update_worker is None:
            self._update_button = None
            self._update_dialog = None
