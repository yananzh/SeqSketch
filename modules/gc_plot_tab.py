"""GC Content / GC Skew Plot Tab — sliding-window analysis for DNA sequences."""

import os

import matplotlib
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from utils.common_components import BaseTabWidget, FileDropLineEdit
from utils.example_data import stage_example

matplotlib.use("Qt5Agg")
import math

import matplotlib.ticker as ticker
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class GCPlotTab(BaseTabWidget):
    """GC Content / GC Skew Plot — sliding-window analysis for DNA sequences."""

    def __init__(self, parent=None):
        super().__init__("GC Content / GC Skew", "sequence")
        self._logo_generated = False

        self.run_btn.setText("Plot")
        self.run_btn.setFixedWidth(100)
        if hasattr(self, "copy_btn"):
            self.copy_btn.hide()
        if hasattr(self, "export_btn"):
            self.export_btn.hide()
        self.output_group.hide()
        self.output_text.hide()
        self.output_label.hide()
        self.input_hint.hide()

        self._setup_file_input()

        # Add Save Figure button in the status row after Plot
        self._save_fig_btn = QPushButton(self.tr("Save Figure"))
        self._save_fig_btn.setFixedWidth(110)
        self._save_fig_btn.clicked.connect(self.export_result)
        _idx = self.status_layout.indexOf(self.run_btn)
        self.status_layout.insertWidget(_idx + 1, self._save_fig_btn)

        self._setup_parameters()
        self._add_plot_canvas()

        # Keep step default in sync with window changes
        self.window_spin.valueChanged.connect(self._sync_step_to_window)

    def _setup_file_input(self):
        """Replace the paste editor with a file-only input (Browse + drag & drop)."""
        self.input_text.hide()
        self.upload_btn.hide()

        self.input_path_edit = FileDropLineEdit()
        self.input_path_edit.setReadOnly(True)
        self.input_path_edit.setPlaceholderText(
            self.tr("Select a FASTA file or drag & drop it here...")
        )
        self.input_path_edit.setToolTip(
            self.tr("DNA sequence (FASTA format) for GC content / GC skew analysis")
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
            self._auto_adjust_window()

    def _sync_step_to_window(self, val):
        """When window changes, update step default to match (non-overlapping)."""
        if self.step_spin.value() == self.step_spin.maximum() or self.step_spin.value() <= 1:
            self.step_spin.setValue(val)

    def _load_example(self):
        """Stage the bundled pBR322 plasmid example and fill the file field."""
        path = stage_example("dna", "pBR322.fasta")
        if not path:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. Please check your installation."),
            )
            return
        self.input_path_edit.setText(path)
        self._auto_adjust_window()
        self.show_status(self.tr("Loaded example data: pBR322.fasta"))

    def _auto_adjust_window(self):
        """Set window size automatically based on the current input file length."""
        path = self.input_path_edit.text().strip()
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            return
        records = self._parse_fasta(text)
        if not records:
            return
        _, seq = records[0]
        clean = "".join(c for c in seq.upper() if c.isalpha())
        n = len(clean)
        if n < 1:
            return
        # Scale window as ~0.5 × sqrt(n), clamped to [21, 5001], rounded to nearest odd
        w = max(21, min(5001, int(math.sqrt(n) * 0.5)))
        if w % 2 == 0:
            w += 1
        self.window_spin.setValue(w)
        self.step_spin.setValue(w)

    # ── Layout ──────────────────────────────────────────────────────────────

    def _setup_parameters(self):
        param_group = QGroupBox(self.tr("Plot Options"))
        param_group.setFlat(True)
        pg_layout = QVBoxLayout(param_group)
        pg_layout.setContentsMargins(12, 12, 0, 12)
        pg_layout.setSpacing(6)

        row = QHBoxLayout()
        row.setSpacing(16)

        row.addWidget(QLabel(self.tr("Window:")))
        self.window_spin = QSpinBox()
        self.window_spin.setRange(21, 10001)
        self.window_spin.setSingleStep(2)
        self.window_spin.setValue(101)
        self.window_spin.setSuffix(self.tr(" bp"))
        self.window_spin.setToolTip(
            self.tr(
                "Sliding window size. Automatically adjusted based on sequence length. "
                "Larger windows produce smoother curves."
            )
        )
        row.addWidget(self.window_spin)

        row.addWidget(QLabel(self.tr("Step:")))
        self.step_spin = QSpinBox()
        self.step_spin.setRange(1, 10001)
        self.step_spin.setValue(101)
        self.step_spin.setSuffix(self.tr(" bp"))
        self.step_spin.setToolTip(
            self.tr(
                "Step size between windows. "
                "Equal to window = non-overlapping; smaller = smoother curve."
            )
        )
        row.addWidget(self.step_spin)

        row.addStretch()
        pg_layout.addLayout(row)

        self._cumulative_cb = QCheckBox(
            self.tr("Cumulative GC Skew (Σ (G−C)/(G+C) — shows oriC/terC boundaries)")
        )
        self._cumulative_cb.setToolTip(
            self.tr(
                "When checked, GC skew values are accumulated (running sum) across the "
                "sequence. The global minimum indicates the replication origin (oriC); "
                "the global maximum indicates the terminus (terC). Uncheck to show "
                "per-window (local) GC skew instead."
            )
        )
        self._cumulative_cb.setVisible(False)
        pg_layout.addWidget(self._cumulative_cb)

        self.content_area.insertWidget(1, param_group)

    def _add_plot_canvas(self):
        # --- View-switching buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        self._btn_gc = QPushButton(self.tr("GC Content"))
        self._btn_gc.setCheckable(True)
        self._btn_gc.setChecked(True)
        self._btn_gc.clicked.connect(lambda: self._switch_view(0))

        self._btn_skew = QPushButton(self.tr("GC Skew"))
        self._btn_skew.setCheckable(True)
        self._btn_skew.clicked.connect(lambda: self._switch_view(1))

        self._btn_cumul = QPushButton(self.tr("Cumulative GC Skew"))
        self._btn_cumul.setCheckable(True)
        self._btn_cumul.clicked.connect(lambda: self._switch_view(2))

        for btn in (self._btn_gc, self._btn_skew, self._btn_cumul):
            btn.setStyleSheet(
                "QPushButton { padding: 4px 12px; border: 1px solid #bbb; border-radius: 3px; background: #eee; }"
                "QPushButton:checked { background: #1976d2; color: white; border-color: #1976d2; }"
            )
        btn_layout.addWidget(self._btn_gc)
        btn_layout.addWidget(self._btn_skew)
        btn_layout.addWidget(self._btn_cumul)
        btn_layout.addStretch()

        # --- QStackedWidget with three pages ---
        self._stack = QStackedWidget()
        self._stack.setMinimumHeight(300)

        self._figs: list[Figure] = []
        self._canvases: list[FigureCanvas] = []
        for _ in range(3):
            fig = Figure(figsize=(10, 3.2))
            canvas = FigureCanvas(fig)
            canvas.setMinimumHeight(280)
            scroll = QScrollArea()
            scroll.setWidgetResizable(False)
            scroll.setWidget(canvas)
            self._stack.addWidget(scroll)
            self._figs.append(fig)
            self._canvases.append(canvas)

        self.content_area.insertLayout(self.content_area.count() - 1, btn_layout)
        self.content_area.insertWidget(self.content_area.count() - 1, self._stack)
        self._draw_placeholder_plot()

    def _switch_view(self, idx: int):
        """Switch the stacked widget to the selected plot view."""
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate((self._btn_gc, self._btn_skew, self._btn_cumul)):
            btn.setChecked(i == idx)

    def _draw_placeholder_plot(self):
        labels = [
            self.tr("GC Content"),
            self.tr("GC Skew"),
            self.tr("Cumulative GC Skew"),
        ]
        for fig, canvas, label in zip(self._figs, self._canvases, labels):
            fig.clear()
            ax = fig.add_subplot(111)
            ax.text(
                0.5,
                0.5,
                self.tr(f"{label} plot will appear here after clicking 'Plot'"),
                ha="center",
                va="center",
                fontsize=12,
                color="#999",
                transform=ax.transAxes,
            )
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
            canvas.draw()

    # ── Core logic ──────────────────────────────────────────────────────────

    def _validate_dna(self, seq):
        """Return True if the sequence is predominantly DNA."""
        clean = "".join(c for c in seq.upper() if c.isalpha())
        if not clean:
            return False
        acgt = sum(1 for c in clean if c in "ACGT")
        return acgt / len(clean) >= 0.6

    def run(self):
        self.status_label.setText("")
        path = self.input_path_edit.text().strip()
        if not path:
            QMessageBox.warning(
                self, self.tr("Input Error"), self.tr("Please select a DNA sequence file.")
            )
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            QMessageBox.warning(self, self.tr("Input Error"), str(exc))
            return
        text = text.strip()

        records = self._parse_fasta(text)
        if not records:
            QMessageBox.warning(
                self,
                self.tr("Input Error"),
                self.tr("No valid FASTA sequences detected."),
            )
            return

        header, seq = records[0]
        clean = "".join(c for c in seq.upper() if c.isalpha())
        if len(clean) < self.window_spin.value():
            QMessageBox.warning(
                self,
                self.tr("Sequence Too Short"),
                self.tr(
                    f"Sequence length ({len(clean)} bp) is shorter than the window "
                    f"size ({self.window_spin.value()} bp). "
                    "Please use a longer sequence or a smaller window."
                ),
            )
            return

        if not self._validate_dna(clean):
            QMessageBox.warning(
                self,
                self.tr("Input Warning"),
                self.tr(
                    "The input does not appear to be a DNA sequence "
                    "(fewer than 60% ACGT bases). "
                    "GC content / GC skew analysis requires a DNA sequence."
                ),
            )
            return

        window = self.window_spin.value()
        step = self.step_spin.value()
        half = window // 2
        n = len(clean)

        # Compute at sampled positions (every `step` bp), then interpolate
        sample_positions = list(range(0, n, step))
        if not sample_positions or sample_positions[-1] != n - 1:
            sample_positions.append(n - 1)

        sample_gc = []
        sample_skew = []
        sample_x = []
        for i in sample_positions:
            start = max(0, i - half)
            end = min(n, i + half + 1)
            segment = clean[start:end]
            g = segment.count("G")
            c = segment.count("C")
            total = g + c + segment.count("A") + segment.count("T")
            w = end - start
            if w < half + 1 or total == 0 or (g + c) == 0:
                continue
            sample_x.append(i)
            sample_gc.append(((g + c) / total) * 100)
            sample_skew.append((g - c) / (g + c) if (g + c) > 0 else 0.0)

        if len(sample_x) < 2:
            QMessageBox.warning(
                self,
                self.tr("Analysis Error"),
                self.tr("Not enough data points. Try a smaller window or step size."),
            )
            return

        sample_x = np.array(sample_x, dtype=float)
        all_x = np.arange(n, dtype=float)
        gc_content = np.interp(all_x, sample_x, sample_gc)
        gc_skew = np.interp(all_x, sample_x, sample_skew)
        cumul_skew = np.cumsum(gc_skew)

        self._draw_gc_content(clean, gc_content, window, header)
        self._draw_gc_skew(clean, gc_skew, window, header)
        self._draw_cumul_skew(clean, cumul_skew, window, header)
        mean_gc = np.nanmean(gc_content)
        self.status_label.setText(self.tr(f"Plotted \u2014 {n:,} bp, mean GC = {mean_gc:.1f}%"))

        if not self._logo_generated:
            self._logo_generated = True

    def _draw_gc_content(self, seq, gc_content, window, header):
        """Draw GC Content on page 0."""
        fig = self._figs[0]
        fig.clear()
        x = np.arange(1, len(seq) + 1)
        ax = fig.add_subplot(111)
        ax.set_facecolor("#f9f9f9")

        ax.plot(x, gc_content, color="#1976d2", linewidth=1.0)
        mean_gc = np.nanmean(gc_content)
        ax.axhline(
            y=mean_gc,
            color="#d32f2f",
            linestyle="--",
            linewidth=1.0,
            label=self.tr(f"Mean GC = {mean_gc:.1f}%"),
        )
        ax.set_ylabel(self.tr("GC Content (%)"), fontsize=12)
        ax.set_title(
            self.tr(f"GC Content — {header} (window={window})"),
            fontsize=13,
            fontweight="bold",
        )
        ax.set_xlim(1, len(seq))
        ax.set_ylim(0, 100)
        ax.legend(loc="upper right", fontsize=9)

        n = len(seq)
        if n >= 10000:
            ax.xaxis.set_major_formatter(
                ticker.FuncFormatter(
                    lambda v, _: f"{v / 1000:.0f} kb" if v >= 1000 else f"{int(v)}"
                )
            )
            ax.set_xlabel(self.tr("Position (kb)"), fontsize=12)
        else:
            ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
            ax.set_xlabel(self.tr("Position (bp)"), fontsize=12)

        fig.tight_layout()
        self._canvases[0].draw()

    def _draw_gc_skew(self, seq, gc_skew, window, header):
        """Draw local GC Skew on page 1."""
        fig = self._figs[1]
        fig.clear()
        x = np.arange(1, len(seq) + 1)
        ax = fig.add_subplot(111)
        ax.set_facecolor("#f9f9f9")

        ax.plot(x, gc_skew, color="#388e3c", linewidth=1.0)
        ax.axhline(y=0, color="#999", linestyle="--", linewidth=0.8)
        ax.fill_between(
            x,
            0,
            gc_skew,
            where=(gc_skew > 0),
            color="#388e3c",
            alpha=0.15,
            label=self.tr("G excess"),
        )
        ax.fill_between(
            x,
            0,
            gc_skew,
            where=(gc_skew < 0),
            color="#d32f2f",
            alpha=0.15,
            label=self.tr("C excess"),
        )
        ax.set_ylabel(self.tr("GC Skew"), fontsize=12)
        ax.set_title(
            self.tr(f"GC Skew = (G−C)/(G+C) — {header}"),
            fontsize=13,
            fontweight="bold",
        )
        ax.set_ylim(-1, 1)

        n = len(seq)
        if n >= 10000:
            ax.xaxis.set_major_formatter(
                ticker.FuncFormatter(
                    lambda v, _: f"{v / 1000:.0f} kb" if v >= 1000 else f"{int(v)}"
                )
            )
            ax.set_xlabel(self.tr("Position (kb)"), fontsize=12)
        else:
            ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
            ax.set_xlabel(self.tr("Position (bp)"), fontsize=12)
        ax.legend(loc="upper right", fontsize=9)

        fig.tight_layout()
        self._canvases[1].draw()

    def _draw_cumul_skew(self, seq, cumul_skew, window, header):
        """Draw Cumulative GC Skew on page 2."""
        fig = self._figs[2]
        fig.clear()
        x = np.arange(1, len(seq) + 1)
        ax = fig.add_subplot(111)
        ax.set_facecolor("#f9f9f9")

        ax.plot(x, cumul_skew, color="#7b1fa2", linewidth=1.2)
        ax.axhline(y=0, color="#999", linestyle="--", linewidth=0.8)
        ax.fill_between(
            x,
            0,
            cumul_skew,
            where=(cumul_skew > 0),
            color="#7b1fa2",
            alpha=0.12,
            label=self.tr("G excess (leading)"),
        )
        ax.fill_between(
            x,
            0,
            cumul_skew,
            where=(cumul_skew < 0),
            color="#e65100",
            alpha=0.12,
            label=self.tr("C excess (lagging)"),
        )
        ax.set_ylabel(self.tr("Cumulative GC Skew"), fontsize=12)
        ax.set_title(
            self.tr(f"Cumulative GC Skew = Σ (G−C)/(G+C) — {header}"),
            fontsize=13,
            fontweight="bold",
        )
        idx_min = np.argmin(cumul_skew)
        idx_max = np.argmax(cumul_skew)
        ax.scatter(
            x[idx_min],
            cumul_skew[idx_min],
            color="#d32f2f",
            s=60,
            zorder=5,
            label=self.tr(f"oriC ≈ {int(x[idx_min])} bp"),
        )
        ax.scatter(
            x[idx_max],
            cumul_skew[idx_max],
            color="#2e7d32",
            s=60,
            zorder=5,
            label=self.tr(f"terC ≈ {int(x[idx_max])} bp"),
        )

        n = len(seq)
        if n >= 10000:
            ax.xaxis.set_major_formatter(
                ticker.FuncFormatter(
                    lambda v, _: f"{v / 1000:.0f} kb" if v >= 1000 else f"{int(v)}"
                )
            )
            ax.set_xlabel(self.tr("Position (kb)"), fontsize=12)
        else:
            ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
            ax.set_xlabel(self.tr("Position (bp)"), fontsize=12)
        ax.legend(loc="upper right", fontsize=9)

        fig.tight_layout()
        self._canvases[2].draw()

    def clear(self):
        self.input_path_edit.clear()
        self._draw_placeholder_plot()
        self._logo_generated = False
        self.status_label.setText(self.tr("Cleared"))

    def export_result(self):
        """Save the currently displayed figure to a file."""
        idx = self._stack.currentIndex()
        fig = self._figs[idx]
        if fig is None:
            QMessageBox.warning(self, self.tr("Export Error"), self.tr("Generate a plot first."))
            return
        from PyQt6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save GC Plot"),
            "gc_plot.png",
            self.tr("PNG Files (*.png);;PDF Files (*.pdf);;SVG Files (*.svg);;All Files (*)"),
        )
        if file_path:
            try:
                fig.savefig(file_path, dpi=300, bbox_inches="tight")
                self.status_label.setText(self.tr("Figure saved"))
            except Exception as e:
                QMessageBox.warning(
                    self, self.tr("Export Error"), self.tr(f"Failed to save figure:\n{str(e)}")
                )

    def show_help(self):
        from PyQt6.QtWidgets import (
            QDialog,
            QLabel,
            QPushButton,
            QScrollArea,
            QVBoxLayout,
        )

        help_text = self.tr("""
<h2>GC Content / GC Skew Plot — Sliding-Window Analysis</h2>

<p><b>What does this tool do?</b><br>
It computes GC content and GC skew across a DNA sequence using a
sliding window, then plots both profiles. GC content reveals base
composition variation; GC skew reveals strand asymmetry caused by
differential mutation rates during replication — a classic method
for locating the origin (<em>oriC</em>) and terminus of replication
in bacterial genomes (Lobry 1996, Grigoriev 1998).</p>

<h3>Quick Start</h3>
<ol>
<li>Select a FASTA file (via <b>Browse</b> or drag-and-drop), or click <b>Example</b> to load the pBR322 plasmid</li>
<li>Adjust <b>Window</b> size for the desired smoothing level</li>
<li>Click <b>Plot</b> — use the three buttons (GC Content / GC Skew / Cumulative GC Skew) above the plot to switch views</li>
</ol>

<h3>Metrics Explained</h3>
<table border='0' cellpadding='4' cellspacing='2'>
<tr><td><b>Metric</b></td><td><b>Formula</b></td><td><b>Range</b></td><td><b>Interpretation</b></td></tr>
<tr><td>GC Content</td><td>(G+C)/(A+T+G+C)</td><td>0–100%</td><td>Overall GC richness; coding regions tend to be GC-rich; intergenic regions often AT-rich</td></tr>
<tr><td>Local GC Skew</td><td>(G−C)/(G+C)</td><td>−1 to +1</td><td>Positive = G excess (leading strand); negative = C excess (lagging strand). Strand-specific mutation and selection biases create the skew</td></tr>
<tr><td>Cumulative GC Skew</td><td>&Sigma; (G−C)/(G+C)</td><td>varies</td><td>Running sum across the genome. The V-shaped curve crosses from negative to positive near oriC. Global minimum &asymp; oriC; global maximum &asymp; terC</td></tr>
</table>

<h3>Sliding Window — How It Works</h3>
<p>A window of <b>W</b> bp slides across the sequence in steps of <b>S</b> bp.
At each position, GC content and GC skew are computed for the bases within
the window centred at that position. Values between sampled positions are
linearly interpolated for a smooth curve.</p>
<ul>
<li>Larger windows (500–1000 bp) smooth out local noise for genome-scale patterns</li>
<li>Smaller windows (20–100 bp) reveal gene-level GC variation</li>
<li>Step = Window gives non-overlapping windows (faster); Step &lt; Window gives
overlapping windows (smoother curves)</li>
</ul>

<h3>Cumulative GC Skew and oriC Detection</h3>
<p>In most bacteria, the leading strand accumulates G over C (positive skew)
while the lagging strand accumulates C over G (negative skew). Because
replication is bidirectional from a single origin, the strand asymmetry
reverses at oriC and terC. When GC skew is cumulatively summed across the
genome, this produces a characteristic V-shaped curve:</p>
<ul>
<li><b>Global minimum</b> (lowest cumulative value) &rarr; putative <em>oriC</em></li>
<li><b>Global maximum</b> (highest cumulative value) &rarr; putative <em>terC</em></li>
<li>The difference between the two extrema reflects the strength of strand bias</li>
</ul>
<p>This method works best on complete or near-complete bacterial chromosomes.
Plasmid and partial sequences may not show a clear pattern.</p>

<h3>Parameter Selection Guide</h3>
<table border='0' cellpadding='4' cellspacing='2'>
<tr><td><b>Sequence type</b></td><td><b>Recommended Window</b></td><td><b>Recommended Step</b></td></tr>
<tr><td>Complete bacterial genome (~1–10 Mb)</td><td>1001–5001 bp</td><td>= Window</td></tr>
<tr><td>Bacterial chromosome segment (~10–500 kb)</td><td>501–1001 bp</td><td>= Window</td></tr>
<tr><td>Plasmid or phage (~1–200 kb)</td><td>51–501 bp</td><td>= Window</td></tr>
<tr><td>Gene or short segment (&lt;5 kb)</td><td>21–101 bp</td><td>≤ Window/2</td></tr>
</table>

<h3>Examples &amp; Use Cases</h3>
<ul>
<li><b>oriC prediction</b> — load a complete bacterial genome, check Cumulative GC Skew,
set Window=1001, and click Plot. The red/green markers show predicted oriC/terC</li>
<li><b>Genome quality check</b> — a noisy or flat cumulative skew curve suggests
assembly errors, mis-assigned contig orientation, or incomplete genome</li>
<li><b>Plasmid analysis</b> — local GC skew can reveal the leading/lagging strand
boundaries even in small replicons</li>
<li><b>Horizontal gene transfer detection</b> — regions with GC content deviating
sharply from the genome mean often indicate recently acquired DNA</li>
</ul>

<h3>Tips</h3>
<ul>
<li>Use the <b>Example</b> button to load the pBR322 plasmid (4,361 bp) — a compact
circular replicon where the leading/lagging strand bias is clearly visible</li>
<li>Use <b>Save Figure</b> to export the current view as PNG/PDF/SVG</li>
<li>For multi-contig assemblies, run the tool on each contig separately</li>
<li>The first FASTA record in the selected file is used if multiple are present</li>
<li>N bases are ignored in GC calculations within each window</li>
</ul>
""")
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("Help - GC Content / GC Skew Plot"))
        dialog.resize(620, 500)
        dialog.setMinimumSize(400, 300)
        layout = QVBoxLayout()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        label = QLabel(help_text)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setMargin(20)
        scroll_area.setWidget(label)
        layout.addWidget(scroll_area)
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)
        dialog.setLayout(layout)
        dialog.exec()

    # ── FASTA parsing ───────────────────────────────────────────────────────

    def _parse_fasta(self, text):
        records = []
        lines = text.strip().split("\n")
        current_header = None
        current_seq = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current_header is not None:
                    seq = "".join(current_seq)
                    if seq:
                        records.append((current_header, seq))
                current_header = line[1:].strip()
                current_seq = []
            else:
                current_seq.append(line)
        if current_header is not None:
            seq = "".join(current_seq)
            if seq:
                records.append((current_header, seq))
        return records
