import os
from collections import Counter

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from utils.common_components import BaseTabWidget, FASTAWorker, FileDropLineEdit

NUCLEOTIDE_BASES = set("ACGTUNRYMKSWBDHV")
AMBIGUOUS_BASES = set("RYMKSWBDHV")
PROTEIN_BASES = set("ABCDEFGHIKLMNPQRSTVWXYZ*-")
VALID_SEQUENCE_CHARS = NUCLEOTIDE_BASES | PROTEIN_BASES


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
    invalid_chars = sorted({char for char in sequence if char not in VALID_SEQUENCE_CHARS})
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

    duplicate_counts = Counter(record.header for record in records)
    duplicate_id_map = {
        sequence_id: count for sequence_id, count in duplicate_counts.items() if count > 1
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
    total_ambiguous_count = sum(item["ambiguous_count"] or 0 for item in per_sequence_stats)
    total_invalid_char_count = sum(item["invalid_char_count"] for item in per_sequence_stats)
    invalid_record_count = sum(1 for item in per_sequence_stats if item["invalid_char_count"] > 0)
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
        "duplicate_ids": duplicate_id_count,
        "duplicate_id_map": duplicate_id_map,
        "ambiguous_bases": total_ambiguous_count,
        "invalid_chars": total_invalid_char_count,
        "total_n_count": total_n_count if detected_type == "DNA/RNA" else None,
        "n_content_rate": n_content_rate,
        "type_breakdown": "; ".join(
            f"{sequence_type}:{count}" for sequence_type, count in sorted(type_counts.items())
        ),
        "warning_count": len(warnings),
    }
    return summary, per_sequence_stats, warnings


