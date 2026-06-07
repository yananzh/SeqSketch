import configparser
import os
import sys


APP_NAME = "BioSeqAnalyzer"


def runtime_root() -> str:
    """Return the root path that contains bundled runtime resources."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return str(sys._MEIPASS)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(*parts: str) -> str:
    """Build a path inside the runtime resource root."""
    return os.path.join(runtime_root(), *parts)


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
    """
    if getattr(sys, "frozen", False):
        config_path = os.path.join(portable_root(), "config.ini")
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
    except Exception:
        pass
    return None
