import json
import subprocess
from pathlib import Path

import pandas as pd
import pytest

import modules.one_step_multigenephy_workflow as workflow_module
from modules.one_step_multigenephy_io import (
    build_gene_datasets,
    concatenate_gene_alignments,
    parse_excel_sheet,
    read_excel_columns,
    write_run_manifest,
)
from modules.one_step_multigenephy_models import GeneCell, ProjectInput
from modules.one_step_multigenephy_workflow import (
    OneStepMultiGenePhyRunner,
    ToolAdapters,
    WorkflowWorker,
    build_default_tool_adapters,
)


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

    by_key = {(cell.strain_name, cell.gene_name): cell.value_type for cell in parsed.cells}

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


def test_parse_excel_sheet_rejects_missing_gene_column(tmp_path):
    df = pd.DataFrame({
        "Strain": ["strain_a"],
        "ITS": ["ON123456.1"],
    })
    excel_path = tmp_path / "missing_gene_column.xlsx"
    df.to_excel(excel_path, index=False)

    with pytest.raises(ValueError, match="Missing gene column"):
        parse_excel_sheet(
            str(excel_path),
            sheet_name="Sheet1",
            strain_column="Strain",
            gene_columns=["ITS", "TEF1"],
        )


def test_read_excel_columns_uses_header_row(tmp_path):
    df = pd.DataFrame({
        "Strain": ["strain_a"],
        "ITS": ["ON123456.1"],
        "TEF1": ["ATGCGTAA"],
    })
    excel_path = tmp_path / "columns.xlsx"
    df.to_excel(excel_path, index=False)

    columns = read_excel_columns(str(excel_path), sheet_name="Sheet1")

    assert columns == ["Strain", "ITS", "TEF1"]


def test_build_gene_datasets_tracks_missing_invalid_and_normalized_sequences():
    cells = [
        GeneCell("strain_a", "ITS", "ATGC", "sequence", normalized_sequence="ATGC"),
        GeneCell("strain_b", "ITS", "", "missing"),
        GeneCell("strain_c", "ITS", "bad-value", "invalid"),
        GeneCell("strain_a", "TEF1", "ON123456.1", "accession", accession="ON123456.1"),
        GeneCell("strain_b", "TEF1", "GGTT", "sequence", normalized_sequence="GGTT"),
    ]

    datasets = build_gene_datasets(cells, ["strain_a", "strain_b", "strain_c"])

    its_dataset = datasets["ITS"]
    tef1_dataset = datasets["TEF1"]

    assert its_dataset.missing_strains == ["strain_b"]
    assert its_dataset.invalid_cells == [cells[2]]
    assert its_dataset.normalized_sequences == {"strain_a": "ATGC"}
    assert tef1_dataset.missing_strains == []
    assert tef1_dataset.invalid_cells == []
    assert tef1_dataset.normalized_sequences == {"strain_b": "GGTT"}


def test_concatenate_gene_alignments_gap_fills_missing_genes():
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


def test_concatenate_gene_alignments_rejects_mismatched_trimmed_lengths():
    datasets = build_gene_datasets(
        [
            GeneCell("strain_a", "ITS", "AAA", "sequence", normalized_sequence="AAA"),
            GeneCell("strain_b", "ITS", "AA", "sequence", normalized_sequence="AA"),
        ],
        ["strain_a", "strain_b"],
    )
    datasets["ITS"].trimmed_sequences = {"strain_a": "AAA", "strain_b": "AA"}

    with pytest.raises(ValueError, match="ITS.*trimmed sequence lengths"):
        concatenate_gene_alignments(datasets, strain_order=["strain_a", "strain_b"])


