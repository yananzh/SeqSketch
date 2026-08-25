"""Unit tests for utils/run_provenance.py.

Version probing must never raise and must parse the real bundled tools'
output shapes (MAFFT on stderr with banner lines, trimAl with a blank first
line).  The run log must be append-only and machine-reproducible.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest

from utils import run_provenance as rp

# ── probe_tool_version ─────────────────────────────────────────────────────


def _fake_subprocess_run(stdout="", stderr="", returncode=0):
    def _run(cmd, **kwargs):
        return type(
            "Result",
            (),
            {"stdout": stdout, "stderr": stderr, "returncode": returncode},
        )()

    return _run


@pytest.mark.parametrize(
    "exe,stdout,stderr,expected",
    [
        # BLAST: stdout first line
        (
            r"C:\tools\blastn.exe",
            "blastn: 2.17.0+\n Package: blast 2.17.0, build Jul  1 2025\n",
            "",
            "2.17.0+",
        ),
        # IQ-TREE: stdout first line
        (
            r"C:\tools\iqtree3.exe",
            "IQ-TREE version 3.1.3 for Windows 64-bit built Jun 19 2026\n",
            "",
            "3.1.3",
        ),
        # MUSCLE: name has version suffix in the filename
        (
            r"C:\tools\muscle-win64.v5.3.exe",
            "muscle 5.3.win64 [d9725ac]\nBuilt Nov 10 2024 22:59:05\n",
            "",
            "5.3.win64",
        ),
        # trimAl: blank first line, version on line 2
        (
            r"C:\tools\trimal.exe",
            "\ntrimAl v1.5.rev1 build[2025-11-25]\n",
            "",
            "v1.5.rev1",
        ),
        # MAFFT: version on stderr, AFTER a banner
        (
            r"C:\tools\mafft.bat",
            "",
            "Active code page: 65001\n...\nv7.526 (2024/Apr/26)\n",
            "v7.526",
        ),
    ],
)
def test_probe_tool_version_parses_bundled_outputs(
    monkeypatch, exe, stdout, stderr, expected
):
    monkeypatch.setattr(rp.subprocess, "run", _fake_subprocess_run(stdout, stderr))
    rp.clear_version_cache()
    assert rp.probe_tool_version(exe) == expected


def test_probe_tool_version_caches_results(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return type("R", (), {"stdout": "blastn: 2.17.0+\n", "stderr": ""})()

    monkeypatch.setattr(rp.subprocess, "run", fake_run)
    rp.clear_version_cache()
    assert rp.probe_tool_version(r"C:\tools\blastn.exe") == "2.17.0+"
    assert rp.probe_tool_version(r"C:\tools\blastn.exe") == "2.17.0+"
    assert len(calls) == 1  # second call served from cache


def test_probe_tool_version_failure_returns_unknown(monkeypatch):
    def boom(cmd, **kwargs):
        raise OSError("no such file")

    monkeypatch.setattr(rp.subprocess, "run", boom)
    rp.clear_version_cache()
    assert rp.probe_tool_version(r"C:\missing\blastn.exe") == "unknown"


def test_probe_tool_version_unparseable_output_returns_unknown(monkeypatch):
    monkeypatch.setattr(
        rp.subprocess,
        "run",
        _fake_subprocess_run(stdout="garbage output\nno version here\n"),
    )
    rp.clear_version_cache()
    assert rp.probe_tool_version(r"C:\tools\blastn.exe") == "unknown"


def test_probe_tool_version_empty_exe():
    rp.clear_version_cache()
    assert rp.probe_tool_version("") == "unknown"
    assert rp.probe_tool_version(None) == "unknown"


# ── append_run_log ─────────────────────────────────────────────────────────


def test_append_run_log_writes_block_with_all_fields(tmp_path):
    out_dir = tmp_path / "out"
    rp.append_run_log(
        str(out_dir),
        tool="MAFFT",
        version="v7.526",
        cmd=["C:\\Program Files\\mafft.bat", "--auto", "in file.fasta"],
        input_path=r"C:\in\seq.fasta",
        output_path=r"C:\out\aln.fasta",
        exe=r"C:\Program Files\mafft.bat",
    )
    log = (out_dir / "run_log.txt").read_text(encoding="utf-8")
    assert "Tool: MAFFT" in log
    assert "Version: v7.526" in log
    # list2cmdline quoting round-trips spaces in paths
    assert '"C:\\Program Files\\mafft.bat"' in log
    assert "Command:" in log and "in file.fasta" in log
    assert "Input: C:\\in\\seq.fasta" in log
    assert "Output: C:\\out\\aln.fasta" in log
    assert "Run: 20" in log  # timestamp starts with the year
    assert "SeqSketch:" in log


def test_append_run_log_is_append_only(tmp_path):
    out_dir = tmp_path / "out"
    rp.append_run_log(str(out_dir), "MAFFT", "v1", ["mafft", "a"])
    rp.append_run_log(str(out_dir), "IQ-TREE", "3.1.3", ["iqtree3", "b"])
    log = (out_dir / "run_log.txt").read_text(encoding="utf-8")
    assert log.count("Tool: MAFFT") == 1
    assert log.count("Tool: IQ-TREE") == 1
    assert log.index("Tool: MAFFT") < log.index("Tool: IQ-TREE")


def test_append_run_log_creates_output_dir(tmp_path):
    out_dir = tmp_path / "deep" / "nested"
    rp.append_run_log(str(out_dir), "BLAST", "2.17.0+", ["blastn", "-db", "x"])
    assert (out_dir / "run_log.txt").is_file()


def test_append_run_log_never_raises(tmp_path):
    # Unwritable path (a file pretending to be a directory)
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")
    rp.append_run_log(str(blocker), "MAFFT", "v1", ["mafft"])
    # Empty dir is a no-op
    rp.append_run_log("", "MAFFT", "v1", ["mafft"])


def test_record_tool_run_probes_and_appends(monkeypatch, tmp_path):
    monkeypatch.setattr(
        rp.subprocess,
        "run",
        _fake_subprocess_run(stdout="IQ-TREE version 3.1.3 for Windows 64-bit\n"),
    )
    rp.clear_version_cache()
    out_dir = tmp_path / "out"
    rp.record_tool_run(
        str(out_dir),
        tool="IQ-TREE",
        exe=r"C:\tools\iqtree3.exe",
        cmd=["iqtree3.exe", "-s", "aln.fasta", "-m", "GTR"],
    )
    log = (out_dir / "run_log.txt").read_text(encoding="utf-8")
    assert "Tool: IQ-TREE" in log
    assert "Version: 3.1.3" in log
    assert "Command: iqtree3.exe -s aln.fasta -m GTR" in log
