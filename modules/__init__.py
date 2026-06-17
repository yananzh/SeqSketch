"""
SeqSketch - 功能模块包

包含各种生物信息学分析功能模块：
- fasta_processor: FASTA文件处理模块
- sequence_analyzer: 序列分析模块
- alignment_tools: 比对工具模块
- blast_tools: BLAST分析模块
- primer_tools: 引物设计模块
- phylogeny_tools: 进化分析模块
"""

__version__ = "1.0.0"
__author__ = "SeqSketch Team"

# 导入主要模块
from .fasta_processor import FASTAProcessor
from .sequence_analyzer import SequenceAnalyzer
from .sequence_statistics_tab import SequenceStatisticsTab
from .simplify_ids_tab import SimplifyIDsTab
from .extract_by_id_tab import ExtractByIDTab
from .extract_by_regex_tab import ExtractByRegexTab
from .download_from_ncbi_tab import DownloadFromNCBITab
from .batch_rename_ids_tab import BatchRenameIDsTab
from .rna_tab import RNATab
from .complement_tab import ComplementTab
from .reverse_complement_tab import ReverseComplementTab
from .translate_tab import TranslateTab
from .orf_tab import ORFTab
from .sanger_tab import SangerTab
from .amino_acid_composition_tab import AminoAcidCompositionTab
from .physicochemical_properties_tab import PhysicochemicalPropertiesTab

# 引物设计相关模块
try:
    from .primer3_gui import MainWindow as Primer3MainWindow
except ImportError:
    Primer3MainWindow = None

try:
    from .primer_gui import MainWindow as PrimerMainWindow
except ImportError:
    PrimerMainWindow = None

__all__ = [
    "FASTAProcessor",
    "SequenceAnalyzer",
    "SequenceStatisticsTab",
    "SimplifyIDsTab",
    "ExtractByIDTab",
    "ExtractByRegexTab",
    "DownloadFromNCBITab",
    "BatchRenameIDsTab",
    "Primer3MainWindow",
    "PrimerMainWindow",
]
