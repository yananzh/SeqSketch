"""
Primer Pair Analyzer (PyQt6 + primer3-py)
Check properties of user-specified primer pairs.
"""

import sys
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

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
        fwd_row.addWidget(QLabel(self.tr("Forward (5'→3'):")))
        self.fwd_edit = QLineEdit()
        self.fwd_edit.setPlaceholderText(self.tr("e.g. ATCGATCGATCGATCGATCG"))
        self.fwd_edit.setMinimumWidth(240)
        self.fwd_len_label = QLabel("0 nt")
        fwd_row.addWidget(self.fwd_edit, 1)
        fwd_row.addWidget(self.fwd_len_label)
        input_v.addLayout(fwd_row)

        rev_row = QHBoxLayout()
        rev_row.addWidget(QLabel(self.tr("Reverse (5'→3'):")))
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
        self.template_edit.setPlaceholderText(
            self.tr("Paste template to check binding positions and product size...")
        )
        self.template_edit.setMaximumHeight(80)
        template_v.addWidget(self.template_edit)
        root.addWidget(template_group)

        # ── 3. Salt parameters ──────────────────────────────────────
        params_row = QHBoxLayout()
        params_row.addWidget(QLabel(self.tr("Salt (mM):")))
        self.mv_spin = QDoubleSpinBox()
        self.mv_spin.setRange(10, 200)
        self.mv_spin.setValue(50)
        self.mv_spin.setFixedWidth(70)
        self.mv_spin.setToolTip(self.tr("Monovalent salt (Na⁺/K⁺) concentration"))
        params_row.addWidget(self.mv_spin)

        params_row.addSpacing(16)
        params_row.addWidget(QLabel(self.tr("Mg²⁺ (mM):")))
        self.dv_spin = QDoubleSpinBox()
        self.dv_spin.setRange(0.5, 10)
        self.dv_spin.setValue(3.0)
        self.dv_spin.setFixedWidth(70)
        self.dv_spin.setToolTip(self.tr("Divalent salt (Mg²⁺) concentration"))
        params_row.addWidget(self.dv_spin)
        params_row.addStretch()
        root.addLayout(params_row)

        # ── Analyze button ──────────────────────────────────────────
        self.analyze_btn = QPushButton(self.tr("Analyze Primer Pair"))
        self.analyze_btn.setMinimumHeight(38)
        root.addWidget(self.analyze_btn)

        # ── Results ─────────────────────────────────────────────────
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setPlaceholderText(
            self.tr("Enter forward and reverse primer sequences, then click Analyze.")
        )
        root.addWidget(self.results_text, 1)

        # ── Status ──────────────────────────────────────────────────
        self.status_label = QLabel(self.tr("Ready"))
        self.status_label.setStyleSheet("color: #666; padding: 2px 8px;")
        root.addWidget(self.status_label)

    def connect_signals(self):
        self.fwd_edit.textChanged.connect(self._on_input_changed)
        self.rev_edit.textChanged.connect(self._on_input_changed)
        self.analyze_btn.clicked.connect(self.run_analysis)

    def _on_input_changed(self):
        fwd = self._normalize(self.fwd_edit.text())
        rev = self._normalize(self.rev_edit.text())
        self.fwd_len_label.setText(f"{len(fwd)} nt")
        self.rev_len_label.setText(f"{len(rev)} nt")

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
            self.results_text.setPlainText(
                "Primer sequences are too short (minimum 8 nt)."
            )
            return
        valid = set("ACGTUN")
        if not all(c in valid for c in fwd) or not all(c in valid for c in rev):
            self.results_text.setPlainText(
                "Invalid bases detected. Allowed: A/C/G/T/U/N."
            )
            return

        mv = self.mv_spin.value()
        dv = self.dv_spin.value()

        self.status_label.setText("Analyzing...")

        try:
            fwd_tm = primer3.calc_tm(fwd, mv_conc=mv, dv_conc=dv).tm
            rev_tm = primer3.calc_tm(rev, mv_conc=mv, dv_conc=dv).tm
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

        lines = []
        lines.append("=" * 60)
        lines.append("  PRIMER PAIR ANALYSIS RESULTS")
        lines.append("=" * 60)

        lines.append(f"\n{'Property':<28} {'Forward':>14} {'Reverse':>14}")
        lines.append("-" * 56)
        lines.append(f"{'Length':<28} {len(fwd):>14} nt {len(rev):>14} nt")
        lines.append(f"{'Tm':<28} {fwd_tm:>14.1f} °C {rev_tm:>14.1f} °C")
        lines.append(f"{'GC%':<28} {fwd_gc:>14.1f} %  {rev_gc:>14.1f} %")
        lines.append(
            f"{'Hairpin ΔG':<28} {fwd_hairpin.dg:>14.2f}  {rev_hairpin.dg:>14.2f} kcal/mol"
        )
        hp_fwd_tm = getattr(fwd_hairpin, "tm", 0)
        hp_rev_tm = getattr(rev_hairpin, "tm", 0)
        lines.append(f"{'Hairpin Tm':<28} {hp_fwd_tm:>14.1f} °C {hp_rev_tm:>14.1f} °C")
        lines.append(
            f"{'Self-Dimer ΔG':<28} {fwd_homodimer.dg:>14.2f}  {rev_homodimer.dg:>14.2f} kcal/mol"
        )
        lines.append("-" * 56)
        lines.append(f"{'Tm Difference':<28} {tm_diff:>14.1f} °C")
        lines.append(f"{'Cross-Dimer ΔG':<28} {heterodimer.dg:>14.2f} kcal/mol")
        lines.append(f"{'Cross-Dimer Tm':<28} {heterodimer.tm:>14.1f} °C")

        # Template binding
        template_raw = self._normalize(self.template_edit.toPlainText())
        if template_raw and len(template_raw) >= len(fwd) + len(rev):
            fwd_pos = self._find_binding(template_raw, fwd)
            rev_pos = self._find_binding(template_raw, rev)
            lines.append("-" * 56)
            if fwd_pos > 0 and rev_pos > 0:
                lines.append(f"{'Fwd Binding Position':<28} {fwd_pos:>14}")
                lines.append(f"{'Rev Binding Position':<28} {rev_pos:>14}")
                product_size = abs(rev_pos - fwd_pos) + len(rev)
                lines.append(f"{'Product Size':<28} {product_size:>14} bp")
            else:
                if fwd_pos < 0:
                    lines.append(f"{'Fwd Binding':<28} {'NOT FOUND':>14}")
                if rev_pos < 0:
                    lines.append(f"{'Rev Binding':<28} {'NOT FOUND':>14}")

        # Quality assessment
        lines.append("\n" + "-" * 56)
        lines.append("  QUALITY ASSESSMENT")
        lines.append("-" * 56)
        warnings = []
        if tm_diff > 2.0:
            warnings.append(f"⚠ Tm difference > 2°C ({tm_diff:.1f}°C)")
        if fwd_gc < 40 or fwd_gc > 60:
            warnings.append(f"⚠ Forward GC% out of 40-60%: {fwd_gc:.1f}%")
        if rev_gc < 40 or rev_gc > 60:
            warnings.append(f"⚠ Reverse GC% out of 40-60%: {rev_gc:.1f}%")
        if not fwd_homodimer.no_structure:
            warnings.append(f"⚠ Forward self-dimer (ΔG={fwd_homodimer.dg:.1f})")
        if not rev_homodimer.no_structure:
            warnings.append(f"⚠ Reverse self-dimer (ΔG={rev_homodimer.dg:.1f})")
        if not heterodimer.no_structure:
            warnings.append(f"⚠ Cross-dimer detected (ΔG={heterodimer.dg:.1f})")
        if not warnings:
            warnings.append("✓ All checks passed.")
        for w in warnings:
            lines.append(f"  {w}")

        lines.append("\n" + "=" * 60)
        self.results_text.setPlainText("\n".join(lines))
        self.status_label.setText(
            f"Done. ΔTm={tm_diff:.1f}°C, Fwd={len(fwd)}nt, Rev={len(rev)}nt"
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = PrimerAnalysisTab()
    w.show()
    sys.exit(app.exec())
