import importlib.util
import os
import sys

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu, QMenuBar


def create_menus(window):
    menubar = window.menuBar()
    menubar.clear()
    # 1. FASTA Tools
    fasta_menu = menubar.addMenu("FASTA Tools")
    # 四个功能项
    seq_stat_action = QAction("FASTA Statistics", window)
    seq_stat_action.triggered.connect(window.open_sequence_statistics_tab)
    fasta_menu.addAction(seq_stat_action)
    # 新增：批量重命名ID
    batch_rename_action = QAction("Rename IDs", window)
    batch_rename_action.triggered.connect(window.open_batch_rename_ids_tab)
    fasta_menu.addAction(batch_rename_action)
    simplify_ids_action = QAction("Simplify Headers", window)
    simplify_ids_action.triggered.connect(window.open_simplify_ids_tab)
    fasta_menu.addAction(simplify_ids_action)
    extract_by_id_action = QAction("Filter by IDs", window)
    extract_by_id_action.triggered.connect(window.open_extract_by_id_tab)
    fasta_menu.addAction(extract_by_id_action)
    # 新增：长度筛选
    filter_len_action = QAction("Filter by Length", window)
    filter_len_action.triggered.connect(window.open_filter_by_length_tab)
    fasta_menu.addAction(filter_len_action)
    extract_by_regex_action = QAction("Regex Filter", window)
    extract_by_regex_action.triggered.connect(window.open_extract_by_regex_tab)
    fasta_menu.addAction(extract_by_regex_action)
    # 新增：从NCBI下载序列
    download_ncbi_action = QAction("NCBI Download", window)
    download_ncbi_action.triggered.connect(window.open_download_from_ncbi_tab)
    fasta_menu.addAction(download_ncbi_action)
    # 新增：去重
    dedup_action = QAction("Deduplicate", window)
    dedup_action.triggered.connect(window.open_deduplicate_tab)
    fasta_menu.addAction(dedup_action)
    # 新增：合并FASTA
    concat_action = QAction("Concatenate FASTA", window)
    concat_action.triggered.connect(window.open_concat_fasta_tab)
    fasta_menu.addAction(concat_action)
    # 新增：拆分FASTA
    split_action = QAction("Split FASTA", window)
    split_action.triggered.connect(window.open_split_fasta_tab)
    fasta_menu.addAction(split_action)
    # 新增：排序FASTA
    sort_action = QAction("Sort FASTA", window)
    sort_action.triggered.connect(window.open_sort_fasta_tab)
    fasta_menu.addAction(sort_action)
    # 新增：FASTA与表格互转
    table_action = QAction("FASTA \u2194 Table", window)
    table_action.triggered.connect(window.open_fasta_table_converter_tab)
    fasta_menu.addAction(table_action)
    # 2. DNA Analysis
    dna_menu = menubar.addMenu("DNA Analysis")
    rna_action = QAction("Convert to RNA", window)
    rna_action.triggered.connect(window.open_rna_tab)
    dna_menu.addAction(rna_action)
    complement_action = QAction("Complement/Reverse Complement", window)
    complement_action.triggered.connect(window.open_complement_tab)
    dna_menu.addAction(complement_action)
    translate_action = QAction("Translate", window)
    translate_action.triggered.connect(window.open_translate_tab)
    dna_menu.addAction(translate_action)
    orf_action = QAction("ORF Finder", window)
    orf_action.triggered.connect(window.open_orf_tab)
    dna_menu.addAction(orf_action)
    sanger_viewer_action = QAction("Sanger Chromatogram Viewer", window)
    sanger_viewer_action.triggered.connect(window.open_sanger_viewer_tab)
    dna_menu.addAction(sanger_viewer_action)
    sanger_action = QAction("Sanger Sequence Assembly", window)
    sanger_action.triggered.connect(window.open_sanger_tab)
    dna_menu.addAction(sanger_action)
    codon_usage_action = QAction("Codon Usage Analysis", window)
    codon_usage_action.triggered.connect(window.open_codon_usage_tab)
    dna_menu.addAction(codon_usage_action)
    restriction_action = QAction("Restriction Enzyme Analysis", window)
    restriction_action.triggered.connect(window.open_restriction_enzyme_tab)
    dna_menu.addAction(restriction_action)
    gc_plot_action = QAction("GC Content / GC Skew Plot", window)
    gc_plot_action.triggered.connect(window.open_gc_plot_tab)
    dna_menu.addAction(gc_plot_action)
    cpg_island_action = QAction("CpG Island Finder", window)
    cpg_island_action.triggered.connect(window.open_cpg_island_tab)
    dna_menu.addAction(cpg_island_action)
    ssr_finder_action = QAction("SSR / Microsatellite Finder", window)
    ssr_finder_action.triggered.connect(window.open_ssr_finder_tab)
    dna_menu.addAction(ssr_finder_action)
    # 3. Protein Analysis
    protein_menu = menubar.addMenu("Protein Analysis")

    # ── Local Analysis (submenu) ──────────────────────────────────────
    local_analysis_menu = QMenu("Local Analysis", window)
    aa_comp_action = QAction("Amino Acid Composition", window)
    aa_comp_action.triggered.connect(window.open_amino_acid_composition_tab)
    local_analysis_menu.addAction(aa_comp_action)
    physchem_action = QAction("Physicochemical Properties", window)
    physchem_action.triggered.connect(window.open_physicochemical_properties_tab)
    local_analysis_menu.addAction(physchem_action)
    hydro_plot_action = QAction("Hydrophobicity Plot", window)
    hydro_plot_action.triggered.connect(window.open_hydrophobicity_plot_tab)
    local_analysis_menu.addAction(hydro_plot_action)
    protease_cleavage_action = QAction("Protease Cleavage Map", window)
    protease_cleavage_action.triggered.connect(window.open_protease_cleavage_tab)
    local_analysis_menu.addAction(protease_cleavage_action)
    protein_menu.addMenu(local_analysis_menu)
    protein_menu.addSeparator()

    # ── Sequence Annotation & Features (submenu) ───────────────────────
    annotation_menu = QMenu("Annotation & Features", window)
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
    annotation_menu.addSeparator()
    # Domain & Motif
    interpro_action = QAction("InterPro", window)
    interpro_action.triggered.connect(
        lambda: window.open_url_in_browser("https://www.ebi.ac.uk/interpro/")
    )
    annotation_menu.addAction(interpro_action)
    cd_search_action = QAction("NCBI CD-Search", window)
    cd_search_action.triggered.connect(
        lambda: window.open_url_in_browser("https://www.ncbi.nlm.nih.gov/Structure/cdd/wrpsb.cgi")
    )
    annotation_menu.addAction(cd_search_action)
    scanprosite_action = QAction("ScanProsite", window)
    scanprosite_action.triggered.connect(
        lambda: window.open_url_in_browser("https://prosite.expasy.org/scanprosite/")
    )
    annotation_menu.addAction(scanprosite_action)
    meme_suite_action = QAction("MEME Suite", window)
    meme_suite_action.triggered.connect(
        lambda: window.open_url_in_browser("https://meme-suite.org/meme/")
    )
    annotation_menu.addAction(meme_suite_action)
    annotation_menu.addSeparator()
    # Signal / Topology / Localization
    signalp_action = QAction("SignalP 6.0", window)
    signalp_action.triggered.connect(
        lambda: window.open_url_in_browser(
            "https://services.healthtech.dtu.dk/services/SignalP-6.0/"
        )
    )
    annotation_menu.addAction(signalp_action)
    deeptmhmm_action = QAction("DeepTMHMM 1.0", window)
    deeptmhmm_action.triggered.connect(
        lambda: window.open_url_in_browser(
            "https://services.healthtech.dtu.dk/services/DeepTMHMM-1.0/"
        )
    )
    annotation_menu.addAction(deeptmhmm_action)
    deeploc_action = QAction("DeepLoc 2.1", window)
    deeploc_action.triggered.connect(
        lambda: window.open_url_in_browser(
            "https://services.healthtech.dtu.dk/services/DeepLoc-2.1/"
        )
    )
    annotation_menu.addAction(deeploc_action)
    protein_menu.addMenu(annotation_menu)

    # ── Structure (submenu) ────────────────────────────────────────────
    structure_menu = QMenu("Structure", window)
    # Secondary structure
    psipred_action = QAction("PSIPRED", window)
    psipred_action.triggered.connect(
        lambda: window.open_url_in_browser("http://bioinf.cs.ucl.ac.uk/psipred/")
    )
    structure_menu.addAction(psipred_action)
    jpred_action = QAction("Jpred4", window)
    jpred_action.triggered.connect(
        lambda: window.open_url_in_browser("https://www.compbio.dundee.ac.uk/jpred/")
    )
    structure_menu.addAction(jpred_action)
    structure_menu.addSeparator()
    # Tertiary prediction
    swiss_model_action = QAction("SWISS-MODEL", window)
    swiss_model_action.triggered.connect(
        lambda: window.open_url_in_browser("https://swissmodel.expasy.org/")
    )
    structure_menu.addAction(swiss_model_action)
    alphafold_action = QAction("AlphaFold Server", window)
    alphafold_action.triggered.connect(
        lambda: window.open_url_in_browser("https://alphafoldserver.com/")
    )
    structure_menu.addAction(alphafold_action)
    structure_menu.addSeparator()
    # Structure databases
    alphafold_db_action = QAction("AlphaFold DB", window)
    alphafold_db_action.triggered.connect(
        lambda: window.open_url_in_browser("https://alphafold.ebi.ac.uk/")
    )
    structure_menu.addAction(alphafold_db_action)
    rcsb_pdb_action = QAction("RCSB PDB", window)
    rcsb_pdb_action.triggered.connect(lambda: window.open_url_in_browser("https://www.rcsb.org/"))
    structure_menu.addAction(rcsb_pdb_action)
    structure_menu.addSeparator()
    # Structure comparison
    foldseek_action = QAction("Foldseek Search", window)
    foldseek_action.triggered.connect(
        lambda: window.open_url_in_browser("https://search.foldseek.com/search")
    )
    structure_menu.addAction(foldseek_action)
    rcsb_structure_alignment_action = QAction("RCSB Pairwise Alignment", window)
    rcsb_structure_alignment_action.triggered.connect(
        lambda: window.open_url_in_browser("https://www.rcsb.org/alignment")
    )
    structure_menu.addAction(rcsb_structure_alignment_action)
    protein_menu.addMenu(structure_menu)

    # ── Function & Interaction (submenu) ───────────────────────────────
    function_menu = QMenu("Function & Interaction", window)
    string_action = QAction("STRING", window)
    string_action.triggered.connect(lambda: window.open_url_in_browser("https://string-db.org/"))
    function_menu.addAction(string_action)
    mobidb_action = QAction("MobiDB", window)
    mobidb_action.triggered.connect(lambda: window.open_url_in_browser("https://mobidb.org/"))
    function_menu.addAction(mobidb_action)
    hmmer_action = QAction("HMMER (phmmer)", window)
    hmmer_action.triggered.connect(
        lambda: window.open_url_in_browser("https://www.ebi.ac.uk/Tools/hmmer/search/phmmer")
    )
    function_menu.addAction(hmmer_action)
    protein_menu.addMenu(function_menu)
    # 4. Alignment
    align_menu = menubar.addMenu("Alignment")
    # 1. 双序列比对 (本地)
    pairwise_action = QAction("Pairwise Sequence Alignment", window)
    pairwise_action.triggered.connect(window.open_pairwise_alignment_tab)
    align_menu.addAction(pairwise_action)
    # 2. DotPlot (本地)
    dotplot_action = QAction("DotPlot", window)
    dotplot_action.triggered.connect(window.open_dotplot_tab)
    align_menu.addAction(dotplot_action)
    # 3. 多序列比对 (本地) — MAFFT / Muscle5 子菜单
    msa_menu = QMenu("Multiple Sequence Alignment", window)
    mafft_action = QAction("MAFFT", window)
    mafft_action.triggered.connect(window.open_mafft_alignment_tab)
    msa_menu.addAction(mafft_action)
    msa_action = QAction("Muscle5", window)
    msa_action.triggered.connect(window.open_multiple_sequence_alignment_tab)
    msa_menu.addAction(msa_action)
    align_menu.addMenu(msa_menu)
    converter_action = QAction("Alignment Format Converter", window)
    converter_action.triggered.connect(window.open_alignment_format_converter_tab)
    align_menu.addAction(converter_action)
    # 4. MSA可视化 (本地)
    msa_viz_action = QAction("MSA Visualization (pyMSAviz)", window)
    msa_viz_action.triggered.connect(window.open_msa_visualization_tab)
    align_menu.addAction(msa_viz_action)
    # 5. 序列标识图 (本地)
    seq_logo_action = QAction("Sequence Logo (Logomaker)", window)
    seq_logo_action.triggered.connect(window.open_sequence_logo_tab)
    align_menu.addAction(seq_logo_action)
    # 5. BLAST
    blast_menu = menubar.addMenu("BLAST")
    # NCBI在线BLAST
    ncbi_blast_action = QAction("NCBI Online BLAST", window)
    ncbi_blast_action.triggered.connect(window.open_ncbi_blast_web)
    blast_menu.addAction(ncbi_blast_action)
    local_blast_action = QAction("Local BLAST", window)
    local_blast_action.triggered.connect(window.open_blast_local_tab)
    blast_menu.addAction(local_blast_action)
    # 6. Primer Design
    primer_menu = menubar.addMenu("Primer Design")
    open_primer_action = QAction("qPCR Primer Design", window)
    open_primer_action.triggered.connect(window.open_primer_design_tab)
    primer_menu.addAction(open_primer_action)
    open_cloning_action = QAction("Cloning Primer Design", window)
    open_cloning_action.triggered.connect(window.open_cloning_primer_tab)
    primer_menu.addAction(open_cloning_action)
    open_analysis_action = QAction("Primer Analysis", window)
    open_analysis_action.triggered.connect(window.open_primer_analysis_tab)
    primer_menu.addAction(open_analysis_action)
    # 7. Phylogenetic Tree
    evolution_menu = menubar.addMenu("Phylogenetic Tree")
    # 7.1 Alignment Trimming (trimAl)
    trimal_action = QAction("Alignment Trimming (trimAl)", window)
    trimal_action.triggered.connect(window.open_alignment_trimming_tab)
    evolution_menu.addAction(trimal_action)
    # 7.2 Sequence Concatenation
    partition_action = QAction("Sequence Concatenation", window)
    partition_action.triggered.connect(window.open_partition_concat_tab)
    evolution_menu.addAction(partition_action)
    # 7.3 Distance Tree Construction
    dist_tree_action = QAction("Distance Tree Construction", window)
    dist_tree_action.triggered.connect(window.open_distance_tree_tab)
    evolution_menu.addAction(dist_tree_action)
    # 7.4 ML Tree Construction (IQ-TREE)
    iqtree_local_action = QAction("ML Tree Construction (IQ-TREE)", window)
    iqtree_local_action.triggered.connect(window.open_iqtree_tab)
    evolution_menu.addAction(iqtree_local_action)
    one_step_multigenephy_action = QAction("One Step MultiGenePhy", window)
    one_step_multigenephy_action.triggered.connect(window.open_one_step_multigenephy_tab)
    evolution_menu.addAction(one_step_multigenephy_action)
    # 7.5 Tree Visualization (local, toytree)
    toytree_vis_action = QAction("Tree Visualization (Toytree)", window)
    toytree_vis_action.triggered.connect(window.open_toytree_visualization_tab)
    evolution_menu.addAction(toytree_vis_action)
    # 8. Bookmarks
    fav_menu = menubar.addMenu("Bookmarks")
    manage_fav_action = QAction("Manage Bookmarks", window)
    manage_fav_action.triggered.connect(window.open_favorites_manager_tab)
    fav_menu.addAction(manage_fav_action)
    # Settings menu
    settings_menu = menubar.addMenu("Settings")

    # 检查更新
    check_update_action = QAction("Check for Updates", window)
    check_update_action.triggered.connect(window.check_for_updates)
    settings_menu.addAction(check_update_action)

    # 关于
    about_action = QAction("About", window)
    about_action.triggered.connect(window.show_about_dialog)
    settings_menu.addAction(about_action)
