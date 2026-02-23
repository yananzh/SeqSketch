import os
import configparser

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.ini")
CONFIG_SECTION = "BLAST"
CONFIG_KEY = "bin_dir"

# Bundled BLAST+ binary shipped with the application
_BUNDLED_BIN = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "softwares",
    "ncbi-blast-2.16.0+",
    "bin",
)


def get_blast_bin_dir() -> str | None:
    """Return configured BLAST+ bin dir, auto-detecting the bundled copy if needed."""
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE, encoding="utf-8")
        if CONFIG_SECTION in config and CONFIG_KEY in config[CONFIG_SECTION]:
            stored = config[CONFIG_SECTION][CONFIG_KEY]
            if stored and os.path.isdir(stored):
                return stored
    # Fall back to bundled BLAST
    if os.path.isdir(_BUNDLED_BIN):
        set_blast_bin_dir(_BUNDLED_BIN)
        return _BUNDLED_BIN
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
