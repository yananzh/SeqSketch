# One Step MultiGenePhy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-instance `One Step MultiGenePhy` tab that imports a mixed Excel matrix, normalizes accession-or-sequence cells, runs per-gene alignment/trimming, concatenates with gap filling, builds an IQ-TREE tree, and surfaces logs plus artifacts from one workflow screen.

**Architecture:** Add one new file-mode workflow tab for the UI, one workflow module for orchestration and worker/thread seams, and one focused data/helper module for Excel parsing, classification, concatenation, manifest/report output, and shared dataclasses. Keep existing phylogeny tabs intact and reuse them only through extracted helper logic or subprocess-style adapters, never by calling widget methods from the new workflow.

**Tech Stack:** PyQt6, pandas, openpyxl, Biopython Entrez, pytest, existing bundled MAFFT/trimAl/IQ-TREE executables, `utils.common_components.BaseTabWidget`, `utils.app_paths.resource_path`

---

## Planned File Map

- Modify: `requirements.txt`
  Add `openpyxl` so Excel import is actually available for `.xlsx` files.
- Create: `modules/one_step_multigenephy_models.py`
  Keep dataclasses and typed result containers small and stable.
- Create: `modules/one_step_multigenephy_io.py`
  Parse Excel, classify cells, build per-gene datasets, concatenate with gap filling, and write manifest/report files.
- Create: `modules/one_step_multigenephy_workflow.py`
  Hold tool adapters, ordered workflow runner, run-directory creation, and a Qt worker thread that emits progress/log/result signals.
- Create: `modules/one_step_multigenephy_tab.py`
  File-mode `BaseTabWidget` UI for import preview, options, run monitor, and artifact list.
- Modify: `main_window.py`
  Add `open_one_step_multigenephy_tab()` with the same single-instance reuse pattern used by other phylogeny tabs.
- Modify: `menus.py`
  Add `One Step MultiGenePhy` under `Phylogenetic Tree`.
- Create: `tests/test_one_step_multigenephy_workflow.py`
  Pure data and orchestration tests. No real NCBI or external tool execution.
- Create: `tests/test_one_step_multigenephy_tab.py`
  Tab rendering and mocked-run UI behavior.
- Modify: `tests/test_dna_analysis_tabs.py`
  Menu wiring and main-window single-instance regression coverage.

## Implementation Rules For This Plan

- Keep the first Excel row as the header row. Do not add a header toggle in v1.
- Treat only the selected strain column as metadata; all selected gene columns are biological inputs.
- Missing genes stay in scope and must be gap-filled during concatenation.
- A gene with fewer than 2 usable sequences is skipped with a warning, not a fatal run error.
- The overall run fails only if no valid concatenation remains or IQ-TREE fails on the final matrix.
- Use `resource_path(...)` for bundled executables instead of new `__file__`-relative path code.
- Keep long-running work off the UI thread.

### Task 1: Add Excel Dependency And Import/Data Models

**Files:**
- Modify: `requirements.txt`
- Create: `modules/one_step_multigenephy_models.py`
- Create: `modules/one_step_multigenephy_io.py`
- Test: `tests/test_one_step_multigenephy_workflow.py`

- [ ] **Step 1: Write the failing import/classification tests**

```python
import pandas as pd
import pytest

from modules.one_step_multigenephy_io import parse_excel_sheet


def test_parse_excel_sheet_classifies_mixed_cells(tmp_path):
    df = pd.DataFrame({
        "Strain": ["strain_a", "strain_b"],
        "ITS": ["ON123456.1", "ATGCGTAA"],
        "TEF1": ["", "not-a-sequence"],
    })
    excel_path = tmp_path / "multigene.xlsx"
    df.to_excel(excel_path, index=False)

    parsed = parse_excel_sheet(
        str(excel_path),
        sheet_name="Sheet1",
        strain_column="Strain",
        gene_columns=["ITS", "TEF1"],
    )

    by_key = {
        (cell.strain_name, cell.gene_name): cell.value_type for cell in parsed.cells
    }

    assert by_key[("strain_a", "ITS")] == "accession"
    assert by_key[("strain_b", "ITS")] == "sequence"
    assert by_key[("strain_a", "TEF1")] == "missing"
    assert by_key[("strain_b", "TEF1")] == "invalid"
    assert parsed.summary["strain_count"] == 2
    assert parsed.summary["gene_count"] == 2
    assert parsed.summary["invalid_count"] == 1


def test_parse_excel_sheet_rejects_duplicate_strain_names(tmp_path):
    df = pd.DataFrame({
        "Strain": ["dup", "dup"],
        "ITS": ["ON123456.1", "ATGCGTAA"],
    })
    excel_path = tmp_path / "duplicate.xlsx"
    df.to_excel(excel_path, index=False)

    with pytest.raises(ValueError, match="Duplicate strain names"):
        parse_excel_sheet(
            str(excel_path),
            sheet_name="Sheet1",
            strain_column="Strain",
            gene_columns=["ITS"],
        )
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `py -m pytest tests/test_one_step_multigenephy_workflow.py -k parse_excel_sheet -q`
Expected: `FAIL` with import errors because `modules.one_step_multigenephy_io` and its functions do not exist yet.

- [ ] **Step 3: Write the minimal dependency, dataclasses, and import parser**

`requirements.txt`

```text
PyQt6>=6.0.0
matplotlib>=3.5.0
numpy>=1.21.0
biopython>=1.79
scipy>=1.7.0
primer3-py>=1.3.2
pandas>=1.3.0
openpyxl>=3.1.0
logomaker>=0.8
phytreeviz>=0.3.0
```

`modules/one_step_multigenephy_models.py`

```python
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
```

`modules/one_step_multigenephy_io.py`

```python
import re

