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
from modules.one_step_multigenephy_models import GeneCell


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
