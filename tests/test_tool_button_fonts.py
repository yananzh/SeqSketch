"""Native Windows tool buttons must receive a valid point-sized font."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


@pytest.mark.parametrize("stylesheet", ["styles.qss", "resources/styles/modern_theme.qss"])
@pytest.mark.parametrize("scale", ["1", "1.5"])
def test_tool_buttons_render_without_invalid_point_size(stylesheet, scale):
    root = Path(__file__).resolve().parents[1]
    script = textwrap.dedent("""
        import sys
        from pathlib import Path
        from PyQt6.QtCore import Qt, qInstallMessageHandler
        from PyQt6.QtGui import QIcon, QPixmap
        from PyQt6.QtWidgets import (
            QApplication, QHBoxLayout, QMainWindow, QToolBar, QToolButton, QWidget,
        )

        warnings = []
        def capture(kind, context, message):
            if 'QFont::setPointSize' in message:
                warnings.append(message)
        previous = qInstallMessageHandler(capture)
        app = QApplication([])
        window = QMainWindow()
        window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        toolbar = QToolBar(window)
        window.addToolBar(toolbar)
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.black)
        for name in ('Home', 'Back', 'Forward', 'Pan', 'Zoom', 'Save'):
            toolbar.addAction(QIcon(pixmap), name)
        preview = QWidget()
        preview.setObjectName('treePreviewToolbar')
        layout = QHBoxLayout(preview)
        for text in ('Fit', '100%', '+', '-'):
            button = QToolButton(preview)
            button.setText(text)
            layout.addWidget(button)
        window.setCentralWidget(preview)
        window.setStyleSheet(Path(sys.argv[1]).read_text(encoding='utf-8'))
        window.show()
        for _ in range(3):
            app.processEvents()
            window.grab()
        for button in window.findChildren(QToolButton):
            assert button.font().pointSizeF() > 0, button.text()
        window.close()
        app.processEvents()
        qInstallMessageHandler(previous)
        assert not warnings, warnings
    """)
    env = os.environ.copy()
    # Exercise the Windows native painting path even though conftest configures
    # the parent pytest QApplication to use the offscreen platform.
    env["QT_QPA_PLATFORM"] = "windows" if sys.platform == "win32" else "offscreen"
    env["QT_SCALE_FACTOR"] = scale
    result = subprocess.run(
        [sys.executable, "-c", script, str(root / stylesheet)],
        cwd=root, env=env, capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