import pandas as pd

from modules.one_step_multigenephy_models import GeneCell, ParsedExcelSheet


_ACCESSION_RE = re.compile(r"^[A-Z]{1,4}_?\d+(?:\.\d+)?$", re.IGNORECASE)
_DNA_RE = re.compile(r"^[ACGTRYSWKMBDHVN-]+$", re.IGNORECASE)


def classify_cell_value(raw_value: object) -> tuple[str, str, str]:
    text = "" if raw_value is None else str(raw_value).strip()
    if not text:
        return "missing", "", ""
    if _ACCESSION_RE.match(text):
        return "accession", text, "public"
    if _DNA_RE.match(text):
        return "sequence", text.upper(), "private"
    return "invalid", text, ""


def parse_excel_sheet(
    excel_path: str,
    sheet_name: str,
    strain_column: str,
    gene_columns: list[str],
) -> ParsedExcelSheet:
    df = pd.read_excel(excel_path, sheet_name=sheet_name, header=0)
    if df.empty:
        raise ValueError("Excel sheet is empty")
    if strain_column not in df.columns:
        raise ValueError(f"Missing strain column: {strain_column}")
    if not gene_columns:
        raise ValueError("At least one gene column is required")

    strain_names = df[strain_column].fillna("").astype(str).str.strip().tolist()
    if any(not name for name in strain_names):
        raise ValueError("Blank strain names are not allowed")
    if len(set(strain_names)) != len(strain_names):
        raise ValueError("Duplicate strain names are not allowed")

    cells: list[GeneCell] = []
    summary = {
        "strain_count": len(strain_names),
        "gene_count": len(gene_columns),
        "accession_count": 0,
        "sequence_count": 0,
        "missing_count": 0,
        "invalid_count": 0,
    }

    for _, row in df.iterrows():
        strain_name = str(row[strain_column]).strip()
        for gene_name in gene_columns:
            value_type, payload, source = classify_cell_value(row.get(gene_name, ""))
            summary[f"{value_type}_count"] += 1
            cells.append(
                GeneCell(
                    strain_name=strain_name,
                    gene_name=gene_name,
                    raw_value=""
                    if pd.isna(row.get(gene_name, ""))
                    else str(row.get(gene_name, "")).strip(),
                    value_type=value_type,
                    accession=payload if value_type == "accession" else "",
                    normalized_sequence=payload if value_type == "sequence" else "",
                    source=source,
                )
            )

    usable_gene_count = sum(
        any(
            cell.gene_name == gene and cell.value_type in {"accession", "sequence"}
            for cell in cells
        )
        for gene in gene_columns
    )
    if usable_gene_count == 0:
        raise ValueError("No selected gene column contains usable values")

    return ParsedExcelSheet(strain_order=strain_names, cells=cells, summary=summary)


def read_excel_columns(excel_path: str, sheet_name: str) -> list[str]:
    df = pd.read_excel(excel_path, sheet_name=sheet_name, header=0, nrows=0)
    return [str(column) for column in df.columns]
```

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `py -m pytest tests/test_one_step_multigenephy_workflow.py -k parse_excel_sheet -q`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt modules/one_step_multigenephy_models.py modules/one_step_multigenephy_io.py tests/test_one_step_multigenephy_workflow.py
git commit -m "feat: add multigene phy excel import foundation"
```

### Task 2: Add Dataset Building, Gap-Fill Concatenation, And Reports

**Files:**
- Modify: `modules/one_step_multigenephy_models.py`
- Modify: `modules/one_step_multigenephy_io.py`
- Test: `tests/test_one_step_multigenephy_workflow.py`

- [ ] **Step 1: Write the failing dataset/concatenation/report tests**

```python
import json

from modules.one_step_multigenephy_io import (
    build_gene_datasets,
    concatenate_gene_alignments,
    write_run_manifest,
)
from modules.one_step_multigenephy_models import GeneCell


def test_concatenate_gene_alignments_gap_fills_missing_genes(tmp_path):
    cells = [
        GeneCell("strain_a", "ITS", "ON123", "sequence", normalized_sequence="AA"),
        GeneCell("strain_b", "ITS", "AT", "sequence", normalized_sequence="AT"),
        GeneCell("strain_a", "TEF1", "GG", "sequence", normalized_sequence="GG"),
        GeneCell("strain_b", "TEF1", "", "missing"),
    ]

    datasets = build_gene_datasets(cells, ["strain_a", "strain_b"])
    datasets["ITS"].trimmed_sequences = {"strain_a": "AA", "strain_b": "AT"}
    datasets["TEF1"].trimmed_sequences = {"strain_a": "GG"}

    concatenated, partitions = concatenate_gene_alignments(
        datasets,
        strain_order=["strain_a", "strain_b"],
    )

    assert concatenated["strain_a"] == "AAGG"
    assert concatenated["strain_b"] == "AT--"
    assert partitions == [("ITS", 1, 2), ("TEF1", 3, 4)]


def test_write_run_manifest_persists_stage_and_artifact_metadata(tmp_path):
    manifest_path = tmp_path / "run_manifest.json"

    write_run_manifest(
        manifest_path,
        {
            "summary": {"strain_count": 2},
            "steps": {"Import": "succeeded", "Build Tree": "warning"},
            "artifacts": {"treefile": "05_iqtree/final.treefile"},
        },
    )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["summary"]["strain_count"] == 2
    assert payload["steps"]["Build Tree"] == "warning"
    assert payload["artifacts"]["treefile"].endswith("final.treefile")
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `py -m pytest tests/test_one_step_multigenephy_workflow.py -k "concatenate_gene_alignments or write_run_manifest" -q`
Expected: `FAIL` because the helper functions and extra dataclass fields do not exist yet.

- [ ] **Step 3: Write the minimal dataset, concatenation, and reporting helpers**

`modules/one_step_multigenephy_models.py`

```python
from dataclasses import dataclass, field


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
    treefile_path: str = ""
    normalized_files: dict[str, str] = field(default_factory=dict)
    aligned_files: dict[str, str] = field(default_factory=dict)
    trimmed_files: dict[str, str] = field(default_factory=dict)
    extra_paths: dict[str, str] = field(default_factory=dict)
