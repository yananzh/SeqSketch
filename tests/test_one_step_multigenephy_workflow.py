import json

import pandas as pd
import pytest

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
        run_iqtree=lambda concat_path, partition_path, output_dir, bootstrap, threads: str(
            tmp_path / "final.treefile"
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
        run_trimming=lambda gene_name, sequences, output_dir, mode: (dict(sequences), ""),
        run_iqtree=lambda concat_path, partition_path, output_dir, bootstrap, threads: "",
    )

    runner = OneStepMultiGenePhyRunner(adapters=adapters)

    with pytest.raises(RuntimeError, match="No genes remain usable for concatenation"):
        runner.run(project, cells, strain_order=["strain_a", "strain_b"])
