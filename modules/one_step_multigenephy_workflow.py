from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QThread, pyqtSignal

try:
    from Bio import Entrez
except ImportError:  # pragma: no cover - dependency is expected in normal runs
    Entrez = None

from modules.one_step_multigenephy_io import (
    build_gene_datasets,
    concatenate_gene_alignments,
    write_run_manifest,
)
from modules.one_step_multigenephy_models import RunArtifacts, WorkflowRunResult
from utils.app_paths import resource_path, tool_path_from_config


def _creation_flags() -> int:
    if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        return subprocess.CREATE_NO_WINDOW
    return 0


def _parse_fasta_text(text: str) -> dict[str, str]:
    sequences: dict[str, str] = {}
    header: str | None = None
    chunks: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if header is not None:
                sequences[header] = "".join(chunks).upper()
            header = line[1:].strip().split()[0] or f"seq{len(sequences) + 1}"
            chunks = []
            continue
        chunks.append(line)

    if header is not None:
        sequences[header] = "".join(chunks).upper()

    return sequences


def _read_fasta_file(path: Path) -> dict[str, str]:
    return _parse_fasta_text(path.read_text(encoding="utf-8"))


def _mafft_executable() -> str:
    configured = tool_path_from_config("MAFFT", "bin_dir")
    if configured:
        for name in ("mafft.bat", "mafft-signed.ps1"):
            candidate = os.path.join(configured, name)
            if os.path.isfile(candidate):
                return candidate
    for name in ("mafft.bat", "mafft-signed.ps1"):
        candidate = resource_path("softwares", "mafft-win_v7.526", name)
        if os.path.isfile(candidate):
            return candidate
    return resource_path("softwares", "mafft-win_v7.526", "mafft.bat")


def _trimal_executable() -> str:
    configured = tool_path_from_config("TrimAl", "bin_dir")
    if configured:
        exe = os.path.join(configured, "trimal.exe")
        if os.path.isfile(exe):
            return exe
    return resource_path("softwares", "trimAl_Windows_v1.5.1", "trimal.exe")


def _iqtree_executable() -> str:
    configured = tool_path_from_config("IQTree", "bin_dir")
    if configured:
        exe = os.path.join(configured, "iqtree3.exe")
        if os.path.isfile(exe):
            return exe
    return resource_path("softwares", "iqtree-3.0.1-Windows", "bin", "iqtree3.exe")


def _ensure_executable(path: str, tool_name: str) -> None:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"{tool_name} executable not found: {path}")


def _run_command(cmd: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_creation_flags(),
        cwd=cwd,
    )
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(details or f"Command failed with exit code {result.returncode}")
    return result


def _write_sequences_file(path: Path, sequences: dict[str, str]) -> None:
    content = "".join(
        f">{strain_name}\n{sequence}\n" for strain_name, sequence in sequences.items()
    )
    path.write_text(content, encoding="utf-8")