```

`modules/one_step_multigenephy_io.py`

```python
import json
from pathlib import Path

from modules.one_step_multigenephy_models import GeneDataset


def build_gene_datasets(cells, strain_order: list[str]) -> dict[str, GeneDataset]:
    datasets: dict[str, GeneDataset] = {}
    for cell in cells:
        dataset = datasets.setdefault(
            cell.gene_name,
            GeneDataset(gene_name=cell.gene_name, strain_order=list(strain_order)),
        )
        dataset.cells.append(cell)
        if cell.value_type == "invalid":
            dataset.invalid_cells.append(cell)
        elif cell.value_type == "missing":
            dataset.missing_strains.append(cell.strain_name)
        elif cell.normalized_sequence:
            dataset.normalized_sequences[cell.strain_name] = cell.normalized_sequence
    return datasets


def concatenate_gene_alignments(
    datasets: dict[str, GeneDataset],
    strain_order: list[str],
) -> tuple[dict[str, str], list[tuple[str, int, int]]]:
    concatenated = {strain: "" for strain in strain_order}
    partitions: list[tuple[str, int, int]] = []
    position = 1

    for gene_name, dataset in datasets.items():
        if not dataset.trimmed_sequences:
            continue
        gene_length = len(next(iter(dataset.trimmed_sequences.values())))
        start = position
        end = position + gene_length - 1
        partitions.append((gene_name, start, end))
        for strain in strain_order:
            concatenated[strain] += dataset.trimmed_sequences.get(
                strain, "-" * gene_length
            )
        position = end + 1

    return concatenated, partitions


def write_run_manifest(path: str | Path, payload: dict) -> None:
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `py -m pytest tests/test_one_step_multigenephy_workflow.py -k "concatenate_gene_alignments or write_run_manifest" -q`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add modules/one_step_multigenephy_models.py modules/one_step_multigenephy_io.py tests/test_one_step_multigenephy_workflow.py
git commit -m "feat: add multigene phy dataset and reporting helpers"
```

### Task 3: Add The Workflow Runner And Tool Adapter Seams

**Files:**
- Create: `modules/one_step_multigenephy_workflow.py`
- Modify: `modules/one_step_multigenephy_models.py`
- Modify: `modules/one_step_multigenephy_io.py`
- Test: `tests/test_one_step_multigenephy_workflow.py`

- [ ] **Step 1: Write the failing orchestration tests**

```python
from modules.one_step_multigenephy_models import GeneCell, ProjectInput
from modules.one_step_multigenephy_workflow import (
    OneStepMultiGenePhyRunner,
    ToolAdapters,
)


def test_runner_continues_when_one_gene_fails_alignment(tmp_path):
    project = ProjectInput(
        excel_path="input.xlsx",
        sheet_name="Sheet1",
        strain_column="Strain",
        gene_columns=["ITS", "TEF1"],
        output_dir=str(tmp_path / "run"),
        ncbi_email="user@example.com",
    )
    cells = [
        GeneCell("strain_a", "ITS", "ON123456.1", "accession", accession="ON123456.1"),
        GeneCell("strain_b", "ITS", "ATGT", "sequence", normalized_sequence="ATGT"),
        GeneCell("strain_a", "TEF1", "GGGG", "sequence", normalized_sequence="GGGG"),
        GeneCell("strain_b", "TEF1", "GGGA", "sequence", normalized_sequence="GGGA"),
    ]

    def fake_align(gene_name, sequences, output_dir, mode):
        if gene_name == "TEF1":
            raise RuntimeError("simulated MAFFT failure")
        return {name: seq for name, seq in sequences.items()}, str(
            tmp_path / f"{gene_name}.aln"
        )

    adapters = ToolAdapters(
        fetch_accession=lambda accession, email: "ATGC",
        run_alignment=fake_align,
        run_trimming=lambda gene_name, sequences, output_dir, mode: (
            sequences,
            str(tmp_path / f"{gene_name}.trimmed.fasta"),
        ),
        run_iqtree=lambda concat_path, partition_path, output_dir, bootstrap, threads: (
            str(tmp_path / "final.treefile")
        ),
    )

    runner = OneStepMultiGenePhyRunner(adapters=adapters)
    result = runner.run(project, cells, strain_order=["strain_a", "strain_b"])

    assert result.step_status["Align per Gene"] == "warning"
    assert "TEF1" in result.warnings
    assert result.artifacts.treefile_path.endswith("final.treefile")


