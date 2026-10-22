"""Runtime UI translation. Source literals stay English; packs live in resources/i18n."""

import glob
import json
import os
import re
import weakref
from dataclasses import dataclass, field
from types import MethodType

from PyQt6.QtCore import QEvent, QLibraryInfo, QObject, QSignalBlocker, Qt, QTranslator
from PyQt6.QtWidgets import (
    QAbstractButton,
    QAbstractSpinBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QToolButton,
    QTreeWidget,
    QWidget,
)

from config.settings import Settings
from utils.app_paths import resource_path

DEFAULT_LANGUAGE = "en"
LANGUAGES = {"en": "English", "zh-CN": "简体中文"}
_PLACEHOLDER = re.compile(r"\{([A-Za-z_]\w*)\}")
_active = DEFAULT_LANGUAGE
_packs: dict[str, "LanguagePack"] = {}
_COMBO_SOURCE_ROLE = Qt.ItemDataRole.UserRole + 173


def combo_value(combo: QComboBox) -> str:
    """Return the source option, independently of its translated display label."""
    source = combo.currentData(_COMBO_SOURCE_ROLE)
    return source if source is not None and not combo.isEditable() else combo.currentText()


def find_combo_value(combo: QComboBox, source: str) -> int:
    index = combo.findData(source, _COMBO_SOURCE_ROLE)
    return index if index >= 0 else combo.findText(source)


def set_combo_value(combo: QComboBox, source: str) -> None:
    index = find_combo_value(combo, source)
    if index >= 0:
        combo.setCurrentIndex(index)
    elif combo.isEditable():
        combo.setEditText(source)


def localize_combo_items(combo: QComboBox) -> None:
    """Translate opted-in options, preserving userData and the source identity."""
    if not combo.property("translateItems") or combo.isEditable():
        return
    keys = combo.property("itemTranslationKeys") or {}
    with QSignalBlocker(combo):
        for index in range(combo.count()):
            source = combo.itemData(index, _COMBO_SOURCE_ROLE)
            if source is None:
                source = combo.itemText(index)
                combo.setItemData(index, source, _COMBO_SOURCE_ROLE)
            display = source if _active == DEFAULT_LANGUAGE else tr_ui(keys.get(source, source))
            combo.setItemText(index, display)


def enable_combo_translation(
    combo: QComboBox, *, translation_keys: dict[str, str] | None = None,
) -> QComboBox:
    """Opt static UI choices into translation; never use for user-supplied data."""
    combo.setProperty("translateItems", True)
    if translation_keys:
        combo.setProperty("itemTranslationKeys", translation_keys)
    # New options (e.g. DNA/protein distance models) can be populated after Show.
    reference = weakref.ref(combo)

    def inserted(*_):
        widget = reference()
        if widget is not None:
            localize_combo_items(widget)

    combo.model().rowsInserted.connect(inserted)
    localize_combo_items(combo)
    return combo


def connect_combo_source(combo: QComboBox, slot) -> None:
    """Connect a text callback that expects the canonical English option."""
    reference = weakref.ref(combo)
    # Match PyQt's weak ownership of bound slots. Capturing a bound method in
    # a lambda would retain its tab and Qt children through native teardown.
    slot_reference = weakref.WeakMethod(slot) if isinstance(slot, MethodType) else lambda: slot

    def changed(_text):
        widget, callback = reference(), slot_reference()
        if widget is not None and callback is not None:
            callback(combo_value(widget))

    combo.currentTextChanged.connect(changed)


@dataclass
class LanguagePack:
    exact: dict[str, str] = field(default_factory=dict)
    patterns: list[tuple[re.Pattern[str], list[str], str]] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def normalize_language(value) -> str:
    return value if isinstance(value, str) and value in LANGUAGES else DEFAULT_LANGUAGE


def active_language() -> str:
    return _active


def set_active_language(code) -> None:
    global _active
    _active = normalize_language(code)


def pack_dir(language: str) -> str:
    return resource_path("resources", "i18n", language)


def _compile_pattern(template: str) -> tuple[re.Pattern[str], list[str]]:
    parts: list[str] = []
    names: list[str] = []
    end = 0
    for match in _PLACEHOLDER.finditer(template):
        parts.append(re.escape(template[end : match.start()]))
        parts.append(f"(?P<v{len(names)}>.*?)")
        names.append(match.group(1))
        end = match.end()
    parts.append(re.escape(template[end:]))
    return re.compile("".join(parts), re.DOTALL), names


