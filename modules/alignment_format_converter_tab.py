import os

from Bio import AlignIO
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
)

from utils.common_components import (
    BaseTabWidget,
    validate_input_path,
    validate_output_path,
)


FORMAT_LABELS = {
    "FASTA": "fasta",
    "CLUSTAL": "clustal",
    "PHYLIP": "phylip-relaxed",
    "NEXUS": "nexus",
}

FORMAT_EXTENSIONS = {
    "FASTA": ".fasta",
    "CLUSTAL": ".aln",
    "PHYLIP": ".phy",
    "NEXUS": ".nex",
}

SUPPORTED_EXTENSIONS = [
    ".fasta",
    ".fa",
    ".fas",
    ".fna",
    ".afa",
    ".aln",
    ".clustal",
    ".phy",
    ".phylip",
    ".nex",
    ".nexus",
]


def convert_alignment_file(
    input_path: str,
    output_path: str,
    input_format_label: str,
    output_format_label: str,
) -> tuple[int, int, int]:
    input_format = FORMAT_LABELS[input_format_label]
    output_format = FORMAT_LABELS[output_format_label]

    with open(input_path, "r", encoding="utf-8", errors="replace") as handle:
        alignments = list(AlignIO.parse(handle, input_format))

    if not alignments:
        raise ValueError("No alignment records were found in the input file.")

    with open(output_path, "w", encoding="utf-8") as handle:
        written = AlignIO.write(alignments, handle, output_format)

    first_alignment = alignments[0]
    return written, len(first_alignment), first_alignment.get_alignment_length()


