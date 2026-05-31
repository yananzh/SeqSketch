import os
from types import SimpleNamespace
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

import modules.one_step_multigenephy_tab as tab_module
from modules.one_step_multigenephy_tab import OneStepMultiGenePhyTab


class _FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)


class _FakeWorker:
    def __init__(self, runner, project, cells, strain_order):
        self.runner = runner
        self.project = project
        self.cells = cells
        self.strain_order = strain_order
        self.completed = _FakeSignal()
        self.failed = _FakeSignal()
        self.step_changed = _FakeSignal()
        self.log_line = _FakeSignal()
        self.start_calls = 0

    def start(self):
        self.start_calls += 1


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
    assert "Raw sequences: 2" in text
    assert [tab.gene_list.item(i).text() for i in range(tab.gene_list.count())] == [
        "ITS",
        "TEF1",
        "RPB2",
    ]


def test_tab_renders_import_summary_with_translated_labels(qapp, monkeypatch):
    monkeypatch.setattr(OneStepMultiGenePhyTab, "tr", lambda self, text: f"T::{text}")

    tab = OneStepMultiGenePhyTab()
    tab._render_import_summary({
        "strain_count": 2,
        "gene_count": 3,
        "accession_count": 4,
        "sequence_count": 2,
        "missing_count": 1,
        "invalid_count": 0,
    })

    assert tab.summary_view.toPlainText().splitlines() == [
        "T::Strains: 2",
        "T::Genes: 3",
        "T::Accessions: 4",
        "T::Raw sequences: 2",
        "T::Missing: 1",
        "T::Invalid: 0",
    ]


def test_tab_loads_gene_columns_from_excel_header(qapp, monkeypatch, tmp_path):
    excel_path = tmp_path / "multigene.xlsx"

    def fake_read_excel_columns(path, sheet_name):
        assert path == str(excel_path)
        assert sheet_name == "Sheet1"
        return ["Strain", "ITS", "TEF1", "RPB2"]

    monkeypatch.setattr(tab_module, "read_excel_columns", fake_read_excel_columns)

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


def test_tab_updates_status_log_step_summary_and_artifacts_after_mocked_run(qapp):
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

    assert tab.current_step_label.text() == "Align per Gene: running"
    assert tab.step_status_view.toPlainText().splitlines() == [
        "Align per Gene: warning",
        "Build Tree: succeeded",
    ]
    assert tab.status_label.text() == "Completed with warnings"
    assert "ITS aligned successfully" in tab.log_area.toPlainText()
    assert (
        "TEF1 skipped because fewer than 2 usable sequences remain"
        in tab.log_area.toPlainText()
    )
    assert tab.artifact_list.count() == 3
    assert tab.artifact_list.item(0).text() == "F:/run/05_iqtree/final.treefile"


def test_start_run_parses_sheet_builds_runner_and_starts_worker(
    qapp, monkeypatch, tmp_path
):
    excel_path = tmp_path / "input.xlsx"
    output_dir = tmp_path / "run"
    parsed = SimpleNamespace(
        summary={
            "strain_count": 2,
            "gene_count": 2,
            "accession_count": 1,
            "sequence_count": 2,
            "missing_count": 1,
            "invalid_count": 0,
        },
        cells=["cell-a", "cell-b"],
        strain_order=["strain_a", "strain_b"],
    )
    observed = {}
    adapters = object()
    created_workers = []

    def fake_parse_excel_sheet(path, sheet_name, strain_column, gene_columns):
        observed["parse_args"] = (path, sheet_name, strain_column, list(gene_columns))
        return parsed

    def fake_build_default_tool_adapters():
        observed["adapters_built"] = True
        return adapters

    class FakeRunner:
        def __init__(self, adapters):
            observed["runner_adapters"] = adapters

    def fake_worker_factory(runner, project, cells, strain_order):
        worker = _FakeWorker(runner, project, cells, strain_order)
        created_workers.append(worker)
        return worker

    monkeypatch.setattr(tab_module, "parse_excel_sheet", fake_parse_excel_sheet)
    monkeypatch.setattr(
        tab_module,
        "build_default_tool_adapters",
        fake_build_default_tool_adapters,
    )
    monkeypatch.setattr(tab_module, "OneStepMultiGenePhyRunner", FakeRunner)
    monkeypatch.setattr(tab_module, "WorkflowWorker", fake_worker_factory)

    tab = OneStepMultiGenePhyTab()
    tab.excel_path_edit.setText(str(excel_path))
    tab.sheet_name_edit.setText("SheetA")
    tab.strain_column_edit.setText("Strain")
    tab.output_dir_edit.setText(str(output_dir))
    tab.email_edit.setText("user@example.com")
    tab._populate_gene_columns(["ITS", "TEF1"])

    tab.start_run()

    assert observed["parse_args"] == (
        str(excel_path),
        "SheetA",
        "Strain",
        ["ITS", "TEF1"],
    )
    assert observed["adapters_built"] is True
    assert observed["runner_adapters"] is adapters
    assert len(created_workers) == 1

    worker = created_workers[0]
    assert worker.project.excel_path == str(excel_path)
    assert worker.project.sheet_name == "SheetA"
    assert worker.project.strain_column == "Strain"
    assert worker.project.gene_columns == ["ITS", "TEF1"]
    assert worker.project.output_dir == str(output_dir)
    assert worker.project.ncbi_email == "user@example.com"
    assert worker.cells == parsed.cells
    assert worker.strain_order == parsed.strain_order
    assert worker.completed.callbacks == [tab._handle_run_completed]
    assert worker.failed.callbacks
    assert worker.step_changed.callbacks == [tab._handle_step_update]
    assert worker.log_line.callbacks == [tab._append_log]
    assert worker.start_calls == 1
    assert "Strains: 2" in tab.summary_view.toPlainText()

    worker.failed.callbacks[0]("simulated failure")

    assert tab.status_label.text() == "Workflow failed"
    assert "simulated failure" in tab.log_area.toPlainText()


def test_start_run_stops_when_parse_excel_sheet_fails(qapp, monkeypatch, tmp_path):
    excel_path = tmp_path / "input.xlsx"
    worker_calls = []

    def fake_parse_excel_sheet(path, sheet_name, strain_column, gene_columns):
        raise ValueError("sheet parse failed")

    def fake_worker_factory(*args, **kwargs):
        worker_calls.append((args, kwargs))
        return _FakeWorker(*args)

    monkeypatch.setattr(tab_module, "parse_excel_sheet", fake_parse_excel_sheet)
    monkeypatch.setattr(tab_module, "WorkflowWorker", fake_worker_factory)

    tab = OneStepMultiGenePhyTab()
    tab.excel_path_edit.setText(str(excel_path))
    tab.sheet_name_edit.setText("Sheet1")
    tab.strain_column_edit.setText("Strain")
    tab.output_dir_edit.setText(str(tmp_path / "run"))
    tab._populate_gene_columns(["ITS"])

    tab.start_run()

    assert worker_calls == []
    assert tab.status_label.text() == "Failed to parse workbook"
    assert "sheet parse failed" in tab.log_area.toPlainText()
