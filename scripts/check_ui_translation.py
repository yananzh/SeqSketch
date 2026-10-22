"""Report visible UI text that stays English while zh-CN is active.

Usage::

    py scripts/check_ui_translation.py                  # every discoverable tab
    py scripts/check_ui_translation.py CodonUsageTab    # one class
    py scripts/check_ui_translation.py --help-pages     # zh help-page coverage
    py scripts/check_ui_translation.py --include-combos # include combo items

The check instantiates each tab twice (English, then zh-CN), shows it offscreen,
and compares the visible text of both instances. Static, translatable combo-box
options are included; --include-combos also inspects user-data combo boxes.
"""

import argparse
import importlib
import inspect
import os
import pkgutil
import re
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PyQt6.QtWidgets import (  # noqa: E402
    QAbstractButton,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTableWidget,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QWidget,
)

from utils.i18n import (  # noqa: E402
    configure_matplotlib_fonts,
    help_slug,
    install_ui_translator,
    language_pack,
    set_active_language,
)

_LETTER = re.compile(r"[A-Za-z]")
_NON_TEXT = [
    re.compile(r"^[A-Za-z]:[\\/]"),  # Windows path
    re.compile(r"^[\\/]"),  # POSIX path
    re.compile(r"^[\w.-]+\.(?:fasta|fa|fna|faa|ffn|fastq|txt|csv|tsv|xlsx|xls|png|svg|pdf|json|html|htm|treefile|log|ini|cfg|zip)$", re.I),
    re.compile(r"^[A-Za-z0-9_.-]+$"),  # bare identifiers / snake_case keys
    re.compile(r"^[ACGTUNacgtun\s]{12,}$"),  # nucleotide sequence
    re.compile(r"^[A-Z]{6,}$"),  # acronym-only labels
]
EXTRA_CLASSES = {
    "SangerTab",
    "SangerViewerTab",
    "PrimerDesignTab",
    "PrimerAnalysisTab",
    "CodonUsageTab",
    "BookmarkManager",
}
# Scientific names, cited preset names and format identifiers stay unchanged.
_TECHNICAL_CHOICES = {
    "6 (TSV)", "5 (XML)", "E. coli K-12", "S. cerevisiae", "C. elegans",
    "A. thaliana", "M. musculus", "Gardiner-Garden & Frommer 1987",
    "Takai & Jones 2002", "Jukes-Cantor (JC69)", "CSV (.csv)", "TSV (.tsv)",
    "Excel (.xlsx)", "Engelman (GES)", "UFBoot + SH-aLRT",
}


def _instantiable_no_args(cls) -> bool:
    try:
        params = list(inspect.signature(cls.__init__).parameters.values())[1:]
    except (TypeError, ValueError):
        return False
    return all(
        p.default is not inspect.Parameter.empty
        or p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        for p in params
    )


def tab_classes() -> dict:
    import modules
    from utils.common_components import BaseTabWidget

    classes = {}
    for mod_info in pkgutil.iter_modules(modules.__path__):
        mod = importlib.import_module(f"modules.{mod_info.name}")
        for name, obj in vars(mod).items():
            if (
                inspect.isclass(obj)
                and obj.__module__ == mod.__name__
                and (issubclass(obj, BaseTabWidget) or name in EXTRA_CLASSES)
            ):
                classes[name] = obj
    return {n: c for n, c in classes.items() if _instantiable_no_args(c)}


def _visible(widget, root) -> bool:
    return widget.isVisibleTo(root)


def collect(root: QWidget, include_combos: bool) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []

    def add(kind: str, text: str, index=0) -> None:
        if isinstance(text, str) and text.strip():
            rows.append((kind, str(index), text))

    add("windowTitle", root.windowTitle())
    for kind, cls in (
        ("label", QLabel),
        ("button", QAbstractButton),
        ("group", QGroupBox),
        ("lineedit", QLineEdit),
        ("textedit", QTextEdit),
        ("plaintext", QPlainTextEdit),
    ):
        for index, widget in enumerate(root.findChildren(cls)):
            if not _visible(widget, root):
                continue
            if kind == "label":
                add(kind, widget.text(), index)
            elif kind == "button":
                add(kind, widget.text(), index)
            elif kind == "group":
                add(kind, widget.title(), index)
            else:
                add(kind, widget.placeholderText(), index)
    for index, spin in enumerate(root.findChildren(QAbstractSpinBox)):
        if _visible(spin, root):
            add("spin-special", spin.specialValueText(), index)
    for index, tabs in enumerate(root.findChildren(QTabWidget)):
        if _visible(tabs, root):
            for page in range(tabs.count()):
                add("tab", tabs.tabText(page), f"{index}:{page}")
    for index, combo in enumerate(root.findChildren(QComboBox)):
        if _visible(combo, root):
            add("combo-placeholder", combo.placeholderText(), index)
            if include_combos or combo.property("translateItems"):
                for item in range(combo.count()):
                    add("combo-item", combo.itemText(item), f"{index}:{item}")
    for index, table in enumerate(root.findChildren(QTableWidget)):
        if _visible(table, root):
            for column in range(table.columnCount()):
                item = table.horizontalHeaderItem(column)
                if item is not None:
                    add("table-header", item.text(), f"{index}:{column}")
    for index, tree in enumerate(root.findChildren(QTreeWidget)):
        if _visible(tree, root):
            header = tree.headerItem()
            if header is not None:
                for column in range(tree.columnCount()):
                    add("tree-header", header.text(column), f"{index}:{column}")
    for index, widget in enumerate(root.findChildren(QWidget)):
        if _visible(widget, root) and widget.toolTip():
            add("tooltip", widget.toolTip(), index)
    return rows


