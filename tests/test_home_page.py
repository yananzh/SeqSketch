"""Home-page translations and wrapped headings fit without clipping."""

import os
from pathlib import Path

import pytest
from PyQt6.QtCore import QEvent
from PyQt6.QtGui import QFontDatabase, QFontInfo
from PyQt6.QtWidgets import QLabel, QWidget

from utils.app_paths import resource_path
from utils.home_page import HomePage
from utils.i18n import install_ui_translator, set_active_language


@pytest.fixture
def home_fonts(qapp):
    font_ids = []
    if os.name == "nt" and not QFontInfo(qapp.font()).family():
        for filename in ("segoeui.ttf", "msyh.ttc"):
            font_ids.append(QFontDatabase.addApplicationFont(
                str(Path(os.environ["WINDIR"]) / "Fonts" / filename)
            ))
    yield
    for font_id in font_ids:
        if font_id >= 0:
            QFontDatabase.removeApplicationFont(font_id)


@pytest.mark.parametrize("language", ["en", "zh-CN"])
@pytest.mark.parametrize("width", [460, 622, 920])
@pytest.mark.parametrize("heading_size", [15, 18])
def test_home_content_is_centered_and_wrapped_text_is_fully_visible(
    qapp, home_fonts, language, width, heading_size,
):
    install_ui_translator(qapp)
    set_active_language(language)
    page = HomePage()
    stylesheet = Path(resource_path("styles.qss")).read_text(encoding="utf-8")
    page.setStyleSheet(
        stylesheet + f"\nQLabel#homeFeatureTitle {{ font-size: {heading_size}px; }}"
    )
    # The narrow portrait case needs extra height for wrapped English text.
    page.resize(width, 750 if width == 460 else 635)
    page.show()
    for _ in range(3):
        qapp.processEvents()
    try:
        content = page.findChild(QWidget, "homeContent")
        assert abs(content.geometry().center().x() - page.rect().center().x()) <= 1
        assert content.width() == min(width - 80, 680)
        headings = [label for label in page.findChildren(QLabel)
                    if label.objectName() == "homeFeatureTitle"]
        assert len(headings) == 4
        for label in page.findChildren(QLabel):
            if label.wordWrap():
                assert label.height() >= label.heightForWidth(label.width()), label.text()
                assert content.rect().contains(label.geometry()), label.text()
        for left, right in ((headings[0], headings[1]), (headings[2], headings[3])):
            assert left.y() == right.y()
            assert left.height() == right.height()
        if language == "zh-CN":
            assert headings[1].text() == "DNA 与蛋白质分析"
    finally:
        page.close()
        page.deleteLater()
        qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        set_active_language("en")