def build_default_tool_adapters(
    commands: list[str] | None = None,
) -> ToolAdapters:
    if commands is None:
        commands = []
    import time

    def _track(cmd_parts: list[str]) -> None:
        commands.append(" ".join(cmd_parts))

    def fetch_accession(accession: str, email: str) -> str:
        if Entrez is None:
            raise RuntimeError("Biopython Entrez is not available")
        if not email:
            raise ValueError("NCBI email is required to fetch accession sequences")

        Entrez.email = email
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with Entrez.efetch(
                    db="nucleotide",
                    id=accession,
                    rettype="fasta",
                    retmode="text",
                ) as handle:
                    sequences = _parse_fasta_text(handle.read())

                if not sequences:
                    raise RuntimeError(f"No FASTA sequence returned for {accession}")
                return next(iter(sequences.values()))
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    delay = (2**attempt) * 0.5
                    time.sleep(delay)
        raise last_error  # type: ignore[misc]

    def run_alignment(
        gene_name: str,
        sequences: dict[str, str],
        output_dir: str,
        mode: str,
    ) -> tuple[dict[str, str], str]:
        mafft_exe = _mafft_executable()
        _ensure_executable(mafft_exe, "MAFFT")

        stage_dir = Path(output_dir)
        stage_dir.mkdir(parents=True, exist_ok=True)
        input_path = stage_dir / f"{gene_name}.input.fasta"
        output_path = stage_dir / f"{gene_name}.aligned.fasta"
        _write_sequences_file(input_path, sequences)

        cmd = [mafft_exe]
        mode_tokens = (mode or "--auto").split()
        cmd.extend(mode_tokens or ["--auto"])
        cmd.extend(["--thread", "1", str(input_path)])

        _track(cmd)
        result = _run_command(cmd)
        aligned_text = (result.stdout or "").strip()
        if not aligned_text:
            raise RuntimeError("MAFFT produced no alignment output")

        aligned_sequences = _parse_fasta_text(aligned_text)
        if not aligned_sequences:
            raise RuntimeError("MAFFT output could not be parsed as FASTA")

        _write_sequences_file(
            output_path,
            _ordered_sequences(aligned_sequences, list(sequences)),
        )
        return aligned_sequences, str(output_path)

    def run_trimming(
        gene_name: str,
        sequences: dict[str, str],
        output_dir: str,
        mode: str,
    ) -> tuple[dict[str, str], str]:
        trimal_exe = _trimal_executable()
        _ensure_executable(trimal_exe, "trimAl")

        stage_dir = Path(output_dir)
        stage_dir.mkdir(parents=True, exist_ok=True)
        input_path = stage_dir / f"{gene_name}.aligned.fasta"
        output_path = stage_dir / f"{gene_name}.trimmed.fasta"
        _write_sequences_file(input_path, sequences)

        cmd = [trimal_exe, "-in", str(input_path), "-out", str(output_path)]
        normalized_mode = (mode or "automated1").strip()
        if normalized_mode:
            if normalized_mode.startswith("-"):
                cmd.extend(normalized_mode.split())
            else:
                cmd.append(f"-{normalized_mode}")

        _track(cmd)
        _run_command(cmd)

        if not output_path.is_file():
            raise RuntimeError("trimAl did not produce an output FASTA")

        trimmed_sequences = _read_fasta_file(output_path)
        return trimmed_sequences, str(output_path)

    def run_iqtree(
        concat_path: str,
        partition_path: str,
        output_dir: str,
        bootstrap: int,
        threads: str,
        bootstrap_mode: str = "ufboot",
    ) -> str:
        iqtree_exe = _iqtree_executable()
        _ensure_executable(iqtree_exe, "IQ-TREE")

        stage_dir = Path(output_dir)
        stage_dir.mkdir(parents=True, exist_ok=True)
        prefix = stage_dir / "final"
        cmd = [
            iqtree_exe,
            "-s",
            concat_path,
            "-p",
            partition_path,
            "-T",
            str(threads),
            "--prefix",
            str(prefix),
            "-redo",
        ]
        if bootstrap:
            if bootstrap_mode == "standard":
                cmd.extend(["-b", str(bootstrap)])
            elif bootstrap_mode == "ufboot_shalrt":
                cmd.extend(["-B", str(bootstrap), "-alrt", str(bootstrap)])
            else:
                cmd.extend(["-B", str(bootstrap)])

        _track(cmd)
        _run_command(cmd, cwd=str(stage_dir))

        treefile_path = Path(f"{prefix}.treefile")
        if not treefile_path.is_file():
            raise RuntimeError("IQ-TREE did not produce a treefile")
        return str(treefile_path)

    return ToolAdapters(
        fetch_accession=fetch_accession,
        run_alignment=run_alignment,
        run_trimming=run_trimming,
        run_iqtree=run_iqtree,
    )


def _build_manifest_payload(
    step_status: dict[str, str],
    warnings: list[str],
    artifacts: RunArtifacts,
) -> dict:
    return {
        "steps": step_status,
        "warnings": warnings,
        "artifacts": {
            "normalized": artifacts.normalized_files,
            "aligned": artifacts.aligned_files,
            "trimmed": artifacts.trimmed_files,
            "supermatrix": artifacts.extra_paths.get("supermatrix", ""),
            "partitions": artifacts.extra_paths.get("partitions", ""),
            "treefile": artifacts.treefile_path,
        },
    }


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
    content = "".join(f">{strain_name}\n{sequence}\n" for strain_name, sequence in ordered.items())
    path.write_text(content, encoding="utf-8")


