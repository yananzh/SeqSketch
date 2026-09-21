"""Platform-aware discovery of the bundled external tools.

The bundled layout is deliberately NOT uniform — every tool keeps its
executable somewhere else, and the macOS bundles sometimes split by CPU
architecture. Hard-coding those names in the tab modules is what silently broke
the macOS paths, so all of it lives here instead.

========  ======================================  =========================================
tool      Windows                                 macOS
========  ======================================  =========================================
MAFFT     ``mafft-win_v7.526/mafft.bat``          ``mafft-7.526-macOS/mafft.bat``
trimAl    ``trimAl_Windows_v1.5.1/trimal.exe``    ``trimAl-1.51-MacOS-<arch>/bin/trimal``
IQ-TREE   ``iqtree-3.x-Windows/bin/iqtree3.exe``  ``iqtree-3.x-macOS/bin/iqtree3``
MUSCLE    ``muscle-win64.v5.3.exe`` (a file)      ``muscle-5.3-MacOS-<arch>`` (a file)
========  ======================================  =========================================

``<arch>`` is ``arm64`` or ``x86`` — see :func:`utils.app_paths.mac_arch`.

Every resolver follows the same order: an explicit ``config.ini`` override
wins, then the bundled copy for this platform, then a plausible path so the
caller can still raise a useful "not found" error.
"""

import os

from utils.app_paths import (
    bundled_tool_entries,
    exe_name,
    find_bundled_tool,
    mac_arch,
    platform_dir,
    resource_path,
    tool_path_from_config,
)

# MAFFT ships as a launcher script. `mafft.bat` is also the macOS launcher name
# (it is a POSIX shell script there); `mafft-signed.ps1` exists on Windows only.
_MAFFT_LAUNCHERS = ("mafft.bat", "mafft-signed.ps1")


def _mafft_launcher_relatives() -> tuple[str, ...]:
    """Launcher locations relative to a tool root.

    Includes the nested ``usr/bin/`` layout that some MAFFT zips use.
    """
    relatives = []
    for name in _MAFFT_LAUNCHERS:
        relatives.append(name)
        relatives.append(os.path.join("usr", "bin", name))
    return tuple(relatives)


def _pick(root: str, relatives) -> str | None:
    """First existing file under *root*, or None."""
    for rel in relatives:
        candidate = os.path.join(root, rel)
        if os.path.isfile(candidate):
            return candidate
    return None


def _bundled_dir(prefix: str, *, arch_split: bool = False) -> str | None:
    """Newest bundled tool folder matching *prefix*, or None.

    *arch_split* resolves the macOS ``<tool>-<version>-MacOS-<arch>`` folders
    against the running CPU. It is a no-op when a single folder matches, which
    is always the case on Windows.
    """
    matches = bundled_tool_entries(prefix, dirs=True)
    if arch_split and len(matches) > 1:
        arch = mac_arch()
        tagged = [path for path in matches if arch in os.path.basename(path)]
        if tagged:
            return tagged[-1]
    return matches[-1] if matches else None


def mafft_launcher() -> str:
    """MAFFT launcher script (``mafft.bat`` — a shell script on macOS)."""
    relatives = _mafft_launcher_relatives()
    configured = tool_path_from_config("MAFFT", "bin_dir")
    if configured:
        found = _pick(configured, relatives)
        if found:
            return found
    root = _bundled_dir("mafft")
    if root:
        found = _pick(root, relatives)
        if found:
            return found
    return os.path.join(root or find_bundled_tool("mafft"), "mafft.bat")


def trimal_executable() -> str:
    """trimAl executable (``trimal.exe`` on Windows, ``bin/trimal`` on macOS)."""
    relatives = (exe_name("trimal"), os.path.join("bin", exe_name("trimal")))
    configured = tool_path_from_config("TrimAl", "bin_dir")
    if configured:
        found = _pick(configured, relatives)
        if found:
            return found
    root = _bundled_dir("trimAl", arch_split=True)
    if root:
        found = _pick(root, relatives)
        if found:
            return found
    return os.path.join(root or find_bundled_tool("trimAl"), exe_name("trimal"))


def iqtree_executable() -> str:
    """IQ-TREE executable — ``bin/`` on both platforms, ``.exe`` on Windows."""
    name = exe_name("iqtree3")
    configured = tool_path_from_config("IQTree", "bin_dir")
    if configured:
        candidate = os.path.join(configured, name)
        if os.path.isfile(candidate):
            return candidate
    return find_bundled_tool("iqtree-", "bin", name)


def muscle_executable() -> str:
    """MUSCLE executable — a bare binary file on both platforms."""
    configured = tool_path_from_config("MUSCLE", "exe")
    if configured and os.path.isfile(configured):
        return configured
    matches = bundled_tool_entries("muscle", dirs=False)
    if len(matches) > 1:
        arch = mac_arch()
        tagged = [path for path in matches if arch in os.path.basename(path)]
        if tagged:
            matches = tagged
    if matches:
        return matches[-1]
    return os.path.join(resource_path("softwares", platform_dir()), exe_name("muscle"))
