from collections import Counter
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QGridLayout,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from utils.common_components import FASTAWorker, BaseTabWidget
import os


NUCLEOTIDE_BASES = set("ACGTUNRYMKSWBDHV")
AMBIGUOUS_BASES = set("RYMKSWBDHV")
PROTEIN_BASES = set("ABCDEFGHIKLMNPQRSTVWXYZ*-")
VALID_SEQUENCE_CHARS = NUCLEOTIDE_BASES | PROTEIN_BASES


def compute_n50_l50(lengths: list[int]) -> tuple[int, int]:
    nonzero_lengths = sorted((length for length in lengths if length > 0), reverse=True)
    if not nonzero_lengths:
        return 0, 0

    half_total = sum(nonzero_lengths) / 2
    cumulative = 0
    for index, length in enumerate(nonzero_lengths, start=1):
        cumulative += length
        if cumulative >= half_total:
            return length, index
    return 0, 0


def detect_sequence_type(sequence: str) -> str:
    letters = {char for char in sequence.upper() if char.isalpha()}
    if not letters:
        return "Mixed/Unknown"

    invalid_letters = letters - VALID_SEQUENCE_CHARS
    if invalid_letters:
        return "Mixed/Unknown"

    if letters <= NUCLEOTIDE_BASES:
        return "DNA/RNA"

    if letters <= PROTEIN_BASES and (letters - NUCLEOTIDE_BASES):
        return "Protein"

    return "Mixed/Unknown"


def format_metric_value(value) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def analyze_record(record) -> dict:
    sequence = record.sequence.upper()
    invalid_chars = sorted({
        char for char in sequence if char not in VALID_SEQUENCE_CHARS
    })
    invalid_char_count = sum(1 for char in sequence if char not in VALID_SEQUENCE_CHARS)
    sequence_type = detect_sequence_type(sequence)
    if invalid_char_count:
        sequence_type = "Mixed/Unknown"

    gc_content = None
    n_count = None
    ambiguous_count = None
    if sequence_type == "DNA/RNA":
        n_count = sequence.count("N")
        ambiguous_count = sum(sequence.count(base) for base in AMBIGUOUS_BASES)
        gc_total = sequence.count("G") + sequence.count("C")
        gc_content = (gc_total / len(sequence) * 100) if sequence else 0.0

    return {
        "sequence_id": record.header,
        "length": record.length,
        "sequence_type": sequence_type,
        "gc_content": gc_content,
        "n_count": n_count,
        "ambiguous_count": ambiguous_count,
        "invalid_char_count": invalid_char_count,
        "invalid_chars": "".join(invalid_chars) if invalid_chars else "-",
        "description_length": len(record.description),
    }


def build_statistics_report(records) -> tuple[dict, list[dict], list[str]]:
    if not records:
        raise ValueError("No sequences found in FASTA file")

    lengths = [record.length for record in records]
    total = len(records)
    total_length = sum(lengths)
    avg_len = total_length / total if total else 0.0
    min_len = min(lengths) if lengths else 0
    max_len = max(lengths) if lengths else 0
    n50, l50 = compute_n50_l50(lengths)

    duplicate_counts = Counter(record.header for record in records)
    duplicate_id_map = {
        sequence_id: count
        for sequence_id, count in duplicate_counts.items()
        if count > 1
    }

    per_sequence_stats = [analyze_record(record) for record in records]
    type_counts = Counter(item["sequence_type"] for item in per_sequence_stats)
    if set(type_counts) == {"DNA/RNA"}:
        detected_type = "DNA/RNA"
    elif set(type_counts) == {"Protein"}:
        detected_type = "Protein"
    else:
        detected_type = "Mixed/Unknown"

    total_n_count = sum(item["n_count"] or 0 for item in per_sequence_stats)
    total_ambiguous_count = sum(
        item["ambiguous_count"] or 0 for item in per_sequence_stats
    )
    total_invalid_char_count = sum(
        item["invalid_char_count"] for item in per_sequence_stats
    )
    invalid_record_count = sum(
        1 for item in per_sequence_stats if item["invalid_char_count"] > 0
    )
    duplicate_id_count = sum(count - 1 for count in duplicate_id_map.values())

    n_content_rate = None
    if detected_type == "DNA/RNA" and total_length:
        n_content_rate = total_n_count / total_length * 100

    warnings = []
    if duplicate_id_map:
        preview = ", ".join(
            f"{sequence_id} (x{count})"
            for sequence_id, count in sorted(duplicate_id_map.items())[:5]
        )
        warnings.append(f"Duplicate IDs detected: {preview}")
    if detected_type == "Mixed/Unknown":
        warnings.append(
            "Mixed or unknown sequence alphabets detected; nucleotide-only metrics may be reported as N/A."
        )
    if total_invalid_char_count:
        warnings.append(
            f"Invalid characters detected in {invalid_record_count} sequence(s), total invalid characters: {total_invalid_char_count}."
        )

    summary = {
        "sequence_type": detected_type,
        "total": total,
        "total_length": total_length,
        "avg_len": avg_len,
        "min_len": min_len,
        "max_len": max_len,
        "n50": n50,
        "l50": l50,
        "duplicate_ids": duplicate_id_count,
        "duplicate_id_map": duplicate_id_map,
        "ambiguous_bases": total_ambiguous_count,
        "invalid_chars": total_invalid_char_count,
        "total_n_count": total_n_count if detected_type == "DNA/RNA" else None,
        "n_content_rate": n_content_rate,
        "type_breakdown": "; ".join(
            f"{sequence_type}:{count}"
            for sequence_type, count in sorted(type_counts.items())
        ),
        "warning_count": len(warnings),
    }
    return summary, per_sequence_stats, warnings


