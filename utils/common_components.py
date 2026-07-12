"""
Common worker base classes and components
Reduce duplication and provide unified error handling and signals
"""

from PyQt6.QtCore import QObject, QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QPushButton,
    QFrame,
    QTextEdit,
    QLineEdit,
    QFileDialog,
    QMessageBox,
    QDialog,
    QScrollArea,
)
from typing import Any, Dict, Optional
import logging
import os


# ── Shared file-drop line edit ──────────────────────────────────────────────


class FileDropLineEdit(QLineEdit):
    """A QLineEdit that accepts file drops, filtering by extension.

    Use ``FASTA_EXTENSIONS`` or ``MAPPING_EXTENSIONS`` for the *allowed* parameter,
    or pass your own set of lowercase extensions (including the leading dot).
    """

    FASTA_EXTENSIONS = {".fasta", ".fa", ".fas", ".fna", ".ffn", ".faa", ".frn", ".txt"}
    MAPPING_EXTENSIONS = {".csv", ".tsv", ".txt", ".xlsx", ".xls"}

    file_dropped = pyqtSignal(str)

    def __init__(self, allowed_extensions=None, parent=None):
        super().__init__(parent)
        self._allowed = allowed_extensions or self.FASTA_EXTENSIONS
        self.setAcceptDrops(True)

    # ── drag-and-drop ──────────────────────────────────────────────────

    def dragEnterEvent(self, event):
        if self._has_valid_url(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        path = self._first_local_url(event.mimeData())
        if path and self._is_valid(path):
            self.setText(path)
            self.file_dropped.emit(path)
            event.acceptProposedAction()
        else:
            event.ignore()

    # ── helpers ────────────────────────────────────────────────────────

    def _has_valid_url(self, mime_data) -> bool:
        path = self._first_local_url(mime_data)
        return bool(path and self._is_valid(path))

    @staticmethod
    def _first_local_url(mime_data) -> str | None:
        if not mime_data or not mime_data.hasUrls():
            return None
        for url in mime_data.urls():
            local = url.toLocalFile()
            if local:
                return local
        return None

    def _is_valid(self, path: str) -> bool:
        try:
            ext = os.path.splitext(path)[1].lower()
            return os.path.isfile(path) and ext in self._allowed
        except Exception:
            return False


SEQUENCE_EDITOR_STYLE = (
    "border: 1px solid #94a3b8;"
    "border-radius: 6px;"
    "padding: 8px 10px;"
    "background: #ffffff;"
    "selection-background-color: #d9ebff;"
    "selection-color: #1a1a1a;"
)

READ_ONLY_SEQUENCE_EDITOR_STYLE = "background: #f7f9fc;"
LOG_VIEWER_STYLE = (
    "border: none;"
    "padding: 8px 10px;"
    "background: #ffffff;"
    "color: #1e293b;"
    'font-family: "Cascadia Mono", "Consolas", monospace;'
)


def apply_sequence_editor_style(editor: QTextEdit) -> None:
    editor.setProperty("sequenceEditorStyled", True)
    style = SEQUENCE_EDITOR_STYLE
    if editor.isReadOnly():
        style += READ_ONLY_SEQUENCE_EDITOR_STYLE
    editor.setStyleSheet(style)
    # Remove the native Qt frame so only the CSS border is visible.
    # Without this the widget renders a native border on top of the CSS
    # one, producing a "double border" inside QGroupBox containers.
    editor.setFrameShape(QFrame.Shape.NoFrame)
    # Make the viewport transparent so the outer frame's rounded corners and
    # background colour are visible instead of being covered by a white rectangle.
    editor.viewport().setStyleSheet("background: transparent;")


def apply_transparent_text_edit_background(editor: QTextEdit) -> None:
    style = editor.styleSheet()
    style = style.replace("background: #ffffff;", "")
    style = style.replace(READ_ONLY_SEQUENCE_EDITOR_STYLE, "")
    style = style.replace("border: none;", "")
    style = style.replace("background: transparent;", "")
    if "border: 1px solid #94a3b8;" not in style:
        style += "border: 1px solid #94a3b8;"
    if "border-radius: 6px;" not in style:
        style += "border-radius: 6px;"
    editor.setFrameShape(QFrame.Shape.NoFrame)
    editor.setStyleSheet(style + "background: transparent;")
    editor.viewport().setStyleSheet("background: transparent; border: none;")


def apply_log_viewer_style(editor: QTextEdit) -> None:
    editor.setProperty("logViewer", True)
    editor.setStyleSheet(LOG_VIEWER_STYLE)
    editor.viewport().setStyleSheet("background: transparent;")


class BaseWorker(QObject):
    """
    通用工作线程基类
    所有后台任务继承此类，减少重复代码
    """

    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

    def emit_progress(self, message: str):
        """Emit progress message"""
        self.progress.emit(message)
        self.logger.info(f"Progress: {message}")

    def emit_error(self, error_msg: str, exception: Optional[Exception] = None):
        """Emit error message"""
        if exception:
            self.logger.exception(f"Error: {error_msg}")
        else:
            self.logger.error(error_msg)
        self.error.emit(error_msg)

    def emit_finished(self, result_msg: str):
        """Emit finished message"""
        self.logger.info(f"Task finished: {result_msg}")
        self.finished.emit(result_msg)

    def run(self):
        """Must be implemented by subclass"""
        raise NotImplementedError("Subclass must implement run()")


class DataWorker(BaseWorker):
    """
    Data worker base class for tasks returning processed data
    """

    data_finished = pyqtSignal(dict)

    def emit_data_finished(self, data: Dict[str, Any], message: str = "Completed"):
        """Emit data finished signal"""
        self.logger.info(f"Data task completed: {message}")
        self.data_finished.emit(data)
        self.finished.emit(message)


class BaseTabWidget(QWidget):
    """
    Common Tab base class providing unified UI patterns and error handling
    """

    def __init__(self, title: str = "Analysis Tools", tab_type: str = "file"):
        super().__init__()
        self.title = title
        self.tab_type = tab_type
        self.worker_thread: Optional[QThread] = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self.init_common_ui()
        self.connect_common_signals()

    def init_common_ui(self):
        """Initialize common UI components"""
        self.main_layout = QVBoxLayout(self)

        # Content area for subclasses
        self.content_area = QVBoxLayout()
        self.main_layout.addLayout(self.content_area)

        if self.tab_type == "sequence":
            # Create input/output areas for sequence tabs
            self.init_sequence_ui()

        # Status area — Run/Clear go on the same row as Help, bottom-right
        self.status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_layout.addWidget(QLabel("Status:"))
        self.status_layout.addWidget(self.status_label)
        self.status_layout.addStretch()

        # Run/Clear buttons for sequence tabs — placed at bottom-right
        if self.tab_type == "sequence" and hasattr(self, "run_btn"):
            self.run_btn.setFixedWidth(90)
            self.clear_btn.setFixedWidth(90)
            self.status_layout.addWidget(self.run_btn)
            self.status_layout.addWidget(self.clear_btn)

        # Help button (for all modes)
        self.help_btn = QPushButton("Help")
        self.help_btn.clicked.connect(self.show_help)
        self.status_layout.addWidget(self.help_btn)

        # Log area (file mode only)
        if self.tab_type == "file":
            self.log_group = QGroupBox(self.tr("Operation Log"))
            self.log_group.setProperty("logGroup", True)
            self.log_area = QTextEdit()
            self.log_area.setReadOnly(True)
            apply_log_viewer_style(self.log_area)
            self.log_area.setMinimumHeight(120)
            self.log_area.setMaximumHeight(160)
            self.log_area.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            self.log_area.setPlaceholderText(
                self.tr("Run a FASTA tool to see progress and results here...")
            )

            log_layout = QVBoxLayout(self.log_group)
            log_layout.setContentsMargins(10, 6, 10, 10)
            log_layout.setSpacing(0)
            log_layout.addWidget(self.log_area)
            self.main_layout.addWidget(self.log_group)

        # 添加状态到布局
        self.main_layout.addLayout(self.status_layout)

    def init_sequence_ui(self):
        """Initialize sequence processing UI with QGroupBox sections"""
        # ── Input QGroupBox ───────────────────────────────────────────
        self.input_group = QGroupBox(self.tr("Input Sequence"))
        self.input_group.setFlat(True)
        ig_layout = QVBoxLayout(self.input_group)
        ig_layout.setContentsMargins(0, 16, 0, 4)
        ig_layout.setSpacing(6)

        self.input_text = QTextEdit()
        apply_sequence_editor_style(self.input_text)
        self.input_text.setPlaceholderText("Paste DNA/RNA sequence, or upload a file...")
        self.upload_btn = QPushButton(self.tr("Upload File"))
        self.upload_btn.clicked.connect(self.open_file)
        self.input_hint = QLabel("")
        self.input_hint.setStyleSheet("color: #888;")

        ig_layout.addWidget(self.input_text)
        ig_layout.addWidget(self.upload_btn)
        ig_layout.addWidget(self.input_hint)
        self.content_area.addWidget(self.input_group)

        # ── Parameter insertion point ─────────────────────────────────
        # Subclasses add parameter controls here via add_parameter_layout()
        # or add_content_layout()
        self._param_layout = QVBoxLayout()
        self._param_layout.setContentsMargins(0, 0, 0, 0)
        self.content_area.addLayout(self._param_layout)

        # ── Output QGroupBox ──────────────────────────────────────────
        self.output_group = QGroupBox(self.tr("Output Result"))
        self.output_group.setFlat(True)
        og_layout = QVBoxLayout(self.output_group)
        og_layout.setContentsMargins(0, 16, 0, 4)
        og_layout.setSpacing(6)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        apply_sequence_editor_style(self.output_text)
        apply_transparent_text_edit_background(self.output_text)

        # ── Strip CSS border from text widgets ────────────────────────
        # styles.qss already gives every QGroupBox a 1px border.
        # Keeping a second border on the inner QTextEdit produces a
        # visible double-border effect.
        for _editor in (self.input_text, self.output_text):
            _style = _editor.styleSheet()
            _style = _style.replace("border: 1px solid #94a3b8;", "border: none;")
            _editor.setStyleSheet(_style)

        self.export_btn = QPushButton(self.tr("Export Result"))
        self.copy_btn = QPushButton(self.tr("Copy to Clipboard"))
        self.export_btn.clicked.connect(self.export_result)
        self.copy_btn.clicked.connect(self.copy_result)

        ob_layout = QHBoxLayout()
        ob_layout.addWidget(self.export_btn)
        ob_layout.addWidget(self.copy_btn)
        ob_layout.addStretch()

        og_layout.addWidget(self.output_text)
        og_layout.addLayout(ob_layout)
        self.content_area.addWidget(self.output_group)

        # ── Legacy label attributes (for subclasses that reference them) ──
        self.input_label = QLabel()
        self.output_label = QLabel()

        # ── Run / Clear buttons (placed in status row by init_common_ui) ──
        self.run_btn = QPushButton(self.tr("Run"))
        self.clear_btn = QPushButton(self.tr("Clear"))
        self.run_btn.clicked.connect(self.run)
        self.clear_btn.clicked.connect(self.clear)

        # ── Enable drag-and-drop for sequence input ───────────────────
        self._setup_sequence_drag_drop()

    def open_file(self):
        """Open file (sequence mode)"""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select sequence file",
            "",
            "FASTA/TXT/GenBank (*.fasta *.fa *.txt *.gb *.gbk);;All Files (*)",
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.input_text.setPlainText(content)
                self.input_hint.setText(f"Loaded file: {file_path}")
            except Exception as e:
                QMessageBox.warning(self, "File Read Error", str(e))

    def export_result(self):
        """Export result (sequence mode)"""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Result",
            "result.txt",
            "Text Files (*.txt);;FASTA Files (*.fasta);;CSV Files (*.csv)",
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.output_text.toPlainText())
                self.status_label.setText(f"Exported: {file_path}")
            except Exception as e:
                QMessageBox.warning(self, "Export Error", str(e))

    def copy_result(self):
        """Copy result to clipboard (sequence mode)"""
        self.output_text.selectAll()
        self.output_text.copy()
        self.status_label.setText("Copied to clipboard")

    def run(self):
        """由子类实现的主要运行方法"""
        pass

    def clear(self):
        """Clear content"""
        if hasattr(self, "input_text"):
            self.input_text.clear()
        if hasattr(self, "output_text"):
            self.output_text.clear()
        if hasattr(self, "input_hint"):
            self.input_hint.clear()
        if hasattr(self, "log_area"):
            self.log_area.clear()
        self.show_status("Cleared")

    def show_help(self):
        """Help method implemented by subclass"""
        pass

    def show_help_dialog(self, title: str, help_text: str, width: int = 720, height: int = 460):
        """Display a scrollable rich-text help dialog with an OK button.

        Centralizes the help-popup behavior so subclass ``show_help`` methods
        only need to build ``help_text`` (HTML) and call::

            self.show_help_dialog("Help - <Feature>", help_text, 820, 600)
        """
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setFixedSize(width, height)
        layout = QVBoxLayout()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        label = QLabel(help_text)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        label.setMargin(20)
        scroll_area.setWidget(label)
        layout.addWidget(scroll_area)
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)
        dialog.setLayout(layout)
        dialog.exec()

    # ── Drag-and-drop helpers (sequence mode) ────────────────────────────

    def _setup_sequence_drag_drop(self):
        """Enable drag-and-drop for FASTA files on the input text area."""
        self.input_text.setAcceptDrops(True)
        self.input_text.dragEnterEvent = self._drag_enter_event
        self.input_text.dropEvent = self._drop_event

    def _drag_enter_event(self, event):
        md = event.mimeData()
        if md.hasUrls():
            urls = md.urls()
            if urls and urls[0].toLocalFile():
                event.acceptProposedAction()
                return
        event.ignore()

    def _drop_event(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.input_text.setPlainText(content)
                self.input_hint.setText(f"Loaded file: {file_path}")
                event.acceptProposedAction()
            except Exception as e:
                self.show_status(f"Error loading file: {e}")
                event.ignore()

    # ── Layout helpers ──────────────────────────────────────────────────

    def add_parameter_layout(self, layout):
        """Insert a parameter layout between the input and output sections."""
        if hasattr(self, "_param_layout"):
            self._param_layout.addLayout(layout)

    def add_content_layout(self, layout):
        """Add content layout — redirects to _param_layout in sequence mode."""
        if hasattr(self, "_param_layout"):
            self._param_layout.addLayout(layout)
        else:
            self.content_area.addLayout(layout)

    def add_content_widget(self, widget):
        """Add content widget"""
        self.content_area.addWidget(widget)

    def connect_common_signals(self):
        """Connect common signals (optional override)"""
        pass

    def show_status(self, message: str):
        """Show status message"""
        self.status_label.setText(message)
        self.logger.info(message)

    def log_message(self, message: str, level: str = "INFO"):
        """Append log message (file mode only)"""
        if not hasattr(self, "log_area"):
            return

        prefix = {"INFO": "[Info]", "ERROR": "[Error]", "WARNING": "[Warning]"}.get(level, "[Info]")

        self.log_area.append(f"{prefix} {message}")

        if level == "ERROR":
            self.logger.error(message)
        elif level == "WARNING":
            self.logger.warning(message)
        else:
            self.logger.info(message)

    def set_running_state(self, running: bool):
        """设置运行状态 - 子类应重写以禁用特定按钮"""
        self.show_status("Processing..." if running else "Ready")

    def handle_worker_finished(self, message: str):
        """处理工作线程完成"""
        if hasattr(self, "log_area"):
            self.log_message(message)
        else:
            self.show_status("Completed")
        self.set_running_state(False)
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None

    def handle_worker_error(self, error_msg: str):
        """处理工作线程错误"""
        if hasattr(self, "log_area"):
            self.log_message(error_msg, "ERROR")
        else:
            self.show_status(f"Error: {error_msg}")
        self.set_running_state(False)
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None

    def start_worker(self, worker: BaseWorker):
        """启动工作线程的通用方法"""
        if self.worker_thread and self.worker_thread.isRunning():
            error_msg = "A task is already running, please wait until it completes"
            if hasattr(self, "log_area"):
                self.log_message(error_msg, "WARNING")
            else:
                self.show_status(error_msg)
            return False

        self.worker_thread = QThread()
        worker.moveToThread(self.worker_thread)

        # 连接信号
        self.worker_thread.started.connect(worker.run)
        worker.finished.connect(self.handle_worker_finished)
        worker.error.connect(self.handle_worker_error)
        worker.finished.connect(self.worker_thread.quit)
        worker.error.connect(self.worker_thread.quit)

        # 如果有进度信号，连接到状态显示
        if hasattr(worker, "progress"):
            worker.progress.connect(self.show_status)

        self.set_running_state(True)
        self.worker_thread.start()
        return True


class FASTAWorker(BaseWorker):
    """
    FASTA文件处理专用工作线程基类
    """

    def __init__(self, input_path: str, output_path: str):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path

    def validate_files(self) -> bool:
        """验证输入输出文件路径"""
        import os

        if not self.input_path or not os.path.isfile(self.input_path):
            self.emit_error("输入文件无效或不存在")
            return False

        if not self.output_path:
            self.emit_error("输出文件路径不能为空")
            return False

        # 检查输出目录是否存在，不存在则创建
        output_dir = os.path.dirname(self.output_path)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                self.emit_error(f"无法创建输出目录: {e}")
                return False

        return True

    def load_fasta_processor(self):
        """加载FASTA处理器"""
        try:
            from modules.fasta_processor import FASTAProcessor

            processor = FASTAProcessor()
            if not processor.read_file(self.input_path):
                self.emit_error("无法读取FASTA文件")
                return None
            return processor
        except Exception as e:
            self.emit_error(f"加载FASTA处理器失败: {e}")
            return None


# 常用工具函数
def setup_logging():
    """设置项目日志"""
    import logging
    import os
    from datetime import datetime

    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file = os.path.join(log_dir, f"bioseq_{datetime.now().strftime('%Y%m%d')}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def validate_input_path(path: str, file_types: list | None = None) -> tuple[bool, str]:
    """
    验证输入文件路径

    Args:
        path: 文件路径
        file_types: 允许的文件扩展名列表，如 ['.fasta', '.fa', '.fas']

    Returns:
        (是否有效, 错误消息)
    """
    import os

    if not path or not path.strip():
        return False, "文件路径不能为空"

    if not os.path.isfile(path):
        return False, "文件不存在或不是有效文件"

    if file_types:
        ext = os.path.splitext(path)[1].lower()
        if ext not in file_types:
            return False, f"不支持的文件类型，请选择: {', '.join(file_types)}"

    return True, ""


def validate_output_path(path: str) -> tuple[bool, str]:
    """
    验证输出文件路径

    Returns:
        (是否有效, 错误消息)
    """
    import os

    if not path or not path.strip():
        return False, "输出路径不能为空"

    output_dir = os.path.dirname(path)
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
        except Exception as e:
            return False, f"无法创建输出目录: {e}"

    return True, ""
