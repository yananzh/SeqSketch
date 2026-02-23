import os
import tempfile

import matplotlib

matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar

from PyQt6.QtWidgets import (
    QMessageBox,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QTextEdit,
    QCheckBox,
    QSpinBox,
    QFrame,
    QDialog,
    QTextBrowser,
    QScrollArea,
    QWidget,
)
from PyQt6.QtCore import Qt

from utils.common_components import BaseTabWidget

# All pyMSAviz color schemes
_COLOR_SCHEMES = [
    "Clustal",
    "Zappo",
    "Taylor",
    "Flower",
    "Blossom",
    "Sunset",
    "Ocean",
    "Hydrophobicity",
    "HelixPropensity",
    "StrandPropensity",
    "TurnPropensity",
    "BuriedIndex",
    "Nucleotide",
    "Purine/Pyrimidine",
    "Identity",
    "None",
]


class MSAVisualizationTab(BaseTabWidget):
    """MSA Visualization tab — renders aligned FASTA sequences with pyMSAviz."""

    def __init__(self, parent=None):
        super().__init__("MSA Visualization", "sequence")
        self._current_figure = None

        # Rewire base widgets
        self.run_btn.setText("Visualize")
        self.export_btn.setText("Save Figure")
        self.copy_btn.hide()
        self.output_text.hide()
        self.output_label.hide()

        # Placeholder
        self.input_label.setText("Input Alignment (FASTA):")
        self.input_text.setPlaceholderText(
            "Paste an aligned FASTA file (all sequences must be the same length), "
            "or drag-and-drop a file…\n\n"
            "Example:\n"
            ">seq1\nATGCATGCATGC\n"
            ">seq2\nATGCATGCATGC\n"
            ">seq3\nATGCATGCATGT"
        )
        self.input_text.setMaximumHeight(150)
        self.upload_btn.setText("Upload FASTA File")
        self.input_hint.setStyleSheet("color: #888;")

        self._setup_parameters()
        self._add_canvas()
        self._setup_drag_drop()

    # ---------------------------------------------------------------- layout

    def _setup_parameters(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        self.content_area.insertWidget(1, line)

        # Row 1 — color scheme + wrap length
        row1 = QHBoxLayout()
        row1.setSpacing(20)

        row1.addWidget(QLabel("Color Scheme:"))
        self.color_combo = QComboBox()
        self.color_combo.addItems(_COLOR_SCHEMES)
        self.color_combo.setCurrentText("Clustal")
        self.color_combo.setMinimumWidth(200)
        self.color_combo.setToolTip(
            "Residue coloring scheme.\n"
            "DNA: Nucleotide or Purine/Pyrimidine recommended.\n"
            "Protein: Clustal, Taylor, Zappo, etc."
        )
        row1.addWidget(self.color_combo)

        row1.addSpacing(20)
        row1.addWidget(QLabel("Wrap Length:"))
        self.wrap_spin = QSpinBox()
        self.wrap_spin.setRange(0, 9999)
        self.wrap_spin.setValue(80)
        self.wrap_spin.setFixedWidth(90)
        self.wrap_spin.setSpecialValueText("No wrap")  # 0 → None
        self.wrap_spin.setToolTip(
            "Number of residues per row before wrapping.\n"
            "Set to 0 for a single continuous row."
        )
        row1.addWidget(self.wrap_spin)
        row1.addStretch()

        # Row 2 — display toggles
        row2 = QHBoxLayout()
        row2.setSpacing(24)

        self.chk_seq_char = QCheckBox("Sequence Characters")
        self.chk_grid = QCheckBox("Grid")
        self.chk_count = QCheckBox("Position Count")
        self.chk_consensus = QCheckBox("Consensus")
        self.chk_sort = QCheckBox("Sort by Similarity")

        self.chk_seq_char.setChecked(True)
        self.chk_consensus.setChecked(False)

        for chk in (
            self.chk_seq_char,
            self.chk_grid,
            self.chk_count,
            self.chk_consensus,
            self.chk_sort,
        ):
            row2.addWidget(chk)
        row2.addStretch()

        # Row 3 — highlight identity threshold + DPI
        row3 = QHBoxLayout()
        row3.setSpacing(20)

        self.chk_highlight = QCheckBox("Highlight Conserved Columns (identity ≥")
        self.chk_highlight.setChecked(True)
        self.ident_spin = QSpinBox()
        self.ident_spin.setRange(0, 100)
        self.ident_spin.setValue(70)
        self.ident_spin.setSuffix("%)")
        self.ident_spin.setFixedWidth(100)
        self.ident_spin.setToolTip(
            "Columns where ≥ this % of residues are identical will be highlighted."
        )

        row3.addWidget(self.chk_highlight)
        row3.addWidget(self.ident_spin)
        row3.addSpacing(30)
        row3.addWidget(QLabel("DPI:"))
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 600)
        self.dpi_spin.setValue(300)
        self.dpi_spin.setFixedWidth(90)
        self.dpi_spin.setToolTip(
            "Resolution used when rendering and exporting the figure."
        )
        row3.addWidget(self.dpi_spin)
        row3.addStretch()

        self.content_area.insertLayout(2, row1)
        self.content_area.insertLayout(3, row2)
        self.content_area.insertLayout(4, row3)

    def _add_canvas(self):
        """Insert a scrollable matplotlib canvas below the parameters."""
        self._canvas_container = QScrollArea()
        # Do NOT use setWidgetResizable(True) — that squashes the figure to
        # fit the viewport, making long alignments blurry.
        self._canvas_container.setWidgetResizable(False)
        self._canvas_container.setMinimumHeight(320)

        self._canvas_inner = QWidget()
        self._canvas_vbox = QVBoxLayout(self._canvas_inner)
        self._canvas_vbox.setContentsMargins(0, 0, 0, 0)
        self._canvas_vbox.setSpacing(0)

        self._canvas_container.setWidget(self._canvas_inner)

        # Toolbar placeholder — populated after first render
        self._toolbar_placeholder = QHBoxLayout()
        self._canvas_vbox.addLayout(self._toolbar_placeholder)

        self.canvas = None
        self.nav_bar = None

        insert_at = max(0, self.content_area.count() - 1)
        self.content_area.insertWidget(insert_at, self._canvas_container)

    # --------------------------------------------------------------- drag-drop

    def _setup_drag_drop(self):
        w = self.input_text
        w.setAcceptDrops(True)

        def drag_enter(e):
            if e.mimeData().hasUrls():
                e.acceptProposedAction()
            else:
                e.ignore()

        def drop(e):
            urls = e.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        w.setPlainText(f.read())
                    self.input_hint.setText(f"Loaded: {path}")
                    e.acceptProposedAction()
                except Exception as ex:
                    QMessageBox.warning(self, "File Read Error", str(ex))
                    e.ignore()

        w.dragEnterEvent = drag_enter
        w.dropEvent = drop

    # ---------------------------------------------------------------- actions

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open aligned FASTA file",
            "",
            "FASTA files (*.fasta *.fa *.fna *.faa *.aln *.txt);;All Files (*)",
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.input_text.setPlainText(f.read())
                self.input_hint.setText(f"Loaded: {path}")
            except Exception as e:
                QMessageBox.warning(self, "File Read Error", str(e))

    def export_result(self):
        if self._current_figure is None:
            QMessageBox.information(
                self, "Nothing to Export", "Run the visualization first."
            )
            return

        _EXT_MAP = {
            "PNG (*.png)": ".png",
            "SVG (*.svg)": ".svg",
            "PDF (*.pdf)": ".pdf",
            "TIFF (*.tiff)": ".tiff",
        }
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Figure",
            "msa_visualization.png",
            ";;".join(_EXT_MAP.keys()),
        )
        if not path:
            return

        # Ensure the chosen extension is present
        ext = _EXT_MAP.get(selected_filter, "")
        if ext and not path.lower().endswith(ext):
            path += ext

        try:
            fmt = os.path.splitext(path)[1].lstrip(".").lower()
            if fmt == "tiff":
                fmt = "tiff"
            self._current_figure.savefig(
                path,
                format=fmt,
                dpi=self.dpi_spin.value(),
            )
            self.status_label.setText(f"Saved: {path}")
        except Exception as e:
            QMessageBox.warning(self, "Export Error", str(e))

    def clear(self):
        self.input_text.clear()
        self.input_hint.setText("")
        self._clear_canvas()
        self.status_label.setText("Ready")

    def _clear_canvas(self):
        if self.canvas is not None:
            self._canvas_vbox.removeWidget(self.canvas)
            self.canvas.setParent(None)
            self.canvas = None
        if self.nav_bar is not None:
            while self._toolbar_placeholder.count():
                item = self._toolbar_placeholder.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
            self.nav_bar = None
        self._current_figure = None
        # Reset inner container so scroll area shows nothing
        self._canvas_inner.setFixedSize(0, 0)

    # ------------------------------------------------------------------ run

    def run(self):
        raw = self.input_text.toPlainText().strip()
        if not raw:
            self.status_label.setText("Please enter or upload an aligned FASTA file.")
            return

        # Validate: at least 2 sequences
        n_seq = raw.count(">")
        if n_seq < 2:
            QMessageBox.warning(
                self, "Input Error", "At least 2 sequences are required."
            )
            return

        # Write to temp file (MsaViz requires a file path)
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".fa", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(raw)
                tmp_path = tmp.name

            from pymsaviz import MsaViz

            color = self.color_combo.currentText()
            color_arg = None if color == "None" else color
            wrap = self.wrap_spin.value() or None  # 0 → None

            mv = MsaViz(
                tmp_path,
                format="fasta",
                color_scheme=color_arg,
                wrap_length=wrap,
                show_label=True,
                show_seq_char=self.chk_seq_char.isChecked(),
                show_grid=self.chk_grid.isChecked(),
                show_count=self.chk_count.isChecked(),
                show_consensus=self.chk_consensus.isChecked(),
                sort=self.chk_sort.isChecked(),
            )

            if self.chk_highlight.isChecked():
                mv.set_highlight_pos_by_ident_thr(
                    min_thr=self.ident_spin.value(),
                    max_thr=100,
                )

            fig = mv.plotfig(dpi=self.dpi_spin.value())

            self._clear_canvas()
            self._current_figure = fig
            self.canvas = FigureCanvas(fig)

            # Size the canvas to the figure's natural pixel dimensions so
            # the scroll area can scroll to it rather than compressing it.
            w_px = int(fig.get_figwidth() * fig.dpi)
            h_px = int(fig.get_figheight() * fig.dpi)
            self.canvas.setFixedSize(w_px, h_px)

            self.nav_bar = NavigationToolbar(self.canvas, self._canvas_inner)

            # Resize the inner container to match canvas + toolbar
            toolbar_h = self.nav_bar.sizeHint().height()
            self._canvas_inner.setFixedSize(w_px, h_px + toolbar_h + 4)

            self._toolbar_placeholder.addWidget(self.nav_bar)
            self._canvas_vbox.addWidget(self.canvas)

            aln_len = mv.alignment_length
            self.status_label.setText(
                f"Rendered — {n_seq} sequences | alignment length: {aln_len} | "
                f"color: {color}"
            )

        except Exception as e:
            QMessageBox.critical(self, "Visualization Error", str(e))
            self.status_label.setText("Visualization failed.")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    # ------------------------------------------------------------------ help

    def show_help(self):
        html = """
<h3>MSA Visualization</h3>
<p>Renders a colored multiple sequence alignment figure using
<b>pyMSAviz</b> — a Python wrapper around Matplotlib.</p>

<h4>Input</h4>
<ul>
  <li>Paste a <b>pre-aligned</b> FASTA file (all sequences must be the same length,
      with gap characters <code>-</code>), or click <b>Upload FASTA File</b> /
      drag-and-drop.</li>
  <li>At least <b>2 sequences</b> are required.</li>
  <li>Use the <b>Multiple Sequence Alignment (Muscle5)</b> tab to generate the
      alignment first, then paste the output here.</li>
</ul>

<h4>Color Scheme</h4>
<ul>
  <li><b>Clustal</b> — classic Clustal-X colors (protein default).</li>
  <li><b>Nucleotide</b> / <b>Purine/Pyrimidine</b> — recommended for DNA.</li>
  <li><b>Taylor, Zappo, Flower, …</b> — alternative protein color schemes.</li>
  <li><b>Identity</b> — colors by residue conservation level.</li>
  <li><b>None</b> — plain gray residues.</li>
</ul>

<h4>Display Options</h4>
<ul>
  <li><b>Sequence Characters</b> — show/hide residue letters inside each cell.</li>
  <li><b>Grid</b> — draw cell borders between residues.</li>
  <li><b>Position Count</b> — show position numbers along the x-axis.</li>
  <li><b>Consensus</b> — draw a consensus sequence bar below the alignment.</li>
  <li><b>Sort by Similarity</b> — reorder sequences by similarity to the first.</li>
</ul>

<h4>Highlight Conserved Columns</h4>
<p>Columns where the fraction of identical residues meets the identity threshold
are highlighted with a light blue background, making conserved regions easy to spot.</p>

<h4>Wrap Length</h4>
<p>Maximum number of residue columns per row.
Set to <b>0</b> for a single, continuous (unwrapped) row.</p>

<h4>DPI</h4>
<p>Rendering and export resolution in dots-per-inch. Higher values produce
sharper figures but take longer to render.</p>

<h4>Export</h4>
<p>Click <b>Save Figure</b> to export the current visualization as
PNG, SVG, PDF, or TIFF. Use the toolbar above the figure to zoom,
pan, and interactively explore the alignment.</p>
"""
        dlg = QDialog(self)
        dlg.setWindowTitle("Help – MSA Visualization")
        dlg.setMinimumWidth(660)
        dlg.setMinimumHeight(520)
        layout = QVBoxLayout()
        browser = QTextBrowser()
        browser.setHtml(html)
        layout.addWidget(browser)
        btn_row = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        dlg.setLayout(layout)
        dlg.exec()
