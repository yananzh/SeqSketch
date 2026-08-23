import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
)

from menus import create_menus
from utils.app_paths import resource_path


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
        shutdown = getattr(widget, "shutdown", None)
        if callable(shutdown):
            # Preferred path: the tab stops its own threads/processes.
            shutdown()
        else:
            # Legacy fallback for tabs that are not BaseTabWidget subclasses.
            for attr_name in ("worker_thread", "_thread", "_batch_worker"):
                obj = getattr(widget, attr_name, None)
                if obj is None:
                    continue
                try:
                    if hasattr(obj, "stop"):
                        obj.stop()
                except RuntimeError:
                    pass
                try:
                    if hasattr(obj, "isRunning") and obj.isRunning():
                        if hasattr(obj, "quit"):
                            obj.quit()
                        if hasattr(obj, "wait"):
                            obj.wait(3000)
                except RuntimeError:
                    pass
        self.tabs.removeTab(index)
        widget.deleteLater()

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
        QMessageBox.information(
            self,
            "Check for Updates",
            "Current version: v1.0.0\n\nNo updates available.\n\n"
                "Visit the project page for the latest info:\n"
                "https://github.com/yananzh/SeqSketch",
        )

    def show_about_dialog(self):
        about_text = """
<div style="text-align:center;">
<h2 style="color:#2c7fb8; font-size:26px; margin-bottom:6px;">SeqSketch</h2>
<p style="color:#888; font-size:14px; margin:0 0 16px 0;">Sequence Analysis &amp; Visualization Toolkit</p>

<p style="font-size:14px; color:#555; margin:0; line-height:1.8;">
<b>Version 1.0.0</b><br>
yananzh &middot; MIT License
</p>

<p style="font-size:13px; color:#999; margin:12px 0 0 0;">
Built with Python &middot; PyQt6 &middot; Biopython &middot; Matplotlib
</p>

<p style="margin:16px 0 0 0; font-size:14px;">
<a href="https://github.com/yananzh/SeqSketch" style="color:#2c7fb8; text-decoration:none;">github.com/yananzh/SeqSketch</a>
</p>
</div>
        """
        from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout

        dlg = QDialog(self)
        dlg.setWindowTitle("About SeqSketch")
        dlg.setFixedSize(340, 240)
        dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(28, 24, 28, 24)
        label = QLabel(about_text)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        layout.addWidget(label)
        dlg.exec()