def pack_from_entries(entries: dict[str, str]) -> LanguagePack:
    pack = LanguagePack()
    templates: list[tuple[int, str, str]] = []
    for source, target in entries.items():
        if not isinstance(source, str) or not isinstance(target, str):
            pack.problems.append(f"non-string entry: {source!r}")
            continue
        pack.exact[source] = target
        names = _PLACEHOLDER.findall(source)
        if not names:
            continue
        literal = _PLACEHOLDER.sub("", source)
        if not literal.strip():
            pack.problems.append(f"pattern has no literal text: {source!r}")
            continue
        target_names = set(_PLACEHOLDER.findall(target))
        stray = target_names - set(names)
        missing = set(names) - target_names
        if stray or missing:
            pack.problems.append(
                f"placeholder mismatch (unknown {sorted(stray)}, missing {sorted(missing)}) "
                f"in {source!r}"
            )
        templates.append((len(literal), source, target))
    # Longest literal text first, so a specific template wins over a generic one.
    for _, source, target in sorted(templates, key=lambda item: -item[0]):
        regex, arg_names = _compile_pattern(source)
        pack.patterns.append((regex, arg_names, target))
    return pack


def _load_pack(language: str) -> LanguagePack:
    merged: dict[str, str] = {}
    problems: list[str] = []
    for path in sorted(glob.glob(os.path.join(pack_dir(language), "*.json"))):
        name = os.path.basename(path)
        try:
            with open(path, encoding="utf-8") as handle:
                entries = json.load(handle)
        except (OSError, ValueError) as exc:
            problems.append(f"{name}: {exc}")
            continue
        if not isinstance(entries, dict):
            problems.append(f"{name}: top level must be a JSON object")
            continue
        for source, target in entries.items():
            if source in merged and merged[source] != target:
                problems.append(f"{name}: conflicting translation for {source!r}")
            merged.setdefault(source, target)
    pack = pack_from_entries(merged)
    pack.problems[:0] = problems
    return pack


def language_pack(language: str) -> LanguagePack:
    code = normalize_language(language)
    if code not in _packs:
        _packs[code] = _load_pack(code)
    return _packs[code]


def _translate_with(pack: LanguagePack, text: str) -> str:
    if text in pack.exact:
        return pack.exact[text]
    if not text or _PLACEHOLDER.search(text):
        return text
    for regex, names, target in pack.patterns:
        match = regex.fullmatch(text)
        if match:
            values = {name: match.group(f"v{i}") for i, name in enumerate(names)}
            return _PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), target)
    return text


def tr_ui(text: str, language: str | None = None) -> str:
    code = _active if language is None else normalize_language(language)
    if code == DEFAULT_LANGUAGE or not text:
        return text
    return _translate_with(language_pack(code), text)


def tr_format(template: str, **values: str) -> str:
    """Translate a template that still has its ``{name}`` placeholders, then fill them."""
    translated = tr_ui(template)
    try:
        return translated.format(**values)
    except (KeyError, IndexError, ValueError):
        # A malformed pack must never break a status update; English is the fallback.
        return template.format(**values)


def help_slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")


def help_path(title: str, language: str) -> str:
    return os.path.join(pack_dir(language), "help", help_slug(title) + ".html")


def _localize_help_body(dialog: QDialog) -> None:
    """Replace an English help body with its zh-CN file as the dialog opens."""
    path = help_path(dialog.windowTitle(), _active)
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as handle:
            body = handle.read()
    except (OSError, UnicodeDecodeError):
        return
    for view in dialog.findChildren(QTextBrowser):
        if "<h2" in view.toHtml():
            view.setHtml(body)
            return
    for label in dialog.findChildren(QLabel):
        if "<h2" in label.text():
            label.setText(body)
            return


def _retext(current: str, setter) -> None:
    translated = tr_ui(current)
    if translated != current:
        setter(translated)


def _fit_translated_text(widget: QWidget) -> None:
    if isinstance(widget, QPushButton):
        # Widths are assigned before Show, when the caption is still English.
        from utils.common_components import unify_button_size

        unify_button_size(widget)
    elif isinstance(widget, QToolButton) and widget.icon().isNull():
        if widget.minimumWidth() == widget.maximumWidth():
            widget.setFixedWidth(max(widget.width(), widget.fontMetrics().horizontalAdvance(widget.text()) + 12))
    elif isinstance(widget, QLabel) and widget.minimumWidth() == widget.maximumWidth():
        if widget.fontMetrics().horizontalAdvance(widget.text()) > widget.contentsRect().width():
            widget.setWordWrap(True)


def translate_menu_tree(root) -> None:
    for action in root.actions():
        _retext(action.text(), action.setText)
        if action.menu() is not None:
            translate_menu_tree(action.menu())


