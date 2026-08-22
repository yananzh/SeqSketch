"""Cloning Primer Design Tab — restriction-site-flanked PCR primers for subcloning."""

from __future__ import annotations

import os
import re
from typing import Any, Optional

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from utils.common_components import BaseTabWidget, unify_status_button_sizes
from utils.example_data import load_example_text

# (name, recognition site, 0-based cut index on the 5'->3' strand, protection bases)
CLONING_ENZYMES: list[tuple[str, str, int, int]] = [
    ("EcoRI", "GAATTC", 1, 2),
    ("BamHI", "GGATCC", 1, 2),
    ("SalI", "GTCGAC", 1, 4),
    ("NotI", "GCGGCCGC", 2, 4),
    ("XhoI", "CTCGAG", 1, 3),
    ("HindIII", "AAGCTT", 1, 2),
    ("KpnI", "GGTACC", 5, 3),
    ("SacI", "GAGCTC", 5, 3),
    ("NheI", "GCTAGC", 1, 2),
    ("SpeI", "ACTAGT", 1, 2),
    ("SacII", "CCGCGG", 4, 2),
    ("EagI", "CGGCCG", 1, 2),
    ("PstI", "CTGCAG", 5, 3),
    ("SmaI", "CCCGGG", 3, 3),
    ("BglII", "AGATCT", 1, 2),
    ("XbaI", "TCTAGA", 1, 3),
]

NO_ENZYME_LABEL = "None"

_IUPAC = {
    "A": "A",
    "C": "C",
    "G": "G",
    "T": "T",
    "R": "[AG]",
    "Y": "[CT]",
    "M": "[AC]",
    "K": "[GT]",
    "S": "[GC]",
    "W": "[AT]",
    "B": "[CGT]",
    "D": "[AGT]",
    "H": "[ACT]",
    "V": "[ACG]",
    "N": "[ACGT]",
}

try:
    import primer3 as _primer3

    _HAS_PRIMER3 = True
except ImportError:
    _primer3 = None  # type: ignore[assignment]
    _HAS_PRIMER3 = False

_COMPLEMENT = str.maketrans(
    "ACGTRYMKBDHVNacgtrymkbdhvn", "TGCAYRKMVHDBNtgcayrkmvhdbn"
)


def normalize_sequence(raw: str) -> str:
    """Strip FASTA headers, whitespace and lowercase from a pasted sequence."""
    seq_lines: list[str] = []
    for line in raw.strip().splitlines():
        line = line.strip()
        if line and not line.startswith(">"):
            seq_lines.append(line)
    return "".join(seq_lines).replace(" ", "").replace("\r", "").upper()


def count_fasta_records(text: str) -> int:
    """Count FASTA '>' header lines in pasted or uploaded text."""
    return sum(1 for line in text.splitlines() if line.strip().startswith(">"))


def complement(seq: str) -> str:
    return seq.translate(_COMPLEMENT)


def reverse_complement(seq: str) -> str:
    return complement(seq)[::-1]


def _site_regex(site: str) -> re.Pattern[str]:
    return re.compile("".join(_IUPAC[base] for base in site.upper()))


def find_site_positions(seq: str, site: str) -> list[tuple[int, str]]:
    """Locate a recognition site on both strands of a linear sequence.

    Returns (0-based position, strand) pairs; palindrome sites found at the
    same position on both strands are reported once per strand.
    """
    hits: list[tuple[int, str]] = []
    pattern = _site_regex(site)
    for match in pattern.finditer(seq):
        hits.append((match.start(), "fwd"))
    rc_seq = reverse_complement(seq)
    for match in pattern.finditer(rc_seq):
        pos = len(seq) - match.start() - len(site)
        hits.append((pos, "rev"))
    return hits


def gc_percent(seq: str) -> float:
    if not seq:
        return 0.0
    seq = seq.upper()
    return 100.0 * (seq.count("G") + seq.count("C")) / len(seq)