def test_concatenate_gene_alignments_skips_zero_length_trimmed_gene():
    datasets = build_gene_datasets(
        [
            GeneCell("strain_a", "ITS", "", "sequence", normalized_sequence=""),
            GeneCell("strain_b", "ITS", "", "sequence", normalized_sequence=""),
            GeneCell("strain_a", "TEF1", "GG", "sequence", normalized_sequence="GG"),
            GeneCell("strain_b", "TEF1", "GA", "sequence", normalized_sequence="GA"),
        ],
        ["strain_a", "strain_b"],
    )
    datasets["ITS"].trimmed_sequences = {"strain_a": "", "strain_b": ""}
    datasets["TEF1"].trimmed_sequences = {"strain_a": "GG", "strain_b": "GA"}

    concatenated, partitions = concatenate_gene_alignments(
        datasets,
        strain_order=["strain_a", "strain_b"],
    )

    assert concatenated == {"strain_a": "GG", "strain_b": "GA"}
    assert partitions == [("TEF1", 1, 2)]


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
        return dict(sequences), str(tmp_path / f"{gene_name}.aln")

    adapters = ToolAdapters(
        fetch_accession=lambda accession, email: "ATGC",
        run_alignment=fake_align,
        run_trimming=lambda gene_name, sequences, output_dir, mode: (
            dict(sequences),
            str(tmp_path / f"{gene_name}.trimmed.fasta"),
        ),
        run_iqtree=lambda concat_path, partition_path, output_dir, bootstrap, threads, bootstrap_mode="ufboot": (
            str(tmp_path / "final.treefile")
        ),
    )

    runner = OneStepMultiGenePhyRunner(adapters=adapters)

    result = runner.run(project, cells, strain_order=["strain_a", "strain_b"])

    assert result.step_status["Align per Gene"] == "warning"
    assert any("TEF1" in warning for warning in result.warnings)
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
        GeneCell("strain_b", "ITS", "ATGA", "sequence", normalized_sequence="ATGA"),
    ]

    adapters = ToolAdapters(
        fetch_accession=lambda accession, email: "ATGC",
        run_alignment=lambda gene_name, sequences, output_dir, mode: (_ for _ in ()).throw(
            RuntimeError("alignment failed")
        ),
        run_trimming=lambda gene_name, sequences, output_dir, mode: (
            dict(sequences),
            "",
        ),
        run_iqtree=lambda concat_path, partition_path, output_dir, bootstrap, threads, bootstrap_mode="ufboot": (
            ""
        ),
    )

    runner = OneStepMultiGenePhyRunner(adapters=adapters)

    with pytest.raises(RuntimeError, match="No genes remain usable for concatenation"):
        runner.run(project, cells, strain_order=["strain_a", "strain_b"])

    manifest_path = tmp_path / "run" / "06_reports" / "run_manifest.json"
    summary_path = tmp_path / "run" / "06_reports" / "run.log"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summary = summary_path.read_text(encoding="utf-8")

    assert manifest["steps"]["Align per Gene"] == "warning"
    assert manifest["steps"]["Trim per Gene"] == "warning"
    assert manifest["steps"]["Concatenate"] == "failed"
    assert manifest["warnings"] == [
        "ITS: alignment failed",
        "Concatenate failed: No genes remain usable for concatenation",
    ]
    assert summary_path.exists()
    assert "Concatenate failed: No genes remain usable for concatenation" in summary


def test_runner_writes_failed_run_state_when_iqtree_raises(tmp_path):
    project = ProjectInput(
        excel_path="input.xlsx",
        sheet_name="Sheet1",
        strain_column="Strain",
        gene_columns=["ITS", "TEF1"],
        output_dir=str(tmp_path / "run"),
        ncbi_email="user@example.com",
    )
    cells = [
        GeneCell("strain_a", "ITS", "ATGC", "sequence", normalized_sequence="ATGC"),
        GeneCell("strain_b", "ITS", "ATGA", "sequence", normalized_sequence="ATGA"),
        GeneCell("strain_a", "TEF1", "GGGG", "sequence", normalized_sequence="GGGG"),
        GeneCell("strain_b", "TEF1", "GGGA", "sequence", normalized_sequence="GGGA"),
    ]

    def fake_align(gene_name, sequences, output_dir, mode):
        if gene_name == "TEF1":
            raise RuntimeError("simulated MAFFT failure")
        return dict(sequences), str(tmp_path / f"{gene_name}.aln")

    adapters = ToolAdapters(
        fetch_accession=lambda accession, email: "ATGC",
        run_alignment=fake_align,
        run_trimming=lambda gene_name, sequences, output_dir, mode: (
            dict(sequences),
            str(tmp_path / f"{gene_name}.trimmed.fasta"),
        ),
        run_iqtree=lambda concat_path, partition_path, output_dir, bootstrap, threads, bootstrap_mode="ufboot": (
            (_ for _ in ()).throw(RuntimeError("iqtree failed"))
        ),
    )

    runner = OneStepMultiGenePhyRunner(adapters=adapters)

    with pytest.raises(RuntimeError, match="iqtree failed"):
        runner.run(project, cells, strain_order=["strain_a", "strain_b"])

    manifest_path = tmp_path / "run" / "06_reports" / "run_manifest.json"
    summary_path = tmp_path / "run" / "06_reports" / "run.log"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summary = summary_path.read_text(encoding="utf-8")

    assert manifest["steps"]["Align per Gene"] == "warning"
    assert manifest["steps"]["Build Tree"] == "failed"
    assert manifest["warnings"] == [
        "TEF1: simulated MAFFT failure",
        "Build Tree failed: iqtree failed",
    ]
    assert manifest["artifacts"]["supermatrix"].endswith("supermatrix.fasta")
    assert manifest["artifacts"]["treefile"] == ""
    assert summary_path.exists()
    assert "Build Tree failed: iqtree failed" in summary


