"""List UI string literals that have no translation in a language pack.

Usage: py scripts/extract_ui_strings.py [--language zh-CN] [--summary] [--all] [files ...]
Each line prints a JSON-encoded key, ready to paste into a pack file.
"""

import argparse
import ast
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from utils.i18n import language_pack, tr_ui  # noqa: E402

UI_CALLS = {
    "QAction",
    "QCheckBox",
    "QGroupBox",
    "QLabel",
    "QMenu",
    "QPushButton",
    "QRadioButton",
    "QToolButton",
    "_find_or_open",
    "_set_status",
    "_show_help",
    "addAction",
    "addButton",
    "addMenu",
    "addTab",
    "critical",
    "getExistingDirectory",
    "getOpenFileName",
    "getOpenFileNames",
    "getSaveFileName",
    "information",
    "log_message",
    "question",
    "setHeaderLabels",
    "setHorizontalHeaderLabels",
    "setInformativeText",
    "setPlaceholderText",
    "setStatusTip",
    "setTabText",
    "setText",
    "setTitle",
    "setToolTip",
    "setWindowTitle",
    "show_help_dialog",
    "show_status",
    "showMessage",
    "warning",
}
_LETTER = re.compile(r"[A-Za-z]")
_SOURCE_GLOBS = ["modules/*.py", "utils/*.py", "menus.py", "main_window.py", "main.py"]


def _literals(node):
    """Yield (text, dynamic) for each string literal under an argument node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value, False
    elif isinstance(node, ast.JoinedStr):
        text = "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in node.values)
        yield text, True
    else:
        for child in ast.iter_child_nodes(node):
            yield from _literals(child)


def scan_file(path: str) -> list[tuple[int, str, bool]]:
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)
    found: dict[tuple[str, bool], int] = {}
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name not in UI_CALLS:
            continue
        args = call.args[:1] if name == "log_message" else call.args
        for arg in [*args, *(kw.value for kw in call.keywords)]:
            for text, dynamic in _literals(arg):
                if len(text.strip()) >= 2 and _LETTER.search(text):
                    found.setdefault((text, dynamic), call.lineno)
    return sorted((line, text, dynamic) for (text, dynamic), line in found.items())


def is_translated(text: str, dynamic: bool, language: str) -> bool:
    sample = text.replace("{}", "x") if dynamic else text
    return sample in language_pack(language).exact or tr_ui(sample, language) != sample


def default_files() -> list[str]:
    paths = []
    for pattern in _SOURCE_GLOBS:
        paths.extend(glob.glob(os.path.join(ROOT, pattern)))
    return sorted(paths)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*")
    parser.add_argument("--language", default="zh-CN")
    parser.add_argument("--summary", action="store_true", help="print per-file counts only")
    parser.add_argument("--all", action="store_true", help="also list translated strings")
    args = parser.parse_args(argv)

    paths = [os.path.abspath(p) for p in args.files] or default_files()
    total = missing = 0
    for path in paths:
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        rows = scan_file(path)
        pending = [r for r in rows if not is_translated(r[1], r[2], args.language)]
        total += len(rows)
        missing += len(pending)
        if args.summary:
            if pending:
                print(f"{len(pending):4d} / {len(rows):4d}  {rel}")
            continue
        shown = rows if args.all else pending
        if shown:
            print(rel)
            for line, text, dynamic in shown:
                tag = "[dynamic] " if dynamic else ""
                print(f"  L{line}  {tag}{json.dumps(text, ensure_ascii=False)}")
    print(f"{missing} of {total} UI literals have no {args.language} translation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
