"""
SeqSketch — feature module package.

Contains tab widgets and supporting modules for FASTA processing,
DNA/RNA analysis, protein analysis, alignment, BLAST, primer design,
phylogenetics, and Sanger sequencing.
"""

__version__ = "1.0.0"
__author__ = "SeqSketch Team"

from .amino_acid_composition_tab import AminoAcidCompositionTab
from .batch_rename_ids_tab import BatchRenameIDsTab
from .complement_tab import ComplementTab
from .download_from_ncbi_tab import DownloadFromNCBITab
from .extract_by_id_tab import ExtractByIDTab
from .extract_by_regex_tab import ExtractByRegexTab
from .fasta_processor import FASTAProcessor
from .orf_tab import ORFTab
from .physicochemical_properties_tab import PhysicochemicalPropertiesTab
from .reverse_complement_tab import ReverseComplementTab
from .rna_tab import RNATab
from .sanger_tab import SangerTab
from .sequence_statistics_tab import SequenceStatisticsTab
from .simplify_ids_tab import SimplifyIDsTab
from .translate_tab import TranslateTab

__all__ = [
    "FASTAProcessor",
    "SequenceStatisticsTab",
    "SimplifyIDsTab",
    "ExtractByIDTab",
    "ExtractByRegexTab",
    "DownloadFromNCBITab",
    "BatchRenameIDsTab",
]
