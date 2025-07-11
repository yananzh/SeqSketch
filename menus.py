from PyQt6.QtWidgets import QMenuBar, QMenu
from PyQt6.QtGui import QAction

def create_menus(window):
    menubar = window.menuBar()
    menubar.clear()
    # 1. FASTA工具
    fasta_menu = menubar.addMenu(window.tr("FASTA工具"))
    # 四个功能项
    seq_stat_action = QAction(window.tr("序列统计"), window)
    seq_stat_action.triggered.connect(window.open_sequence_statistics_tab)
    fasta_menu.addAction(seq_stat_action)
    simplify_ids_action = QAction(window.tr("ID 简化"), window)
    simplify_ids_action.triggered.connect(window.open_simplify_ids_tab)
    fasta_menu.addAction(simplify_ids_action)
    extract_by_id_action = QAction(window.tr("序列提取 (按ID)"), window)
    extract_by_id_action.triggered.connect(window.open_extract_by_id_tab)
    fasta_menu.addAction(extract_by_id_action)
    extract_by_regex_action = QAction(window.tr("序列提取 (正则表达式)"), window)
    extract_by_regex_action.triggered.connect(window.open_extract_by_regex_tab)
    fasta_menu.addAction(extract_by_regex_action)
    # 新增：从NCBI下载序列
    download_ncbi_action = QAction(window.tr("从NCBI下载序列"), window)
    download_ncbi_action.triggered.connect(window.open_download_from_ncbi_tab)
    fasta_menu.addAction(download_ncbi_action)
    # 新增：批量重命名ID
    batch_rename_action = QAction(window.tr("批量重命名ID"), window)
    batch_rename_action.triggered.connect(window.open_batch_rename_ids_tab)
    fasta_menu.addAction(batch_rename_action)
    # 2. DNA序列分析
    dna_menu = menubar.addMenu(window.tr("DNA序列分析"))
    rna_action = QAction(window.tr("转成RNA"), window)
    rna_action.triggered.connect(window.open_rna_tab)
    dna_menu.addAction(rna_action)
    complement_action = QAction(window.tr("互补序列"), window)
    complement_action.triggered.connect(window.open_complement_tab)
    dna_menu.addAction(complement_action)
    revcomp_action = QAction(window.tr("反向互补序列"), window)
    revcomp_action.triggered.connect(window.open_reverse_complement_tab)
    dna_menu.addAction(revcomp_action)
    translate_action = QAction(window.tr("翻译序列"), window)
    translate_action.triggered.connect(window.open_translate_tab)
    dna_menu.addAction(translate_action)
    orf_action = QAction(window.tr("ORF Finder"), window)
    orf_action.triggered.connect(window.open_orf_tab)
    dna_menu.addAction(orf_action)
    sanger_action = QAction(window.tr("桑格测序数据处理"), window)
    sanger_action.triggered.connect(window.open_sanger_tab)
    dna_menu.addAction(sanger_action)
    # 3. 蛋白质序列分析
    protein_menu = menubar.addMenu(window.tr("蛋白质序列分析"))
    # 4. 序列比对
    align_menu = menubar.addMenu(window.tr("序列比对"))
    # 5. BLAST分析
    blast_menu = menubar.addMenu(window.tr("BLAST分析"))
    # 6. 引物设计
    primer_menu = menubar.addMenu(window.tr("引物设计"))
    # 7. 进化分析
    evolution_menu = menubar.addMenu(window.tr("进化分析"))
    # 8. 收藏夹系统
    fav_menu = menubar.addMenu(window.tr("收藏夹"))
    # 主题切换
    theme_menu = menubar.addMenu(window.tr("主题"))
    light_action = QAction(window.tr("浅色主题"), window)
    dark_action = QAction(window.tr("深色主题"), window)
    light_action.triggered.connect(lambda: window.switch_theme(False))
    dark_action.triggered.connect(lambda: window.switch_theme(True))
    theme_menu.addAction(light_action)
    theme_menu.addAction(dark_action)
    # 语言切换
    lang_menu = menubar.addMenu(window.tr("语言"))
    zh_action = QAction("中文", window)
    en_action = QAction("English", window)
    zh_action.triggered.connect(lambda: window.switch_language('zh'))
    en_action.triggered.connect(lambda: window.switch_language('en'))
    lang_menu.addAction(zh_action)
    lang_menu.addAction(en_action) 