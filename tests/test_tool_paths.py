"""Platform-aware resolution of the bundled external tools.

``softwares/`` is gitignored, so most tests here build a fake bundle that
mirrors the real per-platform layout and redirect ``resource_path`` into it.
That way the macOS branch is exercised on any machine — the previous
implementation hard-coded Windows folder *and* executable names
(``mafft-win_v7.526``, ``trimal.exe``, ``iqtree3.exe``), which no test could
catch and which made every bundled tool unresolvable on macOS.
"""

import configparser
import glob
import os
import sys

import pytest

from utils import app_paths, tool_paths

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Layout of the shipped bundles under softwares/windows and softwares/Mac.
WINDOWS_LAYOUT = [
    "iqtree-3.1.3-Windows/bin/iqtree3.exe",
    "mafft-win_v7.526/mafft.bat",
    "mafft-win_v7.526/mafft-signed.ps1",
    "trimAl_Windows_v1.5.1/trimal.exe",
    "muscle-win64.v5.3.exe",
    "ncbi-blast-2.17.0+/bin/blastn.exe",
]

MACOS_LAYOUT = [
    "iqtree-3.1.3-macOS/bin/iqtree3",
    "mafft-7.526-macOS/mafft.bat",
    # trimAl ships flat on macOS (trimAl-1.51-MacOS-<arch>/trimal), unlike
    # Windows where trimal.exe sits next to its DLLs. Both are verified
    # against the real bundle; the bin/ variant is covered separately.
    "trimAl-1.51-MacOS-arm64/trimal",
    "trimAl-1.51-MacOS-x86/trimal",
    "muscle-5.3-MacOS-arm64",
    "muscle-5.3-MacOS-x86",
    "ncbi-blast-2.17.0-macOS/bin/blastn",
]


@pytest.fixture
def fake_bundle(tmp_path, monkeypatch):
    """Create a fake ``softwares/`` tree and redirect ``resource_path`` into it."""

    def build(layout, platform_folder):
        for relative in layout:
            target = tmp_path / "softwares" / platform_folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("", encoding="utf-8")

        def replacement(*parts):
            return str(tmp_path.joinpath(*parts))

        monkeypatch.setattr(app_paths, "resource_path", replacement)
        monkeypatch.setattr(tool_paths, "resource_path", replacement)
        return tmp_path

    return build


