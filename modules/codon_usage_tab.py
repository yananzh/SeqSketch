"""Codon Usage Analysis Tab (English UI)."""

from __future__ import annotations

import csv
import collections
import math
import re
from typing import Dict, List, Optional, Tuple

import matplotlib
import matplotlib.patches as mpatches
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QComboBox,
    QGroupBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QFileDialog,
    QMessageBox,
    QApplication,
    QHeaderView,
    QLineEdit,
    QRadioButton,
    QCheckBox,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QColor
from utils.example_data import load_example_text

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

GENETIC_CODES: Dict[str, int] = {
    "1 - Standard (Universal)": 1,
    "2 - Vertebrate Mitochondrial": 2,
    "3 - Yeast Mitochondrial": 3,
    "4 - Mold / Protozoan / Coelenterate Mitochondrial": 4,
    "5 - Invertebrate Mitochondrial": 5,
    "6 - Ciliate, Dasycladacean and Hexamita Nuclear": 6,
    "9 - Echinoderm and Flatworm Mitochondrial": 9,
    "11 - Bacterial, Archaeal and Plant Plastid": 11,
    "12 - Alternative Yeast Nuclear": 12,
    "13 - Ascidian Mitochondrial": 13,
    "14 - Alternative Flatworm Mitochondrial": 14,
}

# Reference codon usage tables for CAI (RSCU-like relative adaptiveness)
_CAI_REFERENCES: Dict[str, Dict[str, float]] = {
    "Human (H. sapiens)": {
        "TTT": 0.45,
        "TTC": 1.55,
        "TTA": 0.07,
        "TTG": 0.13,
        "CTT": 0.13,
        "CTC": 0.20,
        "CTA": 0.07,
        "CTG": 1.98,
        "ATT": 0.36,
        "ATC": 1.47,
        "ATA": 0.16,
        "ATG": 1.0,
        "GTT": 0.18,
        "GTC": 0.24,
        "GTA": 0.11,
        "GTG": 1.47,
        "TCT": 0.15,
        "TCC": 0.22,
        "TCA": 0.15,
        "TCG": 0.06,
        "AGT": 0.15,
        "AGC": 0.27,
        "CCT": 0.28,
        "CCC": 0.33,
        "CCA": 0.27,
        "CCG": 0.12,
        "ACT": 0.25,
        "ACC": 0.36,
        "ACA": 0.28,
        "ACG": 0.11,
        "GCT": 0.26,
        "GCC": 0.40,
        "GCA": 0.23,
        "GCG": 0.11,
        "TAT": 0.44,
        "TAC": 1.56,
        "CAT": 0.41,
        "CAC": 1.59,
        "CAA": 0.27,
        "CAG": 1.73,
        "AAT": 0.46,
        "AAC": 1.54,
        "AAA": 0.43,
        "AAG": 1.57,
        "GAT": 0.46,
        "GAC": 1.54,
        "GAA": 0.40,
        "GAG": 1.60,
        "TGT": 0.45,
        "TGC": 1.55,
        "TGG": 1.0,
        "CGT": 0.08,
        "CGC": 0.18,
        "CGA": 0.11,
        "CGG": 0.20,
        "AGA": 0.20,
        "AGG": 0.23,
        "GGT": 0.16,
        "GGC": 0.34,
        "GGA": 0.25,
        "GGG": 0.25,
    },
    "E. coli K-12": {
        "TTT": 0.51,
        "TTC": 1.49,
        "TTA": 0.13,
        "TTG": 0.21,
        "CTT": 0.12,
        "CTC": 0.11,
        "CTA": 0.04,
        "CTG": 1.97,
        "ATT": 1.07,
        "ATC": 1.65,
        "ATA": 0.28,
        "ATG": 1.0,
        "GTT": 0.82,
        "GTC": 0.68,
        "GTA": 0.69,
        "GTG": 1.81,
        "TCT": 0.69,
        "TCC": 0.87,
        "TCA": 0.71,
        "TCG": 0.89,
        "AGT": 0.48,
        "AGC": 1.37,
        "CCT": 0.47,
        "CCC": 0.44,
        "CCA": 0.50,
        "CCG": 2.59,
        "ACT": 0.75,
        "ACC": 1.44,
        "ACA": 0.59,
        "ACG": 1.22,
        "GCT": 1.02,
        "GCC": 1.26,
        "GCA": 1.00,
        "GCG": 1.72,
        "TAT": 0.78,
        "TAC": 1.22,
        "CAT": 0.76,
        "CAC": 1.24,
        "CAA": 0.44,
        "CAG": 1.56,
        "AAT": 0.45,
        "AAC": 1.55,
        "AAA": 1.59,
        "AAG": 0.41,
        "GAT": 1.11,
        "GAC": 0.89,
        "GAA": 1.54,
        "GAG": 0.46,
        "TGT": 0.43,
        "TGC": 1.57,
        "TGG": 1.0,
        "CGT": 1.72,
        "CGC": 1.59,
        "CGA": 0.36,
        "CGG": 0.53,
        "AGA": 0.22,
        "AGG": 0.18,
        "GGT": 1.21,
        "GGC": 1.68,
        "GGA": 0.52,
        "GGG": 0.59,
    },
    "S. cerevisiae": {
        "TTT": 0.78,
        "TTC": 1.22,
        "TTA": 0.37,
        "TTG": 1.90,
        "CTT": 0.30,
        "CTC": 0.21,
        "CTA": 0.29,
        "CTG": 0.25,
        "ATT": 1.08,
        "ATC": 1.30,
        "ATA": 0.62,
        "ATG": 1.0,
        "GTT": 0.91,
        "GTC": 0.79,
        "GTA": 0.49,
        "GTG": 0.81,
        "TCT": 1.62,
        "TCC": 1.43,
        "TCA": 1.29,
        "TCG": 0.33,
        "AGT": 0.79,
        "AGC": 0.55,
        "CCT": 0.75,
        "CCC": 0.62,
        "CCA": 1.76,
        "CCG": 0.86,
        "ACT": 1.38,
        "ACC": 1.00,
        "ACA": 1.27,
        "ACG": 0.35,
        "GCT": 1.38,
        "GCC": 1.64,
        "GCA": 0.88,
        "GCG": 0.10,
        "TAT": 0.85,
        "TAC": 1.15,
        "CAT": 0.55,
        "CAC": 1.45,
        "CAA": 1.57,
        "CAG": 0.43,
        "AAT": 1.04,
        "AAC": 0.96,
        "AAA": 1.57,
        "AAG": 0.43,
        "GAT": 1.35,
        "GAC": 0.65,
        "GAA": 1.47,
        "GAG": 0.53,
        "TGT": 0.72,
        "TGC": 1.28,
        "TGG": 1.0,
        "CGT": 0.22,
        "CGC": 0.22,
        "CGA": 0.20,
        "CGG": 0.18,
        "AGA": 1.83,
        "AGG": 1.36,
        "GGT": 1.44,
        "GGC": 1.35,
        "GGA": 0.89,
        "GGG": 0.32,
    },
}