def test_runner_fails_when_no_gene_reaches_concatenation(tmp_path):
    project = ProjectInput(
        excel_path="input.xlsx",
        sheet_name="Sheet1",
        strain_column="Strain",
        gene_columns=["ITS"],
        output_dir=str(tmp_path / "run"),
        ncbi_email="user@example.com",
    )
    cells = [
        GeneCell("strain_a", "ITS", "ATGC", "sequence", normalized_sequence="ATGC"),
    ]

    adapters = ToolAdapters(
        fetch_accession=lambda accession, email: "ATGC",
        run_alignment=lambda gene_name, sequences, output_dir, mode: (
            _ for _ in ()
        ).throw(RuntimeError("alignment failed")),
        run_trimming=lambda gene_name, sequences, output_dir, mode: (sequences, ""),
        run_iqtree=lambda concat_path, partition_path, output_dir, bootstrap, threads: (
            ""
        ),
    )

    runner = OneStepMultiGenePhyRunner(adapters=adapters)

    with pytest.raises(RuntimeError, match="No genes remain usable for concatenation"):
        runner.run(project, cells, strain_order=["strain_a"])
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `py -m pytest tests/test_one_step_multigenephy_workflow.py -k "runner_" -q`
Expected: `FAIL` because the runner, adapters, and result types do not exist yet.

- [ ] **Step 3: Write the minimal workflow runner and worker seam**

`modules/one_step_multigenephy_models.py`

```python
@dataclass(slots=True)
class WorkflowRunResult:
    step_status: dict[str, str]
    warnings: list[str]
    artifacts: RunArtifacts
```

`modules/one_step_multigenephy_workflow.py`

```python
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from modules.one_step_multigenephy_io import (
    build_gene_datasets,
    concatenate_gene_alignments,
    write_run_manifest,
)
from modules.one_step_multigenephy_models import RunArtifacts, WorkflowRunResult


@dataclass(slots=True)
class ToolAdapters:
    fetch_accession: callable
    run_alignment: callable
    run_trimming: callable
    run_iqtree: callable


class OneStepMultiGenePhyRunner:
    def __init__(self, adapters: ToolAdapters):
        self.adapters = adapters

    def run(self, project, cells, strain_order: list[str]) -> WorkflowRunResult:
        root = Path(project.output_dir)
        for name in [
            "00_import",
            "01_normalized",
            "02_alignments",
            "03_trimmed",
            "04_concat",
            "05_iqtree",
            "06_reports",
        ]:
            (root / name).mkdir(parents=True, exist_ok=True)

        datasets = build_gene_datasets(cells, strain_order)
        warnings: list[str] = []
        step_status = {
            "Import": "succeeded",
            "Fetch/Normalize": "succeeded",
            "Align per Gene": "succeeded",
            "Trim per Gene": "succeeded",
            "Concatenate": "succeeded",
            "Build Tree": "succeeded",
            "Summarize": "succeeded",
        }

        for dataset in datasets.values():
            for cell in dataset.cells:
                if cell.value_type == "accession":
                    try:
                        sequence = self.adapters.fetch_accession(
                            cell.accession, project.ncbi_email
                        )
                        cell.normalized_sequence = sequence
                        dataset.normalized_sequences[cell.strain_name] = sequence
                    except Exception as exc:
                        cell.status = "warning"
                        cell.message = str(exc)
                        warnings.append(
                            f"{dataset.gene_name}: failed to fetch {cell.accession}: {exc}"
                        )
                elif cell.value_type == "sequence" and cell.normalized_sequence:
                    dataset.normalized_sequences[cell.strain_name] = (
                        cell.normalized_sequence
                    )

        if any("failed to fetch" in warning for warning in warnings):
            step_status["Fetch/Normalize"] = "warning"

        for gene_name, dataset in datasets.items():
            usable = dataset.normalized_sequences
            if len(usable) < 2:
                warnings.append(
                    f"{gene_name}: skipped because fewer than 2 usable sequences remain"
                )
                dataset.status = "skipped"
                continue
            try:
                aligned, aligned_path = self.adapters.run_alignment(
                    gene_name,
                    usable,
                    str(root / "02_alignments"),
                    project.mafft_mode,
                )
                dataset.artifacts["aligned"] = aligned_path
                trimmed, trimmed_path = self.adapters.run_trimming(
                    gene_name,
                    aligned,
                    str(root / "03_trimmed"),
                    project.trimal_mode,
                )
                dataset.trimmed_sequences = trimmed
                dataset.artifacts["trimmed"] = trimmed_path
                dataset.status = "succeeded"
            except Exception as exc:
                warnings.append(f"{gene_name}: {exc}")
                dataset.status = "warning"

        if warnings:
            step_status["Align per Gene"] = "warning"
            step_status["Trim per Gene"] = "warning"

        concatenated, partitions = concatenate_gene_alignments(datasets, strain_order)
        if not partitions:
            raise RuntimeError("No genes remain usable for concatenation")

        concat_path = root / "04_concat" / "supermatrix.fasta"
        partition_path = root / "04_concat" / "partitions.nex"
        concat_path.write_text(
            "".join(f">{strain}\n{seq}\n" for strain, seq in concatenated.items()),
            encoding="utf-8",
        )
        partition_path.write_text(
            "\n".join(
                f"charset {gene} = {start}-{end};" for gene, start, end in partitions
            ),
            encoding="utf-8",
        )

        treefile_path = self.adapters.run_iqtree(
            str(concat_path),
            str(partition_path),
            str(root / "05_iqtree"),
            project.iqtree_bootstrap,
            project.threads,
        )

        artifacts = RunArtifacts(
            root_dir=str(root),
            treefile_path=treefile_path,
            manifest_path=str(root / "06_reports" / "run_manifest.json"),
            report_path=str(root / "06_reports" / "summary.txt"),
        )
        write_run_manifest(
            artifacts.manifest_path,
            {
                "steps": step_status,
                "warnings": warnings,
                "artifacts": {
                    "treefile": treefile_path,
                    "concat": str(concat_path),
                    "partitions": str(partition_path),
                },
            },
        )
        Path(artifacts.report_path).write_text(
            "\n".join(warnings) or "Run completed", encoding="utf-8"
        )
        return WorkflowRunResult(
            step_status=step_status, warnings=warnings, artifacts=artifacts
        )


class WorkflowWorker(QThread):
    step_changed = pyqtSignal(str, str)
    log_line = pyqtSignal(str)
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, runner, project, cells, strain_order):
        super().__init__()
        self.runner = runner
        self.project = project
        self.cells = cells
        self.strain_order = strain_order

    def run(self):
        try:
            result = self.runner.run(self.project, self.cells, self.strain_order)
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
```

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `py -m pytest tests/test_one_step_multigenephy_workflow.py -k "runner_" -q`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add modules/one_step_multigenephy_models.py modules/one_step_multigenephy_io.py modules/one_step_multigenephy_workflow.py tests/test_one_step_multigenephy_workflow.py
git commit -m "feat: add multigene phy workflow runner"
```

### Task 4: Add The Workflow Tab UI And Mocked-Run Rendering

**Files:**
- Create: `modules/one_step_multigenephy_tab.py`
- Create: `tests/test_one_step_multigenephy_tab.py`

- [ ] **Step 1: Write the failing tab behavior tests**

```python
from types import SimpleNamespace

