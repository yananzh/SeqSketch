from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QFileDialog,
    QMessageBox,
    QScrollArea,
    QDialog,
    QSpinBox,
    QDoubleSpinBox,
)
from PyQt6.QtCore import Qt

from utils.common_components import apply_sequence_editor_style


class SangerTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Input section
        input_label = QLabel("Input Sequences")
        input_label.setStyleSheet("font-size: 11pt;")
        main_layout.addWidget(input_label)

        input_hint = QLabel(
            "Paste one forward read and one reverse read. The reverse read will be auto reverse-complemented before overlap assembly."
        )
        input_hint.setWordWrap(True)
        input_hint.setStyleSheet("color: #666; font-size: 10pt;")
        main_layout.addWidget(input_hint)

        # Forward and Reverse sequences side by side
        seqs_hbox = QHBoxLayout()
        seqs_hbox.setSpacing(12)

        fwd_vbox = QVBoxLayout()
        fwd_label = QLabel("Forward Sequence (5' → 3'):")
        self.fwd_edit = QTextEdit()
        apply_sequence_editor_style(self.fwd_edit)
        self.fwd_edit.setPlaceholderText(
            "Paste forward sequencing sequence...\nExample: ATGCGATCGATCG..."
        )
        self.fwd_edit.setMinimumHeight(120)
        fwd_vbox.addWidget(fwd_label)
        fwd_vbox.addWidget(self.fwd_edit)

        rev_vbox = QVBoxLayout()
        rev_label = QLabel("Reverse Sequence (auto reverse-complemented):")
        self.rev_edit = QTextEdit()
        apply_sequence_editor_style(self.rev_edit)
        self.rev_edit.setPlaceholderText(
            "Paste reverse sequencing sequence...\nExample: CGACCGATCGCAT..."
        )
        self.rev_edit.setMinimumHeight(120)
        rev_vbox.addWidget(rev_label)
        rev_vbox.addWidget(self.rev_edit)

        seqs_hbox.addLayout(fwd_vbox)
        seqs_hbox.addLayout(rev_vbox)
        main_layout.addLayout(seqs_hbox)

        # Parameters section
        params_label = QLabel("Assembly Parameters")
        params_label.setStyleSheet("font-size: 11pt;")
        main_layout.addWidget(params_label)

        params_hbox = QHBoxLayout()
        params_hbox.addWidget(QLabel("Min overlap:"))
        self.min_overlap_spin = QSpinBox()
        self.min_overlap_spin.setRange(5, 5000)
        self.min_overlap_spin.setValue(20)
        self.min_overlap_spin.setToolTip(
            "Minimum overlap length to consider during assembly"
        )
        self.min_overlap_spin.setMinimumWidth(80)
        params_hbox.addWidget(self.min_overlap_spin)

        params_hbox.addSpacing(20)
        params_hbox.addWidget(QLabel("Min identity:"))
        self.min_identity_spin = QDoubleSpinBox()
        self.min_identity_spin.setRange(0.50, 1.00)
        self.min_identity_spin.setSingleStep(0.01)
        self.min_identity_spin.setValue(0.90)
        self.min_identity_spin.setToolTip("Minimum identity within overlap (0.50-1.00)")
        self.min_identity_spin.setMinimumWidth(80)
        params_hbox.addWidget(self.min_identity_spin)
        params_hbox.addStretch()
        main_layout.addLayout(params_hbox)

        # Action buttons (Help unified at bottom-right)
        btn_hbox = QHBoxLayout()
        self.assemble_btn = QPushButton("Run Assembly")
        self.assemble_btn.clicked.connect(self.run_assembly)
        self.assemble_btn.setMinimumWidth(120)
        btn_hbox.addWidget(self.assemble_btn)
        btn_hbox.addStretch()
        main_layout.addLayout(btn_hbox)

        # Output section
        output_label = QLabel("Assembly Result")
        output_label.setStyleSheet("font-size: 11pt;")
        main_layout.addWidget(output_label)

        self.assembly_result = QTextEdit()
        self.assembly_result.setReadOnly(True)
        apply_sequence_editor_style(self.assembly_result)
        self.assembly_result.setPlaceholderText(
            "Assembled sequence will appear here..."
        )
        self.assembly_result.setMinimumHeight(150)
        main_layout.addWidget(self.assembly_result)

        # Export buttons
        export_hbox = QHBoxLayout()
        self.copy_assembly_btn = QPushButton("Copy to Clipboard")
        self.copy_assembly_btn.clicked.connect(self.copy_assembled_to_clipboard)
        self.copy_assembly_btn.setMinimumWidth(140)
        export_hbox.addWidget(self.copy_assembly_btn)

        self.save_assembly_btn = QPushButton("Save to File")
        self.save_assembly_btn.clicked.connect(self.save_assembly_result)
        self.save_assembly_btn.setMinimumWidth(120)
        export_hbox.addWidget(self.save_assembly_btn)
        export_hbox.addStretch()
        main_layout.addLayout(export_hbox)

        # Status + Help (bottom-right Help placement)
        status_layout = QHBoxLayout()
        status_caption = QLabel("Status:")
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        status_layout.addWidget(status_caption)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        help_btn = QPushButton("Help")
        help_btn.clicked.connect(self.show_help)
        status_layout.addWidget(help_btn)
        main_layout.addLayout(status_layout)

        self.setLayout(main_layout)

    def run_assembly(self):
        fwd = self.fwd_edit.toPlainText().strip().upper().replace("U", "T")
        rev = self.rev_edit.toPlainText().strip().upper().replace("U", "T")
        if not fwd or not rev:
            self.status_label.setText(
                "Error: Please paste both forward and reverse sequences"
            )
            QMessageBox.warning(
                self, "Input Error", "Paste both forward and reverse sequences"
            )
            return

        self.status_label.setText("Running assembly...")
        # Automatically reverse-complement the reverse input
        rev_rc = self.reverse_complement(rev)
        min_overlap = self.min_overlap_spin.value()
        min_identity = float(self.min_identity_spin.value())
        overlap, identity, merged = self.auto_assemble(
            fwd, rev_rc, min_overlap=min_overlap, min_identity=min_identity
        )

        if overlap < min_overlap or identity < min_identity:
            self.status_label.setText(
                f"Warning: No clear overlap (overlap={overlap}bp, identity={identity:.2f})"
            )
            QMessageBox.warning(
                self,
                "Assembly Warning",
                f"No clear overlap detected (overlap={overlap}, identity={identity:.2f}); concatenating ends directly",
            )
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
            self.status_label.setText(
                f"Assembly complete: {overlap}bp overlap, {identity:.2%} identity"
            )
            QMessageBox.information(self, "Assembly Complete", success_msg)

        self.assembly_result.setPlainText(merged)

    def reverse_complement(self, seq):
        comp_map = str.maketrans("ACGT", "TGCA")
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
            self.status_label.setText("Error: No assembly result to save")
            QMessageBox.warning(self, "No Assembly Result", "Run assembly first")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save assembled sequence",
            "assembled_seq.fasta",
            "FASTA Files (*.fasta);;Text Files (*.txt)",
        )
        if file_path:
            with open(file_path, "w") as f:
                f.write(seq)
            self.status_label.setText(f"Saved to: {file_path}")
            QMessageBox.information(self, "Save Successful", f"Saved to: {file_path}")

    def copy_assembled_to_clipboard(self):
        seq = self.assembly_result.toPlainText().strip()
        if not seq:
            self.status_label.setText("Error: No assembly result to copy")
            QMessageBox.warning(self, "No Assembly Result", "Run assembly first")
            return
        from PyQt6.QtWidgets import QApplication

        QApplication.clipboard().setText(seq)
        self.status_label.setText("Copied to clipboard")
        QMessageBox.information(
            self, "Copied", "Assembled sequence copied to clipboard"
        )

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