def translate_widget(widget: QWidget) -> None:
    if isinstance(widget, QDialog) and widget.isWindow():
        _localize_help_body(widget)
    if widget.isWindow():
        _retext(widget.windowTitle(), widget.setWindowTitle)
    if widget.toolTip():
        _retext(widget.toolTip(), widget.setToolTip)
    if isinstance(widget, (QLabel, QAbstractButton)):
        original = widget.text()
        _retext(widget.text(), widget.setText)
        if widget.text() != original:
            _fit_translated_text(widget)
    if isinstance(widget, QGroupBox):
        _retext(widget.title(), widget.setTitle)
    if isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit, QComboBox)):
        _retext(widget.placeholderText(), widget.setPlaceholderText)
    if isinstance(widget, QAbstractSpinBox):
        _retext(widget.specialValueText(), widget.setSpecialValueText)
    if isinstance(widget, QComboBox):
        localize_combo_items(widget)
    if isinstance(widget, QTabWidget):
        for index in range(widget.count()):
            _retext(widget.tabText(index), lambda text, i=index: widget.setTabText(i, text))
    if isinstance(widget, QTableWidget):
        for column in range(widget.columnCount()):
            item = widget.horizontalHeaderItem(column)
            if item is not None:
                _retext(item.text(), item.setText)
    if isinstance(widget, QTreeWidget):
        header = widget.headerItem()
        for column in range(widget.columnCount()):
            _retext(header.text(column), lambda text, i=column: header.setText(i, text))
    if isinstance(widget, QMessageBox):
        _retext(widget.text(), widget.setText)
        _retext(widget.informativeText(), widget.setInformativeText)
    if isinstance(widget, (QMenu, QMenuBar)):
        translate_menu_tree(widget)


class UITranslator(QObject):
    """Translates widgets as they are shown while a non-English language is active."""

    def __init__(self, app):
        super().__init__(app)
        self._app = app
        # Detach before teardown; native widgets can outlive Python objects.
        app.aboutToQuit.connect(self._detach)

    def _detach(self):
        self._app.removeEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            event.type() == QEvent.Type.Show
            and isinstance(watched, QWidget)
            and _active != DEFAULT_LANGUAGE
        ):
            try:
                translate_widget(watched)
            except RuntimeError:
                # The C++ widget is already being destroyed.
                pass
        return False


def install_ui_translator(app) -> UITranslator:
    translator = getattr(app, "_seqsketch_ui_translator", None)
    if translator is None:
        translator = UITranslator(app)
        app.installEventFilter(translator)
        app._seqsketch_ui_translator = translator
    return translator


def install_qt_translator(app, language: str):
    """Load Qt's own catalog so standard dialogs and buttons are localized too."""
    code = normalize_language(language)
    if code == DEFAULT_LANGUAGE:
        return None
    translator = getattr(app, "_seqsketch_qt_translator", None)
    if translator is not None:
        return translator
    translator = QTranslator(app)
    locale = code.replace("-", "_")
    translations = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if not translator.load(f"qtbase_{locale}", translations):
        return None
    app.installTranslator(translator)
    app._seqsketch_qt_translator = translator
    return translator


def remove_ui_translator(app) -> None:
    translator = getattr(app, "_seqsketch_ui_translator", None)
    if translator is not None:
        app.removeEventFilter(translator)
        app._seqsketch_ui_translator = None


def saved_language() -> str:
    return normalize_language(Settings().get("ui.language", DEFAULT_LANGUAGE))


# Matplotlib ships DejaVu Sans, which has no CJK glyphs. Prefer a system CJK
# family so translated chart titles/axis labels render instead of tofu boxes.
_MATPLOTLIB_FONTS = (
    "Microsoft YaHei",
    "SimHei",
    "DengXian",
    "PingFang SC",
    "Heiti SC",
    "Arial Unicode MS",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "WenQuanYi Zen Hei",
)


def configure_matplotlib_fonts(language: str | None = None) -> bool:
    """Best-effort CJK font setup for matplotlib; returns False when nothing changed."""
    code = _active if language is None else normalize_language(language)
    if code == DEFAULT_LANGUAGE:
        return False
    try:
        import matplotlib
        from matplotlib import font_manager
    except ImportError:
        return False
    available = {font.name for font in font_manager.fontManager.ttflist}
    chosen = [name for name in _MATPLOTLIB_FONTS if name in available]
    if not chosen:
        return False
    fallbacks = [name for name in matplotlib.rcParams["font.sans-serif"] if name not in chosen]
    matplotlib.rcParams["font.sans-serif"] = chosen + fallbacks
    matplotlib.rcParams["axes.unicode_minus"] = False
    return True


def activate_saved_language(app) -> str:
    """Apply the saved language at startup; English installs nothing."""
    set_active_language(saved_language())
    if _active != DEFAULT_LANGUAGE:
        install_qt_translator(app, _active)
        install_ui_translator(app)
        configure_matplotlib_fonts(_active)
    return _active
