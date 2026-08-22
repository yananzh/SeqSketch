"""Codon Usage Analysis Tab (English UI)."""

from __future__ import annotations

import collections
import csv
import math
import os
import re
from typing import Dict, List, Optional, Tuple

import matplotlib
import matplotlib.patches as mpatches
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.common_components import unify_status_button_sizes
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
    "C. elegans": {
        "TTT": 0.39,
        "TTC": 1.61,
        "TTA": 0.20,
        "TTG": 0.69,
        "CTT": 0.84,
        "CTC": 0.93,
        "CTA": 0.26,
        "CTG": 2.28,
        "ATT": 1.21,
        "ATC": 1.39,
        "ATA": 0.40,
        "ATG": 1.0,
        "GTT": 1.27,
        "GTC": 1.27,
        "GTA": 0.24,
        "GTG": 1.22,
        "TCT": 1.50,
        "TCC": 1.29,
        "TCA": 0.75,
        "TCG": 0.35,
        "AGT": 0.63,
        "AGC": 1.48,
        "CCT": 1.37,
        "CCC": 0.72,
        "CCA": 1.10,
        "CCG": 0.81,
        "ACT": 1.41,
        "ACC": 1.43,
        "ACA": 0.61,
        "ACG": 0.55,
        "GCT": 1.99,
        "GCC": 1.10,
        "GCA": 0.43,
        "GCG": 0.48,
        "TAT": 0.26,
        "TAC": 1.74,
        "CAT": 0.62,
        "CAC": 1.38,
        "CAA": 0.50,
        "CAG": 1.50,
        "AAT": 0.39,
        "AAC": 1.61,
        "AAA": 0.46,
        "AAG": 1.54,
        "GAT": 0.63,
        "GAC": 1.37,
        "GAA": 0.85,
        "GAG": 1.15,
        "TGT": 0.62,
        "TGC": 1.38,
        "TGG": 1.0,
        "CGT": 0.46,
        "CGC": 1.30,
        "CGA": 0.41,
        "CGG": 0.60,
        "AGA": 0.70,
        "AGG": 0.49,
        "GGT": 1.77,
        "GGC": 1.23,
        "GGA": 0.57,
        "GGG": 0.43,
    },
    "A. thaliana": {
        "TTT": 0.80,
        "TTC": 1.20,
        "TTA": 0.30,
        "TTG": 0.90,
        "CTT": 1.00,
        "CTC": 0.80,
        "CTA": 0.30,
        "CTG": 1.00,
        "ATT": 1.10,
        "ATC": 1.00,
        "ATA": 0.30,
        "ATG": 1.0,
        "GTT": 1.30,
        "GTC": 0.90,
        "GTA": 0.30,
        "GTG": 1.10,
        "TCT": 1.30,
        "TCC": 1.00,
        "TCA": 0.70,
        "TCG": 0.40,
        "AGT": 0.60,
        "AGC": 1.00,
        "CCT": 1.30,
        "CCC": 0.70,
        "CCA": 1.00,
        "CCG": 0.60,
        "ACT": 1.30,
        "ACC": 1.20,
        "ACA": 0.60,
        "ACG": 0.50,
        "GCT": 1.80,
        "GCC": 1.10,
        "GCA": 0.60,
        "GCG": 0.50,
        "TAT": 0.40,
        "TAC": 1.60,
        "CAT": 0.60,
        "CAC": 1.40,
        "CAA": 0.80,
        "CAG": 1.20,
        "AAT": 0.50,
        "AAC": 1.50,
        "AAA": 0.60,
        "AAG": 1.40,
        "GAT": 0.70,
        "GAC": 1.30,
        "GAA": 0.90,
        "GAG": 1.10,
        "TGT": 0.50,
        "TGC": 1.50,
        "TGG": 1.0,
        "CGT": 0.60,
        "CGC": 1.00,
        "CGA": 0.40,
        "CGG": 0.40,
        "AGA": 0.50,
        "AGG": 0.40,
        "GGT": 1.60,
        "GGC": 1.20,
        "GGA": 0.70,
        "GGG": 0.50,
    },
    "M. musculus": {
        "TTT": 0.48,
        "TTC": 1.52,
        "TTA": 0.10,
        "TTG": 0.16,
        "CTT": 0.15,
        "CTC": 0.22,
        "CTA": 0.08,
        "CTG": 1.90,
        "ATT": 0.40,
        "ATC": 1.42,
        "ATA": 0.18,
        "ATG": 1.0,
        "GTT": 0.22,
        "GTC": 0.28,
        "GTA": 0.12,
        "GTG": 1.38,
        "TCT": 0.18,
        "TCC": 0.26,
        "TCA": 0.16,
        "TCG": 0.07,
        "AGT": 0.16,
        "AGC": 0.30,
        "CCT": 0.32,
        "CCC": 0.36,
        "CCA": 0.30,
        "CCG": 0.13,
        "ACT": 0.30,
        "ACC": 0.40,
        "ACA": 0.32,
        "ACG": 0.12,
        "GCT": 0.30,
        "GCC": 0.44,
        "GCA": 0.26,
        "GCG": 0.12,
        "TAT": 0.44,
        "TAC": 1.56,
        "CAT": 0.46,
        "CAC": 1.54,
        "CAA": 0.30,
        "CAG": 1.70,
        "AAT": 0.50,
        "AAC": 1.50,
        "AAA": 0.46,
        "AAG": 1.54,
        "GAT": 0.50,
        "GAC": 1.50,
        "GAA": 0.44,
        "GAG": 1.56,
        "TGT": 0.50,
        "TGC": 1.50,
        "TGG": 1.0,
        "CGT": 0.10,
        "CGC": 0.22,
        "CGA": 0.12,
        "CGG": 0.24,
        "AGA": 0.20,
        "AGG": 0.24,
        "GGT": 0.18,
        "GGC": 0.38,
        "GGA": 0.26,
        "GGG": 0.28,
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


# Three-letter amino acid codes for the AA filter (three-letter input support).
_AA_3_TO_1 = {
    "ALA": "A",
    "ARG": "R",
    "ASN": "N",
    "ASP": "D",
    "CYS": "C",
    "GLN": "Q",
    "GLU": "E",
    "GLY": "G",
    "HIS": "H",
    "ILE": "I",
    "LEU": "L",
    "LYS": "K",
    "MET": "M",
    "PHE": "F",
    "PRO": "P",
    "SER": "S",
    "THR": "T",
    "TRP": "W",
    "TYR": "Y",
    "VAL": "V",
}

# Codons with RSCU below this threshold are reported as "rare" (common
# cut-off used for heterologous expression analysis).
_RARE_RSCU_THRESHOLD = 0.3


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
    skipped = pyqtSignal(int)

    def __init__(self, text: str, table_id: int, cai_ref: str, frame_offset: int = 0, parent=None):
        super().__init__(parent)
        self._text = text
        self._table_id = table_id
        self._cai_ref = cai_ref
        self._frame_offset = frame_offset

    def run(self):
        try:
            records = _parse_fasta(self._text)
            if not records:
                records = [("Sequence", self._text.strip())]
            total = len(records)
            results = []
            skipped_count = 0
            for idx, (header, seq) in enumerate(records):
                self.progress.emit(idx + 1, total)
                seq_clean = seq.upper().replace("U", "T")
                # Reject ambiguous sequences instead of silently deleting
                # non-ACGT characters (which would shift the reading frame).
                if not re.fullmatch(r"[ACGT]+", seq_clean):
                    skipped_count += 1
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

                rare_codons = sum(
                    1
                    for row in rows
                    if row["aa"] != "*" and row["count"] > 0 and row["rscu"] < _RARE_RSCU_THRESHOLD
                )

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
                    "rare_codons": rare_codons,
                    "rows": rows,
                    "counts": counts,
                })
            self.skipped.emit(skipped_count)
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
        self._skipped_count: int = 0
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        left_panel = self._build_left_panel()
        right_panel = self._build_right_panel()
        left_panel.setMinimumWidth(280)
        right_panel.setMinimumWidth(520)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([320, 560])

        self._status_label = QLabel("Ready")

        self._btn_run = QPushButton("Run")
        self._btn_run.clicked.connect(self._run_analysis)

        self._btn_export_csv = QPushButton("Export CSV")
        self._btn_export_csv.setEnabled(False)
        self._btn_export_csv.clicked.connect(self._export_csv)

        self._btn_export_plot = QPushButton("Export Plot")
        self._btn_export_plot.setToolTip(
            "Save the current chart (RSCU / GC / Comparison) as an image file"
        )
        self._btn_export_plot.setEnabled(False)
        self._btn_export_plot.clicked.connect(self._export_plot)

        self._btn_help = QPushButton("Help")
        self._btn_help.clicked.connect(self._show_help)

        self.status_layout = QHBoxLayout()
        self.status_layout.addWidget(self._status_label)
        self.status_layout.addStretch()
        self.status_layout.addWidget(self._btn_run)
        self.status_layout.addWidget(self._btn_export_csv)
        self.status_layout.addWidget(self._btn_export_plot)
        self.status_layout.addWidget(self._btn_help)
        # Same one-word/two-word width rule as the BaseTabWidget tabs.
        unify_status_button_sizes(self)
        root.addLayout(self.status_layout)

        self._result_tabs.currentChanged.connect(self._update_export_plot_state)

    def _build_left_panel(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        grp_input = QGroupBox(self.tr("Input Sequence"))
        gi = QVBoxLayout(grp_input)
        gi.setContentsMargins(6, 16, 6, 4)
        gi.setSpacing(6)

        self._input_text = QTextEdit()
        self._input_text.setPlaceholderText(
            "Paste one or more DNA coding sequences in FASTA format, "
            "or drag & drop a file...\n\n"
            ">gene1\nATGAAAGGGTTTCCCAAATAG\n"
            ">gene2\nATGGCATTTCGATGA"
        )
        self._input_text.setMinimumHeight(150)
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
        go.setContentsMargins(6, 16, 6, 4)

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

        self._btn_load.clicked.connect(self._load_file)
        self._btn_example.clicked.connect(self._insert_example)
        self._btn_clear.clicked.connect(self._clear_all)
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
        self._stats_table.setMinimumHeight(200)
        self._stats_table.setMaximumHeight(240)
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
        self._top10_table.setMinimumHeight(190)
        self._top10_table.setMaximumHeight(220)
        sv.addWidget(self._top10_table)
        sv.addStretch()
        self._result_tabs.addTab(self._summary_widget, "Summary")

        codon_container = QWidget()
        cv = QVBoxLayout(codon_container)
        fr = QHBoxLayout()
        fr.addWidget(QLabel("Filter by amino acid:"))
        self._aa_filter = QLineEdit()
        self._aa_filter.setPlaceholderText("e.g. L, M or Leu")
        self._aa_filter.setMaximumWidth(110)
        self._aa_filter.setToolTip(
            "One-letter or three-letter codes, comma-separated (e.g. L, Leu)"
        )
        self._aa_filter.setClearButtonEnabled(True)
        fr.addWidget(self._aa_filter)
        fr.addStretch()
        self._chk_hide_zero = QCheckBox("Hide zero-count codons")
        self._chk_hide_zero.setChecked(True)
        self._chk_hide_zero.setToolTip("Hide codons that do not appear in the current sequence")
        fr.addWidget(self._chk_hide_zero)
        self._chk_show_stop = QCheckBox("Show stop codons")
        self._chk_show_stop.setChecked(False)
        fr.addWidget(self._chk_show_stop)
        cv.addLayout(fr)

        self._codon_table = QTableWidget()
        self._codon_table.setColumnCount(5)
        self._codon_table.setHorizontalHeaderLabels([
            "Codon",
            "AA",
            "Count",
            "Freq(/1000)",
            "RSCU",
        ])
        header = self._codon_table.horizontalHeader()
        for col in range(4):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._codon_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._codon_table.setAlternatingRowColors(True)
        self._codon_table.setSortingEnabled(True)
        cv.addWidget(self._codon_table)
        self._result_tabs.addTab(codon_container, "Codons")

        rscu_container = QWidget()
        rv = QVBoxLayout(rscu_container)
        self._rscu_fig = Figure(figsize=(8, 3.0), tight_layout=True)
        self._rscu_canvas = FigureCanvas(self._rscu_fig)
        self._rscu_canvas.setMinimumHeight(300)
        rv.addWidget(self._rscu_canvas)
        self._result_tabs.addTab(rscu_container, "RSCU")

        gc_container = QWidget()
        gv = QVBoxLayout(gc_container)
        self._gc_fig = Figure(figsize=(8, 2.6), tight_layout=True)
        self._gc_canvas = FigureCanvas(self._gc_fig)
        self._gc_canvas.setMinimumHeight(260)
        gv.addWidget(self._gc_canvas)
        self._result_tabs.addTab(gc_container, "GC/Neutrality")

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
        self._cmp_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._cmp_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._cmp_table.setSortingEnabled(True)
        self._cmp_table.setMaximumHeight(200)
        mv.addWidget(self._cmp_table)

        self._nc_fig = Figure(figsize=(8, 2.4), tight_layout=True)
        self._nc_canvas = FigureCanvas(self._nc_fig)
        self._nc_canvas.setMinimumHeight(240)
        mv.addWidget(self._nc_canvas)
        self._result_tabs.addTab(cmp_container, "Compare")

        self._seq_combo.currentIndexChanged.connect(self._on_seq_changed)
        self._aa_filter.textChanged.connect(self._apply_aa_filter)
        self._codon_table.horizontalHeader().sectionClicked.connect(
            lambda _: self._apply_aa_filter(self._aa_filter.text())
        )
        self._chk_show_stop.stateChanged.connect(
            lambda _: self._apply_aa_filter(self._aa_filter.text())
        )
        self._chk_hide_zero.stateChanged.connect(
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
            path = os.path.normpath(urls[0].toLocalFile())
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

    def _clear_all(self):
        """Clear the input and reset all result views."""
        self._input_text.clear()
        self._results = []
        self._skipped_count = 0
        self._current_seq_idx = 0
        self._seq_combo.blockSignals(True)
        self._seq_combo.clear()
        self._seq_combo.blockSignals(False)
        self._seq_selector_row.setVisible(False)
        self._stats_table.setRowCount(0)
        self._top10_table.setRowCount(0)
        self._codon_table.setRowCount(0)
        self._cmp_table.setRowCount(0)
        for fig, canvas in (
            (self._rscu_fig, self._rscu_canvas),
            (self._gc_fig, self._gc_canvas),
            (self._nc_fig, self._nc_canvas),
        ):
            fig.clear()
            canvas.draw_idle()
        self._btn_export_csv.setEnabled(False)
        self._btn_export_plot.setEnabled(False)
        self._set_status("Cleared")

    def _set_status(self, msg: str):
        self._status_label.setText(msg)
        if self._status_cb:
            self._status_cb(msg, 4000)

    def _update_export_plot_state(self, *_args):
        """Enable Export Plot only when a chart tab is active with results."""
        self._btn_export_plot.setEnabled(
            bool(self._results) and self._result_tabs.currentIndex() >= 2
        )

    def _export_plot(self):
        """Save the currently visible chart (RSCU / GC / Comparison) as an image."""
        figs = {2: self._rscu_fig, 3: self._gc_fig, 4: self._nc_fig}
        fig = figs.get(self._result_tabs.currentIndex())
        if fig is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Plot",
            "codon_usage.png",
            "PNG Images (*.png);;PDF Files (*.pdf);;SVG Files (*.svg)",
        )
        if path:
            try:
                fig.savefig(path, dpi=150, bbox_inches="tight", pad_inches=0.15)
                self._set_status(f"Plot saved: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

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
        self._btn_export_csv.setEnabled(False)
        self._set_status("Analyzing...")

        self._thread = QThread(self)
        self._worker = _Worker(text, table_id, cai_ref, frame_offset)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.skipped.connect(self._on_skipped)
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

        self._btn_run.setEnabled(True)
        self._btn_export_csv.setEnabled(True)

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
        parts = [f"{len(results)} sequence(s) analyzed"]
        if self._skipped_count:
            parts.append(f"{self._skipped_count} skipped (ambiguous bases)")
        if short:
            parts.append(f"{len(short)} with <100 codons (RSCU/ENC may be unreliable)")
        self._set_status("Done — " + "; ".join(parts) + ".")
        self._update_export_plot_state()

    def _on_skipped(self, count: int):
        self._skipped_count = count

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
            (
                "Rare Codons (RSCU < 0.3)",
                (
                    f"{r['rare_codons']} ({r['rare_codons'] / r['total_codons'] * 100:.1f}%)"
                    if r["total_codons"]
                    else "0 (0.0%)"
                ),
            ),
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

        self._codon_table.setSortingEnabled(True)
        self._apply_aa_filter(self._aa_filter.text())

    def _apply_aa_filter(self, text: str):
        q = self._parse_aa_query(text)
        show_stop = self._chk_show_stop.isChecked()
        hide_zero = self._chk_hide_zero.isChecked()
        for row in range(self._codon_table.rowCount()):
            aa_item = self._codon_table.item(row, 1)
            if not aa_item:
                continue
            aa = aa_item.text().upper()
            if aa == "STOP" and not show_stop:
                self._codon_table.setRowHidden(row, True)
                continue
            hide = bool(q) and aa not in q
            if not hide and hide_zero:
                count_item = self._codon_table.item(row, 2)
                hide = count_item is not None and count_item.text() == "0"
            self._codon_table.setRowHidden(row, hide)

    def _parse_aa_query(self, text: str) -> set:
        """Parse the AA filter into a set of one-letter codes.

        Accepts one-letter codes, three-letter codes and comma/space separated
        lists, e.g. 'L', 'Leu', 'L,M' or 'leu, met'.
        """
        codes: set = set()
        for token in re.split(r"[,;\s]+", text.strip()):
            token = token.upper()
            if not token:
                continue
            if token == "STOP":
                codes.add("STOP")
            elif len(token) == 3 and token in _AA_3_TO_1:
                codes.add(_AA_3_TO_1[token])
            else:
                codes.add(token)
        return codes

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

        rows = self._results
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["== Summary =="])
                writer.writerow([
                    "Sequence",
                    "Length_nt",
                    "Codons",
                    "ENC",
                    "CAI",
                    "GC_pct",
                    "GC1_pct",
                    "GC2_pct",
                    "GC3_pct",
                    "GC12_pct",
                    "Rare_Codons",
                    "Rare_Codons_pct",
                ])
                for r in rows:
                    cai = f"{r['cai']:.4f}" if r.get("cai") is not None else "N/A"
                    rare_pct = (
                        f"{r['rare_codons'] / r['total_codons'] * 100:.2f}"
                        if r["total_codons"]
                        else "0.00"
                    )
                    writer.writerow([
                        r["header"],
                        r["seq_len"],
                        r["total_codons"],
                        f"{r['enc']:.2f}",
                        cai,
                        f"{r['gc_all']:.2f}",
                        f"{r['gc1']:.2f}",
                        f"{r['gc2']:.2f}",
                        f"{r['gc3']:.2f}",
                        f"{r['gc12']:.2f}",
                        r["rare_codons"],
                        rare_pct,
                    ])
                writer.writerow([])
                writer.writerow(["== Codon Usage =="])
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
            self._set_status(f"Exported: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _show_help(self):
        help_text = self.tr(
            "<h2>Codon Usage Analysis &mdash; Comprehensive Codon Bias Toolkit</h2>"
            "<p><b>What does this tool do?</b><br>"
            "It performs a complete codon usage analysis of protein-coding sequences (CDS). "
            "The tool computes key metrics including <b>RSCU</b> (Relative Synonymous Codon Usage), "
            "<b>ENC</b> (Effective Number of Codons), <b>CAI</b> (Codon Adaptation Index), "
            "and GC-content at each codon position. Results are presented across five "
            "interactive tabs with sortable tables and publication-ready "
            "Matplotlib charts.</p>"
            "<h3>Quick Start</h3>"
            "<ol>"
            "<li>Paste one or more CDS sequences in FASTA format into the input editor, or click <b>Load File</b></li>"
            "<li>Select the appropriate <b>Genetic Code</b> for your organism (default: Standard)</li>"
            "<li>Optionally choose a <b>CAI Reference Organism</b> to compute the Codon Adaptation Index</li>"
            "<li>Select a <b>Reading Frame</b> (default +1 works for most CDS inputs)</li>"
            "<li>Click <b>Run</b> (bottom right) and browse the five result tabs</li>"
            "</ol>"
            "<h3>Key Metrics Explained</h3>"
            "<table border='0' cellpadding='4' cellspacing='2'>"
            "<tr><td><b>Metric</b></td><td><b>Meaning</b></td><td><b>Interpretation</b></td></tr>"
            "<tr><td>RSCU</td><td>Relative Synonymous Codon Usage</td><td>Values &gt; 1 = over-represented, &lt; 1 = under-represented; ideal = 1.0 (no bias)</td></tr>"
            "<tr><td>ENC</td><td>Effective Number of Codons</td><td>Ranges 20 (extreme bias) to 61 (no bias); values ≤ 35 indicate strong codon bias</td></tr>"
            "<tr><td>CAI</td><td>Codon Adaptation Index</td><td>Ranges 0–1; higher values mean better translation-adaptation to the reference organism</td></tr>"
            "<tr><td>Rare codons</td><td>Codons with RSCU &lt; 0.3</td><td>Many rare codons can bottleneck protein expression in heterologous hosts</td></tr>"
            "<tr><td>GC / GC3</td><td>Overall GC% and GC% at 3rd codon position</td><td>GC3 is a sensitive indicator of mutational bias; low GC3 often correlates with translational selection</td></tr>"
            "</table>"
            "<h3>Result Tabs</h3>"
            "<ul>"
            "<li><b>Summary</b> — key statistics for the current sequence, plus a top-10 most-used codons table</li>"
            "<li><b>Codons</b> — full 64-codon table with counts, frequency per 1000 and RSCU. Filter by amino acid (one- or three-letter, e.g. L or Leu), hide zero-count codons, or toggle stop codons</li>"
            "<li><b>RSCU</b> — grouped bar chart of RSCU values per amino acid, with one bar per synonymous codon</li>"
            "<li><b>GC/Neutrality</b> — stacked GC1/GC2/GC3 bars for each sequence, plus a GC12 vs GC3 neutrality plot (slope ≈ 1 = neutral evolution; slope &lt; 1 = selective constraint)</li>"
            "<li><b>Compare</b> — per-sequence table (ENC, CAI, GC%, GC3%) and the Nc plot (ENC vs GC3) to detect mutational vs selective pressure</li>"
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
            "in a reference organism. Built-in references: <b>Human</b>, <b>E. coli K-12</b>, <b>S. cerevisiae</b>, "
            "<b>C. elegans</b>, <b>A. thaliana</b> and <b>M. musculus</b> (RSCU tables derived from genome-wide codon "
            "usage data). CAI values &gt; 0.8 suggest good adaptation to the reference.</p>"
            "<h3>Reading Frames</h3>"
            "<p>The tool translates your sequence in one of three forward reading frames. Use <b>Frame +1</b> for "
            "canonical CDS input; try frames +2 and +3 if the sequence may be misaligned or contains alternative start sites.</p>"
            "<h3>Tips</h3>"
            "<ul>"
            "<li>Click <b>Example</b> to load a real bacterial spoT CDS for a quick trial</li>"
            "<li>The <b>Codons</b> table supports sorting — click any column header to reorder rows</li>"
            "<li>Use the amino acid filter (e.g. &quot;L&quot;, &quot;Leu&quot; or &quot;L,M&quot;) to focus on specific codon families; <b>Hide zero-count codons</b> is on by default</li>"
            "<li>Multi-sequence input enables the <b>Compare</b> tab with per-sequence summaries and the Nc plot</li>"
            "<li>Use <b>Export Plot</b> to save the current chart (RSCU / GC/Neutrality / Compare) as PNG, PDF or SVG</li>"
            "<li><b>Clear</b> resets the input and all result views</li>"
            "<li>Export data as CSV &mdash; the file contains a per-sequence summary and the full codon usage table</li>"
            "<li>For whole-genome codon usage analysis, concatenate CDS sequences from the same genome into a single FASTA file</li>"
            "</ul>"
            "<h3>Related Tools in SeqSketch</h3>"
            "<ul>"
            "<li><b>Translate</b> — translate DNA to protein (also supports alternative genetic codes)</li>"
            "<li><b>ORF Finder</b> — locate open reading frames in genomic DNA</li>"
            "<li><b>GC Content / GC Skew Plot</b> — whole-sequence GC analysis with sliding windows</li>"
            "</ul>"
        )
        from PyQt6.QtCore import Qt as QtCore
        from PyQt6.QtWidgets import (
            QHBoxLayout,
            QLabel,
            QPushButton,
            QScrollArea,
            QVBoxLayout,
        )

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("Help - Codon Usage Analysis"))
        dlg.resize(640, 520)
        dlg.setMinimumSize(400, 300)
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