from modules.one_step_multigenephy_tab import OneStepMultiGenePhyTab


def test_tab_renders_import_summary(qapp):
    tab = OneStepMultiGenePhyTab()
    tab._populate_gene_columns(["ITS", "TEF1", "RPB2"])

    tab._render_import_summary({
        "strain_count": 2,
        "gene_count": 3,
        "accession_count": 4,
        "sequence_count": 2,
        "missing_count": 1,
        "invalid_count": 0,
    })

    text = tab.summary_view.toPlainText()
    assert "Strains: 2" in text
    assert "Genes: 3" in text
    assert "Accessions: 4" in text
    assert [tab.gene_list.item(i).text() for i in range(tab.gene_list.count())] == [
        "ITS",
        "TEF1",
        "RPB2",
    ]


def test_tab_loads_gene_columns_from_excel_header(qapp, monkeypatch):
    tab = OneStepMultiGenePhyTab()

    monkeypatch.setattr(
        "modules.one_step_multigenephy_tab.read_excel_columns",
        lambda excel_path, sheet_name: ["Strain", "ITS", "TEF1", "RPB2"],
    )

    tab.excel_path_edit.setText("F:/input.xlsx")
    tab.sheet_name_edit.setText("Sheet1")
    tab.strain_column_edit.setText("Strain")
    tab.load_sheet_columns()

    assert tab.gene_columns == ["ITS", "TEF1", "RPB2"]


def test_tab_updates_status_log_and_artifacts_after_mocked_run(qapp):
    tab = OneStepMultiGenePhyTab()

    tab._handle_step_update("Align per Gene", "running")
    tab._append_log("ITS aligned successfully")
    tab._handle_run_completed(
        SimpleNamespace(
            step_status={"Align per Gene": "warning", "Build Tree": "succeeded"},
            warnings=["TEF1 skipped because fewer than 2 usable sequences remain"],
            artifacts=SimpleNamespace(
                treefile_path="F:/run/05_iqtree/final.treefile",
                manifest_path="F:/run/06_reports/run_manifest.json",
                report_path="F:/run/06_reports/summary.txt",
            ),
        )
    )

    assert tab.status_label.text() == "Completed with warnings"
    assert "ITS aligned successfully" in tab.log_area.toPlainText()
    assert tab.artifact_list.count() == 3
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `py -m pytest tests/test_one_step_multigenephy_tab.py -q`
Expected: `FAIL` because the tab module and helper methods do not exist yet.

- [ ] **Step 3: Write the minimal file-mode tab UI**

`modules/one_step_multigenephy_tab.py`

