"""
Primer Pair Analyzer (PyQt6 + primer3-py)
Check properties of user-specified primer pairs.
"""

import sys
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.common_components import apply_sequence_editor_style
from utils.example_data import load_example_text

try:
    import primer3

    _HAS_PRIMER3 = True
except ImportError:
    _HAS_PRIMER3 = False


def _gc_percent(seq: str) -> float:
    if not seq:
        return 0.0
    seq = seq.upper()
    gc = seq.count("G") + seq.count("C")
    return gc / len(seq) * 100.0


class PrimerAnalysisTab(QWidget):
    def __init__(self):
        super().__init__()
        self._last_results: str = ""
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ── 1. Primer Input ────────────────────────────────────────
        input_group = QGroupBox(self.tr("1. Primer Sequences"))
        input_v = QVBoxLayout(input_group)

        fwd_row = QHBoxLayout()
        fwd_label = QLabel(self.tr("Forward (5'→3'):"))
        fwd_label.setFixedWidth(130)
        fwd_row.addWidget(fwd_label)
        self.fwd_edit = QLineEdit()
        self.fwd_edit.setPlaceholderText(self.tr("e.g. ATCGATCGATCGATCGATCG"))
        self.fwd_edit.setMinimumWidth(240)
        self.fwd_len_label = QLabel("0 nt")
        fwd_row.addWidget(self.fwd_edit, 1)
        fwd_row.addWidget(self.fwd_len_label)
        input_v.addLayout(fwd_row)

        rev_row = QHBoxLayout()
        rev_label = QLabel(self.tr("Reverse (5'→3'):"))
        rev_label.setFixedWidth(130)
        rev_row.addWidget(rev_label)
        self.rev_edit = QLineEdit()
        self.rev_edit.setPlaceholderText(self.tr("e.g. GCTAGCTAGCTAGCTAGCTA"))
        self.rev_edit.setMinimumWidth(240)
        self.rev_len_label = QLabel("0 nt")
        rev_row.addWidget(self.rev_edit, 1)
        rev_row.addWidget(self.rev_len_label)
        input_v.addLayout(rev_row)

        root.addWidget(input_group)

        # ── 2. Template (optional) ──────────────────────────────────
        template_group = QGroupBox(self.tr("2. Template Sequence (optional)"))
        template_v = QVBoxLayout(template_group)
        self.template_edit = QTextEdit()
        apply_sequence_editor_style(self.template_edit)
        self.template_edit.setPlaceholderText(
            self.tr("Paste template to check binding positions and product size...")
        )
        self.template_edit.setMinimumHeight(60)
        self.template_edit.setMaximumHeight(120)
        template_v.addWidget(self.template_edit)
        root.addWidget(template_group)

        # ── 3. Salt Conditions ──────────────────────────────────────
        salt_group = QGroupBox(self.tr("3. Salt Conditions"))
        salt_row = QHBoxLayout(salt_group)
        salt_row.addWidget(QLabel(self.tr("Salt (mM):")))
        self.mv_spin = QDoubleSpinBox()
        self.mv_spin.setRange(10, 200)
        self.mv_spin.setDecimals(0)
        self.mv_spin.setSingleStep(1)
        self.mv_spin.setValue(50)
        self.mv_spin.setFixedWidth(104)
        self.mv_spin.setToolTip(self.tr("Monovalent salt (Na⁺/K⁺) concentration"))
        salt_row.addWidget(self.mv_spin)

        salt_row.addSpacing(16)
        salt_row.addWidget(QLabel(self.tr("Mg²⁺ (mM):")))
        self.dv_spin = QDoubleSpinBox()
        self.dv_spin.setRange(1, 10)
        self.dv_spin.setDecimals(0)
        self.dv_spin.setSingleStep(1)
        self.dv_spin.setValue(3)
        self.dv_spin.setFixedWidth(104)
        self.dv_spin.setToolTip(self.tr("Divalent salt (Mg²⁺) concentration"))
        salt_row.addWidget(self.dv_spin)
        salt_row.addStretch()
        root.addWidget(salt_group)

        # ── 4. Results ──────────────────────────────────────────────
        results_group = QGroupBox(self.tr("4. Analysis Results"))
        results_v = QVBoxLayout(results_group)
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setPlaceholderText(
            self.tr("Enter forward and reverse primer sequences, then click Run.")
        )
        results_v.addWidget(self.results_text)
        root.addWidget(results_group, 1)

        # ── Bottom bar: Status + Analyze / Copy / Help ──────────────
        status_row = QHBoxLayout()
        self.status_label = QLabel(self.tr("Ready"))
        self.status_label.setStyleSheet("color: #666; padding: 2px 8px;")
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        self.run_btn = QPushButton(self.tr("Run"))
        self.example_btn = QPushButton(self.tr("Example"))
        self.example_btn.setToolTip(self.tr("Load example primer pair and template"))
        self.clear_btn = QPushButton(self.tr("Clear"))
        self.help_btn = QPushButton(self.tr("Help"))
        status_row.addWidget(self.run_btn)
        status_row.addWidget(self.example_btn)
        status_row.addWidget(self.clear_btn)
        status_row.addWidget(self.help_btn)
        root.addLayout(status_row)

    def connect_signals(self):
        self.run_btn.clicked.connect(self.run_analysis)
        self.example_btn.clicked.connect(self._load_example)
        self.clear_btn.clicked.connect(self._clear_all)
        self.help_btn.clicked.connect(self._show_help)
        self.fwd_edit.textChanged.connect(self._on_input_changed)
        self.rev_edit.textChanged.connect(self._on_input_changed)

    def _load_example(self):
        """Load example primer pair and template from primer_example.fasta."""
        text = load_example_text("dna", "primer_example.fasta")
        if not text:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. Please check your installation."),
            )
            return
        # Parse multi-record FASTA — extract first two as primers, third as template
        records: list[tuple[str, str]] = []
        for block in text.split(">"):
            block = block.strip()
            if not block:
                continue
            lines = block.splitlines()
            header = lines[0].strip()
            seq = "".join(line.strip() for line in lines[1:]).upper()
            records.append((header, seq))
        if len(records) < 2:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Example file has insufficient records."),
            )
            return
        self.fwd_edit.setText(records[0][1])
        self.rev_edit.setText(records[1][1])
        if len(records) >= 3:
            # Reconstruct FASTA for template display
            template_text = f">{records[2][0]}\n{records[2][1]}"
            self.template_edit.setPlainText(template_text)
        self.status_label.setText(self.tr("Loaded example: primer_example.fasta"))

    def _clear_all(self):
        self.fwd_edit.clear()
        self.rev_edit.clear()
        self.template_edit.clear()
        self.results_text.clear()
        self._last_results = ""
        self.status_label.setText("Cleared.")

    def _show_help(self):
        from PyQt6.QtCore import Qt as QtCore
        from PyQt6.QtWidgets import QLabel, QPushButton, QScrollArea, QVBoxLayout

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("Primer Analysis - Help"))
        dlg.setFixedSize(680, 500)
        layout = QVBoxLayout(dlg)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(QtCore.ScrollBarPolicy.ScrollBarAsNeeded)

        label = QLabel(
            self.tr("""
<h2>Primer Analysis</h2>

<p><b>What does this tool do?</b><br>
Analyzes a user-specified primer pair for key thermodynamic properties
including Tm, GC%, hairpin formation, self-dimer, and cross-dimer potential.
Optionally, provide a template sequence to check binding positions and
expected product size.</p>

<h3>Quick Start</h3>
<ol>
<li>Enter forward and reverse primer sequences (5'&rarr;3' orientation),
    or click <b>Example</b> to load sample data.</li>
<li>Optionally paste a template sequence to detect binding positions
    and calculate the expected PCR product size.</li>
<li>Adjust salt conditions if your buffer differs from defaults
    (50 mM Na&plus;/K&plus;, 3 mM Mg&sup2;&plus;).</li>
<li>Click <b>Run</b> to compute all properties.</li>
<li>Review the results — metrics are color-coded:
    <span style="color:#2e7d32;">green</span> = optimal,
    <span style="color:#e65100;">orange</span> = marginal,
    <span style="color:#c62828;">red</span> = poor.</li>
</ol>

<h3>Metrics Reference</h3>
<table border='0' cellpadding='4' cellspacing='2'>
<tr><td><b>Tm</b></td><td>Melting temperature (°C). Fwd and Rev should be
    within 2°C of each other for synchronized annealing.</td></tr>
<tr><td><b>GC%</b></td><td>GC content (%). Optimal range: 40-60%.</td></tr>
<tr><td><b>Hairpin &Delta;G</b></td><td>Free energy of internal secondary
    structure (kcal/mol). More negative = stronger hairpin (bad).</td></tr>
<tr><td><b>Hairpin Tm</b></td><td>Melting temperature of the hairpin
    structure. Lower is better.</td></tr>
<tr><td><b>Self-Dimer</b></td><td>Primer binding to itself. Can cause
    PCR failure. Avoid any dimer with &Delta;G &lt; -3 kcal/mol.</td></tr>
<tr><td><b>Cross-Dimer</b></td><td>Forward binding to reverse primer.
    Produces primer-dimers instead of desired amplicon.</td></tr>
<tr><td><b>Tm Difference</b></td><td>|Fwd Tm - Rev Tm|. Keep
    &lt;2°C for qPCR.</td></tr>
</table>

<h3>Quality Assessment</h3>
<p>The tool automatically flags potential issues:</p>
<ul>
<li>&#10003; <b>All checks passed</b> — primer pair looks good.</li>
<li>&#9888; <b>Warnings</b> — Tm difference &gt; 2°C, GC% out of
    40-60% range, or dimer/hairpin structures detected.</li>
</ul>

<h3>Template Binding (Optional)</h3>
<p>When a template is provided, the tool searches for both forward and
reverse primer binding sites (including reverse-complement matches)
and calculates the expected PCR product size.</p>
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

    def _on_input_changed(self):
        """Update live length indicators as the user types."""
        fwd_len = len(self._normalize(self.fwd_edit.text()))
        rev_len = len(self._normalize(self.rev_edit.text()))
        self.fwd_len_label.setText(f"{fwd_len} nt")
        self.rev_len_label.setText(f"{rev_len} nt")

    def _normalize(self, raw: str) -> str:
        return raw.strip().upper().replace(" ", "").replace("\r", "").replace("\n", "")

    def _find_binding(self, template: str, primer: str) -> int:
        rev_comp = str.maketrans("ACGTUN", "TGCAAN")
        rc = primer.translate(rev_comp)[::-1]
        pos = template.find(primer)
        if pos >= 0:
            return pos + 1
        pos = template.find(rc)
        if pos >= 0:
            return pos + 1
        return -1

    def run_analysis(self):
        if not _HAS_PRIMER3:
            self.results_text.setPlainText("Error: primer3-py is not installed.")
            return

        fwd = self._normalize(self.fwd_edit.text())
        rev = self._normalize(self.rev_edit.text())
        if not fwd or not rev:
            self.results_text.setPlainText(
                "Please enter both forward and reverse primer sequences."
            )
            return
        if len(fwd) < 8 or len(rev) < 8:
            self.results_text.setPlainText("Primer sequences are too short (minimum 8 nt).")
            return
        valid = set("ACGTUN")
        if not all(c in valid for c in fwd) or not all(c in valid for c in rev):
            self.results_text.setPlainText("Invalid bases detected. Allowed: A/C/G/T/U/N.")
            return

        mv = self.mv_spin.value()
        dv = self.dv_spin.value()

        self.status_label.setText("Analyzing...")

        try:
            fwd_tm = primer3.calc_tm(fwd, mv_conc=mv, dv_conc=dv)
            rev_tm = primer3.calc_tm(rev, mv_conc=mv, dv_conc=dv)
            fwd_hairpin = primer3.calc_hairpin(fwd, mv_conc=mv, dv_conc=dv)
            rev_hairpin = primer3.calc_hairpin(rev, mv_conc=mv, dv_conc=dv)
            fwd_homodimer = primer3.calc_homodimer(fwd, mv_conc=mv, dv_conc=dv)
            rev_homodimer = primer3.calc_homodimer(rev, mv_conc=mv, dv_conc=dv)
            heterodimer = primer3.calc_heterodimer(fwd, rev, mv_conc=mv, dv_conc=dv)
        except Exception as e:
            self.results_text.setPlainText(f"Analysis error: {e}")
            self.status_label.setText("Analysis failed.")
            return

        fwd_gc = _gc_percent(fwd)
        rev_gc = _gc_percent(rev)
        tm_diff = abs(fwd_tm - rev_tm)

        # Color helpers
        def _tm_color(tm):
            if 58 <= tm <= 62:
                return "#2e7d32"
            if 55 <= tm <= 65:
                return "#e65100"
            return "#c62828"

        def _gc_color(gc):
            if 40 <= gc <= 60:
                return "#2e7d32"
            if 30 <= gc <= 70:
                return "#e65100"
            return "#c62828"

        def _dg_color(dimer):
            dg = dimer.dg
            if dg >= -3:
                return "#2e7d32"
            if dg >= -6:
                return "#e65100"
            return "#c62828"

        def _dim_label(dimer):
            return "✓ None" if not dimer.ascii_structure else f"⚠ {dimer.dg:.1f}"

        hp_fwd_tm = getattr(fwd_hairpin, "tm", 0)
        hp_rev_tm = getattr(rev_hairpin, "tm", 0)

        html = []
        html.append('<div style="font-family:Segoe UI,sans-serif;">')
        html.append('<h3 style="color:#1976d2;margin:0 0 8px 0;">Primer Pair Analysis Results</h3>')

        # Main metrics table
        html.append(
            '<table cellpadding="5" cellspacing="0" style="border-collapse:collapse;width:100%;">'
        )
        html.append(
            '<tr style="background:#e3f2fd;font-weight:bold;"><td>Property</td><td>Forward</td><td>Reverse</td></tr>'
        )

        rows = [
            ("Length", f"{len(fwd)} nt", f"{len(rev)} nt", None),
            ("Tm (°C)", f"{fwd_tm:.1f}", f"{rev_tm:.1f}", None),
            ("GC%", f"{fwd_gc:.1f}%", f"{rev_gc:.1f}%", None),
            (
                "Hairpin ΔG",
                f"{fwd_hairpin.dg:.2f} kcal/mol",
                f"{rev_hairpin.dg:.2f} kcal/mol",
                None,
            ),
            (
                "Hairpin Tm",
                f"{hp_fwd_tm:.1f} °C" if hp_fwd_tm else "n/a",
                f"{hp_rev_tm:.1f} °C" if hp_rev_tm else "n/a",
                None,
            ),
            ("Self-Dimer", _dim_label(fwd_homodimer), _dim_label(rev_homodimer), None),
        ]
        for label, f_val, r_val, _ in rows:
            bg = "#fafafa" if rows.index((label, f_val, r_val, _)) % 2 == 0 else "#fff"
            html.append(
                f'<tr style="background:{bg};"><td><b>{label}</b></td><td>{f_val}</td><td>{r_val}</td></tr>'
            )

        # Pair-level metrics
        html.append('<tr style="background:#fff3e0;"><td colspan="3"><b>Pair Metrics</b></td></tr>')
        pair_rows = [
            ("Tm Difference", f"{tm_diff:.1f} °C", ""),
            ("Cross-Dimer ΔG", f"{heterodimer.dg:.2f} kcal/mol", ""),
            ("Cross-Dimer Tm", f"{heterodimer.tm:.1f} °C", ""),
        ]
        for label, val, _ in pair_rows:
            html.append(
                f'<tr style="background:#fff8e1;"><td><b>{label}</b></td><td colspan="2">{val}</td></tr>'
            )
        html.append("</table>")

        # Template binding
        template_raw = self._normalize(self.template_edit.toPlainText())
        if template_raw and len(template_raw) >= len(fwd) + len(rev):
            fwd_pos = self._find_binding(template_raw, fwd)
            rev_pos = self._find_binding(template_raw, rev)
            product_size = abs(rev_pos - fwd_pos) + len(rev) if fwd_pos > 0 and rev_pos > 0 else 0
            html.append('<h4 style="color:#1976d2;margin:12px 0 6px 0;">Template Binding</h4>')
            html.append(
                '<table cellpadding="5" cellspacing="0" style="border-collapse:collapse;width:100%;">'
            )
            html.append(
                '<tr style="background:#e8f5e9;font-weight:bold;"><td>Property</td><td>Value</td></tr>'
            )
            if fwd_pos > 0:
                html.append(f"<tr><td>Fwd Binding Position</td><td>{fwd_pos}</td></tr>")
            else:
                html.append(
                    '<tr style="color:#c62828;"><td>Fwd Binding</td><td>NOT FOUND</td></tr>'
                )
            if rev_pos > 0:
                html.append(f"<tr><td>Rev Binding Position</td><td>{rev_pos}</td></tr>")
            else:
                html.append(
                    '<tr style="color:#c62828;"><td>Rev Binding</td><td>NOT FOUND</td></tr>'
                )
            if product_size:
                html.append(
                    f'<tr style="background:#e8f5e9;"><td><b>Product Size</b></td><td><b>{product_size} bp</b></td></tr>'
                )
            html.append("</table>")

        # Dimer structures
        dimer_sections = []
        for label, result in [
            ("Forward Self-Dimer", fwd_homodimer),
            ("Reverse Self-Dimer", rev_homodimer),
            ("Cross-Dimer", heterodimer),
        ]:
            asc = getattr(result, "ascii_structure", None)
            if asc and str(asc).strip():
                dimer_sections.append((label, str(asc)))
        if dimer_sections:
            html.append('<h4 style="color:#1976d2;margin:12px 0 6px 0;">Dimer Structures</h4>')
            for label, structure in dimer_sections:
                html.append(f"<p><b>{label}:</b></p>")
                html.append(
                    f'<pre style="background:#f5f5f5;padding:6px;font-family:Cascadia Mono,Consolas,monospace;font-size:12px;border-radius:4px;">{structure}</pre>'
                )

        # Quality assessment
        html.append('<h4 style="color:#1976d2;margin:12px 0 6px 0;">Quality Assessment</h4>')
        warnings = []
        if tm_diff > 2.0:
            warnings.append(("warn", f"Tm difference > 2°C ({tm_diff:.1f}°C)"))
        if fwd_gc < 40 or fwd_gc > 60:
            warnings.append(("warn", f"Forward GC% out of 40-60% ({fwd_gc:.1f}%)"))
        if rev_gc < 40 or rev_gc > 60:
            warnings.append(("warn", f"Reverse GC% out of 40-60% ({rev_gc:.1f}%)"))
        if fwd_homodimer.ascii_structure:
            warnings.append((
                "warn",
                f"Forward self-dimer detected (ΔG={fwd_homodimer.dg:.1f})",
            ))
        if rev_homodimer.ascii_structure:
            warnings.append((
                "warn",
                f"Reverse self-dimer detected (ΔG={rev_homodimer.dg:.1f})",
            ))
        if heterodimer.ascii_structure:
            warnings.append(("warn", f"Cross-dimer detected (ΔG={heterodimer.dg:.1f})"))
        if not warnings:
            html.append(
                '<p style="color:#2e7d32;font-weight:bold;">✓ All checks passed. Primer pair looks good!</p>'
            )
        else:
            html.append('<ul style="color:#e65100;">')
            for level, msg in warnings:
                html.append(f"<li>{msg}</li>")
            html.append("</ul>")

        html.append("</div>")
        self._last_results = "".join(html)
        self.results_text.setHtml(self._last_results)
        self.status_label.setText(f"Done. ΔTm={tm_diff:.1f}°C, Fwd={len(fwd)}nt, Rev={len(rev)}nt")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = PrimerAnalysisTab()
    w.show()
    sys.exit(app.exec())