def test_runner_preserves_original_failure_when_manifest_write_raises(tmp_path, monkeypatch):
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
        GeneCell("strain_b", "ITS", "ATGA", "sequence", normalized_sequence="ATGA"),
    ]

    adapters = ToolAdapters(
        fetch_accession=lambda accession, email: "ATGC",
        run_alignment=lambda gene_name, sequences, output_dir, mode: (
            dict(sequences),
            str(tmp_path / f"{gene_name}.aln"),
        ),
        run_trimming=lambda gene_name, sequences, output_dir, mode: (
            dict(sequences),
            str(tmp_path / f"{gene_name}.trimmed.fasta"),
        ),
        run_iqtree=lambda concat_path, partition_path, output_dir, bootstrap, threads, bootstrap_mode="ufboot": (
            (_ for _ in ()).throw(RuntimeError("iqtree failed"))
        ),
    )

    def fail_manifest_write(path, payload):
        raise OSError("manifest disk full")

    monkeypatch.setattr(workflow_module, "write_run_manifest", fail_manifest_write)

    runner = OneStepMultiGenePhyRunner(adapters=adapters)

    with pytest.raises(RuntimeError, match="iqtree failed"):
        runner.run(project, cells, strain_order=["strain_a", "strain_b"])

    reports_dir = tmp_path / "run" / "06_reports"
    summary_path = reports_dir / "run.log"

    assert not (reports_dir / "run_manifest.json").exists()
    assert summary_path.exists()
    summary = summary_path.read_text(encoding="utf-8")
    assert "Build Tree failed: iqtree failed" in summary
    assert "manifest disk full" in summary


def test_runner_marks_summarize_failed_when_summary_write_raises(tmp_path, monkeypatch):
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
        GeneCell("strain_b", "ITS", "ATGA", "sequence", normalized_sequence="ATGA"),
    ]

    adapters = ToolAdapters(
        fetch_accession=lambda accession, email: "ATGC",
        run_alignment=lambda gene_name, sequences, output_dir, mode: (
            dict(sequences),
            str(tmp_path / f"{gene_name}.aln"),
        ),
        run_trimming=lambda gene_name, sequences, output_dir, mode: (
            dict(sequences),
            str(tmp_path / f"{gene_name}.trimmed.fasta"),
        ),
        run_iqtree=lambda concat_path, partition_path, output_dir, bootstrap, threads, bootstrap_mode="ufboot": (
            str(tmp_path / "final.treefile")
        ),
    )

    def fail_summary_write(
        path, step_status, warnings, artifacts, commands, gene_stats, concat_info, gene_models
    ):
        raise OSError("summary disk full")

    monkeypatch.setattr(workflow_module, "_write_html_report", fail_summary_write)

    transitions = []
    runner = OneStepMultiGenePhyRunner(adapters=adapters)

    with pytest.raises(OSError, match="summary disk full"):
        runner.run(
            project,
            cells,
            strain_order=["strain_a", "strain_b"],
            step_changed=lambda step, status: transitions.append((step, status)),
        )

    manifest_path = tmp_path / "run" / "06_reports" / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert [status for step, status in transitions if step == "Summarize"] == [
        "running",
        "failed",
    ]
    assert manifest["steps"]["Summarize"] == "failed"
    assert manifest["warnings"] == [
        "Summarize failed: summary disk full",
    ]