def _build_codon_table(table_id: int):
    from Bio.Data import CodonTable

    return CodonTable.unambiguous_dna_by_id[table_id]


def _count_codons(seq: str) -> Dict[str, int]:
    seq = seq.upper().replace(" ", "").replace("\n", "")
    counts: Dict[str, int] = {}
    for i in range(0, len(seq) - 2, 3):
        codon = seq[i : i + 3]
        if len(codon) == 3:
            counts[codon] = counts.get(codon, 0) + 1
    return counts


def _compute_rscu(codon_counts: Dict[str, int], table_id: int) -> Dict[str, float]:
    bt = _build_codon_table(table_id)
    syn_groups: Dict[str, List[str]] = collections.defaultdict(list)
    for codon, aa in bt.forward_table.items():
        syn_groups[aa].append(codon)
    for codon in bt.stop_codons:
        syn_groups["*"].append(codon)

    rscu: Dict[str, float] = {}
    for _, codons in syn_groups.items():
        n = len(codons)
        total = sum(codon_counts.get(c, 0) for c in codons)
        for codon in codons:
            obs = codon_counts.get(codon, 0)
            rscu[codon] = (obs * n) / total if total > 0 and n > 0 else 0.0
    return rscu


def _gc_positions(seq: str) -> Tuple[float, float, float, float, float]:
    seq = seq.upper().replace(" ", "").replace("\n", "")
    codons = [seq[i : i + 3] for i in range(0, len(seq) - 2, 3) if len(seq[i : i + 3]) == 3]
    if not codons:
        return 0.0, 0.0, 0.0, 0.0, 0.0

    def gc(c):
        return c in "GC"

    p1 = [codon[0] for codon in codons]
    p2 = [codon[1] for codon in codons]
    p3 = [codon[2] for codon in codons]
    all_nt = list(seq)

    gc_all = sum(1 for n in all_nt if gc(n)) / len(all_nt) * 100
    gc1 = sum(1 for n in p1 if gc(n)) / len(p1) * 100
    gc2 = sum(1 for n in p2 if gc(n)) / len(p2) * 100
    gc3 = sum(1 for n in p3 if gc(n)) / len(p3) * 100
    gc12 = (gc1 + gc2) / 2.0
    return gc_all, gc1, gc2, gc3, gc12


def _compute_enc(codon_counts: Dict[str, int], table_id: int) -> float:
    """Wright (1990) ENC, excluding stop codons from all calculations."""
    bt = _build_codon_table(table_id)
    syn_groups: Dict[str, List[str]] = collections.defaultdict(list)
    for codon, aa in bt.forward_table.items():
        syn_groups[aa].append(codon)
    # Stop codons are intentionally excluded — ENC is defined only for amino-acid families.

    fam_f: Dict[int, List[float]] = collections.defaultdict(list)
    singletons = 0
    for _, codons in syn_groups.items():
        n = len(codons)
        if n == 1:
            singletons += 1  # Met, Trp (and equivalents in alt. codes) — F always = 1
            continue
        counts = [codon_counts.get(c, 0) for c in codons]
        total = sum(counts)
        if total == 0:
            continue
        sum_pi_sq = sum((c / total) ** 2 for c in counts)
        f = 1.0 if total == 1 else (sum_pi_sq * total - 1) / (total - 1)
        fam_f[n].append(f)

    nc = float(singletons)  # dynamically counted (2.0 for standard code)
    for _, f_vals in fam_f.items():
        if not f_vals:
            continue
        mean_f = sum(f_vals) / len(f_vals)
        nc += len(f_vals) / mean_f if mean_f > 0 else 61.0

    return min(nc, 61.0)


def _compute_cai(codon_counts: Dict[str, int], ref_name: str) -> Optional[float]:
    if not ref_name or ref_name not in _CAI_REFERENCES:
        return None
    ref = _CAI_REFERENCES[ref_name]
    # Convert RSCU-like reference values to standard relative adaptiveness.
    # w_i = value_i / max(family)  where family == all codons for the same
    # amino acid. Without normalization the RSCU-derived weights can exceed 1
    # and the geometric mean can drift above the valid [0,1] range.
    w_map = _normalize_cai_reference(ref)
    log_sum = 0.0
    total = 0
    for codon, cnt in codon_counts.items():
        w = w_map.get(codon, 0.0)
        if w > 0 and cnt > 0:
            log_sum += cnt * math.log(w)
            total += cnt
    if total == 0:
        return None
    return math.exp(log_sum / total)


def _normalize_cai_reference(ref: Dict[str, float]) -> Dict[str, float]:
    """Convert RSCU-like reference values to relative adaptiveness (0–1 range).

    Standard CAI (Sharp & Li) uses w_i = value_i / max_value(family).
    This ensures exp(mean(log w)) ∈ (0,1] and makes CAI values
    comparable across reference organisms.
    """
    from Bio.Data import CodonTable

    # Use the standard genetic code (ID 1) to group codons into families.
    # All built-in CAI references target the standard code.
    table = CodonTable.unambiguous_dna_by_id[1]
    # Build amino-acid → list of codons mapping
    family: Dict[str, List[str]] = {}
    for codon in ref:
        aa = table.forward_table.get(codon) or table.back_table.get(codon)
        if aa is None:
            aa_key = codon  # fallback (should not happen for standard code)
        else:
            aa_key = aa if isinstance(aa, str) else aa.upper()
        family.setdefault(aa_key, []).append(codon)

    w_map: Dict[str, float] = {}
    for codons in family.values():
        max_val = max(ref.get(c, 0.0) for c in codons)
        if max_val > 0:
            for c in codons:
                w_map[c] = ref.get(c, 0.0) / max_val
    # Any codon not in a family (e.g. stops) gets weight 0.
    return w_map


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


