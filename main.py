import sys
from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from main_window import MainWindow
import os

def main():
    app = QApplication(sys.argv)
    # 显示启动界面
    logo_path = os.path.join(os.path.dirname(__file__), "Gemini_Generated_Image_ohhms3ohhms3ohhm.png")
    splash = None
    if os.path.exists(logo_path):
        pixmap = QPixmap(logo_path)
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