def test_runner_persists_summarize_succeeded_on_success(tmp_path):
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
        GeneCell("strain_b", "ITS", "ATGA", "sequence", normalized_sequence="ATGA"),
    ]

    adapters = ToolAdapters(
        fetch_accession=lambda accession, email: "ATGC",
        run_alignment=lambda gene_name, sequences, output_dir, mode: (
            dict(sequences),
            str(tmp_path / f"{gene_name}.aln"),
        ),
        run_trimming=lambda gene_name, sequences, output_dir, mode: (
            dict(sequences),
            str(tmp_path / f"{gene_name}.trimmed.fasta"),
        ),
        run_iqtree=lambda concat_path, partition_path, output_dir, bootstrap, threads, bootstrap_mode="ufboot": (
            str(tmp_path / "final.treefile")
        ),
    )

    runner = OneStepMultiGenePhyRunner(adapters=adapters)

    result = runner.run(project, cells, strain_order=["strain_a", "strain_b"])

    manifest_path = tmp_path / "run" / "06_reports" / "run_manifest.json"
    summary_path = tmp_path / "run" / "06_reports" / "run.log"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert result.step_status["Summarize"] == "succeeded"
    assert manifest["steps"]["Summarize"] == "succeeded"
    assert summary_path.exists()


def test_runner_marks_empty_trimmed_output_as_warning(tmp_path):
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
        GeneCell("strain_b", "ITS", "ATGA", "sequence", normalized_sequence="ATGA"),
    ]

    adapters = ToolAdapters(
        fetch_accession=lambda accession, email: "ATGC",
        run_alignment=lambda gene_name, sequences, output_dir, mode: (
            dict(sequences),
            str(tmp_path / f"{gene_name}.aln"),
        ),
        run_trimming=lambda gene_name, sequences, output_dir, mode: (
            {strain_name: "" for strain_name in sequences},
            str(tmp_path / f"{gene_name}.trimmed.fasta"),
        ),
        run_iqtree=lambda concat_path, partition_path, output_dir, bootstrap, threads, bootstrap_mode="ufboot": (
            ""
        ),
    )

    runner = OneStepMultiGenePhyRunner(adapters=adapters)

    with pytest.raises(RuntimeError, match="No genes remain usable for concatenation"):
        runner.run(project, cells, strain_order=["strain_a", "strain_b"])

    manifest_path = tmp_path / "run" / "06_reports" / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["steps"]["Trim per Gene"] == "warning"
    assert manifest["warnings"] == [
        "ITS: trimming produced no usable output",
        "Concatenate failed: No genes remain usable for concatenation",
    ]
    assert manifest["artifacts"]["trimmed"] == {}


def test_build_default_tool_adapters_fetch_accession_uses_entrez_email(monkeypatch):
    calls = {}

    class FakeHandle:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return ">ON123456.1 sample\nATGC\n"

    class FakeEntrez:
        email = ""

        @staticmethod
        def efetch(db, id, rettype, retmode):
            calls["request"] = (db, id, rettype, retmode, FakeEntrez.email)
            return FakeHandle()

    monkeypatch.setattr(workflow_module, "Entrez", FakeEntrez)

    adapters = build_default_tool_adapters()

    sequence = adapters.fetch_accession("ON123456.1", "user@example.com")

    assert sequence == "ATGC"
    assert calls["request"] == (
        "nucleotide",
        "ON123456.1",
        "fasta",
        "text",
        "user@example.com",
    )


