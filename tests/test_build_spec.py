"""Validate SeqSketch.spec structure for onedir builds."""

import os
import sys

import pytest

SPEC_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "SeqSketch.spec"
)


def _spec_source() -> str:
    with open(SPEC_PATH, "r", encoding="utf-8") as fh:
        return fh.read()


def test_spec_file_exists():
    """The .spec file must exist in the project root."""
    assert os.path.isfile(SPEC_PATH), f"Missing: {SPEC_PATH}"


def test_spec_is_valid_python():
    """The .spec file must be syntactically valid Python."""
    with open(SPEC_PATH, "r", encoding="utf-8") as fh:
        source = fh.read()
    compile(source, SPEC_PATH, "exec")


def test_spec_onedir_not_onefile():
    """The spec must use onedir mode (onefile=False), not onefile."""
    with open(SPEC_PATH, "r", encoding="utf-8") as fh:
        source = fh.read()
    assert "onefile=True" not in source, "Spec must NOT use onefile=True"
    assert "COLLECT(" in source, "Spec must contain COLLECT() for onedir output"


def test_spec_bundles_softwares():
    """softwares/ must be listed in datas for bundling."""
    with open(SPEC_PATH, "r", encoding="utf-8") as fh:
        source = fh.read()
    assert "'softwares'" in source or '"softwares"' in source, (
        "softwares/ must be in datas"
    )


def test_spec_adds_tools_per_platform_not_as_a_whole_tree():
    """softwares/ is added per platform, never as the entire tree.

    Bundling the whole tree put roughly 375 MB of the other platform's
    binaries inside every distribution.
    """
    source = _spec_source()
    start = source.index("datas = [")
    static_datas = source[start : source.index("]", start)]
    assert "softwares" not in static_datas, (
        "the static datas list must not bundle all of softwares/"
    )
    assert "_SOFTWARES_PLATFORM" in source, "spec must select softwares/<platform>"


def test_spec_platform_folder_matches_app_paths():
    """The spec's platform folder must agree with utils.app_paths.platform_dir()."""
    from utils.app_paths import platform_dir

    assert f"_SOFTWARES_PLATFORM = '{platform_dir()}'" in _spec_source()


def test_spec_bundles_config_ini():
    """config.ini must be listed in datas for bundling."""
    with open(SPEC_PATH, "r", encoding="utf-8") as fh:
        source = fh.read()
    assert "'config.ini'" in source or '"config.ini"' in source, (
        "config.ini must be in datas"
    )


def test_spec_console_disabled():
    """The exe must run without a console window."""
    with open(SPEC_PATH, "r", encoding="utf-8") as fh:
        source = fh.read()
    assert "console=False" in source, "console must be False for GUI app"


def test_spec_excludes_tkinter():
    """tkinter must be excluded (not needed for PyQt6 app)."""
    with open(SPEC_PATH, "r", encoding="utf-8") as fh:
        source = fh.read()
    assert "'tkinter'" in source or '"tkinter"' in source, "tkinter must be in excludes"
