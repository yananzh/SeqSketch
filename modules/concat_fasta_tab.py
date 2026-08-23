"""Concatenate multiple FASTA files into a single output file."""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from utils.common_components import BaseTabWidget, apply_input_list_style, unify_status_button_sizes


class ConcatFastaTab(BaseTabWidget):
    """Concatenate multiple FASTA files."""

    def __init__(self):
        super().__init__("Concatenate FASTA", "file")
        self.init_ui()
        self.connect_signals()
        unify_status_button_sizes(self)

    def init_ui(self):
        _label_width = 130

        # ── Input files ──
        input_group = QGroupBox("Input FASTA")
        input_main = QVBoxLayout(input_group)

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.file_list.setMinimumHeight(100)
        self.file_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        apply_input_list_style(self.file_list)
        input_main.addWidget(self.file_list)

        file_btn_row = QHBoxLayout()
        self.add_btn = QPushButton("Add Files")
        self.add_btn.setToolTip("Add one or more FASTA files to the list")
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.setToolTip("Remove the currently selected file from the list")
        self.clear_files_btn = QPushButton("Clear All")
        self.example_btn = QPushButton("Example")
        self.example_btn.setToolTip("Load bundled example gene files")
        file_btn_row.addWidget(self.add_btn)
        file_btn_row.addWidget(self.example_btn)
        file_btn_row.addWidget(self.remove_btn)
        file_btn_row.addWidget(self.clear_files_btn)
        file_btn_row.addStretch()
        input_main.addLayout(file_btn_row)

        # ── Options ──
        opts_group = QGroupBox("Options")
        opts_layout = QHBoxLayout(opts_group)
        self.add_prefix_checkbox = QCheckBox("Add source filename as ID prefix")
        self.add_prefix_checkbox.setToolTip(
            "Prepend the source filename (without extension) to each ID, "
            "e.g. 'file1|NM_001101.5'. Useful for tracking which file each "
            "sequence came from."
        )
        opts_layout.addWidget(self.add_prefix_checkbox)
        self.dedup_checkbox = QCheckBox("Deduplicate after concatenation")
        self.dedup_checkbox.setToolTip(
            "Remove duplicate sequence IDs from the merged output. "
            "The first occurrence of each ID is kept."
        )
        opts_layout.addWidget(self.dedup_checkbox)
        opts_layout.addStretch()

        # ── Preview ──
        self.preview_panel = QPlainTextEdit()
        self.preview_panel.setReadOnly(True)
        self.preview_panel.setPlaceholderText(
            "Click Preview to see file counts and total sequences..."
        )
        self.preview_panel.setMaximumHeight(110)
        self.preview_panel.setProperty("previewPanel", True)

        # ── Output ──
        output_layout = QHBoxLayout()
        output_label = QLabel("Output FASTA file:")
        output_label.setFixedWidth(_label_width)
        output_layout.addWidget(output_label)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose where to save the concatenated file...")
        self.output_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.output_btn = QPushButton("Browse")
        self.output_btn.setFixedWidth(90)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)

        # ── Control buttons in status bar ──
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setToolTip("Preview file counts and total sequence count")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.preview_btn)
        self.run_btn = QPushButton("Run")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.run_btn)
        self.clear_btn = QPushButton("Clear")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.clear_btn)
        self.add_open_output_dir_button()

        # ── Assemble ──
        self.add_content_widget(input_group)
        self.add_content_widget(opts_group)
        self.add_content_widget(self.preview_panel)
        self.add_content_layout(output_layout)
        self.content_area.addStretch()

    def connect_signals(self):
        self.add_btn.clicked.connect(self.add_files)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.clear_files_btn.clicked.connect(self.clear_files_list)
        self.example_btn.clicked.connect(self._load_example)
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_concat)
        self.preview_btn.clicked.connect(self.preview_concat)
        self.clear_btn.clicked.connect(self.clear_all)

    def _file_paths(self):
        return [
            self.file_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.file_list.count())
        ]

    def _add_path(self, path: str):
        """Append a file path to the list, skipping duplicates.
        Scans the file to show the sequence count in the list item."""
        existing = set(self._file_paths())
        if path in existing:
            return
        # Scan the file for sequence count
        seq_count = 0
        try:
            from modules.fasta_processor import FASTAProcessor

            processor = FASTAProcessor()
            if processor.read_file(path):
                seq_count = len(processor.records)
        except (OSError, ValueError):
            pass
        label = os.path.basename(path)
        if seq_count:
            label = f"{label}  ({seq_count} sequences)"
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, path)
        item.setToolTip(path)
        self.file_list.addItem(item)

    def add_files(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select FASTA files",
            "",
            "FASTA Files (*.fasta *.fa *.fas *.fna *.ffn *.faa *.frn *.txt);;All Files (*)",
        )
        for p in file_paths:
            self._add_path(p)

    def remove_selected(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))

    def clear_files_list(self):
        self.file_list.clear()

    def _load_example(self):
        """Load bundled example gene files into the file list."""
        from PyQt6.QtWidgets import QMessageBox

        from utils.example_data import stage_example

        self.file_list.clear()
        examples = [
            ("phylo", "gene1.fasta"),
            ("phylo", "gene2.fasta"),
            ("phylo", "gene3.fasta"),
        ]
        loaded = []
        for folder, name in examples:
            path = stage_example(folder, name)
            if not path:
                continue
            loaded.append(name)
            self._add_path(path)
        if not loaded:
            QMessageBox.information(
                self,
                "Example",
                "Failed to load example data. Please check the installation.",
            )
            return
        self.show_status("Example loaded: " + ", ".join(loaded))

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

        summary = f"Files: {valid_paths}/{len(paths)} valid  ·  Total sequences: {total_seqs}"
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

            # Optional dedup after concatenation
            if self.dedup_checkbox.isChecked():
                dedup_before = len(all_records)
                seen = set()
                deduped = []
                for rec in all_records:
                    if rec.header not in seen:
                        seen.add(rec.header)
                        deduped.append(rec)
                removed = dedup_before - len(deduped)
                if removed:
                    self.log_message(
                        f"Deduplicated: kept {len(deduped)}, removed {removed} duplicate ID(s)",
                        "INFO",
                    )
                all_records = deduped

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
        self.file_list.clear()
        self.output_edit.clear()
        self.add_prefix_checkbox.setChecked(False)
        self.dedup_checkbox.setChecked(False)
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
        self.dedup_checkbox.setEnabled(not running)
        self.example_btn.setEnabled(not running)

    def show_help(self):
        help_text = """
<h2>Concatenate FASTA &mdash; Merge Multiple Files</h2>

<p><b>What does this tool do?</b><br>
It combines multiple FASTA files into a single output file. Add files with
<b>Add Files</b>, and click <b>Run</b>. The output order matches the file
list order.</p>

<h3>Quick Start</h3>
<ol>
<li>Click <b>Add Files</b> to select one or more FASTA files
(or click <b>Example</b> to add the bundled sample).</li>
<li>Each file shows its sequence count in the list once added.</li>
<li>Click <b>Preview</b> to verify all files are readable and see
the total sequence count.</li>
<li>Choose an output file, then click <b>Run</b>.</li>
</ol>

<h3>Options</h3>
<ul>
<li><b>Add source filename as ID prefix</b> &mdash; prepends the source
filename (without extension) to each sequence ID with a <code>|</code>
separator. Example: <code>file1.fasta</code> containing
<code>&gt;NM_001101.5</code> becomes <code>&gt;file1|NM_001101.5</code>.</li>
<li><b>Deduplicate after concatenation</b> &mdash; removes duplicate
sequence IDs from the merged output, keeping the first occurrence.
Useful when different files contain sequences with the same ID.</li>
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
<li>Use <b>FASTA Statistics</b> afterwards to verify the merged result.</li>
<li>If your source files share sequence IDs, enable
<b>Deduplicate after concatenation</b> to avoid duplicate headers
in the output.</li>
</ul>
        """
        self.show_help_dialog("Help - Concatenate FASTA", help_text, 600, 480)
