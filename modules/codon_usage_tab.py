"""Codon Usage Analysis Tab (English UI)."""

from __future__ import annotations

import csv
import io
import collections
import math
from typing import Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

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
    QScrollArea,
    QApplication,
    QHeaderView,
    QLineEdit,
    QRadioButton,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QPixmap, QImage

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
    codons = [
        seq[i : i + 3] for i in range(0, len(seq) - 2, 3) if len(seq[i : i + 3]) == 3
    ]
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
    bt = _build_codon_table(table_id)
    syn_groups: Dict[str, List[str]] = collections.defaultdict(list)
    for codon, aa in bt.forward_table.items():
        syn_groups[aa].append(codon)

    fam_f: Dict[int, List[float]] = collections.defaultdict(list)
    for _, codons in syn_groups.items():
        n = len(codons)
        if n == 1:
            continue
        counts = [codon_counts.get(c, 0) for c in codons]
        total = sum(counts)
        if total == 0:
            continue
        sum_pi_sq = sum((c / total) ** 2 for c in counts)
        f = 1.0 if total == 1 else (sum_pi_sq * total - 1) / (total - 1)
        fam_f[n].append(f)

    nc = 2.0
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
    log_sum = 0.0
    total = 0
    for codon, cnt in codon_counts.items():
        w = ref.get(codon, 0.0)
        if w > 0 and cnt > 0:
            log_sum += cnt * math.log(w)
            total += cnt
    if total == 0:
        return None
    return math.exp(log_sum / total)


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
    error = pyqtSignal(str)
    progress = pyqtSignal(int, int)

    def __init__(self, text: str, table_id: int, cai_ref: str, parent=None):
        super().__init__(parent)
        self._text = text
        self._table_id = table_id
        self._cai_ref = cai_ref

    def run(self):
        try:
            records = _parse_fasta(self._text)
            if not records:
                records = [("Sequence", self._text.strip())]
            total = len(records)
            results = []
            for idx, (header, seq) in enumerate(records):
                self.progress.emit(idx + 1, total)
                seq_clean = "".join(c for c in seq.upper() if c in "ACGTU")
                seq_clean = seq_clean.replace("U", "T")

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
                    rows.append(
                        {
                            "codon": codon,
                            "aa": aa,
                            "count": cnt,
                            "freq_per1000": freq,
                            "rscu": rscu.get(codon, 0.0),
                        }
                    )

                results.append(
                    {
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
                    }
                )
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
        self._rscu_fig_buf: Optional[bytes] = None
        self._gc_fig_buf: Optional[bytes] = None
        self._nc_fig_buf: Optional[bytes] = None
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter)

        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([360, 840])

    def _build_left_panel(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        grp_input = QGroupBox("1) Input Sequence")
        gi = QVBoxLayout(grp_input)
        gi.setSpacing(6)

        hint = QLabel(
            "Paste one or more CDS FASTA sequences, or load from a file.\n"
            "Accepts DNA or RNA; multiple sequences are compared."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#555;font-size:13px;")
        gi.addWidget(hint)

        self._input_text = QTextEdit()
        self._input_text.setPlaceholderText(
            ">gene1\nATGAAAGGGTTTCCCAAATAG\n\n>gene2\nATGGCATTTCGATGA"
        )
        self._input_text.setMinimumHeight(200)
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

        grp_opt = QGroupBox("2) Options")
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
        lay.addWidget(grp_opt)

        self._btn_run = QPushButton("Analyze")
        self._btn_run.setFixedHeight(38)
        self._btn_run.setStyleSheet(
            "QPushButton{background:#1976d2;color:white;border-radius:5px;font-weight:600;}"
            "QPushButton:hover{background:#1565c0;}"
            "QPushButton:disabled{background:#aaa;}"
        )
        lay.addWidget(self._btn_run)

        grp_exp = QGroupBox("3) Export")
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

        self._btn_help = QPushButton("Help")
        lay.addWidget(self._btn_help)
        lay.addStretch()

        self._btn_load.clicked.connect(self._load_file)
        self._btn_example.clicked.connect(self._insert_example)
        self._btn_clear.clicked.connect(self._input_text.clear)
        self._btn_run.clicked.connect(self._run_analysis)
        self._btn_export_csv.clicked.connect(self._export_csv)
        self._btn_copy.clicked.connect(self._copy_table)
        self._btn_help.clicked.connect(self._show_help)
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
        self._stats_table.setMaximumHeight(230)
        sv.addWidget(self._stats_table)

        sv.addWidget(QLabel("Top 10 Most-Used Codons (excluding stop):"))
        self._top10_table = QTableWidget(0, 5)
        self._top10_table.setHorizontalHeaderLabels(
            ["Codon", "Amino Acid", "Count", "Freq(/1000)", "RSCU"]
        )
        self._top10_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._top10_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._top10_table.setMaximumHeight(220)
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
        cv.addLayout(fr)

        self._codon_table = QTableWidget()
        self._codon_table.setColumnCount(6)
        self._codon_table.setHorizontalHeaderLabels(
            ["Codon", "Amino Acid", "Count", "Freq(/1000)", "RSCU", "RSCU Bar"]
        )
        self._codon_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._codon_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._codon_table.setAlternatingRowColors(True)
        self._codon_table.setSortingEnabled(True)
        cv.addWidget(self._codon_table)
        self._result_tabs.addTab(codon_container, "Codon Table")

        rscu_container = QWidget()
        rv = QVBoxLayout(rscu_container)
        rr = QHBoxLayout()
        rr.addStretch()
        self._btn_save_rscu = QPushButton("Save Chart as PNG")
        self._btn_save_rscu.setEnabled(False)
        rr.addWidget(self._btn_save_rscu)
        rv.addLayout(rr)
        rscu_scroll = QScrollArea()
        rscu_scroll.setWidgetResizable(True)
        self._rscu_chart_label = QLabel(alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        rscu_scroll.setWidget(self._rscu_chart_label)
        rv.addWidget(rscu_scroll)
        self._result_tabs.addTab(rscu_container, "RSCU Chart")

        gc_container = QWidget()
        gv = QVBoxLayout(gc_container)
        gr = QHBoxLayout()
        gr.addStretch()
        self._btn_save_gc = QPushButton("Save Chart as PNG")
        self._btn_save_gc.setEnabled(False)
        gr.addWidget(self._btn_save_gc)
        gv.addLayout(gr)
        gc_scroll = QScrollArea()
        gc_scroll.setWidgetResizable(True)
        self._gc_chart_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        gc_scroll.setWidget(self._gc_chart_label)
        gv.addWidget(gc_scroll)
        self._result_tabs.addTab(gc_container, "GC / Neutrality")

        cmp_container = QWidget()
        mv = QVBoxLayout(cmp_container)
        nr = QHBoxLayout()
        nr.addWidget(QLabel("Nc plot: ENC vs GC3 for all sequences"))
        nr.addStretch()
        self._btn_save_nc = QPushButton("Save Chart as PNG")
        self._btn_save_nc.setEnabled(False)
        nr.addWidget(self._btn_save_nc)
        mv.addLayout(nr)

        self._cmp_table = QTableWidget(0, 7)
        self._cmp_table.setHorizontalHeaderLabels(
            ["Sequence", "Length (nt)", "Codons", "ENC", "CAI", "GC%", "GC3%"]
        )
        self._cmp_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._cmp_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._cmp_table.setSortingEnabled(True)
        self._cmp_table.setMaximumHeight(220)
        mv.addWidget(self._cmp_table)

        nc_scroll = QScrollArea()
        nc_scroll.setWidgetResizable(True)
        self._nc_chart_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        nc_scroll.setWidget(self._nc_chart_label)
        mv.addWidget(nc_scroll)
        self._result_tabs.addTab(cmp_container, "Comparison")

        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet("color:#555;font-size:13px;")
        lay.addWidget(self._status_label)

        self._seq_combo.currentIndexChanged.connect(self._on_seq_changed)
        self._aa_filter.textChanged.connect(self._apply_aa_filter)
        self._btn_save_rscu.clicked.connect(lambda: self._save_chart("rscu"))
        self._btn_save_gc.clicked.connect(lambda: self._save_chart("gc"))
        self._btn_save_nc.clicked.connect(lambda: self._save_chart("nc"))

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
        self._input_text.setPlainText(
            ">BRCA1_exon11_CDS\n"
            "ATGGATTTATCTGCTCTTCGCGTTGAAGAAGTACAAAATGTCATTAATGCTATGCAGAAA\n"
            "ATCTTAGAGTGTCCCATCTGTCTGGAGTTGATCAAGGAACCTGTCTCCACAAAGTGTGAC\n"
            "CATCTCAAAGACCTATGTGTAAAGAAGATGGTAGAAGATTTTGGCTTGGCTGAAGAGCTG\n"
            "TGA\n\n"
            ">EGFR_kinase_CDS\n"
            "ATGCGACCCTCCGGGACGGCCGGGGCAGCGCTCCTGGCGCTGCTGGCTGCGCTCTGCCCG\n"
            "GCGAGTCGGGCTCTGGAGGAAAAGAAAGTTTGCCAAGGCACGAGTAACAAGCTCACGCAG\n"
            "TTGGGCACTTTTGAAGATCATTTTCTCAGCCTCCAGAGGATGTTCAATAACTGTGAGGTG\n"
            "GTCCTTGGGAATTTGGAAATTACCTATGTGCAGAGGAATTATGATCTTTCCTTCTTAAAG\n"
            "TGA\n"
        )

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

        self._btn_run.setEnabled(False)
        self._btn_export_csv.setEnabled(False)
        self._btn_copy.setEnabled(False)
        self._btn_save_rscu.setEnabled(False)
        self._btn_save_gc.setEnabled(False)
        self._btn_save_nc.setEnabled(False)
        self._set_status("Analyzing...")

        self._thread = QThread(self)
        self._worker = _Worker(text, table_id, cai_ref)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_analysis_done)
        self._worker.error.connect(self._on_analysis_error)
        self._worker.finished.connect(self._thread.quit)
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
                "RSCU and ENC may be unreliable:\n\n"
                + names,
            )

        self._btn_run.setEnabled(True)
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
        QMessageBox.critical(self, "Analysis Error", msg)
        self._set_status("Error: " + msg[:80])

    def _cleanup_worker(self):
        self._worker = None
        self._thread = None

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
            self._btn_save_rscu.setEnabled(True)
            self._btn_save_gc.setEnabled(True)
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
            self._codon_table.setItem(i, 1, QTableWidgetItem("Stop" if row["aa"] == "*" else row["aa"]))
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
        for row in range(self._codon_table.rowCount()):
            aa_item = self._codon_table.item(row, 1)
            if not aa_item:
                continue
            aa = aa_item.text().upper()
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

        fig, ax = plt.subplots(figsize=(20, 6.5), dpi=96)
        fig.patch.set_facecolor("#f9f9f9")
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
                elif v < 1.0:
                    c = "#ff9800"
                elif v <= 1.0:
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
        ax.axhline(1.0, color="#999", linestyle="--", linewidth=0.8)
        ax.set_ylabel("RSCU")
        ax.set_title(f"RSCU — {r['header'][:70]}")

        y_min = ax.get_ylim()[0]
        for mid, aa in zip(aa_mid_x, aa_labels):
            ax.text(mid, y_min - 0.18, aa, ha="center", va="top", fontsize=8, fontweight="bold")

        legend = [
            mpatches.Patch(color="#ef5350", label="RSCU < 0.6 Underused"),
            mpatches.Patch(color="#ff9800", label="0.6 ≤ RSCU < 1.0"),
            mpatches.Patch(color="#66bb6a", label="RSCU = 1.0 Equal"),
            mpatches.Patch(color="#42a5f5", label="1.0 < RSCU < 2.0 Preferred"),
            mpatches.Patch(color="#7e57c2", label="RSCU ≥ 2.0 Highly preferred"),
            mpatches.Patch(color="#cccccc", label="Count = 0"),
        ]
        ax.legend(handles=legend, loc="upper right", fontsize=8, framealpha=0.85)

        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        self._rscu_fig_buf = buf.getvalue()
        buf.seek(0)
        self._rscu_chart_label.setPixmap(self._buf_to_pixmap(buf.read()))
        plt.close(fig)

    def _draw_gc_chart(self, r: dict):
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), dpi=96)
        fig.patch.set_facecolor("#f9f9f9")

        ax1 = axes[0]
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
            ax1.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.5, f"{v:.1f}%", ha="center", va="bottom", fontsize=9.5)

        ax2 = axes[1]
        ax2.set_facecolor("#f9f9f9")
        if len(self._results) > 1:
            gc12s = [rs["gc12"] for rs in self._results]
            gc3s = [rs["gc3"] for rs in self._results]
            ax2.scatter(gc3s, gc12s, color="#1976d2", s=50, alpha=0.75, zorder=3)
            ax2.scatter(r["gc3"], r["gc12"], color="#ef5350", s=90, zorder=4, label="Current")
            if len(gc3s) >= 3:
                m, b = np.polyfit(gc3s, gc12s, 1)
                xs = np.linspace(min(gc3s), max(gc3s), 100)
                ax2.plot(xs, m * xs + b, "--", color="#888", linewidth=1.0, label=f"Slope={m:.2f}")
        else:
            ax2.scatter([r["gc3"]], [r["gc12"]], color="#1976d2", s=80)

        ax2.plot([0, 100], [0, 100], ":", color="#bbb", linewidth=1.0, label="GC12 = GC3")
        ax2.set_xlabel("GC3 (%)")
        ax2.set_ylabel("GC12 (%)")
        ax2.set_title("Neutrality Plot (GC12 vs GC3)")
        ax2.set_xlim(0, 100)
        ax2.set_ylim(0, 100)
        ax2.legend(fontsize=8, framealpha=0.8)

        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        self._gc_fig_buf = buf.getvalue()
        buf.seek(0)
        self._gc_chart_label.setPixmap(self._buf_to_pixmap(buf.read()))
        plt.close(fig)

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
        self._btn_save_nc.setEnabled(True)

    def _draw_nc_plot(self):
        fig, ax = plt.subplots(figsize=(8, 5.5), dpi=96)
        fig.patch.set_facecolor("#f9f9f9")
        ax.set_facecolor("#f9f9f9")

        gc3_theory = np.linspace(0.05, 0.95, 200)
        enc_theory = 2 + gc3_theory + 29 / (gc3_theory**2 + (1 - gc3_theory) ** 2)
        ax.plot(gc3_theory * 100, enc_theory, "-", color="#aaa", linewidth=1.5, label="Expected (no selection)")

        encs = [r["enc"] for r in self._results]
        gc3s = [r["gc3"] for r in self._results]
        ax.scatter(gc3s, encs, s=60, c="#1976d2", alpha=0.8, label="Sequences")

        if len(self._results) <= 20:
            for r, gx, ey in zip(self._results, gc3s, encs):
                ax.annotate(r["header"][:20], (gx, ey), textcoords="offset points", xytext=(4, 4), fontsize=7.5)

        ax.set_xlabel("GC3 (%)")
        ax.set_ylabel("ENC")
        ax.set_title("Nc Plot — ENC vs GC3")
        ax.set_xlim(0, 100)
        ax.set_ylim(20, 65)
        ax.legend(fontsize=8, framealpha=0.85)

        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        self._nc_fig_buf = buf.getvalue()
        buf.seek(0)
        self._nc_chart_label.setPixmap(self._buf_to_pixmap(buf.read()))
        plt.close(fig)

    def _save_chart(self, which: str):
        mp = {"rscu": self._rscu_fig_buf, "gc": self._gc_fig_buf, "nc": self._nc_fig_buf}
        buf = mp.get(which)
        if not buf:
            return

        default = {"rscu": "rscu_chart.png", "gc": "gc_chart.png", "nc": "nc_plot.png"}[which]
        path, _ = QFileDialog.getSaveFileName(self, "Save Chart as PNG", default, "PNG Images (*.png)")
        if path:
            try:
                with open(path, "wb") as f:
                    f.write(buf)
                self._set_status(f"Chart saved: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", str(e))

    def _export_csv(self):
        if not self._results:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "codon_usage.csv", "CSV Files (*.csv)")
        if not path:
            return

        export_all = self._rb_all.isChecked()
        rows = self._results if export_all else [self._results[self._current_seq_idx]]
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["Sequence", "Codon", "Amino Acid", "Count", "Freq_per_1000", "RSCU"])
                for r in rows:
                    for row in r["rows"]:
                        writer.writerow(
                            [
                                r["header"],
                                row["codon"],
                                row["aa"],
                                row["count"],
                                f"{row['freq_per1000']:.4f}",
                                f"{row['rscu']:.4f}",
                            ]
                        )
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
            return "#ef5350"
        if val < 1.0:
            return "#ff9800"
        if val <= 1.0:
            return "#66bb6a"
        if val < 2.0:
            return "#42a5f5"
        return "#7e57c2"

    @staticmethod
    def _buf_to_pixmap(data: bytes) -> QPixmap:
        img = QImage.fromData(data)
        return QPixmap.fromImage(img)

    def _show_help(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Codon Usage Analysis — Help")
        dlg.resize(580, 520)
        lay = QVBoxLayout(dlg)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml(
            """
<h3>How to Use</h3>
<ol>
  <li>Paste one or more <b>CDS FASTA sequences</b>, or use <b>Load File</b>.</li>
  <li>Select the <b>Genetic Code</b>.</li>
  <li>Optional: choose <b>CAI Reference Organism</b>.</li>
  <li>Click <b>Analyze</b>.</li>
</ol>

<h3>Key Metrics</h3>
<ul>
  <li><b>RSCU</b>: Relative Synonymous Codon Usage.</li>
  <li><b>ENC</b>: Effective Number of Codons (20–61; lower means stronger bias).</li>
  <li><b>GC1/GC2/GC3</b>: GC content at codon positions 1/2/3.</li>
  <li><b>GC12</b>: mean of GC1 and GC2, used with GC3 in neutrality plots.</li>
  <li><b>CAI</b>: Codon Adaptation Index (0–1), higher means better adaptation to reference usage.</li>
</ul>

<h3>Plots</h3>
<ul>
  <li><b>RSCU Chart</b>: codon-level preference bars.</li>
  <li><b>GC / Neutrality</b>: GC-position bars + GC12 vs GC3 neutrality plot.</li>
  <li><b>Comparison</b>: sequence summary table + Nc plot (ENC vs GC3).</li>
</ul>

<h3>Export</h3>
<p><b>Export CSV</b> and <b>Copy Table</b> follow the chosen scope: all sequences or current sequence.</p>
            """
        )
        lay.addWidget(text)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(dlg.accept)
        lay.addWidget(btns)
        dlg.exec()
