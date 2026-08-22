import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

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
        self._abort = False
        self.deleteLater_calls = 0

    def start(self):
        self.start_calls += 1

    def isRunning(self):
        return False

    def wait(self, msecs=None):
        return True

    def requestInterruption(self):
        self._abort = True

    def deleteLater(self):
        self.deleteLater_calls += 1


def test_tab_renders_import_summary_and_gene_list(qapp):
    tab = OneStepMultiGenePhyTab()
    tab._populate_gene_columns(["ITS", "TEF1", "RPB2"])

    tab._log_import_summary({
        "strain_count": 2,
        "gene_count": 3,
        "accession_count": 4,
        "sequence_count": 2,
        "missing_count": 1,
        "invalid_count": 0,
    })

    text = tab.log_area.toPlainText()

    assert "Strains: 2" in text
    assert "Genes: 3" in text
    assert "Accessions: 4" in text
    assert "Raw sequences: 2" in text
    assert tab._checked_gene_columns() == ["ITS", "TEF1", "RPB2"]


def test_tab_logs_import_summary_with_translated_labels(qapp, monkeypatch):
    monkeypatch.setattr(OneStepMultiGenePhyTab, "tr", lambda self, text: f"T::{text}")

    tab = OneStepMultiGenePhyTab()
    tab._log_import_summary({
        "strain_count": 2,
        "gene_count": 3,
        "accession_count": 4,
        "sequence_count": 2,
        "missing_count": 1,
        "invalid_count": 0,
    })

    log_text = tab.log_area.toPlainText()
    assert "T::Strains: 2" in log_text
    assert "T::Genes: 3" in log_text
    assert "T::Accessions: 4" in log_text


def test_tab_loads_gene_columns_from_excel_header(qapp, monkeypatch, tmp_path):
    excel_path = tmp_path / "multigene.xlsx"

    def fake_read_excel_sheet_names(path):
        assert path == str(excel_path)
        return ["Sheet1", "Sheet2"]

    def fake_read_excel_columns(path, sheet_name):
        assert path == str(excel_path)
        assert sheet_name == "Sheet1"
        return ["Strain", "ITS", "TEF1", "RPB2"]

    monkeypatch.setattr(tab_module, "read_excel_sheet_names", fake_read_excel_sheet_names)
    monkeypatch.setattr(tab_module, "read_excel_columns", fake_read_excel_columns)

    tab = OneStepMultiGenePhyTab()
    tab.excel_path_edit.setText(str(excel_path))
    tab.sheet_name_combo.setCurrentText("Sheet1")
    tab.strain_column_combo.setCurrentText("Strain")

    tab.load_sheet_columns()

    assert tab.gene_columns == ["ITS", "TEF1", "RPB2"]
    assert tab._checked_gene_columns() == ["ITS", "TEF1", "RPB2"]


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
                html_report_path="F:/run/06_reports/run_report.html",
                manifest_path="F:/run/06_reports/run_manifest.json",
                report_path="F:/run/06_reports/summary.txt",
            ),
        )
    )

    assert tab.status_label.text() == "Completed with warnings"
    log_text = tab.log_area.toPlainText()
    assert "ITS aligned successfully" in log_text
    assert "TEF1 skipped because fewer than 2 usable sequences remain" in log_text
    assert "Align per Gene: warning" in log_text
    assert "Build Tree: succeeded" in log_text
    assert "Tree file: F:/run/05_iqtree/final.treefile" in log_text
    assert "HTML report: F:/run/06_reports/run_report.html" in log_text


def test_start_run_parses_sheet_builds_runner_and_starts_worker(qapp, monkeypatch, tmp_path):
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

    def fake_build_default_tool_adapters(commands=None):
        observed["adapters_built"] = True
        return adapters

    class FakeRunner:
        def __init__(self, adapters, commands=None):
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

    # Create the Excel file so validation passes
    excel_path.write_text("", encoding="utf-8")

    tab = OneStepMultiGenePhyTab()
    tab.excel_path_edit.setText(str(excel_path))
    tab.sheet_name_combo.setCurrentText("SheetA")
    tab.strain_column_combo.setCurrentText("Strain")
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
    assert worker.project.mafft_mode == "--auto"
    assert worker.project.trimal_mode == "automated1"
    assert worker.project.iqtree_bootstrap == 1000
    assert worker.project.threads == "AUTO"
    assert worker.project.keep_intermediates is True
    assert worker.cells == parsed.cells
    assert worker.strain_order == parsed.strain_order
    assert worker.completed.callbacks == [tab._handle_run_completed]
    assert worker.failed.callbacks
    assert worker.step_changed.callbacks == [tab._handle_step_update]
    assert worker.log_line.callbacks == [tab._append_log]
    assert worker.start_calls == 1
    assert "Strains: 2" in tab.log_area.toPlainText()

    worker.failed.callbacks[0]("simulated failure")

    assert tab.status_label.text() == "Workflow failed"
    assert "simulated failure" in tab.log_area.toPlainText()


