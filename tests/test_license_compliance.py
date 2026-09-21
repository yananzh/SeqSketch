"""Guards for the third-party licence compliance of the published downloads.

Two properties have to stay true for SeqSketch to be publishable:

* every bundled external tool carries its licence text, so the conditions travel
  with the download;
* the repository documents every third-party component, including the PyQt6
  ``GPL-3.0-only`` constraint that rules out a permissive project licence.

The tool-bundle checks skip themselves when ``softwares/`` has not been
downloaded (which is the case on CI).
"""

import os
import re

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOFTWARES = os.path.join(REPO_ROOT, "softwares")
NOTICES = os.path.join(REPO_ROOT, "THIRD-PARTY-NOTICES.md")
README = os.path.join(REPO_ROOT, "README.MD")
SPEC = os.path.join(REPO_ROOT, "SeqSketch.spec")
COLLECTOR = os.path.join(REPO_ROOT, "scripts", "collect_licenses.py")
PYTHON_LICENCES = os.path.join(REPO_ROOT, "third_party_licenses", "python")
LICENCE = os.path.join(REPO_ROOT, "LICENSE")
VERSION_RESOURCE = os.path.join(REPO_ROOT, "version_info.txt")
MAIN_WINDOW = os.path.join(REPO_ROOT, "main_window.py")
BUILD_SCRIPT = os.path.join(REPO_ROOT, "scripts", "build_onedir.ps1")

# Tool folder prefix -> the licence files that must accompany it. MAFFT needs
# two: the BSD text for the core, plus the notices for the extension components.
_TOOL_LICENCES = {
    "ncbi-blast-": ("LICENSE",),
    "mafft": ("MAFFT-LICENSE.txt", "MAFFT-EXTENSIONS-NOTICE.txt"),
    "iqtree-": ("LICENSE",),
    "trimal": ("LICENSE",),
    "muscle": ("MUSCLE-LICENSE.txt",),
}

# Markers proving the shipped file is the actual licence rather than a stub.
_TOOL_LICENCE_MARKERS = {
    "ncbi-blast-": ("PUBLIC DOMAIN NOTICE",),
    "mafft": (
        "Copyright (c) 2002-2007 Kazutaka Katoh",
        "Redistribution and use in source and binary forms",
    ),
    "iqtree-": ("GNU GENERAL PUBLIC LICENSE", "Version 2"),
    "trimal": ("GNU GENERAL PUBLIC LICENSE", "Version 3"),
    "muscle": ("GNU GENERAL PUBLIC LICENSE", "Version 3"),
}

_TOOL_UPSTREAMS = {
    "NCBI BLAST+": "ftp.ncbi.nlm.nih.gov/blast",
    "MAFFT": "mafft.cbrc.jp",
    "IQ-TREE": "github.com/iqtree/iqtree3",
    "trimAl": "github.com/scapella/trimal",
    "MUSCLE": "github.com/rcedgar/muscle",
}

# Packages with copyleft obligations among the bundled dependencies.
_COPYLEFT_PACKAGES = (
    "PyQt6",
    "PyQt6-Qt6",
    "primer3-py",
    "patchworklib",
    "toytree",
    "sangerseq-viewer",
)


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _flat(path: str) -> str:
    """File text with runs of whitespace collapsed, so assertions survive rewrapping."""
    return " ".join(_read(path).split())


# Collected folders are named "<Name>-<Version>", where the version starts with a
# digit. Matching on the name alone would make PyQt6 and PyQt6-Qt6 ambiguous.
_FOLDER_RE = re.compile(r"^(?P<name>.+?)-(?P<version>\d[^-]*)$")


def _python_licence_dir(package: str) -> str:
    if not os.path.isdir(PYTHON_LICENCES):
        return ""
    for name in sorted(os.listdir(PYTHON_LICENCES)):
        match = _FOLDER_RE.match(name)
        if match and match.group("name").lower() == package.lower():
            return os.path.join(PYTHON_LICENCES, name)
    return ""


def _requirement_for(entry_name: str):
    """Map a tool entry to the licence files it needs, ignoring the files themselves."""
    lowered = entry_name.lower()
    if "license" in lowered or lowered.startswith(("notice", "copying")):
        return None
    for prefix, required in _TOOL_LICENCES.items():
        if lowered.startswith(prefix):
            return prefix, required
    return None


def _platform_dirs() -> list[str]:
    return [name for name in ("windows", "Mac") if os.path.isdir(os.path.join(SOFTWARES, name))]


def _find_licence(platform_dir: str, entry: str, filename: str):
    """Look for *filename* inside the tool folder, then beside it."""
    for candidate in (
        os.path.join(SOFTWARES, platform_dir, entry, filename),
        os.path.join(SOFTWARES, platform_dir, filename),
    ):
        if os.path.isfile(candidate):
            return candidate
    return None


# ── Repository documentation ─────────────────────────────────────────────────


def test_third_party_notices_exist():
    assert os.path.isfile(NOTICES), "THIRD-PARTY-NOTICES.md must exist in the repo root"


def test_notices_cover_every_bundled_tool():
    text = _flat(NOTICES)
    for name, upstream in _TOOL_UPSTREAMS.items():
        assert name in text, f"THIRD-PARTY-NOTICES.md must document {name}"
        assert upstream in text, f"THIRD-PARTY-NOTICES.md must link {name}'s upstream source"


def test_notices_state_the_gpl_source_offer():
    text = _flat(NOTICES)
    assert "Corresponding source" in text
    assert "github.com/yananzh/SeqSketch/issues" in text