def calc_tm(seq: str, mv: float = 50.0, dv: float = 2.0) -> Optional[float]:
    """Nearest-neighbour Tm via primer3 when available; Wallace rule otherwise."""
    if not seq:
        return None
    if _HAS_PRIMER3:
        return round(_primer3.calc_tm(seq, mv_conc=mv, dv_conc=dv), 1)
    return round(
        2.0 * (seq.count("A") + seq.count("T")) + 4.0 * (seq.count("G") + seq.count("C")),
        1,
    )


def calc_dimer_dg(seq: str, mv: float = 50.0, dv: float = 2.0) -> Optional[float]:
    """Self-dimer free energy (kcal/mol) via primer3; None when unavailable."""
    if not seq or not _HAS_PRIMER3:
        return None
    try:
        return round(_primer3.calc_homodimer(seq, mv_conc=mv, dv_conc=dv).dg, 1)
    except Exception:
        return None


def calc_heterodimer_dg(
    seq1: str, seq2: str, mv: float = 50.0, dv: float = 2.0
) -> Optional[float]:
    """Cross-dimer free energy (kcal/mol) between two primers via primer3."""
    if not seq1 or not seq2 or not _HAS_PRIMER3:
        return None
    try:
        return round(
            _primer3.calc_heterodimer(seq1, seq2, mv_conc=mv, dv_conc=dv).dg, 1
        )
    except Exception:
        return None


def _core_warnings(core: str, last: str, clamp_3: bool) -> list[str]:
    warnings: list[str] = []
    if re.search(r"(A{4,}|C{4,}|G{4,}|T{4,})", core):
        warnings.append("homopolymer run (4+) in core")
    gc = gc_percent(core)
    if gc < 35 or gc > 65:
        warnings.append(f"GC% {gc:.0f} outside 35-65%")
    if "N" in core:
        warnings.append("ambiguous base N in core")
    if clamp_3 and last in "AT":
        warnings.append("3' end not G/C (no in-range length satisfies clamp)")
    return warnings