def test_start_run_stops_when_parse_excel_sheet_fails(qapp, monkeypatch, tmp_path):
    excel_path = tmp_path / "input.xlsx"
    excel_path.write_text("", encoding="utf-8")
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
    tab.sheet_name_combo.setCurrentText("Sheet1")
    tab.strain_column_combo.setCurrentText("Strain")
    tab.output_dir_edit.setText(str(tmp_path / "run"))
    tab.email_edit.setText("user@example.com")
    tab._populate_gene_columns(["ITS"])

    tab.start_run()

    assert worker_calls == []
    assert tab.status_label.text() == "Failed to parse workbook"
    assert "sheet parse failed" in tab.log_area.toPlainText()


def test_show_help_displays_structured_workflow_guidance(qapp):
    tab = OneStepMultiGenePhyTab()
    # show_help calls show_help_dialog which creates a modal dialog;
    # verify the help_text content by inspecting the method source
    import inspect

    source = inspect.getsource(tab.show_help)
    assert "Workbook Format" in source
    assert "Quick Start" in source
    assert "Pipeline Steps" in source
    assert "output directory" in source
    assert "Tips" in source
    assert "NCBI accession" in source
    assert "Concatenate" in source


def test_threads_max_equals_cpu_count(qapp):
    tab = OneStepMultiGenePhyTab()

    assert tab.threads_spin.maximum() == max(os.cpu_count() or 1, 1)


def test_example_button_on_excel_row_left_of_browse(qapp):
    from PyQt6.QtWidgets import QPushButton

    tab = OneStepMultiGenePhyTab()
    excel_row = tab.excel_path_edit.parent().layout()
    buttons = [
        (widget, widget.text())
        for i in range(excel_row.count())
        if isinstance((widget := excel_row.itemAt(i).widget()), QPushButton)
    ]
    assert [t for _, t in buttons] == ["Example", "Browse"]


def test_gene_list_unchecking_excludes_gene(qapp):
    from PyQt6.QtCore import Qt

    tab = OneStepMultiGenePhyTab()
    tab._populate_gene_columns(["ITS", "TEF1", "RPB2"])

    assert tab._checked_gene_columns() == ["ITS", "TEF1", "RPB2"]

    tab.gene_list.item(1).setCheckState(Qt.CheckState.Unchecked)

    assert tab._checked_gene_columns() == ["ITS", "RPB2"]


def test_resume_mode_combo_exists_and_resets(qapp):
    tab = OneStepMultiGenePhyTab()

    assert hasattr(tab, "resume_mode_combo")
    assert tab.resume_mode_combo.count() == 3
    tab.resume_mode_combo.setCurrentIndex(2)
    tab._clear()
    assert tab.resume_mode_combo.currentIndex() == 0


def test_result_folder_button_opens_output_dir(qapp, monkeypatch, tmp_path):
    from PyQt6.QtCore import QUrl

    tab = OneStepMultiGenePhyTab()
    opened = []
    monkeypatch.setattr(
        "modules.one_step_multigenephy_tab.QDesktopServices.openUrl",
        lambda url: opened.append(url.toString()),
    )
    assert tab.open_output_btn.text() == "Result Folder"

    tab._open_output_folder()
    assert tab.status_label.text() == "No output folder selected yet"

    out_dir = tmp_path / "run"
    tab.output_dir_edit.setText(str(out_dir))
    tab._open_output_folder()
    assert tab.status_label.text() == "Output folder does not exist yet"

    out_dir.mkdir()
    tab._open_output_folder()
    assert opened == [QUrl.fromLocalFile(str(out_dir)).toString()]
