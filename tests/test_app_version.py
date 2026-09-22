"""App version lives outside modules/ so importing the package has no Qt cost."""

import ast
import os
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW = REPO_ROOT / "main_window.py"
MODULES_INIT = REPO_ROOT / "modules" / "__init__.py"


def test_app_version_constant():
    from utils.app_version import APP_VERSION

    assert APP_VERSION == "1.0.0"


def test_modules_init_has_no_eager_imports_or_version():
    source = MODULES_INIT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = [
        node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.Assign))
    ]
    assert imports == [], "modules/__init__.py must not import tabs or define version"


def test_importing_modules_does_not_load_tabs():
    """Import the package in a subprocess so sys.modules stays clean here."""
    code = (
        "import sys; import modules; "
        "assert 'modules.amino_acid_composition_tab' not in sys.modules, "
        "'importing modules pulled in a Qt tab'; "
        "assert 'PyQt6' not in sys.modules, 'importing modules pulled in PyQt6'; "
        "print('ok')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


def test_from_modules_import_blast_config_still_works():
    from modules import blast_config

    assert blast_config.get_blast_bin_dir is not None


def test_about_and_update_dialogs_use_app_version():
    source = MAIN_WINDOW.read_text(encoding="utf-8")
    assert "from utils.app_version import APP_VERSION" in source
    assert "APP_VERSION" in source
    assert "Version 1.0.0" not in source
    assert "v1.0.0" not in source
