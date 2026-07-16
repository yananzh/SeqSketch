"""Protease Cleavage Map Tab — predict proteolytic digestion fragments."""

from PyQt6.QtWidgets import (
    QMessageBox,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QSpinBox,
    QGroupBox,
    QScrollArea,
    QCheckBox,
    QTextEdit,
    QPushButton,
    QFileDialog,
)
from PyQt6.QtCore import Qt
from utils.common_components import BaseTabWidget, apply_sequence_editor_style
from utils.example_data import load_example_text
import csv
import re

# ── Protease definitions ─────────────────────────────────────────────────────
# Each entry: (display_name, cleavage_rule)
# cleavage_rule is a callable: (seq: str) -> list of cut positions (0-based,
# position AFTER the cut, i.e. the index of the first residue of the next fragment)

AA = "ARNDCEQGHILKMFPSTWYV"

# Amino acid masses (monoisotopic)
AA_MASS = {
    "A": 71.03711,
    "R": 156.10111,
    "N": 114.04293,
    "D": 115.02694,
    "C": 103.00919,
    "E": 129.04259,
    "Q": 128.05858,
    "G": 57.02146,
    "H": 137.05891,
    "I": 113.08406,
    "L": 113.08406,
    "K": 128.09496,
    "M": 131.04049,
    "F": 147.06841,
    "P": 97.05276,
    "S": 87.03203,
    "T": 101.04768,
    "W": 186.07931,
    "Y": 163.06333,
    "V": 99.06841,
}

H2O = 18.01056


def _cuts_after(seq, residues, block_before="P"):
    """Return cut positions (0-based, after cleavage) for residues NOT followed by block_before."""
    cuts = []
    for i, aa in enumerate(seq[:-1]):
        if aa in residues and seq[i + 1] not in block_before:
            cuts.append(i + 1)
    # Always cut at the very end to capture the terminal fragment
    cuts.append(len(seq))
    return sorted(set(cuts))


def _cuts_before(seq, residues):
    """Return cut positions (0-based, before the given residues)."""
    cuts = [0]
    for i, aa in enumerate(seq):
        if aa in residues:
            cuts.append(i)
    cuts.append(len(seq))
    return sorted(set(cuts))


PROTEASES = {
    "Trypsin": {
        "rule": lambda s: _cuts_after(s, set("KR")),
        "desc": "Cleaves C-terminal to Arg (R) and Lys (K), unless followed by Pro (P).",
    },
    "Chymotrypsin": {
        "rule": lambda s: _cuts_after(s, set("FYW"), block_before="P"),
        "desc": "Cleaves C-terminal to Phe (F), Tyr (Y), Trp (W), unless followed by Pro (P).",
    },
    "Pepsin (pH 1.3)": {
        "rule": lambda s: _cuts_before(s, set("FL")),
        "desc": "Cleaves N-terminal to Phe (F) and Leu (L) at low pH.",
    },
    "Pepsin (pH > 2)": {
        "rule": lambda s: _cuts_before(s, set("FLYW")),
        "desc": "Cleaves N-terminal to Phe (F), Leu (L), Tyr (Y), Trp (W) at higher pH.",
    },
    "CNBr": {
        "rule": lambda s: _cuts_after(s, set("M"), block_before=""),
        "desc": "Chemical cleavage C-terminal to Met (M).",
    },
    "V8 (Glu-specific)": {
        "rule": lambda s: _cuts_after(s, set("E"), block_before=""),
        "desc": "Cleaves C-terminal to Glu (E) in phosphate buffer.",
    },
    "V8 (Glu+Asp)": {
        "rule": lambda s: _cuts_after(s, set("DE"), block_before=""),
        "desc": "Cleaves C-terminal to Glu (E) and Asp (D) in bicarbonate buffer.",
    },
    "Arg-C": {
        "rule": lambda s: _cuts_after(s, set("R"), block_before=""),
        "desc": "Cleaves C-terminal to Arg (R).",
    },
    "Lys-C": {
        "rule": lambda s: _cuts_after(s, set("K"), block_before=""),
        "desc": "Cleaves C-terminal to Lys (K).",
    },
    "Asp-N": {
        "rule": lambda s: _cuts_before(s, set("D")),
        "desc": "Cleaves N-terminal to Asp (D).",
    },
}


