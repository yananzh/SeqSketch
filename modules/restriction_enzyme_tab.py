"""Restriction Enzyme Analysis Tab — find and visualise restriction sites."""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QCheckBox, QSpinBox, QMessageBox, QPushButton, QFileDialog,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from utils.common_components import BaseTabWidget
from utils.example_data import load_example_text


class _AnalysisWorker(QObject):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, seq: str, enzyme_names: List[str], linear: bool = True):
        super().__init__()
        self._seq = seq
        self._enzyme_names = enzyme_names
        self._linear = linear

    def run(self):
        try:
            from Bio.Restriction import RestrictionBatch, CommOnly, AllEnzymes
            from Bio.Seq import Seq
            all_enz = {e.__name__: e for e in AllEnzymes}
            batch_enzymes = []
            name_to_obj: Dict[str, object] = {}
            for name in self._enzyme_names:
                enz = all_enz.get(name)
                if enz is not None:
                    batch_enzymes.append(enz)
                    name_to_obj[name] = enz
            if not batch_enzymes:
                self.finished.emit([])
                return
            rb = RestrictionBatch(batch_enzymes)
            ana = rb.search(Seq(self._seq), linear=self._linear)

            results = []
            seq_len = len(self._seq)
            for enz_name in self._enzyme_names:
                enz_obj = name_to_obj.get(enz_name)
                if enz_obj is None:
                    continue
                positions = sorted(ana.get(enz_obj, []))
                site = str(enz_obj.site) if enz_obj.site else ""
                if positions:
                    cuts = [0] + positions + [seq_len] if self._linear else positions + [positions[0] + seq_len]
                    fragments = [cuts[i + 1] - cuts[i] for i in range(len(cuts) - 1)]
                else:
                    fragments = [seq_len] if self._linear else [seq_len]
                results.append({
                    "enzyme": enz_name,
                    "site": site,
                    "positions": positions,
                    "cuts": len(positions),
                    "fragments": fragments,
                })
            self.finished.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))


