"""
Common worker base classes and components
Reduce duplication and provide unified error handling and signals
"""

import logging
import os
import re
from typing import Any, Dict, Optional

from PyQt6.QtCore import QObject, Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QPainter
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStyle,
    QStyleOptionComboBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# ── Shared placeholder combo box ────────────────────────────────────────────


class PlaceholderComboBox(QComboBox):
    """QComboBox that paints its placeholder text in a muted gray.

    Under a stylesheet (styles.qss), Qt renders QComboBox placeholder text
    with the widget's regular text color (black) instead of the
    PlaceholderText palette role, so palette fixes do not apply. This
    subclass draws the placeholder itself whenever the combo is empty.
    """

    def paintEvent(self, event):
        if self.currentIndex() == -1 and self.placeholderText():
            painter = QPainter(self)
            opt = QStyleOptionComboBox()
            self.initStyleOption(opt)
            self.style().drawComplexControl(QStyle.ComplexControl.CC_ComboBox, opt, painter, self)
            rect = self.style().subControlRect(
                QStyle.ComplexControl.CC_ComboBox,
                opt,
                QStyle.SubControl.SC_ComboBoxEditField,
                self,
            )
            painter.setPen(QColor("#888888"))
            painter.drawText(
                rect.adjusted(3, 0, -3, 0),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                self.fontMetrics().elidedText(
                    self.placeholderText(),
                    Qt.TextElideMode.ElideRight,
                    max(rect.width() - 6, 0),
                ),
            )
            painter.end()
        else:
            super().paintEvent(event)


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
                return os.path.normpath(local)
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


# ── Unified status-bar button sizing ───────────────────────────────────────
STATUS_BUTTON_WIDTH_SINGLE = 80   # one-word labels: Run, Clear, Help, Stop, ...
STATUS_BUTTON_WIDTH_DOUBLE = 120  # two-word labels: View Tree, Export Matrix, ...


def unify_status_button_sizes(tab) -> None:
    """Give every status-bar button of ``tab`` a consistent width.

    One-word labels get ``STATUS_BUTTON_WIDTH_SINGLE`` and two-word labels
    ``STATUS_BUTTON_WIDTH_DOUBLE``, so the bottom button rows look the same
    across feature tabs regardless of how each tab built its buttons.
    """
    layout = tab.status_layout
    for i in range(layout.count()):
        widget = layout.itemAt(i).widget()
        if isinstance(widget, QPushButton):
            width = (
                STATUS_BUTTON_WIDTH_DOUBLE
                if len(widget.text().split()) > 1
                else STATUS_BUTTON_WIDTH_SINGLE
            )
            widget.setFixedWidth(width)


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


def park_qthread(thread: Optional[QThread]):
    """Detach a possibly still-running QThread without destroying it.

    The thread's reference is dropped, but destruction is deferred to
    finished→deleteLater so a running QThread is never garbage-collected
    (which would abort the app with "QThread: Destroyed while thread is
    still running"). Safe to call with None, non-thread objects, or an
    already-finished thread.
    """
    if thread is None or not hasattr(thread, "isRunning"):
        return
    try:
        if not thread.isRunning():
            thread.deleteLater()
            return
        thread.finished.connect(thread.deleteLater)
    except RuntimeError:
        # C++ object already deleted — nothing left to park
        pass


