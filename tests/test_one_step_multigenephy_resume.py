"""Read-only reuse prechecks and their asynchronous UI feedback."""

from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtTest import QTest

import modules.one_step_multigenephy_tab as tab_module
from modules.one_step_multigenephy_io import parse_excel_sheet, write_run_manifest
from modules.one_step_multigenephy_models import ProjectInput, RunArtifacts
from modules.one_step_multigenephy_workflow import (
    _build_manifest_payload,
    _project_fingerprint,
    check_resume_inputs,
)


@pytest.fixture
def saved_run(tmp_path):
    workbook = tmp_path / "input.xlsx"
    pd.DataFrame({"ID": ["taxon_a", "taxon_b"], "ITS": ["ACGT", "ACGA"]}).to_excel(
        workbook, index=False
    )
    project = ProjectInput(str(workbook), "Sheet1", "ID", ["ITS"], str(tmp_path / "run"))
    parsed = parse_excel_sheet(str(workbook), "Sheet1", "ID", ["ITS"])
    root = Path(project.output_dir)
    for name in ("01_normalized", "04_concat", "06_reports"):
        (root / name).mkdir(parents=True)
    normalized = root / "01_normalized/ITS.fasta"
    normalized.write_text(">taxon_a\nACGT\n>taxon_b\nACGA\n")
    matrix = root / "04_concat/supermatrix.fasta"
    matrix.write_bytes(normalized.read_bytes())
    partitions = root / "04_concat/partitions.nex"
    partitions.write_text("charset ITS = 1-4;\n")
    artifacts = RunArtifacts(
        str(root), gene_ids={"ITS": "ITS"}, normalized_files={"ITS": str(normalized)},
        extra_paths={"supermatrix": str(matrix), "partitions": str(partitions)},
    )
    manifest = root / "06_reports/run_manifest.json"
    write_run_manifest(manifest, _build_manifest_payload(
        {}, [], artifacts,
        resume_fingerprints={stage: _project_fingerprint(
            project, parsed.cells, parsed.strain_order, stage
        ) for stage in ("align", "tree")},
    ))
    return project, parsed


@pytest.mark.parametrize("mode", ["align", "tree"])
def test_resume_precheck_is_read_only(saved_run, mode, monkeypatch):
    project, parsed = saved_run
    project = replace(project, resume_mode=mode)
    root = Path(project.output_dir)
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob("*") if p.is_file()}
    monkeypatch.setattr(tab_module, "build_default_tool_adapters", lambda *a, **k: pytest.fail(
        "Precheck must not create tool adapters"
    ))
    _, paths, partitions = check_resume_inputs(project, parsed.cells, parsed.strain_order)
    if mode == "tree":
        assert partitions == [("ITS", 1, 4)]
    else:
        assert len(paths) == 1
    worker = tab_module._ResumeCheckThread(project, 1, None)
    worker.run()
    assert worker.result.startswith("Reuse ready:")
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns)
                      for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("change, reason", [
    ("missing_manifest", "manifest is required"),
    ("changed_matrix", "Changed or unverified artifact"),
    ("missing_matrix", "Missing or invalid artifact"),
    ("upstream_parameter", "inputs or upstream parameters changed"),
    ("selected_genes", "inputs or upstream parameters changed"),
])
def test_precheck_reports_specific_unavailable_reason(saved_run, change, reason):
    project, parsed = saved_run
    project = replace(project, resume_mode="tree")
    root = Path(project.output_dir)
    if change == "missing_manifest":
        (root / "06_reports/run_manifest.json").unlink()
    elif change == "changed_matrix":
        (root / "04_concat/supermatrix.fasta").write_text(">taxon_a\nAAAA\n>taxon_b\nAAAA\n")
    elif change == "missing_matrix":
        (root / "04_concat/supermatrix.fasta").unlink()
    elif change == "upstream_parameter":
        project.mafft_mode = "--localpair"
    else:
        project.gene_columns = ["OTHER"]
    with pytest.raises(ValueError, match=reason):
        check_resume_inputs(project, parsed.cells, parsed.strain_order)


def test_tree_precheck_allows_bootstrap_and_threads_changes(saved_run):
    project, parsed = saved_run
    project = replace(project, resume_mode="tree", iqtree_bootstrap=100,
                      iqtree_bootstrap_mode="standard", threads="4")
    check_resume_inputs(project, parsed.cells, parsed.strain_order)


def _configure_tab(project):
    tab = tab_module.OneStepMultiGenePhyTab()
    tab.excel_path_edit.setText(project.excel_path)
    tab.load_sheet_columns()
    tab.output_dir_edit.setText(project.output_dir)
    return tab


def _wait_for_precheck(tab):
    for _ in range(300):
        QTest.qWait(20)
        if tab._resume_check_thread is None and not tab._resume_timer.isActive():
            return
    pytest.fail("Resume precheck did not complete")


@pytest.mark.parametrize("mode, message", [
    ("tree", "Skip fetch, alignment, trimming and concatenation"),
    ("align", "Skip fetch; rerun alignment"),
])
def test_resume_ui_auto_checks_and_popup_reports_changed_files(qapp, saved_run, mode, message):
    project, _ = saved_run
    tab = _configure_tab(project)
    try:
        assert not tab._resume_check_result
        tab.resume_mode_combo.setCurrentIndex(tab.resume_mode_combo.findData(mode))
        _wait_for_precheck(tab)
        assert "Reuse ready:" in tab._resume_check_result
        assert message in tab._resume_check_result
        assert tab._resume_dialog.isVisible()
        assert message in tab._resume_dialog.text()
        artifact = "04_concat/supermatrix.fasta" if mode == "tree" else "01_normalized/ITS.fasta"
        (Path(project.output_dir) / artifact).write_text("modified")
        tab.threads_spin.setValue(1)
        _wait_for_precheck(tab)
        assert "Changed or unverified artifact" in tab._resume_check_result
        assert "Changed or unverified artifact" in tab._resume_dialog.text()
        tab.resume_mode_combo.setCurrentIndex(0)
        assert not tab._resume_check_result
        assert not tab._resume_timer.isActive()
    finally:
        tab.shutdown()


def test_resume_ui_ignores_stale_results_and_checks_latest_input(qapp, saved_run, monkeypatch):
    class ControlledCheck(QObject):
        finished = pyqtSignal()
        started = []

        def __init__(self, project, revision, parent):
            super().__init__(parent)
            self.project, self.revision = project, revision
            self.result = "Reuse ready: old result"

        def start(self):
            self.started.append(self)

    monkeypatch.setattr(tab_module, "_ResumeCheckThread", ControlledCheck)
    project, _ = saved_run
    tab = _configure_tab(project)
    try:
        tab.resume_mode_combo.setCurrentIndex(2)
        tab._resume_timer.stop()
        tab._start_resume_check()
        first = ControlledCheck.started[0]
        tab.mafft_mode_combo.setCurrentIndex(1)
        first.finished.emit()
        assert tab._resume_check_result == "Checking reuse…"
        QTest.qWait(500)
        latest = ControlledCheck.started[1]
        assert latest.project.mafft_mode == "--localpair"
        latest.result = "Reuse unavailable: changed settings"
        latest.finished.emit()
        assert "changed settings" in tab._resume_check_result
        tab._clear()
        assert not tab._resume_check_result
        assert not tab._resume_timer.isActive()
    finally:
        tab.shutdown()
