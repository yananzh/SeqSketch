"""Every tab's help dialog follows the shared style contract.

Checked for all discoverable tabs (offscreen, dialog exec neutralized):
- window title starts with ``Help - ``
- body has one ``<h2>`` main heading that includes an em-dash tagline
- body has a ``Quick Start`` section (beginner baseline)
- body contains no CJK characters (UI language is English)
"""

import importlib
import inspect
import os
import pkgutil
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QTextBrowser  # noqa: E402

_CJK = re.compile(r"[\u4e00-\u9fff]")


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


def _tab_classes():
    import modules
    from utils.common_components import BaseTabWidget

    extra_names = {
        "SangerTab",
        "SangerViewerTab",
        "PrimerDesignTab",
        "PrimerAnalysisTab",
        "CodonUsageTab",
        "BookmarkManager",
    }
    classes = {}
    for mod_info in pkgutil.iter_modules(modules.__path__):
        mod = importlib.import_module(f"modules.{mod_info.name}")
        for name, obj in vars(mod).items():
            if (
                inspect.isclass(obj)
                and obj.__module__ == mod.__name__
                and (issubclass(obj, BaseTabWidget) or name in extra_names)
            ):
                classes[name] = obj
    return {n: c for n, c in classes.items() if _instantiable_no_args(c)}


def _trigger_help(tab):
    for name in ("show_help", "_show_help", "show_help_dialog"):
        method = getattr(tab, name, None)
        if callable(method):
            method()
            return True
    return False


@pytest.fixture(scope="module")
def help_dialogs(qapp):
    """Return {ClassName: (title, html)} for every tab's help dialog."""
    original_exec = QDialog.exec
    QDialog.exec = lambda self: 0  # keep dialogs modal-free in tests
    try:
        results = {}
        for name, cls in _tab_classes().items():
            tab = cls()
            before = {id(w) for w in tab.findChildren(QDialog)}
            assert _trigger_help(tab), f"{name} exposes no help method"
            dlg = next(
                (d for d in tab.findChildren(QDialog) if id(d) not in before), None
            )
            assert dlg is not None, f"{name} did not open a help dialog"
            browsers = [b for b in dlg.findChildren(QTextBrowser)]
            if browsers:
                html = browsers[0].toHtml()
            else:
                labels = [lbl.text() for lbl in dlg.findChildren(QLabel)]
                html = max(labels, key=len, default="")
            results[name] = (dlg.windowTitle(), html)
            dlg.deleteLater()
            tab.deleteLater()
        return results
    finally:
        QDialog.exec = original_exec


def test_every_tab_has_a_help_dialog(help_dialogs):
    assert len(help_dialogs) >= 35, "tab discovery found too few tabs"


def test_help_dialog_titles_are_standardized(help_dialogs):
    bad = {n: t for n, (t, _) in help_dialogs.items() if not t.startswith("Help - ")}
    assert not bad, f"non-standard titles: {bad}"


def test_help_body_has_h2_with_tagline_and_quick_start(help_dialogs):
    bad = []
    for name, (_title, html) in help_dialogs.items():
        h2 = re.search(r"<h2[^>]*>(.*?)</h2>", html, re.S)
        if not h2:
            bad.append((name, "no <h2>"))
            continue
        if "&mdash;" not in h2.group(1) and "\u2014" not in h2.group(1):
            bad.append((name, f"h2 lacks tagline: {h2.group(1)[:40]}"))
        if "Quick Start" not in html:
            bad.append((name, "no Quick Start section"))
    assert not bad, bad


def test_help_body_is_english_only(help_dialogs):
    bad = {n: t[:40] for n, (_t, t) in help_dialogs.items() if _CJK.search(t)}
    assert not bad, f"CJK characters found in help body: {bad}"
