from utils.common_components import BaseTabWidget
import re
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt


class ComplementTab(BaseTabWidget):
    complement_map = str.maketrans(
        "ACGTacgtRYMKSWBDHVNrymkswbdhvn",
        "TGCAtgcaYRKMWSVHDBNyrkmwsvhdbn",
    )

    def __init__(self, parent=None):
        super().__init__("Complement/Reverse Complement", "sequence")
        self._setup_drag_drop()
        self._setup_mode_controls()
        self._update_ui_layout()

    def _setup_drag_drop(self):
        """Enable drag-and-drop for FASTA files"""
        self.input_text.setAcceptDrops(True)
        self.input_text.dragEnterEvent = self._drag_enter_event
        self.input_text.dropEvent = self._drop_event

    def _drag_enter_event(self, event):
        """Handle drag enter for file drops"""
        md = event.mimeData()
        if md.hasUrls():
            urls = md.urls()
            if urls and urls[0].toLocalFile():
                event.acceptProposedAction()
                return
        event.ignore()

    def _drop_event(self, event):
        """Handle file drop for FASTA input"""
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.input_text.setPlainText(content)
                self.input_hint.setText(f"Loaded file: {file_path}")
                event.acceptProposedAction()
            except Exception as e:
                self.status_label.setText(f"Error loading file: {e}")
                event.ignore()

    def _update_ui_layout(self):
        """Update placeholder and input/output sizing"""
        self.input_text.setPlaceholderText(
            "Paste DNA sequence in FASTA format (single or multiple sequences) or drag-and-drop a file...\n"
            "Examples:\n"
            ">seq1\n"
            "ATGCGATCGATCG\n"
            ">seq2\n"
            "TTAAGGCCTTAAGG"
        )
        self.input_hint.setText(
            "Supports raw DNA and multi-sequence FASTA input. Use Mode to switch between complement and reverse complement output."
        )
        self._update_output_placeholder()
        self.input_text.setMinimumHeight(200)
        self.output_text.setMinimumHeight(200)

    def _setup_mode_controls(self):
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Complement", "Reverse Complement"])
        self.mode_combo.setMinimumWidth(220)
        self.mode_combo.currentTextChanged.connect(self._update_output_placeholder)
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()
        self.content_area.insertLayout(1, mode_layout)

    def _update_output_placeholder(self):
        if self.mode_combo.currentText() == "Reverse Complement":
            self.output_text.setPlaceholderText(
                "Reverse complement sequences will appear here..."
            )
        else:
            self.output_text.setPlaceholderText(
                "Complement sequences will appear here..."
            )

    def set_mode(self, mode: str):
        index = self.mode_combo.findText(mode)
        if index >= 0:
            self.mode_combo.setCurrentIndex(index)

    def _transform_sequence(self, sequence: str) -> str:
        transformed = sequence.translate(self.complement_map)
        if self.mode_combo.currentText() == "Reverse Complement":
            return transformed[::-1]
        return transformed

    def _mode_label(self) -> str:
        return self.mode_combo.currentText().lower()

    def run(self):
        seq = self.input_text.toPlainText().strip()
        if not seq:
            self.show_status("Please enter a DNA sequence or FASTA.")
            return

        if ">" in seq:
            result = self._convert_fasta(seq)
            if result:
                self.output_text.setPlainText(result)
                self.show_status(f"Generated {self._mode_label()} for FASTA input")
            else:
                self.show_status("Invalid FASTA format or sequences")
        else:
            if not self.is_valid_dna(seq):
                self.show_status(
                    "Invalid characters. Allowed IUPAC codes: A/T/G/C/N, etc."
                )
                return
            transformed = self._transform_sequence(seq)
            self.output_text.setPlainText(transformed)
            self.show_status(f"{self.mode_combo.currentText()} generated")

    def _convert_fasta(self, fasta_text):
        """Convert FASTA format DNA with the selected mode."""
        lines = fasta_text.split("\n")
        output_lines = []
        current_seq = []
        current_header = None

        for line in lines:
            line = line.strip()
            if line.startswith(">"):
                if current_header is not None and current_seq:
                    seq = "".join(current_seq)
                    if self.is_valid_dna(seq):
                        transformed = self._transform_sequence(seq)
                        output_lines.append(current_header)
                        output_lines.append(transformed)
                    else:
                        return None
                current_header = line
                current_seq = []
            elif line:
                current_seq.append(line)

        if current_header is not None and current_seq:
            seq = "".join(current_seq)
            if self.is_valid_dna(seq):
                transformed = self._transform_sequence(seq)
                output_lines.append(current_header)
                output_lines.append(transformed)
            else:
                return None

        return "\n".join(output_lines) if output_lines else None

    def is_valid_dna(self, seq):
        return re.fullmatch(r"[ACGTNacgtnRYMKSWBDHVrykmswbdhv\s]+", seq) is not None

    def show_help(self):
        help_text = """
<h3>Complement / Reverse Complement</h3>
<p><b>Description:</b></p>
<p>Generate either the direct complement or the reverse complement of DNA sequences from one unified tab.</p>

<p><b>Usage:</b></p>
<ol>
<li>Paste DNA sequence(s) or drag-and-drop a FASTA file</li>
<li>Select <b>Complement</b> or <b>Reverse Complement</b> from the mode dropdown</li>
<li>Click "Run" to generate the selected transformation</li>
<li>Export or copy the result</li>
</ol>

<p><b>Input formats:</b></p>
<ul>
<li><b>Raw sequence:</b> Plain DNA text (e.g., ATGCGATCG)</li>
<li><b>FASTA single:</b> >header followed by sequence</li>
<li><b>FASTA multi:</b> Multiple sequences with headers</li>
</ul>

<p><b>Mode examples:</b></p>
<pre>
Input:
>seq1
ATGCGATCG

Complement:
>seq1
TACGCTAGC

Reverse Complement:
>seq1
CGATCGCAT
</pre>

<p><b>Rules:</b></p>
<ul>
<li>A ↔ T</li>
<li>G ↔ C</li>
<li>N → N (unchanged)</li>
<li>IUPAC codes supported (R, Y, M, K, S, W, B, D, H, V)</li>
</ul>

<p><b>Typical uses:</b></p>
<ul>
<li>Complement only: strand comparison and probe design</li>
<li>Reverse complement: primer work, cloning workflows, antisense sequence review</li>
</ul>
        """
        from PyQt6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QLabel,
            QPushButton,
            QScrollArea,
        )

        dialog = QDialog(self)
        dialog.setWindowTitle("Help - Complement/Reverse Complement")
        dialog.setFixedSize(720, 560)
        layout = QVBoxLayout()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        label = QLabel(help_text)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        label.setMargin(20)
        scroll_area.setWidget(label)
        layout.addWidget(scroll_area)
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)
        dialog.setLayout(layout)
        dialog.exec()