def test_notices_explain_the_project_licence():
    """The GPL-3.0 choice, and the PyQt6 reason for it, must stay documented."""
    text = _flat(NOTICES)
    assert "GPL-3.0-only" in text
    assert "PyQt6" in text
    assert "GNU General Public License, version 3" in text
    assert "or-later" in text, "the primer3 GPL-2/GPL-3 compatibility note must stay"
    assert "modified versions must also be released under GPL-3.0" in text


def test_notices_note_the_mafft_no_fee_condition():
    text = _flat(NOTICES)
    assert "not redistributed for any fee" in text


def test_readme_documents_licensing_and_source():
    readme = _flat(README)
    assert "许可与来源" in readme
    assert "THIRD-PARTY-NOTICES.md" in readme
    assert "GPL-3.0-only" in readme


def test_readme_does_not_claim_a_permissive_project_licence():
    """MIT is incompatible with the bundled PyQt6, so it must not be declared."""
    readme = _read(README)
    assert "License: MIT" not in readme
    assert "MIT License" not in readme


# ── Project licence ──────────────────────────────────────────────────────


def test_readme_declares_gpl3():
    readme = _flat(README)
    assert "GNU General Public License v3.0" in readme
    assert "[LICENSE](LICENSE)" in readme
    assert "Copyright (C) 2026" in readme


def test_readme_notice_matches_the_declared_licence():
    """The GNU notice block must not promise a later-version option."""
    readme = _read(README)
    assert "GPL-3.0-only" in readme
    assert "任何更新版本" not in readme


def test_project_licence_file_is_the_full_gpl3():
    assert os.path.isfile(LICENCE), "LICENSE must exist in the repo root"
    text = _read(LICENCE)
    assert "GNU GENERAL PUBLIC LICENSE" in text
    assert "Version 3, 29 June 2007" in text
    assert "END OF TERMS AND CONDITIONS" in text
    assert len(text) > 30000, "the full licence text must ship, not a summary"


def test_version_resource_states_the_gpl():
    """The Windows VERSIONINFO resource used to claim MIT."""
    text = _read(VERSION_RESOURCE)
    assert "MIT License" not in text
    assert "GNU General Public License" in text


def test_about_dialog_states_the_gpl():
    """The About dialog used to claim MIT."""
    text = _read(MAIN_WINDOW)
    assert "MIT License" not in text
    assert "GPL-3.0" in text


# ── Build wiring ─────────────────────────────────────────────────────────────


def test_spec_bundles_the_licence_material():
    source = _read(SPEC)
    assert "'LICENSE'" in source, "the project licence must ship with the app"
    assert "'third_party_licenses'" in source, "collected licence texts must be bundled"
    assert "'THIRD-PARTY-NOTICES.md'" in source, "the notices must ship with the app"


def test_build_script_puts_the_licence_beside_the_launcher():
    source = _read(BUILD_SCRIPT)
    assert "'LICENSE'" in source and "'THIRD-PARTY-NOTICES.md'" in source


# ── Collected Python licences ───────────────────────────────────────


def test_collected_python_licences_cover_the_copyleft_packages():
    assert os.path.isdir(PYTHON_LICENCES), "run: python scripts/collect_licenses.py"
    for package in _COPYLEFT_PACKAGES:
        assert _python_licence_dir(package), (
            f"no collected licence for {package} (found: {sorted(os.listdir(PYTHON_LICENCES))})"
        )


@pytest.mark.parametrize(
    "package, marker",
    [
        ("PyQt6", "Version 3, 29 June 2007"),
        ("patchworklib", "Version 3, 29 June 2007"),
        ("primer3-py", "Version 2, June 1991"),
    ],
)
def test_copyleft_licence_texts_are_complete(package, marker):
    """The collected file must be the full licence, not a one-line reference."""
    folder = _python_licence_dir(package)
    assert folder, f"missing collected licences for {package}"
    text = "".join(_read(os.path.join(folder, name)) for name in sorted(os.listdir(folder)))
    assert "GNU GENERAL PUBLIC LICENSE" in text.upper()
    assert marker in text


def test_collector_lists_every_copyleft_package():
    source = _read(COLLECTOR)
    for package in _COPYLEFT_PACKAGES:
        assert f'"{package}"' in source, f"scripts/collect_licenses.py must collect {package}"


# ── Tool bundles (skipped when softwares/ is not downloaded) ─────────────────


requires_bundles = pytest.mark.skipif(
    not _platform_dirs(), reason="external tool bundles are not downloaded"
)


@requires_bundles
def test_every_bundled_tool_ships_its_licence():
    seen: set[str] = set()
    for platform_dir in _platform_dirs():
        for entry in sorted(os.listdir(os.path.join(SOFTWARES, platform_dir))):
            requirement = _requirement_for(entry)
            if requirement is None:
                continue
            prefix, filenames = requirement
            seen.add(prefix)
            for filename in filenames:
                found = _find_licence(platform_dir, entry, filename)
                assert found, f"{platform_dir}/{entry} is missing {filename}"

    missing = set(_TOOL_LICENCES) - seen
    assert not missing, f"these tools are not present under softwares/: {sorted(missing)}"


@requires_bundles
def test_tool_licences_are_the_real_licences():
    checked = 0
    for platform_dir in _platform_dirs():
        for entry in sorted(os.listdir(os.path.join(SOFTWARES, platform_dir))):
            requirement = _requirement_for(entry)
            if requirement is None:
                continue
            prefix, filenames = requirement
            path = _find_licence(platform_dir, entry, filenames[0])
            if path is None:
                continue  # reported by the presence test
            text = _read(path)
            for marker in _TOOL_LICENCE_MARKERS[prefix]:
                assert marker in text, f"{path} does not look like the real licence"
            checked += 1
    assert checked >= len(_TOOL_LICENCES)
