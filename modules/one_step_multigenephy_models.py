from dataclasses import dataclass


@dataclass(slots=True)
class ProjectInput:
    excel_path: str
    sheet_name: str
    strain_column: str
    gene_columns: list[str]
    output_dir: str
    ncbi_email: str = ""
    keep_intermediates: bool = True
    missing_gene_strategy: str = "gap"
    mafft_mode: str = "--auto"
    trimal_mode: str = "automated1"
    iqtree_bootstrap: int = 1000
    threads: str = "AUTO"


@dataclass(slots=True)
class GeneCell:
    strain_name: str
    gene_name: str
    raw_value: str
    value_type: str
    accession: str = ""
    normalized_sequence: str = ""
    source: str = ""
    status: str = "pending"
    message: str = ""


@dataclass(slots=True)
class ParsedExcelSheet:
    strain_order: list[str]
    cells: list[GeneCell]
    summary: dict[str, int]
