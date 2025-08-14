import sys
from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from main_window import MainWindow
import os

def main():
    app = QApplication(sys.argv)
    # 显示启动界面
    logo_path = os.path.join(os.path.dirname(__file__), "启动界面logo.png")
    splash = None
    if os.path.exists(logo_path):
        pixmap = QPixmap(logo_path)
        # 缩放logo到合适大小 - 最大宽度400像素，保持宽高比
        if pixmap.width() > 400:
            pixmap = pixmap.scaledToWidth(400, Qt.TransformationMode.SmoothTransformation)
        # 如果高度仍然过大，限制最大高度为300像素
        if pixmap.height() > 300:
            pixmap = pixmap.scaledToHeight(300, Qt.TransformationMode.SmoothTransformation)
        
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