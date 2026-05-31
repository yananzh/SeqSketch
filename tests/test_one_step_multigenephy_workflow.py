import pandas as pd
import pytest

from modules.one_step_multigenephy_io import parse_excel_sheet, read_excel_columns


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
