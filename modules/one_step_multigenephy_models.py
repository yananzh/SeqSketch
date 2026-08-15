from dataclasses import dataclass, field


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
    iqtree_bootstrap_mode: str = "ufboot"
    threads: str = "AUTO"
    resume_mode: str = "scratch"  # "scratch" | "align" (skip fetch) | "tree" (skip fetch/align/trim/concat)


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


@dataclass(slots=True)
class GeneDataset:
    gene_name: str
    strain_order: list[str]
    cells: list[GeneCell] = field(default_factory=list)
    missing_strains: list[str] = field(default_factory=list)
    invalid_cells: list[GeneCell] = field(default_factory=list)
    normalized_sequences: dict[str, str] = field(default_factory=dict)
    trimmed_sequences: dict[str, str] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    status: str = "pending"


@dataclass(slots=True)
class RunArtifacts:
    root_dir: str
    manifest_path: str = ""
    report_path: str = ""
    html_report_path: str = ""
    treefile_path: str = ""
    normalized_files: dict[str, str] = field(default_factory=dict)
    aligned_files: dict[str, str] = field(default_factory=dict)
    trimmed_files: dict[str, str] = field(default_factory=dict)
    extra_paths: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class WorkflowRunResult:
    step_status: dict[str, str]
    warnings: list[str]
    artifacts: RunArtifacts
