from PyQt6.QtWidgets import QMainWindow, QTabWidget, QStatusBar, QFileDialog, QMessageBox, QApplication
from PyQt6.QtCore import Qt, QTranslator, QLocale
from menus import create_menus
from modules import SequenceStatisticsTab, SimplifyIDsTab, ExtractByIDTab, ExtractByRegexTab, DownloadFromNCBITab, BatchRenameIDsTab
from PyQt6.QtGui import QIcon, QPixmap
import os
# 新增DNA序列分析相关Tab
from modules import RNATab, ComplementTab, ReverseComplementTab, TranslateTab, ORFTab, SangerTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.tr("BioSeq Analyzer 生物序列分析器"))
        self.resize(1100, 700)
        self.setAcceptDrops(True)
        # 设置窗口logo
        icon_path = os.path.join(os.path.dirname(__file__), "Gemini_Generated_Image_ohhms3ohhms3ohhm1.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self._init_ui()
        self._load_style()
        self.translator = None

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
        qss_path = os.path.join(os.path.dirname(__file__), 'styles.qss')
        try:
            with open(qss_path, 'r', encoding='utf-8') as f:
                qss = f.read()
            self.setStyleSheet(qss)
        except Exception as e:
            print("QSS加载失败:", e)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        pass

    def switch_language(self, lang):
        if self.translator:
            QApplication.instance().removeTranslator(self.translator)
        self.translator = QTranslator()
        if lang == 'zh':
            qm_path = os.path.join(os.path.dirname(__file__), '../resources/translations/zh_CN.qm')
        else:
            qm_path = os.path.join(os.path.dirname(__file__), '../resources/translations/en_US.qm')
        if self.translator.load(qm_path):
            QApplication.instance().installTranslator(self.translator)
            self._init_ui()

    def switch_theme(self, dark):
        self._load_style(dark=dark)

    def show_message(self, text, error=False):
        if error:
            QMessageBox.critical(self, self.tr("错误"), text)
        else:
            self.status.showMessage(text, 5000)

    def open_sequence_statistics_tab(self):
        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), SequenceStatisticsTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = SequenceStatisticsTab()
        self.tabs.addTab(tab, self.tr("序列统计"))
        self.tabs.setCurrentWidget(tab)

    def open_simplify_ids_tab(self):
        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), SimplifyIDsTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = SimplifyIDsTab()
        self.tabs.addTab(tab, self.tr("ID 简化"))
        self.tabs.setCurrentWidget(tab)

    def open_extract_by_id_tab(self):
        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), ExtractByIDTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = ExtractByIDTab()
        self.tabs.addTab(tab, self.tr("序列提取 (按ID)"))
        self.tabs.setCurrentWidget(tab)

    def open_extract_by_regex_tab(self):
        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), ExtractByRegexTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = ExtractByRegexTab()
        self.tabs.addTab(tab, self.tr("序列提取 (正则表达式)"))
        self.tabs.setCurrentWidget(tab)

    def open_download_from_ncbi_tab(self):
        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), DownloadFromNCBITab):
                self.tabs.setCurrentIndex(i)
                return
        tab = DownloadFromNCBITab()
        self.tabs.addTab(tab, self.tr("从NCBI下载序列"))
        self.tabs.setCurrentWidget(tab)

    def open_batch_rename_ids_tab(self):
        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), BatchRenameIDsTab):
                self.tabs.setCurrentIndex(i)
                return
        tab = BatchRenameIDsTab()
        self.tabs.addTab(tab, self.tr("批量重命名ID"))
        self.tabs.setCurrentWidget(tab)

    # DNA序列分析六大功能Tab
    def open_rna_tab(self):
        tab = RNATab()
        self.tabs.addTab(tab, "转成RNA")
        self.tabs.setCurrentWidget(tab)

    def open_complement_tab(self):
        tab = ComplementTab()
        self.tabs.addTab(tab, "互补序列")
        self.tabs.setCurrentWidget(tab)

    def open_reverse_complement_tab(self):
        tab = ReverseComplementTab()
        self.tabs.addTab(tab, "反向互补序列")
        self.tabs.setCurrentWidget(tab)

    def open_translate_tab(self):
        tab = TranslateTab()
        self.tabs.addTab(tab, "翻译序列")
        self.tabs.setCurrentWidget(tab)

    def open_orf_tab(self):
        tab = ORFTab()
        self.tabs.addTab(tab, "ORF Finder")
        self.tabs.setCurrentWidget(tab)

    def open_sanger_tab(self):
        tab = SangerTab()
        self.tabs.addTab(tab, "桑格测序数据处理")
        self.tabs.setCurrentWidget(tab)

    def close_tab(self, index):
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        widget.deleteLater() 