def test_build_default_tool_adapters_use_resource_paths_and_parse_outputs(tmp_path, monkeypatch):
    mafft_exe = tmp_path / "mafft.bat"
    trimal_exe = tmp_path / "trimal.exe"
    iqtree_exe = tmp_path / "iqtree3.exe"
    for path in (mafft_exe, trimal_exe, iqtree_exe):
        path.write_text("echo", encoding="utf-8")

    resource_paths = {
        ("softwares", "mafft-win_v7.526", "mafft.bat"): str(mafft_exe),
        ("softwares", "mafft-win_v7.526", "mafft-signed.ps1"): str(tmp_path / "missing-mafft.ps1"),
        ("softwares", "trimAl_Windows_v1.5.1", "trimal.exe"): str(trimal_exe),
        ("softwares", "iqtree-3.0.1-Windows", "bin", "iqtree3.exe"): str(iqtree_exe),
    }
    calls = []

    def fake_resource_path(*parts):
        return resource_paths[parts]

    def make_fake_popen():
        class _FakeStream:
            def __init__(self, text):
                self._lines = text.splitlines(keepends=True)

            def __iter__(self):
                return iter(self._lines)

        class _FakePopen:
            def __init__(self, cmd, stdout=None, stderr=None, text=None,
                         encoding=None, errors=None, creationflags=None, cwd=None):
                calls.append({"cmd": list(cmd), "creationflags": creationflags, "cwd": cwd})
                executable_name = Path(cmd[0]).name.lower()
                if executable_name == "mafft.bat":
                    self._stdout_text = ">strain_a\nAA-\n>strain_b\nAT-\n"
                elif executable_name == "trimal.exe":
                    output_path = Path(cmd[cmd.index("-out") + 1])
                    output_path.write_text(
                        ">strain_a\nAA\n>strain_b\nAT\n",
                        encoding="utf-8",
                    )
                    self._stdout_text = ""
                elif executable_name == "iqtree3.exe":
                    prefix = cmd[cmd.index("--prefix") + 1]
                    Path(f"{prefix}.treefile").write_text("(strain_a,strain_b);\n", encoding="utf-8")
                    self._stdout_text = "ok"
                else:
                    raise AssertionError(f"Unexpected command: {cmd}")
                self.returncode = 0
                self.stdout = _FakeStream(self._stdout_text)
                self.stderr = _FakeStream("")
                self.pid = 0

            def poll(self):
                return self.returncode

            def wait(self, timeout=None):
                return self.returncode

        return _FakePopen

    monkeypatch.setattr(workflow_module, "tool_path_from_config", lambda section, key: None)
    monkeypatch.setattr(workflow_module, "resource_path", fake_resource_path)
    monkeypatch.setattr(workflow_module.subprocess, "Popen", make_fake_popen())

    adapters = build_default_tool_adapters()

    aligned_sequences, aligned_path = adapters.run_alignment(
        "ITS",
        {"strain_a": "AA", "strain_b": "AT"},
        str(tmp_path / "alignments"),
        "--auto",
    )
    trimmed_sequences, trimmed_path = adapters.run_trimming(
        "ITS",
        aligned_sequences,
        str(tmp_path / "trimmed"),
        "automated1",
    )
    treefile_path = adapters.run_iqtree(
        str(tmp_path / "concat" / "supermatrix.fasta"),
        str(tmp_path / "concat" / "partitions.nex"),
        str(tmp_path / "iqtree"),
        1000,
        "AUTO",
    )

    assert aligned_sequences == {"strain_a": "AA-", "strain_b": "AT-"}
    assert trimmed_sequences == {"strain_a": "AA", "strain_b": "AT"}
    assert Path(aligned_path).exists()
    assert Path(trimmed_path).exists()
    assert Path(treefile_path).exists()

    no_window = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    assert calls[0]["cmd"][0] == str(mafft_exe)
    assert calls[0]["creationflags"] == no_window
    assert "--auto" in calls[0]["cmd"]
    assert calls[1]["cmd"][0] == str(trimal_exe)
    assert "-automated1" in calls[1]["cmd"]
    assert calls[2]["cmd"][0] == str(iqtree_exe)
    assert calls[2]["cmd"][calls[2]["cmd"].index("-T") + 1] == "AUTO"
    assert calls[2]["cmd"][calls[2]["cmd"].index("-B") + 1] == "1000"


def test_runner_concatenates_in_project_gene_column_order(tmp_path):
    project = ProjectInput(
        excel_path="input.xlsx",
        sheet_name="Sheet1",
        strain_column="Strain",
        gene_columns=["TEF1", "ITS"],
        output_dir=str(tmp_path / "run"),
        ncbi_email="user@example.com",
    )
    cells = [
        GeneCell("strain_a", "ITS", "AA", "sequence", normalized_sequence="AA"),
        GeneCell("strain_b", "ITS", "AT", "sequence", normalized_sequence="AT"),
        GeneCell("strain_a", "TEF1", "GG", "sequence", normalized_sequence="GG"),
        GeneCell("strain_b", "TEF1", "GA", "sequence", normalized_sequence="GA"),
    ]

    adapters = ToolAdapters(
        fetch_accession=lambda accession, email: "ATGC",
        run_alignment=lambda gene_name, sequences, output_dir, mode: (
            dict(sequences),
            str(tmp_path / f"{gene_name}.aln"),
        ),
        run_trimming=lambda gene_name, sequences, output_dir, mode: (
            dict(sequences),
            str(tmp_path / f"{gene_name}.trimmed.fasta"),
        ),
        run_iqtree=lambda concat_path, partition_path, output_dir, bootstrap, threads, bootstrap_mode="ufboot": (
            str(tmp_path / "final.treefile")
        ),
    )

    runner = OneStepMultiGenePhyRunner(adapters=adapters)

    runner.run(project, cells, strain_order=["strain_a", "strain_b"])

    partition_path = tmp_path / "run" / "04_concat" / "partitions.nex"
    supermatrix_path = tmp_path / "run" / "04_concat" / "supermatrix.fasta"

    assert partition_path.read_text(encoding="utf-8").splitlines()[2:4] == [
        "  charset TEF1 = 1-2;",
        "  charset ITS = 3-4;",
    ]
    assert supermatrix_path.read_text(encoding="utf-8") == ">strain_a\nGGAA\n>strain_b\nGAAT\n"


