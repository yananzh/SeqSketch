"""Collect the licence texts of the Python packages bundled into the app.

The packaged application embeds third-party Python packages, several of which
are GPL licensed. GPL-3 requires the licence text to travel with the work, so
the texts are collected into ``third_party_licenses/`` and bundled by
``SeqSketch.spec``.

Re-run after upgrading a dependency::

    python scripts/collect_licenses.py

``--check`` re-collects into a temporary directory and verifies the committed
copies still match the installed packages, without writing anything.
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
import tempfile
from importlib.metadata import distributions
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "third_party_licenses"

# Packages that end up inside the PyInstaller build. Keep in sync with
# requirements.txt when a dependency is added or removed.
BUNDLED_PACKAGES = (
    "PyQt6",
    "PyQt6-Qt6",
    "biopython",
    "logomaker",
    "matplotlib",
    "numpy",
    "pandas",
    "patchworklib",
    "Pillow",
    "primer3-py",
    "pyMSAviz",
    "requests",
    "sangerseq-viewer",
    "scipy",
    "toytree",
)

_LICENCE_NAMES = ("LICENSE", "LICENSE.txt", "LICENSE.rst", "COPYING", "NOTICE")


def _installed(name: str):
    """Return the installed distribution called *name*, or ``None``."""
    wanted = name.lower().replace("-", "_")
    for dist in distributions():
        current = (dist.metadata["Name"] or "").lower().replace("-", "_")
        if current == wanted:
            return dist
    return None


def _licence_files(dist) -> list[tuple[Path, Path]]:
    """Return ``(relative name, source path)`` for *dist*'s licence files.

    ``locate_file("")`` resolves to the site-packages root rather than to the
    metadata directory, so the recorded file list is the reliable starting
    point: licence texts appear there as ``<name>.dist-info/licenses/...`` or as
    a bare ``LICENSE``/``COPYING``/``NOTICE`` beside ``METADATA``.
    """
    found: list[tuple[Path, Path]] = []
    for entry in dist.files or []:
        parts = list(entry.parts)
        if len(parts) < 2 or not parts[0].lower().endswith(".dist-info"):
            continue
        tail = parts[1:]
        head = tail[0].lower()
        if head == "licenses":
            relative = Path(*tail[1:]) if len(tail) > 1 else Path("LICENSE")
        elif head.startswith("license") or head in ("copying", "notice"):
            relative = Path(*tail)
        else:
            continue
        source = Path(dist.locate_file(entry))
        if source.is_file():
            found.append((relative, source))
    return sorted(found)


def collect_into(target: Path) -> tuple[list[str], list[str]]:
    """Write every bundled package's licence text under *target*.

    Returns ``(written, missing)``, where *missing* lists installed packages
    that expose no licence file.
    """
    written: list[str] = []
    missing: list[str] = []
    python_dir = target / "python"

    for name in BUNDLED_PACKAGES:
        dist = _installed(name)
        if dist is None:
            missing.append(f"{name} (not installed)")
            continue
        licences = _licence_files(dist)
        if not licences:
            missing.append(f"{name} (no licence file in metadata)")
            continue

        folder = f"{dist.metadata['Name']}-{dist.version}"
        for relative, source in licences:
            destination = python_dir / folder / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            written.append(str(destination.relative_to(target)).replace("\\", "/"))

    return sorted(written), missing


def _compare(committed: Path, fresh: Path) -> list[str]:
    """Return a list of differences between the committed and fresh trees."""
    problems: list[str] = []

    def relative_files(root: Path) -> set[str]:
        if not root.is_dir():
            return set()
        return {
            str(path.relative_to(root)).replace("\\", "/")
            for path in root.rglob("*")
            if path.is_file()
        }

    committed_files = relative_files(committed)
    fresh_files = relative_files(fresh)

    for name in sorted(fresh_files - committed_files):
        problems.append(f"missing from third_party_licenses/: {name}")
    for name in sorted(committed_files - fresh_files):
        problems.append(f"no longer produced by any dependency: {name}")
    for name in sorted(committed_files & fresh_files):
        if not filecmp.cmp(committed / name, fresh / name, shallow=False):
            problems.append(f"differs from the installed package: {name}")

    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the committed copies instead of writing them",
    )
    args = parser.parse_args(argv)

    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            fresh = Path(tmp)
            _, missing = collect_into(fresh)
            problems = _compare(OUTPUT_DIR, fresh)
        for name in missing:
            problems.append(f"no licence collected for {name}")
        if problems:
            print("third_party_licenses/ is out of date:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            print("\nRun: python scripts/collect_licenses.py", file=sys.stderr)
            return 1
        count = sum(1 for path in OUTPUT_DIR.rglob("*") if path.is_file())
        print(f"third_party_licenses/ is up to date ({count} files).")
        return 0

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    written, missing = collect_into(OUTPUT_DIR)

    for name in written:
        print(f"  {name}")
    print(f"Collected {len(written)} licence files into {OUTPUT_DIR.name}/.")
    for name in missing:
        print(f"WARNING: no licence file found for {name}", file=sys.stderr)
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
