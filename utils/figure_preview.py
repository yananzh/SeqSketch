"""Shared frame, toolbar and empty state for figure previews."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from utils.common_components import unify_button_size


class FigurePreview(QFrame):
    def __init__(
        self, figure_widget: QWidget, empty_text: str, export_button: QPushButton | None = None
    ):
        super().__init__()
        self.setObjectName("figurePreview")

        self.toolbar_widget = QWidget()
        self.toolbar_widget.setObjectName("figurePreviewToolbar")
        self.toolbar = QHBoxLayout(self.toolbar_widget)
        self.toolbar.setContentsMargins(8, 6, 8, 6)
        self.toolbar.setSpacing(6)
        self.toolbar.addStretch()

        self.export_button = export_button
        if self.export_button is not None:
            self.export_button.setText("Export Image")
            self.export_button.setProperty("actionRole", "secondary")
            unify_button_size(self.export_button)
            self.toolbar.addWidget(self.export_button)

        self.empty_label = QLabel(empty_text)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.setProperty("hintLabel", True)

        self._pages = QStackedWidget()
        self._pages.addWidget(self.empty_label)
        self._pages.addWidget(figure_widget)
        self._figure_widget = figure_widget

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(self.toolbar_widget)
        self.toolbar_widget.setVisible(self.export_button is not None)
        body = QVBoxLayout()
        body.setContentsMargins(8, 8, 8, 8)
        body.addWidget(self._pages)
        layout.addLayout(body, 1)

        self.set_has_figure(False)

    @property
    def has_figure(self) -> bool:
        return self._pages.currentWidget() is self._figure_widget

    def set_has_figure(self, available: bool) -> None:
        self._pages.setCurrentWidget(self._figure_widget if available else self.empty_label)
        if self.export_button is not None:
            self.export_button.setEnabled(available)

    def add_scroll_reset(self, scroll_area: QScrollArea) -> None:
        """Offer a way back to the first visible row and column of a long figure."""
        horizontal = scroll_area.horizontalScrollBar()
        vertical = scroll_area.verticalScrollBar()
        button = QPushButton("Back to Start")
        button.setProperty("actionRole", "quiet")
        unify_button_size(button)
        button.setEnabled(False)

        def update():
            button.setEnabled(horizontal.value() != 0 or vertical.value() != 0)

        def reset():
            horizontal.setValue(0)
            vertical.setValue(0)

        horizontal.valueChanged.connect(update)
        vertical.valueChanged.connect(update)
        button.clicked.connect(reset)
        self.toolbar.insertWidget(0, button)
