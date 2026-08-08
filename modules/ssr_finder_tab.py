"""SSR / Microsatellite Finder Tab — MISA-style perfect and compound SSR search."""

from __future__ import annotations

import csv
import os
from typing import Dict, List, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStyle,
    QStyleOptionComboBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from utils.common_components import BaseTabWidget, FileDropLineEdit
from utils.example_data import stage_example

# MISA default thresholds: minimum repeat count per unit length (1-6).
DEFAULT_THRESHOLDS: Dict[int, int] = {1: 10, 2: 6, 3: 5, 4: 5, 5: 5, 6: 5}
DEFAULT_COMPOUND_DIST = 100  # bp


class _PlaceholderComboBox(QComboBox):
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
            self.style().drawComplexControl(
                QStyle.ComplexControl.CC_ComboBox, opt, painter, self
            )
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

THRESHOLD_PRESETS: Dict[str, Dict[int, int]] = {
    "MISA default": dict(DEFAULT_THRESHOLDS),
    "Stringent": {1: 12, 2: 8, 3: 7, 4: 6, 5: 6, 6: 6},
    "Relaxed": {1: 8, 2: 5, 3: 4, 4: 4, 5: 4, 6: 4},
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


def find_ssrs(seq: str, thresholds: Dict[int, int]) -> List[dict]:
    """Scan perfect tandem repeats of unit length 1-6.

    Nested hits (e.g. (AT)10 also matches the tetra search) are deduplicated:
    the shortest repeat unit that forms a run wins, matching MISA behaviour.
    """
    results: List[dict] = []
    covered: List[Tuple[int, int]] = []
    n = len(seq)
    for unit_len in range(1, 7):
        thresh = thresholds.get(unit_len, 5)
        i = 0
        while i < n - unit_len:
            motif = seq[i : i + unit_len]
            j = i
            while j + unit_len <= n and seq[j : j + unit_len] == motif:
                j += unit_len
            repeats = (j - i) // unit_len
            if repeats >= thresh:
                if not any(s <= i and j <= e for s, e in covered):
                    results.append({
                        "start": i,
                        "end": j,
                        "unit_len": unit_len,
                        "motif": motif,
                        "repeats": repeats,
                    })
                    covered.append((i, j))
                i = j
            else:
                i += 1
    return results


def find_compound_ssrs(perfect: List[dict], max_dist: int = 100) -> List[dict]:
    """Group consecutive perfect SSRs separated by <= *max_dist* bp (MISA-style)."""
    if not perfect:
        return []
    ordered = sorted(perfect, key=lambda r: r["start"])
    groups: List[List[dict]] = []
    cur = [ordered[0]]
    for r in ordered[1:]:
        if r["start"] - cur[-1]["end"] <= max_dist:
            cur.append(r)
        else:
            groups.append(cur)
            cur = [r]
    groups.append(cur)

    compound: List[dict] = []
    for g in groups:
        if len(g) < 2:
            continue
        motif_str = "".join(f"({x['motif']}){x['repeats']}" for x in g)
        compound.append({
            "start": g[0]["start"] + 1,  # 1-based
            "end": g[-1]["end"],
            "size": g[-1]["end"] - g[0]["start"],
            "motif": motif_str,
            "n": len(g),
        })
    return compound


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


class SsrFinderTab(BaseTabWidget):
    """Find perfect and compound microsatellites (MISA-style thresholds)."""

    def __init__(self, parent=None):
        super().__init__("SSR / Microsatellite Finder", "sequence")
        self._records: List[Tuple[str, str]] = []
        self._record_results: List[dict] = []
        self._all_records_mode = True
        self._perfect: List[dict] = []
        self._compound: List[dict] = []
        self._setup_file_input()
        self._setup_parameters()
        self._setup_results_area()
        self._setup_export_button()
        self.output_group.hide()
        self.output_text.hide()

    # ── UI ─────────────────────────────────────────────────────────────

    def _setup_file_input(self):
        """File-only input row (Browse + drag & drop), consistent with other DNA tabs."""
        self.input_text.hide()
        self.upload_btn.hide()
        self.input_hint.hide()

        self.input_path_edit = FileDropLineEdit()
        self.input_path_edit.setReadOnly(True)
        self.input_path_edit.setPlaceholderText(
            self.tr("Select a FASTA file or drag & drop it here...")
        )
        self.input_path_edit.setToolTip(
            self.tr("DNA sequence (FASTA format) to search for microsatellites")
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
        self._record_combo = _PlaceholderComboBox()
        self._record_combo.setPlaceholderText(
            self.tr("Run first, then select a record to view (multi-record files)")
        )
        self._record_combo.setToolTip(
            self.tr(
                "Analyze all FASTA records, or pick one record "
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

        def thresh_spin(value: int, tooltip: str) -> QSpinBox:
            sp = QSpinBox()
            sp.setRange(2, 100)
            sp.setValue(value)
            sp.setFixedWidth(80)  # uniform width for the six threshold boxes
            sp.setToolTip(tooltip)
            return sp

        unit_names = ("Mono", "Di", "Tri", "Tetra", "Penta", "Hexa")
        row1 = QHBoxLayout()
        row1.addWidget(QLabel(self.tr("Min repeats:")))
        self._thresh_spins: Dict[int, QSpinBox] = {}
        for unit_len in range(1, 7):
            row1.addStretch(1)  # spread the six groups evenly across the row
            row1.addWidget(QLabel(self.tr(f"{unit_names[unit_len - 1]}:")))
            sp = thresh_spin(
                DEFAULT_THRESHOLDS[unit_len],
                self.tr(
                    f"Min repeats for {unit_names[unit_len - 1].lower()}-nucleotide SSRs "
                    f"(MISA default {DEFAULT_THRESHOLDS[unit_len]})"
                ),
            )
            row1.addWidget(sp)
            self._thresh_spins[unit_len] = sp
        row1.addStretch(1)
        grid.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel(self.tr("Preset:")))
        self._preset_combo = QComboBox()
        self._preset_combo.addItems(list(THRESHOLD_PRESETS.keys()) + ["Custom"])
        self._preset_combo.setFixedWidth(160)
        self._preset_combo.setToolTip(
            self.tr(
                "Apply a ready-made set of minimum repeat counts "
                "(MISA default / stringent / relaxed)"
            )
        )
        row2.addWidget(self._preset_combo)
        row2.addStretch(1)  # spread the three groups evenly across the row
        row2.addWidget(QLabel(self.tr("Compound distance:")))
        self._compound_dist_spin = QSpinBox()
        self._compound_dist_spin.setRange(0, 1000)
        self._compound_dist_spin.setValue(DEFAULT_COMPOUND_DIST)
        self._compound_dist_spin.setSuffix(self.tr(" bp"))
        self._compound_dist_spin.setFixedWidth(120)
        self._compound_dist_spin.setToolTip(
            self.tr(
                "Max gap (bp) between two SSRs to merge them into a compound SSR "
                "(MISA default 100)"
            )
        )
        row2.addWidget(self._compound_dist_spin)
        row2.addStretch(1)
        self._compound_check = QCheckBox(self.tr("Report compound SSRs"))
        self._compound_check.setChecked(True)
        row2.addWidget(self._compound_check)
        row2.addStretch(1)
        grid.addLayout(row2)

        self._preset_combo.currentTextChanged.connect(self._apply_preset)
        for sp in self._thresh_spins.values():
            sp.valueChanged.connect(self._on_thresh_changed)

        self.content_area.insertWidget(1, grp)

    def _apply_preset(self, name: str):
        """Apply a threshold preset to the six spin boxes."""
        values = THRESHOLD_PRESETS.get(name)
        if values is None:
            return
        self._preset_guard = True
        try:
            for unit_len, sp in self._thresh_spins.items():
                sp.setValue(values[unit_len])
        finally:
            self._preset_guard = False

    def _on_thresh_changed(self, _value: int):
        """Any manual spin change marks the thresholds as custom."""
        if getattr(self, "_preset_guard", False):
            return
        if self._preset_combo.currentText() != "Custom":
            self._preset_combo.setCurrentText("Custom")

    def _setup_results_area(self):
        grp = QGroupBox(self.tr("Microsatellites"))
        grp.setFlat(True)
        gl = QVBoxLayout(grp)
        gl.setContentsMargins(0, 14, 0, 4)
        gl.setSpacing(4)

        self._ssr_table = QTableWidget(0, 8)
        self._ssr_table.setHorizontalHeaderLabels([
            "#",
            "Type",
            "Motif",
            "Unit",
            "Repeats",
            "Start",
            "End",
            "Size (bp)",
        ])
        header = self._ssr_table.horizontalHeader()
        for col in range(7):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._ssr_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._ssr_table.setSortingEnabled(True)
        self._ssr_table.setMinimumHeight(120)
        gl.addWidget(self._ssr_table)

        self.add_content_widget(grp)

    # ── Run ────────────────────────────────────────────────────────────

    def _thresholds(self) -> Dict[int, int]:
        return {unit_len: sp.value() for unit_len, sp in self._thresh_spins.items()}

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
        """Detect SSRs for the currently selected record(s) and refresh results."""
        if not self._records:
            return
        combo_idx = self._record_combo.currentIndex()
        self._all_records_mode = combo_idx <= 0 and len(self._records) > 1
        thresholds = self._thresholds()
        max_dist = self._compound_dist_spin.value()
        report_compound = self._compound_check.isChecked()

        indexes = range(len(self._records)) if self._all_records_mode else [max(combo_idx - 1, 0)]
        self._record_results = []
        for i in indexes:
            header, seq = self._records[i]
            perfect = find_ssrs(seq, thresholds)
            compound = find_compound_ssrs(perfect, max_dist) if report_compound else []
            self._record_results.append({
                "name": self._record_label(header, i + 1),
                "seq": seq,
                "perfect": perfect,
                "compound": compound,
            })

        # Compound grouping is per record; flatten for the table.
        self._perfect = [r for rec in self._record_results for r in rec["perfect"]]
        self._compound = [r for rec in self._record_results for r in rec["compound"]]

        # ── Table (Record column only when scanning all records) ──
        record_col = self._all_records_mode
        labels = ["#", "Type", "Motif", "Unit", "Repeats", "Start", "End", "Size (bp)"]
        if record_col:
            labels.append("Record")
        self._ssr_table.setColumnCount(len(labels))
        self._ssr_table.setHorizontalHeaderLabels(labels)
        if record_col:
            self._ssr_table.horizontalHeader().setSectionResizeMode(
                8, QHeaderView.ResizeMode.ResizeToContents
            )

        flat_perfect = [
            (r, rec["name"]) for rec in self._record_results for r in rec["perfect"]
        ]
        flat_compound = [
            (r, rec["name"]) for rec in self._record_results for r in rec["compound"]
        ]

        self._ssr_table.setSortingEnabled(False)
        self._ssr_table.setRowCount(len(flat_perfect) + len(flat_compound))
        for i, (r, name) in enumerate(flat_perfect):
            values = [
                str(i + 1), "Perfect", f"({r['motif']}){r['repeats']}",
                str(r["unit_len"]), str(r["repeats"]), str(r["start"] + 1),
                str(r["end"]), str(r["end"] - r["start"]),
            ]
            if record_col:
                values.append(name)
            self._fill_row(i, values)
        for j, (r, name) in enumerate(flat_compound):
            row_idx = len(flat_perfect) + j
            values = [
                f"c{j + 1}", "Compound", r["motif"], "-", str(r["n"]),
                str(r["start"]), str(r["end"]), str(r["size"]),
            ]
            if record_col:
                values.append(name)
            self._fill_row(row_idx, values)
        self._ssr_table.setSortingEnabled(True)
        self._ssr_table.sortItems(5, Qt.SortOrder.AscendingOrder)

        # ── Status / export state ──
        self._export_btn.setEnabled(bool(self._perfect or self._compound))
        if not self._perfect and not self._compound:
            self.show_status(self.tr("No microsatellites found with the current thresholds"))
            return
        if self._all_records_mode:
            scope = self.tr(f" across {len(self._record_results)} sequences")
        else:
            rec = self._record_results[0]
            scope = self.tr(f" ({rec['name']}, {len(rec['seq']):,} bp)")
        msg = self.tr(f"Found {len(self._perfect)} perfect SSR(s)") + (
            self.tr(f", {len(self._compound)} compound") if self._compound else ""
        ) + scope
        self.show_status(msg)

    def _fill_row(self, row_idx: int, values: List[str]):
        """Populate one table row; numeric columns get value-aware sorting items."""
        for col_idx, value in enumerate(values):
            item = QTableWidgetItem(value)
            if col_idx in (4, 5, 6, 7):
                item = _NumItem(float(value), value)
            self._ssr_table.setItem(row_idx, col_idx, item)

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

        A summary-statistics block (MISA-style) is written above the table
        header so the exported file carries both overview and detail rows.
        """
        if not self._perfect and not self._compound:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Save CSV"), "ssr_results.csv", self.tr("CSV Files (*.csv)")
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
                    self._ssr_table.horizontalHeaderItem(c).text()
                    for c in range(self._ssr_table.columnCount())
                ])
                for row_idx in range(self._ssr_table.rowCount()):
                    writer.writerow([
                        self._ssr_table.item(row_idx, col).text()
                        for col in range(self._ssr_table.columnCount())
                    ])
            self.show_status(self.tr(f"Exported: {os.path.normpath(path)}"))
        except OSError as exc:
            self.show_status(self.tr(f"Error: Cannot write CSV \u2014 {exc}"))

    def _statistics(self) -> List[Tuple[str, str]]:
        """Summary statistics for the current view (single record or all)."""
        n_perfect = len(self._perfect)
        n_compound = len(self._compound)
        total_bp = sum(len(rec["seq"]) for rec in self._record_results)
        perfect_bp = sum(r["end"] - r["start"] for r in self._perfect)
        density = (n_perfect + n_compound) / total_bp * 1_000_000 if total_bp else 0.0
        coverage = perfect_bp / total_bp * 100 if total_bp else 0.0

        by_len: Dict[int, int] = {unit_len: 0 for unit_len in range(1, 7)}
        motif_counts: Dict[str, int] = {}
        for r in self._perfect:
            by_len[r["unit_len"]] += 1
            motif_counts[r["motif"]] = motif_counts.get(r["motif"], 0) + 1
        top_motifs = ", ".join(
            f"({motif}) x{count}"
            for motif, count in sorted(
                motif_counts.items(), key=lambda kv: (-kv[1], kv[0])
            )[:3]
        ) or "-"

        rows: List[Tuple[str, str]] = [
            ("Sequences", str(len(self._record_results))),
            ("Total_bp", f"{total_bp:,}"),
            ("Perfect_SSRs", str(n_perfect)),
            ("Compound_SSRs", str(n_compound)),
            ("SSR_density_per_Mb", f"{density:.2f}"),
            ("SSR_coverage_pct", f"{coverage:.2f}"),
        ]
        for unit_len, label in enumerate(
            ("Mono", "Di", "Tri", "Tetra", "Penta", "Hexa"), 1
        ):
            rows.append((f"SSRs_{label}", str(by_len[unit_len])))
        rows.append(("Top_motifs", top_motifs))
        return rows

    # ── Example / clear ────────────────────────────────────────────────

    def _load_example(self):
        path = stage_example("dna", "ssr_example.fasta")
        if not path:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. Please check your installation."),
            )
            return
        self.input_path_edit.setText(path)
        self.show_status(self.tr("Loaded example data: ssr_example.fasta"))

    def clear(self):
        self.input_path_edit.clear()
        self._records = []
        self._record_results = []
        self._perfect = []
        self._compound = []
        self._all_records_mode = True
        self._record_combo.blockSignals(True)
        self._record_combo.clear()
        self._record_combo.blockSignals(False)
        self._ssr_table.setRowCount(0)
        self._export_btn.setEnabled(False)
        super().clear()

    # ── Help ───────────────────────────────────────────────────────────

    def show_help(self):
        help_text = """
<h2>SSR / Microsatellite Finder &mdash; MISA-style Search</h2>

<p><b>What does this tool do?</b><br>
It searches DNA sequences for simple sequence repeats (SSRs, microsatellites)
&mdash; tandem repeats of 1&ndash;6 bp motifs &mdash; using the same detection
strategy as the MISA (MicroSAtellite identification) tool: per-motif-length
thresholds, plus compound SSR reporting when two repeats lie close together.</p>

<h3>Quick Start</h3>
<ol>
<li>Select a FASTA file (via <b>Browse</b> or drag-and-drop) or click <b>Example</b></li>
<li>Choose <b>Sequence</b> &mdash; <b>All records</b> scans every FASTA record (results
    get a <b>Record</b> column); single-record files show just the record name</li>
<li>Adjust the minimum repeat counts if needed (MISA defaults are pre-set)</li>
<li>Click <b>Run</b> &mdash; results appear in the table</li>
<li>Click <b>Export CSV</b> to save the results table with a summary-statistics
    header (counts, density, motif-length distribution) &mdash; Excel-friendly</li>
</ol>

<h3>Thresholds (MISA defaults)</h3>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>Motif length</b></td><td>Mono</td><td>Di</td><td>Tri</td><td>Tetra</td><td>Penta</td><td>Hexa</td></tr>
<tr><td><b>Min repeats</b></td><td>10</td><td>6</td><td>5</td><td>5</td><td>5</td><td>5</td></tr>
</table>
<p>The <b>Preset</b> dropdown applies a ready-made threshold set: MISA
default, <b>Stringent</b> (mono 12, di 8, tri&ndash;hexa 7/6), or
<b>Relaxed</b> (mono 8, di 5, tri&ndash;hexa 4). Adjusting any spin box
switches the preset to <b>Custom</b>.</p>
<p>A <b>compound SSR</b> (MISA type <code>c</code>) joins two or more perfect
SSRs separated by at most the <b>Compound distance</b> (default 100 bp), e.g.
<code>(AT)9(TG)6</code>.</p>

<h3>Result columns</h3>
<ul>
<li><b>Motif</b> &mdash; repeat unit with copy number, e.g. (AT)9</li>
<li><b>Repeats</b> &mdash; number of motif copies (compound: number of parts)</li>
<li><b>Start / End / Size</b> &mdash; 1-based positions and length in bp</li>
</ul>

<h3>Tips</h3>
<ul>
<li>Nested repeats are reported once with the shortest unit (e.g. (AT)10, not (ATAT)5)</li>
<li>Lower the di threshold to 4&ndash;5 to find shorter microsatellites</li>
<li>Click a column header to sort; results default to ascending start position</li>
<li>Multi-record FASTA files default to <b>All records</b>; compound SSRs are grouped
    within each record only, never across records</li>
<li>Switching the <b>Sequence</b> dropdown re-runs the analysis automatically</li>
</ul>
"""
        self.show_help_dialog("Help - SSR / Microsatellite Finder", help_text, 620, 520)
