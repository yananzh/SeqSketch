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
    seq_stat_action = QAction(window.tr("FASTA QC"), window)
    seq_stat_action.triggered.connect(window.open_sequence_statistics_tab)
    fasta_menu.addAction(seq_stat_action)
    simplify_ids_action = QAction(window.tr("Simplify Headers"), window)
    simplify_ids_action.triggered.connect(window.open_simplify_ids_tab)
    fasta_menu.addAction(simplify_ids_action)
    extract_by_id_action = QAction(window.tr("Filter by IDs"), window)
    extract_by_id_action.triggered.connect(window.open_extract_by_id_tab)
    fasta_menu.addAction(extract_by_id_action)
    extract_by_regex_action = QAction(window.tr("Regex Filter"), window)
    extract_by_regex_action.triggered.connect(window.open_extract_by_regex_tab)
    fasta_menu.addAction(extract_by_regex_action)
    # 新增：从NCBI下载序列
    download_ncbi_action = QAction(window.tr("NCBI Download"), window)
    download_ncbi_action.triggered.connect(window.open_download_from_ncbi_tab)
    fasta_menu.addAction(download_ncbi_action)
    # 新增：批量重命名ID
    batch_rename_action = QAction(window.tr("Rename IDs"), window)
    batch_rename_action.triggered.connect(window.open_batch_rename_ids_tab)
    fasta_menu.addAction(batch_rename_action)
    # 新增：去重
    dedup_action = QAction(window.tr("Deduplicate"), window)
    dedup_action.triggered.connect(window.open_deduplicate_tab)
    fasta_menu.addAction(dedup_action)
    # 新增：长度筛选
    filter_len_action = QAction(window.tr("Filter by Length"), window)
    filter_len_action.triggered.connect(window.open_filter_by_length_tab)
    fasta_menu.addAction(filter_len_action)
    # 新增：合并FASTA
    concat_action = QAction(window.tr("Concatenate FASTA"), window)
    concat_action.triggered.connect(window.open_concat_fasta_tab)
    fasta_menu.addAction(concat_action)
    # 2. DNA Analysis
    dna_menu = menubar.addMenu(window.tr("DNA Analysis"))
    rna_action = QAction(window.tr("Convert to RNA"), window)
    rna_action.triggered.connect(window.open_rna_tab)
    dna_menu.addAction(rna_action)
    complement_action = QAction(window.tr("Complement/Reverse Complement"), window)
    complement_action.triggered.connect(window.open_complement_tab)
    dna_menu.addAction(complement_action)
    translate_action = QAction(window.tr("Translate"), window)
    translate_action.triggered.connect(window.open_translate_tab)
    dna_menu.addAction(translate_action)
    orf_action = QAction(window.tr("ORF Finder"), window)
    orf_action.triggered.connect(window.open_orf_tab)
    dna_menu.addAction(orf_action)
    sanger_viewer_action = QAction(window.tr("Sanger Seq Viewer"), window)
    sanger_viewer_action.triggered.connect(window.open_sanger_viewer_tab)
    dna_menu.addAction(sanger_viewer_action)
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
    # 3. Protein Annotation and Reference (submenu)
    annotation_menu = QMenu(window.tr("Protein Annotation and Reference"), window)
    uniprotkb_action = QAction("UniProtKB", window)
    uniprotkb_action.triggered.connect(
        lambda: window.open_url_in_browser("https://www.uniprot.org/uniprotkb")
    )
    annotation_menu.addAction(uniprotkb_action)
    uniprot_mapping_action = QAction("UniProt ID Mapping", window)
    uniprot_mapping_action.triggered.connect(
        lambda: window.open_url_in_browser("https://www.uniprot.org/id-mapping")
    )
    annotation_menu.addAction(uniprot_mapping_action)
    protein_menu.addMenu(annotation_menu)
    # 3. Secondary Structure Prediction (submenu)
    sec_struct_menu = QMenu(window.tr("Secondary Structure Prediction"), window)
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
    # 4. Tertiary Structure Prediction (submenu)
    tert_struct_menu = QMenu(window.tr("Tertiary Structure Prediction"), window)
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
    # 5. Tertiary Structure Reference (submenu)
    tert_reference_menu = QMenu(window.tr("Tertiary Structure Reference"), window)
    alphafold_db_action = QAction("AlphaFold DB", window)
    alphafold_db_action.triggered.connect(
        lambda: window.open_url_in_browser("https://alphafold.ebi.ac.uk/")
    )
    tert_reference_menu.addAction(alphafold_db_action)
    rcsb_pdb_action = QAction("RCSB PDB", window)
    rcsb_pdb_action.triggered.connect(
        lambda: window.open_url_in_browser("https://www.rcsb.org/")
    )
    tert_reference_menu.addAction(rcsb_pdb_action)
    protein_menu.addMenu(tert_reference_menu)
    # 5. Domain and Motif Analysis (submenu)
    domain_menu = QMenu(window.tr("Domain and Motif Analysis"), window)
    interpro_action = QAction("InterPro", window)
    interpro_action.triggered.connect(
        lambda: window.open_url_in_browser("https://www.ebi.ac.uk/interpro/")
    )
    domain_menu.addAction(interpro_action)
    meme_suite_action = QAction("MEME Suite", window)
    meme_suite_action.triggered.connect(
        lambda: window.open_url_in_browser("https://meme-suite.org/meme/")
    )
    domain_menu.addAction(meme_suite_action)
    scanprosite_action = QAction("ScanProsite", window)
    scanprosite_action.triggered.connect(
        lambda: window.open_url_in_browser("https://prosite.expasy.org/scanprosite/")
    )
    domain_menu.addAction(scanprosite_action)
    cd_search_action = QAction("NCBI CD-Search", window)
    cd_search_action.triggered.connect(
        lambda: window.open_url_in_browser(
            "https://www.ncbi.nlm.nih.gov/Structure/cdd/wrpsb.cgi"
        )
    )
    domain_menu.addAction(cd_search_action)
    protein_menu.addMenu(domain_menu)
    # 6. Signal Peptide and Topology Prediction (submenu)
    signal_menu = QMenu(window.tr("Signal Peptide and Topology Prediction"), window)
    signalp_action = QAction("SignalP 6.0", window)
    signalp_action.triggered.connect(
        lambda: window.open_url_in_browser(
            "https://services.healthtech.dtu.dk/services/SignalP-6.0/"
        )
    )
    signal_menu.addAction(signalp_action)
    deeptmhmm_action = QAction("DeepTMHMM 1.0", window)
    deeptmhmm_action.triggered.connect(
        lambda: window.open_url_in_browser(
            "https://services.healthtech.dtu.dk/services/DeepTMHMM-1.0/"
        )
    )
    signal_menu.addAction(deeptmhmm_action)
    protein_menu.addMenu(signal_menu)
    # 8. Protein Homology Search (submenu)
    homolog_menu = QMenu(window.tr("Protein Homology Search"), window)
    hmmer_action = QAction("HMMER", window)
    hmmer_action.triggered.connect(
        lambda: window.open_url_in_browser(
            "https://www.ebi.ac.uk/Tools/hmmer/search/phmmer"
        )
    )
    homolog_menu.addAction(hmmer_action)
    protein_menu.addMenu(homolog_menu)
    # 9. Protein Function and Interaction (submenu)
    function_menu = QMenu(window.tr("Protein Function and Interaction"), window)
    string_action = QAction("STRING", window)
    string_action.triggered.connect(
        lambda: window.open_url_in_browser("https://string-db.org/")
    )
    function_menu.addAction(string_action)
    mobidb_action = QAction("MobiDB", window)
    mobidb_action.triggered.connect(
        lambda: window.open_url_in_browser("https://mobidb.org/")
    )
    function_menu.addAction(mobidb_action)
    protein_menu.addMenu(function_menu)
    # 9. Protein Structure Similarity Search (submenu)
    structure_similarity_menu = QMenu(
        window.tr("Protein Structure Similarity Search"), window
    )
    foldseek_action = QAction("Foldseek Search", window)
    foldseek_action.triggered.connect(
        lambda: window.open_url_in_browser("https://search.foldseek.com/search")
    )
    structure_similarity_menu.addAction(foldseek_action)
    protein_menu.addMenu(structure_similarity_menu)
    # 10. Pairwise Protein Structure Alignment (submenu)
    pairwise_structure_menu = QMenu(
        window.tr("Pairwise Protein Structure Alignment"), window
    )
    rcsb_structure_alignment_action = QAction(
        window.tr("RCSB Pairwise Structure Alignment"), window
    )
    rcsb_structure_alignment_action.triggered.connect(
        lambda: window.open_url_in_browser("https://www.rcsb.org/alignment")
    )
    pairwise_structure_menu.addAction(rcsb_structure_alignment_action)
    protein_menu.addMenu(pairwise_structure_menu)
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
    mafft_action = QAction(window.tr("Multiple Sequence Alignment (MAFFT)"), window)
    mafft_action.triggered.connect(window.open_mafft_alignment_tab)
    align_menu.addAction(mafft_action)
    converter_action = QAction(window.tr("Alignment Format Converter"), window)
    converter_action.triggered.connect(window.open_alignment_format_converter_tab)
    align_menu.addAction(converter_action)
    # 4. MSA可视化 (本地)
    msa_viz_action = QAction(window.tr("MSA Visualization (pyMSAviz)"), window)
    msa_viz_action.triggered.connect(window.open_msa_visualization_tab)
    align_menu.addAction(msa_viz_action)
    # 5. 序列标识图 (本地)
    seq_logo_action = QAction(window.tr("Sequence Logo (Logomaker)"), window)
    seq_logo_action.triggered.connect(window.open_sequence_logo_tab)
    align_menu.addAction(seq_logo_action)
    # 5. BLAST
    blast_menu = menubar.addMenu(window.tr("BLAST"))
    # NCBI在线BLAST
    ncbi_blast_action = QAction(window.tr("NCBI Online BLAST"), window)
    ncbi_blast_action.triggered.connect(window.open_ncbi_blast_web)
    blast_menu.addAction(ncbi_blast_action)
    local_blast_action = QAction(window.tr("Local BLAST"), window)
    local_blast_action.triggered.connect(window.open_blast_local_tab)
    blast_menu.addAction(local_blast_action)
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
    # 7.1 Alignment Trimming (trimAl)
    trimal_action = QAction(window.tr("Alignment Trimming (trimAl)"), window)
    trimal_action.triggered.connect(window.open_alignment_trimming_tab)
    evolution_menu.addAction(trimal_action)
    # 7.2 Sequence Concatenation
    partition_action = QAction(window.tr("Sequence Concatenation"), window)
    partition_action.triggered.connect(window.open_partition_concat_tab)
    evolution_menu.addAction(partition_action)
    # 7.3 Tree Construction (IQ-TREE)
    iqtree_local_action = QAction(window.tr("Tree Construction (IQ-TREE)"), window)
    iqtree_local_action.triggered.connect(window.open_iqtree_tab)
    evolution_menu.addAction(iqtree_local_action)
    one_step_multigenephy_action = QAction(window.tr("One Step MultiGenePhy"), window)
    one_step_multigenephy_action.triggered.connect(
        window.open_one_step_multigenephy_tab
    )
    evolution_menu.addAction(one_step_multigenephy_action)
    # 7.4 Simple Tree Visualization (local, phytreeviz)
    tree_vis_action = QAction(
        window.tr("Simple Tree Visualization (Phytreeviz)"), window
    )
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
