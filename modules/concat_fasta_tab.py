"""Concatenate multiple FASTA files into a single output file."""

from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QFileDialog,
    QSizePolicy,
    QCheckBox,
    QGroupBox,
)
from PyQt6.QtCore import pyqtSignal
from utils.common_components import BaseTabWidget
import os


class ConcatFastaTab(BaseTabWidget):
    """Concatenate multiple FASTA files."""

    def __init__(self):
        super().__init__("Concatenate FASTA", "file")
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        _label_width = 120

        # ── Input files ──
        input_group = QGroupBox("Input FASTA Files")
        input_main = QVBoxLayout(input_group)

        self.files_edit = QPlainTextEdit()
        self.files_edit.setReadOnly(True)
        self.files_edit.setPlaceholderText(
            "Click 'Add Files' to select FASTA files to concatenate..."
        )
        self.files_edit.setMinimumHeight(100)
        self.files_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.files_edit.setStyleSheet(
            "border: 1px solid #94a3b8; border-radius: 6px; padding: 8px 10px; background: #ffffff;"
        )
        self.files_edit.viewport().setStyleSheet("background: transparent;")
        input_main.addWidget(self.files_edit)

        file_btn_row = QHBoxLayout()
        self.add_btn = QPushButton("Add Files")
        self.add_btn.setToolTip("Add one or more FASTA files to the list")
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.setToolTip("Remove the currently selected file from the list")
        self.clear_files_btn = QPushButton("Clear All")
        file_btn_row.addWidget(self.add_btn)
        file_btn_row.addWidget(self.remove_btn)
        file_btn_row.addWidget(self.clear_files_btn)
        file_btn_row.addStretch()
        input_main.addLayout(file_btn_row)

        # ── Options ──
        opts_layout = QHBoxLayout()
        self.add_prefix_checkbox = QCheckBox("Add source filename as ID prefix")
        self.add_prefix_checkbox.setToolTip(
            "Prepend the source filename (without extension) to each ID, "
            "e.g. 'file1|NM_001101.5'. Useful for tracking which file each "
            "sequence came from."
        )
        opts_layout.addWidget(self.add_prefix_checkbox)
        opts_layout.addStretch()

        # ── Preview ──
        self.preview_panel = QPlainTextEdit()
        self.preview_panel.setReadOnly(True)
        self.preview_panel.setPlaceholderText(
            "Click Preview to see file counts and total sequences..."
        )
        self.preview_panel.setMaximumHeight(110)
        self.preview_panel.setStyleSheet(
            "border: 1px solid #94a3b8; border-radius: 6px; padding: 8px 10px; background: transparent;"
        )

        # ── Output ──
        output_layout = QHBoxLayout()
        output_label = QLabel("Output file:")
        output_label.setFixedWidth(_label_width)
        output_layout.addWidget(output_label)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText(
            "Choose where to save the concatenated file..."
        )
        self.output_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.output_btn = QPushButton("Save As")
        self.output_btn.setFixedWidth(90)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)

        # ── Controls ──
        control_layout = QHBoxLayout()
        control_layout.addStretch(1)
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setToolTip("Preview file counts and total sequence count")
        self.run_btn = QPushButton("Start")
        self.clear_btn = QPushButton("Clear")
        control_layout.addWidget(self.preview_btn)
        control_layout.addWidget(self.run_btn)
        control_layout.addWidget(self.clear_btn)
        control_layout.setSpacing(10)

        # ── Assemble ──
        self.add_content_widget(input_group)
        self.add_content_layout(opts_layout)
        self.add_content_widget(self.preview_panel)
        self.add_content_layout(output_layout)
        self.add_content_layout(control_layout)
        self.content_area.addStretch()

    def connect_signals(self):
        self.add_btn.clicked.connect(self.add_files)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.clear_files_btn.clicked.connect(self.clear_files_list)
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_concat)
        self.preview_btn.clicked.connect(self.preview_concat)
        self.clear_btn.clicked.connect(self.clear_all)

    def _file_paths(self):
        text = self.files_edit.toPlainText().strip()
        if not text:
            return []
        return [line.strip() for line in text.splitlines() if line.strip()]

    def add_files(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select FASTA files",
            "",
            "FASTA Files (*.fasta *.fa *.fas *.fna *.ffn *.faa *.frn *.txt);;All Files (*)",
        )
        if file_paths:
            current = self.files_edit.toPlainText().strip()
            new_lines = []
            seen = set(current.splitlines()) if current else set()
            for p in file_paths:
                if p not in seen:
                    new_lines.append(p)
                    seen.add(p)
            if current:
                all_lines = current.splitlines() + new_lines
            else:
                all_lines = new_lines
            self.files_edit.setPlainText("\n".join(all_lines))

    def remove_selected(self):
        cursor = self.files_edit.textCursor()
        if cursor.hasSelection():
            selected = cursor.selectedText().strip()
            current = self.files_edit.toPlainText()
            new_text = current.replace(selected, "", 1).strip()
            # Clean up double newlines
            import re

            new_text = re.sub(r"\n\s*\n", "\n", new_text)
            self.files_edit.setPlainText(new_text)

    def clear_files_list(self):
        self.files_edit.clear()

    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save concatenated file",
            "",
            "FASTA Files (*.fasta *.fa *.fas);;All Files (*)",
        )
        if file_path:
            self.output_edit.setText(file_path)

    def preview_concat(self):
        paths = self._file_paths()
        if not paths:
            self.log_message("Please add at least one FASTA file", "ERROR")
            return

        lines = []
        total_seqs = 0
        valid_paths = 0
        for path in paths:
            if not os.path.isfile(path):
                lines.append(f"  ✗ {path}  (file not found)")
                continue
            try:
                from modules.fasta_processor import FASTAProcessor

                processor = FASTAProcessor()
                if processor.read_file(path) and processor.records:
                    count = len(processor.records)
                    total_seqs += count
                    valid_paths += 1
                    lines.append(f"  ✓ {os.path.basename(path)}  ({count} sequences)")
                else:
                    lines.append(f"  ✗ {os.path.basename(path)}  (no sequences)")
            except Exception:
                lines.append(f"  ✗ {os.path.basename(path)}  (read error)")

        summary = (
            f"Files: {valid_paths}/{len(paths)} valid  ·  Total sequences: {total_seqs}"
        )
        lines.insert(0, summary)
        lines.insert(1, "")
        self.preview_panel.setPlainText("\n".join(lines))
        self.log_message("Preview updated — see panel above", "INFO")

    def run_concat(self):
        paths = self._file_paths()
        output_path = self.output_edit.text().strip()
        use_prefix = self.add_prefix_checkbox.isChecked()

        from utils.common_components import validate_output_path

        valid, error = validate_output_path(output_path)
        if not valid:
            self.log_message(error, "ERROR")
            return

        if not paths:
            self.log_message("Please add at least one FASTA file", "ERROR")
            return

        valid_paths = [p for p in paths if os.path.isfile(p)]
        if not valid_paths:
            self.log_message("None of the specified files exist", "ERROR")
            return

        self.set_running_state(True)
        self.log_message(f"Concatenating {len(valid_paths)} file(s)...", "INFO")
        try:
            from modules.fasta_processor import FASTAProcessor

            all_records = []
            for path in valid_paths:
                processor = FASTAProcessor()
                if not processor.read_file(path):
                    self.log_message(
                        f"Skipping unreadable file: {os.path.basename(path)}", "WARNING"
                    )
                    continue
                if use_prefix:
                    prefix = os.path.splitext(os.path.basename(path))[0]
                    for rec in processor.records:
                        rec.header = f"{prefix}|{rec.header}"
                all_records.extend(processor.records)
                self.log_message(
                    f"  {os.path.basename(path)}: {len(processor.records)} sequence(s)",
                    "INFO",
                )

            if not all_records:
                self.log_message("No sequences to concatenate", "ERROR")
                return

            if not processor.save_file(output_path, all_records):
                self.log_message("Failed to save file", "ERROR")
                return
            self.log_message(
                f"Concatenation complete! Total: {len(all_records)} sequences. "
                f"Saved to: {output_path}",
                "INFO",
            )
            self.show_status("Complete")
        except Exception as e:
            import traceback

            self.log_message(f"Error: {e}\n{traceback.format_exc()}", "ERROR")
            self.show_status("Error")
        finally:
            self.set_running_state(False)

    def clear_all(self):
        self.files_edit.clear()
        self.output_edit.clear()
        self.add_prefix_checkbox.setChecked(False)
        self.preview_panel.clear()
        self.log_area.clear()
        self.show_status("Cleared")

    def set_running_state(self, running: bool):
        super().set_running_state(running)
        self.run_btn.setEnabled(not running)
        self.preview_btn.setEnabled(not running)
        self.add_btn.setEnabled(not running)
        self.remove_btn.setEnabled(not running)
        self.clear_files_btn.setEnabled(not running)
        self.output_btn.setEnabled(not running)
        self.add_prefix_checkbox.setEnabled(not running)

    def show_help(self):
        from PyQt6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QLabel,
            QPushButton,
            QScrollArea,
        )
        from PyQt6.QtCore import Qt

        help_text = """
<h2>Concatenate FASTA &mdash; Merge Multiple Files</h2>

<p><b>What does this tool do?</b><br>
It combines multiple FASTA files into a single output file. Add files with
<b>Add Files</b>, reorder them manually if needed, and click <b>Start</b>.</p>

<h3>Options</h3>
<ul>
<li><b>Add source filename as ID prefix</b> &mdash; appends the source filename
to each sequence ID so you can trace which file each entry came from.
Example: 'file1.fasta' containing '>NM_001101.5' becomes
'>file1|NM_001101.5'.</li>
</ul>

<h3>Use Cases</h3>
<ul>
<li>Merge chromosome-level assemblies into one whole-genome FASTA.</li>
<li>Combine multiple gene-family alignments.</li>
<li>Aggregate results from parallel BLAST searches.</li>
</ul>

<h3>Tips</h3>
<ul>
<li>Files are concatenated in the order they appear in the list.</li>
<li>Always <b>Preview</b> before running to verify each file is readable.</li>
<li>Use <b>FASTA QC</b> afterwards to verify the merged result.</li>
</ul>
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Help - Concatenate FASTA")
        dialog.setFixedSize(720, 460)
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