def test_workflow_worker_emits_runner_progress_signals(tmp_path):
    project = ProjectInput(
        excel_path="input.xlsx",
        sheet_name="Sheet1",
        strain_column="Strain",
        gene_columns=["ITS"],
        output_dir=str(tmp_path / "run"),
    )
    steps: list[tuple[str, str]] = []
    lines: list[str] = []
    completed: list[object] = []

    class FakeRunner:
        def run(
            self,
            project,
            cells,
            strain_order,
            step_changed=None,
            log_line=None,
            is_aborted=None,
        ):
            assert step_changed is not None
            assert log_line is not None
            step_changed("Import", "running")
            log_line("starting import")
            return {"ok": True}

    worker = WorkflowWorker(FakeRunner(), project, [], [])
    worker.step_changed.connect(lambda step, status: steps.append((step, status)))
    worker.log_line.connect(lines.append)
    worker.completed.connect(completed.append)

    worker.run()

    assert steps == [("Import", "running")]
    assert lines == ["starting import"]
    assert completed == [{"ok": True}]


def test_workflow_worker_emits_failed_on_runner_exception(tmp_path):
    project = ProjectInput(
        excel_path="input.xlsx",
        sheet_name="Sheet1",
        strain_column="Strain",
        gene_columns=["ITS"],
        output_dir=str(tmp_path / "run"),
    )
    failed: list[str] = []
    completed: list[object] = []

    class FakeRunner:
        def run(
            self,
            project,
            cells,
            strain_order,
            step_changed=None,
            log_line=None,
            is_aborted=None,
        ):
            raise RuntimeError("runner exploded")

    worker = WorkflowWorker(FakeRunner(), project, [], [])
    worker.failed.connect(failed.append)
    worker.completed.connect(completed.append)

    worker.run()

    assert failed == ["runner exploded"]
    assert completed == []


def test_runner_skips_fetch_align_trim_when_outputs_exist(tmp_path):
    run_dir = tmp_path / "run"
    normalized = run_dir / "01_normalized"
    trimmed = run_dir / "03_trimmed"
    concat = run_dir / "04_concat"
    reports = run_dir / "06_reports"
    normalized.mkdir(parents=True)
    trimmed.mkdir(parents=True)
    concat.mkdir(parents=True)
    reports.mkdir(parents=True)
    (normalized / "ITS.fasta").write_text(
        ">strain_a\nATGC\n>strain_b\nATGA\n", encoding="utf-8"
    )
    (trimmed / "ITS.fasta").write_text(
        ">strain_a\nATGC\n>strain_b\nATGA\n", encoding="utf-8"
    )
    (concat / "supermatrix.fasta").write_text(
        ">strain_a\nATGC\n>strain_b\nATGA\n", encoding="utf-8"
    )
    (concat / "partitions.nex").write_text("charset gene1 = 1-4;\n", encoding="utf-8")

    project = ProjectInput(
        excel_path="input.xlsx",
        sheet_name="Sheet1",
        strain_column="Strain",
        gene_columns=["ITS"],
        output_dir=str(run_dir),
        ncbi_email="user@example.com",
        resume_mode="tree",
    )
    cells = [
        GeneCell("strain_a", "ITS", "MK123", "accession", accession="MK123"),
        GeneCell("strain_b", "ITS", "MK124", "accession", accession="MK124"),
    ]

    # Resume reuse requires a manifest fingerprint matching the current inputs
    fingerprint = workflow_module._project_fingerprint(project, cells, ["strain_a", "strain_b"])
    workflow_module.write_run_manifest(
        reports / "run_manifest.json", {"input_fingerprint": fingerprint}
    )

    def _boom(*args, **kwargs):
        raise AssertionError("adapter should not be called when skipping")

    adapters = ToolAdapters(
        fetch_accession=_boom,
        run_alignment=_boom,
        run_trimming=_boom,
        run_iqtree=lambda concat_path, partition_path, output_dir, bootstrap, threads, bootstrap_mode="ufboot": (
            str(tmp_path / "final.treefile")
        ),
    )
    runner = OneStepMultiGenePhyRunner(adapters=adapters)

    result = runner.run(project, cells, strain_order=["strain_a", "strain_b"])

    assert result.step_status["Fetch/Normalize"] == "skipped"
    assert result.step_status["Align per Gene"] == "skipped"
    assert result.step_status["Trim per Gene"] == "skipped"
    assert result.step_status["Concatenate"] == "skipped"
    assert result.step_status["Build Tree"] == "succeeded"
    assert not result.warnings
    assert result.artifacts.treefile_path.endswith("final.treefile")