class AlignmentFormatConverterTab(BaseTabWidget):
    def __init__(self):
        super().__init__("Alignment Format Converter", "file")
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        class FileDropLineEdit(QLineEdit):
            file_dropped = pyqtSignal(str)

            def __init__(self, parent=None):
                super().__init__(parent)
                self.setAcceptDrops(True)

            def dragEnterEvent(self, event):
                md = event.mimeData()
                if md.hasUrls():
                    urls = md.urls()
                    if urls:
                        local = urls[0].toLocalFile()
                        if self._is_valid_alignment(local):
                            event.acceptProposedAction()
                            return
                event.ignore()

            def dropEvent(self, event):
                urls = event.mimeData().urls()
                if urls:
                    local = urls[0].toLocalFile()
                    if self._is_valid_alignment(local):
                        self.setText(local)
                        self.file_dropped.emit(local)
                        event.acceptProposedAction()
                        return
                event.ignore()

            @staticmethod
            def _is_valid_alignment(path: str) -> bool:
                try:
                    ext = os.path.splitext(path)[1].lower()
                    return os.path.isfile(path) and ext in SUPPORTED_EXTENSIONS
                except Exception:
                    return False

        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Input alignment:"))
        self.input_edit = FileDropLineEdit()
        self.input_edit.setPlaceholderText(
            "Select or drop an aligned FASTA / CLUSTAL / PHYLIP / NEXUS file..."
        )
        self.input_edit.setMinimumWidth(320)
        self.input_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.input_btn = QPushButton("Browse")
        self.input_btn.setFixedWidth(90)
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(self.input_btn)
        input_layout.setSpacing(8)

        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Input format:"))
        self.input_format_combo = QComboBox()
        self.input_format_combo.addItems(list(FORMAT_LABELS))
        format_layout.addWidget(self.input_format_combo)
        format_layout.addSpacing(16)
        format_layout.addWidget(QLabel("Output format:"))
        self.output_format_combo = QComboBox()
        self.output_format_combo.addItems(list(FORMAT_LABELS))
        self.output_format_combo.setCurrentText("CLUSTAL")
        format_layout.addWidget(self.output_format_combo)
        format_layout.addStretch(1)

        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output file:"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText(
            "Choose where to save the converted alignment..."
        )
        self.output_edit.setMinimumWidth(320)
        self.output_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.output_btn = QPushButton("Save As")
        self.output_btn.setFixedWidth(90)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        output_layout.setSpacing(8)

        control_layout = QHBoxLayout()
        control_layout.addStretch(1)
        self.run_btn = QPushButton("Convert")
        self.clear_btn = QPushButton("Clear")
        control_layout.addWidget(self.run_btn)
        control_layout.addWidget(self.clear_btn)
        control_layout.setSpacing(10)

        self.add_content_layout(input_layout)
        self.add_content_layout(format_layout)
        self.add_content_layout(output_layout)
        self.add_content_layout(control_layout)
        self.content_area.addStretch()

    def connect_signals(self):
        self.input_btn.clicked.connect(self.select_input_file)
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_conversion)
        self.clear_btn.clicked.connect(self.clear_all)
        self.output_format_combo.currentTextChanged.connect(
            self._update_output_extension
        )
        if hasattr(self.input_edit, "file_dropped"):
            self.input_edit.file_dropped.connect(self.handle_input_file_selected)

    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select alignment file",
            "",
            "Alignment Files (*.fasta *.fa *.fas *.fna *.afa *.aln *.clustal *.phy *.phylip *.nex *.nexus);;All Files (*)",
        )
        if file_path:
            self.handle_input_file_selected(file_path)

    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save converted alignment",
            self.output_edit.text().strip() or "converted_alignment",
            "Alignment Files (*.fasta *.fa *.aln *.phy *.nex);;All Files (*)",
        )
        if file_path:
            self.output_edit.setText(file_path)
            self._update_output_extension()

    def handle_input_file_selected(self, file_path: str):
        self.input_edit.setText(file_path)
        ext = os.path.splitext(file_path)[1].lower()
        if ext in {".fasta", ".fa", ".fas", ".fna", ".afa"}:
            self.input_format_combo.setCurrentText("FASTA")
        elif ext in {".aln", ".clustal"}:
            self.input_format_combo.setCurrentText("CLUSTAL")
        elif ext in {".phy", ".phylip"}:
            self.input_format_combo.setCurrentText("PHYLIP")
        elif ext in {".nex", ".nexus"}:
            self.input_format_combo.setCurrentText("NEXUS")
        if not self.output_edit.text().strip():
            base, _ = os.path.splitext(file_path)
            self.output_edit.setText(
                base + FORMAT_EXTENSIONS[self.output_format_combo.currentText()]
            )

    def _update_output_extension(self):
        output_path = self.output_edit.text().strip()
        if not output_path:
            return
        root, ext = os.path.splitext(output_path)
        if ext.lower() in FORMAT_EXTENSIONS.values():
            self.output_edit.setText(
                root + FORMAT_EXTENSIONS[self.output_format_combo.currentText()]
            )

    def _resolved_output_path(self) -> str:
        output_path = self.output_edit.text().strip()
        if not output_path:
            return ""
        root, ext = os.path.splitext(output_path)
        if ext:
            return output_path
        resolved = root + FORMAT_EXTENSIONS[self.output_format_combo.currentText()]
        self.output_edit.setText(resolved)
        return resolved

    def run_conversion(self):
        input_path = self.input_edit.text().strip()
        output_path = self._resolved_output_path()

        valid, error = validate_input_path(input_path, SUPPORTED_EXTENSIONS)
        if not valid:
            self.log_message(error, "ERROR")
            self.show_status(f"Error: {error}")
            return

        valid, error = validate_output_path(output_path)
        if not valid:
            self.log_message(error, "ERROR")
            self.show_status(f"Error: {error}")
            return

        try:
            written, seq_count, alignment_length = convert_alignment_file(
                input_path=input_path,
                output_path=output_path,
                input_format_label=self.input_format_combo.currentText(),
                output_format_label=self.output_format_combo.currentText(),
            )
            self.log_message(
                f"Converted {written} alignment(s); sequences: {seq_count}; alignment length: {alignment_length}."
            )
            self.log_message(f"Saved converted alignment to: {output_path}")
            self.show_status("Ready")
        except Exception as exc:
            self.log_message(str(exc), "ERROR")
            self.show_status(f"Error: {exc}")

    def clear_all(self):
        self.input_edit.clear()
        self.output_edit.clear()
        self.log_area.clear()
        self.show_status("Ready")

    def show_help(self):
        html = """
<h2>Alignment Format Converter</h2>

<p><b>What does this tool do?</b><br>
Converts alignment files between common bioinformatics formats:
FASTA, CLUSTAL, PHYLIP, and NEXUS. Input sequences must already be
aligned to the same length.</p>

<h3>Quick Start</h3>
<ol>
<li>Select an aligned input file (or drag &amp; drop)</li>
<li>Verify the <b>Input Format</b> &mdash; the tool auto-detects from the file extension</li>
<li>Choose the <b>Output Format</b> and an output path</li>
<li>Click <b>Convert</b></li>
</ol>

<h3>Supported Formats</h3>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>FASTA</b></td><td>&rarr; standard aligned FASTA (<code>.fasta</code>, <code>.fa</code>, <code>.afa</code>)</td></tr>
<tr><td><b>CLUSTAL</b></td><td>&rarr; CLUSTAL-W alignment format (<code>.aln</code>, <code>.clustal</code>)</td></tr>
<tr><td><b>PHYLIP</b></td><td>&rarr; relaxed interleaved PHYLIP (<code>.phy</code>)</td></tr>
<tr><td><b>NEXUS</b></td><td>&rarr; NEXUS alignment block (<code>.nex</code>)</td></tr>
</table>

<h3>Auto-Detection</h3>
<p>The input format is inferred from the file extension when you select a file.
Common extensions are recognised automatically; you can override the
detection manually if needed.</p>

<h3>Output Auto-Naming</h3>
<p>When you select an input file the output path is pre-filled with the
same base name and the extension matching the chosen output format.
Click <b>Save As</b> to choose a different location.</p>

<h3>Limitations</h3>
<ul>
<li>Input sequences must already be <b>aligned to the same length</b>
    (columns must match). This tool does not perform alignment.</li>
<li>NEXUS input may contain a single DATA block with one alignment.</li>
</ul>
"""
        from PyQt6.QtWidgets import (
            QDialog,
            QTextBrowser,
            QVBoxLayout,
            QHBoxLayout,
            QPushButton,
        )

        dlg = QDialog(self)
        dlg.setWindowTitle("Help – Alignment Format Converter")
        dlg.setMinimumWidth(660)
        dlg.setMinimumHeight(440)
        layout = QVBoxLayout()
        browser = QTextBrowser()
        browser.setHtml(html)
        layout.addWidget(browser)
        btn_row = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        dlg.setLayout(layout)
        dlg.exec()
