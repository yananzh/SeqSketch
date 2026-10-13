"""Regression cases from the October 2026 code quality review."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from modules.fasta_processor import parse_unique_fasta_dict
from modules.one_step_multigenephy_io import build_gene_ids, parse_excel_sheet
from modules.one_step_multigenephy_models import GeneCell, ProjectInput
from modules.partition_concat_tab import _sanitize_gene_names
from modules.sanger_tab import SangerTab


@pytest.mark.parametrize("text", [
    ">a\nAAAA\n>a\nTTTT\n>b\nCCCC\n",
    ">a first\nAAAA\n>a second\nTTTT\n>b\nCCCC\n",
])
def test_alignment_rejects_duplicate_primary_ids(text):
    with pytest.raises(ValueError, match="Duplicate sequence ID"):
        parse_unique_fasta_dict(text)


def test_sanger_iupac_reverse_complement():
    assert SangerTab.reverse_complement("ARYK") == "MRYT"
    assert SangerTab.reverse_complement("ACGTRYSWKMBDHVN") == "NBDHVKMWSRYACGT"


@pytest.mark.parametrize("owned", [True, False])
def test_posix_cancellation_kills_only_owned_process_groups(monkeypatch, owned):
    from types import SimpleNamespace

    import utils.process_control as control
    calls = []
    monkeypatch.delattr(control.subprocess, "CREATE_NEW_PROCESS_GROUP", raising=False)
    monkeypatch.setattr(control.os, "getpgid", lambda pid: pid if owned else 99, raising=False)
    monkeypatch.setattr(control.os, "killpg", lambda pid, sig: calls.append("group"), raising=False)
    monkeypatch.setattr(control.signal, "SIGKILL", 9, raising=False)
    proc = SimpleNamespace(pid=4711, poll=lambda: None,
                           terminate=lambda: calls.append("child"),
                           wait=lambda **k: calls.append("reaped"))
    control.kill_process_tree(proc)
    assert calls == (["group", "reaped"] if owned else ["child", "reaped"])


def test_source_smoke_loads_lazy_tabs_and_exits_normally():
    result = subprocess.run([sys.executable, "main.py", "--smoke-test"],
                            capture_output=True, encoding="utf-8", errors="replace", timeout=30,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SMOKE:" in result.stdout


def test_unavailable_enc_displays_and_exports_without_numeric_bias(qapp, tmp_path, monkeypatch):
    import modules.codon_usage_tab as codon
    results = []
    worker = codon._Worker(">short\nATGATGTGG\n", 1, "")
    worker.finished.connect(results.extend)
    worker.run()
    assert results and results[0]["enc"] is None
    tab = codon.CodonUsageTab()
    tab._on_analysis_done(results)
    assert tab._cmp_table.item(0, 3).text() == "N/A"
    summary = {tab._stats_table.item(i, 0).text(): tab._stats_table.item(i, 1).text()
               for i in range(tab._stats_table.rowCount())}
    assert summary["ENC"] == "N/A" and summary["Codon Bias Strength"].startswith("N/A")
    output = tmp_path / "codon.csv"
    monkeypatch.setattr(codon.QFileDialog, "getSaveFileName", lambda *a, **k: (str(output), ""))
    tab._export_csv()
    assert "N/A" in output.read_text(encoding="utf-8-sig")
    tab.deleteLater()


@pytest.mark.parametrize("text", [">a\nAAAA\n>b\nTTTT\n", "ACGT!", "AC-GT", ""])
def test_sanger_rejects_multiple_records_and_invalid_bases(text):
    with pytest.raises(ValueError):
        SangerTab._sequence_from_input(text)


def test_sanger_unknown_bases_do_not_form_confident_overlap(qapp):
    tab = SangerTab()
    assert tab.auto_assemble("N" * 20, "N" * 20) == (0, 0.0, "N" * 40)
    tab.deleteLater()


@pytest.mark.parametrize(
    "forward,reverse_rc,min_identity,expected_overlap,expected_length",
    [
        ("AAAGGGCCC", "GGGCCCTTT", 0.9, 6, 12),
        ("AAAGGGCCC", "GGTCCCTTT", 0.8, 6, 12),
        ("N" * 20, "N" * 20, 0.9, 0, 40),
    ],
)
def test_sanger_chart_uses_contig_coordinates_for_reads_and_merged_output(
    qapp, monkeypatch, tmp_path, forward, reverse_rc, min_identity,
    expected_overlap, expected_length,
):
    from PyQt6.QtWidgets import QMessageBox

    tab = SangerTab()
    try:
        forward_file = tmp_path / "forward.fasta"
        reverse_file = tmp_path / "reverse.fasta"
        forward_file.write_text(f">forward\n{forward}\n", encoding="utf-8")
        reverse_file.write_text(
            f">reverse\n{tab.reverse_complement(reverse_rc)}\n", encoding="utf-8"
        )
        tab.fwd_edit.setText(str(forward_file))
        tab.rev_edit.setText(str(reverse_file))
        output_file = tmp_path / "assembled.fasta"
        tab.output_edit.setText(str(output_file))
        tab.min_overlap_spin.setValue(5)
        tab.min_identity_spin.setValue(min_identity * 100)
        monkeypatch.setattr(QMessageBox, "information", lambda *a: None)
        monkeypatch.setattr(QMessageBox, "warning", lambda *a: None)
        tab.run_assembly()
        tab._overlap_canvas.draw()

        assert tab._last_overlap == expected_overlap
        output_lines = output_file.read_text(encoding="utf-8").splitlines()
        assert output_lines[0] == ">assembled_contig"
        assert len("".join(output_lines[1:])) == expected_length
        assert "Saved" in tab.status_label.text()
        ax = tab._overlap_fig.axes[0]
        bars = {p.get_gid(): p for p in ax.patches}
        assert bars["read-forward"].get_x() == 0
        assert bars["read-forward"].get_width() == len(forward)
        assert bars["read-reverse-rc"].get_x() == len(forward) - expected_overlap
        assert bars["read-reverse-rc"].get_width() == len(reverse_rc)
        assert bars["read-merged"].get_x() == 0
        assert bars["read-merged"].get_width() == expected_length
        assert expected_length in ax.get_xticks()
        assert {"Forward read", "Reverse complement", "Merged sequence"} <= {
            t.get_text() for t in ax.texts
        }
        if expected_overlap:
            assert "identity" in tab._overlap_fig.texts[0].get_text()
            for track in ("read-forward", "read-reverse-rc", "read-merged"):
                region = bars[track + "-overlap"]
                assert region.get_x() == len(forward) - expected_overlap
                assert region.get_width() == expected_overlap
            has_mismatch = forward[-expected_overlap:] != reverse_rc[:expected_overlap]
            assert bool(ax.collections) == has_mismatch
        else:
            assert "No overlap" in tab._overlap_fig.texts[0].get_text()
            assert not any(key.endswith("-overlap") for key in bars)
        tab._clear_all()
        assert not tab._overlap_fig.axes
        assert not tab.output_edit.text()
        assert not tab.result_folder_btn.isEnabled()
        assert output_file.is_file()
    finally:
        tab.deleteLater()


@pytest.mark.parametrize("output_mode", ["automatic", "input_file", "write_error"])
def test_sanger_file_output_defaults_and_failures(qapp, monkeypatch, tmp_path, output_mode):
    from PyQt6.QtWidgets import QMessageBox, QTextEdit

    import modules.sanger_tab as sanger

    tab = SangerTab()
    try:
        forward = tmp_path / "forward.fasta"
        reverse = tmp_path / "reverse.fasta"
        original = ">forward\nAAAGGGCCC\n"
        forward.write_text(original, encoding="utf-8")
        reverse.write_text(">reverse\nAAAGGGCCC\n", encoding="utf-8")
        tab.fwd_edit.setText(str(forward))
        tab.rev_edit.setText(str(reverse))
        tab.min_overlap_spin.setValue(6)
        warnings = []
        monkeypatch.setattr(QMessageBox, "warning", lambda *a: warnings.append(a[-1]))
        assert not tab.findChildren(QTextEdit)
        if output_mode == "input_file":
            tab.output_edit.setText(str(forward))
        elif output_mode == "write_error":
            output = tmp_path / "existing.fasta"
            output.write_text("previous output", encoding="utf-8")
            tab.output_edit.setText(str(output))
            monkeypatch.setattr(sanger.FASTAProcessor, "save_file", lambda *a: False)

        tab.run_assembly()

        assert forward.read_text(encoding="utf-8") == original
        if output_mode == "automatic":
            output = Path(tab.output_edit.text())
            assert output == forward.parent / "assembled_contig.fasta"
            assert output.read_text(encoding="utf-8") == ">assembled_contig\nAAAGGGCCCTTT\n"
            assert tab.result_folder_btn.isEnabled()
            assert "Saved:" in tab.status_label.text()
            assert not warnings
        else:
            assert warnings
            assert tab.status_label.text().startswith("Error:")
            assert not tab.result_folder_btn.isEnabled()
            assert not tab._last_output_path
            if output_mode == "write_error":
                assert output.read_text(encoding="utf-8") == "previous output"
                assert not list(tmp_path.glob("tmp*.fasta"))
    finally:
        tab.deleteLater()


def test_partition_names_are_unique_after_suffix_collisions():
    names, _ = _sanitize_gene_names(["gene", "gene", "gene_2", "Gene"])
    assert len({n.casefold() for n in names}) == 4


@pytest.mark.parametrize("name", ["Sample A", "Sample:1", "样本", "Sample-1"])
def test_excel_rejects_unstable_sample_ids(monkeypatch, name):
    monkeypatch.setattr(pd, "read_excel", lambda *a, **k: pd.DataFrame({
        "Strain": [name, "valid"], "ITS": ["ATGC", "ATGA"]
    }))
    with pytest.raises(ValueError, match="row 2"):
        parse_excel_sheet("input.xlsx", "Sheet1", "Strain", ["ITS"])


@pytest.mark.parametrize("name", ["../../escaped", "C:\\escaped", "/absolute", "a/b"])
def test_gene_names_cannot_escape_output_directory(name):
    with pytest.raises(ValueError, match="Unsafe gene"):
        build_gene_ids([name])


def test_gene_id_mapping_handles_display_names_reserved_names_and_case():
    names = ["ITS (rDNA)", "CON", "gene", "Gene", "gene_2", "1gene"]
    mapping = build_gene_ids(names)
    assert mapping == build_gene_ids(names)
    assert mapping["ITS (rDNA)"] == "ITS__rDNA"
    assert mapping["CON"] == "gene_CON"
    assert len({n.casefold() for n in mapping.values()}) == len(names)


def test_ncbi_version_matching_and_legacy_headers():
    from modules.download_from_ncbi_tab import match_accession, parse_fasta_headers
    ids = parse_fasta_headers(">gi|123|gb|AB123.1| description\nACGT\n")
    assert ids == ["AB123.1"]
    assert match_accession("ab123", ids) == "AB123.1"
    assert match_accession("AB123.1", ids) == "AB123.1"
    assert match_accession("AB123.2", ids) is None
    assert match_accession("AB12", ids) is None


def test_relative_output_records_provenance_in_actual_parent(tmp_path, monkeypatch):
    from utils.run_provenance import append_run_log
    monkeypatch.chdir(tmp_path)
    append_run_log("", "MAFFT", "test", ["mafft", "in.fa"], output_path="out.fa")
    assert "Tool: MAFFT" in (tmp_path / "run_log.txt").read_text(encoding="utf-8")


def test_atomic_save_preserves_existing_output_on_replace_failure(tmp_path, monkeypatch):
    import utils.atomic_file as atomic
    target = tmp_path / "result.fasta"
    target.write_text("previous", encoding="utf-8")
    def fail(*args):
        raise PermissionError("read-only destination")
    monkeypatch.setattr(atomic.os, "replace", fail)
    with pytest.raises(PermissionError):
        atomic.write_text_atomic(target, "new")
    assert target.read_text(encoding="utf-8") == "previous"
    assert list(tmp_path.iterdir()) == [target]


def test_mafft_snapshot_and_save_failure_restore_controls(qapp, tmp_path, monkeypatch):
    import modules.mafft_alignment_tab as mafft
    tab = mafft.MafftAlignmentTab()
    output = tmp_path / "original.fasta"
    tab.input_text.setPlainText(">a\nAAAA\n>b\nAAAT\n")
    tab.output_file_edit.setText(str(output))
    marker = tmp_path / "mafft.bat"
    marker.touch()
    tab.mafft_path_edit.setText(str(marker))
    captured = []
    def capture(worker):
        captured.append(worker)
        tab.set_running_state(True)
    monkeypatch.setattr(tab, "start_worker", capture)
    tab.run()
    assert captured and captured[0].output_path == str(output)
    assert not tab.output_file_edit.isEnabled()
    tab.clear()
    assert tab.input_text.toPlainText()
    tab.output_file_edit.setText(str(tmp_path / "changed.fasta"))
    def fail(*args):
        raise PermissionError("locked")
    monkeypatch.setattr(mafft, "write_text_atomic", fail)
    monkeypatch.setattr(mafft.QMessageBox, "critical", lambda *a: None)
    tab.handle_worker_finished(">a\nAAAA\n>b\nAAAT\n")
    assert tab.run_btn.isEnabled() and tab.clear_btn.isEnabled() and tab.upload_btn.isEnabled()
    assert tab._aligned_fasta and "save failed" in tab.status_label.text().lower()
    monkeypatch.undo()
    tab._write_single_file_output(tab._aligned_fasta)
    assert output.is_file() and not (tmp_path / "changed.fasta").exists()
    tab.deleteLater()


def test_ncbi_snapshot_survives_programmatic_output_change(qapp, tmp_path, monkeypatch):
    import modules.download_from_ncbi_tab as ncbi
    tab = ncbi.DownloadFromNCBITab()
    monkeypatch.setattr(ncbi.QThread, "start", lambda self: None)
    tab.email_edit.setText("test@example.com")
    tab.acc_edit.setPlainText("AB123")
    original = tmp_path / "original.fasta"
    tab.output_edit.setText(str(original))
    tab.run_download()
    assert not tab.output_edit.isEnabled() and not tab.clear_btn.isEnabled()
    tab.clear_all()
    assert tab.acc_edit.toPlainText() == "AB123"
    tab.output_edit.setText(str(tmp_path / "changed.fasta"))
    tab._on_download_finished(">AB123.1\nACGT\n", {
        "succeeded_accessions": ["AB123"], "failed_accessions": [],
        "sequences_returned": 1, "unique_requested_count": 1,
    })
    assert original.is_file() and not (tmp_path / "changed.fasta").exists()
    assert tab.run_btn.isEnabled()
    tab.shutdown()
    tab.deleteLater()


@pytest.mark.parametrize("damage", [None, "deleted", "changed", "matrix_deleted", "matrix_changed"])
def test_production_adapter_outputs_support_validated_resume(tmp_path, monkeypatch, damage):
    import modules.one_step_multigenephy_workflow as workflow
    marker = tmp_path / "tool.exe"
    marker.touch()
    monkeypatch.setattr(workflow, "_mafft_executable", lambda: str(marker))
    monkeypatch.setattr(workflow, "_trimal_executable", lambda: str(marker))
    monkeypatch.setattr(workflow, "probe_tool_version", lambda *a: "test")
    calls = []
    def command(cmd, **kwargs):
        if "-in" in cmd:
            calls.append("trim")
            source = Path(cmd[cmd.index("-in") + 1])
            Path(cmd[cmd.index("-out") + 1]).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            return type("Result", (), {"stdout": ""})()
        calls.append("align")
        return type("Result", (), {"stdout": Path(cmd[-1]).read_text(encoding="utf-8")})()
    monkeypatch.setattr(workflow, "_run_command", command)
    adapters = workflow.build_default_tool_adapters()
    def tree(*args):
        calls.append("tree")
        path = Path(args[2]) / "final.treefile"
        path.write_text("(a,b);", encoding="utf-8")
        return str(path)
    adapters.run_iqtree = tree
    project = ProjectInput("input.xlsx", "Sheet1", "Strain", ["ITS (rDNA)"], str(tmp_path / "run"))
    cells = [GeneCell(s, "ITS (rDNA)", seq, "sequence", normalized_sequence=seq)
             for s, seq in [("a", "ATGC"), ("b", "ATGA")]]
    result = workflow.OneStepMultiGenePhyRunner(adapters).run(project, cells, ["a", "b"])
    trimmed = Path(result.artifacts.trimmed_files["ITS__rDNA"])
    assert trimmed.name == "ITS__rDNA.trimmed.fasta"
    manifest = json.loads(Path(result.artifacts.manifest_path).read_text(encoding="utf-8"))
    assert manifest["gene_ids"] == {"ITS (rDNA)": "ITS__rDNA"}
    if damage == "deleted":
        trimmed.unlink()
    elif damage == "changed":
        trimmed.write_text(">a\nAAAA\n>b\nTTTT\n", encoding="utf-8")
    matrix = Path(result.artifacts.extra_paths["supermatrix"])
    if damage == "matrix_deleted":
        matrix.unlink()
    elif damage == "matrix_changed":
        matrix.write_text(">a\nAAAA\n>b\nTTTT\n", encoding="utf-8")
    calls.clear()
    project.resume_mode = "tree"
    if damage in ("matrix_deleted", "matrix_changed"):
        saved_manifest = Path(result.artifacts.manifest_path).read_bytes()
        with pytest.raises(ValueError, match="Cannot resume from tree"):
            workflow.OneStepMultiGenePhyRunner(adapters).run(project, cells, ["a", "b"])
        assert calls == []
        assert Path(result.artifacts.manifest_path).read_bytes() == saved_manifest
        return
    resumed = workflow.OneStepMultiGenePhyRunner(adapters).run(project, cells, ["a", "b"])
    # Tree-only reuse depends on the supermatrix and partitions, not earlier files.
    assert calls == ["tree"]
    assert resumed.step_status["Concatenate"] == "skipped"
    assert "ATGC" in Path(resumed.artifacts.extra_paths["supermatrix"]).read_text(encoding="utf-8")
