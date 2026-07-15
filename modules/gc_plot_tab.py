"""GC Content / GC Skew Plot Tab — sliding-window analysis for DNA sequences."""

from PyQt6.QtWidgets import (
    QMessageBox,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QSpinBox,
    QGroupBox,
    QScrollArea,
    QPushButton,
    QWidget,
    QCheckBox,
)
from PyQt6.QtCore import Qt
from utils.common_components import BaseTabWidget
from utils.example_data import load_example_text
import matplotlib

matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import numpy as np
import math
import matplotlib.ticker as ticker


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

        self.input_text.setPlaceholderText(
            self.tr(
                "Paste a DNA sequence in FASTA format or drag-and-drop a file...\n\n"
                "Example:\n>my_sequence\nATGCGATCGATCGTAGCTAGCTAGCTAGC\n"
            )
        )
        self.input_text.setMaximumHeight(100)

        self._setup_parameters()
        self._add_plot_canvas()
        self._setup_drag_drop()
        self.current_figure = None

        # Place Example button horizontally with upload_btn
        self.example_btn = QPushButton(self.tr("Example"))
        self.example_btn.clicked.connect(self._load_example)
        ig_layout = self.input_group.layout()
        ig_layout.removeWidget(self.upload_btn)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.upload_btn, 1)
        btn_row.addWidget(self.example_btn, 1)
        ig_layout.insertLayout(1, btn_row)

        # Keep step default in sync with window changes
        self.window_spin.valueChanged.connect(self._sync_step_to_window)

    def _sync_step_to_window(self, val):
        """When window changes, update step default to match (non-overlapping)."""
        if self.step_spin.value() == self.step_spin.maximum() or self.step_spin.value() <= 1:
            self.step_spin.setValue(val)

    def _load_example(self):
        """Load the bundled E. coli K-12 genome example for GC skew analysis."""
        text = load_example_text("dna", "Escherichia coli_K-12.fasta")
        if not text:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. Please check your installation."),
            )
            return
        self.input_text.setPlainText(text)
        self._auto_adjust_window()
        self.show_status(self.tr("Loaded example data: Escherichia coli_K-12.fasta"))

    def _auto_adjust_window(self):
        """Set window size automatically based on the current input sequence length."""
        text = self.input_text.toPlainText().strip()
        if not text:
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
        pg_layout.addWidget(self._cumulative_cb)

        self.content_area.insertWidget(1, param_group)

    def _add_plot_canvas(self):
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(False)
        self._scroll_area.setMinimumHeight(300)

        self.figure = Figure(figsize=(10, 4.2))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumHeight(300)
        self._scroll_area.setWidget(self.canvas)

        self.toolbar = NavigationToolbar(self.canvas, self)
        self.toolbar.hide()

        plot_layout = QVBoxLayout()
        plot_layout.addWidget(self.toolbar)
        plot_layout.addWidget(self._scroll_area)
        self.content_area.insertLayout(self.content_area.count() - 1, plot_layout)
        self._draw_placeholder_plot()

    def _draw_placeholder_plot(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(
            0.5,
            0.5,
            self.tr("GC content / GC skew plot will appear here after clicking 'Plot'"),
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
        self.canvas.draw()

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
        text = self.input_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(
                self, self.tr("Input Error"), self.tr("Please input a DNA sequence.")
            )
            return

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

        cumulative = self._cumulative_cb.isChecked()
        gc_skew_display = np.cumsum(gc_skew) if cumulative else gc_skew

        self._draw_plot(clean, gc_content, gc_skew_display, window, header, cumulative)
        mean_gc = np.nanmean(gc_content)
        self.status_label.setText(
            self.tr(
                f"Plotted GC content / GC skew (window={window}) — {n} bp, mean GC = {mean_gc:.1f}%"
            )
        )

    def _draw_plot(self, seq, gc_content, gc_skew, window, header, cumulative=False):
        self.figure.clear()
        x = np.arange(1, len(seq) + 1)

        # --- GC Content (top panel) ---
        ax1 = self.figure.add_subplot(211)
        ax1.set_facecolor("#f9f9f9")

        ax1.plot(x, gc_content, color="#1976d2", linewidth=1.0)
        mean_gc = np.nanmean(gc_content)
        ax1.axhline(
            y=mean_gc,
            color="#d32f2f",
            linestyle="--",
            linewidth=1.0,
            label=self.tr(f"Mean GC = {mean_gc:.1f}%"),
        )
        ax1.set_ylabel(self.tr("GC Content (%)"), fontsize=12)
        ax1.set_title(
            self.tr(f"GC Content — {header} (window={window})"),
            fontsize=13,
            fontweight="bold",
        )
        ax1.set_xlim(1, len(seq))
        ax1.set_ylim(0, 100)
        ax1.legend(loc="upper right", fontsize=9)

        # --- GC Skew (bottom panel) ---
        ax2 = self.figure.add_subplot(212, sharex=ax1)
        ax2.set_facecolor("#f9f9f9")

        if cumulative:
            # Cumulative GC skew — oriC detection mode
            ax2.plot(x, gc_skew, color="#7b1fa2", linewidth=1.2)
            ax2.axhline(y=0, color="#999", linestyle="--", linewidth=0.8)
            ax2.fill_between(
                x,
                0,
                gc_skew,
                where=(gc_skew > 0),
                color="#7b1fa2",
                alpha=0.12,
                label=self.tr("G excess (leading)"),
            )
            ax2.fill_between(
                x,
                0,
                gc_skew,
                where=(gc_skew < 0),
                color="#e65100",
                alpha=0.12,
                label=self.tr("C excess (lagging)"),
            )
            ax2.set_ylabel(self.tr("Cumulative GC Skew"), fontsize=12)
            ax2.set_title(
                self.tr(f"Cumulative GC Skew = Σ (G−C)/(G+C) — {header}"),
                fontsize=13,
                fontweight="bold",
            )
            # Mark global min (putative oriC) and max (putative terC)
            idx_min = np.argmin(gc_skew)
            idx_max = np.argmax(gc_skew)
            ax2.scatter(
                x[idx_min],
                gc_skew[idx_min],
                color="#d32f2f",
                s=60,
                zorder=5,
                label=self.tr(f"oriC ≈ {int(x[idx_min])} bp"),
            )
            ax2.scatter(
                x[idx_max],
                gc_skew[idx_max],
                color="#2e7d32",
                s=60,
                zorder=5,
                label=self.tr(f"terC ≈ {int(x[idx_max])} bp"),
            )
        else:
            # Local (per-window) GC skew
            ax2.plot(x, gc_skew, color="#388e3c", linewidth=1.0)
            ax2.axhline(y=0, color="#999", linestyle="--", linewidth=0.8)
            ax2.fill_between(
                x,
                0,
                gc_skew,
                where=(gc_skew > 0),
                color="#388e3c",
                alpha=0.15,
                label=self.tr("G excess"),
            )
            ax2.fill_between(
                x,
                0,
                gc_skew,
                where=(gc_skew < 0),
                color="#d32f2f",
                alpha=0.15,
                label=self.tr("C excess"),
            )
            ax2.set_ylabel(self.tr("GC Skew"), fontsize=12)
            ax2.set_title(
                self.tr(f"GC Skew = (G−C)/(G+C) — {header}"),
                fontsize=13,
                fontweight="bold",
            )
            ax2.set_ylim(-1, 1)

        ax2.set_xlabel(self.tr("Position (bp)"), fontsize=12)
        ax2.legend(loc="upper right", fontsize=9)

        # Clean x-axis: use plain bp or kb formatting, no scientific offset
        n = len(seq)
        if n >= 10000:
            ax2.xaxis.set_major_formatter(
                ticker.FuncFormatter(
                    lambda v, _: f"{v / 1000:.0f} kb" if v >= 1000 else f"{int(v)}"
                )
            )
            ax2.set_xlabel(self.tr("Position (kb)"), fontsize=12)
        else:
            ax2.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
            ax2.set_xlabel(self.tr("Position (bp)"), fontsize=12)
        ax1.tick_params(labelbottom=False)  # top panel shares x-axis, hide its labels

        self.figure.tight_layout()
        self.current_figure = self.figure

        if not self._logo_generated:
            self.toolbar.show()
            self._logo_generated = True

        self.canvas.draw()

    def clear(self):
        self.input_text.clear()
        self._draw_placeholder_plot()
        self.toolbar.hide()
        self._logo_generated = False
        self.current_figure = None
        self.status_label.setText(self.tr("Cleared"))

    def export_result(self):
        if self.current_figure is None:
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
                self.current_figure.savefig(file_path, dpi=300, bbox_inches="tight")
                self.status_label.setText(self.tr(f"Figure saved: {file_path}"))
            except Exception as e:
                QMessageBox.warning(
                    self, self.tr("Export Error"), self.tr(f"Failed to save figure:\n{str(e)}")
                )

    def show_help(self):
        from PyQt6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QLabel,
            QPushButton,
            QScrollArea,
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
<li>Paste a DNA sequence or click <b>Example</b> to load the E.&nbsp;coli K-12 genome</li>
<li>Adjust <b>Window</b> size for the desired smoothing level</li>
<li>Check <b>Cumulative GC Skew</b> if you want to locate oriC/terC</li>
<li>Click <b>Plot</b> — use the toolbar to zoom, pan, or export</li>
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
<li>Use the <b>Example</b> button to load the E.&nbsp;coli K-12 genome (~4.6 Mb) —
a well-characterised chromosome where oriC (~3.92 Mb) is reliably detected</li>
<li>The <b>Matplotlib toolbar</b> above the plot provides zoom, pan, home, and save
(PNG/PDF/SVG) — no separate Save button needed</li>
<li>For multi-contig assemblies, run the tool on each contig separately</li>
<li>Paste FASTA or raw sequence; the first record is used if multiple are present</li>
<li>N bases are ignored in GC calculations within each window</li>
</ul>
""")
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("Help - GC Content / GC Skew Plot"))
        dialog.setFixedSize(820, 680)
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

    # ── Drag & drop + FASTA parsing ─────────────────────────────────────────

    def _setup_drag_drop(self):
        self.input_text.setAcceptDrops(True)

        def drag_enter(e):
            md = e.mimeData()
            if md.hasUrls():
                urls = md.urls()
                if urls and urls[0].toLocalFile():
                    e.acceptProposedAction()
                    return
            e.ignore()

        def drop(e):
            urls = e.mimeData().urls()
            if urls:
                file_path = urls[0].toLocalFile()
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    self.input_text.setPlainText(content)
                    self._auto_adjust_window()
                except Exception as ex:
                    QMessageBox.warning(self, self.tr("File Read Error"), str(ex))

        self.input_text.dragEnterEvent = drag_enter
        self.input_text.dropEvent = drop

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