def snapshot(cls, language: str, include_combos: bool):
    set_active_language(language)
    configure_matplotlib_fonts(language)
    tab = cls()
    tab.show()
    QApplication.processEvents()
    rows = collect(tab, include_combos=include_combos)
    tab.close()
    tab.deleteLater()
    QApplication.processEvents()
    return rows


def untranslated(cls_name: str, cls, include_combos: bool) -> list[tuple[str, str]]:
    pack = language_pack("zh-CN")
    english = snapshot(cls, "en", include_combos)
    chinese = snapshot(cls, "zh-CN", include_combos)
    zh_map = {(kind, index): text for kind, index, text in chinese}
    missing = []
    for kind, index, text in english:
        if zh_map.get((kind, index)) != text:
            continue
        if kind == "combo-item" and text in _TECHNICAL_CHOICES:
            continue
        if text in pack.exact:
            # Deliberately identical translation (units, acronyms, product names).
            continue
        if not _LETTER.search(text) or any(p.match(text) for p in _NON_TEXT):
            continue
        missing.append((kind, text))
    set_active_language("en")
    return missing


def check_help_pages(app) -> list[str]:
    set_active_language("zh-CN")
    configure_matplotlib_fonts("zh-CN")
    original_exec = QDialog.exec
    QDialog.exec = lambda self: 0
    missing = []
    try:
        for name, cls in tab_classes().items():
            try:
                tab = cls()
            except Exception as exc:  # pragma: no cover - diagnostic
                print(f"skip {name}: {exc}")
                continue
            before = {id(w) for w in tab.findChildren(QDialog)}
            triggered = False
            for method_name in ("show_help", "_show_help", "show_help_dialog"):
                method = getattr(tab, method_name, None)
                if callable(method):
                    method()
                    triggered = True
                    break
            if not triggered:
                tab.deleteLater()
                continue
            dialog = next((d for d in tab.findChildren(QDialog) if id(d) not in before), None)
            if dialog is None:
                tab.deleteLater()
                continue
            title = dialog.windowTitle()
            path = os.path.join(
                ROOT, "resources", "i18n", "zh-CN", "help", help_slug(title) + ".html"
            )
            if not os.path.isfile(path):
                missing.append(f"{name}: {title!r} -> {os.path.basename(path)}")
            dialog.deleteLater()
            tab.deleteLater()
    finally:
        QDialog.exec = original_exec
        set_active_language("en")
    return missing


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("classes", nargs="*")
    parser.add_argument("--include-combos", action="store_true")
    parser.add_argument("--help-pages", action="store_true")
    args = parser.parse_args(argv)

    app = QApplication.instance() or QApplication([])
    install_ui_translator(app)

    if args.help_pages:
        missing = check_help_pages(app)
        for row in missing:
            print(f"MISSING HELP  {row}")
        print(f"{len(missing)} help page(s) missing zh-CN bodies")
        return 1 if missing else 0

    classes = tab_classes()
    if args.classes:
        unknown = [name for name in args.classes if name not in classes]
        if unknown:
            parser.error(f"unknown tab classes: {unknown}")
        classes = {name: classes[name] for name in args.classes}

    total = 0
    for name, cls in classes.items():
        missing = untranslated(name, cls, args.include_combos)
        total += len(missing)
        if not missing:
            print(f"OK    {name}")
            continue
        print(f"TODO  {name}: {len(missing)} untranslated")
        for kind, text in missing:
            print(f"        {kind:16s} {text[:110]!r}")
    print(f"{total} untranslated visible string(s) across {len(classes)} tab(s)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