class RestrictionEnzymeTab(BaseTabWidget):
    """Find restriction enzyme cut sites in a DNA sequence."""

    def __init__(self, parent=None):
        super().__init__("Restriction Enzyme Analysis", "sequence")
        self._results: List[dict] = []
        self._thread: Optional[QThread] = None
        self._worker: Optional[_AnalysisWorker] = None
        self._setup_enzyme_ui()
        self._setup_results_area()
        self.input_text.setPlaceholderText(
            self.tr(
                "Paste DNA sequence in FASTA format or raw sequence...\n"
                "Example:\n"
                ">plasmid\n"
                "ATGCGATCGATCGAAGCTTCGATCG..."
            )
        )
        self.output_text.setPlaceholderText(
            self.tr("Restriction enzyme results will appear here...")
        )
        self.input_text.setMinimumHeight(90)
        self.output_text.setMinimumHeight(80)

        # Hide copy & export buttons from output QGroupBox
        if hasattr(self, "copy_btn"):
            self.copy_btn.hide()
        if hasattr(self, "export_btn"):
            self.export_btn.hide()
        # Add Export Excel to status row after Run
        self.export_xlsx_btn = QPushButton(self.tr("Export Excel"))
        self.export_xlsx_btn.setFixedWidth(110)
        self.export_xlsx_btn.clicked.connect(self._export_excel)
        _idx = self.status_layout.indexOf(self.run_btn)
        self.status_layout.insertWidget(_idx + 1, self.export_xlsx_btn)
        # Move Upload File button down slightly
        self.upload_btn.setStyleSheet("margin-top: 4px;")

        # Place Example button horizontally with upload_btn
        self.example_btn = QPushButton(self.tr("Example"))
        self.example_btn.clicked.connect(self._load_example)
        ig_layout = self.input_group.layout()
        ig_layout.removeWidget(self.upload_btn)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.upload_btn, 1)
        btn_row.addWidget(self.example_btn, 1)
        ig_layout.insertLayout(1, btn_row)

    def _load_example(self):
        """Load the bundled pBR322 plasmid example for restriction analysis."""
        text = load_example_text("dna", "pBR322.fasta")
        if not text:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("示例数据加载失败，请检查安装是否完整。"),
            )
            return
        self.input_text.setPlainText(text)
        self.show_status(self.tr("已载入示例数据: pBR322.fasta"))

    def _setup_enzyme_ui(self):
        """Enzyme selection controls between input and output."""
        params = QHBoxLayout()

        params.addWidget(QLabel(self.tr("Enzyme Set:")))
        self._enzyme_set_combo = QComboBox()
        self._enzyme_set_combo.addItems([
            self.tr("Common (commercially available)"),
            self.tr("All REBASE enzymes"),
        ])
        self._enzyme_set_combo.setMinimumWidth(220)
        params.addWidget(self._enzyme_set_combo)
        params.addSpacing(16)

        params.addWidget(QLabel(self.tr("Min cuts:")))
        self._min_cuts_spin = QSpinBox()
        self._min_cuts_spin.setRange(0, 99)
        self._min_cuts_spin.setValue(1)
        self._min_cuts_spin.setToolTip(self.tr("Only show enzymes that cut at least this many times"))
        params.addWidget(self._min_cuts_spin)
        params.addSpacing(8)

        params.addWidget(QLabel(self.tr("Max cuts:")))
        self._max_cuts_spin = QSpinBox()
        self._max_cuts_spin.setRange(0, 999)
        self._max_cuts_spin.setValue(50)
        self._max_cuts_spin.setToolTip(self.tr("Only show enzymes that cut at most this many times"))
        params.addWidget(self._max_cuts_spin)
        params.addSpacing(8)

        self._linear_check = QCheckBox(self.tr("Linear DNA"))
        self._linear_check.setChecked(True)
        self._linear_check.setToolTip(
            self.tr("Uncheck for circular DNA (plasmid)")
        )
        params.addWidget(self._linear_check)
        params.addStretch()

        self.add_content_layout(params)

    def _setup_results_area(self):
        """Linear restriction map below the output area."""
        grp = QGroupBox(self.tr("Restriction Map"))
        grp.setFlat(True)
        gl = QVBoxLayout(grp)
        gl.setContentsMargins(0, 16, 0, 4)
        gl.setSpacing(2)

        self._map_fig = Figure(figsize=(8, 3), dpi=100)
        self._map_canvas = FigureCanvas(self._map_fig)
        self._map_canvas.setMinimumHeight(180)
        self._map_toolbar = NavigationToolbar(self._map_canvas, grp)
        gl.addWidget(self._map_toolbar)
        gl.addWidget(self._map_canvas)

        self.add_content_widget(grp)

    # ── Run ────────────────────────────────────────────────────────────

    def run(self):
        raw = self.input_text.toPlainText().strip()
        if not raw:
            self.status_label.setText(self.tr("Please enter a DNA sequence."))
            return

        # Parse FASTA
        seq = raw
        if ">" in seq:
            lines = seq.split("\n")
            seq_parts = []
            for line in lines:
                line = line.strip()
                if line.startswith(">"):
                    continue
                if line:
                    seq_parts.append(line)
            seq = "".join(seq_parts)

        seq = seq.replace("\n", "").replace(" ", "").upper().replace("U", "T")
        if not seq:
            self.status_label.setText(self.tr("No valid sequence found."))
            return
        if not re.fullmatch(r"[ACGTN]+", seq):
            self.status_label.setText(
                self.tr("Invalid characters. Only A/T/G/C/N allowed.")
            )
            return

        # Build enzyme list
        use_common = self._enzyme_set_combo.currentIndex() == 0
        try:
            from Bio.Restriction import CommOnly, AllEnzymes
            enzyme_names = (
                [e.__name__ for e in CommOnly] if use_common
                else [e.__name__ for e in AllEnzymes]
            )
        except ImportError:
            QMessageBox.critical(
                self, self.tr("Missing Dependency"),
                self.tr("BioPython is required for restriction enzyme analysis."),
            )
            return

        self.status_label.setText(self.tr("Analysing..."))

        self._thread = QThread(self)
        self._worker = _AnalysisWorker(seq, enzyme_names, self._linear_check.isChecked())
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_results)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_results(self, results: list):
        min_cuts = self._min_cuts_spin.value()
        max_cuts = self._max_cuts_spin.value()
        results = [r for r in results if min_cuts <= r["cuts"] <= max_cuts]
        results.sort(key=lambda r: r["cuts"])
        self._results = results

        seq_len = len(self._worker._seq) if self._worker else 0
        self._draw_map(results, seq_len)

        n_total = sum(1 for r in results for _ in r["positions"])
        if min_cuts == 0 and max_cuts == 0:
            self.status_label.setText(
                self.tr(f"Found {len(results)} enzymes with no cut sites")
            )
        else:
            self.status_label.setText(
                self.tr(f"Found {len(results)} enzymes, {n_total} cut sites  "
                        f"(cuts: {min_cuts}–{max_cuts})")
            )

        # Populate output_text for export
        out_lines = []
        for r in results:
            out_lines.append(
                f"{r['enzyme']}  {r['site']}  cuts={r['cuts']}  "
                f"positions={','.join(str(p) for p in r['positions'])}  "
                f"fragments={','.join(str(f) for f in r['fragments'])}"
            )
        self.output_text.setPlainText("\n".join(out_lines))

    def _on_error(self, msg: str):
        self.status_label.setText(self.tr(f"Error: {msg[:100]}"))
        QMessageBox.critical(
            self, self.tr("Analysis Error"), msg,
        )

    # ── Linear map ─────────────────────────────────────────────────────

    def _draw_map(self, results, seq_len):
        self._map_fig.clear()
        if seq_len <= 0:
            self._map_canvas.draw_idle()
            return

        ax = self._map_fig.add_subplot(111)
        ax.set_facecolor("#fafafa")

        # Sequence backbone
        ax.plot([0, seq_len], [0, 0], color="#333", linewidth=2.5, zorder=0)

        # Collect cut positions from enzymes that actually cut
        cut_map: Dict[int, List[str]] = {}
        for r in results:
            for p in r["positions"]:
                cut_map.setdefault(p, []).append(r["enzyme"])

        max_enzymes = max(len(v) for v in cut_map.values()) if cut_map else 1

        for pos, enzymes in cut_map.items():
            count = len(enzymes)
            alpha = 0.35 + 0.65 * (count / max_enzymes)
            ax.plot([pos, pos], [-0.35, 0.35], color="#d32f2f",
                    linewidth=1.5, alpha=alpha, zorder=1)

        # Tick labels
        step = max(1, seq_len // 10)
        tick_positions = list(range(0, seq_len + 1, step))
        if tick_positions[-1] != seq_len:
            tick_positions.append(seq_len)
        ax.set_xticks(tick_positions)
        ax.set_xticklabels([str(p) for p in tick_positions], fontsize=7)
        ax.set_xlim(-seq_len * 0.025, seq_len * 1.025)
        ax.set_ylim(-0.5, 0.55)
        ax.set_yticks([])
        ax.set_xlabel(self.tr("Position (bp)"), fontsize=8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)

        self._map_fig.tight_layout(pad=0.5)
        self._map_canvas.draw_idle()

    # ── Export ──────────────────────────────────────────────────────────

    def _export_excel(self):
        """Export enzyme results as an Excel (.xlsx) file."""
        if not self._results:
            QMessageBox.information(self, self.tr("No Data"), self.tr("Run analysis first."))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Export Restriction Analysis"),
            "restriction_enzymes.xlsx",
            self.tr("Excel Files (*.xlsx);;CSV Files (*.csv);;Text Files (*.txt)"),
        )
        if not path:
            return
        try:
            if path.endswith(".xlsx"):
                # openpyxl for Excel
                import openpyxl
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Restriction Enzymes"
                ws.append(["Enzyme", "Recognition Site", "Cuts", "Positions", "Fragments", "Fragment Sizes (bp)"])
                for r in self._results:
                    ws.append([
                        r["enzyme"], r["site"], r["cuts"],
                        ", ".join(str(p) for p in r["positions"]),
                        len(r["fragments"]),
                        ", ".join(str(f) for f in r["fragments"]),
                    ])
                wb.save(path)
            else:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write("\n".join(
                        f"{r['enzyme']}\t{r['site']}\t{r['cuts']}\t"
                        f"{','.join(str(p) for p in r['positions'])}\t"
                        f"{len(r['fragments'])}\t"
                        f"{','.join(str(f) for f in r['fragments'])}"
                        for r in self._results
                    ))
            self.status_label.setText(self.tr(f"Exported {len(self._results)} enzymes to {path}"))
        except Exception as e:
            QMessageBox.critical(self, self.tr("Export Error"), str(e))

    # ── Help ───────────────────────────────────────────────────────────

    def show_help(self):
        help_text = self.tr(
            "<h2>Restriction Enzyme Analysis &mdash; Find Cut Sites</h2>"

            "<p><b>What does this tool do?</b><br>"
            "It searches a DNA sequence for restriction enzyme recognition sites "
            "and reports cut positions and predicted fragment sizes. Supports both "
            "linear and circular DNA, with a visual restriction map.</p>"

            "<h3>Quick Start</h3>"
            "<ol>"
            "<li>Paste your DNA sequence or drag-and-drop a FASTA file</li>"
            "<li>Choose <b>Common</b> (commercial enzymes) or <b>All REBASE</b></li>"
            "<li>Set min/max cuts to filter results (e.g. 1&ndash;3 for rare cutters)</li>"
            "<li>Toggle <b>Linear</b> vs circular DNA</li>"
            "<li>Click <b>Run</b></li>"
            "</ol>"

            "<h3>Results Table</h3>"
            "<ul>"
            "<li><b>Enzyme</b> &mdash; standard REBASE name</li>"
            "<li><b>Recognition Site</b> &mdash; the DNA sequence the enzyme recognises</li>"
            "<li><b>Cuts</b> &mdash; number of cut sites in the sequence</li>"
            "<li><b>Positions</b> &mdash; 1-based cut positions</li>"
            "<li><b>Fragment Sizes</b> &mdash; predicted band sizes after digestion (bp)</li>"
            "</ul>"

            "<h3>Tips</h3>"
            "<ul>"
            "<li>Use <b>Common</b> mode for routine cloning &mdash; it is much faster</li>"
            "<li>Set max cuts to 3&ndash;5 to find unique or rare cutters for cloning</li>"
            "<li>For plasmid maps, uncheck <b>Linear DNA</b> to treat the sequence as circular</li>"
            "<li>Select rows in the table and use <b>Copy to Clipboard</b> to copy specific enzymes</li>"
            "</ul>"
        )
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
        )
        from PyQt6.QtCore import Qt as QtCore

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("Help - Restriction Enzyme Analysis"))
        dlg.setFixedSize(800, 600)
        layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(QtCore.ScrollBarPolicy.ScrollBarAsNeeded)
        label = QLabel(help_text)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setAlignment(QtCore.AlignmentFlag.AlignTop | QtCore.AlignmentFlag.AlignLeft)
        label.setMargin(20)
        scroll.setWidget(label)
        layout.addWidget(scroll)
        ok = QPushButton("OK")
        ok.clicked.connect(dlg.accept)
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_box.addWidget(ok)
        layout.addLayout(btn_box)
        dlg.setLayout(layout)
        dlg.exec()