class ProteaseCleavageTab(BaseTabWidget):
    """Protease Cleavage Map — predict fragment patterns from protease digestion."""

    def __init__(self, parent=None):
        super().__init__("Protease Cleavage Map", "sequence")
        self.run_btn.setText("Digest")
        self.run_btn.setFixedWidth(100)
        if hasattr(self, "copy_btn"):
            self.copy_btn.hide()
        if hasattr(self, "export_btn"):
            self.export_btn.hide()
        self.output_text.setReadOnly(True)
        self.output_text.setPlaceholderText("Predicted fragments will appear here...")

        self.input_hint.hide()
        self.input_text.setPlaceholderText(
            "Paste a protein sequence in FASTA format or drag-and-drop a file...\n\n"
            "Example:\n>my_protein\nMKLFVTGASRGIGRAIALRLGKDGA"
        )
        self.input_text.setMaximumHeight(100)

        self._setup_parameters()
        self._setup_drag_drop()
        self.current_results = []

        # Add Export CSV button to status row after Digest
        self.export_csv_btn = QPushButton(self.tr("Export CSV"))
        self.export_csv_btn.setFixedWidth(110)
        self.export_csv_btn.clicked.connect(self.export_csv)
        _idx = self.status_layout.indexOf(self.run_btn)
        self.status_layout.insertWidget(_idx + 1, self.export_csv_btn)

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
        """Load the bundled protein example."""
        text = load_example_text("protein", "protein_example.fasta")
        if not text:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. Please check your installation."),
            )
            return
        self.input_text.setPlainText(text)
        self.show_status(self.tr("Loaded example data: protein_example.fasta"))

    # ── Parameters ───────────────────────────────────────────────────────────

    def _setup_parameters(self):
        param_group = QGroupBox("Digestion Options")
        param_group.setFlat(True)
        pg_layout = QVBoxLayout(param_group)
        pg_layout.setContentsMargins(12, 12, 0, 12)
        pg_layout.setSpacing(6)

        # Row 1 — Protease selector
        row1 = QHBoxLayout()
        row1.setSpacing(16)
        row1.addWidget(QLabel("Protease:"))
        self.protease_combo = QComboBox()
        self.protease_combo.addItems(list(PROTEASES.keys()))
        self.protease_combo.setCurrentText("Trypsin")
        self.protease_combo.setMinimumWidth(200)
        self.protease_combo.currentTextChanged.connect(self._update_protease_hint)
        row1.addWidget(self.protease_combo)

        # Missed cleavages
        row1.addWidget(QLabel("Missed:"))
        self.missed_spin = QSpinBox()
        self.missed_spin.setRange(0, 5)
        self.missed_spin.setValue(0)
        self.missed_spin.setToolTip(
            "Number of allowed missed cleavage sites. "
            "Produces longer fragments for partial digests."
        )
        row1.addWidget(self.missed_spin)
        row1.addStretch()
        pg_layout.addLayout(row1)

        # Row 2 — Protease description hint
        self._protease_hint = QLabel(PROTEASES["Trypsin"]["desc"])
        self._protease_hint.setStyleSheet("color: #777; font-size: 12px;")
        self._protease_hint.setWordWrap(True)
        pg_layout.addWidget(self._protease_hint)

        self.content_area.insertWidget(1, param_group)

    def _update_protease_hint(self, name):
        self._protease_hint.setText(PROTEASES.get(name, {}).get("desc", ""))

    # ── Core logic ──────────────────────────────────────────────────────────

    def run(self):
        self.status_label.setText("")
        text = self.input_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Input Error", "Please input a protein sequence.")
            return

        try:
            records = self.parse_fasta(text)
        except Exception as e:
            QMessageBox.warning(self, "Format Error", str(e))
            return
        if not records:
            QMessageBox.warning(self, "Input Error", "No valid FASTA sequences detected.")
            return

        header, seq = records[0]
        seq = "".join(c for c in seq.upper() if c in AA)
        if not seq:
            QMessageBox.warning(self, "Input Error", "Sequence is empty after cleaning.")
            return

        protease_name = self.protease_combo.currentText()
        protease = PROTEASES[protease_name]
        missed = self.missed_spin.value()

        # Get all cut positions
        cut_rule = protease["rule"]
        cuts = cut_rule(seq)  # list of cut positions (0-based, after cut)

        # Generate fragments considering missed cleavages
        # cuts are sorted positions where cleavage occurs
        # A fragment goes from cut[i] to cut[i+1+missed]
        fragments = []
        for i in range(len(cuts)):
            end_idx = min(i + 1 + missed, len(cuts) - 1)
            if i == end_idx:
                continue
            start = cuts[i]
            end = cuts[end_idx]
            frag_seq = seq[start:end]
            if frag_seq:
                mw = sum(AA_MASS.get(aa, 0) for aa in frag_seq) + H2O
                fragments.append({
                    "start": start + 1,
                    "end": end,
                    "length": len(frag_seq),
                    "sequence": frag_seq if len(frag_seq) <= 40 else frag_seq[:37] + "...",
                    "mw": round(mw, 2),
                    "full_seq": frag_seq,
                })

        if not fragments:
            QMessageBox.warning(self, "No Fragments", "No cleavage sites found for this protease.")
            return

        # Display results
        out_lines = []
        out_lines.append(f"Protease: {protease_name}  |  Missed cleavages: {missed}")
        out_lines.append(f"Sequence: {header}  |  Length: {len(seq)} aa")
        out_lines.append("")
        out_lines.append(f"{'#':>4}  {'Start':>6} {'End':>6} {'Len':>5}  {'MW (Da)':>10}  Sequence")
        out_lines.append(f"{'─' * 4}  {'─' * 6} {'─' * 6} {'─' * 5}  {'─' * 10}  {'─' * 8}")

        for idx, frag in enumerate(fragments, 1):
            out_lines.append(
                f"{idx:>4}  {frag['start']:>6} {frag['end']:>6} {frag['length']:>5}"
                f"  {frag['mw']:>10.2f}  {frag['sequence']}"
            )
        out_lines.append("")
        out_lines.append(f"Total fragments: {len(fragments)}")
        total_mw = sum(f["mw"] for f in fragments)
        out_lines.append(f"Sum of fragment MW: {total_mw:.2f} Da")

        self.output_text.setPlainText("\n".join(out_lines))
        self.current_results = fragments
        self.status_label.setText(f"Digested with {protease_name} — {len(fragments)} fragments")

    def clear(self):
        self.input_text.clear()
        self.output_text.clear()
        self.current_results = []
        self.status_label.setText("Cleared")

    def export_csv(self):
        """Export digestion fragments to a CSV file."""
        if not self.current_results:
            QMessageBox.warning(
                self,
                self.tr("Export Error"),
                self.tr("Run a digestion first to generate fragments."),
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Export CSV"),
            "protease_fragments.csv",
            self.tr("CSV Files (*.csv);;All Files (*)"),
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["#", "Start", "End", "Length", "MW (Da)", "Sequence"])
                for frag in self.current_results:
                    writer.writerow([
                        self.current_results.index(frag) + 1,
                        frag["start"],
                        frag["end"],
                        frag["length"],
                        f"{frag['mw']:.2f}",
                        frag["sequence"],
                    ])
            self.status_label.setText(
                self.tr(f"Exported {len(self.current_results)} fragments to {path}")
            )
        except Exception as e:
            QMessageBox.warning(self, self.tr("Export Error"), str(e))

    def show_help(self):
        from PyQt6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QLabel,
            QPushButton,
            QScrollArea,
        )

        help_text = """
<h2>Protease Cleavage Map &mdash; Predict Digestion Fragments</h2>

<p><b>What does this tool do?</b><br>
It performs an <i>in silico</i> digestion of a protein sequence with a
selected protease (or chemical reagent), producing a list of predicted
fragments with their positions, lengths, and molecular weights.</p>

<h3>Available Proteases</h3>
<ul>
<li><b>Trypsin</b> &mdash; the workhorse for mass-spec. Cuts after K, R
(not before P).</li>
<li><b>Chymotrypsin</b> &mdash; cuts after F, Y, W (not before P).</li>
<li><b>Pepsin</b> &mdash; cuts before F, L (pH&nbsp;1.3) or F, L, Y, W
(pH&nbsp;&gt;&nbsp;2).</li>
<li><b>CNBr</b> &mdash; chemical cleavage after M.</li>
<li><b>V8</b> &mdash; Glu-specific or Glu+Asp depending on buffer.</li>
<li><b>Arg-C / Lys-C / Asp-N</b> &mdash; residue-specific enzymes.</li>
</ul>

<h3>Missed Cleavages</h3>
<p>Set to 0 for a complete digest. Increase to 1&ndash;2 to simulate
partial digestion, which produces longer overlapping fragments.</p>

<h3>Tips</h3>
<ul>
<li>Use <b>Trypsin with 0 missed</b> to predict peptides for mass-spec
proteomics.</li>
<li>Molecular weights are <b>monoisotopic</b> (includes H<sub>2</sub>O
at termini). Average masses can differ ~0.06%.</li>
<li>Long fragments are truncated in the display column; the full
sequence is used for MW calculation.</li>
</ul>
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Help - Protease Cleavage Map")
        dialog.setFixedSize(700, 500)
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
                except Exception as ex:
                    QMessageBox.warning(self, "File Read Error", str(ex))

        self.input_text.dragEnterEvent = drag_enter
        self.input_text.dropEvent = drop

    def parse_fasta(self, text):
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
