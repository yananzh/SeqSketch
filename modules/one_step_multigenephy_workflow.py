from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QThread, pyqtSignal

from modules.one_step_multigenephy_io import (
    build_gene_datasets,
    concatenate_gene_alignments,
    write_run_manifest,
)
from modules.one_step_multigenephy_models import RunArtifacts, WorkflowRunResult


def _ordered_sequences(
    sequences: dict[str, str],
    strain_order: list[str],
) -> dict[str, str]:
    return {
        strain_name: sequences[strain_name]
        for strain_name in strain_order
        if strain_name in sequences and sequences[strain_name]
    }


def _write_fasta(
    path: Path,
    sequences: dict[str, str],
    strain_order: list[str],
) -> None:
    ordered = _ordered_sequences(sequences, strain_order)
    content = "".join(
        f">{strain_name}\n{sequence}\n"
        for strain_name, sequence in ordered.items()
    )
    path.write_text(content, encoding="utf-8")


def _write_partitions(
    path: Path,
    partitions: list[tuple[str, int, int]],
) -> None:
    lines = ["#nexus", "begin sets;"]
    lines.extend(
        f"  charset {gene_name} = {start}-{end};"
        for gene_name, start, end in partitions
    )
    lines.append("end;")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_summary(
    path: Path | str,
    step_status: dict[str, str],
    warnings: list[str],
    artifacts: RunArtifacts,
) -> None:
    lines = ["One Step MultiGenePhy Summary", "", "Steps:"]
    lines.extend(f"- {step}: {status}" for step, status in step_status.items())
    lines.append("")
    lines.append("Warnings:")
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- none")
    lines.append("")
    lines.append("Artifacts:")
    lines.append(f"- treefile: {artifacts.treefile_path or 'not generated'}")
    lines.append(f"- manifest: {artifacts.manifest_path}")
    lines.append(f"- report: {artifacts.report_path}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


@dataclass(slots=True)
class ToolAdapters:
    fetch_accession: Callable[[str, str], str]
    run_alignment: Callable[[str, dict[str, str], str, str], tuple[dict[str, str], str]]
    run_trimming: Callable[[str, dict[str, str], str, str], tuple[dict[str, str], str]]
    run_iqtree: Callable[[str, str, str, int, str], str]


class OneStepMultiGenePhyRunner:
    def __init__(self, adapters: ToolAdapters):
        self.adapters = adapters

    def run(self, project, cells, strain_order: list[str]) -> WorkflowRunResult:
        root_dir = Path(project.output_dir)
        stage_dirs = {
            "import": root_dir / "00_import",
            "normalized": root_dir / "01_normalized",
            "alignments": root_dir / "02_alignments",
            "trimmed": root_dir / "03_trimmed",
            "concat": root_dir / "04_concat",
            "iqtree": root_dir / "05_iqtree",
            "reports": root_dir / "06_reports",
        }
        for directory in stage_dirs.values():
            directory.mkdir(parents=True, exist_ok=True)

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
        artifacts = RunArtifacts(
            root_dir=str(root_dir),
            manifest_path=str(stage_dirs["reports"] / "run_manifest.json"),
            report_path=str(stage_dirs["reports"] / "summary.txt"),
        )

        fetch_warning = False
        for dataset in datasets.values():
            for cell in dataset.cells:
                if cell.value_type == "accession" and cell.accession:
                    try:
                        sequence = self.adapters.fetch_accession(
                            cell.accession,
                            project.ncbi_email,
                        ).strip().upper()
                    except Exception as exc:
                        fetch_warning = True
                        cell.status = "warning"
                        cell.message = str(exc)
                        warnings.append(
                            f"{dataset.gene_name}: failed to fetch {cell.accession}: {exc}"
                        )
                        continue

                    cell.normalized_sequence = sequence
                    dataset.normalized_sequences[cell.strain_name] = sequence
                    cell.status = "succeeded"
                elif cell.value_type == "sequence" and cell.normalized_sequence:
                    normalized = cell.normalized_sequence.strip().upper()
                    cell.normalized_sequence = normalized
                    dataset.normalized_sequences[cell.strain_name] = normalized
                    cell.status = "succeeded"

            if dataset.normalized_sequences:
                normalized_path = stage_dirs["normalized"] / f"{dataset.gene_name}.fasta"
                _write_fasta(normalized_path, dataset.normalized_sequences, strain_order)
                dataset.artifacts["normalized"] = str(normalized_path)
                artifacts.normalized_files[dataset.gene_name] = str(normalized_path)

        if fetch_warning:
            step_status["Fetch/Normalize"] = "warning"

        alignment_warning = False
        trimming_warning = False
        for dataset in datasets.values():
            usable_sequences = _ordered_sequences(dataset.normalized_sequences, strain_order)
            if len(usable_sequences) < 2:
                alignment_warning = True
                dataset.status = "warning"
                warnings.append(
                    f"{dataset.gene_name}: skipped because fewer than 2 usable sequences remain"
                )
                continue

            try:
                aligned_sequences, aligned_path = self.adapters.run_alignment(
                    dataset.gene_name,
                    usable_sequences,
                    str(stage_dirs["alignments"]),
                    project.mafft_mode,
                )
            except Exception as exc:
                alignment_warning = True
                dataset.status = "warning"
                warnings.append(f"{dataset.gene_name}: {exc}")
                continue

            dataset.artifacts["aligned"] = aligned_path
            artifacts.aligned_files[dataset.gene_name] = aligned_path

            try:
                trimmed_sequences, trimmed_path = self.adapters.run_trimming(
                    dataset.gene_name,
                    _ordered_sequences(aligned_sequences, strain_order),
                    str(stage_dirs["trimmed"]),
                    project.trimal_mode,
                )
            except Exception as exc:
                trimming_warning = True
                dataset.status = "warning"
                warnings.append(f"{dataset.gene_name}: {exc}")
                continue

            dataset.trimmed_sequences = _ordered_sequences(trimmed_sequences, strain_order)
            dataset.artifacts["trimmed"] = trimmed_path
            artifacts.trimmed_files[dataset.gene_name] = trimmed_path
            dataset.status = "succeeded"

        if alignment_warning:
            step_status["Align per Gene"] = "warning"
        if trimming_warning:
            step_status["Trim per Gene"] = "warning"

        concatenated, partitions = concatenate_gene_alignments(datasets, strain_order)
        if not partitions:
            step_status["Concatenate"] = "failed"
            raise RuntimeError("No genes remain usable for concatenation")

        concat_path = stage_dirs["concat"] / "supermatrix.fasta"
        partition_path = stage_dirs["concat"] / "partitions.nex"
        _write_fasta(concat_path, concatenated, strain_order)
        _write_partitions(partition_path, partitions)
        artifacts.extra_paths["supermatrix"] = str(concat_path)
        artifacts.extra_paths["partitions"] = str(partition_path)

        treefile_path = self.adapters.run_iqtree(
            str(concat_path),
            str(partition_path),
            str(stage_dirs["iqtree"]),
            project.iqtree_bootstrap,
            project.threads,
        )
        artifacts.treefile_path = treefile_path
        artifacts.extra_paths["iqtree_dir"] = str(stage_dirs["iqtree"])

        write_run_manifest(
            artifacts.manifest_path,
            {
                "steps": step_status,
                "warnings": warnings,
                "artifacts": {
                    "normalized": artifacts.normalized_files,
                    "aligned": artifacts.aligned_files,
                    "trimmed": artifacts.trimmed_files,
                    "supermatrix": str(concat_path),
                    "partitions": str(partition_path),
                    "treefile": treefile_path,
                },
            },
        )
        _write_summary(artifacts.report_path, step_status, warnings, artifacts)

        return WorkflowRunResult(
            step_status=step_status,
            warnings=warnings,
            artifacts=artifacts,
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

    def run(self) -> None:
        try:
            result = self.runner.run(self.project, self.cells, self.strain_order)
        except Exception as exc:
            self.failed.emit(str(exc))
            return

        self.completed.emit(result)