def write_statistics_report(
    output_path: str, summary: dict, per_sequence_stats: list[dict]
):
    summary_rows = [
        ("Detected_Sequence_Type", summary["sequence_type"]),
        ("Total_Sequences", summary["total"]),
        ("Total_Length", summary["total_length"]),
        ("Average_Length", summary["avg_len"]),
        ("Min_Length", summary["min_len"]),
        ("Max_Length", summary["max_len"]),
        ("N50", summary["n50"]),
        ("L50", summary["l50"]),
        ("Duplicate_ID_Count", summary["duplicate_ids"]),
        ("Total_N_Count", summary["total_n_count"]),
        ("N_Content_Rate(%)", summary["n_content_rate"]),
        ("Total_Ambiguous_Count", summary["ambiguous_bases"]),
        ("Total_Invalid_Char_Count", summary["invalid_chars"]),
        ("Type_Breakdown", summary["type_breakdown"]),
        ("Warning_Count", summary["warning_count"]),
    ]

    lines = ["# Summary", "Metric\tValue"]
    for metric, value in summary_rows:
        lines.append(f"{metric}\t{format_metric_value(value)}")

    lines.extend([
        "",
        "# Per-Sequence Statistics",
        "Sequence_ID\tLength\tSequence_Type\tGC_Content(%)\tN_Count\tAmbiguous_Count\tInvalid_Char_Count\tInvalid_Chars\tDescription_Length",
    ])

    for item in per_sequence_stats:
        lines.append(
            "\t".join([
                item["sequence_id"],
                format_metric_value(item["length"]),
                item["sequence_type"],
                format_metric_value(item["gc_content"]),
                format_metric_value(item["n_count"]),
                format_metric_value(item["ambiguous_count"]),
                format_metric_value(item["invalid_char_count"]),
                item["invalid_chars"],
                format_metric_value(item["description_length"]),
            ])
        )

    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


class SequenceStatisticsWorker(FASTAWorker):
    """Sequence length statistics worker"""

    # 信号必须定义为类变量，不能在__init__或run中定义
    stats_finished = pyqtSignal(dict)

    def __init__(self, input_path: str, output_path: str):
        super().__init__(input_path, output_path)

    def run(self):
        try:
            if not self.validate_files():
                return
            self.emit_progress("Loading FASTA file...")
            processor = self.load_fasta_processor()
            if not processor:
                return

            summary, per_sequence_stats, warnings = build_statistics_report(
                processor.records
            )
            self.emit_progress("Saving statistics report...")
            write_statistics_report(self.output_path, summary, per_sequence_stats)

            for warning in warnings:
                self.progress.emit(f"Warning: {warning}")

            self.stats_finished.emit(summary)
            self.emit_finished(
                f"Statistics complete! Results saved to: {self.output_path}"
            )
        except Exception as e:
            import traceback

            self.emit_error(f"Unexpected error: {e}\n{traceback.format_exc()}")


