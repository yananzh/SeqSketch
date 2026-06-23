"""Shared loader for bundled teaching example data.

Single read-only source under ``examples/`` (resolved via ``resource_path`` so
it works in dev and in PyInstaller onedir builds). File-mode tabs stage a
writable copy in ``user_data_dir()/example_work/``; sequence-mode tabs read
the text directly.
"""

import os
import shutil

from utils.app_paths import resource_path, user_data_dir


def example_path(*parts: str) -> str:
    """Absolute path to a bundled example file (read-only source)."""
    return resource_path("examples", *parts)


def stage_example(*parts: str, dest_dir: str | None = None) -> str | None:
    """Copy a bundled example file to a writable dir; return the copy path.

    dest_dir defaults to ``user_data_dir()/example_work/``. Overwrites an
    existing copy. Returns None if the source is missing or the copy fails
    (caller falls back to the read-only :func:`example_path`).
    """
    src = example_path(*parts)
    if not os.path.isfile(src):
        return None
    target_dir = dest_dir or os.path.join(user_data_dir(), "example_work")
    try:
        os.makedirs(target_dir, exist_ok=True)
        dest = os.path.join(target_dir, os.path.basename(src))
        shutil.copy2(src, dest)
        return dest
    except OSError:
        return None


def load_example_text(*parts: str) -> str:
    """Read a bundled example file as text. Returns '' on failure."""
    src = example_path(*parts)
    try:
        with open(src, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""