```python
from PyQt6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from modules.one_step_multigenephy_io import read_excel_columns
from modules.one_step_multigenephy_workflow import WorkflowWorker
from utils.common_components import BaseTabWidget


class OneStepMultiGenePhyTab(BaseTabWidget):
    def __init__(self, status_callback=None):
        super().__init__("One Step MultiGenePhy", "file")
        self._status_callback = status_callback
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        input_group = QGroupBox(self.tr("Input"))
        input_form = QFormLayout(input_group)
        self.excel_path_edit = QLineEdit()
        self.sheet_name_edit = QLineEdit("Sheet1")
        self.strain_column_edit = QLineEdit("Strain")
        self.email_edit = QLineEdit()
        self.output_dir_edit = QLineEdit()
        self.summary_view = QTextEdit()
        self.summary_view.setReadOnly(True)
        self.gene_list = QListWidget()
        self.gene_columns: list[str] = []
        browse_excel_btn = QPushButton(self.tr("Browse"))
        preview_btn = QPushButton(self.tr("Preview Columns"))
        browse_output_btn = QPushButton(self.tr("Browse"))
        browse_excel_btn.clicked.connect(self._choose_excel)
        preview_btn.clicked.connect(self.load_sheet_columns)
        browse_output_btn.clicked.connect(self._choose_output_dir)

        excel_row = QHBoxLayout()
        excel_row.addWidget(self.excel_path_edit)
        excel_row.addWidget(browse_excel_btn)
        excel_row.addWidget(preview_btn)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_dir_edit)
        output_row.addWidget(browse_output_btn)

        input_form.addRow(self.tr("Excel file:"), excel_row)
        input_form.addRow(self.tr("Sheet:"), self.sheet_name_edit)
        input_form.addRow(self.tr("Strain column:"), self.strain_column_edit)
        input_form.addRow(self.tr("NCBI email:"), self.email_edit)
        input_form.addRow(self.tr("Gene columns:"), self.gene_list)
        input_form.addRow(self.tr("Output directory:"), output_row)
        input_form.addRow(self.tr("Import summary:"), self.summary_view)

        run_group = QGroupBox(self.tr("Run Monitor"))
        run_layout = QVBoxLayout(run_group)
        self.step_summary = QLabel(
            self.tr(
                "Import -> Fetch/Normalize -> Align per Gene -> Trim per Gene -> Concatenate -> Build Tree -> Summarize"
            )
        )
        self.artifact_list = QListWidget()
        self.run_btn = QPushButton(self.tr("Run Workflow"))
        self.run_btn.clicked.connect(self.start_run)
        run_layout.addWidget(self.step_summary)
        run_layout.addWidget(self.artifact_list)
        run_layout.addWidget(self.run_btn)

        self.add_content_widget(input_group)
        self.add_content_widget(run_group)
        self.content_area.addStretch()

    def add_content_widget(self, widget):
        self.content_area.addWidget(widget)

    def _choose_excel(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Select Excel file"), "", "Excel Files (*.xlsx *.xls)"
        )
        if path:
            self.excel_path_edit.setText(path)

    def load_sheet_columns(self):
        columns = read_excel_columns(
            self.excel_path_edit.text().strip(),
            self.sheet_name_edit.text().strip() or "Sheet1",
        )
        strain_column = self.strain_column_edit.text().strip()
        self._populate_gene_columns([
            column for column in columns if column != strain_column
        ])

    def _choose_output_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, self.tr("Select output directory"), ""
        )
        if path:
            self.output_dir_edit.setText(path)

    def _populate_gene_columns(self, gene_names: list[str]):
        self.gene_list.clear()
        self.gene_columns = list(gene_names)
        for gene_name in gene_names:
            self.gene_list.addItem(QListWidgetItem(gene_name))

    def _render_import_summary(self, summary: dict[str, int]):
        self.summary_view.setPlainText(
            "\n".join([
                f"Strains: {summary['strain_count']}",
                f"Genes: {summary['gene_count']}",
                f"Accessions: {summary['accession_count']}",
                f"Raw sequences: {summary['sequence_count']}",
                f"Missing: {summary['missing_count']}",
                f"Invalid: {summary['invalid_count']}",
            ])
        )

    def _handle_step_update(self, step_name: str, status: str):
        self.status_label.setText(f"{step_name}: {status}")
        if self._status_callback:
            self._status_callback(f"{step_name}: {status}")

    def _append_log(self, line: str):
        self.log_message(line)

    def _handle_run_completed(self, result):
        self.artifact_list.clear()
        for value in [
            result.artifacts.treefile_path,
            result.artifacts.manifest_path,
            result.artifacts.report_path,
        ]:
            if value:
                self.artifact_list.addItem(value)
        self.status_label.setText(
            self.tr("Completed with warnings")
            if result.warnings
            else self.tr("Completed")
        )
        for warning in result.warnings:
            self.log_message(warning, "WARNING")

    def start_run(self):
        self.log_message("Workflow start requested")
```

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `py -m pytest tests/test_one_step_multigenephy_tab.py -q`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add modules/one_step_multigenephy_tab.py tests/test_one_step_multigenephy_tab.py
git commit -m "feat: add multigene phy workflow tab"
```

### Task 5: Wire The Menu And Main Window Entry Points

**Files:**
- Modify: `menus.py`
- Modify: `main_window.py`
- Modify: `tests/test_dna_analysis_tabs.py`

- [ ] **Step 1: Write the failing menu/main-window regression tests**

```python
from modules.one_step_multigenephy_tab import OneStepMultiGenePhyTab


def test_main_window_reuses_one_step_multigenephy_tab(qapp):
    window = MainWindow()

    window.open_one_step_multigenephy_tab()
    first_tab = window.tabs.currentWidget()
    window.open_one_step_multigenephy_tab()

    assert window.tabs.count() == 1
    assert window.tabs.currentWidget() is first_tab
    assert isinstance(first_tab, OneStepMultiGenePhyTab)
    assert window.tabs.tabText(window.tabs.currentIndex()) == "One Step MultiGenePhy"
    assert first_tab.email_edit is not None


