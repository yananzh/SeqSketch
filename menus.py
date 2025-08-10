from PyQt6.QtWidgets import QMenuBar, QMenu
from PyQt6.QtGui import QAction
from modules.favorites_manager import BookmarkManager
import os
import sys
import importlib.util

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
    # 1. 氨基酸组成
    aa_comp_action = QAction(window.tr("氨基酸组成"), window)
    aa_comp_action.triggered.connect(window.open_amino_acid_composition_tab)
    protein_menu.addAction(aa_comp_action)
    # 2. 物化性质计算
    physchem_action = QAction(window.tr("物化性质计算"), window)
    physchem_action.triggered.connect(window.open_physicochemical_properties_tab)
    protein_menu.addAction(physchem_action)
    protein_menu.addSeparator()
    # 3. 二级结构预测（子菜单）
    sec_struct_menu = QMenu(window.tr("二级结构预测"), window)
    psipred_action = QAction("PSIPRED", window)
    psipred_action.triggered.connect(lambda: window.open_url_in_browser("http://bioinf.cs.ucl.ac.uk/psipred/"))
    sec_struct_menu.addAction(psipred_action)
    jpred_action = QAction("Jpred4", window)
    jpred_action.triggered.connect(lambda: window.open_url_in_browser("https://www.compbio.dundee.ac.uk/jpred/"))
    sec_struct_menu.addAction(jpred_action)
    protein_menu.addMenu(sec_struct_menu)
    # 4. 三级结构预测（子菜单）
    tert_struct_menu = QMenu(window.tr("三级结构预测"), window)
    swiss_model_action = QAction("SWISS-MODEL", window)
    swiss_model_action.triggered.connect(lambda: window.open_url_in_browser("https://swissmodel.expasy.org/"))
    tert_struct_menu.addAction(swiss_model_action)
    alphafold_action = QAction("AlphaFold Server", window)
    alphafold_action.triggered.connect(lambda: window.open_url_in_browser("https://alphafoldserver.com/"))
    tert_struct_menu.addAction(alphafold_action)
    protein_menu.addMenu(tert_struct_menu)
    # 5. 结构域预测（子菜单）
    domain_menu = QMenu(window.tr("结构域预测"), window)
    interpro_action = QAction("InterPro", window)
    interpro_action.triggered.connect(lambda: window.open_url_in_browser("https://www.ebi.ac.uk/interpro/"))
    domain_menu.addAction(interpro_action)
    protein_menu.addMenu(domain_menu)
    # 6. 信号肽预测（子菜单）
    signal_menu = QMenu(window.tr("信号肽预测"), window)
    signalp_action = QAction("SignalP 6.0", window)
    signalp_action.triggered.connect(lambda: window.open_url_in_browser("https://services.healthtech.dtu.dk/services/SignalP-6.0/"))
    signal_menu.addAction(signalp_action)
    protein_menu.addMenu(signal_menu)
    # 7. 跨膜螺旋预测（子菜单）
    tmhmm_menu = QMenu(window.tr("跨膜螺旋预测"), window)
    deeptmhmm_action = QAction("DeepTMHMM 1.0", window)
    deeptmhmm_action.triggered.connect(lambda: window.open_url_in_browser("https://services.healthtech.dtu.dk/services/DeepTMHMM-1.0/"))
    tmhmm_menu.addAction(deeptmhmm_action)
    protein_menu.addMenu(tmhmm_menu)
    # 8. 同源蛋白搜索（子菜单）
    homolog_menu = QMenu(window.tr("同源蛋白搜索"), window)
    hmmer_action = QAction("HMMER", window)
    hmmer_action.triggered.connect(lambda: window.open_url_in_browser("https://www.ebi.ac.uk/Tools/hmmer/search/phmmer"))
    homolog_menu.addAction(hmmer_action)
    protein_menu.addMenu(homolog_menu)
    # 9. 结构相似蛋白搜索（子菜单）
    structure_similarity_menu = QMenu(window.tr("结构相似蛋白搜索"), window)
    foldseek_action = QAction("Foldseek Search", window)
    foldseek_action.triggered.connect(lambda: window.open_url_in_browser("https://search.foldseek.com/search"))
    structure_similarity_menu.addAction(foldseek_action)
    protein_menu.addMenu(structure_similarity_menu)
    # 4. 序列比对
    align_menu = menubar.addMenu(window.tr("序列比对"))
    # 1. 双序列比对 (在线工具) (子菜单)
    pairwise_align_menu = QMenu(window.tr("双序列比对 (在线工具)"), window)
    water_action = QAction("局部比对 (EBI EMBOSS Water)", window)
    water_action.triggered.connect(lambda: window.open_url_in_browser("https://www.ebi.ac.uk/jdispatcher/emboss/water"))
    pairwise_align_menu.addAction(water_action)
    needle_action = QAction("全局比对 (EBI EMBOSS Needle)", window)
    needle_action.triggered.connect(lambda: window.open_url_in_browser("https://www.ebi.ac.uk/jdispatcher/emboss/needle"))
    pairwise_align_menu.addAction(needle_action)
    align_menu.addMenu(pairwise_align_menu)
    # 2. 多序列比对 (在线工具) (子菜单)
    multiple_align_menu = QMenu(window.tr("多序列比对 (在线工具)"), window)
    clustalo_action = QAction("EBI Clustal Omega", window)
    clustalo_action.triggered.connect(lambda: window.open_url_in_browser("https://www.ebi.ac.uk/jdispatcher/msa/clustalo"))
    multiple_align_menu.addAction(clustalo_action)
    muscle_action = QAction("EBI MUSCLE", window)
    muscle_action.triggered.connect(lambda: window.open_url_in_browser("https://www.ebi.ac.uk/jdispatcher/msa/muscle"))
    multiple_align_menu.addAction(muscle_action)
    mafft_action = QAction("MAFFT Server", window)
    mafft_action.triggered.connect(lambda: window.open_url_in_browser("https://mafft.cbrc.jp/alignment/server/"))
    multiple_align_menu.addAction(mafft_action)
    # 新增 T-Coffee 选项
    tcoffee_action = QAction("T-Coffee", window)
    tcoffee_action.triggered.connect(lambda: window.open_url_in_browser("https://tcoffee.crg.eu/apps/tcoffee/index.html"))
    multiple_align_menu.addAction(tcoffee_action)
    align_menu.addMenu(multiple_align_menu)
    # 3. 序列标识图 (在线工具) (子菜单)
    seq_logo_menu = QMenu(window.tr("序列标识图 (在线工具)"), window)
    weblogo_action = QAction("WebLogo", window)
    weblogo_action.triggered.connect(lambda: window.open_url_in_browser("http://weblogo.berkeley.edu/"))
    seq_logo_menu.addAction(weblogo_action)
    align_menu.addMenu(seq_logo_menu)
    # 5. BLAST分析
    blast_menu = menubar.addMenu(window.tr("BLAST分析"))
    # NCBI在线BLAST
    ncbi_blast_action = QAction(window.tr("NCBI在线BLAST"), window)
    ncbi_blast_action.triggered.connect(window.open_ncbi_blast_web)
    blast_menu.addAction(ncbi_blast_action)
    # 本地BLAST子菜单
    local_blast_menu = QMenu(window.tr("本地BLAST"), window)
    make_db_action = QAction(window.tr("1. 构建BLAST数据库..."), window)
    make_db_action.triggered.connect(window.open_blast_make_db_dialog)
    local_blast_menu.addAction(make_db_action)
    run_blast_action = QAction(window.tr("2. 运行BLAST查询..."), window)
    run_blast_action.triggered.connect(window.open_blast_run_dialog)
    local_blast_menu.addAction(run_blast_action)
    blast_menu.addMenu(local_blast_menu)
    # 6. 引物设计
    primer_menu = menubar.addMenu(window.tr("引物设计"))
    open_primer_action = QAction(window.tr("PCR 引物设计助手"), window)
    def _open_primer_designer():
        # 弹出 primer3_gui.py 中的 MainWindow 作为独立窗口
        try:
            import importlib.util
            import sys, os
            primer3_gui_path = os.path.join(os.path.dirname(__file__), "primer3_gui.py")
            module_name = "primer3_gui_dynamic"
            spec = importlib.util.spec_from_file_location(module_name, primer3_gui_path)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = mod
                spec.loader.exec_module(mod)
                # 保持窗口引用，避免被回收
                if not hasattr(window, "_primer3_window") or window._primer3_window is None:
                    window._primer3_window = mod.MainWindow()
                window._primer3_window.show()
                window._primer3_window.raise_()
                window._primer3_window.activateWindow()
            else:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(window, "错误", "无法加载 primer3_gui.py 模块。")
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(window, "错误", f"无法加载引物设计界面: {e}")
    open_primer_action.triggered.connect(_open_primer_designer)
    primer_menu.addAction(open_primer_action)
    # 7. 进化树构建与可视化
    evolution_menu = menubar.addMenu(window.tr("进化树构建与可视化"))
    # 7.1 系统发育树构建（在线工具）子菜单
    phylo_build_menu = QMenu(window.tr("系统发育树构建(在线工具)"), window)
    ngphylogeny_action = QAction("NGPhylogeny.fr", window)
    ngphylogeny_action.triggered.connect(lambda: window.open_url_in_browser("https://ngphylogeny.fr/about"))
    phylo_build_menu.addAction(ngphylogeny_action)
    iqtree_action = QAction("IQ-TREE", window)
    iqtree_action.triggered.connect(lambda: window.open_url_in_browser("http://iqtree.cibiv.univie.ac.at/"))
    phylo_build_menu.addAction(iqtree_action)
    tygs_action = QAction("TYGS", window)
    tygs_action.triggered.connect(lambda: window.open_url_in_browser("https://tygs.dsmz.de/"))
    phylo_build_menu.addAction(tygs_action)
    evolution_menu.addMenu(phylo_build_menu)
    # 7.2 进化树可视化（在线工具）子菜单
    phylo_vis_menu = QMenu(window.tr("进化树可视化（在线工具）"), window)
    itol_action = QAction("iTOL", window)
    itol_action.triggered.connect(lambda: window.open_url_in_browser("https://itol.embl.de/"))
    phylo_vis_menu.addAction(itol_action)
    tvbot_action = QAction("TVBOT", window)
    tvbot_action.triggered.connect(lambda: window.open_url_in_browser("https://www.chiplot.online/tvbot.html"))
    phylo_vis_menu.addAction(tvbot_action)
    evolution_menu.addMenu(phylo_vis_menu)
    # 8. 收藏夹系统
    fav_menu = menubar.addMenu(window.tr("收藏夹"))
    manage_fav_action = QAction(window.tr("管理收藏夹"), window)
    def _open_bookmark_manager():
        # 保持引用，避免窗口被回收
        if not hasattr(window, "_bookmark_manager") or window._bookmark_manager is None:
            window._bookmark_manager = BookmarkManager()
        window._bookmark_manager.show()
        window._bookmark_manager.raise_()
        window._bookmark_manager.activateWindow()
    manage_fav_action.triggered.connect(_open_bookmark_manager)
    fav_menu.addAction(manage_fav_action)
    # 设置菜单
    settings_menu = menubar.addMenu(window.tr("设置"))
    
    # 1. 外观主题 (子菜单)
    theme_menu = QMenu(window.tr("外观主题"), window)
    light_action = QAction(window.tr("浅色主题"), window)
    dark_action = QAction(window.tr("深色主题"), window)
    light_action.triggered.connect(lambda: window.switch_theme(False))
    dark_action.triggered.connect(lambda: window.switch_theme(True))
    theme_menu.addAction(light_action)
    theme_menu.addAction(dark_action)
    settings_menu.addMenu(theme_menu)
    
    # 2. 界面语言 (子菜单)
    lang_menu = QMenu(window.tr("界面语言"), window)
    zh_action = QAction("中文", window)
    en_action = QAction("English", window)
    zh_action.triggered.connect(lambda: window.switch_language('zh'))
    en_action.triggered.connect(lambda: window.switch_language('en'))
    lang_menu.addAction(zh_action)
    lang_menu.addAction(en_action)
    settings_menu.addMenu(lang_menu)
    
    settings_menu.addSeparator()
    
    # 3. 检查更新
    check_update_action = QAction(window.tr("检查更新"), window)
    check_update_action.triggered.connect(window.check_for_updates)
    settings_menu.addAction(check_update_action)
    
    # 4. 关于
    about_action = QAction(window.tr("关于"), window)
    about_action.triggered.connect(window.show_about_dialog)
    settings_menu.addAction(about_action) 