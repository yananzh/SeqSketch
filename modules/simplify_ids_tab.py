from collections import Counter
import os
import re

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
)

from utils.common_components import BaseTabWidget


SIMPLIFY_MODE_FIRST_TOKEN = "first_token"
SIMPLIFY_MODE_DELIMITER_FIELD = "delimiter_field"
SIMPLIFY_MODE_REGEX_CAPTURE = "regex_capture"
SIMPLIFY_MODE_KEEP_TOKENS = "keep_tokens"


def normalize_identifier(candidate: str) -> str:
    return re.sub(r"\s+", "_", candidate.strip())


def reconstruct_full_header(record) -> str:
    if record.description:
        return f"{record.header} {record.description}"
    return record.header


def simplify_identifier(
    full_header: str,
    original_id: str,
    mode: str,
    delimiter: str,
    field_value: int,
    compiled_pattern,
) -> tuple[str, str | None]:
    if mode == SIMPLIFY_MODE_FIRST_TOKEN:
        tokens = full_header.split()
        return normalize_identifier(tokens[0]) if tokens else original_id, None

    if mode == SIMPLIFY_MODE_KEEP_TOKENS:
        tokens = full_header.split()
        candidate = (
            normalize_identifier("_".join(tokens[:field_value])) if tokens else ""
        )
        return candidate or original_id, None

    if mode == SIMPLIFY_MODE_DELIMITER_FIELD:
        if not delimiter:
            raise ValueError("Delimiter cannot be empty in delimiter-field mode")
        parts = [part.strip() for part in full_header.split(delimiter)]
        if field_value <= len(parts):
            candidate = normalize_identifier(parts[field_value - 1])
            return candidate or original_id, None
        return original_id, "delimiter_miss"

    if mode == SIMPLIFY_MODE_REGEX_CAPTURE:
        if compiled_pattern is None:
            raise ValueError("Regex pattern is required in regex-capture mode")
        match = compiled_pattern.search(full_header)
        if not match:
            return original_id, "regex_no_match"
        if match.groups():
            for group in match.groups():
                if group is not None:
                    candidate = normalize_identifier(group)
                    return candidate or original_id, None
        candidate = normalize_identifier(match.group(0))
        return candidate or original_id, None

    raise ValueError(f"Unsupported simplification mode: {mode}")


def mapping_report_path(output_path: str) -> str:
    base, _ = os.path.splitext(output_path)
    return f"{base}_id_mapping.tsv"