def test_phylogenetic_tree_menu_includes_one_step_multigenephy(qapp):
    window = MainWindow()
    menu_bar = window.menuBar()
    phylo_menu = next(
        action.menu()
        for action in menu_bar.actions()
        if action.text() == "Phylogenetic Tree"
    )
    action_texts = [action.text() for action in phylo_menu.actions() if action.text()]

    assert "One Step MultiGenePhy" in action_texts
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `py -m pytest tests/test_dna_analysis_tabs.py -k "one_step_multigenephy" -q`
Expected: `FAIL` because `MainWindow` and `menus.py` do not yet expose the new tab.

- [ ] **Step 3: Write the minimal menu and `MainWindow` wiring**

`main_window.py`

```python
def open_one_step_multigenephy_tab(self):
    from modules.one_step_multigenephy_tab import OneStepMultiGenePhyTab

    for i in range(self.tabs.count()):
        if isinstance(self.tabs.widget(i), OneStepMultiGenePhyTab):
            self.tabs.setCurrentIndex(i)
            return

    tab = OneStepMultiGenePhyTab(status_callback=self.status.showMessage)
    self.tabs.addTab(tab, self.tr("One Step MultiGenePhy"))
    self.tabs.setCurrentWidget(tab)
```

`menus.py`

```python
one_step_multigenephy_action = QAction(window.tr("One Step MultiGenePhy"), window)
one_step_multigenephy_action.triggered.connect(window.open_one_step_multigenephy_tab)
evolution_menu.addAction(one_step_multigenephy_action)
```

- [ ] **Step 4: Run the focused regression tests to verify they pass**

Run: `py -m pytest tests/test_dna_analysis_tabs.py -k "one_step_multigenephy" -q`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add menus.py main_window.py tests/test_dna_analysis_tabs.py
git commit -m "feat: wire multigene phy workflow into phylogenetic tree menu"
```

### Task 6: Connect The Tab To Real Workflow Calls And Run Focused Regression

**Files:**
- Modify: `modules/one_step_multigenephy_tab.py`
- Modify: `modules/one_step_multigenephy_workflow.py`
- Modify: `tests/test_one_step_multigenephy_tab.py`
- Modify: `tests/test_one_step_multigenephy_workflow.py`

- [ ] **Step 1: Write the failing integration-at-the-seam tests**

```python
def test_tab_start_run_parses_excel_and_starts_worker(qapp, monkeypatch, tmp_path):
    started = {}

    class FakeWorker:
        def __init__(self, runner, project, cells, strain_order):
            started["project"] = project
            started["cells"] = cells
            started["strain_order"] = strain_order

        def start(self):
            started["called"] = True

    monkeypatch.setattr("modules.one_step_multigenephy_tab.WorkflowWorker", FakeWorker)
    monkeypatch.setattr(
        "modules.one_step_multigenephy_tab.parse_excel_sheet",
        lambda excel_path, sheet_name, strain_column, gene_columns: SimpleNamespace(
            strain_order=["strain_a", "strain_b"],
            cells=[],
            summary={
                "strain_count": 2,
                "gene_count": 2,
                "accession_count": 1,
                "sequence_count": 1,
                "missing_count": 0,
                "invalid_count": 0,
            },
        ),
    )

    tab = OneStepMultiGenePhyTab()
    tab.excel_path_edit.setText(str(tmp_path / "input.xlsx"))
    tab.sheet_name_edit.setText("Sheet1")
    tab.strain_column_edit.setText("Strain")
    tab.email_edit.setText("user@example.com")
    tab.output_dir_edit.setText(str(tmp_path / "output"))
    tab.gene_columns = ["ITS", "TEF1"]

    tab.start_run()

    assert started["called"] is True
    assert started["project"].gene_columns == ["ITS", "TEF1"]
    assert tab.summary_view.toPlainText().startswith("Strains: 2")
```

- [ ] **Step 2: Run the seam test to verify it fails**

Run: `py -m pytest tests/test_one_step_multigenephy_tab.py -k start_run -q`
Expected: `FAIL` because `start_run()` currently only logs and does not parse input or construct a worker.

- [ ] **Step 3: Write the minimal end-to-end tab-to-runner connection**

`modules/one_step_multigenephy_tab.py`

```python
from modules.one_step_multigenephy_io import parse_excel_sheet
from modules.one_step_multigenephy_models import ProjectInput
from modules.one_step_multigenephy_workflow import (
    OneStepMultiGenePhyRunner,
    ToolAdapters,
    WorkflowWorker,
    build_default_tool_adapters,
)


def start_run(self):
    parsed = parse_excel_sheet(
        self.excel_path_edit.text().strip(),
        sheet_name=self.sheet_name_edit.text().strip() or "Sheet1",
        strain_column=self.strain_column_edit.text().strip(),
        gene_columns=self.gene_columns,
    )
    self._render_import_summary(parsed.summary)
    project = ProjectInput(
        excel_path=self.excel_path_edit.text().strip(),
        sheet_name=self.sheet_name_edit.text().strip() or "Sheet1",
        strain_column=self.strain_column_edit.text().strip(),
        gene_columns=self.gene_columns,
        output_dir=self.output_dir_edit.text().strip(),
        ncbi_email=self.email_edit.text().strip(),
    )
    runner = OneStepMultiGenePhyRunner(adapters=build_default_tool_adapters())
    self._worker = WorkflowWorker(runner, project, parsed.cells, parsed.strain_order)
    self._worker.completed.connect(self._handle_run_completed)
    self._worker.failed.connect(lambda message: self.log_message(message, "ERROR"))
    self._worker.start()
