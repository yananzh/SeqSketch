"""Validate SeqSketch.spec structure for onedir builds."""

import io
import os
import struct
import sys

import pytest

SPEC_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "SeqSketch.spec")


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
    assert "'softwares'" in source or '"softwares"' in source, "softwares/ must be in datas"


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


# Element type -> the square pixel size macOS expects for that slot. Several slots
# share a pixel size; the 1x and 2x variants use different type codes.
_ICNS_SLOTS = {
    "icp4": 16,
    "icp5": 32,
    "ic11": 32,  # 16x16@2x
    "ic12": 64,  # 32x32@2x
    "ic07": 128,
    "ic13": 256,  # 128x128@2x
    "ic08": 256,
    "ic14": 512,  # 256x256@2x
    "ic09": 512,
    "ic10": 1024,  # 512x512@2x
}


# macOS needs an .icns while the repo ships .png/.ico, so the icon is generated
# once by scripts/make_icns.py and committed. A corrupt container would ship a
# generic icon or break the bundle, so the file is checked here.
def test_icns_icon_is_a_valid_container():
    from PIL import Image

    path = os.path.join(os.path.dirname(SPEC_PATH), "window_logo.icns")
    assert os.path.isfile(path), "missing - run: py scripts/make_icns.py"

    data = open(path, "rb").read()
    assert data[:4] == b"icns", "not an icns container"
    declared = struct.unpack(">I", data[4:8])[0]
    assert declared == len(data), f"header declares {declared}, file has {len(data)} bytes"

    seen = set()
    offset = 8
    while offset < len(data):
        element = data[offset : offset + 4].decode("ascii")
        length = struct.unpack(">I", data[offset + 4 : offset + 8])[0]
        assert length > 8, f"{element}: implausible chunk length {length}"
        if element in _ICNS_SLOTS:
            image = Image.open(io.BytesIO(data[offset + 8 : offset + length]))
            expected = _ICNS_SLOTS[element]
            assert image.format == "PNG", f"{element} is not PNG"
            assert image.size == (expected, expected), f"{element} is {image.size}"
            seen.add(element)
        offset += length

    assert seen == set(_ICNS_SLOTS), f"missing slots: {sorted(set(_ICNS_SLOTS) - seen)}"


def test_spec_gives_the_macos_bundle_an_icon():
    """BUNDLE does not inherit the EXE icon, so it must be passed explicitly."""
    source = _spec_source()
    assert "window_logo.icns" in source
    assert "icon=_mac_icon" in source, "BUNDLE would fall back to the generic icon"


def test_spec_bundles_config_ini():
    """config.ini must be listed in datas for bundling."""
    with open(SPEC_PATH, "r", encoding="utf-8") as fh:
        source = fh.read()
    assert "'config.ini'" in source or '"config.ini"' in source, "config.ini must be in datas"


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