class SimplifyIDsTab(BaseTabWidget):
    """Simplify sequence IDs Tab"""

    def __init__(self):
        super().__init__("Simplify Headers", "file")
        self.init_ui()
        self.connect_signals()
        self.update_mode_controls()

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
                        if self._is_valid_fasta(local):
                            event.acceptProposedAction()
                            return
                event.ignore()

            def dropEvent(self, event):
                urls = event.mimeData().urls()
                if urls:
                    local = urls[0].toLocalFile()
                    if self._is_valid_fasta(local):
                        self.setText(local)
                        self.file_dropped.emit(local)
                        event.acceptProposedAction()
                        return
                event.ignore()

            @staticmethod
            def _is_valid_fasta(path: str) -> bool:
                allowed = {".fasta", ".fa", ".fas"}
                try:
                    ext = os.path.splitext(path)[1].lower()
                    return os.path.isfile(path) and ext in allowed
                except Exception:
                    return False

        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Input FASTA file:"))
        self.input_edit = FileDropLineEdit()
        self.input_edit.setPlaceholderText("Select or drop a FASTA file...")
        self.input_edit.setMinimumWidth(320)
        self.input_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.input_btn = QPushButton("Browse")
        self.input_btn.setFixedWidth(90)
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(self.input_btn)
        input_layout.setSpacing(8)

        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output file:"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText(
            "Choose where to save the simplified file..."
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

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Simplify mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("First token", SIMPLIFY_MODE_FIRST_TOKEN)
        self.mode_combo.addItem("Delimiter field", SIMPLIFY_MODE_DELIMITER_FIELD)
        self.mode_combo.addItem("Regex capture", SIMPLIFY_MODE_REGEX_CAPTURE)
        self.mode_combo.addItem("Keep first N tokens", SIMPLIFY_MODE_KEEP_TOKENS)
        mode_layout.addWidget(self.mode_combo)

        self.preserve_description_checkbox = QCheckBox("Preserve description")
        self.export_mapping_checkbox = QCheckBox("Export ID mapping report")
        mode_layout.addWidget(self.preserve_description_checkbox)
        mode_layout.addWidget(self.export_mapping_checkbox)
        mode_layout.addStretch(1)

        parameter_layout = QHBoxLayout()
        parameter_layout.setSpacing(8)
        self.delimiter_label = QLabel("Delimiter:")
        self.delimiter_edit = QLineEdit()
        self.delimiter_edit.setPlaceholderText("Example: |")
        self.delimiter_edit.setFixedWidth(110)
        self.delimiter_edit.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )

        self.field_label = QLabel("Field index:")
        self.field_spin = QSpinBox()
        self.field_spin.setMinimum(1)
        self.field_spin.setMaximum(99)
        self.field_spin.setValue(1)
        self.field_spin.setFixedWidth(80)
        self.field_spin.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )

        self.regex_label = QLabel("Regex:")
        self.regex_edit = QLineEdit()
        self.regex_edit.setPlaceholderText(r"Example: ref\|([^|]+)\|")
        self.regex_edit.setFixedWidth(260)
        self.regex_edit.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )

        parameter_layout.addWidget(self.delimiter_label)
        parameter_layout.addWidget(self.delimiter_edit)
        parameter_layout.addWidget(self.field_label)
        parameter_layout.addWidget(self.field_spin)
        parameter_layout.addWidget(self.regex_label)
        parameter_layout.addWidget(self.regex_edit)
        parameter_layout.addStretch(1)

        control_layout = QHBoxLayout()
        control_layout.addStretch(1)
        self.run_btn = QPushButton("Start")
        self.clear_btn = QPushButton("Clear")
        control_layout.addWidget(self.run_btn)
        control_layout.addWidget(self.clear_btn)
        control_layout.setSpacing(10)

        self.add_content_layout(input_layout)
        self.add_content_layout(output_layout)
        self.add_content_layout(mode_layout)
        self.add_content_layout(parameter_layout)
        self.add_content_layout(control_layout)
        self.content_area.addStretch()

    def current_mode(self) -> str:
        return str(self.mode_combo.currentData())

    def update_mode_controls(self):
        mode = self.current_mode()
        delimiter_mode = mode == SIMPLIFY_MODE_DELIMITER_FIELD
        regex_mode = mode == SIMPLIFY_MODE_REGEX_CAPTURE
        keep_tokens_mode = mode == SIMPLIFY_MODE_KEEP_TOKENS

        self.delimiter_label.setVisible(delimiter_mode)
        self.delimiter_edit.setVisible(delimiter_mode)
        self.delimiter_edit.setEnabled(delimiter_mode)

        self.regex_label.setVisible(regex_mode)
        self.regex_edit.setVisible(regex_mode)
        self.regex_edit.setEnabled(regex_mode)

        self.field_label.setVisible(delimiter_mode or keep_tokens_mode)
        self.field_spin.setVisible(delimiter_mode or keep_tokens_mode)
        self.field_spin.setEnabled(delimiter_mode or keep_tokens_mode)
        if delimiter_mode:
            self.field_label.setText("Field index:")
            self.field_spin.setToolTip(
                "1-based field index after splitting by delimiter"
            )
        elif keep_tokens_mode:
            self.field_label.setText("Token count:")
            self.field_spin.setToolTip("Keep the first N whitespace-separated tokens")

    def connect_signals(self):
        self.input_btn.clicked.connect(self.select_input_file)
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_simplify)
        self.clear_btn.clicked.connect(self.clear_all)
        self.mode_combo.currentIndexChanged.connect(self.update_mode_controls)
        if hasattr(self.input_edit, "file_dropped"):
            self.input_edit.file_dropped.connect(self.handle_input_file_selected)

    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select FASTA file",
            "",
            "FASTA Files (*.fasta *.fa *.fas);;All Files (*)",
        )
        if file_path:
            self.handle_input_file_selected(file_path)

    def handle_input_file_selected(self, file_path: str):
        self.input_edit.setText(file_path)
        base = os.path.splitext(os.path.basename(file_path))[0]
        suggested = os.path.join(os.path.dirname(file_path), base + "_simplified.fasta")
        if not self.output_edit.text().strip():
            self.output_edit.setText(suggested)
        self.show_status("Input file selected")

    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save simplified file",
            "",
            "FASTA Files (*.fasta *.fa *.fas);;All Files (*)",
        )
        if file_path:
            self.output_edit.setText(file_path)

    def clear_all(self):
        self.input_edit.clear()
        self.output_edit.clear()
        self.delimiter_edit.clear()
        self.regex_edit.clear()
        self.field_spin.setValue(1)
        self.mode_combo.setCurrentIndex(0)
        self.preserve_description_checkbox.setChecked(False)
        self.export_mapping_checkbox.setChecked(False)
        self.log_area.clear()
        self.show_status("Cleared")

    def set_running_state(self, running: bool):
        super().set_running_state(running)
        self.run_btn.setEnabled(not running)
        self.input_btn.setEnabled(not running)
        self.output_btn.setEnabled(not running)
        self.mode_combo.setEnabled(not running)
        self.preserve_description_checkbox.setEnabled(not running)
        self.export_mapping_checkbox.setEnabled(not running)
        self.delimiter_edit.setEnabled(
            not running and self.current_mode() == SIMPLIFY_MODE_DELIMITER_FIELD
        )
        self.regex_edit.setEnabled(
            not running and self.current_mode() == SIMPLIFY_MODE_REGEX_CAPTURE
        )
        self.field_spin.setEnabled(
            not running
            and self.current_mode()
            in {SIMPLIFY_MODE_DELIMITER_FIELD, SIMPLIFY_MODE_KEEP_TOKENS}
        )

    def run_simplify(self):
        input_path = self.input_edit.text().strip()
        output_path = self.output_edit.text().strip()
        mode = self.current_mode()
        delimiter = self.delimiter_edit.text()
        regex_pattern = self.regex_edit.text().strip()
        field_value = self.field_spin.value()
        preserve_description = self.preserve_description_checkbox.isChecked()
        export_mapping = self.export_mapping_checkbox.isChecked()

        from utils.common_components import validate_input_path, validate_output_path

        valid, error = validate_input_path(input_path, [".fasta", ".fa", ".fas"])
        if not valid:
            self.log_message(error, "ERROR")
            return
        valid, error = validate_output_path(output_path)
        if not valid:
            self.log_message(error, "ERROR")
            return

        compiled_pattern = None
        if mode == SIMPLIFY_MODE_DELIMITER_FIELD and not delimiter:
            self.log_message(
                "Please enter a delimiter for delimiter-field mode", "ERROR"
            )
            return
        if mode == SIMPLIFY_MODE_REGEX_CAPTURE:
            if not regex_pattern:
                self.log_message(
                    "Please enter a regex pattern for regex-capture mode", "ERROR"
                )
                return
            try:
                compiled_pattern = re.compile(regex_pattern)
            except re.error as exc:
                self.log_message(f"Invalid regex pattern: {exc}", "ERROR")
                return

        self.set_running_state(True)
        self.log_message("Starting ID simplification...", "INFO")
        try:
            from modules.fasta_processor import FASTAProcessor

            self.show_status("Loading FASTA file...")
            processor = FASTAProcessor()
            if not processor.read_file(input_path):
                self.log_message("Unable to read FASTA file", "ERROR")
                return
            records = processor.records
            if not records:
                self.log_message("No sequences found in FASTA file", "ERROR")
                return
            self.log_message(f"Loaded {len(records)} sequences", "INFO")

            self.show_status("Simplifying sequence IDs...")
            mapping_rows = [
                "Original_ID\tSimplified_ID\tChanged\tDescription_Preserved\tMode"
            ]
            warning_counts = Counter()
            changed_count = 0
            unchanged_count = 0
            empty_count = 0
            simplified_ids = []

            for record in records:
                original_id = record.header
                full_header = reconstruct_full_header(record)
                simplified_id, warning_key = simplify_identifier(
                    full_header,
                    original_id,
                    mode,
                    delimiter,
                    field_value,
                    compiled_pattern,
                )

                if not simplified_id:
                    empty_count += 1
                    warning_counts["empty_id"] += 1
                    simplified_id = original_id
                if warning_key:
                    warning_counts[warning_key] += 1

                description_changed = (
                    bool(record.description) and not preserve_description
                )
                changed = simplified_id != original_id or description_changed
                if changed:
                    changed_count += 1
                else:
                    unchanged_count += 1

                record.header = simplified_id
                if not preserve_description:
                    record.description = ""

                simplified_ids.append(simplified_id)
                mapping_rows.append(
                    f"{original_id}\t{simplified_id}\t{str(changed)}\t{str(preserve_description)}\t{mode}"
                )

            duplicate_ids = {
                sequence_id: count
                for sequence_id, count in Counter(simplified_ids).items()
                if count > 1
            }
            if empty_count:
                self.log_message(
                    f"Simplification produced empty IDs for {empty_count} sequence(s)",
                    "ERROR",
                )
                return
            if duplicate_ids:
                preview = ", ".join(
                    f"{sequence_id} (x{count})"
                    for sequence_id, count in sorted(duplicate_ids.items())[:5]
                )
                self.log_message(
                    f"Duplicate simplified IDs detected; output not saved: {preview}",
                    "ERROR",
                )
                return

            self.log_message(
                f"Simplified {changed_count} sequence IDs; {unchanged_count} sequence(s) unchanged",
                "INFO",
            )
            if warning_counts["delimiter_miss"]:
                self.log_message(
                    f"Delimiter was not usable for {warning_counts['delimiter_miss']} sequence(s); kept original IDs for those records",
                    "WARNING",
                )
            if warning_counts["regex_no_match"]:
                self.log_message(
                    f"Regex did not match {warning_counts['regex_no_match']} sequence(s); kept original IDs for those records",
                    "WARNING",
                )
            if unchanged_count == len(records):
                self.log_message(
                    "Selected simplification rule did not change any IDs",
                    "WARNING",
                )

            self.show_status("Saving results...")
            if not processor.save_file(output_path):
                self.log_message("Failed to save file", "ERROR")
                return

            if export_mapping:
                mapping_path = mapping_report_path(output_path)
                with open(mapping_path, "w", encoding="utf-8") as handle:
                    handle.write("\n".join(mapping_rows))
                self.log_message(f"ID mapping report saved to: {mapping_path}", "INFO")

            self.log_message(
                f"Simplification complete! Saved to: {output_path}",
                "INFO",
            )
            self.show_status("Complete")
        except Exception as e:
            import traceback

            self.log_message(
                f"Error during processing: {e}\n{traceback.format_exc()}", "ERROR"
            )
            self.show_status("Error")
        finally:
            self.set_running_state(False)

    def show_help(self):
        help_text = """
<h3>Simplify Headers</h3>
<p><b>Description:</b></p>
<p>Convert complex FASTA headers into cleaner IDs using one of several parsing rules. This is useful when headers come from NCBI, UniProt, assemblies, or lab-specific naming schemes.</p>

<p><b>Modes:</b></p>
<ul>
<li><b>First token:</b> keep the first whitespace-separated token</li>
<li><b>Delimiter field:</b> split the full header by a delimiter and keep the selected 1-based field</li>
<li><b>Regex capture:</b> use the first capturing group (or full match) from a regex pattern</li>
<li><b>Keep first N tokens:</b> keep the first N whitespace-separated tokens, joined with underscores</li>
</ul>

<p><b>Examples:</b></p>
<pre>
Input header:
&gt;gi|12345|ref|NM_001101.5| Homo sapiens gene alpha

First token:
gi|12345|ref|NM_001101.5|

Delimiter field, delimiter="|", field index=4:
NM_001101.5

Regex capture, pattern=ref\|([^|]+)\|:
NM_001101.5

Keep first N tokens, token count=3:
gi|12345|ref|NM_001101.5|_Homo_sapiens
</pre>

<p><b>Safety features:</b></p>
<ul>
<li>Detects duplicate IDs after simplification and blocks saving by default</li>
<li>Optionally preserves description text</li>
<li>Optionally exports an ID mapping report</li>
</ul>

<p><b>Typical workflow:</b></p>
<ol>
<li>Select the input FASTA file and output file</li>
<li>Choose the simplification mode</li>
<li>Fill in the delimiter, regex, or token-count parameter when that mode requires it</li>
<li>Optionally enable <b>Preserve description</b> and <b>Export ID mapping report</b></li>
<li>Click <b>Start</b> and review the log for unchanged IDs, duplicates, or rule misses</li>
</ol>

<p><b>Notes:</b></p>
<ul>
<li>If the selected rule does not match some headers, the original IDs are kept and a warning is logged.</li>
<li>Delimiter field uses 1-based indexing. For example, field index 4 means the fourth part after splitting.</li>
<li>Regex capture prefers the first capture group. If no capture group exists, the full match is used.</li>
</ul>
        """

        dialog = QDialog(self)
        dialog.setWindowTitle("Help - Simplify Headers")
        dialog.setFixedSize(820, 520)

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
