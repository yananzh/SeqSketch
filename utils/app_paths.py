import configparser
import os
import platform
import sys

APP_NAME = "SeqSketch"


def runtime_root() -> str:
    """Return the root path that contains bundled runtime resources."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return str(sys._MEIPASS)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(*parts: str) -> str:
    """Build a path inside the runtime resource root."""
    return os.path.join(runtime_root(), *parts)


# ── Platform primitives ─────────────────────────────────────────────────────
# Bundled tools live under softwares/<platform>/. Executable names differ too:
# Windows appends ".exe", and some macOS bundles are split per CPU
# architecture. Keeping that knowledge here stops the tab modules from
# hard-coding Windows-only names (which silently broke the macOS paths).


def platform_dir() -> str:
    """Name of the softwares/ subfolder holding this platform's tools."""
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "Mac"
    return "linux"


def exe_suffix() -> str:
    """Executable extension for this platform (".exe" on Windows, else "")."""
    return ".exe" if sys.platform.startswith("win") else ""


def exe_name(base: str) -> str:
    """``"blastn"`` -> ``"blastn.exe"`` on Windows, ``"blastn"`` on macOS."""
    return base + exe_suffix()


def mac_arch() -> str:
    """Architecture tag used by the arch-split macOS bundles ("arm64"/"x86")."""
    machine = platform.machine().lower()
    return "arm64" if machine in ("arm64", "aarch64") else "x86"


def tool_search_roots() -> list[str]:
    """Bundled-tool roots, most specific first.

    The platform folder is scanned before the flat legacy root, so a stale
    flat copy can never shadow the platform one.
    """
    return [
        resource_path("softwares", platform_dir()),
        resource_path("softwares"),
    ]


def bundled_tool_entries(prefix: str, *, dirs: bool = True) -> list[str]:
    """Bundled entries under a search root whose name starts with *prefix*.

    Returns full paths, sorted by name, taken from the first root that has a
    match — the platform and flat layouts are never mixed. Empty when nothing
    matches.
    """
    for root in tool_search_roots():
        if not os.path.isdir(root):
            continue
        try:
            names = sorted(os.listdir(root))
        except OSError:
            continue
        matches = [
            os.path.join(root, name)
            for name in names
            if name.startswith(prefix) and os.path.isdir(os.path.join(root, name)) == dirs
        ]
        if matches:
            return matches
    return []


def bundled_tool_path(*parts: str) -> str:
    """Path of a bundled external tool under softwares/.

    The bundle is split per platform (softwares/windows/, softwares/Mac/);
    fall back to the historical flat layout when the split is absent so
    older checkouts keep working.
    """
    flat = resource_path("softwares", *parts)
    split = resource_path("softwares", platform_dir(), *parts)
    return split if os.path.exists(split) else flat


def find_bundled_tool(dir_prefix: str, *parts: str) -> str:
    """Locate a bundled tool folder whose directory name starts with *dir_prefix*.

    Version-numbered tool folders (e.g. ``iqtree-3.1.3-Windows``) change with
    every upgrade; matching by prefix keeps the code working without edits.
    Returns the last candidate path even if it does not exist yet, so callers
    can produce a useful error message.
    """
    matches = bundled_tool_entries(dir_prefix, dirs=True)
    if matches:
        return os.path.join(matches[-1], *parts)
    # No match: return the platform-layout path with the prefix as directory
    # name so the caller's "not found" error names a plausible location.
    return resource_path("softwares", platform_dir(), dir_prefix.rstrip("-") + "-", *parts)


def portable_root() -> str:
    """Writable-data root.  Frozen → exe directory; dev → project root."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def user_data_dir(app_name: str = APP_NAME) -> str:
    """Return writable per-user data directory, creating it if needed.

    In frozen (onedir) mode the directory lives under the exe folder so the
    whole installation stays portable.  In dev mode the legacy %APPDATA%
    location is kept for backwards compatibility.
    """
    if getattr(sys, "frozen", False):
        path = os.path.join(portable_root(), "user_data")
    else:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        path = os.path.join(base, app_name)
    os.makedirs(path, exist_ok=True)
    return path


def user_data_file(filename: str, app_name: str = APP_NAME) -> str:
    """Return writable per-user data file path."""
    return os.path.join(user_data_dir(app_name), filename)


def tool_path_from_config(section: str, key: str) -> str | None:
    """Read a tool path from config.ini in portable_root().

    Returns the resolved absolute path, or None if not configured.
    In frozen mode, tries the writable copy in portable_root() first,
    then falls back to the bundled copy in _internal/.
    """
    if getattr(sys, "frozen", False):
        writable = os.path.join(portable_root(), "config.ini")
        if os.path.isfile(writable):
            config_path = writable
        else:
            config_path = resource_path("config.ini")
    else:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.ini",
        )
    if not os.path.isfile(config_path):
        return None
    try:
        cfg = configparser.ConfigParser()
        cfg.read(config_path, encoding="utf-8")
        rel = cfg.get(section, key, fallback=None)
        if rel:
            return os.path.normpath(os.path.join(portable_root(), rel))
    except (OSError, configparser.Error):
        pass
    return None
