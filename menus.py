from PyQt6.QtWidgets import QMenuBar, QMenu
from PyQt6.QtGui import QAction
from modules.favorites_manager import BookmarkManager
import os
import sys
import importlib.util


def create_menus(window):
    menubar = window.menuBar()
    menubar.clear()
    # 1. FASTA Tools
    fasta_menu = menubar.addMenu(window.tr("FASTA Tools"))
    # 四个功能项
    seq_stat_action = QAction(window.tr("Sequence Statistics"), window)
    seq_stat_action.triggered.connect(window.open_sequence_statistics_tab)
    fasta_menu.addAction(seq_stat_action)
    simplify_ids_action = QAction(window.tr("Simplify IDs"), window)
    simplify_ids_action.triggered.connect(window.open_simplify_ids_tab)
    fasta_menu.addAction(simplify_ids_action)
    extract_by_id_action = QAction(window.tr("Extract by ID"), window)
    extract_by_id_action.triggered.connect(window.open_extract_by_id_tab)
    fasta_menu.addAction(extract_by_id_action)
    extract_by_regex_action = QAction(window.tr("Extract by Regex"), window)
    extract_by_regex_action.triggered.connect(window.open_extract_by_regex_tab)
    fasta_menu.addAction(extract_by_regex_action)
    # 新增：从NCBI下载序列
    download_ncbi_action = QAction(window.tr("Download from NCBI"), window)
    download_ncbi_action.triggered.connect(window.open_download_from_ncbi_tab)
    fasta_menu.addAction(download_ncbi_action)
    # 新增：批量重命名ID
    batch_rename_action = QAction(window.tr("Batch Rename IDs"), window)
    batch_rename_action.triggered.connect(window.open_batch_rename_ids_tab)
    fasta_menu.addAction(batch_rename_action)
    # 2. DNA Analysis
    dna_menu = menubar.addMenu(window.tr("DNA Analysis"))
    rna_action = QAction(window.tr("Convert to RNA"), window)
    rna_action.triggered.connect(window.open_rna_tab)
    dna_menu.addAction(rna_action)
    complement_action = QAction(window.tr("Complement"), window)
    complement_action.triggered.connect(window.open_complement_tab)
    dna_menu.addAction(complement_action)
    revcomp_action = QAction(window.tr("Reverse Complement"), window)
    revcomp_action.triggered.connect(window.open_reverse_complement_tab)
    dna_menu.addAction(revcomp_action)
    translate_action = QAction(window.tr("Translate"), window)
    translate_action.triggered.connect(window.open_translate_tab)
    dna_menu.addAction(translate_action)
    orf_action = QAction(window.tr("ORF Finder"), window)
    orf_action.triggered.connect(window.open_orf_tab)
    dna_menu.addAction(orf_action)
    sanger_action = QAction(window.tr("Sanger Sequence Assembly"), window)
    sanger_action.triggered.connect(window.open_sanger_tab)
    dna_menu.addAction(sanger_action)
    codon_usage_action = QAction(window.tr("Codon Usage Analysis"), window)
    codon_usage_action.triggered.connect(window.open_codon_usage_tab)
    dna_menu.addAction(codon_usage_action)
    # 3. Protein Analysis
    protein_menu = menubar.addMenu(window.tr("Protein Analysis"))
    # 1. 氨基酸组成
    aa_comp_action = QAction(window.tr("Amino Acid Composition"), window)
    aa_comp_action.triggered.connect(window.open_amino_acid_composition_tab)
    protein_menu.addAction(aa_comp_action)
    # 2. 物化性质计算
    physchem_action = QAction(window.tr("Physicochemical Properties"), window)
    physchem_action.triggered.connect(window.open_physicochemical_properties_tab)
    protein_menu.addAction(physchem_action)
    protein_menu.addSeparator()
    # 3. Secondary Structure (submenu)
    sec_struct_menu = QMenu(window.tr("Secondary Structure"), window)
    psipred_action = QAction("PSIPRED", window)
    psipred_action.triggered.connect(
        lambda: window.open_url_in_browser("http://bioinf.cs.ucl.ac.uk/psipred/")
    )
    sec_struct_menu.addAction(psipred_action)
    jpred_action = QAction("Jpred4", window)
    jpred_action.triggered.connect(
        lambda: window.open_url_in_browser("https://www.compbio.dundee.ac.uk/jpred/")
    )
    sec_struct_menu.addAction(jpred_action)
    protein_menu.addMenu(sec_struct_menu)
    # 4. Tertiary Structure (submenu)
    tert_struct_menu = QMenu(window.tr("Tertiary Structure"), window)
    swiss_model_action = QAction("SWISS-MODEL", window)
    swiss_model_action.triggered.connect(
        lambda: window.open_url_in_browser("https://swissmodel.expasy.org/")
    )
    tert_struct_menu.addAction(swiss_model_action)
    alphafold_action = QAction("AlphaFold Server", window)
    alphafold_action.triggered.connect(
        lambda: window.open_url_in_browser("https://alphafoldserver.com/")
    )
    tert_struct_menu.addAction(alphafold_action)
    protein_menu.addMenu(tert_struct_menu)
    # 5. Domain Prediction (submenu)
    domain_menu = QMenu(window.tr("Domain Prediction"), window)
    interpro_action = QAction("InterPro", window)
    interpro_action.triggered.connect(
        lambda: window.open_url_in_browser("https://www.ebi.ac.uk/interpro/")
    )
    domain_menu.addAction(interpro_action)
    protein_menu.addMenu(domain_menu)
    # 6. Signal Peptide (submenu)
    signal_menu = QMenu(window.tr("Signal Peptide"), window)
    signalp_action = QAction("SignalP 6.0", window)
    signalp_action.triggered.connect(
        lambda: window.open_url_in_browser(
            "https://services.healthtech.dtu.dk/services/SignalP-6.0/"
        )
    )
    signal_menu.addAction(signalp_action)
    protein_menu.addMenu(signal_menu)
    # 7. Transmembrane Helices (submenu)
    tmhmm_menu = QMenu(window.tr("Transmembrane Helices"), window)
    deeptmhmm_action = QAction("DeepTMHMM 1.0", window)
    deeptmhmm_action.triggered.connect(
        lambda: window.open_url_in_browser(
            "https://services.healthtech.dtu.dk/services/DeepTMHMM-1.0/"
        )
    )
    tmhmm_menu.addAction(deeptmhmm_action)
    protein_menu.addMenu(tmhmm_menu)
    # 8. Homolog Search (submenu)
    homolog_menu = QMenu(window.tr("Homolog Search"), window)
    hmmer_action = QAction("HMMER", window)
    hmmer_action.triggered.connect(
        lambda: window.open_url_in_browser(
            "https://www.ebi.ac.uk/Tools/hmmer/search/phmmer"
        )
    )
    homolog_menu.addAction(hmmer_action)
    protein_menu.addMenu(homolog_menu)
    # 9. Structure Similarity (submenu)
    structure_similarity_menu = QMenu(window.tr("Structure Similarity"), window)
    foldseek_action = QAction("Foldseek Search", window)
    foldseek_action.triggered.connect(
        lambda: window.open_url_in_browser("https://search.foldseek.com/search")
    )
    structure_similarity_menu.addAction(foldseek_action)
    protein_menu.addMenu(structure_similarity_menu)
    # 4. Alignment
    align_menu = menubar.addMenu(window.tr("Alignment"))
    # 1. 双序列比对 (本地)
    pairwise_action = QAction(window.tr("Pairwise Sequence Alignment"), window)
    pairwise_action.triggered.connect(window.open_pairwise_alignment_tab)
    align_menu.addAction(pairwise_action)
    # 2. DotPlot (本地)
    dotplot_action = QAction(window.tr("DotPlot"), window)
    dotplot_action.triggered.connect(window.open_dotplot_tab)
    align_menu.addAction(dotplot_action)
    # 3. 多序列比对 (本地)
    msa_action = QAction(window.tr("Multiple Sequence Alignment (Muscle5)"), window)
    msa_action.triggered.connect(window.open_multiple_sequence_alignment_tab)
    align_menu.addAction(msa_action)
    # 4. MSA可视化 (本地)
    msa_viz_action = QAction(window.tr("MSA Visualization"), window)
    msa_viz_action.triggered.connect(window.open_msa_visualization_tab)
    align_menu.addAction(msa_viz_action)
    # 5. 序列标识图 (本地)
    seq_logo_action = QAction(window.tr("Sequence Logo"), window)
    seq_logo_action.triggered.connect(window.open_sequence_logo_tab)
    align_menu.addAction(seq_logo_action)
    # 5. BLAST
    blast_menu = menubar.addMenu(window.tr("BLAST"))
    # NCBI在线BLAST
    ncbi_blast_action = QAction(window.tr("NCBI Online BLAST"), window)
    ncbi_blast_action.triggered.connect(window.open_ncbi_blast_web)
    blast_menu.addAction(ncbi_blast_action)
    # 本地BLAST子菜单
    local_blast_menu = QMenu(window.tr("Local BLAST"), window)
    make_db_action = QAction(window.tr("1. Build BLAST Database..."), window)
    make_db_action.triggered.connect(window.open_blast_make_db_dialog)
    local_blast_menu.addAction(make_db_action)
    run_blast_action = QAction(window.tr("2. Run BLAST Query..."), window)
    run_blast_action.triggered.connect(window.open_blast_run_dialog)
    local_blast_menu.addAction(run_blast_action)
    blast_menu.addMenu(local_blast_menu)
    # 6. Primer Design
    primer_menu = menubar.addMenu(window.tr("Primer Design"))
    open_primer_action = QAction(window.tr("PCR Primer Assistant"), window)

    def _open_primer_designer():
        # 弹出 modules/primer3_gui.py 中的 MainWindow 作为独立窗口
        try:
            from modules.primer3_gui import MainWindow as Primer3MainWindow

            # 保持窗口引用，避免被回收
            if not hasattr(window, "_primer3_window") or window._primer3_window is None:
                window._primer3_window = Primer3MainWindow()
            window._primer3_window.show()
            window._primer3_window.raise_()
            window._primer3_window.activateWindow()
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(
                window, "Error", f"Failed to load primer designer: {e}"
            )

    open_primer_action.triggered.connect(_open_primer_designer)
    primer_menu.addAction(open_primer_action)
    # 7. Phylogenetic Tree
    evolution_menu = menubar.addMenu(window.tr("Phylogenetic Tree"))
    # 7.1 Sequence Concatenation & Partition (first)
    partition_action = QAction(
        window.tr("Sequence Concatenation and Partition Models"), window
    )
    partition_action.triggered.connect(window.open_partition_concat_tab)
    evolution_menu.addAction(partition_action)
    # 7.2 Alignment Trimming (trimAl)
    trimal_action = QAction(window.tr("Alignment Trimming (trimAl)"), window)
    trimal_action.triggered.connect(window.open_alignment_trimming_tab)
    evolution_menu.addAction(trimal_action)
    # 7.3 Local IQ-TREE tab
    iqtree_local_action = QAction(window.tr("Tree Construction (IQ-TREE)"), window)
    iqtree_local_action.triggered.connect(window.open_iqtree_tab)
    evolution_menu.addAction(iqtree_local_action)
    # 7.4 Tree Visualization (local, phytreeviz)
    tree_vis_action = QAction(window.tr("Tree Visualization"), window)
    tree_vis_action.triggered.connect(window.open_tree_visualization_tab)
    evolution_menu.addAction(tree_vis_action)
    # 8. Favorites
    fav_menu = menubar.addMenu(window.tr("Favorites"))
    manage_fav_action = QAction(window.tr("Manage Favorites"), window)

    def _open_bookmark_manager():
        # 保持引用，避免窗口被回收
        if not hasattr(window, "_bookmark_manager") or window._bookmark_manager is None:
            window._bookmark_manager = BookmarkManager()
        window._bookmark_manager.show()
        window._bookmark_manager.raise_()
        window._bookmark_manager.activateWindow()

    manage_fav_action.triggered.connect(_open_bookmark_manager)
    fav_menu.addAction(manage_fav_action)
    # Settings menu
    settings_menu = menubar.addMenu(window.tr("Settings"))

    # 检查更新
    check_update_action = QAction(window.tr("Check for Updates"), window)
    check_update_action.triggered.connect(window.check_for_updates)
    settings_menu.addAction(check_update_action)

    # 关于
    about_action = QAction(window.tr("About"), window)
    about_action.triggered.connect(window.show_about_dialog)
    settings_menu.addAction(about_action)
