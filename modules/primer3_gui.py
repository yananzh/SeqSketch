"""
PCR Primer Assistant (PyQt6 + primer3-py)
"""

import csv
import importlib
import sys
from typing import Any, Dict

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSplitter,
    QSpinBox,
    QDoubleSpinBox,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    p3_bindings = importlib.import_module("primer3.bindings")
except Exception:
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
                self.error.emit(
                    "Failed to import primer3. Please install: pip install primer3-py"
                )
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker: Worker | None = None
        self.worker_thread: QThread | None = None
        self.current_results: dict[str, Any] = {}
        self.row_detail_cache: list[dict[str, Any]] = []
        self._last_mode: str = "standard"

        self.init_ui()
        self.connect_signals()
        self.update_ui_for_mode()
        self.setMenuBar(None)

    def init_ui(self):
        self.setWindowTitle("PCR Primer Assistant")
        self.setGeometry(100, 100, 1450, 820)

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(8)

        seq_group = QGroupBox("1. Template Sequence")
        seq_v = QVBoxLayout(seq_group)
        self.seq_input = QPlainTextEdit()
        self.seq_input.setPlaceholderText("Paste FASTA or raw DNA sequence here...")
        self.seq_len_label = QLabel("Sequence Length: 0 bp")

        seq_btn_row = QHBoxLayout()
        self.load_seq_btn = QPushButton("Load from File")
        self.clear_seq_btn = QPushButton("Clear")
        seq_btn_row.addWidget(self.load_seq_btn)
        seq_btn_row.addWidget(self.clear_seq_btn)
        seq_btn_row.addStretch()

        seq_v.addWidget(self.seq_input)
        seq_v.addLayout(seq_btn_row)
        seq_v.addWidget(self.seq_len_label)

        mode_group = QGroupBox("2. Design Mode")
        mode_v = QVBoxLayout(mode_group)
        self.rb_standard = QRadioButton("Standard Primer Design (internal fragment)")
        self.rb_specific = QRadioButton("Specific Region (within target)")
        self.rb_cloning = QRadioButton("Full-length Cloning (entire template)")
        self.rb_standard.setChecked(True)
        mode_v.addWidget(self.rb_standard)
        mode_v.addWidget(self.rb_specific)
        mode_v.addWidget(self.rb_cloning)

        self.region_group = QGroupBox("Target Region")
        region_form = QFormLayout(self.region_group)
        self.region_start_spin = QSpinBox()
        self.region_end_spin = QSpinBox()
        self.region_start_spin.setRange(1, 999999)
        self.region_end_spin.setRange(1, 999999)
        self.region_start_spin.setValue(1)
        self.region_end_spin.setValue(300)
        region_form.addRow("Start:", self.region_start_spin)
        region_form.addRow("End:", self.region_end_spin)

        general_group = QGroupBox("3. Product and Basic Parameters")
        general_form = QFormLayout(general_group)

        self.prod_size_min = QSpinBox()
        self.prod_size_max = QSpinBox()
        self.prod_size_min.setRange(50, 10000)
        self.prod_size_max.setRange(50, 10000)
        self.prod_size_min.setValue(150)
        self.prod_size_max.setValue(300)
        size_box = QWidget()
        size_h = QHBoxLayout(size_box)
        size_h.setContentsMargins(0, 0, 0, 0)
        size_h.setSpacing(6)
        size_h.addWidget(self.prod_size_min)
        size_h.addWidget(self.prod_size_max)

        self.num_primers_spin = QSpinBox()
        self.num_primers_spin.setRange(1, 30)
        self.num_primers_spin.setValue(5)

        general_form.addRow("Product Size Range (Min/Max):", size_box)
        general_form.addRow("Primer Pair Count:", self.num_primers_spin)

        primer_group = QGroupBox("4. Primer Specifications")
        primer_form = QFormLayout(primer_group)

        self.p_len_min = QSpinBox()
        self.p_len_opt = QSpinBox()
        self.p_len_max = QSpinBox()
        for spin in (self.p_len_min, self.p_len_opt, self.p_len_max):
            spin.setRange(15, 35)
        self.p_len_min.setValue(18)
        self.p_len_opt.setValue(20)
        self.p_len_max.setValue(25)
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
            spin.setRange(40.0, 85.0)
            spin.setDecimals(1)
            spin.setSingleStep(0.1)
        self.p_tm_min.setValue(57.0)
        self.p_tm_opt.setValue(60.0)
        self.p_tm_max.setValue(63.0)
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
            spin.setRange(20.0, 80.0)
            spin.setDecimals(1)
            spin.setSingleStep(0.1)
        self.p_gc_min.setValue(40.0)
        self.p_gc_opt.setValue(50.0)
        self.p_gc_max.setValue(60.0)
        gc_box = QWidget()
        gc_h = QHBoxLayout(gc_box)
        gc_h.setContentsMargins(0, 0, 0, 0)
        gc_h.setSpacing(6)
        gc_h.addWidget(self.p_gc_min)
        gc_h.addWidget(self.p_gc_opt)
        gc_h.addWidget(self.p_gc_max)

        primer_form.addRow("Primer Length (Min/Opt/Max):", len_box)
        primer_form.addRow("Primer Tm (°C) (Min/Opt/Max):", tm_box)
        primer_form.addRow("Primer GC (%) (Min/Opt/Max):", gc_box)

        advanced_group = QGroupBox("5. Advanced Constraints")
        adv_form = QFormLayout(advanced_group)

        self.max_poly_x_spin = QSpinBox()
        self.max_poly_x_spin.setRange(2, 10)
        self.max_poly_x_spin.setValue(4)

        self.max_self_any_spin = QDoubleSpinBox()
        self.max_self_any_spin.setRange(2.0, 20.0)
        self.max_self_any_spin.setDecimals(1)
        self.max_self_any_spin.setValue(8.0)

        self.max_self_end_spin = QDoubleSpinBox()
        self.max_self_end_spin.setRange(1.0, 20.0)
        self.max_self_end_spin.setDecimals(1)
        self.max_self_end_spin.setValue(3.0)

        self.max_hairpin_tm_spin = QDoubleSpinBox()
        self.max_hairpin_tm_spin.setRange(10.0, 80.0)
        self.max_hairpin_tm_spin.setDecimals(1)
        self.max_hairpin_tm_spin.setValue(47.0)

        adv_form.addRow("Max Poly-X:", self.max_poly_x_spin)
        adv_form.addRow("Max Self Any:", self.max_self_any_spin)
        adv_form.addRow("Max Self End:", self.max_self_end_spin)
        adv_form.addRow("Max Hairpin Tm:", self.max_hairpin_tm_spin)

        self.design_button = QPushButton("Design Primers")
        self.design_button.setMinimumHeight(38)

        left_layout.addWidget(seq_group)
        left_layout.addWidget(mode_group)
        left_layout.addWidget(self.region_group)
        left_layout.addWidget(general_group)
        left_layout.addWidget(primer_group)
        left_layout.addWidget(advanced_group)
        left_layout.addStretch()
        left_layout.addWidget(self.design_button)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(8)

        top_actions = QHBoxLayout()
        self.copy_selected_btn = QPushButton("Copy Selected")
        self.copy_all_btn = QPushButton("Copy All")
        self.export_csv_btn = QPushButton("Export CSV")
        self.help_btn = QPushButton("Help")
        top_actions.addWidget(self.copy_selected_btn)
        top_actions.addWidget(self.copy_all_btn)
        top_actions.addWidget(self.export_csv_btn)
        top_actions.addWidget(self.help_btn)
        top_actions.addStretch()

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(8)
        self.results_table.setHorizontalHeaderLabels(
            [
                "Pair #",
                "Type",
                "Sequence",
                "Position",
                "Length",
                "Tm",
                "GC%",
                "Product Size",
            ]
        )
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

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
            self.results_table.setColumnWidth(0, 68)
            self.results_table.setColumnWidth(1, 72)
            self.results_table.setColumnWidth(3, 90)
            self.results_table.setColumnWidth(4, 82)
            self.results_table.setColumnWidth(5, 72)
            self.results_table.setColumnWidth(6, 72)
            self.results_table.setColumnWidth(7, 102)

        detail_group = QGroupBox("Selected Primer Detail")
        detail_layout = QVBoxLayout(detail_group)
        self.detail_text = QPlainTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setPlaceholderText(
            "Select a primer row to inspect detailed metrics."
        )
        self.detail_text.setMaximumBlockCount(500)
        detail_layout.addWidget(self.detail_text)

        right_layout.addLayout(top_actions)
        right_layout.addWidget(self.results_table, 3)
        right_layout.addWidget(detail_group, 2)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([560, 860])

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready.")

    def connect_signals(self):
        self.design_button.clicked.connect(self.start_design_task)
        self.rb_standard.toggled.connect(self.update_ui_for_mode)
        self.rb_specific.toggled.connect(self.update_ui_for_mode)
        self.rb_cloning.toggled.connect(self.update_ui_for_mode)
        self.seq_input.textChanged.connect(self.on_sequence_changed)

        self.load_seq_btn.clicked.connect(self.load_sequence_from_file)
        self.clear_seq_btn.clicked.connect(self.clear_sequence)
        self.copy_selected_btn.clicked.connect(self.copy_selected_rows)
        self.copy_all_btn.clicked.connect(self.copy_all_rows)
        self.export_csv_btn.clicked.connect(self.export_results_csv)
        self.help_btn.clicked.connect(self.show_help_dialog)
        self.results_table.itemSelectionChanged.connect(self.update_detail_panel)

    def _normalize_sequence(self, raw_text: str) -> str:
        text = raw_text.strip()
        if text.startswith(">"):
            lines = text.splitlines()
            seq_lines = [line.strip() for line in lines if not line.startswith(">")]
            return (
                "".join(seq_lines)
                .replace(" ", "")
                .replace("\r", "")
                .replace("\n", "")
                .upper()
            )
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
            self.status_bar.showMessage(f"Loaded sequence: {file_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", f"Failed to read file:\n{exc}")

    def clear_sequence(self):
        self.seq_input.clear()
        self.results_table.setRowCount(0)
        self.detail_text.clear()
        self.current_results.clear()
        self.row_detail_cache.clear()
        self.status_bar.showMessage("Sequence and results cleared.")

    def update_ui_for_mode(self):
        is_specific = self.rb_specific.isChecked()
        is_cloning = self.rb_cloning.isChecked()
        mode = "cloning" if is_cloning else ("specific" if is_specific else "standard")

        if mode != self._last_mode:
            if mode == "standard":
                self.apply_standard_presets()
            elif mode == "specific":
                self.apply_specific_presets()
            else:
                self.apply_cloning_relaxed_presets()

        self.region_group.setEnabled(is_specific)
        self.prod_size_min.setEnabled(not is_cloning)
        self.prod_size_max.setEnabled(not is_cloning)
        if is_cloning:
            self.update_cloning_product_size()

        self._last_mode = mode

    def apply_standard_presets(self):
        """Apply balanced preset values for standard primer design."""
        self.p_len_min.setValue(18)
        self.p_len_opt.setValue(20)
        self.p_len_max.setValue(25)

        self.p_tm_min.setValue(57.0)
        self.p_tm_opt.setValue(60.0)
        self.p_tm_max.setValue(63.0)

        self.p_gc_min.setValue(40.0)
        self.p_gc_opt.setValue(50.0)
        self.p_gc_max.setValue(60.0)

        self.max_poly_x_spin.setValue(4)
        self.max_self_any_spin.setValue(8.0)
        self.max_self_end_spin.setValue(3.0)
        self.max_hairpin_tm_spin.setValue(47.0)
        self.num_primers_spin.setValue(5)

        self.prod_size_min.setValue(150)
        self.prod_size_max.setValue(300)
        self.status_bar.showMessage("Applied standard preset parameters.")

    def apply_specific_presets(self):
        """Keep specific mode presets identical to standard mode parameters."""
        self.apply_standard_presets()
        self.status_bar.showMessage(
            "Applied specific-region preset parameters (same as standard mode)."
        )

    def apply_cloning_relaxed_presets(self):
        """Apply a looser preset suitable for full-length cloning mode."""
        self.p_len_min.setValue(16)
        self.p_len_opt.setValue(20)
        self.p_len_max.setValue(30)

        self.p_tm_min.setValue(55.0)
        self.p_tm_opt.setValue(60.0)
        self.p_tm_max.setValue(66.0)

        self.p_gc_min.setValue(30.0)
        self.p_gc_opt.setValue(50.0)
        self.p_gc_max.setValue(70.0)

        self.max_poly_x_spin.setValue(5)
        self.max_self_any_spin.setValue(10.0)
        self.max_self_end_spin.setValue(5.0)
        self.max_hairpin_tm_spin.setValue(55.0)

        # Full-length cloning default: two primer pairs.
        self.num_primers_spin.setValue(2)
        self.status_bar.showMessage(
            "Applied relaxed preset for Full-length Cloning mode."
        )

    def on_sequence_changed(self):
        sequence = self._normalize_sequence(self.seq_input.toPlainText())
        self.seq_len_label.setText(f"Sequence Length: {len(sequence)} bp")
        if self.rb_cloning.isChecked():
            self.update_cloning_product_size()

    def update_cloning_product_size(self):
        seq_len = len(self._normalize_sequence(self.seq_input.toPlainText()))
        if seq_len > 0:
            self.prod_size_min.setValue(max(50, seq_len - 50))
            self.prod_size_max.setValue(seq_len + 50)
        else:
            self.prod_size_min.setValue(150)
            self.prod_size_max.setValue(300)

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
            QMessageBox.warning(
                self, "Input Error", "Please enter a valid DNA template sequence."
            )
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
            QMessageBox.warning(
                self, "Input Error", "Sequence is too short (minimum 50 bp)."
            )
            return
        if not self._validate_parameter_ranges():
            return

        self.design_button.setEnabled(False)
        self.status_bar.showMessage("Preparing parameters...")
        self.results_table.setRowCount(0)
        self.detail_text.clear()
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
            "PRIMER_MAX_POLY_X": self.max_poly_x_spin.value(),
            "PRIMER_MAX_SELF_ANY": self.max_self_any_spin.value(),
            "PRIMER_MAX_SELF_END": self.max_self_end_spin.value(),
            "PRIMER_MAX_HAIRPIN_TH": self.max_hairpin_tm_spin.value(),
        }

        seq_len = len(sequence)
        if self.rb_specific.isChecked():
            start_pos = self.region_start_spin.value()
            end_pos = self.region_end_spin.value()
            if start_pos >= end_pos or end_pos > seq_len:
                self.show_error_message(
                    "Invalid target region. Check start/end positions."
                )
                return
            seq_args["SEQUENCE_INCLUDED_REGION"] = (
                f"{start_pos - 1},{end_pos - start_pos + 1}"
            )
            global_args["PRIMER_PRODUCT_SIZE_RANGE"] = [
                self.prod_size_min.value(),
                self.prod_size_max.value(),
            ]
        elif self.rb_cloning.isChecked():
            seq_args["SEQUENCE_TARGET"] = f"0,{seq_len}"
            global_args["PRIMER_PRODUCT_SIZE_RANGE"] = [
                max(50, seq_len - 50),
                seq_len + 50,
            ]
        else:
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
        self.worker.progress.connect(self.status_bar.showMessage)

        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.error.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker_thread.start()
        self.status_bar.showMessage("Background task started. Designing primers...")

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
            explain = (
                results.get("PRIMER_PAIR_EXPLAIN")
                or results.get("PRIMER_LEFT_EXPLAIN")
                or ""
            )
            self.show_error_message(
                "No primer pairs found. Try relaxing constraints."
                + (f"\n\nPrimer3 explain: {explain}" if explain else "")
            )
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

        self.status_bar.showMessage(f"Found {num_returned} primer pairs.")
        self.design_button.setEnabled(True)
        if self.results_table.rowCount() > 0:
            self.results_table.selectRow(0)

    def update_detail_panel(self):
        current_row = self.results_table.currentRow()
        if current_row < 0 or current_row >= len(self.row_detail_cache):
            self.detail_text.clear()
            return

        d = self.row_detail_cache[current_row]
        pos_text, len_text = self._safe_pos_length(d["pos_len"])
        lines = [
            f"Pair #{d['pair_index']}  ({d['type']})",
            f"Sequence: {d['seq']}",
            f"Position: {pos_text}",
            f"Length: {len_text}",
            f"Tm: {self._to_float_text(d['tm'])}",
            f"GC%: {self._to_float_text(d['gc'])}",
            f"Penalty: {self._to_float_text(d['penalty'])}",
            f"Pair Penalty: {self._to_float_text(d['pair_penalty'])}",
            f"Self Any (TH): {self._to_float_text(d['self_any'])}",
            f"Self End (TH): {self._to_float_text(d['self_end'])}",
            f"Hairpin (TH): {self._to_float_text(d['hairpin'])}",
            f"Product Size: {d['product_size']}",
        ]
        self.detail_text.setPlainText("\n".join(lines))

    def _table_to_tsv(self, selected_only: bool) -> str:
        headers = [
            self.results_table.horizontalHeaderItem(c).text()
            for c in range(self.results_table.columnCount())
        ]
        lines = ["\t".join(headers)]

        if selected_only:
            rows = sorted(
                {
                    idx.row()
                    for idx in self.results_table.selectionModel().selectedRows()
                }
            )
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
        self.status_bar.showMessage("Selected rows copied to clipboard.")

    def copy_all_rows(self):
        if self.results_table.rowCount() == 0:
            self.show_error_message("No results to copy.")
            return
        text = self._table_to_tsv(selected_only=False)
        QApplication.clipboard().setText(text)
        self.status_bar.showMessage("All rows copied to clipboard.")

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
            self.status_bar.showMessage(f"Exported CSV: {out_path}")
        except Exception as exc:
            self.show_error_message(f"Failed to export CSV: {exc}")

    def show_help_dialog(self):
        help_text = (
            "PCR Primer Assistant - Quick Help\n\n"
            "1) Template sequence\n"
            "   - Supports FASTA or raw sequence\n"
            "   - Allowed bases: A/C/G/T/U/N\n\n"
            "2) Design mode\n"
            "   - Standard: internal fragment amplification\n"
            "   - Specific Region: primer design within target coordinates\n"
            "   - Full-length Cloning: auto product range around template length\n\n"
            "3) Parameter tips\n"
            "   - Keep Min ≤ Opt ≤ Max for Length / Tm / GC\n"
            "   - Typical Tm range: 57-63°C\n"
            "   - Typical GC range: 40-60%\n"
            "   - Increase PRIMER_NUM_RETURN to get more candidates\n"
            "   - Relax constraints if no primer pair is returned\n\n"
            "4) Results\n"
            "   - Click a row to inspect penalty, self-complementarity, and hairpin values\n"
            "   - Use Copy Selected / Copy All / Export CSV for downstream analysis"
        )
        QMessageBox.information(self, "PCR Primer Assistant Help", help_text)

    def show_error_message(self, message: str):
        QMessageBox.critical(self, "Error", message)
        self.status_bar.showMessage("Task failed or no results found.")
        self.design_button.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