class _Worker(QObject):
    finished = pyqtSignal(list)
    cancelled = pyqtSignal()
    error = pyqtSignal(str)
    progress = pyqtSignal(int, int)

    def __init__(self, text: str, table_id: int, cai_ref: str, frame_offset: int = 0, parent=None):
        super().__init__(parent)
        self._text = text
        self._table_id = table_id
        self._cai_ref = cai_ref
        self._frame_offset = frame_offset
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            records = _parse_fasta(self._text)
            if not records:
                records = [("Sequence", self._text.strip())]
            total = len(records)
            results = []
            for idx, (header, seq) in enumerate(records):
                if self._cancel:
                    self.cancelled.emit()
                    return
                self.progress.emit(idx + 1, total)
                seq_clean = seq.upper().replace("U", "T")
                # Reject ambiguous sequences instead of silently deleting
                # non-ACGT characters (which would shift the reading frame).
                if not re.fullmatch(r"[ACGT]+", seq_clean):
                    # Skip this record; its absence from results serves as a signal.
                    continue
                if self._frame_offset:
                    seq_clean = seq_clean[self._frame_offset :]

                counts = _count_codons(seq_clean)
                rscu = _compute_rscu(counts, self._table_id)
                gc_all, gc1, gc2, gc3, gc12 = _gc_positions(seq_clean)
                enc = _compute_enc(counts, self._table_id)
                cai = _compute_cai(counts, self._cai_ref)

                bt = _build_codon_table(self._table_id)
                all_codons = sorted(list(bt.forward_table.keys()) + list(bt.stop_codons))
                total_codons = sum(counts.values())

                rows = []
                for codon in all_codons:
                    aa = bt.forward_table.get(codon, "*")
                    cnt = counts.get(codon, 0)
                    freq = cnt / total_codons * 1000 if total_codons else 0.0
                    rows.append({
                        "codon": codon,
                        "aa": aa,
                        "count": cnt,
                        "freq_per1000": freq,
                        "rscu": rscu.get(codon, 0.0),
                    })

                results.append({
                    "header": header,
                    "seq_len": len(seq_clean),
                    "total_codons": total_codons,
                    "gc_all": gc_all,
                    "gc1": gc1,
                    "gc2": gc2,
                    "gc3": gc3,
                    "gc12": gc12,
                    "enc": enc,
                    "cai": cai,
                    "rows": rows,
                    "counts": counts,
                })
            self.finished.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))


class _NumItem(QTableWidgetItem):
    def __init__(self, value: float, fmt: str = "{:.4f}"):
        super().__init__(fmt.format(value))
        self._val = value

    def __lt__(self, other):
        try:
            return self._val < other._val
        except Exception:
            return super().__lt__(other)


