import os
import configparser

from utils.app_paths import resource_path, user_data_file

_LEGACY_CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.ini")
CONFIG_FILE = user_data_file("config.ini")
CONFIG_SECTION = "BLAST"
CONFIG_KEY = "bin_dir"


def _version_key(name: str) -> tuple[int, ...]:
    nums = []
    current = ""
    for ch in name:
        if ch.isdigit():
            current += ch
        elif current:
            nums.append(int(current))
            current = ""
    if current:
        nums.append(int(current))
    return tuple(nums)


def _detect_bundled_bin() -> str | None:
    softwares_dir = resource_path("softwares")
    if not os.path.isdir(softwares_dir):
        return None

    candidates: list[str] = []
    try:
        for name in os.listdir(softwares_dir):
            if not name.startswith("ncbi-blast-"):
                continue
            bin_dir = os.path.join(softwares_dir, name, "bin")
            if os.path.isfile(os.path.join(bin_dir, "blastn.exe")):
                candidates.append(bin_dir)
    except Exception:
        return None

    if not candidates:
        return None

    candidates.sort(key=lambda p: _version_key(os.path.basename(os.path.dirname(p))), reverse=True)
    return candidates[0]


def get_blast_bin_dir() -> str | None:
    """Return configured BLAST+ bin dir, auto-detecting the bundled copy if needed."""
    config = configparser.ConfigParser()

    for cfg_path in (CONFIG_FILE, _LEGACY_CONFIG_FILE):
        if os.path.exists(cfg_path):
            config.read(cfg_path, encoding="utf-8")
            if CONFIG_SECTION in config and CONFIG_KEY in config[CONFIG_SECTION]:
                stored = config[CONFIG_SECTION][CONFIG_KEY]
                if stored and os.path.isdir(stored):
                    if cfg_path != CONFIG_FILE:
                        set_blast_bin_dir(stored)
                    return stored

    # Fall back to bundled BLAST
    bundled = _detect_bundled_bin()
    if bundled and os.path.isdir(bundled):
        set_blast_bin_dir(bundled)
        return bundled

    return None


def set_blast_bin_dir(bin_dir: str) -> None:
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE, encoding="utf-8")
    if CONFIG_SECTION not in config:
        config[CONFIG_SECTION] = {}
    config[CONFIG_SECTION][CONFIG_KEY] = bin_dir
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        config.write(f)
