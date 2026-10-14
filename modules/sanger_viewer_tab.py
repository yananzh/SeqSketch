"""Sanger Chromatogram Viewer Tab — AB1 chromatogram display with selected-range FASTA export."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from typing import List, Optional

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import QObject, Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from modules.fasta_processor import FASTAProcessor
from utils.common_components import (
    park_qthread,
    stop_worker_object,
    unify_status_button_sizes,
    validate_output_path,
)
from utils.example_data import stage_example
from utils.task_lifecycle import skip_when_closing

# Pixels per raw scan when sizing the canvas (1 scan ≈ 1 px gives good peak clarity)
_PX_PER_SCAN = 1
_MIN_CANVAS_W = 800  # px — minimum canvas width before any data is loaded
_TRACE_H_PX = 300  # canvas height (trace only)
_QUAL_H_PX = 80  # extra height added when quality track is shown

_TRACE_COLOR = {"A": "#009900", "T": "#DD0000", "G": "#111111", "C": "#0055CC"}
_BASE_COLOR = {
    "A": "#007700",
    "T": "#BB0000",
    "G": "#111111",
    "C": "#0044AA",
    "N": "#888888",
}


class _LoadThread(QThread):
    """Loads and parses the AB1 file on a background thread.

    Lifetime is owned by :class:`SangerViewerTab`, which stops and parks this
    thread from ``shutdown()`` (called by ``MainWindow.close_tab``). Do not
    add a ``__del__`` hook here: destroying a still-running QThread aborts
    the process with "QThread: Destroyed while thread is still running".
    """


class _LoadWorker(QObject):
    finished = pyqtSignal(dict, str, list)
    error = pyqtSignal(str)

    def __init__(self, path: str) -> None:
        super().__init__()
        self._path = path

    def run(self) -> None:
        try:
            from Bio import SeqIO

            record = SeqIO.read(self._path, "abi")
            raw = record.annotations.get("abif_raw", {})

            # The base assigned to each of DATA9..DATA12 is file-specific and
            # comes from the FWO_ (filter wheel order) tag; hardcoding GATC
            # drew every channel in the wrong base's color when it differed.
            order = raw.get("FWO_", b"GATC")
            if isinstance(order, bytes):
                order = order.decode("ascii", "ignore")
            if sorted(order[:4]) != list("ACGT"):
                order = "GATC"
            channels = {
                base: list(raw.get(f"DATA{9 + offset}", []))
                for offset, base in enumerate(order[:4])
            }
            # Peak scan positions — one entry per called base
            peak_locs: List[int] = list(raw.get("PLOC1", []))

            abi_data = {"channels": channels, "peak_locs": peak_locs}
            sequence = str(record.seq).upper()
            quality: List[int] = list(record.letter_annotations.get("phred_quality", []))
            self.finished.emit(abi_data, sequence, quality)
        except Exception as exc:
            self.error.emit(str(exc))


class SangerViewerTab(QWidget):
    """Displays an AB1 Sanger chromatogram and exports selected sequence ranges as FASTA."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._abi_data: Optional[dict] = None
        self._sequence: str = ""
        self._quality: List[int] = []
        self._last_output_path = ""
        self._thread: Optional[QThread] = None
        self._worker: Optional[_LoadWorker] = None
        self.setAcceptDrops(True)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # --- File selection row ---
        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("AB1 File:"))
        self._file_edit = QLineEdit()
        self._file_edit.setReadOnly(True)
        self._file_edit.setPlaceholderText("Select an AB1 file, or drag & drop one here...")
        self._file_edit.setToolTip(
            "Path to the AB1 Sanger sequencing file.\n"
            "Select or drop a file and it loads automatically."
        )
        file_row.addWidget(self._file_edit, 1)
        self._btn_example = QPushButton("Example")
        self._btn_example.setToolTip("Load a bundled example AB1 trace file")
        file_row.addWidget(self._btn_example)
        self._btn_browse = QPushButton("Browse")
        self._btn_browse.setToolTip("Select an AB1 file (loads automatically)")
        file_row.addWidget(self._btn_browse)
        outer.addLayout(file_row)

        self._chk_quality = QCheckBox("Show Phred quality track")
        self._chk_quality.setChecked(True)
        self._chk_quality.setToolTip("Toggle the Phred quality bar chart below the chromatogram")

        # --- Matplotlib canvas inside a horizontal scroll area ---
        self._fig = Figure()
        self._canvas = FigureCanvas(self._fig)

        # Give the canvas a predictable initial size so the scroll area
        # does not end up with an arbitrary Matplotlib default extent.
        self._canvas.setFixedSize(_MIN_CANVAS_W, _TRACE_H_PX)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidget(self._canvas)
        self._scroll_area.setWidgetResizable(False)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll_area.setMinimumHeight(200)

        # Empty-state hint shown centered in the plot area
        self._hint_page = QWidget()
        self._hint_page.setMinimumHeight(200)
        hint_layout = QVBoxLayout(self._hint_page)
        self._hint_label = QLabel(
            "No chromatogram loaded.\nSelect an AB1 file or drag & drop one here."
        )
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint_label.setStyleSheet("color: #888;")
        hint_layout.addWidget(self._hint_label)

        self._plot_stack = QStackedWidget()
        self._plot_stack.addWidget(self._hint_page)
        self._plot_stack.addWidget(self._scroll_area)

        # --- Plot area wrapped in a QGroupBox ---
        plot_group = QGroupBox("Chromatogram")
        plot_group.setFlat(True)
        plot_vbox = QVBoxLayout(plot_group)
        plot_vbox.setContentsMargins(0, 16, 0, 4)
        plot_vbox.addWidget(self._plot_stack)
        outer.addWidget(plot_group, 1)

        # --- Selected called-sequence range and FASTA output ---
        seq_group = QGroupBox("Called Sequence (5\u2019 to 3\u2019)")
        seq_vbox = QVBoxLayout(seq_group)
        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("Output File:"))
        self._output_edit = QLineEdit()
        self._output_edit.setPlaceholderText("Leave blank to auto-generate an output FASTA file")
        self._output_edit.setToolTip("Save the selected range as FASTA; an empty path uses the AB1 input folder")
        output_row.addWidget(self._output_edit, 1)
        self._btn_browse_output = QPushButton("Browse")
        self._btn_browse_output.clicked.connect(self._browse_output_file)
        output_row.addWidget(self._btn_browse_output)
        seq_vbox.addLayout(output_row)

        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("Range \u2014 Start:"))
        self._spin_start = QSpinBox()
        self._spin_start.setMinimum(1)
        self._spin_start.setMaximum(9999)
        self._spin_start.setValue(1)
        self._spin_start.setToolTip("First base position to save (1-based, inclusive)")
        range_row.addWidget(self._spin_start)
        range_row.addWidget(QLabel("End:"))
        self._spin_end = QSpinBox()
        self._spin_end.setMinimum(1)
        self._spin_end.setMaximum(9999)
        self._spin_end.setValue(1)
        self._spin_end.setToolTip("Last base position to save (1-based, inclusive)")
        range_row.addWidget(self._spin_end)
        range_row.addSpacing(16)
        range_row.addWidget(self._chk_quality)
        self._btn_export_fasta = QPushButton("Save to File")
        self._btn_export_fasta.setToolTip(
            "Save the selected range (Start–End, inclusive) as a FASTA file"
        )
        self._btn_export_fasta.setProperty("accentButton", True)
        self._btn_export_fasta.setEnabled(False)
        self._spin_start.setEnabled(False)
        self._spin_end.setEnabled(False)
        range_row.addStretch()
        seq_vbox.addLayout(range_row)
        outer.addWidget(seq_group)

        # --- Status bar + sequence/plot exports, result folder, clear and help ---
        self.status_layout = QHBoxLayout()
        self._status_label = QLabel("Load an AB1 file to begin")
        self.status_layout.addWidget(self._status_label)
        self.status_layout.addStretch()
        self.status_layout.addWidget(self._btn_export_fasta)
        self._btn_export_plot = QPushButton("Export Plot")
        self._btn_export_plot.setProperty("accentButton", True)
        self._btn_export_plot.setToolTip("Save the current chromatogram as an image file")
        self._btn_export_plot.setEnabled(False)
        self._btn_export_plot.style().unpolish(self._btn_export_plot)
        self._btn_export_plot.style().polish(self._btn_export_plot)
        self.status_layout.addWidget(self._btn_export_plot)
        self._btn_result_folder = QPushButton("Result Folder")
        self._btn_result_folder.setProperty("accentButton", True)
        self._btn_result_folder.setEnabled(False)
        self._btn_result_folder.clicked.connect(self._open_result_folder)
        self.status_layout.addWidget(self._btn_result_folder)
        self._btn_clear = QPushButton("Clear")
        self._btn_clear.setToolTip("Clear the loaded chromatogram and reset the view")
        self.status_layout.addWidget(self._btn_clear)
        self._btn_help = QPushButton("Help")
        self._btn_help.setToolTip("Show usage help")
        self.status_layout.addWidget(self._btn_help)
        # Same one-word/two-word width rule as the BaseTabWidget tabs.
        unify_status_button_sizes(self)
        outer.addLayout(self.status_layout)

        # --- Signal connections ---
        self._btn_browse.clicked.connect(self._browse)
        self._btn_example.clicked.connect(self._load_example)
        self._btn_export_plot.clicked.connect(self._export_plot)
        self._btn_clear.clicked.connect(self._clear_all)
        self._btn_export_fasta.clicked.connect(self._export_fasta)
        self._btn_help.clicked.connect(self._show_help)
        self._chk_quality.stateChanged.connect(lambda _: self._draw_chromatogram())

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open AB1 File",
            "",
            "AB1 Files (*.ab1 *.AB1);;All Files (*)",
        )
        if path:
            self._file_edit.setText(path)
            self._load()  # auto-load so the user sees the chromatogram immediately

    def _load_example(self) -> None:
        """Stage the bundled example AB1 trace, fill the path, and auto-load."""
        path = stage_example("sanger", "pUC19_M13F.ab1")
        if not path:
            QMessageBox.information(
                self,
                "Example",
                "Failed to load example data. Please check your installation.",
            )
            return
        self._file_edit.setText(path)
        self._load()  # auto-load so the user sees the chromatogram immediately

    # ------------------------------------------------------------------
    # Drag-and-drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith(".ab1"):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        self._file_edit.setText(path)
        self._load()  # auto-load so the user sees the chromatogram immediately

    def _load(self) -> None:
        path = self._file_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "No File", "Please select an AB1 file first.")
            return
        self._btn_browse.setEnabled(False)
        self._btn_export_fasta.setEnabled(False)
        self._spin_start.setEnabled(False)
        self._spin_end.setEnabled(False)
        self._last_output_path = ""
        self._btn_result_folder.setEnabled(False)
        self._btn_export_plot.setEnabled(False)
        self._set_status("Loading\u2026")

        self._thread = _LoadThread(self)
        self._worker = _LoadWorker(path)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_loaded)
        self._worker.error.connect(self._on_error)
        # Quit the thread directly from the worker so it stops even if the
        # main thread stops pumping events (e.g. app teardown in tests).
        self._worker.finished.connect(self._thread.quit, Qt.ConnectionType.DirectConnection)
        self._worker.error.connect(self._thread.quit, Qt.ConnectionType.DirectConnection)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._cleanup_thread)
        self._thread.start()

    def _cleanup_thread(self) -> None:
        self._worker = None
        self._thread = None
        self._btn_browse.setEnabled(True)

    def shutdown(self) -> None:
        """Stop and park the loader thread before the tab is destroyed.

        Called by ``MainWindow.close_tab``. ``park_qthread`` defers C++
        destruction of a still-running thread to its ``finished`` signal, so
        Qt never aborts with "QThread: Destroyed while thread is still
        running". ``self._worker`` is intentionally left alone here — it runs
        inside the thread and must outlive it.
        """
        stop_worker_object(self._thread)
        park_qthread(self._thread)
        self._thread = None

    @skip_when_closing
    def _on_loaded(self, abi_data: dict, sequence: str, quality: List[int]) -> None:
        self._abi_data = abi_data
        self._sequence = sequence
        self._quality = quality
        n = len(sequence)
        self._spin_start.setMaximum(n)
        self._spin_end.setMaximum(n)
        self._spin_start.setValue(1)
        self._spin_end.setValue(n)
        self._spin_start.setEnabled(True)
        self._spin_end.setEnabled(True)
        self._last_output_path = ""
        self._btn_result_folder.setEnabled(False)
        self._btn_export_fasta.setEnabled(True)
        self._btn_export_plot.setEnabled(True)

        self._draw_chromatogram()
        self._plot_stack.setCurrentIndex(1)  # show the chromatogram
        self._set_status(f"Loaded \u2014 {n} bases")

    @skip_when_closing
    def _on_error(self, msg: str) -> None:
        QMessageBox.critical(self, "Load Error", msg)
        self._set_status("Error: " + msg[:120])

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw_chromatogram(self) -> None:
        if self._abi_data is None:
            return

        channels = self._abi_data["channels"]
        peak_locs = self._abi_data["peak_locs"]
        n_scans = max((len(v) for v in channels.values()), default=0)

        show_quality = self._chk_quality.isChecked() and bool(self._quality)

        # ── Determine x-axis bounds from base-call positions ─────────
        # Raw scan data (n_scans) often extends well past the last base
        # call, producing large empty whitespace on the right.  Tighten
        # the view to the base-called region with modest padding.
        if peak_locs:
            _pad = 30
            x_min = max(0, peak_locs[0] - _pad)
            x_max = min(n_scans, peak_locs[-1] + _pad)
        else:
            x_min, x_max = 0, n_scans

        # Resize canvas to match the visible data range.
        # Set the figure dimensions first, then force the canvas widget
        # to the matching pixel size so they stay in sync.
        dpi = self._fig.get_dpi()
        # Fixed pixel gutters on the left and right of the data; the axes
        # span the canvas between the two gutters.
        left_gutter_px = 200
        right_gutter_px = 200
        canvas_w = max(
            _MIN_CANVAS_W,
            int(x_max - x_min) * _PX_PER_SCAN + left_gutter_px + right_gutter_px,
        )
        canvas_h = (_TRACE_H_PX + _QUAL_H_PX) if show_quality else _TRACE_H_PX
        self._fig.set_size_inches(canvas_w / dpi, canvas_h / dpi)
        self._canvas.setFixedSize(canvas_w, canvas_h)

        self._fig.clear()

        if show_quality:
            gs = self._fig.add_gridspec(2, 1, height_ratios=[4, 1], hspace=0.05)
            ax_trace = self._fig.add_subplot(gs[0])
            ax_qual = self._fig.add_subplot(gs[1], sharex=ax_trace)
        else:
            ax_trace = self._fig.add_subplot(111)
            ax_qual = None

        ax_trace.set_facecolor("#fafafa")

        # --- Plot raw fluorescence traces ---
        y_max = 1.0
        for base in ("G", "A", "T", "C"):
            ys = channels.get(base, [])
            if not ys:
                continue
            xs = range(len(ys))
            ax_trace.plot(xs, ys, color=_TRACE_COLOR[base], linewidth=0.7, label=base, alpha=0.9)
            y_max = max(y_max, max(ys))

        # --- Base letter annotations at peak scan positions ---
        y_label = y_max * 1.06
        seq = self._sequence
        n = len(seq)
        for i, base in enumerate(seq):
            if i >= len(peak_locs):
                break
            ax_trace.text(
                peak_locs[i],
                y_label,
                base,
                ha="center",
                va="bottom",
                fontsize=6.5,
                fontweight="bold",
                color=_BASE_COLOR.get(base, "#888888"),
            )

        # --- X-ticks at multiples of 10 (10, 20, 30 …) ---
        tick_indices = list(range(9, min(n, len(peak_locs)), 10))  # 0-based: 9,19,29…
        tick_scan_pos = [peak_locs[i] for i in tick_indices]
        ax_trace.set_xticks(tick_scan_pos)
        ax_trace.set_xticklabels([str(i + 1) for i in tick_indices], fontsize=7)
        ax_trace.set_xlim(x_min, x_max)
        ax_trace.set_ylim(0, y_label * 1.12)
        ax_trace.set_ylabel("Fluorescence", fontsize=8)
        ax_trace.legend(loc="upper right", fontsize=7.5, framealpha=0.7)

        # --- Phred quality track (shares scan x-axis) ---
        if ax_qual is not None:
            n_q = min(len(self._quality), len(peak_locs))
            if n_q > 0:
                q_vals = self._quality[:n_q]
                xs_q = peak_locs[:n_q]
                # Bar widths: each bar spans the midpoints between adjacent peaks
                avg_gap = (xs_q[-1] - xs_q[0]) / max(n_q - 1, 1) if n_q > 1 else 10
                bar_lefts: List[float] = []
                bar_widths: List[float] = []
                for i in range(n_q):
                    lh = (xs_q[i] - xs_q[i - 1]) / 2 if i > 0 else xs_q[i] / 2
                    rh = (xs_q[i + 1] - xs_q[i]) / 2 if i + 1 < n_q else avg_gap / 2
                    bar_lefts.append(xs_q[i] - lh)
                    bar_widths.append(lh + rh)
                q_colors = [
                    "#2ca02c" if v >= 30 else "#ff7f0e" if v >= 20 else "#d62728" for v in q_vals
                ]
                ax_qual.bar(
                    bar_lefts,
                    q_vals,
                    width=bar_widths,
                    color=q_colors,
                    linewidth=0,
                    align="edge",
                )
                ax_qual.axhline(20, color="#aaa", linewidth=0.6, linestyle="--")
                ax_qual.axhline(30, color="#888", linewidth=0.6, linestyle="--")
                ax_qual.set_ylim(0, max(65, max(q_vals) + 5))
                ax_qual.set_ylabel("Phred Q", fontsize=7)
                ax_qual.set_facecolor("#fafafa")
            ax_trace.tick_params(labelbottom=False)

        # The canvas is sized to the data range plus fixed gutters on both
        # sides, so the axes span from the left gutter to the right gutter.
        self._fig.subplots_adjust(
            left=left_gutter_px / canvas_w,
            right=(canvas_w - right_gutter_px) / canvas_w,
            top=0.92,
            bottom=0.10,
        )
        self._canvas.draw()

    # ------------------------------------------------------------------
    # Export / clear helpers
    # ------------------------------------------------------------------

    def _browse_output_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save selected sequence", self._output_edit.text() or "sanger_sequence.fasta",
            "FASTA Files (*.fasta *.fa *.fas);;All Files (*)",
        )
        if path:
            self._output_edit.setText(os.path.normpath(path))

    def _open_result_folder(self) -> None:
        if self._last_output_path and os.path.isfile(self._last_output_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(self._last_output_path)))

    def _export_fasta(self) -> None:
        """Save the selected 1-based inclusive range without displaying sequence text."""
        if not self._sequence:
            QMessageBox.warning(self, "Export Error", "Load an AB1 file first.")
            return
        start = self._spin_start.value()
        end = self._spin_end.value()
        if start > end:
            self._set_status("Error: Invalid range")
            QMessageBox.warning(self, "Invalid Range", "Start must be \u2264 End.")
            return
        selected = self._sequence[start - 1 : end]
        path = self._output_edit.text().strip()
        if not path:
            input_path = self._file_edit.text().strip()
            if not input_path:
                QMessageBox.warning(self, "Export Error", "Load an AB1 file first.")
                return
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            path = os.path.join(os.path.dirname(os.path.abspath(input_path)), f"sanger_{stamp}.fasta")
        path = os.path.abspath(path)
        if os.path.normcase(os.path.realpath(path)) == os.path.normcase(
            os.path.realpath(self._file_edit.text().strip())
        ):
            self._set_status("Error: Output path matches the input file")
            QMessageBox.warning(self, "Export Error", "Choose an output file different from the AB1 input.")
            return
        valid, error = validate_output_path(path)
        if not valid:
            self._set_status("Error: Invalid output path")
            QMessageBox.warning(self, "Export Error", error)
            return
        processor = FASTAProcessor()
        processor.parse_text(f">sanger_read range={start}-{end} len={len(selected)}\n{selected}\n")
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=os.path.dirname(path), suffix=".fasta", delete=False
            ) as temporary:
                temporary_path = temporary.name
            if not processor.save_file(temporary_path):
                raise OSError("Cannot write the selected sequence to FASTA.")
            os.replace(temporary_path, path)
        except OSError as exc:
            self._set_status("Error: Cannot save FASTA")
            QMessageBox.warning(self, "Export Error", str(exc))
            return
        finally:
            if temporary_path and os.path.isfile(temporary_path):
                os.remove(temporary_path)
        self._output_edit.setText(path)
        self._output_edit.setToolTip(path)
        self._last_output_path = path
        self._btn_result_folder.setEnabled(True)
        self._status_label.setToolTip(path)
        self._set_status(f"FASTA saved: {os.path.basename(path)}")

    def _export_plot(self) -> None:
        """Save the current chromatogram figure as an image file."""
        if self._abi_data is None:
            QMessageBox.warning(self, "Export Error", "Load an AB1 file first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Plot",
            "chromatogram.png",
            "PNG Images (*.png);;PDF Files (*.pdf);;SVG Files (*.svg)",
        )
        if path:
            try:
                self._fig.savefig(path, dpi=150, bbox_inches="tight", pad_inches=0.15)
                self._set_status(f"Plot saved: {path}")
            except Exception as e:
                QMessageBox.warning(self, "Export Error", str(e))

    def _clear_all(self) -> None:
        """Reset the viewer to its initial empty state."""
        self._abi_data = None
        self._sequence = ""
        self._quality = []
        self._file_edit.clear()
        self._output_edit.clear()
        self._last_output_path = ""
        self._btn_result_folder.setEnabled(False)
        self._spin_start.setEnabled(False)
        self._spin_end.setEnabled(False)
        self._status_label.setToolTip("")
        self._btn_export_fasta.setEnabled(False)
        self._btn_export_plot.setEnabled(False)
        self._spin_start.setMaximum(1)
        self._spin_end.setMaximum(1)
        self._spin_start.setValue(1)
        self._spin_end.setValue(1)
        self._fig.clear()
        self._canvas.draw_idle()
        self._plot_stack.setCurrentIndex(0)  # back to the empty-state hint
        self._set_status("Load an AB1 file to begin")

    # ------------------------------------------------------------------
    # Help
    # ------------------------------------------------------------------

    def _show_help(self) -> None:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import (
            QDialog,
            QLabel,
            QPushButton,
            QScrollArea,
            QVBoxLayout,
        )

        help_text = (
            "<h2>Sanger Chromatogram Viewer &mdash; AB1 Chromatogram Browser</h2>"
            "<p><b>What does this tool do?</b><br>"
            "It displays Sanger sequencing AB1 trace files as a scrollable"
            " chromatogram. You can inspect the raw fluorescence traces, review"
            " Phred quality scores, and save selected sequence ranges as FASTA files"
            " for downstream use.</p>"
            "<h3>Quick Start</h3>"
            "<ol>"
            "<li>Click <b>Browse</b> or drag-and-drop an AB1 file onto the window</li>"
            "<li>The chromatogram loads automatically with base calls and quality data</li>"
            "<li>Click <b>Export Plot</b> to save the chromatogram as an image file</li>"
            "<li>Toggle the <b>Phred quality track</b> to show or hide quality bars</li>"
            "<li>Set Start / End positions, choose an <b>Output File</b>, and click <b>Save to File</b> to export the selected range</li>"
            "</ol>"
            "<h3>Chromatogram Colours</h3>"
            "<table border='0' cellpadding='4' cellspacing='2'>"
            "<tr><td><b>Base</b></td><td><b>Colour</b></td></tr>"
            "<tr><td>A</td><td style='color:#009900'>Green</td></tr>"
            "<tr><td>T</td><td style='color:#DD0000'>Red</td></tr>"
            "<tr><td>G</td><td>Black</td></tr>"
            "<tr><td>C</td><td style='color:#0055CC'>Blue</td></tr>"
            "</table>"
            "<h3>Phred Quality Track</h3>"
            "<table border='0' cellpadding='4' cellspacing='2'>"
            "<tr><td style='color:#2ca02c'><b>Green &ge; 30</b></td>"
            "<td>High quality &mdash; base call is very reliable (error rate &lt; 0.1%)</td></tr>"
            "<tr><td style='color:#ff7f0e'><b>Orange &ge; 20</b></td>"
            "<td>Medium quality &mdash; acceptable for most purposes (error rate &lt; 1%)</td></tr>"
            "<tr><td style='color:#d62728'><b>Red &lt; 20</b></td>"
            "<td>Low quality &mdash; base call may be unreliable; consider trimming</td></tr>"
            "</table>"
            "<h3>Saving Sequence Ranges</h3>"
            "<ul>"
            "<li>Positions are <b>1-based</b> (the first base is position 1)</li>"
            "<li>Start must be &le; End</li>"
            "<li>Leave Output File blank to generate a FASTA file beside the AB1 input; <b>Result Folder</b> opens its location.</li>"
            "<li>Both endpoints are included; the saved FASTA header records the selected range and length</li>"
            "</ul>"
            "<h3>Tips</h3>"
            "<ul>"
            "<li>Use <b>Export Plot</b> to save the current view as a PNG / PDF / SVG for reports or papers</li>"
            "<li>If base calls mismatch the peaks, the sequencing may have mixed templates or poor quality</li>"
            "<li>Supported format: AB1 (Applied Biosystems). SCF and ZTR are not currently supported.</li>"
            "<li>Browse or drag-and-drop a different file to reload; <b>Clear</b> resets the viewer</li>"
            "</ul>"
        )

        dialog = QDialog(self)
        dialog.setWindowTitle("Help - Sanger Chromatogram Viewer")
        dialog.resize(600, 480)
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

    def _set_status(self, msg: str) -> None:
        self._status_label.setText(msg)
