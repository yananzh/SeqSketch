import sys
import traceback
from PyQt6.QtWidgets import QApplication, QSplashScreen, QMessageBox
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from main_window import MainWindow
import os


def _excepthook(exc_type, exc_value, exc_tb):
    """Global exception hook to catch unhandled exceptions."""
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print(tb_str, file=sys.stderr)
    QMessageBox.critical(
        None,
        "Unhandled Error",
        f"An unexpected error occurred:\n\n{exc_value}\n\nDetails:\n{tb_str}",
    )
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _excepthook


def main():
    # 高 DPI 适配（笔记本高分屏关键设置）
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
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
