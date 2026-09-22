"""Reproducibility metadata for external-tool runs.

Every external command (MAFFT, MUSCLE, IQ-TREE, trimAl, BLAST, makeblastdb)
should record tool + version + full argv + timestamp into a ``run_log.txt``
next to its output.  Reviewers ask for exactly this: what was run, with which
engine version, and with which parameters.

Version probing is best-effort and never raises: a failed probe records
"unknown" instead of aborting the analysis.  Results are cached per
executable path so probing is cheap to call from every worker.
"""

import os
import re
import subprocess
from datetime import datetime

from utils.app_version import APP_VERSION as SEQSKETCH_VERSION

RUN_LOG_FILENAME = "run_log.txt"

# Exe basename → (version flag, regex applied to combined stdout+stderr).
# Verified against the bundled binaries:
#   - MAFFT (mafft.bat): output on stderr, version is the LAST line
#   - trimAl: stdout first line is blank, version is line 2
#   - BLAST / IQ-TREE / MUSCLE: version on stdout first line
_VERSION_SPECS = {
    "blastn": ("-version", re.compile(r"blast\w*:\s*(\S+)", re.I)),
    "blastp": ("-version", re.compile(r"blast\w*:\s*(\S+)", re.I)),
    "blastx": ("-version", re.compile(r"blast\w*:\s*(\S+)", re.I)),
    "tblastn": ("-version", re.compile(r"blast\w*:\s*(\S+)", re.I)),
    "tblastx": ("-version", re.compile(r"blast\w*:\s*(\S+)", re.I)),
    "makeblastdb": ("-version", re.compile(r"blast\w*:\s*(\S+)", re.I)),
    "iqtree3": ("-version", re.compile(r"IQ-TREE version\s+(\S+)", re.I)),
    "mafft": ("--version", re.compile(r"(?m)^\s*(v?\d[\d.]*)")),
    "muscle": ("-version", re.compile(r"muscle\s+(\S+)", re.I)),
    "trimal": ("--version", re.compile(r"trimAl\s+(\S+)", re.I)),
}

_VERSION_CACHE: dict[str, str] = {}


def probe_tool_version(exe: str) -> str:
    """Return the version string of *exe*, or "unknown" on any failure.

    Cached per executable path; safe to call from worker threads.
    """
    if not exe:
        return "unknown"
    if exe in _VERSION_CACHE:
        return _VERSION_CACHE[exe]

    basename = os.path.basename(exe).lower()
    # Strip version-ish suffixes (muscle-win64.v5.3.exe → muscle) so known
    # tools are matched by their stable name prefix.
    known = next((name for name in _VERSION_SPECS if basename.startswith(name)), None)
    if known is not None:
        spec = _VERSION_SPECS[known]
    else:
        # Unknown tool — try a generic version flag as a last resort.
        spec = ("--version", re.compile(r"(?i)(?:version|v)\s*([0-9][\w.+-]*)"))
    flag, pattern = spec

    version = "unknown"
    try:
        result = subprocess.run(
            [exe, flag],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW")
                else 0
            ),
        )
        combined = (result.stdout or "") + (result.stderr or "")
        matches = list(pattern.finditer(combined))
        if matches:
            # MAFFT prints a banner before the version line — the version is
            # the LAST match, not the first.
            version = matches[-1].group(1).strip()
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass

    _VERSION_CACHE[exe] = version
    return version


def clear_version_cache() -> None:
    """Reset the version cache (used by tests)."""
    _VERSION_CACHE.clear()


def append_run_log(
    output_dir: str,
    tool: str,
    version: str,
    cmd: list[str] | tuple[str, ...],
    input_path: str = "",
    output_path: str = "",
    note: str = "",
    exe: str = "",
) -> None:
    """Append one reproducibility block to ``output_dir/run_log.txt``.

    The command is rendered with list2cmdline so spaces and quotes in paths
    round-trip exactly.  Best-effort: failures (unwritable dir, etc.) are
    swallowed so provenance never breaks an analysis.
    """
    if not output_dir:
        return
    try:
        os.makedirs(output_dir, exist_ok=True)
        log_path = os.path.join(output_dir, RUN_LOG_FILENAME)
        lines = [
            "=" * 80,
            f"Run: {datetime.now().isoformat(timespec='seconds')}",
            f"SeqSketch: {SEQSKETCH_VERSION}",
            f"Tool: {tool}",
            f"Version: {version or 'unknown'}",
            f"Command: {subprocess.list2cmdline(list(cmd))}",
        ]
        if input_path:
            lines.append(f"Input: {input_path}")
        if output_path:
            lines.append(f"Output: {output_path}")
        if note:
            lines.append(f"Note: {note}")
        if exe:
            lines.append(f"Executable: {exe}")
        lines.append("")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except OSError:
        pass


def record_tool_run(
    output_dir: str,
    tool: str,
    exe: str,
    cmd: list[str] | tuple[str, ...],
    input_path: str = "",
    output_path: str = "",
    note: str = "",
) -> None:
    """Probe the tool version (cached) and append a run-log block."""
    append_run_log(
        output_dir,
        tool,
        probe_tool_version(exe),
        cmd,
        input_path=input_path,
        output_path=output_path,
        note=note,
        exe=exe,
    )
