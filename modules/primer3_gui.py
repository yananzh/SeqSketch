"""
PCR Primer Assistant (PyQt6 + primer3-py)
"""

import csv
import importlib
import os
import sys
from typing import Any, Dict

from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

# matplotlib for primer binding site map
from matplotlib.figure import Figure
from PyQt6.QtCore import QObject, Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# openpyxl for Excel export
try:
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    _HAS_OPENPYXL = True
except ImportError:
    _HAS_OPENPYXL = False

# Shared styling
from utils.common_components import apply_sequence_editor_style
from utils.example_data import load_example_text

try:
    p3_bindings = importlib.import_module("primer3.bindings")
except ImportError:
    p3_bindings = None


class Worker(QObject):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, seq_args: Dict[str, Any], global_args: Dict[str, Any]):
        super().__init__()
        self.seq_args = seq_args
        self.global_args = global_args

    def run(self):
        try:
            self.progress.emit("Calling Primer3 core for computation...")
            if p3_bindings is None:
                self.error.emit("Failed to import primer3. Please install: pip install primer3-py")
                return
            if hasattr(p3_bindings, "design_primers"):
                results = p3_bindings.design_primers(
                    seq_args=self.seq_args,
                    global_args=self.global_args,
                )
            else:
                results = p3_bindings.designPrimers(
                    seq_args=self.seq_args,
                    global_args=self.global_args,
                )
            self.progress.emit("Computation finished.")
            self.finished.emit(results)
        except Exception as exc:
            self.error.emit(f"Error: {exc}")


