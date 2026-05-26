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
# 新增DNA序列分析相关Tab（按需导入）


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.tr("BioSeq Analyzer"))
        self.resize(1100, 700)
        self.setAcceptDrops(True)
        # 设置窗口logo
        icon_path = os.path.join(os.path.dirname(__file__), "window_logo.png")
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

    def open_msa_visualization_tab(self):
        from modules.msa_visualization_tab import MSAVisualizationTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), MSAVisualizationTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = MSAVisualizationTab()
        self.tabs.addTab(tab, self.tr("MSA Visualization"))
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
        """Open (or focus) the Sequence Concatenation & Partition tab."""
        from modules.partition_concat_tab import PartitionConcatTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), PartitionConcatTab):
                self.tabs.setCurrentIndex(i)
                return

        tab = PartitionConcatTab(status_callback=self.status.showMessage)
        self.tabs.addTab(tab, self.tr("Sequence Concatenation and Partition Models"))
        self.tabs.setCurrentWidget(tab)

    def open_tree_visualization_tab(self):
        """Open (or focus) the Tree Visualization tab."""
        from modules.tree_visualization_tab import TreeVisualizationTab

        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), TreeVisualizationTab):
                self.tabs.setCurrentIndex(i)
                return

        tab = TreeVisualizationTab(status_callback=self.status.showMessage)
        self.tabs.addTab(tab, self.tr("Tree Visualization"))
        self.tabs.setCurrentWidget(tab)

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
                "Current version: v1.0.0\n\nNo updates available.\n\nVisit the project page for the latest info:\nhttps://github.com/yananzh/BioSeq-Analyzer"
            ),
        )

    def show_about_dialog(self):
        """Show About dialog"""
        about_text = self.tr("""
<h2>BioSeq Analyzer</h2>
<p><b>Version:</b> v1.0.0</p>
<p><b>Developer:</b> yananzh</p>
<p><b>Description:</b> A powerful toolkit for sequence analysis: FASTA processing, DNA/RNA tools, protein analysis, alignment, BLAST, primer design, and more.</p>

<p><b>Main Features:</b></p>
<ul>
<li>FASTA Tools: statistics, ID simplification, extraction, NCBI download</li>
<li>DNA Analysis: RNA conversion, complement, translation, ORF finder</li>
<li>Protein Analysis: amino acid composition, physicochemical properties, structure prediction</li>
<li>Alignment: pairwise, multiple, sequence logo</li>
<li>BLAST: NCBI online BLAST, local BLAST</li>
<li>Primer Design: PCR primer assistant</li>
<li>Phylogenetics: build and visualize trees</li>
</ul>

<p><b>Tech Stack:</b> Python 3, PyQt6</p>
<p><b>License:</b> MIT License</p>
<p><b>Project Page:</b> <a href="https://github.com/yananzh/BioSeq-Analyzer">https://github.com/yananzh/BioSeq-Analyzer</a></p>

<p>Thanks for using BioSeq Analyzer!</p>
        """)

        QMessageBox.about(self, self.tr("About BioSeq Analyzer"), about_text)
