"""CpG Island Finder Tab — scan for CpG islands (Gardiner-Garden & Frommer 1987)."""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
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

from utils.common_components import BaseTabWidget, FileDropLineEdit
from utils.example_data import stage_example


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
    cur: Optional[List[int]] = None
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


class CpGIslandTab(BaseTabWidget):
    """Scan genomic DNA for CpG islands using the classic sliding-window criteria."""

    def __init__(self, parent=None):
        super().__init__("CpG Island Finder", "sequence")
        self._results: List[dict] = []
        self._setup_file_input()
        self._setup_parameters()
        self._setup_results_area()
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
            self.tr("Genomic DNA sequence (FASTA format) to scan for CpG islands")
        )

        self.example_btn = QPushButton(self.tr("Example"))
        self.example_btn.clicked.connect(self._load_example)

        ig_layout = self.input_group.layout()
        ig_layout.setContentsMargins(6, 16, 6, 4)
        ig_layout.removeWidget(self.upload_btn)
        row = QHBoxLayout()
        row.addWidget(QLabel(self.tr("Sequence File:")))
        row.addWidget(self.input_path_edit, 1)
        self.browse_btn = QPushButton(self.tr("Browse"))
        self.browse_btn.clicked.connect(self._browse_input_file)
        row.addWidget(self.browse_btn)
        row.addWidget(self.example_btn)
        ig_layout.insertLayout(1, row)

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

        row1 = QHBoxLayout()
        row1.addWidget(QLabel(self.tr("Window:")))
        self.window_spin = QSpinBox()
        self.window_spin.setRange(50, 1000)
        self.window_spin.setSingleStep(10)
        self.window_spin.setValue(100)
        self.window_spin.setSuffix(self.tr(" bp"))
        self.window_spin.setToolTip(self.tr("Sliding window size (classic: 100 bp)"))
        row1.addWidget(self.window_spin)
        row1.addSpacing(16)
        row1.addWidget(QLabel(self.tr("Step:")))
        self.step_spin = QSpinBox()
        self.step_spin.setRange(1, 100)
        self.step_spin.setValue(1)
        self.step_spin.setSuffix(self.tr(" bp"))
        self.step_spin.setToolTip(self.tr("Distance between windows (classic: 1 bp)"))
        row1.addWidget(self.step_spin)
        row1.addSpacing(16)
        row1.addWidget(QLabel(self.tr("Min length:")))
        self.min_len_spin = QSpinBox()
        self.min_len_spin.setRange(100, 10000)
        self.min_len_spin.setSingleStep(50)
        self.min_len_spin.setValue(200)
        self.min_len_spin.setSuffix(self.tr(" bp"))
        self.min_len_spin.setToolTip(self.tr("Minimum island length (classic: 200 bp)"))
        row1.addWidget(self.min_len_spin)
        row1.addStretch()
        grid.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel(self.tr("Min GC%:")))
        self.gc_spin = QDoubleSpinBox()
        self.gc_spin.setRange(30, 80)
        self.gc_spin.setDecimals(1)
        self.gc_spin.setValue(50.0)
        self.gc_spin.setSuffix("%")
        self.gc_spin.setToolTip(self.tr("Minimum GC content in a window (classic: 50%)"))
        row2.addWidget(self.gc_spin)
        row2.addSpacing(16)
        row2.addWidget(QLabel(self.tr("Min CpG o/e:")))
        self.oe_spin = QDoubleSpinBox()
        self.oe_spin.setRange(0.1, 2.0)
        self.oe_spin.setDecimals(2)
        self.oe_spin.setSingleStep(0.05)
        self.oe_spin.setValue(0.6)
        self.oe_spin.setToolTip(
            self.tr(
                "Minimum observed/expected CpG ratio in a window "
                "(classic: 0.6; expected = C x G / length)"
            )
        )
        row2.addWidget(self.oe_spin)
        row2.addStretch()
        grid.addLayout(row2)

        self.content_area.insertWidget(1, grp)

    def _setup_results_area(self):
        grp = QGroupBox(self.tr("CpG Islands"))
        grp.setFlat(True)
        gl = QVBoxLayout(grp)
        gl.setContentsMargins(0, 16, 0, 4)
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
        for col in range(7):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self._island_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._island_table.setMinimumHeight(120)
        gl.addWidget(self._island_table)

        self._map_fig = Figure(figsize=(8, 1.6), dpi=100)
        self._map_canvas = FigureCanvas(self._map_fig)
        self._map_canvas.setMinimumHeight(130)
        gl.addWidget(self._map_canvas)

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
        seq = "".join(c for c in records[0][1].upper() if c.isalpha()).replace("U", "T")
        if not seq:
            self.show_status(self.tr("No valid sequence found."))
            return
        if not all(c in "ACGTN" for c in seq):
            self.show_status(self.tr("Invalid characters. Only A/T/G/C/N allowed."))
            return

        self._results = find_cpg_islands(
            seq,
            window=self.window_spin.value(),
            step=self.step_spin.value(),
            min_len=self.min_len_spin.value(),
            min_gc=self.gc_spin.value(),
            min_oe=self.oe_spin.value(),
        )

        self._island_table.setRowCount(len(self._results))
        for i, r in enumerate(self._results):
            self._island_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self._island_table.setItem(i, 1, QTableWidgetItem(str(r["start"])))
            self._island_table.setItem(i, 2, QTableWidgetItem(str(r["end"])))
            self._island_table.setItem(i, 3, QTableWidgetItem(str(r["length"])))
            self._island_table.setItem(i, 4, QTableWidgetItem(f"{r['gc']:.1f}"))
            self._island_table.setItem(i, 5, QTableWidgetItem(f"{r['oe']:.2f}"))
            self._island_table.setItem(i, 6, QTableWidgetItem(str(r["cpg"])))
            self._island_table.setItem(i, 7, QTableWidgetItem(str(r["cg"])))

        self._draw_map(seq, len(seq))
        if self._results:
            total = sum(r["length"] for r in self._results)
            self.show_status(
                self.tr(f"Found {len(self._results)} CpG island(s), total {total:,} bp")
            )
        else:
            self.show_status(self.tr("No CpG islands found with the current criteria"))

    def _draw_map(self, seq: str, seq_len: int):
        self._map_fig.clear()
        ax = self._map_fig.add_subplot(111)
        ax.set_facecolor("#fafafa")
        ax.plot([1, seq_len], [0, 0], color="#333", linewidth=2.5, zorder=0)
        y_h = 0.35
        for r in self._results:
            ax.plot(
                [r["start"], r["end"]],
                [0, 0],
                color="#2e7d32",
                linewidth=7,
                solid_capstyle="butt",
                zorder=1,
            )
            ax.text(
                (r["start"] + r["end"]) / 2,
                y_h,
                f"{r['length']} bp",
                ha="center",
                va="bottom",
                fontsize=7,
                color="#2e7d32",
            )
        step = max(1, seq_len // 10)
        ticks = list(range(1, seq_len + 1, step))
        if ticks[-1] != seq_len:
            ticks.append(seq_len)
        ax.set_xticks(ticks)
        ax.set_xticklabels([str(t) for t in ticks], fontsize=7)
        ax.set_xlim(0, seq_len)
        ax.set_ylim(-0.5, 0.8)
        ax.set_yticks([])
        ax.set_xlabel(self.tr("Position (bp)"), fontsize=8)
        for spine in ("top", "right", "left"):
            ax.spines[spine].set_visible(False)
        self._map_fig.tight_layout(pad=0.5)
        self._map_canvas.draw_idle()

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
        self._results = []
        self._island_table.setRowCount(0)
        self._map_fig.clear()
        self._map_canvas.draw_idle()
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

<h3>Quick Start</h3>
<ol>
<li>Select a FASTA file (via <b>Browse</b> or drag-and-drop) or click <b>Example</b></li>
<li>Adjust the parameters if needed (classic defaults are pre-set)</li>
<li>Click <b>Run</b> &mdash; islands appear in the table and on the map</li>
</ol>

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
<li>Use <b>Window = 100, Step = 1, Min length = 200, GC% = 50, o/e = 0.6</b> for the
classic definition; relaxed criteria (GC% = 50, o/e = 0.48) find more islands</li>
<li>Step &gt; 1 speeds up large sequences but approximates island boundaries</li>
<li>The first FASTA record is analysed if the file contains several</li>
</ul>
"""
        self.show_help_dialog("Help - CpG Island Finder", help_text, 620, 520)
