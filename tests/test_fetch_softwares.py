"""fetch_softwares.ps1 must accept the shipped macOS tool layout.

The Mac tools zip is packed on Windows. trimAl sits at
``trimAl-1.51-MacOS-<arch>/trimal``, not under ``bin/``. A check that only
accepts ``bin/trimal`` fails both macOS release jobs before PyInstaller runs.
"""

import os
import shutil
import subprocess
import zipfile

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "fetch_softwares.ps1")

_MAC_COMMON = [
    "ncbi-blast-2.17.0-macOS/bin/blastn",
    "iqtree-3.1.3-macOS/bin/iqtree3",
    "mafft-7.526-macOS/mafft.bat",
    "muscle-5.3-MacOS-arm64",
]


def _pwsh():
    return shutil.which("pwsh")


pytestmark = pytest.mark.skipif(_pwsh() is None, reason="pwsh is not on PATH")


def _zip_layout(tmp_path, relatives):
    root = tmp_path / "bundle"
    for relative in relatives:
        path = root.joinpath(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"tool")
    archive = tmp_path / "softwares-Mac.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        for path in root.rglob("*"):
            if path.is_file():
                handle.write(path, path.relative_to(root).as_posix())
    return archive


def _fetch(archive, target):
    return subprocess.run(
        [
            _pwsh(),
            "-NoProfile",
            "-File",
            SCRIPT,
            "-Platform",
            "Mac",
            "-Archive",
            str(archive),
            "-Target",
            str(target),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_fetch_accepts_flat_macos_trimal(tmp_path):
    archive = _zip_layout(tmp_path, _MAC_COMMON + ["trimAl-1.51-MacOS-arm64/trimal"])
    target = tmp_path / "softwares" / "Mac"

    result = _fetch(archive, target)

    assert result.returncode == 0, result.stderr
    assert (target / "trimAl-1.51-MacOS-arm64" / "trimal").is_file()
    # Windows reports every existing file as executable. On macOS this is the
    # check that BSD chmod actually ran.
    if os.name != "nt":
        assert os.access(target / "muscle-5.3-MacOS-arm64", os.X_OK)


def test_fetch_accepts_nested_macos_trimal(tmp_path):
    archive = _zip_layout(tmp_path, _MAC_COMMON + ["trimAl-1.51-MacOS-arm64/bin/trimal"])
    target = tmp_path / "softwares" / "Mac"

    result = _fetch(archive, target)

    assert result.returncode == 0, result.stderr
    assert (target / "trimAl-1.51-MacOS-arm64" / "bin" / "trimal").is_file()


def test_fetch_rejects_a_macos_bundle_without_trimal(tmp_path):
    archive = _zip_layout(tmp_path, _MAC_COMMON)
    target = tmp_path / "softwares" / "Mac"

    result = _fetch(archive, target)

    assert result.returncode != 0
    assert "trimAl" in (result.stderr + result.stdout)