def test_windows_layout_resolves(fake_bundle, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    root = fake_bundle(WINDOWS_LAYOUT, "windows")
    bundle = root / "softwares" / "windows"

    assert tool_paths.mafft_launcher() == str(bundle / "mafft-win_v7.526/mafft.bat")
    assert tool_paths.trimal_executable() == str(bundle / "trimAl_Windows_v1.5.1/trimal.exe")
    assert tool_paths.iqtree_executable() == str(bundle / "iqtree-3.1.3-Windows/bin/iqtree3.exe")
    assert tool_paths.muscle_executable() == str(bundle / "muscle-win64.v5.3.exe")


def test_macos_layout_resolves(fake_bundle, monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(tool_paths, "mac_arch", lambda: "arm64")
    root = fake_bundle(MACOS_LAYOUT, "Mac")
    bundle = root / "softwares" / "Mac"

    # `mafft.bat` is a POSIX shell script in the macOS bundle — same file name.
    assert tool_paths.mafft_launcher() == str(bundle / "mafft-7.526-macOS/mafft.bat")
    assert tool_paths.trimal_executable() == str(bundle / "trimAl-1.51-MacOS-arm64/trimal")
    assert tool_paths.iqtree_executable() == str(bundle / "iqtree-3.1.3-macOS/bin/iqtree3")
    assert tool_paths.muscle_executable() == str(bundle / "muscle-5.3-MacOS-arm64")


def test_macos_arch_split_follows_running_cpu(fake_bundle, monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    fake_bundle(MACOS_LAYOUT, "Mac")

    monkeypatch.setattr(tool_paths, "mac_arch", lambda: "arm64")
    assert tool_paths.muscle_executable().endswith("muscle-5.3-MacOS-arm64")
    assert f"{os.sep}trimAl-1.51-MacOS-arm64{os.sep}" in tool_paths.trimal_executable()

    monkeypatch.setattr(tool_paths, "mac_arch", lambda: "x86")
    assert tool_paths.muscle_executable().endswith("muscle-5.3-MacOS-x86")
    assert "trimAl-1.51-MacOS-x86" in tool_paths.trimal_executable()


def test_trimal_resolves_from_a_bin_subfolder_too(fake_bundle, monkeypatch):
    """Some trimAl builds nest the executable under bin/ instead of the root."""
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(tool_paths, "mac_arch", lambda: "arm64")
    root = fake_bundle(["trimAl-1.51-MacOS-arm64/bin/trimal"], "Mac")

    assert tool_paths.trimal_executable() == str(
        root / "softwares" / "Mac" / "trimAl-1.51-MacOS-arm64/bin/trimal"
    )


def test_flat_layout_is_used_when_platform_folder_is_absent(fake_bundle, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    root = fake_bundle(["mafft-win_v7.526/mafft.bat"], "")

    assert tool_paths.mafft_launcher() == str(root / "softwares" / "mafft-win_v7.526/mafft.bat")


def test_config_override_takes_precedence(fake_bundle, monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    fake_bundle(WINDOWS_LAYOUT, "windows")

    custom = tmp_path / "custom-tools"
    custom.mkdir()
    (custom / "mafft.bat").write_text("", encoding="utf-8")
    monkeypatch.setattr(tool_paths, "tool_path_from_config", lambda section, key: str(custom))

    assert tool_paths.mafft_launcher() == str(custom / "mafft.bat")


@pytest.mark.skipif(
    not os.path.isdir(app_paths.resource_path("softwares", app_paths.platform_dir())),
    reason="bundled softwares/ is absent (gitignored; not present on CI)",
)
def test_shipped_bundle_resolves_on_this_platform():
    """Every resolver finds a real file in the bundle shipped for this platform.

    Skipped where ``softwares/`` does not exist (CI), but this is the test that
    catches a mismatch between the code and the actual bundle on a dev machine.
    """
    for name, resolver in (
        ("MAFFT", tool_paths.mafft_launcher),
        ("trimAl", tool_paths.trimal_executable),
        ("IQ-TREE", tool_paths.iqtree_executable),
        ("MUSCLE", tool_paths.muscle_executable),
    ):
        resolved = resolver()
        assert os.path.isfile(resolved), f"{name} did not resolve to a file: {resolved}"


def test_blast_bundle_is_detected_on_this_platform():
    if not os.path.isdir(app_paths.resource_path("softwares", app_paths.platform_dir())):
        pytest.skip("bundled softwares/ is absent")
    from modules import blast_config

    resolved = blast_config._detect_bundled_bin()
    assert resolved is not None, "bundled BLAST+ not detected"
    assert os.path.isfile(os.path.join(resolved, app_paths.exe_name("blastn")))


def test_config_ini_ships_no_platform_specific_paths():
    """One config.ini ships to every platform, so it must not pin a bundle path."""
    config = configparser.ConfigParser()
    config.read(os.path.join(REPO_ROOT, "config.ini"), encoding="utf-8")

    pinned = [
        (section, key, value)
        for section in config.sections()
        for key, value in config[section].items()
        if "softwares" in value.replace("\\", "/")
    ]
    assert not pinned, f"config.ini pins platform-specific tool paths: {pinned}"


# Folder and executable names that only exist on Windows. utils/tool_paths.py is
# the single place allowed to know them.
_WINDOWS_ONLY_BUNDLE_MARKERS = (
    "softwares/windows",
    "softwares\\windows",
    "softwares/Mac",
    "softwares\\Mac",
    "mafft-win_v7.526",
    "trimAl_Windows_v1.5.1",
    "muscle-win64.v5.3.exe",
    "iqtree-3.0.1-Windows",
)


def test_modules_resolve_tools_instead_of_hardcoding_bundle_names():
    """Tab modules must go through utils.tool_paths, never name a bundle folder."""
    offenders = []
    files = sorted(glob.glob(os.path.join(REPO_ROOT, "modules", "*.py")))
    assert files
    for path in files:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        offenders.extend(
            (os.path.basename(path), marker)
            for marker in _WINDOWS_ONLY_BUNDLE_MARKERS
            if marker in text
        )
    assert not offenders, f"hardcoded bundled tool names: {offenders}"