def _write_partitions(
    path: Path,
    partitions: list[tuple[str, int, int]],
) -> None:
    lines = ["#nexus", "begin sets;"]
    lines.extend(f"  charset {gene_name} = {start}-{end};" for gene_name, start, end in partitions)
    lines.append("end;")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_best_model_nex(path: str) -> dict[str, str]:
    """Parse final.best_model.nex to extract per-partition model names.

    Returns a dict mapping gene (charset) name → model string.
    Handles IQ-TREE 3 format:
        HKY{3.158}+F{0.24,0.35}+G4{1.11}: GAPDH{3.158},
        GTR+F+G4: ITS
    """
    import re

    models: dict[str, str] = {}
    if not os.path.isfile(path):
        return models
    try:
        text = Path(path).read_text(encoding="utf-8")
    except Exception:
        return models

    # Regex to match:  ModelString : GeneName  (with optional {params} and trailing comma/semicolon)
    # Example: HKY{3.15836}+F{0.24,...}+G4{1.1096}: GAPDH{3.15784},
    pattern = re.compile(
        r"([A-Za-z0-9+{}.()_,\s-]+?)\s*:\s*([A-Za-z0-9_]+)(?:\{[^}]*\})?\s*[,;]?\s*$"
    )

    # Regex to strip {param} values from model strings for clean display
    _strip_params = re.compile(r"\{[^}]*\}")

    in_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("charpartition"):
            in_block = True
            # Check if a model:gene pair is on the same line as charpartition
            if "=" in stripped:
                after_eq = stripped.split("=", 1)[1].strip().rstrip(";")
                match = pattern.match(after_eq)
                if match:
                    model_str = _strip_params.sub("", match.group(1)).strip()
                    gene_name = match.group(2).strip()
                    models[gene_name] = model_str
            continue
        if in_block:
            if stripped in (";", "end;"):
                break
            match = pattern.match(stripped)
            if match:
                model_str = _strip_params.sub("", match.group(1)).strip()
                gene_name = match.group(2).strip()
                models[gene_name] = model_str

    return models


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
    lines.append(f"- HTML report: {artifacts.html_report_path}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_html_report(
    path: str,
    step_status: dict[str, str],
    warnings: list[str],
    artifacts: RunArtifacts,
    commands: list[str],
    gene_stats: dict[str, dict] | None = None,
    concat_info: list | None = None,
    gene_models: dict[str, str] | None = None,
) -> None:
    if gene_stats is None:
        gene_stats = {}
    if concat_info is None:
        concat_info = []
    if gene_models is None:
        gene_models = {}
    status_color = {
        "succeeded": "#2e7d32",
        "warning": "#e65100",
        "failed": "#c62828",
        "running": "#1565c0",
        "pending": "#9e9e9e",
    }
    steps_html = "".join(
        "<tr><td>{step}</td><td style='color:{color};font-weight:bold'>{status}</td></tr>".format(
            step=step,
            color=status_color.get(status, "#333"),
            status=status,
        )
        for step, status in step_status.items()
    )
    genes_html = "".join(
        "<tr>"
        f"<td>{gene_name}</td>"
        f"<td>{gs.get('accessions', 0)}</td>"
        f"<td style='color:#2e7d32'>{gs.get('fetched', 0)}</td>"
        f"<td style='color:{'#c62828' if gs.get('failed', 0) else '#333'}'>{gs.get('failed', 0)}</td>"
        f"<td>{gs.get('sequences', 0)}</td>"
        f"<td>{'✓' if gs.get('aligned') else '—'}</td>"
        f"<td>{'✓' if gs.get('trimmed') else '—'}</td>"
        f"<td>{'✓' if gs.get('included') else '—'}</td>"
        "</tr>"
        for gene_name, gs in gene_stats.items()
    )
    # Concatenation order table
    concat_html = (
        "".join(
            "<tr>"
            f"<td>{i + 1}</td>"
            f"<td>{gene_name}</td>"
            f"<td>{start}</td>"
            f"<td>{end}</td>"
            f"<td>{end - start + 1}</td>"
            f"<td>{gene_models.get(gene_name, '—')}</td>"
            f"<td>{', '.join(gene_stats.get(gene_name, {}).get('missing_strains', [])) or '—'}</td>"
            "</tr>"
            for i, (gene_name, start, end) in enumerate(concat_info)
        )
        if concat_info
        else "<tr><td colspan='7'>No concatenation data</td></tr>"
    )
    warnings_html = "".join(f"<li>{w}</li>" for w in warnings) if warnings else "<li>None</li>"
    # Group commands by tool
    mafft_cmds = [c for c in commands if "mafft" in c.lower()]
    trimal_cmds = [c for c in commands if "trimal" in c.lower()]
    iqtree_cmds = [c for c in commands if "iqtree" in c.lower()]
    other_cmds = [c for c in commands if c not in mafft_cmds + trimal_cmds + iqtree_cmds]

    def _tool_section(title: str, version: str, cmds: list[str]) -> str:
        if not cmds:
            return ""
        items = "".join(f"<li><code>{c}</code></li>" for c in cmds)
        return f"<h3>{title} <small>({version})</small></h3><ul>{items}</ul>"

    # Extract version hints from executable paths
    def _version_hint(cmds: list[str], exe_name: str) -> str:
        for c in cmds:
            parts = c.split()
            if parts:
                exe = parts[0].replace("\\", "/")
                if exe_name in exe.lower():
                    # e.g. softwares/iqtree-3.0.1-Windows/bin/iqtree3.exe
                    import re

                    m = re.search(r"([\w.-]+-\d[\d.]*)", exe)
                    if m:
                        return m.group(1)
                    return exe
        return exe_name

    commands_html = ""
    commands_html += _tool_section("MAFFT", _version_hint(mafft_cmds, "mafft"), mafft_cmds)
    commands_html += _tool_section("trimAl", _version_hint(trimal_cmds, "trimal"), trimal_cmds)
    commands_html += _tool_section("IQ-TREE", _version_hint(iqtree_cmds, "iqtree"), iqtree_cmds)
    if other_cmds:
        commands_html += _tool_section("Other", "", other_cmds)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>One Step MultiGenePhy Report</title>
