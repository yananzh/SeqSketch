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
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from utils.common_components import BaseTabWidget, FileDropLineEdit, apply_sequence_editor_style


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


def _apply_case_transform(identifier: str, case_mode: str) -> str:
    """Apply case transformation to a simplified identifier."""
    if case_mode == "upper":
        return identifier.upper()
    if case_mode == "lower":
        return identifier.lower()
    return identifier


class SimplifyIDsTab(BaseTabWidget):
    """Simplify sequence IDs Tab"""

    def __init__(self):
        super().__init__("Simplify Headers", "file")
        self.init_ui()
        self.connect_signals()
        self.update_mode_controls()

    def init_ui(self):
        _label_width = 120

        # ── Input file ──
        input_layout = QHBoxLayout()
        input_label = QLabel("Input FASTA file:")
        input_label.setFixedWidth(_label_width)
        input_layout.addWidget(input_label)
        self.input_edit = FileDropLineEdit()
        self.input_edit.setPlaceholderText("Select or drop a FASTA file...")
        self.input_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.input_btn = QPushButton("Browse")
        self.input_btn.setFixedWidth(90)
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(self.input_btn)
        input_layout.setSpacing(8)

        # ── Output file ──
        output_layout = QHBoxLayout()
        output_label = QLabel("Output file:")
        output_label.setFixedWidth(_label_width)
        output_layout.addWidget(output_label)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText(
            "Choose where to save the simplified file..."
        )
        self.output_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.output_btn = QPushButton("Save As")
        self.output_btn.setFixedWidth(90)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        output_layout.setSpacing(8)

        # ── Mode selector with dynamic hint ──
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Simplify mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("First token", SIMPLIFY_MODE_FIRST_TOKEN)
        self.mode_combo.addItem("Delimiter field", SIMPLIFY_MODE_DELIMITER_FIELD)
        self.mode_combo.addItem("Regex capture", SIMPLIFY_MODE_REGEX_CAPTURE)
        self.mode_combo.addItem("Keep first N tokens", SIMPLIFY_MODE_KEEP_TOKENS)
        mode_layout.addWidget(self.mode_combo)
        self.mode_hint_label = QLabel("")
        self.mode_hint_label.setStyleSheet("color: #888; font-size: 13px;")
        mode_layout.addWidget(self.mode_hint_label)
        mode_layout.addStretch(1)

        # ── Parameter panels (QStackedWidget, one per mode) ──
        self.param_stack = QStackedWidget()

        # Panel 0 – First token (no extra params)
        pg0 = QWidget()
        pg0l = QHBoxLayout(pg0)
        pg0l.setContentsMargins(0, 0, 0, 0)
        pg0l.addWidget(QLabel("No extra parameters — keeps the first whitespace-separated token."))
        pg0l.addStretch()
        self.param_stack.addWidget(pg0)

        # Panel 1 – Delimiter field
        pg1 = QWidget()
        pg1l = QHBoxLayout(pg1)
        pg1l.setContentsMargins(0, 0, 0, 0)
        pg1l.addWidget(QLabel("Delimiter:"))
        self.delimiter_edit = QLineEdit()
        self.delimiter_edit.setPlaceholderText("e.g. |")
        self.delimiter_edit.setFixedWidth(110)
        pg1l.addWidget(self.delimiter_edit)
        pg1l.addWidget(QLabel("Field index:"))
        self.field_spin = QSpinBox()
        self.field_spin.setMinimum(1)
        self.field_spin.setMaximum(99)
        self.field_spin.setValue(1)
        self.field_spin.setFixedWidth(70)
        self.field_spin.setToolTip("1-based field index after splitting by delimiter")
        pg1l.addWidget(self.field_spin)
        pg1l.addStretch()
        self.param_stack.addWidget(pg1)

        # Panel 2 – Regex capture
        pg2 = QWidget()
        pg2l = QHBoxLayout(pg2)
        pg2l.setContentsMargins(0, 0, 0, 0)
        pg2l.addWidget(QLabel("Regex:"))
        self.regex_edit = QLineEdit()
        self.regex_edit.setPlaceholderText(r"e.g. ref\|([^|]+)\|")
        self.regex_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        pg2l.addWidget(self.regex_edit)
        self.common_patterns_btn = QPushButton("Common Patterns ▾")
        self.common_patterns_btn.setFixedWidth(150)
        self.common_patterns_btn.clicked.connect(self._show_common_patterns)
        pg2l.addWidget(self.common_patterns_btn)
        self.param_stack.addWidget(pg2)

        # Panel 3 – Keep first N tokens
        pg3 = QWidget()
        pg3l = QHBoxLayout(pg3)
        pg3l.setContentsMargins(0, 0, 0, 0)
        pg3l.addWidget(QLabel("Token count:"))
        self.token_count_spin = QSpinBox()
        self.token_count_spin.setMinimum(1)
        self.token_count_spin.setMaximum(99)
        self.token_count_spin.setValue(2)
        self.token_count_spin.setFixedWidth(70)
        self.token_count_spin.setToolTip(
            "Keep the first N whitespace-separated tokens, joined with underscores"
        )
        pg3l.addWidget(self.token_count_spin)
        pg3l.addStretch()
        self.param_stack.addWidget(pg3)

        # ── Preview panel ──
        self.preview_panel = QPlainTextEdit()
        self.preview_panel.setReadOnly(True)
        self.preview_panel.setPlaceholderText(
            "Click Preview to see the first few simplified IDs here..."
        )
        self.preview_panel.setMaximumHeight(130)
        apply_sequence_editor_style(self.preview_panel)

        # ── Options row ──
        options_layout = QHBoxLayout()
        self.preserve_description_checkbox = QCheckBox("Preserve description")
        self.preserve_description_checkbox.setToolTip(
            "Keep the text after the first space in the FASTA header"
        )
        self.export_mapping_checkbox = QCheckBox("Export ID mapping report")
        self.auto_number_checkbox = QCheckBox("Auto-number duplicate IDs")
        self.auto_number_checkbox.setToolTip(
            "If simplification produces duplicate IDs, append _2, _3, etc. instead of stopping"
        )
        options_layout.addWidget(self.preserve_description_checkbox)
        options_layout.addWidget(self.export_mapping_checkbox)
        options_layout.addWidget(self.auto_number_checkbox)
        options_layout.addStretch(1)

        # ── Case / prefix / suffix ──
        transform_layout = QHBoxLayout()
        transform_layout.addWidget(QLabel("Case:"))
        self.case_combo = QComboBox()
        self.case_combo.addItem("As-is", "as_is")
        self.case_combo.addItem("UPPERCASE", "upper")
        self.case_combo.addItem("lowercase", "lower")
        transform_layout.addWidget(self.case_combo)
        transform_layout.addWidget(QLabel("Prefix:"))
        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText("Optional...")
        self.prefix_edit.setFixedWidth(110)
        transform_layout.addWidget(self.prefix_edit)
        transform_layout.addWidget(QLabel("Suffix:"))
        self.suffix_edit = QLineEdit()
        self.suffix_edit.setPlaceholderText("Optional...")
        self.suffix_edit.setFixedWidth(110)
        transform_layout.addWidget(self.suffix_edit)
        transform_layout.addStretch(1)

        # ── Control buttons ──
        control_layout = QHBoxLayout()
        control_layout.addStretch(1)
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setToolTip(
            "Preview the first 5 simplified IDs without saving"
        )
        self.run_btn = QPushButton("Start")
        self.clear_btn = QPushButton("Clear")
        control_layout.addWidget(self.preview_btn)
        control_layout.addWidget(self.run_btn)
        control_layout.addWidget(self.clear_btn)
        control_layout.setSpacing(10)

        # ── Assemble ──
        self.add_content_layout(input_layout)
        self.add_content_layout(output_layout)
        self.add_content_layout(mode_layout)
        self.add_content_widget(self.param_stack)
        self.add_content_widget(self.preview_panel)
        self.add_content_layout(options_layout)
        self.add_content_layout(transform_layout)
        self.add_content_layout(control_layout)
        self.content_area.addStretch()

    def current_mode(self) -> str:
        return str(self.mode_combo.currentData())

    def update_mode_controls(self):
        mode = self.current_mode()
        _mode_hints = {
            SIMPLIFY_MODE_FIRST_TOKEN: "Keeps the first whitespace-separated word as the new ID",
            SIMPLIFY_MODE_DELIMITER_FIELD: "Splits the header by a delimiter and picks one field",
            SIMPLIFY_MODE_REGEX_CAPTURE: "Uses a regex capturing group (or full match) as the new ID",
            SIMPLIFY_MODE_KEEP_TOKENS: "Keeps the first N whitespace-separated tokens, joined with underscores",
        }
        self.mode_hint_label.setText(_mode_hints.get(mode, ""))

        _page_map = {
            SIMPLIFY_MODE_FIRST_TOKEN: 0,
            SIMPLIFY_MODE_DELIMITER_FIELD: 1,
            SIMPLIFY_MODE_REGEX_CAPTURE: 2,
            SIMPLIFY_MODE_KEEP_TOKENS: 3,
        }
        self.param_stack.setCurrentIndex(_page_map.get(mode, 0))

    def connect_signals(self):
        self.input_btn.clicked.connect(self.select_input_file)
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_simplify)
        self.preview_btn.clicked.connect(self.preview_simplify)
        self.clear_btn.clicked.connect(self.clear_all)
        self.mode_combo.currentIndexChanged.connect(self.update_mode_controls)
        if hasattr(self.input_edit, "file_dropped"):
            self.input_edit.file_dropped.connect(self.handle_input_file_selected)

    def preview_simplify(self):
        """Preview the first 5 simplified IDs in the dedicated preview panel."""
        input_path = self.input_edit.text().strip()
        mode = self.current_mode()
        delimiter = self.delimiter_edit.text()
        regex_pattern = self.regex_edit.text().strip()
        preserve_description = self.preserve_description_checkbox.isChecked()
        prefix = self.prefix_edit.text().strip()
        suffix = self.suffix_edit.text().strip()
        case_mode = self.case_combo.currentData()

        if mode == SIMPLIFY_MODE_DELIMITER_FIELD:
            field_value = self.field_spin.value()
        elif mode == SIMPLIFY_MODE_KEEP_TOKENS:
            field_value = self.token_count_spin.value()
        else:
            field_value = 1

        from utils.common_components import validate_input_path

        valid, error = validate_input_path(
            input_path,
            [".fasta", ".fa", ".fas", ".fna", ".ffn", ".faa", ".frn", ".txt"],
        )
        if not valid:
            self.log_message(error, "ERROR")
            return

        compiled_pattern = None
        if mode == SIMPLIFY_MODE_REGEX_CAPTURE:
            if not regex_pattern:
                self.log_message("Please enter a regex pattern for preview", "ERROR")
                return
            try:
                compiled_pattern = re.compile(regex_pattern)
            except re.error as exc:
                self.log_message(f"Invalid regex pattern: {exc}", "ERROR")
                return
        if mode == SIMPLIFY_MODE_DELIMITER_FIELD and not delimiter:
            self.log_message("Please enter a delimiter for preview", "ERROR")
            return

        try:
            from modules.fasta_processor import FASTAProcessor

            processor = FASTAProcessor()
            if not processor.read_file(input_path):
                self.log_message("Unable to read FASTA file", "ERROR")
                return
            records = processor.records[:5]
            if not records:
                self.log_message("No sequences found in FASTA file", "ERROR")
                return

            lines = []
            for idx, record in enumerate(records, start=1):
                original_id = record.header
                full_header = (
                    f"{record.header} {record.description}".strip()
                    if record.description
                    else record.header
                )
                simplified_id, _ = simplify_identifier(
                    full_header, original_id, mode, delimiter, field_value, compiled_pattern
                )
                simplified_id = _apply_case_transform(simplified_id, case_mode)
                if prefix:
                    simplified_id = prefix + simplified_id
                if suffix:
                    simplified_id = simplified_id + suffix
                desc_note = (
                    " [desc preserved]"
                    if preserve_description and record.description
                    else ""
                )
                changed_mark = " *" if simplified_id != original_id else ""
                lines.append(
                    f"#{idx}:  {original_id}  →  {simplified_id}{changed_mark}{desc_note}"
                )
            self.preview_panel.setPlainText("\n".join(lines))
            self.log_message("Preview updated — see panel above", "INFO")
        except Exception as e:
            self.log_message(f"Preview error: {e}", "ERROR")

    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select FASTA file",
            "",
            "FASTA Files (*.fasta *.fa *.fas *.fna *.ffn *.faa *.frn *.txt);;All Files (*)",
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
        self.token_count_spin.setValue(2)
        self.mode_combo.setCurrentIndex(0)
        self.preserve_description_checkbox.setChecked(False)
        self.export_mapping_checkbox.setChecked(False)
        self.auto_number_checkbox.setChecked(False)
        self.case_combo.setCurrentIndex(0)
        self.prefix_edit.clear()
        self.suffix_edit.clear()
        self.preview_panel.clear()
        self.log_area.clear()
        self.show_status("Cleared")

    def set_running_state(self, running: bool):
        super().set_running_state(running)
        self.run_btn.setEnabled(not running)
        self.preview_btn.setEnabled(not running)
        self.input_btn.setEnabled(not running)
        self.output_btn.setEnabled(not running)
        self.mode_combo.setEnabled(not running)
        self.preserve_description_checkbox.setEnabled(not running)
        self.export_mapping_checkbox.setEnabled(not running)
        self.auto_number_checkbox.setEnabled(not running)
        self.case_combo.setEnabled(not running)
        self.prefix_edit.setEnabled(not running)
        self.suffix_edit.setEnabled(not running)
        self.delimiter_edit.setEnabled(
            not running and self.current_mode() == SIMPLIFY_MODE_DELIMITER_FIELD
        )
        self.regex_edit.setEnabled(
            not running and self.current_mode() == SIMPLIFY_MODE_REGEX_CAPTURE
        )
        self.field_spin.setEnabled(
            not running and self.current_mode() == SIMPLIFY_MODE_DELIMITER_FIELD
        )
        self.token_count_spin.setEnabled(
            not running and self.current_mode() == SIMPLIFY_MODE_KEEP_TOKENS
        )

    def run_simplify(self):
        input_path = self.input_edit.text().strip()
        output_path = self.output_edit.text().strip()
        mode = self.current_mode()
        delimiter = self.delimiter_edit.text()
        regex_pattern = self.regex_edit.text().strip()
        preserve_description = self.preserve_description_checkbox.isChecked()
        export_mapping = self.export_mapping_checkbox.isChecked()
        auto_number = self.auto_number_checkbox.isChecked()
        case_mode = self.case_combo.currentData()
        prefix = self.prefix_edit.text().strip()
        suffix = self.suffix_edit.text().strip()

        if mode == SIMPLIFY_MODE_DELIMITER_FIELD:
            field_value = self.field_spin.value()
        elif mode == SIMPLIFY_MODE_KEEP_TOKENS:
            field_value = self.token_count_spin.value()
        else:
            field_value = 1

        from utils.common_components import validate_input_path, validate_output_path

        valid, error = validate_input_path(
            input_path,
            [".fasta", ".fa", ".fas", ".fna", ".ffn", ".faa", ".frn", ".txt"],
        )
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

                # Apply case transform
                simplified_id = _apply_case_transform(simplified_id, case_mode)
                # Apply prefix / suffix
                if prefix:
                    simplified_id = prefix + simplified_id
                if suffix:
                    simplified_id = simplified_id + suffix

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

            duplicate_counts = Counter(simplified_ids)
            duplicate_ids = {
                sequence_id: count
                for sequence_id, count in duplicate_counts.items()
                if count > 1
            }
            if empty_count:
                self.log_message(
                    f"Simplification produced empty IDs for {empty_count} sequence(s)",
                    "ERROR",
                )
                return
            if duplicate_ids:
                if auto_number:
                    self.log_message(
                        f"Auto-numbering {sum(duplicate_counts.values()) - len(duplicate_counts)} duplicate ID(s)...",
                        "WARNING",
                    )
                    auto_count = 0
                    seen = {}
                    for record in records:
                        base_id = record.header
                        if base_id in seen:
                            seen[base_id] += 1
                            record.header = f"{base_id}_{seen[base_id]}"
                            auto_count += 1
                        else:
                            seen[base_id] = 1
                    self.log_message(
                        f"Auto-numbered {auto_count} duplicate ID(s)",
                        "INFO",
                    )
                else:
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

    def _show_common_patterns(self):
        """Show a popup menu of common regex patterns for common FASTA ID formats."""
        menu = QMenu(self)
        _patterns = [
            ("NCBI GI / GenBank  —  gi|number|...", r"gi\|\d+\|"),
            ("RefSeq accession  —  ref|NM_...|", r"ref\|([^|]+)\|"),
            ("UniProt ID  —  sp|P12345|", r"sp\|([^|]+)\|"),
            ("Ensembl ID  —  ENSG...", r"(ENS[A-Z]{0,3}\d{11})"),
            ("GenBank accession only  —  [A-Z]{1,4}\\d{5,9}", r"([A-Z]{1,4}\d{5,9})"),
            ("First word after '>'  —  >gene_name ...", r"^[^|]*?(\S+)"),
            ("Extract anything between pipes (field 3)", r"^[^|]*\|[^|]*\|([^|]+)"),
        ]
        for label, pattern in _patterns:
            action = menu.addAction(label)
            action.setData(pattern)
        chosen = menu.exec(self.common_patterns_btn.mapToGlobal(
            self.common_patterns_btn.rect().bottomLeft()
        ))
        if chosen and chosen.data():
            self.regex_edit.setText(chosen.data())

    def show_help(self):
        help_text = """
<h2>Simplify Headers &mdash; Clean Up FASTA IDs</h2>

<p><b>What does this tool do?</b><br>
It takes complex FASTA headers (like those from NCBI, UniProt, or assemblies)
and extracts shorter, cleaner sequence IDs using one of four parsing rules.</p>

<h3>Which mode should I choose?</h3>
<p><b>Look at your header and follow this guide:</b></p>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>Your header looks like</b></td><td><b>&rarr; Use this mode</b></td></tr>
<tr><td><code>&gt;NM_001101.5 Homo sapiens gene</code></td><td>&rarr; <b>First token</b></td></tr>
<tr><td><code>&gt;gi|12345|ref|NM_001101.5| gene</code></td><td>&rarr; <b>Delimiter field</b> with <code>|</code></td></tr>
<tr><td><code>&gt;tr|A0A0A0|A0A0A0_HUMAN ...</code></td><td>&rarr; <b>Regex capture</b> or Delimiter field</td></tr>
<tr><td><code>&gt;contig_123 length=5000 cov=10.5</code></td><td>&rarr; <b>Keep first N tokens</b></td></tr>
</table>

<h3>Quick Start</h3>
<ol>
<li>Select a FASTA file</li>
<li>Choose a simplification mode from the dropdown &mdash; a hint will appear</li>
<li>Fill in any required parameters (delimiter, regex, or token count)</li>
<li><b>Click Preview</b> to check the first 5 IDs before running</li>
<li>Adjust options as needed (case, prefix/suffix, description)</li>
<li>Click <b>Start</b> to process the entire file</li>
</ol>

<h3>Modes in Detail</h3>
<ul>
<li><b>First token</b> &mdash; keeps the first whitespace-separated word.
Best when headers are <code>&gt;accession description</code>.</li>
<li><b>Delimiter field</b> &mdash; splits by a character (e.g. <code>|</code>) and
picks one field. Field index is 1-based (1 = first).</li>
<li><b>Regex capture</b> &mdash; uses a regular expression. The first capture
group <code>(...)</code> becomes the new ID. Use the
<b>Common Patterns</b> dropdown for help.</li>
<li><b>Keep first N tokens</b> &mdash; joins the first N whitespace-separated
words with underscores.</li>
</ul>

<h3>Extra Options</h3>
<ul>
<li><b>Case</b> &mdash; force IDs to UPPERCASE or lowercase.</li>
<li><b>Prefix / Suffix</b> &mdash; add text before or after every ID (e.g. a
sample name).</li>
<li><b>Preserve description</b> &mdash; keep the text after the first space in
the original header (the annotation part).</li>
<li><b>Auto-number duplicates</b> &mdash; if two sequences end up with the same
simplified ID, append <code>_2</code>, <code>_3</code> instead of failing.</li>
<li><b>Export ID mapping report</b> &mdash; save a TSV file showing every
old &rarr; new ID mapping for your records.</li>
</ul>

<h3>Examples</h3>
<pre>
Input:  &gt;gi|12345|ref|NM_001101.5| Homo sapiens gene alpha

First token          &rarr;  gi|12345|ref|NM_001101.5|
Delimiter "|" field 4 &rarr;  NM_001101.5
Regex  ref\\|([^|]+)\\|    &rarr;  NM_001101.5
Keep 3 tokens        &rarr;  gi|12345|ref|NM_001101.5|_Homo_sapiens
</pre>

<h3>Tips</h3>
<ul>
<li>Always <b>Preview</b> before running on a large file.</li>
<li>The <b>Common Patterns</b> button (regex mode) has presets for
NCBI, UniProt, Ensembl, and GenBank IDs.</li>
<li>If no IDs change, double-check the mode and parameters match your
header format &mdash; warnings in the log will tell you how many were skipped.</li>
</ul>
        """

        dialog = QDialog(self)
        dialog.setWindowTitle("Help - Simplify Headers")
        dialog.setFixedSize(840, 620)

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
