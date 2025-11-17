from utils.common_components import BaseTabWidget
import re
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import Qt

class ReverseComplementTab(BaseTabWidget):
    complement_map = str.maketrans(
        'ACGTacgtRYMKSWBDHVNrymkswbdhvn',
        'TGCAtgcaYRKMWSVHDBNyrkmwsvhdbn'
    )

    def __init__(self, parent=None):
        super().__init__("Reverse Complement", "sequence")
        self._setup_drag_drop()
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
                with open(file_path, 'r', encoding='utf-8') as f:
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
        self.output_text.setPlaceholderText("Reverse complement sequences will appear here...")
        # Adjust minimum heights for better visibility
        self.input_text.setMinimumHeight(200)
        self.output_text.setMinimumHeight(200)

    def run(self):
        seq = self.input_text.toPlainText().strip()
        if not seq:
            self.status_label.setText("Please enter a DNA sequence or FASTA.")
            return
        
        # Check if input is FASTA format
        if '>' in seq:
            # Parse and convert multi-sequence FASTA
            result = self._convert_fasta(seq)
            if result:
                self.output_text.setPlainText(result)
                self.status_label.setText("Generated reverse complement for FASTA")
            else:
                self.status_label.setText("Invalid FASTA format or sequences")
        else:
            # Single raw sequence
            if not self.is_valid_dna(seq):
                self.status_label.setText("Invalid characters. Allowed IUPAC codes: A/T/G/C/N, etc.")
                return
            revcomp = seq.translate(self.complement_map)[::-1]
            self.output_text.setPlainText(revcomp)
            self.status_label.setText("Reverse complement generated")
    
    def _convert_fasta(self, fasta_text):
        """Convert FASTA format DNA to reverse complement"""
        lines = fasta_text.split('\n')
        output_lines = []
        current_seq = []
        current_header = None
        
        for line in lines:
            line = line.strip()
            if line.startswith('>'):
                # Save previous sequence if exists
                if current_header is not None and current_seq:
                    seq = ''.join(current_seq)
                    if self.is_valid_dna(seq):
                        revcomp = seq.translate(self.complement_map)[::-1]
                        output_lines.append(current_header)
                        output_lines.append(revcomp)
                    else:
                        return None
                # Start new sequence
                current_header = line
                current_seq = []
            elif line:
                current_seq.append(line)
        
        # Save last sequence
        if current_header is not None and current_seq:
            seq = ''.join(current_seq)
            if self.is_valid_dna(seq):
                revcomp = seq.translate(self.complement_map)[::-1]
                output_lines.append(current_header)
                output_lines.append(revcomp)
            else:
                return None
        
        return '\n'.join(output_lines) if output_lines else None

    def is_valid_dna(self, seq):
        return re.fullmatch(r'[ACGTNacgtnRYMKSWBDHVrykmswbdhv\s]+', seq) is not None

    def show_help(self):
        help_text = """
<h3>Reverse Complement</h3>
<p><b>Description:</b></p>
<p>Generate reverse complement of DNA sequences: complement (A↔T, G↔C) then reverse. Supports both raw sequences and FASTA format (single or multiple sequences).</p>

<p><b>Usage:</b></p>
<ol>
<li>Paste DNA sequence(s) or drag-and-drop a FASTA file</li>
<li>Click "Run" to generate reverse complement</li>
<li>Export or copy the result</li>
</ol>

<p><b>Input formats:</b></p>
<ul>
<li><b>Raw sequence:</b> Plain DNA text (e.g., ATGCGATCG)</li>
<li><b>FASTA single:</b> >header followed by sequence</li>
<li><b>FASTA multi:</b> Multiple sequences with headers</li>
</ul>

<p><b>Process:</b></p>
<ol>
<li>Generate complement: A↔T, G↔C</li>
<li>Reverse the sequence (5' to 3' becomes 3' to 5')</li>
</ol>

<p><b>Applications:</b></p>
<ul>
<li>Primer design</li>
<li>Finding complementary strands</li>
<li>Molecular cloning operations</li>
<li>IUPAC codes supported (R, Y, M, K, S, W, B, D, H, V)</li>
</ul>

<p><b>Example:</b></p>
<pre>
Input:
>seq1
ATGCGATCG

Output:
>seq1
CGATCGCAT
</pre>
        """
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QScrollArea
        dialog = QDialog(self)
        dialog.setWindowTitle("Help - Reverse Complement")
        dialog.setFixedSize(700, 520)
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