class SequenceStatisticsTab(BaseTabWidget):
    """Sequence length statistics Tab"""

    def __init__(self):
        super().__init__("FASTA QC", "file")
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        # Inner class: LineEdit with file drag-and-drop support
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
                allowed = {
                    ".fasta",
                    ".fa",
                    ".fas",
                    ".fna",
                    ".ffn",
                    ".faa",
                    ".frn",
                    ".txt",
                }
                try:
                    ext = os.path.splitext(path)[1].lower()
                    return os.path.isfile(path) and ext in allowed
                except Exception:
                    return False

        # 输入文件选择
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

        # 输出文件选择
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output stats file:"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose where to save the QC stats...")
        self.output_edit.setMinimumWidth(320)
        self.output_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.output_btn = QPushButton("Save As")
        self.output_btn.setFixedWidth(90)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        output_layout.setSpacing(8)

        # 全局统计信息显示区
        stats_layout = QGridLayout()
        self.stat_labels = {}
        stats = [
            ("Detected Type", "sequence_type"),
            ("Total Sequences", "total"),
            ("Total Length", "total_length"),
            ("Average Length", "avg_len"),
            ("Min Length", "min_len"),
            ("Max Length", "max_len"),
            ("N50", "n50"),
            ("L50", "l50"),
            ("Duplicate IDs", "duplicate_ids"),
            ("Ambiguous Bases", "ambiguous_bases"),
            ("Invalid Chars", "invalid_chars"),
            ("N Content", "n_content"),
        ]
        for i, (label, key) in enumerate(stats):
            row, col = i // 2, (i % 2) * 2
            l = QLabel(f"{label}: ")
            v = QLabel("--")
            v.setStyleSheet("font-weight: bold; color: #2196F3;")
            stats_layout.addWidget(l, row, col)
            stats_layout.addWidget(v, row, col + 1)
            self.stat_labels[key] = v
        # Flexible value columns and nicer spacing
        stats_layout.setColumnStretch(1, 1)
        stats_layout.setColumnStretch(3, 1)
        stats_layout.setHorizontalSpacing(16)
        stats_layout.setVerticalSpacing(6)

        # 控制按钮
        control_layout = QHBoxLayout()
        self.run_btn = QPushButton("Start")
        self.clear_btn = QPushButton("Clear")
        control_layout.addStretch(1)
        control_layout.addWidget(self.run_btn)
        control_layout.addWidget(self.clear_btn)
        control_layout.setSpacing(10)

        # 添加到内容区域
        self.add_content_layout(input_layout)
        self.add_content_layout(output_layout)
        self.add_content_layout(stats_layout)
        self.add_content_layout(control_layout)
        self.content_area.addStretch()

    def connect_signals(self):
        self.input_btn.clicked.connect(self.select_input_file)
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_statistics)
        self.clear_btn.clicked.connect(self.clear_all)
        # Drag-and-drop signal from input line edit
        if hasattr(self.input_edit, "file_dropped"):
            self.input_edit.file_dropped.connect(self.handle_input_file_selected)

    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select FASTA file",
            "",
            "FASTA Files (*.fasta *.fa *.fas *.fna *.ffn *.faa *.frn *.txt);;All Files (*)",
        )
        if file_path:
            self.handle_input_file_selected(file_path)

    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save statistics", "", "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            self.output_edit.setText(file_path)

    def handle_input_file_selected(self, file_path: str):
        """Handle input selection from dialog or drag-and-drop"""
        self.input_edit.setText(file_path)
        base = os.path.splitext(os.path.basename(file_path))[0]
        suggested = os.path.join(
            os.path.dirname(file_path), base + "_length_statistics.txt"
        )
        if not self.output_edit.text().strip():
            self.output_edit.setText(suggested)
        self.show_status("Input file selected")

    def clear_all(self):
        self.input_edit.clear()
        self.output_edit.clear()
        self.log_area.clear()
        for label in self.stat_labels.values():
            label.setText("--")
        self.show_status("Cleared")

    def set_running_state(self, running: bool):
        """重写以禁用相关按钮"""
        super().set_running_state(running)
        self.run_btn.setEnabled(not running)
        self.input_btn.setEnabled(not running)
        self.output_btn.setEnabled(not running)

    def update_statistics(self, stats: dict):
        """更新统计信息显示"""
        self.stat_labels["sequence_type"].setText(stats.get("sequence_type", "N/A"))
        self.stat_labels["total"].setText(str(stats.get("total", 0)))
        self.stat_labels["total_length"].setText(str(stats.get("total_length", 0)))
        self.stat_labels["avg_len"].setText(f"{stats.get('avg_len', 0):.1f}")
        self.stat_labels["min_len"].setText(str(stats.get("min_len", 0)))
        self.stat_labels["max_len"].setText(str(stats.get("max_len", 0)))
        self.stat_labels["n50"].setText(str(stats.get("n50", 0)))
        self.stat_labels["l50"].setText(str(stats.get("l50", 0)))
        self.stat_labels["duplicate_ids"].setText(str(stats.get("duplicate_ids", 0)))
        self.stat_labels["ambiguous_bases"].setText(
            str(stats.get("ambiguous_bases", 0))
        )
        self.stat_labels["invalid_chars"].setText(str(stats.get("invalid_chars", 0)))

        n_count = stats.get("total_n_count")
        n_rate = stats.get("n_content_rate")
        if n_count is None or n_rate is None:
            self.stat_labels["n_content"].setText("N/A")
        else:
            self.stat_labels["n_content"].setText(f"{n_count} ({n_rate:.1f}%)")

    def show_help(self):
        """Show help information"""
        from PyQt6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QLabel,
            QPushButton,
            QScrollArea,
        )
        from PyQt6.QtCore import Qt

        help_text = """
<h3>FASTA QC</h3>
<p><b>Description:</b></p>
<p>Generate a lightweight FASTA QC report with global assembly-style metrics and per-sequence diagnostics.</p>

<p><b>Features:</b></p>
<ul>
<li><b>Global stats:</b> total sequences, total length, average, min/max length, N50, L50</li>
<li><b>QC flags:</b> detected sequence type, duplicate IDs, ambiguous bases, invalid characters, N content</li>
<li><b>Detailed report:</b> ID, length, type, GC content, ambiguity and invalid-character counts per sequence</li>
</ul>

<p><b>Usage:</b></p>
<ol>
<li>Select a FASTA file (.fasta/.fa/.fas/.fna/.ffn/.faa/.frn/.txt)</li>
<li>Choose where to save the report</li>
<li>Click "Start"</li>
<li>Review the summary panel and operation logs</li>
</ol>

<p><b>Example input:</b></p>
<pre>
&gt;seq1 alpha
ATGCNNNN
&gt;seq2 beta
ATGCTGCA
</pre>

<p><b>What to look for:</b></p>
<ul>
<li><b>Detected Type:</b> DNA/RNA, protein, or mixed/unknown</li>
<li><b>Duplicate IDs:</b> repeated record IDs that may affect downstream tools</li>
<li><b>Ambiguous Bases / N Content:</b> useful for assembly and primer-quality review</li>
<li><b>Invalid Chars:</b> unexpected symbols such as digits or punctuation inside sequences</li>
</ul>

<p><b>Output:</b></p>
<p>The report contains a summary block followed by a per-sequence TSV table for downstream analysis.</p>
<p>Each row includes sequence ID, length, inferred sequence type, GC content, ambiguity counts, invalid-character counts, and description length.</p>
        """

        # 创建自定义对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("Help - FASTA QC")
        dialog.setFixedSize(780, 500)

        layout = QVBoxLayout()

        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # 创建文本标签
        label = QLabel(help_text)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)  # 启用自动换行
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        label.setMargin(20)

        scroll_area.setWidget(label)
        layout.addWidget(scroll_area)

        # Add OK button
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)

        dialog.setLayout(layout)
        dialog.exec()

    def run_statistics(self):
        input_path = self.input_edit.text().strip()
        output_path = self.output_edit.text().strip()

        # 验证输入
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

        self.set_running_state(True)
        self.log_message("Starting sequence statistics processing...", "INFO")

        try:
            from modules.fasta_processor import FASTAProcessor

            if not input_path or not os.path.isfile(input_path):
                self.log_message("Input file is invalid or does not exist", "ERROR")
                return

            if not output_path:
                self.log_message("Output file path cannot be empty", "ERROR")
                return

            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir)
                except Exception as e:
                    self.log_message(f"Unable to create output directory: {e}", "ERROR")
                    return

            self.show_status("Loading FASTA file...")
            self.log_message("Loading FASTA file...", "INFO")
            processor = FASTAProcessor()
            if not processor.read_file(input_path):
                self.log_message("Unable to read FASTA file", "ERROR")
                return

            summary, per_sequence_stats, warnings = build_statistics_report(
                processor.records
            )
            self.update_statistics(summary)

            self.show_status("Computing statistics...")
            self.log_message(
                f"Detected sequence type: {summary['sequence_type']}; total sequences: {summary['total']}; N50: {summary['n50']}",
                "INFO",
            )

            for warning in warnings:
                self.log_message(warning, "WARNING")

            self.show_status("Saving results...")
            self.log_message("Saving detailed QC report...", "INFO")
            write_statistics_report(output_path, summary, per_sequence_stats)

            self.log_message(
                f"Statistics complete! Results saved to: {output_path}", "INFO"
            )
            self.show_status("Complete")

        except Exception as e:
            import traceback

            error_msg = f"Error during processing: {e}\n{traceback.format_exc()}"
            self.log_message(error_msg, "ERROR")
            self.show_status("Error")
        finally:
            # 恢复按钮状态
            self.set_running_state(False)