def stop_worker_object(obj) -> bool:
    """Best-effort stop of a worker thread-like object.

    Calls stop() when present (workers use it to kill subprocesses and set
    abort flags), then quits a running QThread event loop. Returns True when
    the object existed and was handled. The caller keeps ownership: for
    threads that may still be running, pair this with park_qthread().
    """
    if obj is None:
        return False
    try:
        if hasattr(obj, "stop"):
            obj.stop()
        if hasattr(obj, "isRunning") and obj.isRunning():
            if hasattr(obj, "quit"):
                obj.quit()
        return True
    except RuntimeError:
        return False


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

    def shutdown(self):
        """Stop background work before the tab is closed.

        MainWindow.close_tab() calls this on every tab. The base implementation
        stops the shared worker_thread plus the conventional thread/worker
        attributes used across tabs; subclasses owning other threads or
        subprocesses must override this and park/stop them too, then call
        super().shutdown().
        """
        stop_worker_object(self.worker_thread)
        park_qthread(self.worker_thread)
        self.worker_thread = None
        for attr_name in ("_thread", "_batch_worker"):
            thread = getattr(self, attr_name, None)
            if thread is None:
                continue
            stop_worker_object(thread)
            park_qthread(thread)
            setattr(self, attr_name, None)
        for attr_name in ("_worker",):
            worker = getattr(self, attr_name, None)
            if worker is not None:
                stop_worker_object(worker)
                park_qthread(worker)
                setattr(self, attr_name, None)

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
            self.log_area.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
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
        from PyQt6.QtWidgets import QMessageBox

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
        from PyQt6.QtWidgets import QMessageBox

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

    def show_help_dialog(self, title: str, help_text: str, width: int = 560, height: int = 460):
        """Display a scrollable rich-text help dialog with an OK button.

        Centralizes the help-popup behavior so subclass ``show_help`` methods
        only need to build ``help_text`` (HTML) and call::

            self.show_help_dialog("Help - <Feature>", help_text, 600, 500)
        """
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(width, height)
        dialog.setMinimumSize(400, 300)
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

    # ── Shared Example-data loader (file-mode tabs) ────────────────────────

    def load_fasta_example(
        self, *example_parts: str, status_label: str | None = None
    ) -> str | None:
        """Stage a bundled FASTA example into this tab's file input.

        Copies the bundled example to a writable ``example_work`` dir via
        :func:`utils.example_data.stage_example`, then routes it through the
        tab's ``handle_input_file_selected`` so the output-name suggestion and
        status update reuse the same code path as Browse / drag-and-drop.

        Returns the staged path, or None if the example could not be staged
        (an ``QMessageBox.information`` is shown in that case).
        """
        from utils.example_data import stage_example

        path = stage_example(*example_parts)
        if not path:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. The installation may be incomplete."),
            )
            return None
        if hasattr(self, "handle_input_file_selected"):
            self.handle_input_file_selected(path)
        self.show_status(self.tr(f"Example loaded: {status_label or os.path.basename(path)}"))
        return path

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

    def add_open_output_dir_button(self):
        """Add a 'Result Folder' button to the right of Run/Clear in the
        status bar (before Help). It opens the folder containing the current
        output file.
        """
        self.open_output_btn = QPushButton(self.tr("Result Folder"))
        self.open_output_btn.clicked.connect(self._open_output_folder)
        # Insert right before the Help button (always the last status widget)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.open_output_btn)

    def _open_output_folder(self):
        """Open the folder containing the current output file.

        If the output path is itself an existing directory (e.g. the Split
        FASTA tab writes to a directory), that directory is opened directly.
        """
        output_edit = getattr(self, "output_edit", None)
        output_path = output_edit.text().strip() if output_edit is not None else ""
        if not output_path:
            self.show_status(self.tr("No output file selected yet."))
            return
        if os.path.isdir(output_path):
            target_dir = output_path
        else:
            target_dir = os.path.dirname(os.path.abspath(output_path))
        if not os.path.isdir(target_dir):
            self.show_status(self.tr("Output directory does not exist yet."))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(target_dir))

    def log_message(self, message: str, level: str = "INFO"):
        """Append log message (file mode only)"""
        if not hasattr(self, "log_area"):
            return

        prefix = {"INFO": "[Info]", "ERROR": "[Error]", "WARNING": "[Warning]"}.get(level, "[Info]")

        # 文件输出地址单独一行显示
        display = re.sub(r"(?<=to: )(?=[A-Za-z]:[\\\\/]|\\\\|/)", "\n", message)

        self.log_area.append(f"{prefix} {display}")

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
        # 线程引用由 _on_worker_thread_finished() 在线程完全停止后释放，
        # 避免在此处释放仍在运行的 QThread（会导致应用崩溃）

    def handle_worker_error(self, error_msg: str):
        """处理工作线程错误"""
        if hasattr(self, "log_area"):
            self.log_message(error_msg, "ERROR")
        else:
            self.show_status(f"Error: {error_msg}")
        self.set_running_state(False)
        # 线程引用由 _on_worker_thread_finished() 在线程完全停止后释放

    def _on_worker_thread_finished(self):
        """Worker 线程已完全停止 — 此时释放线程引用是安全的。

        直接在线程运行中释放引用会让 PyQt 销毁仍在运行的 QThread，
        触发 Qt 致命错误 "QThread: Destroyed while thread is still running"。
        """
        if self.sender() is self.worker_thread:
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

        # 连接信号 — quit 必须在 handler 之前连接，
        # 否则 handler 若阻塞等待线程退出会造成死锁
        self.worker_thread.started.connect(worker.run)
        worker.finished.connect(self.worker_thread.quit)
        worker.error.connect(self.worker_thread.quit)
        worker.finished.connect(self.handle_worker_finished)
        worker.error.connect(self.handle_worker_error)

        # 如果有进度信号，连接到状态显示
        if hasattr(worker, "progress"):
            worker.progress.connect(self.show_status)

        # 线程真正停止后才释放引用，避免在运行中销毁 QThread
        self.worker_thread.finished.connect(self._on_worker_thread_finished)

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
        return False, "Input path is empty"

    if not os.path.isfile(path):
        return False, "Input file does not exist"

    if file_types:
        ext = os.path.splitext(path)[1].lower()
        if ext not in file_types:
            return False, f"Unsupported file type. Please choose: {', '.join(file_types)}"

    return True, ""


def validate_output_path(path: str) -> tuple[bool, str]:
    """
    验证输出文件路径

    Returns:
        (是否有效, 错误消息)
    """
    import os

    if not path or not path.strip():
        return False, "Output path is empty"

    output_dir = os.path.dirname(path)
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
        except Exception as e:
            return False, f"Cannot create output directory: {e}"

    return True, ""