class PrimerDesignTab(QWidget):
    def __init__(self):
        super().__init__()
        self.worker: Worker | None = None
        self.worker_thread: QThread | None = None
        self.current_results: dict[str, Any] = {}
        self.row_detail_cache: list[dict[str, Any]] = []
        self._current_template_seq: str = ""
        self._last_export_dir: str = ""

        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter, 1)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(8)

        seq_group = QGroupBox(self.tr("1. Template Sequence"))
        seq_v = QVBoxLayout(seq_group)
        self.seq_input = QTextEdit()
        apply_sequence_editor_style(self.seq_input)
        # The group box already draws a 1px border (styles.qss); keeping the
        # editor's own border shows a faint double frame, so strip it like
        # BaseTabWidget does for its input/output editors.
        _style = self.seq_input.styleSheet()
        _style = _style.replace("border: 1px solid #94a3b8;", "border: none;")
        self.seq_input.setStyleSheet(_style)
        self.seq_input.setAcceptDrops(True)
        # Manual line break: QTextEdit placeholders do not word-wrap, and the
        # splitter's left panel is too narrow for the full one-line text.
        self.seq_input.setPlaceholderText(
            self.tr("Paste FASTA or raw DNA sequence here,\nor drag & drop a file...")
        )

        # Patch drag-drop to load file content directly
        _tab = self

        def _drag_enter(widget, event):
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
            else:
                QTextEdit.dragEnterEvent(widget, event)

        def _drop(widget, event):
            if event.mimeData().hasUrls():
                for url in event.mimeData().urls():
                    path = url.toLocalFile()
                    if path and os.path.isfile(path):
                        try:
                            with open(path, "r", encoding="utf-8") as f:
                                _tab.seq_input.setText(f.read())
                            _tab.status_label.setText(f"Dropped file: {path}")
                        except (OSError, UnicodeDecodeError):
                            pass
                        return
            QTextEdit.dropEvent(widget, event)

        import types

        self.seq_input.dragEnterEvent = types.MethodType(_drag_enter, self.seq_input)
        self.seq_input.dropEvent = types.MethodType(_drop, self.seq_input)

        seq_btn_row = QHBoxLayout()
        self.load_seq_btn = QPushButton(self.tr("Browse"))
        self.example_seq_btn = QPushButton(self.tr("Example"))
        self.example_seq_btn.setToolTip(self.tr("Load HBB exon 1 example sequence"))
        self.clear_seq_btn = QPushButton(self.tr("Clear"))
        seq_btn_row.addWidget(self.load_seq_btn)
        seq_btn_row.addWidget(self.example_seq_btn)
        seq_btn_row.addStretch()

        seq_v.addWidget(self.seq_input)
        seq_v.addLayout(seq_btn_row)

        general_group = QGroupBox(self.tr("2. Product Parameters"))
        general_form = QFormLayout(general_group)

        self.prod_size_min = QSpinBox()
        self.prod_size_max = QSpinBox()
        self.prod_size_min.setRange(50, 10000)
        self.prod_size_max.setRange(50, 10000)
        self.prod_size_min.setValue(80)
        self.prod_size_max.setValue(150)
        self.prod_size_min.setFixedWidth(76)
        self.prod_size_max.setFixedWidth(76)
        self.prod_size_min.setToolTip(
            self.tr(
                "Minimum expected PCR product size (bp).\n"
                "Recommended: 80-200 bp for qPCR, 200-1000 bp for conventional PCR."
            )
        )
        self.prod_size_max.setToolTip(
            self.tr("Maximum expected PCR product size (bp).\nMust be >= minimum size.")
        )
        size_box = QWidget()
        size_h = QHBoxLayout(size_box)
        size_h.setContentsMargins(0, 0, 0, 0)
        size_h.setSpacing(6)
        size_h.addWidget(self.prod_size_min)
        size_h.addWidget(self.prod_size_max)
        size_h.addStretch()

        self.num_primers_spin = QSpinBox()
        self.num_primers_spin.setRange(1, 30)
        self.num_primers_spin.setValue(5)
        self.num_primers_spin.setFixedWidth(76)
        self.num_primers_spin.setToolTip(
            self.tr(
                "Number of primer pairs to return.\n"
                "Higher values give more options but take longer to compute."
            )
        )
        count_box = QWidget()
        count_h = QHBoxLayout(count_box)
        count_h.setContentsMargins(0, 0, 0, 0)
        count_h.setSpacing(6)
        count_h.addWidget(self.num_primers_spin)
        count_h.addStretch()

        size_label = QLabel(self.tr("Product Size (Min/Max):"))
        size_label.setFixedWidth(180)
        general_form.addRow(size_label, size_box)
        count_label = QLabel(self.tr("Primer Pair Count:"))
        count_label.setFixedWidth(180)
        general_form.addRow(count_label, count_box)

        primer_group = QGroupBox(self.tr("3. Primer Parameters"))
        primer_form = QFormLayout(primer_group)

        self.p_len_min = QSpinBox()
        self.p_len_opt = QSpinBox()
        self.p_len_max = QSpinBox()
        for spin in (self.p_len_min, self.p_len_opt, self.p_len_max):
            spin.setRange(15, 35)
            spin.setFixedWidth(68)
        self.p_len_min.setValue(18)
        self.p_len_opt.setValue(20)
        self.p_len_max.setValue(25)
        self.p_len_min.setToolTip(self.tr("Minimum acceptable primer length (nt)."))
        self.p_len_opt.setToolTip(
            self.tr("Optimal primer length (nt). Primer3 will prefer this length.")
        )
        self.p_len_max.setToolTip(self.tr("Maximum acceptable primer length (nt)."))
        len_box = QWidget()
        len_h = QHBoxLayout(len_box)
        len_h.setContentsMargins(0, 0, 0, 0)
        len_h.setSpacing(6)
        len_h.addWidget(self.p_len_min)
        len_h.addWidget(self.p_len_opt)
        len_h.addWidget(self.p_len_max)

        self.p_tm_min = QDoubleSpinBox()
        self.p_tm_opt = QDoubleSpinBox()
        self.p_tm_max = QDoubleSpinBox()
        for spin in (self.p_tm_min, self.p_tm_opt, self.p_tm_max):
            spin.setRange(40, 85)
            spin.setDecimals(0)
            spin.setSingleStep(1)
            spin.setFixedWidth(68)
        self.p_tm_min.setValue(57)
        self.p_tm_opt.setValue(60)
        self.p_tm_max.setValue(63)
        self.p_tm_min.setToolTip(
            self.tr("Minimum acceptable melting temperature (°C).\nTypical range: 55-60°C.")
        )
        self.p_tm_opt.setToolTip(
            self.tr("Optimal melting temperature (°C).\nPrimer3 will prefer primers near this Tm.")
        )
        self.p_tm_max.setToolTip(
            self.tr("Maximum acceptable melting temperature (°C).\nTypical range: 60-65°C.")
        )
        tm_box = QWidget()
        tm_h = QHBoxLayout(tm_box)
        tm_h.setContentsMargins(0, 0, 0, 0)
        tm_h.setSpacing(6)
        tm_h.addWidget(self.p_tm_min)
        tm_h.addWidget(self.p_tm_opt)
        tm_h.addWidget(self.p_tm_max)

        self.p_gc_min = QDoubleSpinBox()
        self.p_gc_opt = QDoubleSpinBox()
        self.p_gc_max = QDoubleSpinBox()
        for spin in (self.p_gc_min, self.p_gc_opt, self.p_gc_max):
            spin.setRange(20, 80)
            spin.setDecimals(0)
            spin.setSingleStep(1)
            spin.setFixedWidth(68)
        self.p_gc_min.setValue(40)
        self.p_gc_opt.setValue(50)
        self.p_gc_max.setValue(60)
        self.p_gc_min.setToolTip(
            self.tr("Minimum acceptable GC content (%).\nTypical range: 40-60%.")
        )
        self.p_gc_opt.setToolTip(
            self.tr("Optimal GC content (%).\nPrimer3 will prefer primers near this GC%.")
        )
        self.p_gc_max.setToolTip(
            self.tr("Maximum acceptable GC content (%).\nTypical range: 40-60%.")
        )
        gc_box = QWidget()
        gc_h = QHBoxLayout(gc_box)
        gc_h.setContentsMargins(0, 0, 0, 0)
        gc_h.setSpacing(6)
        gc_h.addWidget(self.p_gc_min)
        gc_h.addWidget(self.p_gc_opt)
        gc_h.addWidget(self.p_gc_max)

        len_label = QLabel(self.tr("Length (Min/Opt/Max):"))
        len_label.setFixedWidth(150)
        primer_form.addRow(len_label, len_box)
        tm_label = QLabel(self.tr("Tm (°C) (Min/Opt/Max):"))
        tm_label.setFixedWidth(150)
        primer_form.addRow(tm_label, tm_box)
        gc_label = QLabel(self.tr("GC (%) (Min/Opt/Max):"))
        gc_label.setFixedWidth(150)
        primer_form.addRow(gc_label, gc_box)

        # ── 4. Advanced Parameters ──────────────────────────────────
        adv_group = QGroupBox(self.tr("4. Advanced Parameters"))
        adv_form = QFormLayout(adv_group)

        self.salt_mono_spin = QDoubleSpinBox()
        self.salt_mono_spin.setRange(10, 200)
        self.salt_mono_spin.setDecimals(0)
        self.salt_mono_spin.setSingleStep(1)
        self.salt_mono_spin.setValue(50)
        self.salt_mono_spin.setFixedWidth(104)
        self.salt_mono_spin.setSuffix(" mM")
        self.salt_mono_spin.setToolTip(
            self.tr(
                "Monovalent salt concentration (Na⁺/K⁺).\n"
                "Affects Tm calculation. Standard PCR: 50 mM."
            )
        )
        salt_label = QLabel(self.tr("Salt (Monovalent):"))
        salt_label.setFixedWidth(150)
        adv_form.addRow(salt_label, self.salt_mono_spin)

        self.mg_spin = QDoubleSpinBox()
        self.mg_spin.setRange(1, 10)
        self.mg_spin.setDecimals(0)
        self.mg_spin.setSingleStep(1)
        self.mg_spin.setValue(3)
        self.mg_spin.setFixedWidth(104)
        self.mg_spin.setSuffix(" mM")
        self.mg_spin.setToolTip(
            self.tr(
                "Divalent salt concentration (Mg²⁺).\n"
                "Standard PCR: 1.5 mM; qPCR typically: 2.5-3.5 mM."
            )
        )
        mg_label = QLabel(self.tr("Mg²⁺:"))
        mg_label.setFixedWidth(150)
        adv_form.addRow(mg_label, self.mg_spin)

        # Hidden defaults for less-commonly-adjusted parameters
        self.max_poly_x_spin = QSpinBox()
        self.max_poly_x_spin.setValue(4)
        self.max_self_any_spin = QDoubleSpinBox()
        self.max_self_any_spin.setDecimals(0)
        self.max_self_any_spin.setSingleStep(1)
        self.max_self_any_spin.setValue(8)
        self.max_self_end_spin = QDoubleSpinBox()
        self.max_self_end_spin.setDecimals(0)
        self.max_self_end_spin.setSingleStep(1)
        self.max_self_end_spin.setValue(3)
        self.max_hairpin_tm_spin = QDoubleSpinBox()
        self.max_hairpin_tm_spin.setDecimals(0)
        self.max_hairpin_tm_spin.setSingleStep(1)
        self.max_hairpin_tm_spin.setValue(47)
        self.max_diff_tm_spin = QDoubleSpinBox()
        self.max_diff_tm_spin.setDecimals(0)
        self.max_diff_tm_spin.setSingleStep(1)
        self.max_diff_tm_spin.setValue(2)
        self.gc_clamp_spin = QSpinBox()
        self.gc_clamp_spin.setValue(1)

        self.design_button = QPushButton(self.tr("Run"))
        self.help_btn = QPushButton(self.tr("Help"))
        self.export_excel_btn = QPushButton(self.tr("Export Excel"))
        self.open_folder_btn = QPushButton(self.tr("Result Folder"))
        self.open_folder_btn.setFixedWidth(110)
        self.open_folder_btn.setProperty("accentButton", True)
        self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.setToolTip(self.tr("Open the folder of the last exported results"))
        if not _HAS_OPENPYXL:
            self.export_excel_btn.setEnabled(False)
            self.export_excel_btn.setToolTip(
                self.tr("Excel export requires openpyxl. Install: pip install openpyxl")
            )

        left_layout.addWidget(seq_group)
        left_layout.addWidget(general_group)
        left_layout.addWidget(primer_group)
        left_layout.addWidget(adv_group)
        left_layout.addStretch()

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(8)

        # ── Primer binding site map (Matplotlib) ─────────────────
        map_group = QGroupBox(self.tr("Primer Binding Site Map"))
        map_v = QVBoxLayout(map_group)
        map_v.setContentsMargins(4, 4, 4, 4)
        map_v.setSpacing(2)
        self._primer_fig = Figure(figsize=(8, 4.0), dpi=100)
        self._primer_canvas = FigureCanvas(self._primer_fig)
        self._primer_canvas.setMinimumHeight(220)
        self._primer_toolbar = NavigationToolbar(self._primer_canvas, map_group)
        map_v.addWidget(self._primer_toolbar)
        map_v.addWidget(self._primer_canvas)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(8)
        self.results_table.setHorizontalHeaderLabels([
            "Pair #",
            "Type",
            "Sequence",
            "Position",
            "Length",
            "Tm",
            "GC%",
            "Product Size",
        ])
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        header = self.results_table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
            self.results_table.setColumnWidth(0, 50)
            self.results_table.setColumnWidth(1, 50)
            self.results_table.setColumnWidth(3, 65)
            self.results_table.setColumnWidth(4, 55)
            self.results_table.setColumnWidth(5, 55)
            self.results_table.setColumnWidth(6, 50)
            self.results_table.setColumnWidth(7, 95)

        right_layout.addWidget(map_group, 2)
        right_layout.addWidget(self.results_table, 3)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([380, 1040])

        # ── Status bar with buttons at the bottom ──
        status_row = QHBoxLayout()
        self.status_label = QLabel(self.tr("Ready"))
        self.status_label.setStyleSheet("color: #666; padding: 2px 8px;")
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        status_row.addWidget(self.design_button)
        status_row.addWidget(self.clear_seq_btn)
        status_row.addWidget(self.export_excel_btn)
        status_row.addWidget(self.open_folder_btn)
        status_row.addWidget(self.help_btn)
        status_row.addSpacing(8)
        root_layout.addLayout(status_row)

    def connect_signals(self):
        self.design_button.clicked.connect(self.start_design_task)
        self.seq_input.textChanged.connect(self.on_sequence_changed)

        self.load_seq_btn.clicked.connect(self.load_sequence_from_file)
        self.example_seq_btn.clicked.connect(self._load_example)
        self.clear_seq_btn.clicked.connect(self.clear_sequence)
        self.export_excel_btn.clicked.connect(self.export_results_excel)
        self.open_folder_btn.clicked.connect(self._open_result_folder)
        self.help_btn.clicked.connect(self.show_help_dialog)
        self.results_table.itemSelectionChanged.connect(self._draw_primer_map)

    def _normalize_sequence(self, raw_text: str) -> str:
        text = raw_text.strip()
        if text.startswith(">"):
            lines = text.splitlines()
            seq_lines = [line.strip() for line in lines if not line.startswith(">")]
            return "".join(seq_lines).replace(" ", "").replace("\r", "").replace("\n", "").upper()
        return text.replace(" ", "").replace("\r", "").replace("\n", "").upper()

    def _validate_sequence(self, sequence: str) -> bool:
        return bool(sequence) and all(base in "ACGTUN" for base in sequence)

    def load_sequence_from_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Sequence File",
            "",
            "Sequence files (*.fa *.fasta *.fna *.txt);;All files (*)",
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                text = handle.read()
            self.seq_input.setPlainText(text)
            self.status_label.setText(f"Loaded sequence: {file_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", f"Failed to read file:\n{exc}")

    def _load_example(self):
        """Load the bundled HBB exon 1 DNA example."""
        text = load_example_text("dna", "hbb_exon1.fasta")
        if not text:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. Please check your installation."),
            )
            return
        self.seq_input.setPlainText(text)
        self.status_label.setText(self.tr("Loaded example data: hbb_exon1.fasta"))

    def clear_sequence(self):
        self.seq_input.clear()
        self.results_table.setRowCount(0)
        self.current_results.clear()
        self.row_detail_cache.clear()
        self._current_template_seq = ""
        self._clear_primer_map()
        self.open_folder_btn.setEnabled(False)
        self.status_label.setText(self.tr("Sequence and results cleared."))

    def apply_standard_presets(self):
        """Apply balanced preset values for qPCR primer design."""
        self.p_len_min.setValue(18)
        self.p_len_opt.setValue(20)
        self.p_len_max.setValue(25)

        self.p_tm_min.setValue(57)
        self.p_tm_opt.setValue(60)
        self.p_tm_max.setValue(63)

        self.p_gc_min.setValue(40)
        self.p_gc_opt.setValue(50)
        self.p_gc_max.setValue(60)

        self.max_poly_x_spin.setValue(4)
        self.max_self_any_spin.setValue(8)
        self.max_self_end_spin.setValue(3)
        self.max_hairpin_tm_spin.setValue(47)
        self.num_primers_spin.setValue(5)

        self.salt_mono_spin.setValue(50)
        self.mg_spin.setValue(3)

        self.prod_size_min.setValue(80)
        self.prod_size_max.setValue(150)
        self.status_label.setText("Applied qPCR preset parameters.")

    def on_sequence_changed(self):
        sequence = self._normalize_sequence(self.seq_input.toPlainText())
        self._current_template_seq = sequence

    def _validate_parameter_ranges(self) -> bool:
        if (
            self.p_len_min.value() > self.p_len_opt.value()
            or self.p_len_opt.value() > self.p_len_max.value()
        ):
            self.show_error_message("Primer length must satisfy Min ≤ Opt ≤ Max.")
            return False
        if (
            self.p_tm_min.value() > self.p_tm_opt.value()
            or self.p_tm_opt.value() > self.p_tm_max.value()
        ):
            self.show_error_message("Primer Tm must satisfy Min ≤ Opt ≤ Max.")
            return False
        if (
            self.p_gc_min.value() > self.p_gc_opt.value()
            or self.p_gc_opt.value() > self.p_gc_max.value()
        ):
            self.show_error_message("Primer GC must satisfy Min ≤ Opt ≤ Max.")
            return False
        if self.prod_size_min.value() > self.prod_size_max.value():
            self.show_error_message("Product size range is invalid (Min > Max).")
            return False
        return True

    def start_design_task(self):
        raw_text = self.seq_input.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "Input Error", "Please enter a valid DNA template sequence.")
            return

        sequence = self._normalize_sequence(raw_text)
        if not self._validate_sequence(sequence):
            QMessageBox.warning(
                self,
                "Input Error",
                "Please enter a valid DNA sequence (A/C/G/T/U/N only).",
            )
            return
        if len(sequence) < 50:
            QMessageBox.warning(self, "Input Error", "Sequence is too short (minimum 50 bp).")
            return
        if not self._validate_parameter_ranges():
            return

        self.design_button.setEnabled(False)
        self.status_label.setText("Preparing parameters...")
        self.results_table.setRowCount(0)
        self.current_results.clear()
        self.row_detail_cache.clear()

        seq_args = {
            "SEQUENCE_ID": "Template",
            "SEQUENCE_TEMPLATE": sequence,
        }
        global_args = {
            "PRIMER_OPT_SIZE": self.p_len_opt.value(),
            "PRIMER_MIN_SIZE": self.p_len_min.value(),
            "PRIMER_MAX_SIZE": self.p_len_max.value(),
            "PRIMER_OPT_TM": self.p_tm_opt.value(),
            "PRIMER_MIN_TM": self.p_tm_min.value(),
            "PRIMER_MAX_TM": self.p_tm_max.value(),
            "PRIMER_MIN_GC": self.p_gc_min.value(),
            "PRIMER_MAX_GC": self.p_gc_max.value(),
            "PRIMER_OPT_GC_PERCENT": self.p_gc_opt.value(),
            "PRIMER_NUM_RETURN": self.num_primers_spin.value(),
            "PRIMER_EXPLAIN_FLAG": 1,
            "PRIMER_SALT_MONOVALENT": self.salt_mono_spin.value(),
            "PRIMER_SALT_DIVALENT": self.mg_spin.value(),
            "PRIMER_MAX_DIFF_TM": self.max_diff_tm_spin.value(),
            "PRIMER_GC_CLAMP": self.gc_clamp_spin.value(),
            "PRIMER_MAX_POLY_X": self.max_poly_x_spin.value(),
            "PRIMER_MAX_SELF_ANY": self.max_self_any_spin.value(),
            "PRIMER_MAX_SELF_END": self.max_self_end_spin.value(),
            "PRIMER_MAX_HAIRPIN_TH": self.max_hairpin_tm_spin.value(),
        }

        global_args["PRIMER_PRODUCT_SIZE_RANGE"] = [
            self.prod_size_min.value(),
            self.prod_size_max.value(),
        ]

        self.worker_thread = QThread()
        self.worker = Worker(seq_args, global_args)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.update_results_table)
        self.worker.error.connect(self.show_error_message)
        self.worker.progress.connect(self.status_label.setText)

        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.error.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker_thread.start()
        self.status_label.setText("Background task started. Designing primers...")

    def _to_float_text(self, value: Any) -> str:
        if isinstance(value, (int, float)):
            return f"{value:.2f}"
        return str(value)

    def _safe_pos_length(self, pos_len: Any) -> tuple[str, str]:
        if isinstance(pos_len, list) and len(pos_len) >= 2:
            return str(pos_len[0]), str(pos_len[1])
        return "", ""

    def update_results_table(self, results: Dict[str, Any]):
        self.current_results = results
        num_returned = int(results.get("PRIMER_PAIR_NUM_RETURNED", 0) or 0)
        if num_returned == 0:
            explain = results.get("PRIMER_PAIR_EXPLAIN") or results.get("PRIMER_LEFT_EXPLAIN") or ""
            self.show_error_message(
                "No primer pairs found. Try relaxing constraints."
                + (f"\n\nPrimer3 explain: {explain}" if explain else "")
            )
            self.design_button.setEnabled(True)
            return

        self.results_table.setRowCount(num_returned * 2)
        self.row_detail_cache = []

        row_idx = 0
        for i in range(num_returned):
            product_size = results.get(f"PRIMER_PAIR_{i}_PRODUCT_SIZE", "")
            pair_penalty = results.get(f"PRIMER_PAIR_{i}_PENALTY", "")

            left = {
                "pair_index": i + 1,
                "type": "Fwd",
                "seq": results.get(f"PRIMER_LEFT_{i}_SEQUENCE", ""),
                "pos_len": results.get(f"PRIMER_LEFT_{i}", []),
                "tm": results.get(f"PRIMER_LEFT_{i}_TM", ""),
                "gc": results.get(f"PRIMER_LEFT_{i}_GC_PERCENT", ""),
                "self_any": results.get(f"PRIMER_LEFT_{i}_SELF_ANY_TH", ""),
                "self_end": results.get(f"PRIMER_LEFT_{i}_SELF_END_TH", ""),
                "hairpin": results.get(f"PRIMER_LEFT_{i}_HAIRPIN_TH", ""),
                "penalty": results.get(f"PRIMER_LEFT_{i}_PENALTY", ""),
                "pair_penalty": pair_penalty,
                "product_size": product_size,
            }
            right = {
                "pair_index": i + 1,
                "type": "Rev",
                "seq": results.get(f"PRIMER_RIGHT_{i}_SEQUENCE", ""),
                "pos_len": results.get(f"PRIMER_RIGHT_{i}", []),
                "tm": results.get(f"PRIMER_RIGHT_{i}_TM", ""),
                "gc": results.get(f"PRIMER_RIGHT_{i}_GC_PERCENT", ""),
                "self_any": results.get(f"PRIMER_RIGHT_{i}_SELF_ANY_TH", ""),
                "self_end": results.get(f"PRIMER_RIGHT_{i}_SELF_END_TH", ""),
                "hairpin": results.get(f"PRIMER_RIGHT_{i}_HAIRPIN_TH", ""),
                "penalty": results.get(f"PRIMER_RIGHT_{i}_PENALTY", ""),
                "pair_penalty": pair_penalty,
                "product_size": product_size,
            }

            for detail in (left, right):
                pos_text, length_text = self._safe_pos_length(detail["pos_len"])
                values = [
                    str(detail["pair_index"]),
                    detail["type"],
                    detail["seq"],
                    pos_text,
                    length_text,
                    self._to_float_text(detail["tm"]),
                    self._to_float_text(detail["gc"]),
                    str(detail["product_size"]),
                ]
                for col, val in enumerate(values):
                    item = QTableWidgetItem(val)
                    if detail["type"] == "Fwd":
                        item.setBackground(QColor("#eef7ff"))
                    else:
                        item.setBackground(QColor("#fff4ee"))
                    if col == 1:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.results_table.setItem(row_idx, col, item)
                self.row_detail_cache.append(detail)
                row_idx += 1

        self.status_label.setText(self.tr("Found %d primer pairs.") % num_returned)
        self.design_button.setEnabled(True)
        if self.results_table.rowCount() > 0:
            self.results_table.selectRow(0)

    def _table_to_tsv(self, selected_only: bool) -> str:
        headers = [
            self.results_table.horizontalHeaderItem(c).text()
            for c in range(self.results_table.columnCount())
        ]
        lines = ["\t".join(headers)]

        if selected_only:
            rows = sorted({idx.row() for idx in self.results_table.selectionModel().selectedRows()})
        else:
            rows = list(range(self.results_table.rowCount()))

        for row in rows:
            vals = []
            for col in range(self.results_table.columnCount()):
                item = self.results_table.item(row, col)
                vals.append(item.text() if item else "")
            lines.append("\t".join(vals))
        return "\n".join(lines)

    def copy_selected_rows(self):
        if self.results_table.rowCount() == 0:
            self.show_error_message("No results to copy.")
            return
        text = self._table_to_tsv(selected_only=True)
        QApplication.clipboard().setText(text)
        self.status_label.setText("Selected rows copied to clipboard.")

    def copy_all_rows(self):
        if self.results_table.rowCount() == 0:
            self.show_error_message("No results to copy.")
            return
        text = self._table_to_tsv(selected_only=False)
        QApplication.clipboard().setText(text)
        self.status_label.setText("All rows copied to clipboard.")

    def export_results_csv(self):
        if self.results_table.rowCount() == 0:
            self.show_error_message("No results to export.")
            return

        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Primer Results",
            "primer_results.csv",
            "CSV files (*.csv)",
        )
        if not out_path:
            return

        headers = [
            self.results_table.horizontalHeaderItem(c).text()
            for c in range(self.results_table.columnCount())
        ]
        try:
            with open(out_path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(headers)
                for row in range(self.results_table.rowCount()):
                    vals = []
                    for col in range(self.results_table.columnCount()):
                        item = self.results_table.item(row, col)
                        vals.append(item.text() if item else "")
                    writer.writerow(vals)
            self.status_label.setText(f"Exported CSV: {out_path}")
            self._last_export_dir = os.path.dirname(out_path)
            self.open_folder_btn.setEnabled(True)
        except Exception as exc:
            self.show_error_message(f"Failed to export CSV: {exc}")

    # ── Excel Export ─────────────────────────────────────────────────

    def _open_result_folder(self):
        """Open the folder of the most recently exported results file."""
        if self._last_export_dir and os.path.isdir(self._last_export_dir):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_export_dir))

    def export_results_excel(self):
        """Export primer results to an Excel (.xlsx) file."""
        if not _HAS_OPENPYXL:
            self.show_error_message(
                self.tr("Excel export requires openpyxl. Install: pip install openpyxl")
            )
            return
        if self.results_table.rowCount() == 0:
            self.show_error_message(self.tr("No results to export."))
            return

        out_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Export Primer Results to Excel"),
            "primer_results.xlsx",
            "Excel files (*.xlsx)",
        )
        if not out_path:
            return

        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Primer Results"

            # Header styling
            header_font = Font(name="Segoe UI", bold=True, color="FFFFFF", size=11)
            header_fill = PatternFill(start_color="4a90e2", end_color="4a90e2", fill_type="solid")
            header_align = Alignment(horizontal="center", vertical="center")
            thin_border = Border(
                left=Side(style="thin", color="cccccc"),
                right=Side(style="thin", color="cccccc"),
                top=Side(style="thin", color="cccccc"),
                bottom=Side(style="thin", color="cccccc"),
            )

            # Write headers
            for col in range(self.results_table.columnCount()):
                hdr_item = self.results_table.horizontalHeaderItem(col)
                cell = ws.cell(row=1, column=col + 1, value=hdr_item.text() if hdr_item else "")
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_align
                cell.border = thin_border

            # Fwd/Rev row fills
            fwd_fill = PatternFill(start_color="eef7ff", end_color="eef7ff", fill_type="solid")
            rev_fill = PatternFill(start_color="fff4ee", end_color="fff4ee", fill_type="solid")
            data_align = Alignment(vertical="center")

            # Write data rows
            for row in range(self.results_table.rowCount()):
                type_item = self.results_table.item(row, 1)
                row_fill = fwd_fill if (type_item and type_item.text() == "Fwd") else rev_fill
                for col in range(self.results_table.columnCount()):
                    item = self.results_table.item(row, col)
                    cell = ws.cell(row=row + 2, column=col + 1, value=item.text() if item else "")
                    cell.fill = row_fill
                    cell.alignment = data_align
                    cell.border = thin_border
                    cell.font = Font(name="Segoe UI", size=11)

            # Auto-fit column widths
            for col in range(self.results_table.columnCount()):
                max_width = 10
                for row in range(self.results_table.rowCount() + 1):
                    cell_val = ws.cell(row=row + 1, column=col + 1).value
                    if cell_val:
                        max_width = max(max_width, len(str(cell_val)) + 2)
                ws.column_dimensions[get_column_letter(col + 1)].width = min(max_width, 60)

            # Freeze header row
            ws.freeze_panes = "A2"

            wb.save(out_path)
            self.status_label.setText(self.tr("Exported Excel: %s") % out_path)
            self._last_export_dir = os.path.dirname(out_path)
            self.open_folder_btn.setEnabled(True)
        except Exception as exc:
            self.show_error_message(self.tr("Failed to export Excel: %s") % exc)

    # ── Primer Binding Site Map (Matplotlib) ─────────────────────────

    def _clear_primer_map(self):
        """Clear the primer binding site map figure."""
        self._primer_fig.clear()
        self._primer_canvas.draw_idle()

    def _draw_primer_map(self):
        """Draw a linear map showing primer binding positions on the template."""
        self._primer_fig.clear()

        template = self._current_template_seq
        if not template:
            self._primer_canvas.draw_idle()
            return

        ax = self._primer_fig.add_subplot(111)
        seq_len = len(template)

        # Draw template as a thick horizontal line at the top
        ax.plot([0, seq_len], [0, 0], "k-", linewidth=3, label="Template", zorder=1)

        # Collect primer pairs from row_detail_cache
        colors_fwd = ["#2196F3", "#1976D2", "#0D47A1", "#42A5F5", "#64B5F6"]
        colors_rev = ["#FF5722", "#E64A19", "#BF360C", "#FF7043", "#FF8A65"]

        # Group by pair index
        pairs: dict[int, dict[str, Any]] = {}
        for d in self.row_detail_cache:
            pi = d["pair_index"]
            if pi not in pairs:
                pairs[pi] = {}
            pairs[pi][d["type"]] = d

        y_offset = -1.2
        max_offset = 0
        for pair_idx in sorted(pairs.keys()):
            pair = pairs[pair_idx]
            fwd = pair.get("Fwd")
            rev = pair.get("Rev")

            if fwd:
                pos_text, len_text = self._safe_pos_length(fwd["pos_len"])
                try:
                    fwd_start = int(pos_text)
                    fwd_len = int(len_text)
                except (ValueError, TypeError):
                    fwd_start, fwd_len = 0, 0
                if fwd_start > 0 and fwd_len > 0:
                    color = colors_fwd[(pair_idx - 1) % len(colors_fwd)]
                    ax.arrow(
                        fwd_start,
                        y_offset,
                        fwd_len,
                        0,
                        head_width=0.35,
                        head_length=min(fwd_len * 0.3, seq_len * 0.02),
                        fc=color,
                        ec=color,
                        linewidth=1.5,
                        zorder=3,
                        length_includes_head=True,
                    )
                    ax.text(
                        fwd_start + fwd_len / 2,
                        y_offset - 0.55,
                        f"P{pair_idx}F",
                        ha="center",
                        va="top",
                        fontsize=7,
                        color=color,
                        fontweight="bold",
                    )

            if rev:
                pos_text, len_text = self._safe_pos_length(rev["pos_len"])
                try:
                    rev_start = int(pos_text)
                    rev_len = int(len_text)
                except (ValueError, TypeError):
                    rev_start, rev_len = 0, 0
                if rev_start > 0 and rev_len > 0:
                    color = colors_rev[(pair_idx - 1) % len(colors_rev)]
                    ax.arrow(
                        rev_start,
                        y_offset,
                        -rev_len,
                        0,
                        head_width=0.35,
                        head_length=min(rev_len * 0.3, seq_len * 0.02),
                        fc=color,
                        ec=color,
                        linewidth=1.5,
                        zorder=3,
                        length_includes_head=True,
                    )
                    ax.text(
                        rev_start - rev_len / 2,
                        y_offset - 0.55,
                        f"P{pair_idx}R",
                        ha="center",
                        va="top",
                        fontsize=7,
                        color=color,
                        fontweight="bold",
                    )

            y_offset -= 1.5
            max_offset = abs(y_offset)

        # Styling
        ax.set_xlim(-seq_len * 0.02, seq_len * 1.02)
        ax.set_ylim(-max_offset - 1.0, 0.8)
        ax.set_xlabel("Template Position (bp)")
        ax.set_yticks([])
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.set_title("Primer Binding Sites on Template", fontweight="bold", fontsize=11)

        self._primer_fig.tight_layout()
        self._primer_canvas.draw_idle()

    # ── Help Dialog ─────────────────────────────────────────────────

    def show_help_dialog(self):
        from PyQt6.QtCore import Qt as QtCore
        from PyQt6.QtWidgets import QLabel, QPushButton, QScrollArea, QVBoxLayout

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("qPCR Primer Design - Help"))
        dlg.setFixedSize(720, 540)
        layout = QVBoxLayout(dlg)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(QtCore.ScrollBarPolicy.ScrollBarAsNeeded)

        label = QLabel(
            self.tr("""
<h2>qPCR Primer Design</h2>

<p><b>What does this tool do?</b><br>
Designs optimal primer pairs for quantitative PCR (qPCR / real-time PCR)
using the Primer3 engine. It searches your template DNA for primer pairs
that meet strict Tm, GC%, and product-size constraints suitable for qPCR.</p>

<h3>Quick Start</h3>
<ol>
<li><b>Enter a template DNA sequence</b> — paste raw sequence or FASTA format
    (bases A/C/G/T/U/N allowed), or click <b>Example</b> to load HBB exon 1.</li>
<li><b>Adjust parameters</b> if needed — the defaults (80-150 bp product,
    57-63°C Tm, 40-60% GC) work well for most qPCR applications.</li>
<li><b>Click "Run"</b> to launch Primer3 in the background.</li>
<li><b>Review results</b> in the table — select any row to see primer
    binding positions drawn on the template map.</li>
<li><b>Export</b> results to Excel or CSV for downstream use.</li>
</ol>

<h3>Parameter Guide</h3>
<table border='0' cellpadding='4' cellspacing='2'>
<tr><td><b>Product Size (Min/Max)</b></td><td>Expected amplicon length in bp.
    qPCR: 70-200 bp for optimal efficiency.</td></tr>
<tr><td><b>Primer Pair Count</b></td><td>How many pairs to return.
    Higher values give more candidates to choose from.</td></tr>
<tr><td><b>Length (Min/Opt/Max)</b></td><td>Primer length in nt.
    Typical: 18-25 nt. Must satisfy Min &le; Opt &le; Max.</td></tr>
<tr><td><b>Tm (Min/Opt/Max)</b></td><td>Melting temperature in °C.
    Typical qPCR range: 57-63°C. Min &le; Opt &le; Max.</td></tr>
<tr><td><b>GC% (Min/Opt/Max)</b></td><td>GC content percentage.
    Typical: 40-60%. Min &le; Opt &le; Max.</td></tr>
</table>

<h3>Advanced Parameters</h3>
<table border='0' cellpadding='4' cellspacing='2'>
<tr><td><b>Salt (Monovalent)</b></td><td>Na&plus;/K&plus; concentration (mM).
    Affects Tm calculation. Standard PCR: 50 mM.</td></tr>
<tr><td><b>Mg&sup2;&plus;</b></td><td>Magnesium concentration (mM).
    Affects Tm and specificity. qPCR typical: 2-3 mM.</td></tr>
</table>

<h3>Interpreting Results</h3>
<ul>
<li><b>Pair #</b> — ranked by Primer3 penalty score (1 = best).</li>
<li><b>Fwd / Rev</b> — Forward (sense) or Reverse (antisense) primer.</li>
<li><b>Position</b> — 5' start coordinate on the template (1-based).</li>
<li><b>Length</b> — primer length in nucleotides.</li>
<li><b>Tm</b> — melting temperature. Fwd and Rev should be within 2°C.</li>
<li><b>GC%</b> — GC content. 40-60% is optimal for qPCR.</li>
<li><b>Product Size</b> — expected amplicon length in bp.</li>
</ul>
<p><b>Binding Site Map</b> — Blue arrows = Forward primers,
Orange arrows = Reverse primers, drawn on the template line to scale.</p>

<h3>Troubleshooting</h3>
<p><b>"No primer pairs found"</b></p>
<ul>
<li>Relax constraints — widen Tm, GC%, or length ranges.</li>
<li>Increase the product size range (e.g. 70-200 bp).</li>
<li>Increase the number of primer pairs requested.</li>
<li>Verify the template contains valid bases (A/C/G/T/U/N only).</li>
<li>For short templates (&lt;100 bp), reduce the product size range.</li>
<li>Ensure primer3-py is installed: <code>pip install primer3-py</code></li>
</ul>

<h3>After Design — Analyze Your Primers</h3>
<p>Open <b>Primer Design &rarr; Primer Analysis</b> to check hairpin,
self-dimer, and cross-dimer properties of any primer pair from the results.</p>
""")
        )
        label.setTextFormat(QtCore.TextFormat.RichText)
        label.setWordWrap(True)
        label.setAlignment(QtCore.AlignmentFlag.AlignTop | QtCore.AlignmentFlag.AlignLeft)
        label.setMargin(20)
        scroll.setWidget(label)
        layout.addWidget(scroll)

        ok = QPushButton("OK")
        ok.clicked.connect(dlg.accept)
        layout.addWidget(ok)
        dlg.exec()

    def show_error_message(self, message: str):
        QMessageBox.critical(self, "Error", message)
        self.status_label.setText("Task failed or no results found.")
        self.design_button.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = PrimerDesignTab()
    w.show()
    sys.exit(app.exec())
