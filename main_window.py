from PyQt6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QStatusBar,
    QFileDialog,
    QMessageBox,
    QApplication,
)
from PyQt6.QtCore import Qt
from menus import create_menus
from PyQt6.QtGui import QIcon, QPixmap
import os

from utils.app_paths import resource_path

# 新增DNA序列分析相关Tab（按需导入）


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.tr("SeqSketch"))
        self.resize(1100, 700)
        self.setAcceptDrops(True)
        # 设置窗口logo
        icon_path = resource_path("window_logo.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        # Keep references to child windows to prevent garbage collection
        self.child_windows = []
        self._init_ui()
        self._load_style()

    def _init_ui(self):
        # Tab区域
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.setCentralWidget(self.tabs)
        # 状态栏
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        # 菜单栏和工具栏
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

    def open_sequence_statistics_tab(self):
        from modules.sequence_statistics_tab import SequenceStatisticsTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), SequenceStatisticsTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = SequenceStatisticsTab()
        self.tabs.addTab(tab, self.tr("FASTA QC"))
        self.tabs.setCurrentWidget(tab)

    def open_simplify_ids_tab(self):
        from modules.simplify_ids_tab import SimplifyIDsTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), SimplifyIDsTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = SimplifyIDsTab()
        self.tabs.addTab(tab, self.tr("Simplify Headers"))
        self.tabs.setCurrentWidget(tab)

    def open_extract_by_id_tab(self):
        from modules.extract_by_id_tab import ExtractByIDTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), ExtractByIDTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = ExtractByIDTab()
        self.tabs.addTab(tab, self.tr("Filter by IDs"))
        self.tabs.setCurrentWidget(tab)

    def open_extract_by_regex_tab(self):
        from modules.extract_by_regex_tab import ExtractByRegexTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), ExtractByRegexTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = ExtractByRegexTab()
        self.tabs.addTab(tab, self.tr("Regex Filter"))
        self.tabs.setCurrentWidget(tab)

    def open_download_from_ncbi_tab(self):
        from modules.download_from_ncbi_tab import DownloadFromNCBITab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), DownloadFromNCBITab):
                self.tabs.setCurrentIndex(i)
                return
        tab = DownloadFromNCBITab()
        self.tabs.addTab(tab, self.tr("NCBI Download"))
        self.tabs.setCurrentWidget(tab)

    def open_batch_rename_ids_tab(self):
        from modules.batch_rename_ids_tab import BatchRenameIDsTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), BatchRenameIDsTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = BatchRenameIDsTab()
        self.tabs.addTab(tab, self.tr("Rename IDs"))
        self.tabs.setCurrentWidget(tab)

    # ── 新增 FASTA Tools ──

    def open_deduplicate_tab(self):
        from modules.deduplicate_tab import DeduplicateTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), DeduplicateTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = DeduplicateTab()
        self.tabs.addTab(tab, self.tr("Deduplicate"))
        self.tabs.setCurrentWidget(tab)

    def open_filter_by_length_tab(self):
        from modules.filter_by_length_tab import FilterByLengthTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), FilterByLengthTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = FilterByLengthTab()
        self.tabs.addTab(tab, self.tr("Filter by Length"))
        self.tabs.setCurrentWidget(tab)

    def open_concat_fasta_tab(self):
        from modules.concat_fasta_tab import ConcatFastaTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), ConcatFastaTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = ConcatFastaTab()
        self.tabs.addTab(tab, self.tr("Concatenate FASTA"))
        self.tabs.setCurrentWidget(tab)

    # DNA序列分析六大功能Tab
    def open_rna_tab(self):
        from modules.rna_tab import RNATab

        tab = RNATab()
        self.tabs.addTab(tab, "Convert to RNA")
        self.tabs.setCurrentWidget(tab)

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

        tab = TranslateTab()
        self.tabs.addTab(tab, "Translate")
        self.tabs.setCurrentWidget(tab)

    def open_orf_tab(self):
        from modules.orf_tab import ORFTab

        tab = ORFTab()
        self.tabs.addTab(tab, "ORF Finder")
        self.tabs.setCurrentWidget(tab)

    def open_sanger_tab(self):
        from modules.sanger_tab import SangerTab

        tab = SangerTab()
        self.tabs.addTab(tab, "Sanger Sequence Assembly")
        self.tabs.setCurrentWidget(tab)

    def open_sanger_viewer_tab(self):
        from modules.sanger_viewer_tab import SangerViewerTab

        tab = SangerViewerTab()
        self.tabs.addTab(tab, self.tr("Sanger Seq Viewer"))
        self.tabs.setCurrentWidget(tab)

    def open_codon_usage_tab(self):
        from modules.codon_usage_tab import CodonUsageTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), CodonUsageTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = CodonUsageTab(status_callback=self.status.showMessage)
        self.tabs.addTab(tab, self.tr("Codon Usage Analysis"))
        self.tabs.setCurrentWidget(tab)

    def open_restriction_enzyme_tab(self):
        from modules.restriction_enzyme_tab import RestrictionEnzymeTab

        tab = RestrictionEnzymeTab()
        self.tabs.addTab(tab, self.tr("Restriction Enzyme Analysis"))
        self.tabs.setCurrentWidget(tab)

    def close_tab(self, index):
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        widget.deleteLater()

    # 蛋白质序列分析相关槽函数
    def open_amino_acid_composition_tab(self):
        from modules.amino_acid_composition_tab import AminoAcidCompositionTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), AminoAcidCompositionTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = AminoAcidCompositionTab()
        self.tabs.addTab(tab, self.tr("Amino Acid Composition"))
        self.tabs.setCurrentWidget(tab)

    def open_physicochemical_properties_tab(self):
        from modules.physicochemical_properties_tab import PhysicochemicalPropertiesTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), PhysicochemicalPropertiesTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = PhysicochemicalPropertiesTab()
        self.tabs.addTab(tab, self.tr("Physicochemical Properties"))
        self.tabs.setCurrentWidget(tab)

    def open_hydrophobicity_plot_tab(self):
        from modules.hydrophobicity_plot_tab import HydrophobicityPlotTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), HydrophobicityPlotTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = HydrophobicityPlotTab()
        self.tabs.addTab(tab, self.tr("Hydrophobicity Plot"))
        self.tabs.setCurrentWidget(tab)

    def open_protease_cleavage_tab(self):
        from modules.protease_cleavage_tab import ProteaseCleavageTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), ProteaseCleavageTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = ProteaseCleavageTab()
        self.tabs.addTab(tab, self.tr("Protease Cleavage Map"))
        self.tabs.setCurrentWidget(tab)

    def open_url_in_browser(self, url):
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl

        QDesktopServices.openUrl(QUrl(url))

    # Alignment相关槽函数
    def open_pairwise_alignment_tab(self):
        from modules.pairwise_alignment_tab import PairwiseAlignmentTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), PairwiseAlignmentTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = PairwiseAlignmentTab()
        self.tabs.addTab(tab, self.tr("Pairwise Sequence Alignment"))
        self.tabs.setCurrentWidget(tab)

    def open_primer_design_tab(self):
        from modules.primer3_gui import PrimerDesignTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), PrimerDesignTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = PrimerDesignTab()
        self.tabs.addTab(tab, self.tr("qPCR Primer Design"))
        self.tabs.setCurrentWidget(tab)

    def open_primer_analysis_tab(self):
        from modules.primer_analysis_tab import PrimerAnalysisTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), PrimerAnalysisTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = PrimerAnalysisTab()
        self.tabs.addTab(tab, self.tr("Primer Analysis"))
        self.tabs.setCurrentWidget(tab)

    def open_favorites_manager_tab(self):
        from modules.favorites_manager import BookmarkManager

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), BookmarkManager):
                self.tabs.setCurrentIndex(i)
                return
        tab = BookmarkManager()
        self.tabs.addTab(tab, self.tr("Favorites"))
        self.tabs.setCurrentWidget(tab)

    def open_dotplot_tab(self):
        from modules.dotplot_tab import DotPlotTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), DotPlotTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = DotPlotTab()
        self.tabs.addTab(tab, self.tr("DotPlot"))
        self.tabs.setCurrentWidget(tab)

    def open_multiple_sequence_alignment_tab(self):
        from modules.multiple_sequence_alignment_tab import MultipleSequenceAlignmentTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), MultipleSequenceAlignmentTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = MultipleSequenceAlignmentTab()
        self.tabs.addTab(tab, self.tr("Multiple Sequence Alignment (Muscle5)"))
        self.tabs.setCurrentWidget(tab)

    def open_mafft_alignment_tab(self):
        from modules.mafft_alignment_tab import MafftAlignmentTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), MafftAlignmentTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = MafftAlignmentTab()
        self.tabs.addTab(tab, self.tr("Multiple Sequence Alignment (MAFFT)"))
        self.tabs.setCurrentWidget(tab)

    def open_alignment_format_converter_tab(self):
        from modules.alignment_format_converter_tab import AlignmentFormatConverterTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), AlignmentFormatConverterTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = AlignmentFormatConverterTab()
        self.tabs.addTab(tab, self.tr("Alignment Format Converter"))
        self.tabs.setCurrentWidget(tab)

    def open_msa_visualization_tab(self):
        from modules.msa_visualization_tab import MSAVisualizationTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), MSAVisualizationTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = MSAVisualizationTab()
        self.tabs.addTab(tab, self.tr("MSA Visualization (pyMSAviz)"))
        self.tabs.setCurrentWidget(tab)

    def open_sequence_logo_tab(self):
        from modules.sequence_logo_tab import SequenceLogoTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), SequenceLogoTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = SequenceLogoTab()
        self.tabs.addTab(tab, self.tr("Sequence Logo (Logomaker)"))
        self.tabs.setCurrentWidget(tab)

    # BLAST分析相关槽函数
    def open_ncbi_blast_web(self):
        import webbrowser

        webbrowser.open_new_tab("https://blast.ncbi.nlm.nih.gov/Blast.cgi")

    def _open_blast_local_tab(self, sub_index: int = 0):
        """Open (or focus) the Local BLAST tab and switch to sub_index."""
        from modules.blast_local_tab import BlastLocalTab
        from modules.blast_result_tab import BlastResultTab

        # Reuse existing tab if already open
        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), BlastLocalTab):
                self.tabs.setCurrentIndex(i)
                self.tabs.widget(i).switch_to(sub_index)
                return

        def on_result(tsv_path):
            result_tab = BlastResultTab(tsv_path)
            self.tabs.addTab(result_tab, "BLAST Result")
            self.tabs.setCurrentWidget(result_tab)

        tab = BlastLocalTab(
            status_callback=self.status.showMessage,
            result_callback=on_result,
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

    def open_iqtree_tab(self):
        """Open (or focus) the IQ-TREE Tree Construction tab."""
        from modules.iqtree_tab import IqTreeTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), IqTreeTab):
                self.tabs.setCurrentIndex(i)
                return

        tab = IqTreeTab(status_callback=self.status.showMessage)
        self.tabs.addTab(tab, self.tr("Tree Construction (IQ-TREE)"))
        self.tabs.setCurrentWidget(tab)

    def open_partition_concat_tab(self):
        """Open (or focus) the Sequence Concatenation tab."""
        from modules.partition_concat_tab import PartitionConcatTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), PartitionConcatTab):
                self.tabs.setCurrentIndex(i)
                return

        tab = PartitionConcatTab(status_callback=self.status.showMessage)
        self.tabs.addTab(tab, self.tr("Sequence Concatenation"))
        self.tabs.setCurrentWidget(tab)

    def open_one_step_multigenephy_tab(self):
        """Open a new One Step MultiGenePhy tab (multi-instance)."""
        from modules.one_step_multigenephy_tab import OneStepMultiGenePhyTab

        tab = OneStepMultiGenePhyTab(status_callback=None)
        self.tabs.addTab(tab, self.tr("One Step MultiGenePhy"))
        self.tabs.setCurrentWidget(tab)

    def _remove_child_window(self, window):
        if window in self.child_windows:
            self.child_windows.remove(window)

    def open_tree_visualization_tab(self):
        """Open (or focus) the Simple Tree Visualization (Phytreeviz) window."""
        from modules.tree_visualization_tab import SimpleTreeVisualizationWindow

        # Check for existing instance and raise it
        for win in self.child_windows:
            if isinstance(win, SimpleTreeVisualizationWindow):
                win.raise_()
                win.activateWindow()
                return

        window = SimpleTreeVisualizationWindow()
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window.destroyed.connect(lambda: self._remove_child_window(window))
        self.child_windows.append(window)
        window.show()

    def open_alignment_trimming_tab(self):
        """Open (or focus) the Alignment Trimming (trimAl) tab."""
        from modules.trimal_tab import AlignmentTrimmingTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), AlignmentTrimmingTab):
                self.tabs.setCurrentIndex(i)
                return

        tab = AlignmentTrimmingTab(status_callback=self.status.showMessage)
        self.tabs.addTab(tab, self.tr("Alignment Trimming (trimAl)"))
        self.tabs.setCurrentWidget(tab)

    def check_for_updates(self):
        """Check for updates"""
        QMessageBox.information(
            self,
            self.tr("Check for Updates"),
            self.tr(
                "Current version: v1.0.0\n\nNo updates available.\n\nVisit the project page for the latest info:\nhttps://github.com/yananzh/SeqSketch"
            ),
        )

    def show_about_dialog(self):
        """Show About dialog"""
        about_text = self.tr("""
<div style="text-align:center; margin-bottom:12px;">
<h1 style="color:#2c7fb8; font-size:22px; margin:0;">🧬 SeqSketch</h1>
<p style="color:#666; font-size:13px; margin:4px 0;">Sequence Analysis &amp; Visualization Toolkit</p>
</div>

<hr style="border:none; border-top:1px solid #ddd;">

<table style="width:100%; font-size:13px; border-spacing:6px;">
<tr><td style="color:#888; white-space:nowrap;">📌 Version</td><td><b>v1.0.0</b></td></tr>
<tr><td style="color:#888; white-space:nowrap;">👤 Developer</td><td><b>yananzh</b></td></tr>
<tr><td style="color:#888; white-space:nowrap;">📄 License</td><td>MIT License</td></tr>
<tr><td style="color:#888; white-space:nowrap;">🐍 Tech Stack</td><td>Python 3 &middot; PyQt6 &middot; Biopython &middot; Matplotlib</td></tr>
</table>

<hr style="border:none; border-top:1px solid #ddd;">

<p style="font-size:13px; color:#444;">SeqSketch is a cross-platform bioinformatics desktop application that integrates <b>40+ analysis modules</b> covering the full spectrum of sequence work:</p>

<table style="width:100%; font-size:12px; border-spacing:4px;">
<tr><td>🔬 <b>FASTA Toolkit</b></td><td>Statistics, dedup, filter, extract, rename, concat, format convert</td></tr>
<tr><td>🧬 <b>DNA / RNA</b></td><td>Complement, reverse-complement, transcription, ORF finder, codon usage</td></tr>
<tr><td>🧪 <b>Protein</b></td><td>Amino acid composition, physicochemical properties, protease cleavage, hydrophobicity</td></tr>
<tr><td>📐 <b>Alignment</b></td><td>Pairwise alignment, MAFFT, MUSCLE, MSA viewer</td></tr>
<tr><td>🔍 <b>BLAST</b></td><td>NCBI online BLAST, local BLAST with custom databases</td></tr>
<tr><td>🧬 <b>Primer Design</b></td><td>Primer3 integration, restriction enzyme analysis</td></tr>
<tr><td>🌳 <b>Phylogenetics</b></td><td>IQ‑TREE, tree visualization (PhyloTreeViz), partition concatenation</td></tr>
<tr><td>📊 <b>Visualization</b></td><td>Sequence logos, dot plots, Sanger electropherograms</td></tr>
<tr><td>🌐 <b>Data Access</b></td><td>NCBI GenBank download, batch retrieval</td></tr>
</table>

<hr style="border:none; border-top:1px solid #ddd;">

<p style="text-align:center; font-size:12px; color:#999; margin:8px 0;">
🔗 <a href="https://github.com/yananzh/SeqSketch" style="color:#2c7fb8;">github.com/yananzh/SeqSketch</a>
</p>

<p style="text-align:center; font-size:12px; color:#aaa; margin:2px 0;">
Made with ❤️ using Python &amp; PyQt6 — for the bioinformatics community
</p>
        """)

        QMessageBox.about(self, self.tr("About SeqSketch"), about_text)
