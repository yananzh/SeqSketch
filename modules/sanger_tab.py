from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QFileDialog, QGroupBox, QMessageBox, QScrollArea, QDialog, QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt

class SangerTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        # Only keep Sequence Assembly section as requested
        main_layout = QVBoxLayout(self)
        self.assembly_group = self.init_assembly_ui()
        main_layout.addWidget(self.assembly_group)
        self.setLayout(main_layout)
    

    # 3. 序列拼接
    def init_assembly_ui(self):
        group = QGroupBox("Sequence Assembly")
        vbox = QVBoxLayout()
        # Forward sequence (paste only)
        fwd_hbox = QHBoxLayout()
        self.fwd_edit = QTextEdit()
        self.fwd_edit.setPlaceholderText("Paste forward sequencing sequence")
        fwd_hbox.addWidget(QLabel("Forward:"))
        fwd_hbox.addWidget(self.fwd_edit)
        vbox.addLayout(fwd_hbox)
        # Reverse sequence (paste only)
        rev_hbox = QHBoxLayout()
        self.rev_edit = QTextEdit()
        self.rev_edit.setPlaceholderText("Paste reverse sequencing sequence (will be auto reverse-complemented)")
        rev_hbox.addWidget(QLabel("Reverse:"))
        rev_hbox.addWidget(self.rev_edit)
        vbox.addLayout(rev_hbox)

        # Assembly parameters
        params_hbox = QHBoxLayout()
        params_hbox.addWidget(QLabel("Min overlap:"))
        self.min_overlap_spin = QSpinBox()
        self.min_overlap_spin.setRange(5, 5000)
        self.min_overlap_spin.setValue(20)
        self.min_overlap_spin.setToolTip("Minimum overlap length to consider during assembly")
        params_hbox.addWidget(self.min_overlap_spin)
        params_hbox.addSpacing(16)
        params_hbox.addWidget(QLabel("Min identity:"))
        self.min_identity_spin = QDoubleSpinBox()
        self.min_identity_spin.setRange(0.50, 1.00)
        self.min_identity_spin.setSingleStep(0.01)
        self.min_identity_spin.setValue(0.90)
        self.min_identity_spin.setSuffix("  (fraction)")
        self.min_identity_spin.setToolTip("Minimum identity within overlap (0.50-1.00)")
        params_hbox.addWidget(self.min_identity_spin)
        params_hbox.addStretch()
        vbox.addLayout(params_hbox)

        run_hbox = QHBoxLayout()
        self.assemble_btn = QPushButton("Run Assembly")
        self.assemble_btn.clicked.connect(self.run_assembly)
        self.help_btn = QPushButton("Help")
        self.help_btn.clicked.connect(self.show_help)
        run_hbox.addWidget(self.assemble_btn)
        run_hbox.addWidget(self.help_btn)
        run_hbox.addStretch()
        vbox.addLayout(run_hbox)
        self.assembly_result = QTextEdit()
        self.assembly_result.setReadOnly(True)
        vbox.addWidget(QLabel("Assembly Result:"))
        vbox.addWidget(self.assembly_result)
        save_hbox = QHBoxLayout()
        self.save_assembly_btn = QPushButton("Save Assembled Sequence to File")
        self.save_assembly_btn.clicked.connect(self.save_assembly_result)
        self.copy_assembly_btn = QPushButton("Copy Assembled to Clipboard")
        self.copy_assembly_btn.clicked.connect(self.copy_assembled_to_clipboard)
        save_hbox.addWidget(self.save_assembly_btn)
        save_hbox.addWidget(self.copy_assembly_btn)
        save_hbox.addStretch()
        vbox.addLayout(save_hbox)
        group.setLayout(vbox)
        return group

    # (Quality visualization and selection UI have been removed)

    def run_assembly(self):
        fwd = self.fwd_edit.toPlainText().strip().upper().replace('U', 'T')
        rev = self.rev_edit.toPlainText().strip().upper().replace('U', 'T')
        if not fwd or not rev:
            QMessageBox.warning(self, "Input Error", "Paste both forward and reverse sequences")
            return
        # Automatically reverse-complement the reverse input
        rev_rc = self.reverse_complement(rev)
        min_overlap = self.min_overlap_spin.value()
        min_identity = float(self.min_identity_spin.value())
        overlap, identity, merged = self.auto_assemble(fwd, rev_rc, min_overlap=min_overlap, min_identity=min_identity)
        
        if overlap < min_overlap or identity < min_identity:
            QMessageBox.warning(self, "Assembly Warning", f"No clear overlap detected (overlap={overlap}, identity={identity:.2f}); concatenating ends directly")
        else:
            # Show detailed success message
            success_msg = f"""<h3>Assembly Successful!</h3>
<p><b>Overlap Information:</b></p>
<ul>
<li><b>Overlap length:</b> {overlap} bp</li>
<li><b>Identity:</b> {identity:.2%} ({int(identity * overlap)}/{overlap} matches)</li>
</ul>
<p><b>Sequence Lengths:</b></p>
<ul>
<li><b>Forward sequence:</b> {len(fwd)} bp</li>
<li><b>Reverse sequence (original):</b> {len(rev)} bp</li>
<li><b>Assembled sequence:</b> {len(merged)} bp</li>
</ul>
"""
            QMessageBox.information(self, "Assembly Complete", success_msg)
        
        self.assembly_result.setPlainText(merged)

    def reverse_complement(self, seq):
        comp_map = str.maketrans('ACGT', 'TGCA')
        return seq.translate(comp_map)[::-1]

    def status_message(self, msg):
        """Display status message (stub for now, could connect to parent status bar)"""
        # Could be connected to parent window's status bar if needed
        pass

    def auto_assemble(self, fwd, rev_rc, min_overlap=20, min_identity=0.9):
        """Simple overlap assembly allowing mismatches based on identity threshold."""
        max_overlap = min(len(fwd), len(rev_rc))
        best_overlap = 0
        best_identity = 0.0
        # try longer overlaps first
        for i in range(max_overlap, min_overlap - 1, -1):
            fseg = fwd[-i:]
            rseg = rev_rc[:i]
            matches = sum(1 for a, b in zip(fseg, rseg) if a == b)
            ident = matches / i if i > 0 else 0.0
            if ident >= min_identity:
                best_overlap = i
                best_identity = ident
                break
            # track best even if below threshold, for info
            if ident > best_identity:
                best_overlap = i
                best_identity = ident
        if best_overlap >= min_overlap and best_identity >= min_identity:
            merged = fwd + rev_rc[best_overlap:]
            return best_overlap, best_identity, merged
        # fallback: concatenate
        return 0, 0.0, fwd + rev_rc

    def save_assembly_result(self):
        seq = self.assembly_result.toPlainText().strip()
        if not seq:
            QMessageBox.warning(self, "No Assembly Result", "Run assembly first")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Save assembled sequence", "assembled_seq.fasta", "FASTA Files (*.fasta);;Text Files (*.txt)")
        if file_path:
            with open(file_path, 'w') as f:
                f.write(seq)
            QMessageBox.information(self, "Save Successful", f"Saved to: {file_path}")

    def copy_assembled_to_clipboard(self):
        seq = self.assembly_result.toPlainText().strip()
        if not seq:
            QMessageBox.warning(self, "No Assembly Result", "Run assembly first")
            return
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(seq)
        QMessageBox.information(self, "Copied", "Assembled sequence copied to clipboard")

    def show_help(self):
        """Show help information for Sanger assembly."""
        help_text = """
<h3>Sanger Sequencing - Sequence Assembly</h3>
<p><b>Description:</b></p>
<p>Assemble forward and reverse Sanger reads into a consensus sequence. Reverse input is automatically reverse-complemented.</p>

<p><b>Usage:</b></p>
<ol>
<li>Paste forward sequence (5' → 3').</li>
<li>Paste reverse sequence (as-read; it will be auto reverse-complemented).</li>
<li>Set assembly parameters: minimum overlap length and minimum identity.</li>
<li>Click "Run Assembly".</li>
<li>Copy or save the assembled sequence.</li>
</ol>

<p><b>Assembly Parameters:</b></p>
<ul>
<li><b>Min overlap:</b> Minimum number of bases that must overlap (default: 20)</li>
<li><b>Min identity:</b> Minimum fraction of matching bases in overlap region (default: 0.90)</li>
</ul>
<p><b>Note:</b> Non-ACGT characters are ignored; U is treated as T.</p>
"""
        from PyQt6.QtWidgets import QVBoxLayout
        dlg = QDialog(self)
        dlg.setWindowTitle("Help - Sanger Sequencing")
        dlg.resize(760, 520)
        layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        label = QLabel(help_text)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        label.setMargin(18)
        scroll.setWidget(label)
        layout.addWidget(scroll)
        btn_box = QHBoxLayout()
        ok = QPushButton("OK")
        ok.clicked.connect(dlg.accept)
        btn_box.addStretch()
        btn_box.addWidget(ok)
        layout.addLayout(btn_box)
        dlg.setLayout(layout)
        dlg.exec()


# (Standalone window class removed; this tool is provided as a tab in the main window.)