def design_cloning_primers(
    sequence: str,
    enzyme_5: Optional[tuple[str, str, int, int]],
    enzyme_3: Optional[tuple[str, str, int, int]],
    core_len: int = 20,
    target_tm: float = 60.0,
    mv: float = 50.0,
    dv: float = 2.0,
    clamp_3: bool = False,
    shift_range: int = 3,
    preserve_frame: bool = False,
) -> dict[str, Any]:
    """Design restriction-site-flanked cloning primers for an insert.

    The forward primer core starts at insert base 1 and the reverse primer
    core covers the 3' end of the insert; core lengths are searched in
    ``core_len +/- shift_range`` to approach the target Tm.
    """
    seq = normalize_sequence(sequence)
    n = len(seq)
    if n < 2 * core_len:
        raise ValueError(
            f"Insert is too short ({n} nt) for two {core_len} nt primer cores."
        )

    min_len = max(15, core_len - shift_range)
    max_len = min(30, core_len + shift_range, n // 2)
    if min_len > max_len:
        raise ValueError("Sequence too short for the chosen primer length.")

    def pick_core(is_fwd: bool) -> tuple[str, float]:
        best: tuple[float, str, float] | None = None
        for length in range(min_len, max_len + 1):
            if is_fwd:
                core = seq[:length]
            else:
                core = reverse_complement(seq[n - length :])
            tm = calc_tm(core, mv, dv) or 0.0
            penalty = 10.0 if clamp_3 and core[-1] in "AT" else 0.0
            score = abs(tm - target_tm) + penalty
            if best is None or score < best[0]:
                best = (score, core, tm)
        return best[1], best[2]

    fwd_core, fwd_tm = pick_core(True)
    rev_core, rev_tm = pick_core(False)

    def build_overhang(enzyme: Optional[tuple[str, str, int, int]]) -> tuple[str, int]:
        if enzyme is None:
            return "", 0
        _name, site, cut, prot = enzyme
        added = 0
        if preserve_frame:
            remnant = len(site) - cut
            added = (3 - remnant % 3) % 3
        return "G" * prot + site + "A" * added, added

    overhang_5, added_5 = build_overhang(enzyme_5)
    overhang_3, added_3 = build_overhang(enzyme_3)

    fwd_full = overhang_5 + fwd_core
    rev_full = overhang_3 + rev_core

    global_warnings: list[str] = []
    seen_positions: set[int] = set()
    for enzyme in (enzyme_5, enzyme_3):
        if enzyme is None:
            continue
        name, site = enzyme[0], enzyme[1]
        for pos, strand in find_site_positions(seq, site):
            if pos in seen_positions:
                continue
            seen_positions.add(pos)
            global_warnings.append(
                f"{name} cuts inside the insert at position {pos + 1} ({strand} strand)"
            )

    def primer_row(
        label: str,
        full: str,
        core: str,
        overhang: str,
        tm: float,
        added: int,
        is_fwd: bool,
    ) -> dict[str, Any]:
        flags = _core_warnings(core, core[-1], clamp_3)
        if added:
            flags.insert(0, f"{added} frame base(s) added after site")
        return {
            "label": label,
            "full": full,
            "core": core,
            "overhang": overhang,
            "tm_core": tm,
            "tm_full": calc_tm(full, mv, dv),
            "gc": gc_percent(core),
            "dimer": calc_dimer_dg(core, mv, dv),
            "flags": flags,
            "is_fwd": is_fwd,
        }

    tm_diff = abs(fwd_tm - rev_tm)
    if tm_diff > 2.0:
        global_warnings.append(
            f"Core Tm difference {tm_diff:.1f}°C between fwd and rev exceeds 2°C"
        )
    cross_dimer = calc_heterodimer_dg(fwd_core, rev_core, mv, dv)
    if cross_dimer is not None and cross_dimer <= -6.0:
        global_warnings.append(
            f"Cross-dimer between fwd and rev cores detected (ΔG={cross_dimer:.1f})"
        )

    name_5 = enzyme_5[0] if enzyme_5 else "None"
    name_3 = enzyme_3[0] if enzyme_3 else "None"
    return {
        "fwd": primer_row(
            f"Fwd ({name_5})", fwd_full, fwd_core, overhang_5, fwd_tm, added_5, True
        ),
        "rev": primer_row(
            f"Rev ({name_3})", rev_full, rev_core, overhang_3, rev_tm, added_3, False
        ),
        "warnings": global_warnings,
        "tm_diff": round(tm_diff, 1),
        "cross_dimer": cross_dimer,
    }


class CloningPrimerTab(BaseTabWidget):
    """Design restriction-site-flanked PCR primers for subcloning an insert."""

    def __init__(self, parent=None):
        super().__init__("Cloning Primer Design", "sequence")
        self._last_design: Optional[dict[str, Any]] = None
        self._last_export_dir: Optional[str] = None
        self._setup_parameter_ui()
        self._setup_results_table()
        self._setup_input_buttons()
        self.input_text.setPlaceholderText(
            self.tr(
                "Select or drag & drop a file, or paste a sequence — "
                "one FASTA record only"
            )
        )
        # The designed-primers table is the only result view, so drop the
        # shared "Output Result" group from the sequence-mode base layout.
        self.content_area.removeWidget(self.output_group)
        self.output_group.hide()
        unify_status_button_sizes(self)

    def _setup_parameter_ui(self):
        grp = QGroupBox(self.tr("Cloning Parameters"))
        grp.setFlat(True)
        grid = QGridLayout(grp)
        grid.setContentsMargins(8, 16, 8, 4)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)

        # One row spanning the full group width: each parameter occupies an
        # equal quarter (label + control), with controls stretching to fill.
        def param_pair(label_text: str, widget, col: int):
            cell = QHBoxLayout()
            cell.setContentsMargins(0, 0, 0, 0)
            cell.setSpacing(8)
            label = QLabel(label_text)
            label.setToolTip(widget.toolTip())
            cell.addWidget(label)
            # One shared control minimum (sized to the combo's content hint)
            # keeps the quarters even when the row nears its minimum width.
            widget.setMinimumWidth(self.enz5_combo.minimumSizeHint().width())
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            cell.addWidget(widget, 1)
            grid.addLayout(cell, 0, col)
            grid.setColumnStretch(col, 1)

        self.enz5_combo = QComboBox()
        self._fill_enzyme_combo(self.enz5_combo, default_index=0)
        self.enz5_combo.setToolTip(
            self.tr("Restriction site added to the 5' end; None = blunt / TA ligation")
        )
        param_pair(self.tr("5' Enzyme"), self.enz5_combo, 0)

        self.enz3_combo = QComboBox()
        self._fill_enzyme_combo(self.enz3_combo, default_index=1)
        self.enz3_combo.setToolTip(
            self.tr("Restriction site added to the 3' end; None = blunt / TA ligation")
        )
        param_pair(self.tr("3' Enzyme"), self.enz3_combo, 1)

        self.core_len_spin = QSpinBox()
        self.core_len_spin.setRange(15, 30)
        self.core_len_spin.setValue(20)
        self.core_len_spin.setSuffix(self.tr(" nt"))
        self.core_len_spin.setToolTip(
            self.tr("Gene-specific primer length (without the restriction overhang)")
        )
        param_pair(self.tr("Core (nt)"), self.core_len_spin, 2)

        self.target_tm_spin = QDoubleSpinBox()
        self.target_tm_spin.setRange(50.0, 70.0)
        self.target_tm_spin.setDecimals(0)
        self.target_tm_spin.setSingleStep(1)
        self.target_tm_spin.setValue(60.0)
        self.target_tm_spin.setSuffix(" °C")
        self.target_tm_spin.setToolTip(
            self.tr(
                "Target melting temperature (°C) for the primer cores; "
                "the tool searches ±3 nt around the core length to approach it"
            )
        )
        param_pair(self.tr("Tm (°C)"), self.target_tm_spin, 3)

        self._param_layout.addWidget(grp)

    @staticmethod
    def _fill_enzyme_combo(combo: QComboBox, default_index: int) -> None:
        for entry in CLONING_ENZYMES:
            combo.addItem(entry[0], entry)
        combo.addItem(NO_ENZYME_LABEL, None)
        combo.setCurrentIndex(default_index)

    def _setup_results_table(self):
        table_grp = QGroupBox(self.tr("Designed Primers"))
        table_grp.setFlat(True)
        tl = QVBoxLayout(table_grp)
        tl.setContentsMargins(0, 16, 0, 4)
        tl.setSpacing(2)

        self.results_table = QTableWidget(0, 9)
        self.results_table.setHorizontalHeaderLabels([
            self.tr("Primer"),
            self.tr("Full Sequence (5'→3')"),
            self.tr("Length (nt)"),
            self.tr("Overhang"),
            self.tr("Core"),
            self.tr("Tm (°C)"),
            self.tr("GC (%)"),
            self.tr("Dimer ΔG"),
            self.tr("Flags"),
        ])
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        self.results_table.setMinimumHeight(120)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.itemDoubleClicked.connect(self._copy_full_sequence)
        tl.addWidget(self.results_table)

        self.export_table_btn = QPushButton(self.tr("Export Table"))
        self.export_table_btn.setToolTip(
            self.tr("Save the primer table as Excel, CSV or TSV")
        )
        self.export_table_btn.clicked.connect(self._export_table)
        self.export_table_btn.setFixedWidth(110)
        self.status_layout.insertWidget(
            self.status_layout.indexOf(self.run_btn) + 1, self.export_table_btn
        )

        self.result_folder_btn = QPushButton(self.tr("Result Folder"))
        self.result_folder_btn.setToolTip(
            self.tr("Open the folder containing the last exported table")
        )
        self.result_folder_btn.clicked.connect(self._open_result_folder)
        self.result_folder_btn.setFixedWidth(110)
        self.status_layout.insertWidget(
            self.status_layout.indexOf(self.export_table_btn) + 1, self.result_folder_btn
        )
        # Match other tabs: one-word buttons 90 px, two-word buttons 110 px.
        self.help_btn.setFixedWidth(90)

        self.content_area.addWidget(table_grp)

    def _setup_input_buttons(self):
        """Wire the Example button and pin Example + Upload to one stretched
        row at the bottom of the input group."""
        self.example_btn = QPushButton(self.tr("Example"))
        self.example_btn.setToolTip(
            self.tr("Load a synthetic insert example (no internal EcoRI/BamHI sites)")
        )
        self.example_btn.clicked.connect(self._load_example)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        for btn in (self.example_btn, self.upload_btn):
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row.addWidget(btn)

        input_layout = self.input_group.layout()
        input_layout.removeWidget(self.upload_btn)
        input_layout.addLayout(row)

    def _load_example(self):
        text = load_example_text("dna", "cloning_insert_example.fasta")
        if not text:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. Please check your installation."),
            )
            return
        self.input_text.setPlainText(text)
        self.enz5_combo.setCurrentIndex(0)  # EcoRI
        self.enz3_combo.setCurrentIndex(1)  # BamHI
        self.show_status(self.tr("Example loaded"))

    def _reject_multi_record(self, text: str) -> bool:
        """Warn and return True when the text holds more than one FASTA record."""
        if count_fasta_records(text) <= 1:
            return False
        QMessageBox.warning(
            self,
            self.tr("Unsupported Input"),
            self.tr(
                "Only one FASTA sequence is supported — "
                "multi-sequence input is not allowed."
            ),
        )
        return True

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select sequence file"),
            "",
            "FASTA/TXT (*.fasta *.fa *.fas *.txt);;All Files (*)",
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            QMessageBox.warning(self, self.tr("File Read Error"), str(e))
            return
        if self._reject_multi_record(content):
            return
        self.input_text.setPlainText(content)
        self.input_hint.setText(self.tr(f"Loaded file: {file_path}"))

    def _drop_event(self, event):
        urls = event.mimeData().urls()
        if not urls or not urls[0].toLocalFile():
            event.ignore()
            return
        file_path = urls[0].toLocalFile()
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            self.show_status(self.tr(f"Error loading file: {e}"))
            event.ignore()
            return
        if self._reject_multi_record(content):
            event.ignore()
            return
        self.input_text.setPlainText(content)
        self.input_hint.setText(self.tr(f"Loaded file: {file_path}"))
        event.acceptProposedAction()

    def run(self):
        raw = self.input_text.toPlainText()
        if not raw.strip():
            self.show_status(self.tr("Please paste an insert sequence first."))
            return
        if count_fasta_records(raw) > 1:
            self.show_status(
                self.tr(
                    "Only one FASTA sequence is supported — "
                    "multi-sequence input is not allowed."
                )
            )
            return
        seq = normalize_sequence(raw)
        if not seq or not all(base in "ACGTUN" for base in seq):
            self.show_status(
                self.tr("Invalid sequence: only A/C/G/T/U/N letters are allowed.")
            )
            return
        same_enzyme = (
            self.enz5_combo.currentData() is not None
            and self.enz5_combo.currentData() is self.enz3_combo.currentData()
        )
        try:
            design = design_cloning_primers(
                seq,
                self.enz5_combo.currentData(),
                self.enz3_combo.currentData(),
                core_len=self.core_len_spin.value(),
                target_tm=self.target_tm_spin.value(),
            )
        except ValueError as exc:
            self.show_status(self.tr(str(exc)))
            return
        if same_enzyme:
            design["warnings"].append(
                self.tr("Same enzyme on both ends (non-directional ligation)")
            )
        self._last_design = design
        self._fill_table(design)
        self._warn_internal_cut_sites(design)
        self.show_status(self.tr("Designed 2 primers"))

    def _warn_internal_cut_sites(self, design: dict[str, Any]) -> None:
        """Pop up a warning when a chosen enzyme cuts inside the insert."""
        hits = [w for w in design.get("warnings", []) if "cuts inside the insert" in w]
        if not hits:
            return
        QMessageBox.warning(
            self,
            self.tr("Internal Cut Site Detected"),
            self.tr("A selected restriction enzyme cuts inside the insert:\n")
            + "\n".join(hits),
        )

    def _fill_table(self, design: dict[str, Any]) -> None:
        rows = [design["fwd"], design["rev"]]
        self.results_table.setRowCount(len(rows))
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.TypeWriter)
        for row, data in enumerate(rows):
            self.results_table.setItem(row, 0, QTableWidgetItem(data["label"]))
            full_item = QTableWidgetItem(data["full"])
            full_item.setFont(mono)
            full_item.setToolTip(self.tr("Double-click to copy this sequence"))
            self.results_table.setItem(row, 1, full_item)
            self.results_table.setItem(row, 2, QTableWidgetItem(str(len(data["full"]))))
            overhang_item = QTableWidgetItem(data["overhang"])
            overhang_item.setFont(mono)
            self.results_table.setItem(row, 3, overhang_item)
            core_item = QTableWidgetItem(data["core"])
            core_item.setFont(mono)
            self.results_table.setItem(row, 4, core_item)
            tm_core = data["tm_core"]
            tm_full = data["tm_full"]
            tm_item = QTableWidgetItem(f"{tm_core:.1f}" if tm_core else "-")
            if tm_full:
                tm_item.setToolTip(
                    self.tr(f"Full primer Tm: {tm_full:.1f} °C (core {tm_core:.1f} °C)")
                )
            self.results_table.setItem(row, 5, tm_item)
            gc_item = QTableWidgetItem(f"{data['gc']:.1f}")
            gc_item.setToolTip(
                self.tr("GC content of the primer core; 35-65% is recommended")
            )
            self.results_table.setItem(row, 6, gc_item)
            dimer = data["dimer"]
            self.results_table.setItem(
                row, 7, QTableWidgetItem(f"{dimer:.1f}" if dimer is not None else "-")
            )
            self.results_table.setItem(row, 8, QTableWidgetItem("; ".join(data["flags"])))

    def _copy_full_sequence(self, item) -> None:
        if item.column() == 1 and item.text():
            QApplication.clipboard().setText(item.text())
            self.show_status(self.tr("Copied to clipboard"))

    def _export_table(self) -> None:
        """Export the primer table as Excel, CSV or TSV."""
        if self.results_table.rowCount() == 0:
            self.show_status(self.tr("Nothing to export — run a design first."))
            return
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            self.tr("Export Primers Table"),
            "primers_table.xlsx",
            self.tr("Excel (*.xlsx);;CSV (*.csv);;TSV (*.tsv)"),
        )
        if not file_path:
            return
        headers = [
            self.results_table.horizontalHeaderItem(c).text()
            for c in range(self.results_table.columnCount())
        ]
        rows = [
            [
                self.results_table.item(r, c).text()
                if self.results_table.item(r, c) is not None
                else ""
                for c in range(self.results_table.columnCount())
            ]
            for r in range(self.results_table.rowCount())
        ]
        try:
            if "Excel" in selected_filter:
                file_path = os.path.splitext(file_path)[0] + ".xlsx"
                self._export_excel(file_path, headers, rows)
            elif "CSV" in selected_filter:
                file_path = os.path.splitext(file_path)[0] + ".csv"
                self._export_delimited(file_path, headers, rows, ",")
            else:
                file_path = os.path.splitext(file_path)[0] + ".tsv"
                self._export_delimited(file_path, headers, rows, "\t")
        except Exception as exc:
            QMessageBox.warning(
                self, self.tr("Export Failed"), self.tr(f"Could not export: {exc}")
            )
            return
        self._last_export_dir = os.path.dirname(os.path.abspath(file_path))
        self.show_status(self.tr(f"Exported table to: {file_path}"))

    def _open_result_folder(self) -> None:
        if not self._last_export_dir or not os.path.isdir(self._last_export_dir):
            self.show_status(self.tr("No exported file yet — use Export Table first."))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_export_dir))

    @staticmethod
    def _export_delimited(
        path: str, headers: list[str], rows: list[list[str]], delimiter: str
    ) -> None:
        import csv

        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=delimiter)
            writer.writerow(headers)
            writer.writerows(rows)

    @staticmethod
    def _export_excel(path: str, headers: list[str], rows: list[list[str]]) -> None:
        import pandas as pd

        pd.DataFrame(rows, columns=headers).to_excel(path, index=False)

    def clear(self):
        self._last_design = None
        if hasattr(self, "results_table"):
            self.results_table.setRowCount(0)
        super().clear()

    def show_help(self):
        self.show_help_dialog(
            self.tr("Cloning Primer Design - Help"),
            self.tr(
                """
<h2>Cloning Primer Design</h2>

<p><b>What does this tool do?</b><br>
Designs PCR primers that add restriction sites (with protective bases) to the
ends of an insert for standard restriction-ligation cloning, or plain
gene-specific primers for blunt / TA ligation when no enzyme is chosen.</p>

<h3>Primer layout</h3>
<pre>Fwd:  [protective bases][site][insert 5' end ~20 nt]
Rev:  [protective bases][rc-site][rc of insert 3' end ~20 nt]</pre>

<h3>Quick Start</h3>
<ol>
<li>Paste or upload a single insert sequence (FASTA or raw DNA, one record
    only; starts with the ATG for a coding insert).</li>
<li>Pick a 5' and a 3' restriction enzyme, or choose <b>None</b> on either or
    both ends for blunt / TA ligation (no overhang added).</li>
<li>Set the core length and target Tm, then click <b>Run</b>.</li>
<li>Read the two designed primers in the <b>Full Sequence (5'&rarr;3')</b>
    column and order them as-is.</li>
</ol>

<h3>Parameter Guide</h3>
<table border='0' cellpadding='4' cellspacing='2'>
<tr><td><b>Core Length (nt)</b></td><td>Gene-specific annealing region without
    the restriction overhang. The tool searches &plusmn;3 nt around this value
    to approach the target Tm.</td></tr>
<tr><td><b>Target Tm (&deg;C)</b></td><td>Melting temperature the primer cores
    are optimised towards. Uses the primer3 nearest-neighbour model under
    50 mM salt / 2 mM Mg&sup2;&plus; when installed, otherwise the Wallace rule.</td></tr>
</table>

<h3>Checks performed</h3>
<ul>
<li>Both chosen enzymes are tested for internal cut sites inside the insert
    (both strands) as part of the design process.</li>
<li>Each core is flagged for GC% outside 35-65%, homopolymer runs (4+) and
    ambiguous bases; the flags appear in the <b>Flags</b> column.</li>
</ul>

<h3>Results &amp; export</h3>
<ul>
<li>Double-click the <b>Full Sequence</b> cell to copy an orderable primer to
    the clipboard; hover the <b>Tm</b> or <b>GC</b> cells for details.</li>
<li><b>Export Table</b> saves the primer table as Excel, CSV or TSV.</li>
</ul>

<h3>Tips</h3>
<ul>
<li>Start from the <b>Example</b> button to see a clean workflow.</li>
<li>Choose <b>None</b> on both ends when your vector strategy uses blunt / TA
    ligation without restriction sites.</li>
<li>Verify the insert has no internal cut sites for the enzymes you plan to
    use.</li>
</ul>
""",
            ),
            640,
            560,
        )
