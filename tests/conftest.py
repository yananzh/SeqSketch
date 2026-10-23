"""Shared pytest fixtures for SeqSketch test suite."""

import os
from pathlib import Path
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtGui import QFontDatabase, QFontInfo
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """Shared QApplication instance for all tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app = cast(QApplication, app)
    app.setQuitOnLastWindowClosed(False)
    # Windows offscreen Qt does not discover system fonts. Keep explicitly
    # loaded fonts for the entire QApplication lifetime: removing them after
    # one test leaves cached family names but no usable fonts in later tests.
    font_ids = []
    if os.name == "nt" and not QFontInfo(app.font()).family():
        for filename in ("segoeui.ttf", "msyh.ttc"):
            font_ids.append(QFontDatabase.addApplicationFont(
                str(Path(os.environ["WINDIR"]) / "Fonts" / filename)
            ))
    yield app
    for font_id in font_ids:
        if font_id >= 0:
            QFontDatabase.removeApplicationFont(font_id)
