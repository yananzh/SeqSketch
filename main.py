import sys
import os
import traceback
import datetime

# ── 启动日志（在任何 import 之前写入，确保 Qt 初始化崩溃也能诊断） ────────────
_STARTUP_LOG = os.path.join(
    os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
    else os.path.dirname(os.path.abspath(__file__)),
    "startup.log",
)
try:
    with open(_STARTUP_LOG, "a", encoding="utf-8") as _log_f:
        _log_f.write(f"\n{'='*60}\n")
        _log_f.write(f"startup : {datetime.datetime.now()}\n")
        _log_f.write(f"python  : {sys.executable}\n")
        _log_f.write(f"frozen  : {getattr(sys, 'frozen', False)}\n")
        _log_f.write(f"argv    : {sys.argv}\n")
        _log_f.write(f"cwd     : {os.getcwd()}\n")
        _log_f.write(f"meipass : {getattr(sys, '_MEIPASS', 'N/A')}\n")
except Exception:
    pass

try:
    from PyQt6.QtWidgets import QApplication, QSplashScreen, QMessageBox
    from PyQt6.QtGui import QPixmap
    from PyQt6.QtCore import Qt
except Exception as _e:
    with open(_STARTUP_LOG, "a", encoding="utf-8") as _log_f:
        _log_f.write(f"FATAL: PyQt6 import failed: {_e}\n")
        traceback.print_exc(file=_log_f)
    raise

from main_window import MainWindow


def _excepthook(exc_type, exc_value, exc_tb):
    """Global exception hook to catch unhandled exceptions."""
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print(tb_str, file=sys.stderr)
    try:
        with open(_STARTUP_LOG, "a", encoding="utf-8") as _log_f:
            _log_f.write(f"UNHANDLED: {exc_value}\n{tb_str}")
    except Exception:
        pass
    try:
        QMessageBox.critical(
            None,
            "Unhandled Error",
            f"An unexpected error occurred:\n\n{exc_value}\n\nDetails:\n{tb_str}",
        )
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _excepthook


def main():
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        app = QApplication(sys.argv)
    except Exception as _e:
        with open(_STARTUP_LOG, "a", encoding="utf-8") as _log_f:
            _log_f.write(f"FATAL: QApplication init failed: {_e}\n")
            traceback.print_exc(file=_log_f)
        raise
    # 显示启动界面
    from utils.app_paths import resource_path

    logo_path = resource_path("start_logo.png")
    splash = None
    if os.path.exists(logo_path):
        pixmap = QPixmap(logo_path)
        # 缩放logo到合适大小 - 最大宽度400像素，保持宽高比
        if pixmap.width() > 400:
            pixmap = pixmap.scaledToWidth(
                400, Qt.TransformationMode.SmoothTransformation
            )
        # 如果高度仍然过大，限制最大高度为300像素
        if pixmap.height() > 300:
            pixmap = pixmap.scaledToHeight(
                300, Qt.TransformationMode.SmoothTransformation
            )

        splash = QSplashScreen(pixmap)
        splash.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        splash.show()
        app.processEvents()
    window = MainWindow()
    if splash:
        splash.finish(window)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