<style>
body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; color: #333; }}
h1 {{ color: #1a5276; border-bottom: 2px solid #2980b9; padding-bottom: 6px; }}
h2 {{ color: #2c3e50; margin-top: 28px; }}
h3 {{ color: #34495e; margin-top: 18px; }}
h3 small {{ font-weight: normal; color: #888; font-size: 0.85em; }}
table {{ border-collapse: collapse; width: 100%; max-width: 700px; }}
td, th {{ border: 1px solid #ddd; padding: 8px 14px; text-align: left; }}
th {{ background: #ecf0f1; }}
ul {{ line-height: 1.8; }}
code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 0.92em; }}
</style>
</head>
<body>
<h1>One Step MultiGenePhy — Run Report</h1>

<h2>Step Status</h2>
<table><tr><th>Step</th><th>Status</th></tr>{steps_html}</table>

<h2>Gene Concatenation Order</h2>
<table>
<tr><th>#</th><th>Gene</th><th>Start</th><th>End</th><th>Length</th><th>Model</th><th>Missing Strains</th></tr>
{concat_html}
</table>

<h2>Per-Gene Details</h2>
<table>
<tr><th>Gene</th><th>Accessions</th><th>Fetched</th><th>Failed</th><th>Sequences</th><th>Aligned</th><th>Trimmed</th><th>Included</th></tr>
{genes_html}
</table>

<h2>Warnings</h2>
<ul>{warnings_html}</ul>

<h2>Tool Commands</h2>
{commands_html}

<h2>Artifacts</h2>
<ul>
<li><b>Tree file:</b> {artifacts.treefile_path or "not generated"}</li>
<li><b>Supermatrix:</b> {artifacts.extra_paths.get("supermatrix", "")}</li>
<li><b>Partitions:</b> {artifacts.extra_paths.get("partitions", "")}</li>
<li><b>Manifest:</b> {artifacts.manifest_path}</li>
<li><b>Run log:</b> {artifacts.report_path}</li>
<li><b>HTML report:</b> {path}</li>
</ul>

<p><em>Generated by SeqSketch — One Step MultiGenePhy workflow</em></p>
</body>
</html>"""
    Path(path).write_text(html, encoding="utf-8")


@dataclass(slots=True)
class ToolAdapters:
    fetch_accession: Callable[[str, str], str]
    run_alignment: Callable[[str, dict[str, str], str, str], tuple[dict[str, str], str]]
    run_trimming: Callable[[str, dict[str, str], str, str], tuple[dict[str, str], str]]
    run_iqtree: Callable[[str, str, str, int, str, str], str]


class OneStepMultiGenePhyRunner:
    def __init__(self, adapters: ToolAdapters, commands: list[str] | None = None):
        self.adapters = adapters
        self.commands = commands if commands is not None else []
        self.log_lines: list[str] = []
        self.concat_info: list[tuple[str, int, int]] = []
        self.gene_models: dict[str, str] = {}

    def run(
        self,
        project,
        cells,
        strain_order: list[str],
        step_changed: Callable[[str, str], None] | None = None,
        log_line: Callable[[str], None] | None = None,
        is_aborted: Callable[[], bool] | None = None,
    ) -> WorkflowRunResult:
        if step_changed is None:
            step_changed = lambda step, status: None
        if log_line is None:
            log_line = lambda line: None
        _orig_log = log_line

        def _log(msg: str) -> None:
            self.log_lines.append(msg)
            _orig_log(msg)

        log_line = _log
        if is_aborted is None:
            is_aborted = lambda: False

        def _check_abort() -> None:
            if is_aborted():
                raise RuntimeError("Workflow cancelled by user")

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

        warnings: list[str] = []
        gene_stats: dict[str, dict] = {}
        step_status = {
            "Import": "pending",
            "Fetch/Normalize": "pending",
            "Align per Gene": "pending",
            "Trim per Gene": "pending",
            "Concatenate": "pending",
            "Build Tree": "pending",
            "Summarize": "pending",
        }
        artifacts = RunArtifacts(
            root_dir=str(root_dir),
            manifest_path=str(stage_dirs["reports"] / "run_manifest.json"),
            report_path=str(stage_dirs["reports"] / "run.log"),
            html_report_path=str(stage_dirs["reports"] / "run_report.html"),
        )

        def set_step(step_name: str, status: str) -> None:
            step_status[step_name] = status
            step_changed(step_name, status)

        def add_warning(message: str) -> None:
            warnings.append(message)
            log_line(message)

        def persist_run_outputs(suppress_errors: bool = False) -> None:
            set_step("Summarize", "running")
            manifest_written = False
            persistence_errors: list[Exception] = []
            persisted_step_status = dict(step_status)
            persisted_step_status["Summarize"] = "succeeded"

            def handle_persistence_error(exc: Exception) -> None:
                failure_message = f"Summarize failed: {exc}"
                if failure_message not in warnings:
                    add_warning(failure_message)
                if step_status["Summarize"] != "failed":
                    set_step("Summarize", "failed")
                persistence_errors.append(exc)

            try:
                write_run_manifest(
                    artifacts.manifest_path,
                    _build_manifest_payload(persisted_step_status, warnings, artifacts),
                )
                manifest_written = True
            except Exception as exc:
                handle_persistence_error(exc)

            try:
                Path(artifacts.report_path).write_text(
                    "\n".join(self.log_lines) + "\n", encoding="utf-8"
                )
            except Exception as exc:
                handle_persistence_error(exc)

            try:
                report_status = (
                    persisted_step_status if not persistence_errors else dict(step_status)
                )
                _write_html_report(
                    artifacts.html_report_path,
                    report_status,
                    warnings,
                    artifacts,
                    self.commands,
                    dict(gene_stats),
                    list(self.concat_info),
                    dict(self.gene_models),
                )
            except Exception as exc:
                handle_persistence_error(exc)

            if manifest_written and persistence_errors:
                try:
                    write_run_manifest(
                        artifacts.manifest_path,
                        _build_manifest_payload(step_status, warnings, artifacts),
                    )
                except Exception:
                    pass

            if persistence_errors:
                if suppress_errors:
                    return
                raise persistence_errors[-1]

            set_step("Summarize", "succeeded")

        current_step = "Import"

        try:
            set_step("Import", "running")
            log_line("Importing gene cells")
            datasets = build_gene_datasets(cells, strain_order)

            # Write import summary to 00_import/
            lines = [
                "One Step MultiGenePhy — Import Summary",
                "",
                f"Strain count: {len(strain_order)}",
                f"Strains: {', '.join(strain_order)}",
                f"Gene count: {len(datasets)}",
                f"Genes: {', '.join(datasets)}",
                "",
                "Per-gene breakdown:",
            ]
            for name, ds in datasets.items():
                acc = sum(1 for c in ds.cells if c.value_type == "accession")
                seq = sum(1 for c in ds.cells if c.value_type == "sequence")
                lines.append(
                    f"  {name}: {len(ds.cells)} cells"
                    f" ({acc} accessions, {seq} sequences,"
                    f" {len(ds.missing_strains)} missing,"
                    f" {len(ds.invalid_cells)} invalid)"
                )
            (stage_dirs["import"] / "import_summary.txt").write_text(
                "\n".join(lines) + "\n", encoding="utf-8"
            )

            set_step("Import", "succeeded")

            _check_abort()
            current_step = "Fetch/Normalize"
            set_step("Fetch/Normalize", "running")
            log_line("Fetching and normalizing sequences")

            fetch_warning = False
            for dataset in datasets.values():
                gene_name = dataset.gene_name
                acc_total = sum(1 for c in dataset.cells if c.value_type == "accession")
                seq_total = sum(1 for c in dataset.cells if c.value_type == "sequence")
                acc_fetched = 0
                acc_failed = 0
                log_line(
                    f"  Normalizing gene: {gene_name} ({acc_total} accessions, {seq_total} sequences)"
                )
                for cell in dataset.cells:
                    if cell.value_type == "accession" and cell.accession:
                        try:
                            sequence = (
                                self.adapters
                                .fetch_accession(
                                    cell.accession,
                                    project.ncbi_email,
                                )
                                .strip()
                                .upper()
                            )
                        except Exception as exc:
                            fetch_warning = True
                            acc_failed += 1
                            cell.status = "warning"
                            cell.message = str(exc)
                            add_warning(f"{gene_name}: failed to fetch {cell.accession}: {exc}")
                            continue

                        acc_fetched += 1

                        cell.normalized_sequence = sequence
                        dataset.normalized_sequences[cell.strain_name] = sequence
                        cell.status = "succeeded"
                    elif cell.value_type == "sequence" and cell.normalized_sequence:
                        normalized = cell.normalized_sequence.strip().upper()
                        cell.normalized_sequence = normalized
                        dataset.normalized_sequences[cell.strain_name] = normalized
                        cell.status = "succeeded"

                gene_stats[gene_name] = {
                    "accessions": acc_total,
                    "fetched": acc_fetched,
                    "failed": acc_failed,
                    "sequences": seq_total,
                    "aligned": False,
                    "trimmed": False,
                    "missing_strains": [],
                    "included": False,
                }

                if dataset.normalized_sequences:
                    normalized_path = stage_dirs["normalized"] / f"{gene_name}.fasta"
                    _write_fasta(normalized_path, dataset.normalized_sequences, strain_order)
                    dataset.artifacts["normalized"] = str(normalized_path)
                    artifacts.normalized_files[dataset.gene_name] = str(normalized_path)

            set_step("Fetch/Normalize", "warning" if fetch_warning else "succeeded")
            # Log per-gene accession summary
            log_line("── Fetch Summary ──")
            for gene_name, gs in sorted(gene_stats.items()):
                log_line(
                    f"  {gene_name}: {gs['fetched']}/{gs['accessions']} accessions fetched"
                    + (f", {gs['failed']} failed" if gs.get("failed") else "")
                    + f", {gs['sequences']} raw sequences"
                )

            current_step = "Align per Gene"
            set_step("Align per Gene", "running")
            set_step("Trim per Gene", "running")
            log_line("Aligning and trimming per-gene sequences")

            alignment_warning = False
            trimming_warning = False
            trimmed_gene_count = 0
            for dataset in datasets.values():
                _check_abort()
                gs = gene_stats.setdefault(dataset.gene_name, {})
                log_line(f"  Processing gene: {dataset.gene_name}")
                usable_sequences = _ordered_sequences(dataset.normalized_sequences, strain_order)
                if len(usable_sequences) < 2:
                    alignment_warning = True
                    dataset.status = "warning"
                    add_warning(
                        f"{dataset.gene_name}: skipped because fewer than 2 usable sequences remain"
                    )
                    continue

                try:
                    gs["aligned"] = True
                    aligned_sequences, aligned_path = self.adapters.run_alignment(
                        dataset.gene_name,
                        usable_sequences,
                        str(stage_dirs["alignments"]),
                        project.mafft_mode,
                    )
                except Exception as exc:
                    alignment_warning = True
                    dataset.status = "warning"
                    add_warning(f"{dataset.gene_name}: {exc}")
                    continue

                dataset.artifacts["aligned"] = aligned_path
                artifacts.aligned_files[dataset.gene_name] = aligned_path

                current_step = "Trim per Gene"
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
                    add_warning(f"{dataset.gene_name}: {exc}")
                    current_step = "Align per Gene"
                    continue

                current_step = "Align per Gene"
                ordered_trimmed_sequences = _ordered_sequences(trimmed_sequences, strain_order)
                if not ordered_trimmed_sequences:
                    trimming_warning = True
                    dataset.status = "warning"
                    add_warning(f"{dataset.gene_name}: trimming produced no usable output")
                    continue

                gs["trimmed"] = True
                dataset.trimmed_sequences = ordered_trimmed_sequences
                dataset.artifacts["trimmed"] = trimmed_path
                artifacts.trimmed_files[dataset.gene_name] = trimmed_path
                trimmed_gene_count += 1
                dataset.status = "succeeded"

            set_step("Align per Gene", "warning" if alignment_warning else "succeeded")
            trim_status = "warning" if trimming_warning or trimmed_gene_count == 0 else "succeeded"
            set_step("Trim per Gene", trim_status)

            _check_abort()
            current_step = "Concatenate"
            set_step("Concatenate", "running")
            log_line("Concatenating trimmed gene alignments")
            concatenated, partitions = concatenate_gene_alignments(
                datasets,
                strain_order,
                gene_order=project.gene_columns,
            )
            self.concat_info = list(partitions)
            # Track which genes are included and missing strains
            for gene_name, gs in gene_stats.items():
                if gene_name in datasets and datasets[gene_name].trimmed_sequences:
                    gs["included"] = True
                    trimmed_set = set(datasets[gene_name].trimmed_sequences)
                    gs["missing_strains"] = [s for s in strain_order if s not in trimmed_set]
            log_line("Genes in concatenation: {n}".format(n=len(partitions)))
            if not partitions:
                raise RuntimeError("No genes remain usable for concatenation")

            concat_path = stage_dirs["concat"] / "supermatrix.fasta"
            partition_path = stage_dirs["concat"] / "partitions.nex"
            _write_fasta(concat_path, concatenated, strain_order)
            _write_partitions(partition_path, partitions)
            artifacts.extra_paths["supermatrix"] = str(concat_path)
            artifacts.extra_paths["partitions"] = str(partition_path)
            set_step("Concatenate", "succeeded")

            _check_abort()
            current_step = "Build Tree"
            set_step("Build Tree", "running")
            log_line("Running IQ-TREE")
            treefile_path = self.adapters.run_iqtree(
                str(concat_path),
                str(partition_path),
                str(stage_dirs["iqtree"]),
                project.iqtree_bootstrap,
                project.threads,
                getattr(project, "iqtree_bootstrap_mode", "ufboot"),
            )
            artifacts.treefile_path = treefile_path
            artifacts.extra_paths["iqtree_dir"] = str(stage_dirs["iqtree"])
            # Parse per-gene models from IQ-TREE output
            best_model_path = str(stage_dirs["iqtree"] / "final.best_model.nex")
            self.gene_models = _parse_best_model_nex(best_model_path)
            set_step("Build Tree", "succeeded")
        except Exception as exc:
            set_step(current_step, "failed")
            add_warning(f"{current_step} failed: {exc}")
            persist_run_outputs(suppress_errors=True)
            raise

        persist_run_outputs()

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
    aborted = pyqtSignal()

    def __init__(self, runner, project, cells, strain_order):
        super().__init__()
        self.runner = runner
        self.project = project
        self.cells = cells
        self.strain_order = strain_order
        self._abort = False

    def run(self) -> None:
        try:
            result = self.runner.run(
                self.project,
                self.cells,
                self.strain_order,
                step_changed=self.step_changed.emit,
                log_line=self.log_line.emit,
                is_aborted=lambda: self._abort or self.isInterruptionRequested(),
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return

        self.completed.emit(result)