def write_statistics_report(output_path: str, summary: dict, per_sequence_stats: list[dict]):
    summary_rows = [
        ("Detected_Sequence_Type", summary["sequence_type"]),
        ("Total_Sequences", summary["total"]),
        ("Total_Length", summary["total_length"]),
        ("Average_Length", summary["avg_len"]),
        ("Min_Length", summary["min_len"]),
        ("Max_Length", summary["max_len"]),
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

            summary, per_sequence_stats, warnings = build_statistics_report(processor.records)
            self.emit_progress("Saving statistics report...")
            write_statistics_report(self.output_path, summary, per_sequence_stats)

            for warning in warnings:
                self.progress.emit(f"Warning: {warning}")

            self.stats_finished.emit(summary)
            self.emit_finished(f"Statistics complete! Results saved to: {self.output_path}")
        except Exception as e:
            import traceback

            self.emit_error(f"Unexpected error: {e}\n{traceback.format_exc()}")


class SequenceStatisticsTab(BaseTabWidget):
    """Sequence length statistics Tab"""

    def __init__(self):
        super().__init__("FASTA Statistics", "file")
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        # 固定标签宽度使两行对齐
        _label_width = 130

        # 输入 / 输出文件
        io_group = QGroupBox("Input / Output")
        io_layout = QVBoxLayout(io_group)
        io_layout.setContentsMargins(6, 16, 6, 4)
        io_layout.setSpacing(6)

        input_layout = QHBoxLayout()
        input_label = QLabel("Input FASTA file:")
        input_label.setFixedWidth(_label_width)
        input_layout.addWidget(input_label)
        self.input_edit = FileDropLineEdit()
        self.input_edit.setPlaceholderText("Select or drop a FASTA file...")
        self.input_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.input_btn = QPushButton("Browse")
        self.input_btn.setFixedWidth(90)
        self.example_btn = QPushButton(self.tr("Example"))
        self.example_btn.setFixedWidth(90)
        self.example_btn.clicked.connect(self._load_example)
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(self.input_btn)
        input_layout.addWidget(self.example_btn)
        input_layout.setSpacing(8)
        io_layout.addLayout(input_layout)

        output_layout = QHBoxLayout()
        output_label = QLabel("Output stats file:")
        output_label.setFixedWidth(_label_width)
        output_layout.addWidget(output_label)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose where to save the QC stats...")
        self.output_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.output_btn = QPushButton("Browse")
        self.output_btn.setFixedWidth(90)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        output_layout.setSpacing(8)
        io_layout.addLayout(output_layout)

        # 全局统计信息显示区
        self.stats_group = QGroupBox(self.tr("Summary Statistics"))
        self.stats_layout = QGridLayout(self.stats_group)
        self.stat_labels = {}
        stats = [
            ("Detected Type", "sequence_type"),
            ("Total Sequences", "total"),
            ("Total Length", "total_length"),
            ("Average Length", "avg_len"),
            ("Min Length", "min_len"),
            ("Max Length", "max_len"),
            ("Duplicate IDs", "duplicate_ids"),
            ("Ambiguous Bases", "ambiguous_bases"),
            ("Invalid Chars", "invalid_chars"),
            ("N Content", "n_content"),
        ]
        for i, (label, key) in enumerate(stats):
            row, col = i // 2, (i % 2) * 2
            l = QLabel(f"{label}: ")
            v = QLabel("--")
            v.setProperty("statValue", True)
            self.stats_layout.addWidget(l, row, col)
            self.stats_layout.addWidget(v, row, col + 1)
            self.stat_labels[key] = v
        # Tooltips for key metrics
        _tooltips = {
            "ambiguous_bases": "Count of IUPAC ambiguity codes (R/Y/M/K/S/W/B/D/H/V) — may indicate low-quality or heterozygous calls",
            "invalid_chars": "Characters outside standard nucleotide/protein alphabets",
            "n_content": "Total N bases and their percentage — high N content often signals assembly gaps",
            "duplicate_ids": "Number of extra records sharing the same ID beyond the first occurrence",
        }
        for key, tip in _tooltips.items():
            if key in self.stat_labels:
                self.stat_labels[key].setToolTip(tip)
        # Flexible value columns and nicer spacing
        self.stats_layout.setColumnStretch(1, 1)
        self.stats_layout.setColumnStretch(3, 1)
        self.stats_layout.setHorizontalSpacing(16)
        self.stats_layout.setVerticalSpacing(6)

        # ── Control buttons in status bar ──
        self.run_btn = QPushButton("Run")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.run_btn)
        self.clear_btn = QPushButton("Clear")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.clear_btn)
        self.add_open_output_dir_button()

        # 添加到内容区域
        self.add_content_widget(io_group)
        self.add_content_widget(self.stats_group)
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
        ).replace("/", "\\")
        if not self.output_edit.text().strip():
            self.output_edit.setText(suggested)
        self.show_status("Input file selected")

    def _load_example(self):
        """Load the bundled cytb teaching example into the input field."""
        from PyQt6.QtWidgets import QMessageBox

        from utils.example_data import stage_example

        path = stage_example("phylo", "cytb_cds_raw.fasta")
        if not path:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. The installation may be incomplete."),
            )
            return
        self.handle_input_file_selected(path)

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
        self.stat_labels["duplicate_ids"].setText(str(stats.get("duplicate_ids", 0)))
        self.stat_labels["ambiguous_bases"].setText(str(stats.get("ambiguous_bases", 0)))
        self.stat_labels["invalid_chars"].setText(str(stats.get("invalid_chars", 0)))

        n_count = stats.get("total_n_count")
        n_rate = stats.get("n_content_rate")
        if n_count is None or n_rate is None:
            self.stat_labels["n_content"].setText("N/A")
        else:
            self.stat_labels["n_content"].setText(f"{n_count} ({n_rate:.1f}%)")

    def show_help(self):
        """Show help information"""
        help_text = """
<h2>FASTA Statistics &mdash; Sequence Statistics for FASTA Files</h2>

<p><b>What does this tool do?</b><br>
It scans your FASTA file and produces a quality report so you can spot problems
before they affect downstream analysis. Think of it as a health check for your
sequence data.</p>

<h3>Quick Start</h3>
<ol>
<li>Select a FASTA file (drag-and-drop is supported)</li>
<li>Choose where to save the statistics report</li>
<li>Click <b>Run</b></li>
<li>Review the summary panel and the saved TSV report</li>
</ol>

<h3>File Formats Supported</h3>
<p>.fasta &middot; .fa &middot; .fas &middot; .fna &middot; .ffn &middot; .faa &middot; .frn &middot; .txt</p>

<h3>Metrics Explained</h3>

<p><b>Total Sequences</b><br>
How many FASTA records (entries starting with <code>&gt;</code>) are in the file.</p>

<p><b>Total Length / Average Length / Min Length / Max Length</b><br>
The sum, mean, shortest, and longest sequence lengths (in bases or residues).
A large gap between min and max may indicate mixed data types or truncated
entries.</p>

<p><b>Detected Type</b><br>
Whether the sequences appear to be DNA/RNA, protein, or a mixture. The tool
infers this from the alphabet of characters found in each sequence.</p>

<p><b>GC Content</b><br>
Percentage of G and C bases (DNA/RNA only). High or low GC content can affect
PCR primer design, sequencing coverage bias, and secondary structure.</p>

<p><b>Ambiguous Bases</b><br>
Count of IUPAC ambiguity codes: R, Y, M, K, S, W, B, D, H, V. These represent
positions where the sequencer could not confidently call a single base
(e.g., R = A or G). Many ambiguous calls may indicate low-quality regions.</p>

<p><b>N Content</b><br>
Total number of N bases and their overall percentage. Ns represent completely
unknown bases and are common in genome assemblies where gaps could not be
resolved. High N content often signals an incomplete or draft assembly.</p>

<p><b>Invalid Characters</b><br>
Characters that do not belong to standard nucleotide or protein alphabets
(such as digits, punctuation, or whitespace inside sequences). These can
break alignment and analysis tools.</p>

<p><b>Duplicate IDs</b><br>
How many sequence IDs appear more than once. Duplicate IDs confuse many
bioinformatics tools and should usually be resolved before further analysis.</p>

<h3>Example Input</h3>
<pre>
&gt;contig_1 length=5000
ATGCNNNNACTG...
&gt;contig_2 length=3200
GGTACCATGGC...
</pre>

<h3>Output</h3>
<p>The tool writes a tab-separated (.txt) report with two sections:</p>
<ul>
<li><b>Summary block</b> &mdash; the global metrics shown in the on-screen panel</li>
<li><b>Per-sequence table</b> &mdash; one row per FASTA record with ID, length, type,
GC%, N count, ambiguous count, invalid chars, and description length</li>
</ul>

<h3>Tips</h3>
<ul>
<li>Run this on every FASTA file before feeding it to alignment, assembly, or
annotation pipelines.</li>
<li>If <i>Detected Type</i> says "Mixed/Unknown", review the per-sequence table to
find which records have unexpected alphabets.</li>
<li>Use the per-sequence TSV in Excel or Python to filter outliers by length
or GC content.</li>
</ul>
        """

        self.show_help_dialog("Help - FASTA Statistics", help_text, 600, 480)

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

            summary, per_sequence_stats, warnings = build_statistics_report(processor.records)
            self.update_statistics(summary)

            self.show_status("Computing statistics...")
            self.log_message(
                f"Detected sequence type: {summary['sequence_type']}; total sequences: {summary['total']}",
                "INFO",
            )

            for warning in warnings:
                self.log_message(warning, "WARNING")

            self.show_status("Saving results...")
            self.log_message("Saving detailed QC report...", "INFO")
            write_statistics_report(output_path, summary, per_sequence_stats)

            self.log_message(f"Statistics complete! Results saved to: {output_path}", "INFO")
            self.show_status("Complete")

        except Exception as e:
            import traceback

            error_msg = f"Error during processing: {e}\n{traceback.format_exc()}"
            self.log_message(error_msg, "ERROR")
            self.show_status("Error")
        finally:
            # 恢复按钮状态
            self.set_running_state(False)