def test_runner_align_mode_skips_fetch_but_runs_align_trim(tmp_path):
    run_dir = tmp_path / "run"
    normalized = run_dir / "01_normalized"
    reports = run_dir / "06_reports"
    normalized.mkdir(parents=True)
    reports.mkdir(parents=True)
    (normalized / "ITS.fasta").write_text(
        ">strain_a\nATGC\n>strain_b\nATGA\n", encoding="utf-8"
    )

    project = ProjectInput(
        excel_path="input.xlsx",
        sheet_name="Sheet1",
        strain_column="Strain",
        gene_columns=["ITS"],
        output_dir=str(run_dir),
        ncbi_email="user@example.com",
        resume_mode="align",
    )
    cells = [
        GeneCell("strain_a", "ITS", "MK123", "accession", accession="MK123"),
        GeneCell("strain_b", "ITS", "MK124", "accession", accession="MK124"),
    ]

    fingerprint = workflow_module._project_fingerprint(project, cells, ["strain_a", "strain_b"])
    workflow_module.write_run_manifest(
        reports / "run_manifest.json", {"input_fingerprint": fingerprint}
    )

    calls = []

    def fetch_accession(accession, email):
        calls.append("fetch")
        return "ATGC"

    def run_alignment(gene_name, sequences, output_dir, mode):
        calls.append("align")
        return dict(sequences), str(tmp_path / f"{gene_name}.aln")

    def run_trimming(gene_name, sequences, output_dir, mode):
        calls.append("trim")
        return dict(sequences), str(tmp_path / f"{gene_name}.trimmed.fasta")

    adapters = ToolAdapters(
        fetch_accession=fetch_accession,
        run_alignment=run_alignment,
        run_trimming=run_trimming,
        run_iqtree=lambda concat_path, partition_path, output_dir, bootstrap, threads, bootstrap_mode="ufboot": (
            str(tmp_path / "final.treefile")
        ),
    )
    runner = OneStepMultiGenePhyRunner(adapters=adapters)

    result = runner.run(project, cells, strain_order=["strain_a", "strain_b"])

    assert calls == ["align", "trim"]  # fetch skipped, align/trim still run
    assert result.step_status["Fetch/Normalize"] == "skipped"
    assert result.step_status["Align per Gene"] == "succeeded"
    assert result.step_status["Trim per Gene"] == "succeeded"