class CodonUsageTab(QWidget):
    def __init__(self, status_callback=None, parent=None):
        super().__init__(parent)
        self._status_cb = status_callback
        self._results: List[dict] = []
        self._thread: Optional[QThread] = None
        self._worker: Optional[_Worker] = None
        self._current_seq_idx: int = 0
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([360, 840])

        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet("color:#555;font-size:15px;")

        self._btn_help = QPushButton("Help")
        self._btn_help.setFixedWidth(80)
        self._btn_help.clicked.connect(self._show_help)

        status_row = QHBoxLayout()
        status_row.addWidget(self._status_label)
        status_row.addStretch()
        status_row.addWidget(self._btn_help)
        root.addLayout(status_row)

    def _build_left_panel(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        grp_input = QGroupBox(self.tr("Input Sequence"))
        gi = QVBoxLayout(grp_input)
        gi.setSpacing(6)

        self._input_text = QTextEdit()
        self._input_text.setPlaceholderText(
            ">gene1\nATGAAAGGGTTTCCCAAATAG\n\n>gene2\nATGGCATTTCGATGA"
        )
        self._input_text.setMinimumHeight(200)
        self._input_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._input_text.setAcceptDrops(True)
        self._input_text.dragEnterEvent = self._drag_enter
        self._input_text.dropEvent = self._drop_event
        gi.addWidget(self._input_text)

        row = QHBoxLayout()
        self._btn_load = QPushButton("Load File")
        self._btn_example = QPushButton("Example")
        self._btn_clear = QPushButton("Clear")
        row.addWidget(self._btn_load)
        row.addWidget(self._btn_example)
        row.addWidget(self._btn_clear)
        gi.addLayout(row)
        lay.addWidget(grp_input)

        grp_opt = QGroupBox(self.tr("Options"))
        go = QVBoxLayout(grp_opt)

        go.addWidget(QLabel("Genetic Code:"))
        self._code_combo = QComboBox()
        for nm in GENETIC_CODES:
            self._code_combo.addItem(nm)
        go.addWidget(self._code_combo)

        go.addWidget(QLabel("CAI Reference Organism:"))
        self._cai_combo = QComboBox()
        self._cai_combo.addItem("None (skip CAI)")
        for nm in _CAI_REFERENCES:
            self._cai_combo.addItem(nm)
        go.addWidget(self._cai_combo)

        go.addWidget(QLabel("Reading Frame:"))
        self._frame_combo = QComboBox()
        self._frame_combo.addItems([
            "Frame +1 (nt 1→)",
            "Frame +2 (nt 2→)",
            "Frame +3 (nt 3→)",
        ])
        go.addWidget(self._frame_combo)
        lay.addWidget(grp_opt)

        run_row = QHBoxLayout()
        self._btn_run = QPushButton("Analyze")
        self._btn_run.setFixedHeight(38)
        self._btn_run.setStyleSheet(
            "QPushButton{background:#1976d2;color:white;border-radius:5px;font-weight:600;}"
            "QPushButton:hover{background:#1565c0;}"
            "QPushButton:disabled{background:#aaa;}"
        )
        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.setFixedHeight(38)
        self._btn_cancel.setEnabled(False)
        run_row.addWidget(self._btn_run)
        run_row.addWidget(self._btn_cancel)
        lay.addLayout(run_row)

        grp_exp = QGroupBox(self.tr("Export"))
        ge = QVBoxLayout(grp_exp)
        scope = QHBoxLayout()
        self._rb_all = QRadioButton("All sequences")
        self._rb_cur = QRadioButton("Current sequence")
        self._rb_all.setChecked(True)
        self._scope_group = QButtonGroup()
        self._scope_group.addButton(self._rb_all, 0)
        self._scope_group.addButton(self._rb_cur, 1)
        scope.addWidget(self._rb_all)
        scope.addWidget(self._rb_cur)
        ge.addLayout(scope)

        self._btn_export_csv = QPushButton("Export CSV")
        self._btn_export_csv.setEnabled(False)
        self._btn_copy = QPushButton("Copy Table")
        self._btn_copy.setEnabled(False)
        ge.addWidget(self._btn_export_csv)
        ge.addWidget(self._btn_copy)
        lay.addWidget(grp_exp)

        self._btn_load.clicked.connect(self._load_file)
        self._btn_example.clicked.connect(self._insert_example)
        self._btn_clear.clicked.connect(self._input_text.clear)
        self._btn_run.clicked.connect(self._run_analysis)
        self._btn_cancel.clicked.connect(self._cancel_analysis)
        self._btn_export_csv.clicked.connect(self._export_csv)
        self._btn_copy.clicked.connect(self._copy_table)
        return w

    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self._seq_selector_row = QWidget()
        sel = QHBoxLayout(self._seq_selector_row)
        sel.setContentsMargins(0, 0, 0, 0)
        sel.addWidget(QLabel("Sequence:"))
        self._seq_combo = QComboBox()
        self._seq_combo.setMinimumWidth(260)
        sel.addWidget(self._seq_combo)
        sel.addStretch()
        self._seq_selector_row.setVisible(False)
        lay.addWidget(self._seq_selector_row)

        self._result_tabs = QTabWidget()
        lay.addWidget(self._result_tabs)

        self._summary_widget = QWidget()
        sv = QVBoxLayout(self._summary_widget)
        sv.addWidget(QLabel("Key Statistics:"))
        self._stats_table = QTableWidget(0, 2)
        self._stats_table.setHorizontalHeaderLabels(["Metric", "Value"])
        self._stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._stats_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._stats_table.setMinimumHeight(280)
        self._stats_table.setMaximumHeight(320)
        sv.addWidget(self._stats_table)

        sv.addSpacing(14)
        sv.addWidget(QLabel("Top 10 Most-Used Codons (excluding stop):"))
        self._top10_table = QTableWidget(0, 5)
        self._top10_table.setHorizontalHeaderLabels([
            "Codon",
            "Amino Acid",
            "Count",
            "Freq(/1000)",
            "RSCU",
        ])
        self._top10_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._top10_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._top10_table.setMinimumHeight(260)
        self._top10_table.setMaximumHeight(300)
        sv.addWidget(self._top10_table)
        sv.addStretch()
        self._result_tabs.addTab(self._summary_widget, "Summary")

        codon_container = QWidget()
        cv = QVBoxLayout(codon_container)
        fr = QHBoxLayout()
        fr.addWidget(QLabel("Filter by amino acid (one-letter):"))
        self._aa_filter = QLineEdit()
        self._aa_filter.setPlaceholderText("e.g. L")
        self._aa_filter.setMaximumWidth(80)
        self._aa_filter.setClearButtonEnabled(True)
        fr.addWidget(self._aa_filter)
        fr.addStretch()
        self._chk_show_stop = QCheckBox("Show stop codons")
        self._chk_show_stop.setChecked(False)
        fr.addWidget(self._chk_show_stop)
        cv.addLayout(fr)

        self._codon_table = QTableWidget()
        self._codon_table.setColumnCount(6)
        self._codon_table.setHorizontalHeaderLabels([
            "Codon",
            "Amino Acid",
            "Count",
            "Freq(/1000)",
            "RSCU",
            "RSCU Bar",
        ])
        self._codon_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._codon_table.setColumnWidth(0, 60)
        self._codon_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._codon_table.setColumnWidth(1, 80)
        self._codon_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._codon_table.setColumnWidth(2, 60)
        self._codon_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._codon_table.setColumnWidth(3, 80)
        self._codon_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._codon_table.setColumnWidth(4, 60)
        self._codon_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self._codon_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._codon_table.setAlternatingRowColors(True)
        self._codon_table.setSortingEnabled(True)
        cv.addWidget(self._codon_table)
        self._result_tabs.addTab(codon_container, "Codon Table")

        rscu_container = QWidget()
        rv = QVBoxLayout(rscu_container)
        self._rscu_fig = Figure(tight_layout=True)
        self._rscu_canvas = FigureCanvas(self._rscu_fig)
        self._rscu_canvas.setMinimumHeight(350)
        self._rscu_toolbar = NavigationToolbar(self._rscu_canvas, rscu_container)
        rv.addWidget(self._rscu_toolbar)
        rv.addWidget(self._rscu_canvas)
        self._result_tabs.addTab(rscu_container, "RSCU Chart")

        gc_container = QWidget()
        gv = QVBoxLayout(gc_container)
        self._gc_fig = Figure(tight_layout=True)
        self._gc_canvas = FigureCanvas(self._gc_fig)
        self._gc_canvas.setMinimumHeight(300)
        self._gc_toolbar = NavigationToolbar(self._gc_canvas, gc_container)
        gv.addWidget(self._gc_toolbar)
        gv.addWidget(self._gc_canvas)
        self._result_tabs.addTab(gc_container, "GC / Neutrality")

        cmp_container = QWidget()
        mv = QVBoxLayout(cmp_container)
        mv.addWidget(QLabel("Nc plot: ENC vs GC3 for all sequences"))

        self._cmp_table = QTableWidget(0, 7)
        self._cmp_table.setHorizontalHeaderLabels([
            "Sequence",
            "Length (nt)",
            "Codons",
            "ENC",
            "CAI",
            "GC%",
            "GC3%",
        ])
        self._cmp_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._cmp_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._cmp_table.setSortingEnabled(True)
        self._cmp_table.setMaximumHeight(220)
        mv.addWidget(self._cmp_table)

        self._nc_fig = Figure(tight_layout=True)
        self._nc_canvas = FigureCanvas(self._nc_fig)
        self._nc_canvas.setMinimumHeight(280)
        self._nc_toolbar = NavigationToolbar(self._nc_canvas, cmp_container)
        mv.addWidget(self._nc_toolbar)
        mv.addWidget(self._nc_canvas)
        self._result_tabs.addTab(cmp_container, "Comparison")

        self._seq_combo.currentIndexChanged.connect(self._on_seq_changed)
        self._aa_filter.textChanged.connect(self._apply_aa_filter)
        self._chk_show_stop.stateChanged.connect(
            lambda _: self._apply_aa_filter(self._aa_filter.text())
        )

        return w

    def _drag_enter(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def _drop_event(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    self._input_text.setPlainText(f.read())
                self._set_status(f"Loaded: {path}")
                event.acceptProposedAction()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))
                event.ignore()

    def _load_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open FASTA File",
            "",
            "FASTA Files (*.fa *.fasta *.fna *.ffn);;All Files (*)",
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    self._input_text.setPlainText(f.read())
                self._set_status(f"Loaded: {path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _insert_example(self):
        text = load_example_text("dna", "codon_example.fasta")
        if not text:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. Please check your installation."),
            )
            return
        self._input_text.setPlainText(text)

    def _set_status(self, msg: str):
        self._status_label.setText(msg)
        if self._status_cb:
            self._status_cb(msg, 4000)

    def _run_analysis(self):
        text = self._input_text.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Input Required", "Please input or load sequences first.")
            return

        clean = "".join(c for c in text.upper() if c.isalpha())
        if clean:
            acgtu_frac = sum(1 for c in clean if c in "ACGTU") / len(clean)
            if acgtu_frac < 0.5:
                ret = QMessageBox.question(
                    self,
                    "Unexpected Input",
                    f"Only {acgtu_frac:.0%} of alphabetic characters are DNA/RNA bases.\n"
                    "This may be protein sequence or mixed text.\n\nContinue anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if ret != QMessageBox.StandardButton.Yes:
                    return

        table_id = GENETIC_CODES[self._code_combo.currentText()]
        cai_ref = self._cai_combo.currentText()
        if cai_ref == "None (skip CAI)":
            cai_ref = ""
        frame_offset = self._frame_combo.currentIndex()

        self._btn_run.setEnabled(False)
        self._btn_cancel.setEnabled(True)
        self._btn_export_csv.setEnabled(False)
        self._btn_copy.setEnabled(False)
        self._set_status("Analyzing...")

        self._thread = QThread(self)
        self._worker = _Worker(text, table_id, cai_ref, frame_offset)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_analysis_done)
        self._worker.cancelled.connect(self._on_analysis_cancelled)
        self._worker.error.connect(self._on_analysis_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.cancelled.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._cleanup_worker)
        self._thread.start()

    def _on_progress(self, cur: int, total: int):
        self._set_status(f"Analyzing sequence {cur}/{total}...")

    def _on_analysis_done(self, results: list):
        self._results = results

        short = [r["header"] for r in results if r["total_codons"] < 100]
        if short:
            names = "\n".join(f"  • {h[:60]}" for h in short[:5])
            QMessageBox.warning(
                self,
                "Short Sequences",
                "The following sequence(s) have fewer than 100 codons.\n"
                "RSCU and ENC may be unreliable:\n\n" + names,
            )

        self._btn_run.setEnabled(True)
        self._btn_cancel.setEnabled(False)
        self._btn_export_csv.setEnabled(True)
        self._btn_copy.setEnabled(True)

        self._seq_combo.blockSignals(True)
        self._seq_combo.clear()
        for r in results:
            label = r["header"][:60] + ("..." if len(r["header"]) > 60 else "")
            self._seq_combo.addItem(label)
        self._seq_combo.blockSignals(False)
        self._seq_selector_row.setVisible(len(results) > 1)
        self._current_seq_idx = 0
        self._seq_combo.setCurrentIndex(0)

        self._display_results(0)
        self._fill_comparison()
        self._set_status(f"Done — {len(results)} sequence(s) analyzed.")

    def _on_analysis_error(self, msg: str):
        self._btn_run.setEnabled(True)
        self._btn_cancel.setEnabled(False)
        QMessageBox.critical(self, "Analysis Error", msg)
        self._set_status("Error: " + msg[:80])

    def _cleanup_worker(self):
        self._worker = None
        self._thread = None

    def _cancel_analysis(self):
        if self._worker is not None:
            self._worker.cancel()
        self._btn_cancel.setEnabled(False)
        self._set_status("Cancelling...")

    def _on_analysis_cancelled(self):
        self._btn_run.setEnabled(True)
        self._btn_cancel.setEnabled(False)
        self._set_status("Analysis cancelled.")

    def _on_seq_changed(self, idx: int):
        if 0 <= idx < len(self._results):
            self._current_seq_idx = idx
            self._display_results(idx)

    def _display_results(self, idx: int):
        if not self._results or idx >= len(self._results):
            return
        r = self._results[idx]
        try:
            self._fill_summary(r)
            self._fill_codon_table(r)
            self._draw_rscu_chart(r)
            self._draw_gc_chart(r)
        except Exception as exc:
            QMessageBox.critical(self, "Display Error", str(exc))
            self._set_status("Display Error: " + str(exc)[:80])

    def _fill_summary(self, r: dict):
        cai_str = f"{r['cai']:.3f}" if r.get("cai") is not None else "N/A"
        enc = r["enc"]
        if enc < 35:
            bias = "Strong bias"
        elif enc < 50:
            bias = "Moderate bias"
        else:
            bias = "Weak / near-equal usage"

        metrics = [
            ("Sequence", r["header"][:80]),
            ("Sequence Length", f"{r['seq_len']:,} nt"),
            ("Total Codons", f"{r['total_codons']:,}"),
            ("GC Content (Overall)", f"{r['gc_all']:.2f}%"),
            ("GC1 (Position 1)", f"{r['gc1']:.2f}%"),
            ("GC2 (Position 2)", f"{r['gc2']:.2f}%"),
            ("GC3 (Position 3)", f"{r['gc3']:.2f}%"),
            ("GC12 (mean of GC1+GC2)", f"{r['gc12']:.2f}%"),
            ("ENC", f"{enc:.2f}"),
            ("Codon Bias Strength", bias),
            ("CAI", cai_str),
        ]
        self._stats_table.setRowCount(len(metrics))
        for i, (k, v) in enumerate(metrics):
            self._stats_table.setItem(i, 0, QTableWidgetItem(k))
            self._stats_table.setItem(i, 1, QTableWidgetItem(v))

        coding_rows = [x for x in r["rows"] if x["aa"] != "*"]
        top10 = sorted(coding_rows, key=lambda x: x["count"], reverse=True)[:10]
        self._top10_table.setRowCount(len(top10))
        for i, row in enumerate(top10):
            self._top10_table.setItem(i, 0, QTableWidgetItem(row["codon"]))
            self._top10_table.setItem(i, 1, QTableWidgetItem(row["aa"]))
            self._top10_table.setItem(i, 2, _NumItem(row["count"], "{:.0f}"))
            self._top10_table.setItem(i, 3, _NumItem(row["freq_per1000"], "{:.2f}"))
            self._top10_table.setItem(i, 4, _NumItem(row["rscu"], "{:.3f}"))

    def _fill_codon_table(self, r: dict):
        rows = r["rows"]
        self._codon_table.setSortingEnabled(False)
        self._codon_table.setRowCount(len(rows))

        for i, row in enumerate(rows):
            rscu = row["rscu"]
            self._codon_table.setItem(i, 0, QTableWidgetItem(row["codon"]))
            self._codon_table.setItem(
                i, 1, QTableWidgetItem("Stop" if row["aa"] == "*" else row["aa"])
            )
            self._codon_table.setItem(i, 2, _NumItem(row["count"], "{:.0f}"))
            self._codon_table.setItem(i, 3, _NumItem(row["freq_per1000"], "{:.2f}"))
            self._codon_table.setItem(i, 4, _NumItem(rscu, "{:.3f}"))

            bar_len = int(min(rscu / 3.0, 1.0) * 20)
            bar_item = QTableWidgetItem("█" * bar_len)
            bar_item.setForeground(QColor(self._rscu_color(rscu)))
            self._codon_table.setItem(i, 5, bar_item)

            if row["aa"] != "*":
                bg = QColor(self._rscu_color(rscu) + "28")
                for col in range(2, 5):
                    item = self._codon_table.item(i, col)
                    if item:
                        item.setBackground(bg)

        self._codon_table.setSortingEnabled(True)
        self._apply_aa_filter(self._aa_filter.text())

    def _apply_aa_filter(self, text: str):
        q = text.strip().upper()
        show_stop = self._chk_show_stop.isChecked()
        for row in range(self._codon_table.rowCount()):
            aa_item = self._codon_table.item(row, 1)
            if not aa_item:
                continue
            aa = aa_item.text().upper()
            if aa == "STOP" and not show_stop:
                self._codon_table.setRowHidden(row, True)
                continue
            hide = bool(q) and not aa.startswith(q)
            self._codon_table.setRowHidden(row, hide)

    def _draw_rscu_chart(self, r: dict):
        from Bio.Data import CodonTable

        table_id = GENETIC_CODES[self._code_combo.currentText()]
        bt = CodonTable.unambiguous_dna_by_id[table_id]

        aa_to_codons: Dict[str, List[str]] = collections.defaultdict(list)
        for codon, aa in bt.forward_table.items():
            aa_to_codons[aa].append(codon)
        for codon in bt.stop_codons:
            aa_to_codons["*"] += [codon]
        for aa in aa_to_codons:
            aa_to_codons[aa].sort()

        aa_order = sorted(aa_to_codons.keys(), key=lambda x: (x == "*", x))
        rscu_map = {row["codon"]: row["rscu"] for row in r["rows"]}

        n_total_codons = sum(len(c) for c in aa_to_codons.values())
        self._rscu_fig.clear()
        self._rscu_fig.set_facecolor("#f9f9f9")
        ax = self._rscu_fig.add_subplot(111)
        ax.set_facecolor("#f9f9f9")

        x = 0
        xtick_pos: List[int] = []
        xtick_lab: List[str] = []
        aa_mid_x: List[float] = []
        aa_labels: List[str] = []

        for aa in aa_order:
            codons = aa_to_codons[aa]
            start = x
            for codon in codons:
                v = rscu_map.get(codon, 0.0)
                if v == 0:
                    c = "#cccccc"
                elif v < 0.6:
                    c = "#ef5350"
                elif v < 0.9:
                    c = "#ff9800"
                elif v <= 1.1:
                    c = "#66bb6a"
                elif v < 2.0:
                    c = "#42a5f5"
                else:
                    c = "#7e57c2"

                ax.bar(x, v, color=c, edgecolor="white", linewidth=0.5, width=0.8)
                xtick_pos.append(x)
                xtick_lab.append(codon)
                x += 1

            aa_mid_x.append((start + x - 1) / 2.0)
            aa_labels.append(aa)
            x += 0.6

        ax.set_xticks(xtick_pos)
        ax.set_xticklabels(xtick_lab, rotation=90, fontsize=7.5, fontfamily="monospace")
        ax.tick_params(axis="x", pad=3)
        ax.axhline(1.0, color="#999", linestyle="--", linewidth=0.8)
        ax.set_ylabel("RSCU")
        ax.set_title(f"RSCU — {r['header'][:70]}")

        # Place AA labels below tick labels using a blended transform:
        # x in data coordinates, y in axes fraction (negative = below axis).
        # This prevents overlap regardless of the data y-scale.
        from matplotlib.transforms import blended_transform_factory

        blend = blended_transform_factory(ax.transData, ax.transAxes)
        for mid, aa in zip(aa_mid_x, aa_labels):
            ax.text(
                mid,
                -0.18,
                aa,
                transform=blend,
                ha="center",
                va="top",
                fontsize=8,
                fontweight="bold",
                clip_on=False,
            )

        legend = [
            mpatches.Patch(color="#ef5350", label="RSCU < 0.6 Strongly underused"),
            mpatches.Patch(color="#ff9800", label="0.6 ≤ RSCU < 0.9 Underused"),
            mpatches.Patch(color="#66bb6a", label="0.9 ≤ RSCU ≤ 1.1 Near-equal"),
            mpatches.Patch(color="#42a5f5", label="1.1 < RSCU < 2.0 Preferred"),
            mpatches.Patch(color="#7e57c2", label="RSCU ≥ 2.0 Highly preferred"),
            mpatches.Patch(color="#cccccc", label="Count = 0"),
        ]
        ax.legend(handles=legend, loc="upper right", fontsize=8, framealpha=0.85)

        # rect=[left, bottom, right, top] in figure fraction;
        # bottom=0.16 reserves tighter space for the AA label row beneath the codon tick labels.
        self._rscu_fig.tight_layout(rect=[0, 0.16, 1, 1])
        self._rscu_canvas.draw()

    def _draw_gc_chart(self, r: dict):
        self._gc_fig.clear()
        self._gc_fig.set_facecolor("#f9f9f9")
        ax1 = self._gc_fig.add_subplot(1, 2, 1)
        ax1.set_facecolor("#f9f9f9")
        cats = ["GC(All)", "GC1", "GC2", "GC3", "GC12"]
        vals = [r["gc_all"], r["gc1"], r["gc2"], r["gc3"], r["gc12"]]
        cols = ["#1976d2", "#42a5f5", "#66bb6a", "#ef5350", "#ff9800"]
        bars = ax1.bar(cats, vals, color=cols, edgecolor="white", linewidth=0.8)
        ax1.set_ylabel("GC Content (%)")
        ax1.set_title("GC Content at Codon Positions")
        ax1.set_ylim(0, 105)
        ax1.axhline(50, color="#aaa", linestyle="--", linewidth=0.8)
        for b, v in zip(bars, vals):
            ax1.text(
                b.get_x() + b.get_width() / 2,
                b.get_height() + 1.5,
                f"{v:.1f}%",
                ha="center",
                va="bottom",
                fontsize=9.5,
            )

        ax2 = self._gc_fig.add_subplot(1, 2, 2)
        ax2.set_facecolor("#f9f9f9")
        if len(self._results) > 1:
            gc12s = [rs["gc12"] for rs in self._results]
            gc3s = [rs["gc3"] for rs in self._results]
            ax2.scatter(gc3s, gc12s, color="#1976d2", s=50, alpha=0.75, zorder=3)
            ax2.scatter(r["gc3"], r["gc12"], color="#ef5350", s=90, zorder=4, label="Current")
            if len(gc3s) >= 3:
                m, b = np.polyfit(gc3s, gc12s, 1)
                xs = np.linspace(min(gc3s), max(gc3s), 100)
                ax2.plot(
                    xs,
                    m * xs + b,
                    "--",
                    color="#888",
                    linewidth=1.0,
                    label=f"Slope={m:.2f}",
                )
        else:
            ax2.scatter([r["gc3"]], [r["gc12"]], color="#1976d2", s=80)

        ax2.plot([0, 100], [0, 100], ":", color="#bbb", linewidth=1.0, label="GC12 = GC3")
        ax2.set_xlabel("GC3 (%)")
        ax2.set_ylabel("GC12 (%)")
        ax2.set_title("Neutrality Plot (GC12 vs GC3)")
        ax2.set_xlim(0, 100)
        ax2.set_ylim(0, 100)
        ax2.legend(fontsize=8, framealpha=0.8)

        self._gc_fig.tight_layout()
        self._gc_canvas.draw()

    def _fill_comparison(self):
        self._cmp_table.setSortingEnabled(False)
        self._cmp_table.setRowCount(len(self._results))
        for i, r in enumerate(self._results):
            cai = f"{r['cai']:.3f}" if r.get("cai") is not None else "N/A"
            self._cmp_table.setItem(i, 0, QTableWidgetItem(r["header"][:60]))
            self._cmp_table.setItem(i, 1, _NumItem(r["seq_len"], "{:.0f}"))
            self._cmp_table.setItem(i, 2, _NumItem(r["total_codons"], "{:.0f}"))
            self._cmp_table.setItem(i, 3, _NumItem(r["enc"], "{:.2f}"))
            self._cmp_table.setItem(i, 4, QTableWidgetItem(cai))
            self._cmp_table.setItem(i, 5, _NumItem(r["gc_all"], "{:.2f}"))
            self._cmp_table.setItem(i, 6, _NumItem(r["gc3"], "{:.2f}"))
        self._cmp_table.setSortingEnabled(True)

        self._draw_nc_plot()

    def _draw_nc_plot(self):
        self._nc_fig.clear()
        self._nc_fig.set_facecolor("#f9f9f9")
        ax = self._nc_fig.add_subplot(111)
        ax.set_facecolor("#f9f9f9")

        gc3_theory = np.linspace(0.05, 0.95, 200)
        enc_theory = 2 + gc3_theory + 29 / (gc3_theory**2 + (1 - gc3_theory) ** 2)
        ax.plot(
            gc3_theory * 100,
            enc_theory,
            "-",
            color="#aaa",
            linewidth=1.5,
            label="Expected (no selection)",
        )

        encs = [r["enc"] for r in self._results]
        gc3s = [r["gc3"] for r in self._results]
        ax.scatter(gc3s, encs, s=60, c="#1976d2", alpha=0.8, label="Sequences")

        if len(self._results) <= 20:
            for r, gx, ey in zip(self._results, gc3s, encs):
                ax.annotate(
                    r["header"][:20],
                    (gx, ey),
                    textcoords="offset points",
                    xytext=(4, 4),
                    fontsize=7.5,
                )

        ax.set_xlabel("GC3 (%)")
        ax.set_ylabel("ENC")
        ax.set_title("Nc Plot — ENC vs GC3")
        ax.set_xlim(0, 100)
        ax.set_ylim(20, 65)
        ax.legend(fontsize=8, framealpha=0.85)

        self._nc_fig.tight_layout()
        self._nc_canvas.draw()

    def _export_csv(self):
        if not self._results:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV", "codon_usage.csv", "CSV Files (*.csv)"
        )
        if not path:
            return

        export_all = self._rb_all.isChecked()
        rows = self._results if export_all else [self._results[self._current_seq_idx]]
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Sequence",
                    "Codon",
                    "Amino Acid",
                    "Count",
                    "Freq_per_1000",
                    "RSCU",
                ])
                for r in rows:
                    for row in r["rows"]:
                        writer.writerow([
                            r["header"],
                            row["codon"],
                            row["aa"],
                            row["count"],
                            f"{row['freq_per1000']:.4f}",
                            f"{row['rscu']:.4f}",
                        ])
            scope = "all sequences" if export_all else "current sequence"
            self._set_status(f"Exported ({scope}): {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _copy_table(self):
        if not self._results:
            return
        export_all = self._rb_all.isChecked()
        rows = self._results if export_all else [self._results[self._current_seq_idx]]

        lines = ["Sequence\tCodon\tAmino Acid\tCount\tFreq/1000\tRSCU"]
        for r in rows:
            for row in r["rows"]:
                lines.append(
                    f"{r['header']}\t{row['codon']}\t{row['aa']}\t"
                    f"{row['count']}\t{row['freq_per1000']:.4f}\t{row['rscu']:.4f}"
                )
        QApplication.clipboard().setText("\n".join(lines))
        scope = "all sequences" if export_all else "current sequence"
        self._set_status(f"Copied ({scope}) to clipboard.")

    @staticmethod
    def _rscu_color(val: float) -> str:
        if val == 0:
            return "#cccccc"
        if val < 0.6:
            return "#ef5350"  # strongly underused
        if val < 0.9:
            return "#ff9800"  # moderately underused
        if val <= 1.1:
            return "#66bb6a"  # near-equal usage (0.9–1.1)
        if val < 2.0:
            return "#42a5f5"  # preferred
        return "#7e57c2"  # highly preferred

    def _show_help(self):
        help_text = self.tr(
            "<h2>Codon Usage Analysis &mdash; Comprehensive Codon Bias Toolkit</h2>"
            "<p><b>What does this tool do?</b><br>"
            "It performs a complete codon usage analysis of protein-coding sequences (CDS). "
            "The tool computes key metrics including <b>RSCU</b> (Relative Synonymous Codon Usage), "
            "<b>ENC</b> (Effective Number of Codons), <b>CAI</b> (Codon Adaptation Index), "
            "and GC-content at each codon position. Results are presented across five "
            "interactive tabs with sortable tables, color-coded RSCU bars, and publication-ready "
            "Matplotlib charts.</p>"
            "<h3>Quick Start</h3>"
            "<ol>"
            "<li>Paste one or more CDS sequences in FASTA format into the input editor, or click <b>Load File</b></li>"
            "<li>Select the appropriate <b>Genetic Code</b> for your organism (default: Standard)</li>"
            "<li>Optionally choose a <b>CAI Reference Organism</b> to compute the Codon Adaptation Index</li>"
            "<li>Select a <b>Reading Frame</b> (default +1 works for most CDS inputs)</li>"
            "<li>Click <b>Analyze</b> and browse the five result tabs</li>"
            "</ol>"
            "<h3>Key Metrics Explained</h3>"
            "<table border='0' cellpadding='4' cellspacing='2'>"
            "<tr><td><b>Metric</b></td><td><b>Meaning</b></td><td><b>Interpretation</b></td></tr>"
            "<tr><td>RSCU</td><td>Relative Synonymous Codon Usage</td><td>Values &gt; 1 = over-represented, &lt; 1 = under-represented; ideal = 1.0 (no bias)</td></tr>"
            "<tr><td>ENC</td><td>Effective Number of Codons</td><td>Ranges 20 (extreme bias) to 61 (no bias); values ≤ 35 indicate strong codon bias</td></tr>"
            "<tr><td>CAI</td><td>Codon Adaptation Index</td><td>Ranges 0–1; higher values mean better translation-adaptation to the reference organism</td></tr>"
            "<tr><td>GC / GC3</td><td>Overall GC% and GC% at 3rd codon position</td><td>GC3 is a sensitive indicator of mutational bias; low GC3 often correlates with translational selection</td></tr>"
            "</table>"
            "<h3>Result Tabs</h3>"
            "<ul>"
            "<li><b>Summary</b> — key statistics for the current sequence, plus a top-10 most-used codons table</li>"
            "<li><b>Codon Table</b> — full 64-codon table with counts, frequency per 1000, RSCU, and a visual RSCU bar (green = enriched, red = depleted). Filter by amino acid or toggle stop codons</li>"
            "<li><b>RSCU Chart</b> — grouped bar chart of RSCU values per amino acid, with one bar per synonymous codon</li>"
            "<li><b>GC / Neutrality</b> — stacked GC1/GC2/GC3 bars for each sequence, plus a GC12 vs GC3 neutrality plot (slope ≈ 1 = neutral evolution; slope &lt; 1 = selective constraint)</li>"
            "<li><b>Comparison</b> — per-sequence table (ENC, CAI, GC%, GC3%) and the Nc plot (ENC vs GC3) to detect mutational vs selective pressure</li>"
            "</ul>"
            "<h3>Genetic Codes</h3>"
            "<p>The tool supports 11 NCBI genetic code tables. The most frequently used alternatives are:</p>"
            "<ul>"
            "<li><b>1 - Standard (Universal)</b> — most nuclear genomes</li>"
            "<li><b>2 - Vertebrate Mitochondrial</b> — uses AGA/AGG (not stop) and AUA = Met</li>"
            "<li><b>5 - Invertebrate Mitochondrial</b> — common for arthropod mtDNA</li>"
            "<li><b>11 - Bacterial, Archaeal and Plant Plastid</b> — identical to Standard for most codons</li>"
            "</ul>"
            "<h3>CAI Reference Tables</h3>"
            "<p>The Codon Adaptation Index compares your sequence's codon usage to that of highly-expressed genes "
            "in a reference organism. Built-in references: <b>Human</b> and <b>E. coli K-12</b> (based on ribosomal "
            "protein genes). CAI values &gt; 0.8 suggest good adaptation to the reference.</p>"
            "<h3>Reading Frames</h3>"
            "<p>The tool translates your sequence in one of three forward reading frames. Use <b>Frame +1</b> for "
            "canonical CDS input; try frames +2 and +3 if the sequence may be misaligned or contains alternative start sites.</p>"
            "<h3>Tips</h3>"
            "<ul>"
            "<li>Click <b>Example</b> to load a real bacterial spoT CDS for a quick trial</li>"
            "<li>The <b>Codon Table</b> supports sorting — click any column header to reorder rows</li>"
            "<li>Use the amino acid filter (e.g. &quot;L&quot; for leucine) to focus on specific codon families</li>"
            "<li>Multi-sequence input enables the <b>Comparison</b> tab with per-sequence summaries and the Nc plot</li>"
            "<li>Export data as CSV or use <b>Copy Table</b> to transfer the current view to your clipboard</li>"
            "<li>For whole-genome codon usage analysis, concatenate CDS sequences from the same genome into a single FASTA file</li>"
            "</ul>"
            "<h3>Related Tools in SeqSketch</h3>"
            "<ul>"
            "<li><b>Translate</b> — translate DNA to protein (also supports alternative genetic codes)</li>"
            "<li><b>ORF Finder</b> — locate open reading frames in genomic DNA</li>"
            "<li><b>GC Content / GC Skew Plot</b> — whole-sequence GC analysis with sliding windows</li>"
            "</ul>"
        )
        from PyQt6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QHBoxLayout,
            QLabel,
            QPushButton,
            QScrollArea,
        )
        from PyQt6.QtCore import Qt as QtCore

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("Help - Codon Usage Analysis"))
        dlg.setFixedSize(900, 680)
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
