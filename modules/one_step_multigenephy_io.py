import re

import pandas as pd

from modules.one_step_multigenephy_models import GeneCell, ParsedExcelSheet


_ACCESSION_RE = re.compile(r"^[A-Z]{1,4}_?\d+(?:\.\d+)?$", re.IGNORECASE)
_DNA_RE = re.compile(r"^[ACGTRYSWKMBDHVN-]+$", re.IGNORECASE)


def classify_cell_value(raw_value: object) -> tuple[str, str, str]:
    if raw_value is None or pd.isna(raw_value):
        return "missing", "", ""

    text = str(raw_value).strip()
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
    missing_gene_columns = [gene_name for gene_name in gene_columns if gene_name not in df.columns]
    if missing_gene_columns:
        raise ValueError(
            f"Missing gene column: {', '.join(missing_gene_columns)}"
        )

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
            raw_value = row.get(gene_name, "")
            value_type, payload, source = classify_cell_value(raw_value)
            summary[f"{value_type}_count"] += 1
            raw_text = (
                ""
                if raw_value is None or pd.isna(raw_value)
                else str(raw_value).strip()
            )
            cells.append(
                GeneCell(
                    strain_name=strain_name,
                    gene_name=gene_name,
                    raw_value=raw_text,
                    value_type=value_type,
                    accession=payload if value_type == "accession" else "",
                    normalized_sequence=payload if value_type == "sequence" else "",
                    source=source,
                )
            )

    usable_gene_count = sum(
        any(
            cell.gene_name == gene_name and cell.value_type in {"accession", "sequence"}
            for cell in cells
        )
        for gene_name in gene_columns
    )
    if usable_gene_count == 0:
        raise ValueError("No selected gene column contains usable values")

    return ParsedExcelSheet(strain_order=strain_names, cells=cells, summary=summary)


def read_excel_columns(excel_path: str, sheet_name: str) -> list[str]:
    df = pd.read_excel(excel_path, sheet_name=sheet_name, header=0, nrows=0)
    return [str(column) for column in df.columns]