def test_runner_resume_falls_back_to_scratch_on_fingerprint_mismatch(tmp_path):
    run_dir = tmp_path / "run"
    normalized = run_dir / "01_normalized"
    reports = run_dir / "06_reports"
    normalized.mkdir(parents=True)
    reports.mkdir(parents=True)
    (normalized / "ITS.fasta").write_text(
        ">strain_a\nATGC\n>strain_b\nATGA\n", encoding="utf-8"
    )
    # Manifest recorded for different inputs (stale fingerprint)
    workflow_module.write_run_manifest(
        reports / "run_manifest.json", {"input_fingerprint": "stale-value"}
    )

    project = ProjectInput(
        excel_path="input.xlsx",
        sheet_name="Sheet1",
        strain_column="Strain",
        gene_columns=["ITS"],
        output_dir=str(run_dir),
        ncbi_email="user@example.com",
        resume_mode="align",
    )
    cells = [
        GeneCell("strain_a", "ITS", "ATGC", "sequence", normalized_sequence="ATGC"),
        GeneCell("strain_b", "ITS", "ATGA", "sequence", normalized_sequence="ATGA"),
    ]

    calls = []

    def fetch_accession(accession, email):
        calls.append("fetch")
        return "ATGC"

    def run_alignment(gene_name, sequences, output_dir, mode):
        calls.append("align")
        return dict(sequences), str(tmp_path / f"{gene_name}.aln")

    def run_trimming(gene_name, sequences, output_dir, mode):
        calls.append("trim")
        return dict(sequences), str(tmp_path / f"{gene_name}.trimmed.fasta")

    adapters = ToolAdapters(
        fetch_accession=fetch_accession,
        run_alignment=run_alignment,
        run_trimming=run_trimming,
        run_iqtree=lambda concat_path, partition_path, output_dir, bootstrap, threads, bootstrap_mode="ufboot": (
            str(tmp_path / "final.treefile")
        ),
    )
    runner = OneStepMultiGenePhyRunner(adapters=adapters)

    result = runner.run(project, cells, strain_order=["strain_a", "strain_b"])

    # Stale fingerprint → full re-run, no silent reuse of old files
    assert calls == ["align", "trim"]  # fetch still skipped: cells are pasted sequences
    assert "Fetch/Normalize" in result.step_status
    assert any("resume disabled" in warning for warning in result.warnings)


def test_runner_resume_without_manifest_falls_back_to_scratch(tmp_path):
    run_dir = tmp_path / "run"
    normalized = run_dir / "01_normalized"
    normalized.mkdir(parents=True)
    (normalized / "ITS.fasta").write_text(
        ">strain_a\nATGC\n>strain_b\nATGA\n", encoding="utf-8"
    )
    # No run_manifest.json at all — reuse must not happen silently.

    project = ProjectInput(
        excel_path="input.xlsx",
        sheet_name="Sheet1",
        strain_column="Strain",
        gene_columns=["ITS"],
        output_dir=str(run_dir),
        ncbi_email="user@example.com",
        resume_mode="align",
    )
    cells = [
        GeneCell("strain_a", "ITS", "ATGC", "sequence", normalized_sequence="ATGC"),
        GeneCell("strain_b", "ITS", "ATGA", "sequence", normalized_sequence="ATGA"),
    ]

    adapters = ToolAdapters(
        fetch_accession=lambda accession, email: "ATGC",
        run_alignment=lambda gene_name, sequences, output_dir, mode: (
            dict(sequences),
            str(tmp_path / f"{gene_name}.aln"),
        ),
        run_trimming=lambda gene_name, sequences, output_dir, mode: (
            dict(sequences),
            str(tmp_path / f"{gene_name}.trimmed.fasta"),
        ),
        run_iqtree=lambda concat_path, partition_path, output_dir, bootstrap, threads, bootstrap_mode="ufboot": (
            str(tmp_path / "final.treefile")
        ),
    )
    runner = OneStepMultiGenePhyRunner(adapters=adapters)

    result = runner.run(project, cells, strain_order=["strain_a", "strain_b"])

    assert any("resume disabled" in warning for warning in result.warnings)
    assert result.step_status["Align per Gene"] == "succeeded"  # re-ran, not skipped


def test_runner_reports_fetch_failure_aggregate_warning(tmp_path):
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
        GeneCell("strain_b", "ITS", "ATGA", "sequence", normalized_sequence="ATGA"),
        GeneCell("strain_c", "ITS", "MK123", "accession", accession="MK123"),
    ]
    adapters = ToolAdapters(
        fetch_accession=lambda accession, email: (_ for _ in ()).throw(
            RuntimeError("network down")
        ),
        run_alignment=lambda gene_name, sequences, output_dir, mode: (
            dict(sequences),
            str(tmp_path / f"{gene_name}.aln"),
        ),
        run_trimming=lambda gene_name, sequences, output_dir, mode: (
            dict(sequences),
            str(tmp_path / f"{gene_name}.trimmed.fasta"),
        ),
        run_iqtree=lambda concat_path, partition_path, output_dir, bootstrap, threads, bootstrap_mode="ufboot": (
            str(tmp_path / "final.treefile")
        ),
    )
    runner = OneStepMultiGenePhyRunner(adapters=adapters)

    result = runner.run(project, cells, strain_order=["strain_a", "strain_b", "strain_c"])

    assert any("failed after retries" in w for w in result.warnings)
    assert result.step_status["Fetch/Normalize"] == "warning"
