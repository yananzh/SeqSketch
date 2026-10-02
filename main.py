import datetime
import os
import sys
import traceback

from utils.app_paths import user_data_dir


# ── 启动日志（在任何 import 之前写入，确保 Qt 初始化崩溃也能诊断） ────────────
# ── Resolve writable root early (avoid __file__ in frozen mode) ───────────────
def _startup_log_dir() -> str:
    return user_data_dir()


_STARTUP_LOG = os.path.join(_startup_log_dir(), "startup.log")
try:
    with open(_STARTUP_LOG, "a", encoding="utf-8") as _log_f:
        _log_f.write(f"\n{'=' * 60}\n")
        _log_f.write(f"startup : {datetime.datetime.now()}\n")
        _log_f.write(f"python  : {sys.executable}\n")
        _log_f.write(f"frozen  : {getattr(sys, 'frozen', False)}\n")
        _log_f.write(f"argv    : {sys.argv}\n")
        _log_f.write(f"cwd     : {os.getcwd()}\n")
        _log_f.write(f"meipass : {getattr(sys, '_MEIPASS', 'N/A')}\n")
except OSError:
    pass

# ── 无控制台时，stdout/stderr 重定向到启动日志，防止 print 丢失 ──────────────
if getattr(sys, "frozen", False):
    try:
        _log_fh = open(_STARTUP_LOG, "a", encoding="utf-8")
        sys.stdout = _log_fh
        sys.stderr = _log_fh
    except OSError:
        pass

try:
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QIcon, QPixmap
    from PyQt6.QtWidgets import QApplication, QMessageBox, QSplashScreen
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
    except OSError:
        pass
    if "--smoke-test" in sys.argv:
        app = QApplication.instance()
        if app:
            app.exit(1)
        return
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


def _smoke_check(app, window):
    """Exercise lazy tab imports and normal shutdown in the packaged runtime."""
    try:
        for opener in (
            window.open_download_from_ncbi_tab,
            window.open_mafft_alignment_tab,
            window.open_multiple_sequence_alignment_tab,
            window.open_codon_usage_tab,
            window.open_sanger_tab,
            window.open_sanger_viewer_tab,
            window.open_distance_tree_tab,
            window.open_one_step_multigenephy_tab,
            window.open_toytree_visualization_tab,
            window.open_blast_local_tab,
        ):
            opener()
        from utils.example_data import load_example_text
        if not load_example_text("phylo", "cytb_cds_raw.fasta"):
            raise RuntimeError("Bundled teaching dataset is missing")
        print(f"SMOKE: {window.tabs.count()} tabs loaded; resources available", flush=True)
        window.close()
    except Exception:
        traceback.print_exc()
        app.exit(1)


def main():
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        app = QApplication(sys.argv)
        # 应用程序级图标回退（任务栏 / Alt+Tab）
        from utils.app_paths import resource_path

        _icon = resource_path("window_logo.ico")
        if os.path.exists(_icon):
            app.setWindowIcon(QIcon(_icon))
    except Exception as _e:
        with open(_STARTUP_LOG, "a", encoding="utf-8") as _log_f:
            _log_f.write(f"FATAL: QApplication init failed: {_e}\n")
            traceback.print_exc(file=_log_f)
        raise
    # 显示启动界面

    logo_path = resource_path("start_logo.png")
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
    if "--smoke-test" in sys.argv:
        QTimer.singleShot(0, lambda: _smoke_check(app, window))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
