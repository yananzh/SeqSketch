"""
PCR Primer Designer GUI using PyQt6 and primer3-py.

- Removed the '详细信息' tab.
- Added per-parameter annotations under each field in section '4. 引物特性参数'.
- Uses a background QThread for primer3 calculations.
"""

import sys
import importlib
from typing import Dict, Any

try:
    p3_bindings = importlib.import_module("primer3.bindings")
except Exception:
    p3_bindings = None

from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
    QFormLayout, QPlainTextEdit, QLabel, QRadioButton, QSpinBox, QDoubleSpinBox,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QStatusBar, QSizePolicy,
    QTabWidget
)


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
        except Exception as e:
            self.error.emit(f"Error: {e}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker: Worker | None = None
        self.worker_thread: QThread | None = None
        self.primer_pair_details: list[dict] = []

        self.init_ui()
        self.connect_signals()
        self.update_ui_for_mode()
        self.setMenuBar(None)

    def init_ui(self):
        self.setWindowTitle("PCR Primer Designer (PyQt6)")
        self.setGeometry(100, 100, 1500, 700)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # Left panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setFixedWidth(600)

        # 1. Sequence
        seq_group = QGroupBox("1. Paste Template Sequence (DNA)")
        seq_v = QVBoxLayout(seq_group)
        self.seq_input = QPlainTextEdit()
        self.seq_input.setPlaceholderText("Paste FASTA or raw DNA sequence here...")
        self.seq_len_label = QLabel("Sequence Length: 0 bp")
        seq_v.addWidget(self.seq_input)
        seq_v.addWidget(self.seq_len_label)

        # 2. Mode
        mode_group = QGroupBox("2. Design Mode")
        mode_v = QVBoxLayout(mode_group)
        self.rb_standard = QRadioButton("Standard Primer Design (internal fragment)")
        self.rb_specific = QRadioButton("Specific Region (within target)")
        self.rb_cloning = QRadioButton("Full-length Cloning (entire template)")
        self.rb_standard.setChecked(True)
        for rb in (self.rb_standard, self.rb_specific, self.rb_cloning):
            mode_v.addWidget(rb)

        # Target region
        self.region_group = QGroupBox("目标区域 (Target Region)")
        region_form = QFormLayout(self.region_group)
        self.region_start_spin = QSpinBox(); self.region_start_spin.setRange(1, 999999)
        self.region_end_spin = QSpinBox(); self.region_end_spin.setRange(1, 999999)
        region_form.addRow("Start:", self.region_start_spin)
        region_form.addRow("End:", self.region_end_spin)

        # 3. General
        general_group = QGroupBox("3. Product and Primer Parameters")
        general_form = QFormLayout(general_group)
        self.prod_size_min = QSpinBox(); self.prod_size_min.setRange(50, 10000); self.prod_size_min.setValue(150)
        self.prod_size_max = QSpinBox(); self.prod_size_max.setRange(50, 10000); self.prod_size_max.setValue(300)
        self.num_primers_spin = QSpinBox(); self.num_primers_spin.setRange(1, 10); self.num_primers_spin.setValue(5)
        size_row = QWidget(); size_h = QHBoxLayout(size_row); size_h.setContentsMargins(0, 0, 0, 0); size_h.setSpacing(6)
        size_h.addWidget(self.prod_size_min); size_h.addWidget(self.prod_size_max)
        general_form.addRow("Product Size Range (Min/Max):", size_row)
        general_form.addRow("Number of Primer Pairs:", self.num_primers_spin)

        # 4. Primer specs with annotations
        primer_group = QGroupBox("4. Primer Specifications")
        primer_form = QFormLayout(primer_group)
        primer_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Length
        self.p_len_min = QSpinBox(); self.p_len_min.setRange(15, 30); self.p_len_min.setValue(18)
        self.p_len_opt = QSpinBox(); self.p_len_opt.setRange(15, 30); self.p_len_opt.setValue(20)
        self.p_len_max = QSpinBox(); self.p_len_max.setRange(15, 30); self.p_len_max.setValue(25)
        len_row = QWidget(); len_h = QHBoxLayout(len_row); len_h.setContentsMargins(0, 0, 0, 0); len_h.setSpacing(6)
        len_h.addWidget(self.p_len_min); len_h.addWidget(self.p_len_opt); len_h.addWidget(self.p_len_max)
        primer_form.addRow("Primer Length (Min/Opt/Max):", len_row)
        
        # Tm
        self.p_tm_min = QDoubleSpinBox(); self.p_tm_min.setRange(40.0, 80.0); self.p_tm_min.setDecimals(1); self.p_tm_min.setValue(57.0)
        self.p_tm_opt = QDoubleSpinBox(); self.p_tm_opt.setRange(40.0, 80.0); self.p_tm_opt.setDecimals(1); self.p_tm_opt.setValue(60.0)
        self.p_tm_max = QDoubleSpinBox(); self.p_tm_max.setRange(40.0, 80.0); self.p_tm_max.setDecimals(1); self.p_tm_max.setValue(63.0)
        tm_row = QWidget(); tm_h = QHBoxLayout(tm_row); tm_h.setContentsMargins(0, 0, 0, 0); tm_h.setSpacing(6)
        tm_h.addWidget(self.p_tm_min); tm_h.addWidget(self.p_tm_opt); tm_h.addWidget(self.p_tm_max)
        primer_form.addRow("Primer Tm (°C) (Min/Opt/Max):", tm_row)
        
        # GC%
        self.p_gc_min = QDoubleSpinBox(); self.p_gc_min.setRange(20.0, 80.0); self.p_gc_min.setDecimals(1); self.p_gc_min.setValue(40.0)
        self.p_gc_opt = QDoubleSpinBox(); self.p_gc_opt.setRange(20.0, 80.0); self.p_gc_opt.setDecimals(1); self.p_gc_opt.setValue(50.0)
        self.p_gc_max = QDoubleSpinBox(); self.p_gc_max.setRange(20.0, 80.0); self.p_gc_max.setDecimals(1); self.p_gc_max.setValue(60.0)
        gc_row = QWidget(); gc_h = QHBoxLayout(gc_row); gc_h.setContentsMargins(0, 0, 0, 0); gc_h.setSpacing(6)
        gc_h.addWidget(self.p_gc_min); gc_h.addWidget(self.p_gc_opt); gc_h.addWidget(self.p_gc_max)
        primer_form.addRow("Primer GC (%) (Min/Opt/Max):", gc_row)

        # Action button
        self.design_button = QPushButton("Design Primers")
        self.design_button.setStyleSheet("font-size: 16px; padding: 10px;")

        # Assemble left
        left_layout.addWidget(seq_group)
        left_layout.addWidget(mode_group)
        left_layout.addWidget(self.region_group)
        left_layout.addWidget(general_group)
        left_layout.addWidget(primer_group)
        left_layout.addStretch()
        left_layout.addWidget(self.design_button)

        # Right panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(7)
        self.results_table.setHorizontalHeaderLabels(["Pair #", "Type", "Sequence", "Length", "Tm", "GC%", "Product Size"])
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = self.results_table.horizontalHeader()
        if header is not None:
            # 设置各列的具体宽度
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # Pair #
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)  # Type
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Sequence
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)  # Length
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)  # Tm
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)  # GC%
            header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)  # Product Size
            
            # 设置固定列的宽度，确保表头完整显示
            self.results_table.setColumnWidth(0, 70)   # Pair #
            self.results_table.setColumnWidth(1, 90)   # Type
            self.results_table.setColumnWidth(3, 80)   # Length
            self.results_table.setColumnWidth(4, 70)   # Tm
            self.results_table.setColumnWidth(5, 70)   # GC%
            self.results_table.setColumnWidth(6, 110)  # Product Size
        self.tabs = QTabWidget()
        self.tabs.addTab(self.results_table, "Primer Pairs")
        right_layout.addWidget(self.tabs)

        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready.")

    def create_menu(self):
        pass

    def connect_signals(self):
        self.design_button.clicked.connect(self.start_design_task)
        self.rb_standard.toggled.connect(self.update_ui_for_mode)
        self.rb_specific.toggled.connect(self.update_ui_for_mode)
        self.rb_cloning.toggled.connect(self.update_ui_for_mode)
        self.seq_input.textChanged.connect(self.on_sequence_changed)

    def update_ui_for_mode(self):
        is_standard = self.rb_standard.isChecked()
        is_specific = self.rb_specific.isChecked()
        is_cloning = self.rb_cloning.isChecked()
        self.region_group.setEnabled(is_specific)
        self.prod_size_min.setEnabled(is_standard or is_specific)
        self.prod_size_max.setEnabled(is_standard or is_specific)
        if is_cloning:
            self.update_cloning_product_size()

    def on_sequence_changed(self):
        seq_len = len(self.seq_input.toPlainText().strip())
        self.seq_len_label.setText(f"Sequence Length: {seq_len} bp")
        if self.rb_cloning.isChecked():
            self.update_cloning_product_size()

    def update_cloning_product_size(self):
        seq_len = len(self.seq_input.toPlainText().strip())
        if seq_len > 0:
            self.prod_size_min.setValue(max(50, seq_len - 50))
            self.prod_size_max.setValue(seq_len + 50)
        else:
            self.prod_size_min.setValue(150)
            self.prod_size_max.setValue(300)

    def start_design_task(self):
        raw_text = self.seq_input.toPlainText().strip()
        if not raw_text:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Input Error", "Please enter a valid DNA template sequence.")
            return

        if raw_text.startswith('>'):
            lines = raw_text.splitlines()
            seq_lines = [line.strip() for line in lines if not line.startswith('>')]
            sequence = ''.join(seq_lines).replace(' ', '').replace('\r', '').replace('\n', '').upper()
        else:
            sequence = raw_text.replace(' ', '').replace('\r', '').replace('\n', '').upper()

        if not sequence or any(c not in 'ACGTUN' for c in sequence):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Input Error", "Please enter a valid DNA template sequence (ACGTU only).")
            return

        self.design_button.setEnabled(False)
        self.status_bar.showMessage("Preparing parameters...")
        self.results_table.setRowCount(0)
        self.primer_pair_details.clear()

        seq_args = {'SEQUENCE_ID': 'MyTemplate', 'SEQUENCE_TEMPLATE': sequence}
        global_args = {
            'PRIMER_OPT_SIZE': self.p_len_opt.value(),
            'PRIMER_MIN_SIZE': self.p_len_min.value(),
            'PRIMER_MAX_SIZE': self.p_len_max.value(),
            'PRIMER_OPT_TM': self.p_tm_opt.value(),
            'PRIMER_MIN_TM': self.p_tm_min.value(),
            'PRIMER_MAX_TM': self.p_tm_max.value(),
            'PRIMER_MIN_GC': self.p_gc_min.value(),
            'PRIMER_MAX_GC': self.p_gc_max.value(),
            'PRIMER_OPT_GC_PERCENT': self.p_gc_opt.value(),
            'PRIMER_NUM_RETURN': self.num_primers_spin.value(),
            'PRIMER_EXPLAIN_FLAG': 1,
        }

        seq_len = len(sequence)
        if self.rb_specific.isChecked():
            start_pos = self.region_start_spin.value()
            end_pos = self.region_end_spin.value()
            if start_pos >= end_pos or end_pos > seq_len:
                self.show_error_message("Invalid target region. Check start/end positions.")
                return
            included_region = f"{start_pos - 1},{end_pos - start_pos + 1}"
            seq_args['SEQUENCE_INCLUDED_REGION'] = included_region
            global_args['PRIMER_PRODUCT_SIZE_RANGE'] = [self.prod_size_min.value(), self.prod_size_max.value()]
        elif self.rb_cloning.isChecked():
            seq_args['SEQUENCE_TARGET'] = f"0,{seq_len}"
            global_args['PRIMER_PRODUCT_SIZE_RANGE'] = [max(50, seq_len - 50), seq_len + 50]
        else:
            global_args['PRIMER_PRODUCT_SIZE_RANGE'] = [self.prod_size_min.value(), self.prod_size_max.value()]

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

    def update_results_table(self, results: Dict[str, Any]):
        num_returned = results.get('PRIMER_PAIR_NUM_RETURNED', 0)
        if num_returned == 0:
            self.show_error_message("No primer pairs found. Try relaxing constraints.")
            return

        self.results_table.setRowCount(num_returned * 2)
        self.primer_pair_details = []
        for i in range(num_returned):
            fwd_seq = results.get(f'PRIMER_LEFT_{i}_SEQUENCE', '')
            rev_seq = results.get(f'PRIMER_RIGHT_{i}_SEQUENCE', '')
            prod_size = results.get(f'PRIMER_PAIR_{i}_PRODUCT_SIZE', '')
            fwd_list = results.get(f'PRIMER_LEFT_{i}', [])
            rev_list = results.get(f'PRIMER_RIGHT_{i}', [])
            fwd_len = fwd_list[1] if isinstance(fwd_list, list) and len(fwd_list) > 1 else ''
            rev_len = rev_list[1] if isinstance(rev_list, list) and len(rev_list) > 1 else ''
            fwd_tm = results.get(f'PRIMER_LEFT_{i}_TM', '')
            fwd_gc = results.get(f'PRIMER_LEFT_{i}_GC_PERCENT', '')
            rev_tm = results.get(f'PRIMER_RIGHT_{i}_TM', '')
            rev_gc = results.get(f'PRIMER_RIGHT_{i}_GC_PERCENT', '')

            pair_info = results.get(f'PRIMER_PAIR_{i}', {})
            pair_info['LEFT'] = fwd_list
            pair_info['RIGHT'] = rev_list
            self.primer_pair_details.append(pair_info)

            self.results_table.setItem(i*2, 0, QTableWidgetItem(str(i + 1)))
            self.results_table.setItem(i*2, 1, QTableWidgetItem("Fwd"))
            self.results_table.setItem(i*2, 2, QTableWidgetItem(fwd_seq))
            self.results_table.setItem(i*2, 3, QTableWidgetItem(str(fwd_len)))
            self.results_table.setItem(i*2, 4, QTableWidgetItem(f"{fwd_tm:.2f}" if isinstance(fwd_tm, (float, int)) else str(fwd_tm)))
            self.results_table.setItem(i*2, 5, QTableWidgetItem(f"{fwd_gc:.2f}" if isinstance(fwd_gc, (float, int)) else str(fwd_gc)))
            self.results_table.setItem(i*2, 6, QTableWidgetItem(str(prod_size)))

            self.results_table.setItem(i*2+1, 0, QTableWidgetItem(str(i + 1)))
            self.results_table.setItem(i*2+1, 1, QTableWidgetItem("Rev"))
            self.results_table.setItem(i*2+1, 2, QTableWidgetItem(rev_seq))
            self.results_table.setItem(i*2+1, 3, QTableWidgetItem(str(rev_len)))
            self.results_table.setItem(i*2+1, 4, QTableWidgetItem(f"{rev_tm:.2f}" if isinstance(rev_tm, (float, int)) else str(rev_tm)))
            self.results_table.setItem(i*2+1, 5, QTableWidgetItem(f"{rev_gc:.2f}" if isinstance(rev_gc, (float, int)) else str(rev_gc)))
            self.results_table.setItem(i*2+1, 6, QTableWidgetItem(str(prod_size)))

        self.status_bar.showMessage(f"Found {num_returned} primer pairs.")
        self.design_button.setEnabled(True)

    def show_error_message(self, message: str):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Error", message)
        self.status_bar.showMessage("Task failed or no results found.")
        self.design_button.setEnabled(True)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
