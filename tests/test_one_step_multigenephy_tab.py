import os
from types import SimpleNamespace
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
import pytest
from PyQt6.QtWidgets import QApplication

from modules.one_step_multigenephy_tab import OneStepMultiGenePhyTab


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app = cast(QApplication, app)
    app.setQuitOnLastWindowClosed(False)
    return app


def test_tab_renders_import_summary_and_gene_list(qapp):
    tab = OneStepMultiGenePhyTab()
    tab._populate_gene_columns(["ITS", "TEF1", "RPB2"])

    tab._render_import_summary(
        {
            "strain_count": 2,
            "gene_count": 3,
            "accession_count": 4,
            "sequence_count": 2,
            "missing_count": 1,
            "invalid_count": 0,
        }
    )

    text = tab.summary_view.toPlainText()

    assert "Strains: 2" in text
    assert "Genes: 3" in text
    assert "Accessions: 4" in text
    assert "Raw sequences: 2" in text
    assert [tab.gene_list.item(i).text() for i in range(tab.gene_list.count())] == [
        "ITS",
        "TEF1",
        "RPB2",
    ]


def test_tab_loads_gene_columns_from_excel_header(qapp, tmp_path):
    excel_path = tmp_path / "multigene.xlsx"
    pd.DataFrame(
        {
            "Strain": ["strain_a"],
            "ITS": ["ON123456.1"],
            "TEF1": ["ATGC"],
            "RPB2": ["ATGA"],
        }
    ).to_excel(excel_path, index=False)

    tab = OneStepMultiGenePhyTab()
    tab.excel_path_edit.setText(str(excel_path))
    tab.sheet_name_edit.setText("Sheet1")
    tab.strain_column_edit.setText("Strain")

    tab.load_sheet_columns()

    assert tab.gene_columns == ["ITS", "TEF1", "RPB2"]
    assert [tab.gene_list.item(i).text() for i in range(tab.gene_list.count())] == [
        "ITS",
        "TEF1",
        "RPB2",
    ]


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

    assert tab.step_summary_label.text() == "Align per Gene: running"
    assert tab.status_label.text() == "Completed with warnings"
    assert "ITS aligned successfully" in tab.log_area.toPlainText()
    assert (
        "TEF1 skipped because fewer than 2 usable sequences remain"
        in tab.log_area.toPlainText()
    )
    assert tab.artifact_list.count() == 3
    assert tab.artifact_list.item(0).text() == "F:/run/05_iqtree/final.treefile"
