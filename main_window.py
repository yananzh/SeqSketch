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
        self.setWindowTitle(self.tr("SeqSketch"))
        self.resize(920, 700)
        self.setAcceptDrops(True)
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
        qss_path = os.path.join(os.path.dirname(__file__), "styles.qss")
        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                qss = f.read()
            self.setStyleSheet(qss)
        except Exception as e:
            print("QSS load failed:", e)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        pass

    def show_message(self, text, error=False):
        if error:
            QMessageBox.critical(self, self.tr("Error"), text)
        else:
            self.status.showMessage(text, 5000)

    def _find_or_open(self, tab_class, title, factory=None, reuse=True):
        """Reuse an existing tab of *tab_class*, or create a new one.

        Args:
            tab_class: tab class used for the isinstance reuse check.
            title: tab title text (wrapped in self.tr()).
            factory: callable returning a new tab; defaults to tab_class().
            reuse: when True, focus an existing tab instead of creating a new one.
        """
        if reuse:
            for i in range(self.tabs.count()):
                if isinstance(self.tabs.widget(i), tab_class):
                    self.tabs.setCurrentIndex(i)
                    return None
        tab = (factory or tab_class)()
        self.tabs.addTab(tab, self.tr(title))
        self.tabs.setCurrentWidget(tab)
        return tab

    def close_tab(self, index):
        widget = self.tabs.widget(index)
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
        self.tabs.addTab(tab, self.tr("Complement/Reverse Complement"))
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
        from modules.blast_result_tab import BlastResultTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), BlastLocalTab):
                self.tabs.setCurrentIndex(i)
                self.tabs.widget(i).switch_to(sub_index)
                return

        def on_result(tsv_path):
            result_tab = BlastResultTab(tsv_path)
            self.tabs.addTab(result_tab, self.tr("BLAST Result"))
            self.tabs.setCurrentWidget(result_tab)

        tab = BlastLocalTab(
            status_callback=self.status.showMessage,
            result_callback=on_result,
        )
        self.tabs.addTab(tab, self.tr("Local BLAST"))
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

    # ── Phylogenetic Tree ────────────────────────────────────────────────

    def open_distance_tree_tab(self):
        from modules.distance_tree_tab import DistanceTreeTab

        self._find_or_open(DistanceTreeTab, "Distance Tree Construction")

    def open_iqtree_tab(self):
        from modules.iqtree_tab import IqTreeTab

        self._find_or_open(
            IqTreeTab,
            "ML Tree Construction (IQ-TREE)",
            factory=lambda: IqTreeTab(status_callback=self.status.showMessage),
        )

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
            factory=lambda: OneStepMultiGenePhyTab(status_callback=None),
            reuse=False,
        )

    def open_tree_visualization_tab(self):
        from modules.tree_visualization_tab import SimpleTreeVisualizationTab

        self._find_or_open(SimpleTreeVisualizationTab, "Tree Visualization")

    def open_alignment_trimming_tab(self):
        from modules.trimal_tab import AlignmentTrimmingTab

        self._find_or_open(AlignmentTrimmingTab, "Alignment Trimming (trimAl)")

    # ── Favorites ────────────────────────────────────────────────────────

    def open_favorites_manager_tab(self):
        from modules.favorites_manager import BookmarkManager

        self._find_or_open(BookmarkManager, "Favorites")

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
            self.tr("Check for Updates"),
            self.tr(
                "Current version: v1.0.0\n\nNo updates available.\n\n"
                "Visit the project page for the latest info:\n"
                "https://github.com/yananzh/SeqSketch"
            ),
        )

    def show_about_dialog(self):
        about_text = self.tr("""
<div style="text-align:center; margin-bottom:10px;">
<h1 style="color:#2c7fb8; font-size:20px; margin:0; text-align:center;">SeqSketch</h1>
<p style="color:#666; font-size:12px; margin:2px 0; text-align:center;">Sequence Analysis &amp; Visualization Toolkit</p>
</div>

<hr style="border:none; border-top:1px solid #ddd;">

<p style="text-align:center; font-size:12px; margin:8px 0;">
<b>v1.0.0</b> &middot; yananzh &middot; MIT License<br>
Python 3 &middot; PyQt6 &middot; Biopython &middot; Matplotlib
</p>

<hr style="border:none; border-top:1px solid #ddd;">

<p style="text-align:center; font-size:12px; color:#444; margin:8px 0;"><b>40+ modules</b> across 8 functional menus</p>

<table style="margin:0 auto; font-size:11px; border-spacing:3px;">
<tr><td style="text-align:right; color:#2c7fb8; white-space:nowrap; padding-right:6px;"><b>FASTA Tools</b></td><td>QC, Filter, Extract, Rename, Deduplicate, Concatenate, NCBI Download</td></tr>
<tr><td style="text-align:right; color:#2c7fb8; white-space:nowrap; padding-right:6px;"><b>DNA Analysis</b></td><td>RNA Conversion, Complement, Translate, ORF Finder, Codon Usage, Sanger, Restriction Enzyme</td></tr>
<tr><td style="text-align:right; color:#2c7fb8; white-space:nowrap; padding-right:6px;"><b>Protein Analysis</b></td><td>Composition, Physicochemical, Hydrophobicity, Protease Cleavage, Annotation, Structure, Function</td></tr>
<tr><td style="text-align:right; color:#2c7fb8; white-space:nowrap; padding-right:6px;"><b>Alignment</b></td><td>Pairwise, DotPlot, MUSCLE, MAFFT, MSA Viewer, Sequence Logo</td></tr>
<tr><td style="text-align:right; color:#2c7fb8; white-space:nowrap; padding-right:6px;"><b>BLAST</b></td><td>NCBI Online BLAST, Local BLAST</td></tr>
<tr><td style="text-align:right; color:#2c7fb8; white-space:nowrap; padding-right:6px;"><b>Primer Design</b></td><td>qPCR Primer Design (Primer3), Primer Analysis</td></tr>
<tr><td style="text-align:right; color:#2c7fb8; white-space:nowrap; padding-right:6px;"><b>Phylogenetic Tree</b></td><td>trimAl, Concatenation, Distance Tree Construction, ML IQ-TREE, One Step MultiGenePhy, Phytreeviz</td></tr>
<tr><td style="text-align:right; color:#2c7fb8; white-space:nowrap; padding-right:6px;"><b>Favorites</b></td><td>Bookmark &amp; manage frequently used sequences</td></tr>
</table>

<hr style="border:none; border-top:1px solid #ddd;">

<p style="text-align:center; font-size:11px; color:#999; margin:6px 0;">
🔗 <a href="https://github.com/yananzh/SeqSketch" style="color:#2c7fb8;">github.com/yananzh/SeqSketch</a>
</p>
        """)
        QMessageBox.about(self, self.tr("About SeqSketch"), about_text)
