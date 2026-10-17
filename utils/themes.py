"""Application themes, including compatibility with legacy widget-local QSS.

Only widget stylesheets are recolored. Scientific figures, HTML reports and
sequence annotations retain their own colors and export appearance.
"""

import json
import re
import weakref

from PyQt6 import sip
from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

from utils.app_paths import resource_path

THEMES = {"light": "Light", "dark": "Dark"}
_COLOR = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|\bwhite\b|\bblack\b")


def apply_button_roles(root):
    """Assign roles before parenting a new tab into the styled main window."""
    for button in root.findChildren(QPushButton):
        if button.property("actionRole"):
            continue
        text = button.text().replace("&", "").strip().lower()
        if button.property("stopButton") or text == "stop":
            role = "danger"
        elif text in {"run", "start", "analyze", "calculate", "align"}:
            role = "primary"
        elif text in {"clear", "clear all", "reset", "help", "close", "cancel"}:
            role = "quiet"
        else:
            role = "secondary"
        # Assign once so progress captions retain their execution role.
        button.setProperty("actionRole", role)


class ThemeManager(QObject):
    """One manager per QApplication; supports existing and lazily created tabs."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.name = "light"
        self._updating = False
        self._original_palette = QPalette(app.palette())
        self._windows = weakref.WeakSet()
        with open(
            resource_path("resources", "styles", "theme_colors.json"), encoding="utf-8"
        ) as handle:
            self.colors = json.load(handle)
        app.installEventFilter(self)
        app.aboutToQuit.connect(self._stop_filter)

    def _stop_filter(self):
        # Native widgets can outlive Python during application teardown.
        self.app.removeEventFilter(self)

    def recolor(self, stylesheet):
        if self.name == "light":
            return stylesheet
        replacements = self.colors["dark"]["replacements"]

        def replace_declaration(match):
            prop, value = match.groups()

            def replace_color(color):
                token = color[0].lower()
                if prop.lower() == "color" and token in ("white", "#fff", "#ffffff"):
                    return "#ffffff"
                return replacements.get(token, color[0])

            return prop + ":" + _COLOR.sub(replace_color, value)

        return re.sub(r"([\w-]+)\s*:([^;{}]+)", replace_declaration, stylesheet)

    def _adapt_widget(self, widget):
        current = widget.styleSheet()
        previous = getattr(widget, "_theme_local_style", None)
        # A tab may replace its local style while showing progress/results.
        source = previous[0] if previous and current == previous[1] else current
        adapted = self.recolor(source)
        widget._theme_local_style = (source, adapted)
        if current != adapted:
            widget.setStyleSheet(adapted)

    def eventFilter(self, watched, event):
        try:
            return self._filter_widget_event(watched, event)
        except RuntimeError:
            # Qt can send a final style event during native widget destruction.
            # Its Python wrapper may already have lost its C++ object.
            return False

    def _filter_widget_event(self, watched, event):
        if watched in self._windows:
            return False
        if (
            not self._updating
            and isinstance(watched, QWidget)
            and (
                event.type() == QEvent.Type.Polish
                or (
                    event.type() == QEvent.Type.StyleChange
                    and watched.testAttribute(Qt.WidgetAttribute.WA_WState_Polished)
                )
            )
        ):
            ancestor = watched
            while ancestor is not None and ancestor not in self._windows:
                ancestor = ancestor.parentWidget()
            if ancestor is None:
                return False
            if getattr(ancestor, "_closing_requested", False):
                return False
            self._updating = True
            try:
                self._adapt_widget(watched)
            finally:
                self._updating = False
        return False

    def apply(self, name, window=None):
        """Apply a known theme; invalid saved preferences fall back to Light."""
        name = name if isinstance(name, str) and name in THEMES else "light"
        with open(resource_path("styles.qss"), encoding="utf-8") as handle:
            stylesheet = handle.read()
        if name == "dark":
            with open(
                resource_path("resources", "styles", "dark_theme.qss"), encoding="utf-8"
            ) as handle:
                extra = handle.read()
        else:
            extra = ""
        self._updating = True
        try:
            self.name = name
            if window is not None:
                self._windows.add(window)
            palette = QPalette(self._original_palette)
            for role, color in self.colors[name]["palette"].items():
                palette.setColor(getattr(QPalette.ColorRole, role), QColor(color))
            themed_style = self.recolor(stylesheet) + "\n" + extra
            self.app.setPalette(palette)
            # Scope repolishing to live app windows, not unrelated Qt widgets
            # (including native dialogs or widgets awaiting deferred deletion).
            for root in list(self._windows):
                if sip.isdeleted(root) or getattr(root, "_closing_requested", False):
                    self._windows.discard(root)
                    continue
                if root.styleSheet() != themed_style:
                    root.setStyleSheet(themed_style)
                root.setPalette(palette)
                for widget in root.findChildren(QWidget):
                    self._adapt_widget(widget)
        finally:
            self._updating = False
        return name


def theme_manager():
    app = QApplication.instance()
    if app is None:
        raise RuntimeError("A QApplication is required to apply a theme")
    manager = getattr(app, "_seqsketch_theme_manager", None)
    if manager is None:
        manager = ThemeManager(app)
        app._seqsketch_theme_manager = manager
    return manager
