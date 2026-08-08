"""CpG Island Finder Tab — scan for CpG islands (Gardiner-Garden & Frommer 1987)."""

from __future__ import annotations

import csv
import os
from typing import Dict, List, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from utils.common_components import BaseTabWidget, FileDropLineEdit, PlaceholderComboBox
from utils.example_data import stage_example

# Gardiner-Garden & Frommer (1987) default criteria.
DEFAULT_CRITERIA: Dict[str, object] = {
    "window": 100,
    "step": 1,
    "min_len": 200,
    "min_gc": 50.0,
    "min_oe": 0.6,
}

CRITERIA_PRESETS: Dict[str, Dict[str, object]] = {
    "Gardiner-Garden & Frommer 1987": dict(DEFAULT_CRITERIA),
    "Takai & Jones 2002": {
        "window": 100,
        "step": 1,
        "min_len": 500,
        "min_gc": 55.0,
        "min_oe": 0.65,
    },
    "Relaxed": {
        "window": 100,
        "step": 1,
        "min_len": 100,
        "min_gc": 50.0,
        "min_oe": 0.6,
    },
}


def _parse_fasta(text: str) -> List[Tuple[str, str]]:
    records: List[Tuple[str, str]] = []
    header = ""
    seq_lines: List[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if header:
                records.append((header, "".join(seq_lines)))
            header = line[1:].strip()
            seq_lines = []
        else:
            seq_lines.append(line)
    if header:
        records.append((header, "".join(seq_lines)))
    return records


def find_cpg_islands(
    seq: str,
    window: int = 100,
    step: int = 1,
    min_len: int = 200,
    min_gc: float = 50.0,
    min_oe: float = 0.6,
) -> List[dict]:
    """Gardiner-Garden & Frommer sliding-window CpG island scan.

    A window qualifies when GC% >= *min_gc* and observed/expected CpG >=
    *min_oe*. Adjacent qualifying windows are merged; merged regions shorter
    than *min_len* bp are discarded. Prefix sums keep the scan O(n).
    """
    n = len(seq)
    if n < window:
        return []

    c_pref = [0] * (n + 1)
    g_pref = [0] * (n + 1)
    cpg_pref = [0] * (n + 1)
    for i in range(n):
        c_pref[i + 1] = c_pref[i] + (1 if seq[i] == "C" else 0)
        g_pref[i + 1] = g_pref[i] + (1 if seq[i] == "G" else 0)
        cpg_pref[i + 1] = cpg_pref[i] + (1 if seq[i : i + 2] == "CG" else 0)

    merged: List[List[int]] = []
    cur: List[int] | None = None
    for start in range(0, n - window + 1, step):
        end = start + window
        c = c_pref[end] - c_pref[start]
        g = g_pref[end] - g_pref[start]
        cpg = cpg_pref[end] - cpg_pref[start]
        gc = (c + g) / window * 100
        oe = (cpg * window) / (c * g) if c and g else 0.0
        ok = gc >= min_gc and oe >= min_oe
        if ok:
            if cur is None:
                cur = [start, end]
            else:
                cur[1] = end
        elif cur is not None:
            merged.append(cur)
            cur = None
    if cur is not None:
        merged.append(cur)

    results: List[dict] = []
    for start, end in merged:
        length = end - start
        if length < min_len:
            continue
        region = seq[start:end]
        c = region.count("C")
        g = region.count("G")
        cpg = region.count("CG")
        gc = (c + g) / length * 100
        oe = (cpg * length) / (c * g) if c and g else 0.0
        results.append({
            "start": start + 1,  # 1-based
            "end": end,
            "length": length,
            "gc": gc,
            "oe": oe,
            "cpg": cpg,
            "cg": c + g,
        })
    return results


class _NumItem(QTableWidgetItem):
    """QTableWidgetItem that sorts numerically instead of lexicographically."""

    def __init__(self, value: float, text: str):
        super().__init__(text)
        self._val = value

    def __lt__(self, other):
        try:
            return self._val < other._val
        except Exception:
            return super().__lt__(other)


class CpGIslandTab(BaseTabWidget):
    """Scan genomic DNA for CpG islands using the classic sliding-window criteria."""

    def __init__(self, parent=None):
        super().__init__("CpG Island Finder", "sequence")
        self._records: List[Tuple[str, str]] = []
        self._record_results: List[dict] = []
        self._all_records_mode = True
        self._results: List[dict] = []
        self._setup_file_input()
        self._setup_parameters()
        self._setup_results_area()
        self._setup_export_button()
        self.output_group.hide()
        self.output_text.hide()

    # ── UI ─────────────────────────────────────────────────────────────

    def _setup_file_input(self):
        """File-only input rows (Browse + drag & drop), consistent with other DNA tabs."""
        self.input_text.hide()
        self.upload_btn.hide()
        self.input_hint.hide()

        self.input_path_edit = FileDropLineEdit()
        self.input_path_edit.setReadOnly(True)
        self.input_path_edit.setPlaceholderText(
            self.tr("Select a FASTA file or drag & drop it here...")
        )
        self.input_path_edit.setToolTip(
            self.tr("Genomic DNA sequence (FASTA format) to scan for CpG islands")
        )

        self.example_btn = QPushButton(self.tr("Example"))
        self.example_btn.clicked.connect(self._load_example)

        ig_layout = self.input_group.layout()
        ig_layout.setContentsMargins(6, 14, 6, 4)
        ig_layout.removeWidget(self.upload_btn)

        # Two aligned rows: label column + input column (shared left edge).
        form = QGridLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)
        form.addWidget(QLabel(self.tr("Sequence File:")), 0, 0)
        form.addWidget(self.input_path_edit, 0, 1)
        self.browse_btn = QPushButton(self.tr("Browse"))
        self.browse_btn.clicked.connect(self._browse_input_file)
        form.addWidget(self.browse_btn, 0, 2)
        form.addWidget(self.example_btn, 0, 3)

        # Record selector: analyze all FASTA records or a single one.
        form.addWidget(QLabel(self.tr("Sequence:")), 1, 0)
        self._record_combo = PlaceholderComboBox()
        self._record_combo.setPlaceholderText(
            self.tr("Run first, then select a record to view (multi-record files)")
        )
        self._record_combo.setToolTip(
            self.tr(
                "Scan all FASTA records, or pick one record "
                "(single-record files show just the record)"
            )
        )
        form.addWidget(self._record_combo, 1, 1, 1, 3)
        form.setColumnStretch(1, 1)
        ig_layout.insertLayout(1, form)
        self._record_combo.currentIndexChanged.connect(self._on_record_changed)

    def _browse_input_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Open FASTA File"),
            "",
            self.tr("FASTA Files (*.fasta *.fa *.fas *.fna *.txt);;All Files (*)"),
        )
        if path:
            self.input_path_edit.setText(os.path.normpath(path))

    def _setup_parameters(self):
        grp = QGroupBox(self.tr("Parameters"))
        grp.setFlat(True)
        grid = QVBoxLayout(grp)
        grid.setContentsMargins(6, 16, 6, 4)
        grid.setSpacing(6)

        def int_spin(value: int, lo: int, hi: int, suffix: str, tooltip: str) -> QSpinBox:
            sp = QSpinBox()
            sp.setRange(lo, hi)
            sp.setValue(value)
            sp.setSuffix(suffix)
            sp.setFixedWidth(100)  # uniform width across the row
            sp.setToolTip(tooltip)
            return sp

        # Row 1: criteria preset + window size (compact, left-aligned).
        row1 = QHBoxLayout()
        row1.addWidget(QLabel(self.tr("Criteria:")))
        self._criteria_combo = QComboBox()
        self._criteria_combo.addItems(list(CRITERIA_PRESETS.keys()) + ["Custom"])
        self._criteria_combo.setFixedWidth(280)
        self._criteria_combo.setToolTip(
            self.tr(
                "Apply a ready-made set of window / length / GC / CpG o/e "
                "criteria (classic definitions from the literature)"
            )
        )
        row1.addWidget(self._criteria_combo)
        row1.addSpacing(16)
        row1.addWidget(QLabel(self.tr("Window:")))
        self.window_spin = int_spin(
            int(DEFAULT_CRITERIA["window"]),
            50,
            1000,
            self.tr(" bp"),
            self.tr("Sliding window size (classic: 100 bp)"),
        )
        row1.addWidget(self.window_spin)
        row1.addStretch()
        grid.addLayout(row1)

        # Row 2: step / min length / GC% / CpG o/e (compact, left-aligned).
        row2 = QHBoxLayout()
        row2.addWidget(QLabel(self.tr("Step:")))
        self.step_spin = int_spin(
            int(DEFAULT_CRITERIA["step"]),
            1,
            100,
            self.tr(" bp"),
            self.tr("Distance between windows (classic: 1 bp)"),
        )
        row2.addWidget(self.step_spin)
        row2.addSpacing(16)
        row2.addWidget(QLabel(self.tr("Min length:")))
        self.min_len_spin = int_spin(
            int(DEFAULT_CRITERIA["min_len"]),
            100,
            10000,
            self.tr(" bp"),
            self.tr("Minimum island length (classic: 200 bp)"),
        )
        row2.addWidget(self.min_len_spin)
        row2.addSpacing(16)
        row2.addWidget(QLabel(self.tr("Min GC%:")))
        self.gc_spin = QDoubleSpinBox()
        self.gc_spin.setRange(30, 80)
        self.gc_spin.setDecimals(1)
        self.gc_spin.setValue(float(DEFAULT_CRITERIA["min_gc"]))
        self.gc_spin.setSuffix("%")
        self.gc_spin.setFixedWidth(100)
        self.gc_spin.setToolTip(self.tr("Minimum GC content in a window (classic: 50%)"))
        row2.addWidget(self.gc_spin)
        row2.addSpacing(16)
        row2.addWidget(QLabel(self.tr("Min CpG o/e:")))
        self.oe_spin = QDoubleSpinBox()
        self.oe_spin.setRange(0.1, 2.0)
        self.oe_spin.setDecimals(2)
        self.oe_spin.setSingleStep(0.05)
        self.oe_spin.setValue(float(DEFAULT_CRITERIA["min_oe"]))
        self.oe_spin.setFixedWidth(100)
        self.oe_spin.setToolTip(
            self.tr(
                "Minimum observed/expected CpG ratio in a window "
                "(classic: 0.6; expected = C x G / length)"
            )
        )
        row2.addWidget(self.oe_spin)
        row2.addStretch()
        grid.addLayout(row2)

        self._criteria_combo.currentTextChanged.connect(self._apply_criteria)
        for sp in (
            self.window_spin,
            self.step_spin,
            self.min_len_spin,
            self.gc_spin,
            self.oe_spin,
        ):
            sp.valueChanged.connect(self._on_criteria_changed)

        self.content_area.insertWidget(1, grp)

    def _apply_criteria(self, name: str):
        """Apply a criteria preset to the five parameter spin boxes."""
        values = CRITERIA_PRESETS.get(name)
        if values is None:
            return
        self._criteria_guard = True
        try:
            self.window_spin.setValue(int(values["window"]))
            self.step_spin.setValue(int(values["step"]))
            self.min_len_spin.setValue(int(values["min_len"]))
            self.gc_spin.setValue(float(values["min_gc"]))
            self.oe_spin.setValue(float(values["min_oe"]))
        finally:
            self._criteria_guard = False

    def _on_criteria_changed(self, _value):
        """Any manual spin change marks the criteria as custom."""
        if getattr(self, "_criteria_guard", False):
            return
        if self._criteria_combo.currentText() != "Custom":
            self._criteria_combo.setCurrentText("Custom")

    def _setup_results_area(self):
        grp = QGroupBox(self.tr("CpG Islands"))
        grp.setFlat(True)
        gl = QVBoxLayout(grp)
        gl.setContentsMargins(0, 14, 0, 4)
        gl.setSpacing(4)

        self._island_table = QTableWidget(0, 8)
        self._island_table.setHorizontalHeaderLabels([
            "#",
            "Start",
            "End",
            "Length (bp)",
            "GC%",
            "CpG o/e",
            "CpG",
            "C+G",
        ])
        header = self._island_table.horizontalHeader()
        header.setMinimumSectionSize(70)  # uniform widths for short numeric cells
        for col in range(8):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._island_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._island_table.setSortingEnabled(True)
        self._island_table.setMinimumHeight(120)
        gl.addWidget(self._island_table)

        self.add_content_widget(grp)

    # ── Run ────────────────────────────────────────────────────────────

    def run(self):
        path = self.input_path_edit.text().strip()
        if not path:
            self.show_status(self.tr("Please select a DNA sequence file."))
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except UnicodeDecodeError:
            with open(path, "r", encoding="latin-1") as fh:
                text = fh.read()
        except OSError as exc:
            self.show_status(self.tr(f"Error: Cannot read file \u2014 {exc}"))
            return

        records = _parse_fasta(text)
        if not records:
            self.show_status(self.tr("No valid FASTA sequence found."))
            return
        cleaned: List[Tuple[str, str]] = []
        for header, seq in records:
            seq = "".join(c for c in seq.upper() if c.isalpha()).replace("U", "T")
            if not seq:
                continue
            if not all(c in "ACGTN" for c in seq):
                self.show_status(self.tr("Invalid characters. Only A/T/G/C/N allowed."))
                return
            cleaned.append((header, seq))
        if not cleaned:
            self.show_status(self.tr("No valid sequence found."))
            return
        self._records = cleaned

        # Rebuild the record selector, preserving the previous pick.
        previous = self._record_combo.currentText()
        self._record_combo.blockSignals(True)
        self._record_combo.clear()
        if len(cleaned) > 1:
            self._record_combo.addItem(self.tr(f"All records ({len(cleaned)})"))
        for i, (header, _seq) in enumerate(cleaned, 1):
            self._record_combo.addItem(self._record_label(header, i))
        index = self._record_combo.findText(previous) if previous else 0
        self._record_combo.setCurrentIndex(index if index >= 0 else 0)
        self._record_combo.blockSignals(False)

        self._analyze()

    @staticmethod
    def _record_label(header: str, index: int) -> str:
        """Short display label for a FASTA record (first token, max 40 chars)."""
        name = header.split()[0].strip() if header.strip() else ""
        name = name or f"Record {index}"
        return name if len(name) <= 40 else name[:40] + "..."

    def _analyze(self):
        """Scan the currently selected record(s) and refresh results."""
        if not self._records:
            return
        combo_idx = self._record_combo.currentIndex()
        self._all_records_mode = combo_idx <= 0 and len(self._records) > 1
        indexes = (
            range(len(self._records))
            if self._all_records_mode
            else [max(combo_idx - 1, 0)]
        )

        self._record_results = []
        for i in indexes:
            header, seq = self._records[i]
            islands = find_cpg_islands(
                seq,
                window=self.window_spin.value(),
                step=self.step_spin.value(),
                min_len=self.min_len_spin.value(),
                min_gc=self.gc_spin.value(),
                min_oe=self.oe_spin.value(),
            )
            self._record_results.append({
                "name": self._record_label(header, i + 1),
                "seq": seq,
                "islands": islands,
            })

        self._results = [r for rec in self._record_results for r in rec["islands"]]

        # ── Table (Record column only when scanning all records) ──
        record_col = self._all_records_mode
        labels = ["#", "Start", "End", "Length (bp)", "GC%", "CpG o/e", "CpG", "C+G"]
        if record_col:
            labels.append("Record")
        self._island_table.setColumnCount(len(labels))
        self._island_table.setHorizontalHeaderLabels(labels)
        if record_col:
            self._island_table.horizontalHeader().setSectionResizeMode(
                8, QHeaderView.ResizeMode.ResizeToContents
            )

        flat = [(r, rec["name"]) for rec in self._record_results for r in rec["islands"]]
        self._island_table.setSortingEnabled(False)
        self._island_table.setRowCount(len(flat))
        for i, (r, name) in enumerate(flat):
            values = [
                str(i + 1), str(r["start"]), str(r["end"]), str(r["length"]),
                f"{r['gc']:.1f}", f"{r['oe']:.2f}", str(r["cpg"]), str(r["cg"]),
            ]
            if record_col:
                values.append(name)
            self._fill_row(i, values)
        self._island_table.setSortingEnabled(True)
        self._island_table.sortItems(1, Qt.SortOrder.AscendingOrder)

        # ── Status / export state ──
        self._export_btn.setEnabled(bool(self._results))
        if not self._results:
            self.show_status(self.tr("No CpG islands found with the current criteria"))
            return
        total = sum(r["length"] for r in self._results)
        if self._all_records_mode:
            scope = self.tr(f" across {len(self._record_results)} sequences")
        else:
            rec = self._record_results[0]
            scope = self.tr(f" ({rec['name']})")
        self.show_status(
            self.tr(f"Found {len(self._results)} CpG island(s), total {total:,} bp") + scope
        )

    def _fill_row(self, row_idx: int, values: List[str]):
        """Populate one table row; numeric columns get value-aware sorting items."""
        for col_idx, value in enumerate(values):
            item = QTableWidgetItem(value)
            if col_idx < 8:
                item = _NumItem(float(value), value)
            self._island_table.setItem(row_idx, col_idx, item)

    def _on_record_changed(self, _index: int):
        """Re-analyze when the record selector changes (no data yet: ignore)."""
        if not self._records:
            return
        self._analyze()

    # ── Export ─────────────────────────────────────────────────────────

    def _setup_export_button(self):
        """Export CSV button between Clear and Help in the status row."""
        self._export_btn = QPushButton(self.tr("Export CSV"))
        self._export_btn.setFixedWidth(110)
        self._export_btn.setProperty("accentButton", True)
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export_csv)
        self._export_btn.style().unpolish(self._export_btn)
        self._export_btn.style().polish(self._export_btn)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self._export_btn)

    def _export_csv(self):
        """Save the current results table as CSV (UTF-8 BOM for Excel).

        A summary-statistics block is written above the table header so the
        exported file carries both overview and detail rows.
        """
        if not self._results:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Save CSV"), "cpg_islands.csv", self.tr("CSV Files (*.csv)")
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.writer(fh)
                writer.writerow(["== Statistics =="])
                for key, value in self._statistics():
                    writer.writerow([key, value])
                writer.writerow([])
                writer.writerow([
                    self._island_table.horizontalHeaderItem(c).text()
                    for c in range(self._island_table.columnCount())
                ])
                for row_idx in range(self._island_table.rowCount()):
                    writer.writerow([
                        self._island_table.item(row_idx, col).text()
                        for col in range(self._island_table.columnCount())
                    ])
            self.show_status(self.tr(f"Exported: {os.path.normpath(path)}"))
        except OSError as exc:
            self.show_status(self.tr(f"Error: Cannot write CSV \u2014 {exc}"))

    def _statistics(self) -> List[Tuple[str, str]]:
        """Summary statistics for the current view (single record or all)."""
        total_bp = 0
        c_total = g_total = cpg_total = 0
        for rec in self._record_results:
            seq = rec["seq"]
            total_bp += len(seq)
            c_total += seq.count("C")
            g_total += seq.count("G")
            cpg_total += seq.count("CG")
        island_bp = sum(r["length"] for r in self._results)
        coverage = island_bp / total_bp * 100 if total_bp else 0.0
        genome_oe = (
            (cpg_total * total_bp) / (c_total * g_total)
            if c_total and g_total
            else 0.0
        )
        ge_500 = sum(1 for r in self._results if r["length"] >= 500)
        lt_500 = len(self._results) - ge_500

        return [
            ("Sequences", str(len(self._record_results))),
            ("Total_bp", f"{total_bp:,}"),
            ("CpG_islands", str(len(self._results))),
            ("Island_bp", f"{island_bp:,}"),
            ("Island_coverage_pct", f"{coverage:.2f}"),
            ("Genome_CpG_o/e", f"{genome_oe:.2f}"),
            ("Islands_200_500_bp", str(lt_500)),
            ("Islands_ge_500_bp", str(ge_500)),
        ]

    # ── Example / clear ────────────────────────────────────────────────

    def _load_example(self):
        path = stage_example("dna", "cpg_island_example.fasta")
        if not path:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. Please check your installation."),
            )
            return
        self.input_path_edit.setText(path)
        self.show_status(self.tr("Loaded example data: cpg_island_example.fasta"))

    def clear(self):
        self.input_path_edit.clear()
        self._records = []
        self._record_results = []
        self._results = []
        self._all_records_mode = True
        self._record_combo.blockSignals(True)
        self._record_combo.clear()
        self._record_combo.blockSignals(False)
        self._island_table.setRowCount(0)
        self._export_btn.setEnabled(False)
        super().clear()

    # ── Help ───────────────────────────────────────────────────────────

    def show_help(self):
        help_text = """
<h2>CpG Island Finder &mdash; Gardiner-Garden &amp; Frommer Criteria</h2>

<p><b>What does this tool do?</b><br>
It scans genomic DNA and reports regions that fulfil the classic CpG island
criteria (Gardiner-Garden &amp; Frommer 1987): a sliding window with
<b>GC content &ge; 50%</b> and <b>observed/expected CpG ratio &ge; 0.6</b>,
merged into islands of <b>&ge; 200 bp</b>.</p>

<h3>What is a CpG island?</h3>
<p>A <b>CpG island</b> is a stretch of DNA (typically ~200 bp to a few kb)
that is unusually rich in G+C bases and, more importantly, in <b>CpG
dinucleotides</b> &mdash; a cytosine immediately followed by a guanine on the
same strand. In most of the genome CpG dinucleotides are heavily depleted:
cytosines in CpG pairs are frequent methylation targets, and methylated
cytosines mutate to thymine over evolutionary time, leaving the genome with
about one fifth of the CpG count expected by chance. Regions that escape this
process &mdash; because their CpGs stay unmethylated &mdash; keep the expected
level of CpG and stand out as "islands" of high GC and high CpG content.</p>
<ul>
<li><b>~70% of human gene promoters</b> lie within CpG islands</li>
<li>Promoter CpG islands are usually <b>unmethylated</b> in normal cells and
    associate with active gene expression</li>
<li>Abnormal hypermethylation of these islands is a hallmark of many cancers</li>
</ul>

<h3>Quick Start</h3>
<ol>
<li>Select a FASTA file (via <b>Browse</b> or drag-and-drop) or click <b>Example</b></li>
<li>Choose <b>Sequence</b> &mdash; <b>All records</b> scans every FASTA record (results
    get a <b>Record</b> column); single-record files show just the record name</li>
<li>Pick a <b>Criteria</b> preset or adjust the parameters (classic defaults pre-set)</li>
<li>Click <b>Run</b> &mdash; islands appear in the table</li>
<li>Click <b>Export CSV</b> to save the results with a summary-statistics header</li>
</ol>

<h3>Criteria presets</h3>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>Preset</b></td><td>Window</td><td>Min length</td><td>Min GC%</td><td>Min o/e</td></tr>
<tr><td><b>Gardiner-Garden &amp; Frommer 1987</b></td><td>100</td><td>200</td><td>50</td><td>0.60</td></tr>
<tr><td><b>Takai &amp; Jones 2002</b></td><td>100</td><td>500</td><td>55</td><td>0.65</td></tr>
<tr><td><b>Relaxed</b></td><td>100</td><td>100</td><td>50</td><td>0.60</td></tr>
</table>
<p>Takai &amp; Jones (2002) is the stricter definition used for most human-genome
studies. Adjusting any spin box switches the preset to <b>Custom</b>.</p>

<h3>Metrics Explained</h3>
<ul>
<li><b>GC%</b> &mdash; fraction of G+C bases in the island</li>
<li><b>CpG o/e</b> &mdash; observed/expected CpG dinucleotides, where
expected = (C count &times; G count) / length. Values &gt; 0.6 indicate
CpG enrichment beyond chance</li>
<li><b>CpG</b> / <b>C+G</b> &mdash; raw dinucleotide and base counts</li>
</ul>

<h3>Why CpG islands matter</h3>
<ul>
<li>Most human gene promoters lie within CpG islands</li>
<li>Unmethylated CpG islands are associated with active gene expression</li>
<li>CpG enrichment reflects the loss of methylation-driven C&rarr;T mutation</li>
</ul>

<h3>Tips</h3>
<ul>
<li>Use the <b>Gardiner-Garden &amp; Frommer 1987</b> preset for the classic
definition; <b>Takai &amp; Jones 2002</b> is the stricter human-genome standard</li>
<li>Step &gt; 1 speeds up large sequences but approximates island boundaries</li>
<li>Multi-record FASTA files default to <b>All records</b>; islands are merged
    within each record only, never across records</li>
<li>Click a column header to sort; results default to ascending start position</li>
<li>Switching the <b>Sequence</b> dropdown re-runs the analysis automatically</li>
</ul>
"""
        self.show_help_dialog("Help - CpG Island Finder", help_text, 620, 520)
