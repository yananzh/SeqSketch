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


def user_data_dir(app_name: str = APP_NAME) -> str:
    """Return writable per-user data directory, creating it if needed."""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, app_name)
    os.makedirs(path, exist_ok=True)
    return path


def user_data_file(filename: str, app_name: str = APP_NAME) -> str:
    """Return writable per-user data file path."""
    return os.path.join(user_data_dir(app_name), filename)