```

`modules/one_step_multigenephy_workflow.py`

```python
import subprocess
from Bio import Entrez

from utils.app_paths import resource_path


def build_default_tool_adapters() -> ToolAdapters:
    mafft_exe = resource_path("softwares", "mafft-win", "mafft.bat")
    trimal_exe = resource_path("softwares", "trimAl_Windows_x86-64", "trimal.exe")
    iqtree_exe = resource_path(
        "softwares", "iqtree-3.0.1-Windows", "bin", "iqtree3.exe"
    )

    def read_fasta_map(path: str) -> dict[str, str]:
        records: dict[str, str] = {}
        current_name = ""
        current_lines: list[str] = []
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.startswith(">"):
                if current_name:
                    records[current_name] = "".join(current_lines)
                current_name = line[1:].strip()
                current_lines = []
            else:
                current_lines.append(line.strip())
        if current_name:
            records[current_name] = "".join(current_lines)
        return records

    def fetch_accession(accession: str, email: str) -> str:
        Entrez.email = email
        with Entrez.efetch(
            db="nucleotide", id=accession, rettype="fasta", retmode="text"
        ) as handle:
            fasta = handle.read()
        return "".join(
            line.strip() for line in fasta.splitlines() if not line.startswith(">")
        )

    def run_alignment(
        gene_name: str, sequences: dict[str, str], output_dir: str, mode: str
    ):
        input_path = Path(output_dir) / f"{gene_name}.input.fasta"
        out_path = Path(output_dir) / f"{gene_name}.aligned.fasta"
        input_path.write_text(
            "".join(f">{name}\n{seq}\n" for name, seq in sequences.items()),
            encoding="utf-8",
        )
        result = subprocess.run(
            [mafft_exe, mode, str(input_path)],
            check=True,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        out_path.write_text(result.stdout, encoding="utf-8")
        return read_fasta_map(str(out_path)), str(out_path)

    def run_trimming(
        gene_name: str, sequences: dict[str, str], output_dir: str, mode: str
    ):
        input_path = Path(output_dir) / f"{gene_name}.aligned.fasta"
        out_path = Path(output_dir) / f"{gene_name}.trimmed.fasta"
        subprocess.run(
            [
                trimal_exe,
                f"-{mode}",
                "-in",
                str(input_path),
                "-out",
                str(out_path),
                "-fasta",
            ],
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return read_fasta_map(str(out_path)), str(out_path)

    def run_iqtree(
        concat_path: str,
        partition_path: str,
        output_dir: str,
        bootstrap: int,
        threads: str,
    ):
        prefix = str(Path(output_dir) / "multigene")
        subprocess.run(
            [
                iqtree_exe,
                "-s",
                concat_path,
                "-p",
                partition_path,
                "-B",
                str(bootstrap),
                "-T",
                str(threads),
                "--prefix",
                prefix,
            ],
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return prefix + ".treefile"

    return ToolAdapters(
        fetch_accession=fetch_accession,
        run_alignment=run_alignment,
        run_trimming=run_trimming,
        run_iqtree=run_iqtree,
    )
```

- [ ] **Step 4: Run the full focused regression slice**

Run: `py -m pytest tests/test_one_step_multigenephy_workflow.py tests/test_one_step_multigenephy_tab.py tests/test_dna_analysis_tabs.py -k "one_step_multigenephy or parse_excel_sheet or runner_" -q`
Expected: all targeted tests pass.

- [ ] **Step 5: Commit**

```bash
git add modules/one_step_multigenephy_tab.py modules/one_step_multigenephy_workflow.py tests/test_one_step_multigenephy_tab.py tests/test_one_step_multigenephy_workflow.py tests/test_dna_analysis_tabs.py
git commit -m "feat: connect multigene phy tab to workflow runner"
```

## Final Verification After Task 6

Run these before opening a PR or handing the branch back:

```bash
py -m pytest tests/test_one_step_multigenephy_workflow.py -q
py -m pytest tests/test_one_step_multigenephy_tab.py -q
py -m pytest tests/test_dna_analysis_tabs.py -k "one_step_multigenephy" -q
py -m pytest tests/test_dna_analysis_tabs.py -q
python main.py
```

Expected:

- the new targeted workflow tests pass
- the existing DNA analysis/window wiring suite still passes
- the app starts and the `Phylogenetic Tree` menu shows `One Step MultiGenePhy`

## Self-Review Notes

- Spec coverage checked: menu entry, single-instance tab, mixed Excel import, missing-gene gap fill, per-gene warning isolation, output manifest/report, and focused testing are all mapped to Tasks 1 through 6.
- Placeholder scan checked: no `TODO`, `TBD`, or cross-task "same as above" shortcuts remain.
- Type consistency checked: `ProjectInput`, `GeneCell`, `GeneDataset`, `RunArtifacts`, `WorkflowRunResult`, `ToolAdapters`, `OneStepMultiGenePhyRunner`, and `WorkflowWorker` are introduced before later tasks use them.