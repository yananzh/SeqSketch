import os
from collections import defaultdict
from datetime import datetime

from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from utils.common_components import BaseTabWidget, FileDropLineEdit, unify_status_button_sizes

# Remove worker, use main thread


def rename_report_path_for_output(output_path: str) -> str:
    base, _ = os.path.splitext(output_path)
    return f"{base}_rename_report.tsv"


def build_mapping_template_rows(records) -> list[dict[str, str]]:
    return [{"old_id": record.header, "new_id": ""} for record in records]


def write_mapping_template_file(output_path: str, rows: list[dict[str, str]]) -> None:
    ext = os.path.splitext(output_path)[1].lower()
    if ext in [".xlsx", ".xls"]:
        try:
            import pandas as pd
        except Exception as exc:
            raise ImportError(
                "Excel export requires pandas. Install with: pip install pandas openpyxl, or save as CSV/TSV."
            ) from exc

        df = pd.DataFrame(rows, columns=["old_id", "new_id"])
        df.to_excel(output_path, index=False)
        return

    if ext in [".csv", ".tsv", ".txt"]:
        import csv

        delimiter = "," if ext == ".csv" else "\t"
        with open(output_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["old_id", "new_id"], delimiter=delimiter)
            writer.writeheader()
            writer.writerows(rows)
        return

    raise ValueError(
        "Unsupported template format. Use Excel (.xlsx/.xls), CSV (.csv) or TSV (.tsv/.txt)."
    )


def normalize_template_output_path(output_path: str, selected_filter: str) -> str:
    if os.path.splitext(output_path)[1]:
        return output_path
    if "Excel" in selected_filter:
        return f"{output_path}.xlsx"
    if "CSV" in selected_filter:
        return f"{output_path}.csv"
    return f"{output_path}.tsv"


def parse_mapping_entries(rows) -> tuple[dict[str, str], dict]:
    mapping = {}
    skipped_rows = 0
    duplicate_old_ids = defaultdict(list)
    new_id_sources = defaultdict(list)

    for row in rows:
        if len(row) < 2:
            skipped_rows += 1
            continue

        old_id = str(row[0]).strip()
        new_id = str(row[1]).strip()
        if not old_id or not new_id:
            skipped_rows += 1
            continue

        if old_id in mapping:
            duplicate_old_ids[old_id].append(new_id)
            continue

        mapping[old_id] = new_id
        new_id_sources[new_id].append(old_id)

    duplicate_new_ids = {
        new_id: old_ids for new_id, old_ids in new_id_sources.items() if len(old_ids) > 1
    }
    summary = {
        "skipped_rows": skipped_rows,
        "duplicate_old_ids": dict(duplicate_old_ids),
        "duplicate_new_ids": duplicate_new_ids,
    }
    return mapping, summary


def load_mapping_file(mapping_path: str, has_header: bool) -> tuple[dict[str, str], dict]:
    ext = os.path.splitext(mapping_path)[1].lower()
    if ext in [".xls", ".xlsx"]:
        try:
            import pandas as pd
        except Exception as exc:
            raise ImportError(
                "Excel mapping requires pandas. Install with: pip install pandas, or save as CSV/TSV."
            ) from exc

        df = pd.read_excel(mapping_path, header=0 if has_header else None)
        if df.shape[1] < 2:
            raise ValueError("Mapping file must have at least two columns (old ID, new ID)")
        rows = df.iloc[:, :2].fillna("").astype(str).values.tolist()
        return parse_mapping_entries(rows)

    if ext in [".csv", ".tsv", ".txt"]:
        import csv

        delimiter = "," if ext == ".csv" else "\t"
        with open(mapping_path, "r", encoding="utf-8") as handle:
            reader = csv.reader(handle, delimiter=delimiter)
            rows = list(reader)
        if has_header and rows:
            rows = rows[1:]
        return parse_mapping_entries(rows)

    raise ValueError(
        "Unsupported mapping format. Use Excel (.xlsx/.xls), CSV (.csv) or TSV (.tsv/.txt)."
    )


def plan_renames(records, mapping: dict[str, str]) -> dict:
    rename_rows = []
    matched_mapping_ids = set()
    renamed_count = 0
    unchanged_count = 0
    final_id_sources = defaultdict(list)

    for record in records:
        old_id = record.header
        if old_id in mapping:
            new_id = mapping[old_id]
            matched_mapping_ids.add(old_id)
            if new_id != old_id:
                status = "renamed"
                reason = "mapping applied"
                renamed_count += 1
            else:
                status = "unchanged"
                reason = "mapping kept existing ID"
                unchanged_count += 1
        else:
            new_id = old_id
            status = "unchanged"
            reason = "no mapping match"
            unchanged_count += 1

        rename_rows.append({
            "record": record,
            "old_id": old_id,
            "new_id": new_id,
            "status": status,
            "reason": reason,
        })
        final_id_sources[new_id].append(old_id)

    collisions = {
        final_id: source_ids
        for final_id, source_ids in final_id_sources.items()
        if len(source_ids) > 1
    }
    unused_mapping_ids = [old_id for old_id in mapping if old_id not in matched_mapping_ids]

    for row in rename_rows:
        if row["new_id"] in collisions:
            row["reason"] = f"output ID collision: {row['new_id']}"

    return {
        "rename_rows": rename_rows,
        "renamed_count": renamed_count,
        "unchanged_count": unchanged_count,
        "unused_mapping_ids": unused_mapping_ids,
        "collisions": collisions,
    }


def write_rename_report(output_path: str, report_rows: list[dict], metadata: dict):
    lines = [
        "Metric\tValue",
        f"Generated_At\t{datetime.now().isoformat(timespec='seconds')}",
        f"Total_Sequences\t{metadata['total_sequences']}",
        f"Renamed_Count\t{metadata['renamed_count']}",
        f"Unchanged_Count\t{metadata['unchanged_count']}",
        f"Unused_Mapping_IDs\t{'; '.join(metadata['unused_mapping_ids']) if metadata['unused_mapping_ids'] else '-'}",
        f"Collision_Count\t{len(metadata['collisions'])}",
        "",
        "Old_ID\tNew_ID\tStatus\tReason",
    ]
    for row in report_rows:
        lines.append(f"{row['old_id']}\t{row['new_id']}\t{row['status']}\t{row['reason']}")
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


class BatchRenameIDsTab(BaseTabWidget):
    """批量重命名序列ID功能Tab"""

    def __init__(self):
        super().__init__("Rename IDs", "file")
        self.init_ui()
        self.connect_signals()
        unify_status_button_sizes(self)

    def init_ui(self):
        _label_width = 130

        # ── Input FASTA ──
        input_group = QGroupBox("Input FASTA")
        input_layout = QHBoxLayout(input_group)
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
        input_layout.addWidget(self.example_btn)
        input_layout.addWidget(self.input_btn)

        # ── ID Mapping ──
        mapping_group = QGroupBox("ID Mapping")
        mapping_main = QVBoxLayout(mapping_group)

        # Step guide
        step_hint = QLabel(
            "Step 1: Select FASTA  →  Step 2: Export Current IDs  →  "
            "Step 3: Edit new IDs externally  →  Step 4: Load mapping  →  Step 5: Start"
        )
        step_hint.setProperty("hintLabel", True)
        mapping_main.addWidget(step_hint)

        # Mapping file row
        map_row = QHBoxLayout()
        map_label = QLabel("ID mapping file:")
        map_label.setFixedWidth(_label_width)
        map_row.addWidget(map_label)
        self.mapping_edit = FileDropLineEdit(FileDropLineEdit.MAPPING_EXTENSIONS)
        self.mapping_edit.setPlaceholderText(
            "Select or drop a mapping file (Excel .xlsx/.xls, CSV, TSV, or TXT)..."
        )
        self.mapping_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.mapping_btn = QPushButton("Browse")
        self.export_ids_btn = QPushButton("Export Current IDs")
        self.export_ids_btn.setEnabled(False)
        self.export_ids_btn.setToolTip(
            "Export the IDs from the selected FASTA as a template. Select a FASTA file above first."
        )
        map_row.addWidget(self.mapping_edit)
        map_row.addWidget(self.export_ids_btn)
        map_row.addWidget(self.mapping_btn)
        mapping_main.addLayout(map_row)

        # Mapping options
        map_opts = QHBoxLayout()
        self.header_checkbox = QCheckBox("Mapping file contains header row")
        self.header_checkbox.setChecked(True)
        self.header_checkbox.setToolTip(
            "Uncheck if your mapping file has no header and the first row is data"
        )
        map_opts.addWidget(self.header_checkbox)
        self.block_on_collisions_checkbox = QCheckBox("Block on collisions")
        self.block_on_collisions_checkbox.setChecked(True)
        self.block_on_collisions_checkbox.setToolTip(
            "Stop if two old IDs map to the same new ID. "
            "Recommended to avoid duplicate sequence IDs in the output."
        )
        map_opts.addWidget(self.block_on_collisions_checkbox)
        self.export_report_checkbox = QCheckBox("Export rename report")
        self.export_report_checkbox.setToolTip(
            "Save a TSV file showing every old → new ID change with status"
        )
        map_opts.addWidget(self.export_report_checkbox)
        map_opts.addStretch()
        mapping_main.addLayout(map_opts)

        # ── Preview panel ──
        self.preview_panel = QPlainTextEdit()
        self.preview_panel.setReadOnly(True)
        self.preview_panel.setPlaceholderText(
            "Click Preview to see the first few rename results here..."
        )
        self.preview_panel.setMaximumHeight(120)
        self.preview_panel.setProperty("previewPanel", True)

        # ── Output ──
        out_group = QGroupBox("Output")
        out_layout = QHBoxLayout(out_group)
        out_label = QLabel("Output FASTA file:")
        out_label.setFixedWidth(_label_width)
        out_layout.addWidget(out_label)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose where to save the renamed file...")
        self.output_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.output_btn = QPushButton("Browse")
        self.output_btn.setFixedWidth(90)
        out_layout.addWidget(self.output_edit)
        out_layout.addWidget(self.output_btn)

        # ── Control buttons in status bar ──
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setToolTip("Preview the first 5 rename results without saving")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.preview_btn)
        self.run_btn = QPushButton("Run")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.run_btn)
        self.clear_btn = QPushButton("Clear")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.clear_btn)
        self.add_open_output_dir_button()

        # ── Assemble ──
        self.add_content_widget(input_group)
        self.add_content_widget(mapping_group)
        self.add_content_widget(self.preview_panel)
        self.add_content_widget(out_group)
        self.content_area.addStretch()

    def connect_signals(self):
        self.input_btn.clicked.connect(self.select_input_file)
        self.mapping_btn.clicked.connect(self.select_mapping_file)
        self.export_ids_btn.clicked.connect(self.select_template_output_file)
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_rename)
        self.preview_btn.clicked.connect(self.preview_rename)
        self.clear_btn.clicked.connect(self.clear_all)
        if hasattr(self.input_edit, "file_dropped"):
            self.input_edit.file_dropped.connect(self.handle_input_file_selected)
        if hasattr(self.mapping_edit, "file_dropped"):
            self.mapping_edit.file_dropped.connect(self.handle_mapping_file_selected)

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
        suggested = os.path.join(os.path.dirname(file_path), base + "_renamed.fasta").replace(
            "/", "\\"
        )
        if not self.output_edit.text().strip():
            self.output_edit.setText(suggested)
        self.export_ids_btn.setEnabled(bool(file_path.strip()))
        self.show_status("Input file selected")

    def _load_example(self):
        """Load the bundled cytb teaching example (FASTA + ID mapping file)."""
        from PyQt6.QtWidgets import QMessageBox

        from utils.example_data import stage_example

        fasta_path = stage_example("phylo", "cytb_cds_raw.fasta")
        mapping_path = stage_example("dna", "cytb_id_mapping.xlsx")
        if not fasta_path or not mapping_path:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. The installation may be incomplete."),
            )
            return
        self.handle_input_file_selected(fasta_path)
        self.handle_mapping_file_selected(mapping_path)
        self.show_status(self.tr("Example loaded"))

    def select_mapping_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select ID mapping file",
            "",
            "Excel Files (*.xlsx *.xls);;CSV Files (*.csv);;TSV Files (*.tsv *.txt);;All Files (*)",
        )
        if file_path:
            self.handle_mapping_file_selected(file_path)

    def handle_mapping_file_selected(self, file_path: str):
        self.mapping_edit.setText(file_path)
        ext = os.path.splitext(file_path)[1].lower()
        if ext in [".xls", ".xlsx"]:
            self.log_message("Excel mapping file selected.")

    def select_template_output_file(self):
        input_path = self.input_edit.text().strip()
        base_name = "current_ids_template"
        if input_path:
            base_name = os.path.splitext(os.path.basename(input_path))[0] + "_id_mapping"

        output_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export current FASTA IDs",
            base_name,
            "Excel Files (*.xlsx);;CSV Files (*.csv);;TSV Files (*.tsv *.txt);;All Files (*)",
        )
        if output_path:
            self.export_current_ids_template(
                normalize_template_output_path(output_path, selected_filter)
            )

    def export_current_ids_template(self, output_path: str) -> bool:
        from utils.common_components import validate_input_path, validate_output_path

        input_path = self.input_edit.text().strip()
        valid, error = validate_input_path(
            input_path,
            [".fasta", ".fa", ".fas", ".fna", ".ffn", ".faa", ".frn", ".txt"],
        )
        if not valid:
            self.log_message(error, "ERROR")
            return False

        valid, error = validate_output_path(output_path)
        if not valid:
            self.log_message(error, "ERROR")
            return False

        self.set_running_state(True)
        self.show_status("Exporting current IDs...")
        try:
            from modules.fasta_processor import FASTAProcessor

            processor = FASTAProcessor()
            if not processor.read_file(input_path):
                self.log_message("Unable to read FASTA file", "ERROR")
                self.show_status("Error")
                return False

            if not processor.records:
                self.log_message("No sequences found in FASTA file", "ERROR")
                self.show_status("Error")
                return False

            write_mapping_template_file(output_path, build_mapping_template_rows(processor.records))
            self.log_message(
                f"Exported {len(processor.records)} current FASTA IDs to: {output_path}",
                "INFO",
            )
            self.show_status("Template exported")
            return True
        except Exception as exc:
            self.log_message(f"Failed to export current IDs: {exc}", "ERROR")
            self.show_status("Error")
            return False
        finally:
            self.set_running_state(False)

    def preview_rename(self):
        """Preview the first 5 rename results without saving."""
        input_path = self.input_edit.text().strip()
        mapping_path = self.mapping_edit.text().strip()
        has_header = self.header_checkbox.isChecked()

        from utils.common_components import validate_input_path

        valid, error = validate_input_path(
            input_path,
            [".fasta", ".fa", ".fas", ".fna", ".ffn", ".faa", ".frn", ".txt"],
        )
        if not valid:
            self.log_message(error, "ERROR")
            return
        if not mapping_path:
            self.log_message("Please select a mapping file", "ERROR")
            return

        try:
            mapping, _ = load_mapping_file(mapping_path, has_header)
        except ImportError as exc:
            self.log_message(str(exc), "ERROR")
            return
        except ValueError as exc:
            self.log_message(str(exc), "ERROR")
            return

        if not mapping:
            self.log_message("No valid mappings found in the file", "ERROR")
            return

        try:
            from modules.fasta_processor import FASTAProcessor

            processor = FASTAProcessor()
            if not processor.read_file(input_path):
                self.log_message("Unable to read FASTA file", "ERROR")
                return
            records = processor.records
            if not records:
                self.log_message("No sequences found in FASTA file", "ERROR")
                return

            rename_plan = plan_renames(records, mapping)
            lines = [
                f"Total: {len(records)} sequences  ·  "
                f"Renamed: {rename_plan['renamed_count']}  ·  "
                f"Unchanged: {rename_plan['unchanged_count']}"
            ]
            lines.append("")
            showing = [r for r in rename_plan["rename_rows"] if r["status"] == "renamed"][:5]
            if showing:
                lines.append(f"─ Renamed (first {len(showing)}) ─")
                for row in showing:
                    lines.append(f"  {row['old_id']}  →  {row['new_id']}")
            else:
                lines.append("(No IDs match the mapping file)")
            self.preview_panel.setPlainText("\n".join(lines))
            self.log_message("Preview updated — see panel above", "INFO")
        except Exception as e:
            self.log_message(f"Preview error: {e}", "ERROR")

    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save renamed file",
            "",
            "FASTA Files (*.fasta *.fa *.fas *.fna *.ffn *.faa *.frn *.txt);;All Files (*)",
        )
        if file_path:
            self.output_edit.setText(file_path)

    def run_rename(self):
        input_path = self.input_edit.text().strip()
        mapping_path = self.mapping_edit.text().strip()
        output_path = self.output_edit.text().strip()
        has_header = self.header_checkbox.isChecked()
        export_report = self.export_report_checkbox.isChecked()
        block_on_collisions = self.block_on_collisions_checkbox.isChecked()

        # Validate input
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
        if not mapping_path:
            self.log_message("Please select a mapping file", "ERROR")
            return

        self.set_running_state(True)
        self.log_message("Starting batch ID renaming...", "INFO")
        try:
            try:
                mapping, mapping_summary = load_mapping_file(mapping_path, has_header)
            except ImportError as exc:
                self.log_message(str(exc), "ERROR")
                return
            except ValueError as exc:
                self.log_message(str(exc), "ERROR")
                return

            if not mapping:
                self.log_message("No valid mappings found in the file", "ERROR")
                return

            if mapping_summary["duplicate_old_ids"]:
                preview = ", ".join(sorted(mapping_summary["duplicate_old_ids"].keys())[:5])
                self.log_message(
                    f"Duplicate source IDs found in mapping file: {preview}",
                    "ERROR",
                )
                return

            self.log_message(f"Loaded {len(mapping)} ID mappings", "INFO")
            if mapping_summary["skipped_rows"]:
                self.log_message(
                    f"Skipped {mapping_summary['skipped_rows']} invalid mapping row(s)",
                    "WARNING",
                )
            if mapping_summary["duplicate_new_ids"]:
                preview = ", ".join(
                    f"{new_id} <- {', '.join(source_ids)}"
                    for new_id, source_ids in list(mapping_summary["duplicate_new_ids"].items())[:5]
                )
                self.log_message(
                    f"Multiple source IDs map to the same target ID: {preview}",
                    "WARNING",
                )

            # Load FASTA
            from modules.fasta_processor import FASTAProcessor

            self.show_status("Loading FASTA file...")
            processor = FASTAProcessor()
            if not processor.read_file(input_path):
                self.log_message("Unable to read FASTA file", "ERROR")
                self.set_running_state(False)
                return
            records = processor.records
            if not records:
                self.log_message("No sequences found in FASTA file", "ERROR")
                return
            self.log_message(f"Loaded {len(records)} sequences", "INFO")

            # Rename IDs
            self.show_status("Renaming sequence IDs...")
            total = len(records)
            rename_plan = plan_renames(records, mapping)

            if rename_plan["unused_mapping_ids"]:
                preview = ", ".join(rename_plan["unused_mapping_ids"][:5])
                self.log_message(
                    f"Unused mapping IDs: {preview}",
                    "WARNING",
                )

            if rename_plan["collisions"]:
                preview = ", ".join(
                    f"{final_id} <- {', '.join(source_ids)}"
                    for final_id, source_ids in list(rename_plan["collisions"].items())[:5]
                )
                level = "ERROR" if block_on_collisions else "WARNING"
                self.log_message(
                    f"Output ID collisions detected: {preview}",
                    level,
                )
                if block_on_collisions:
                    if export_report:
                        report_rows = rename_plan["rename_rows"] + [
                            {
                                "old_id": old_id,
                                "new_id": mapping[old_id],
                                "status": "unused_mapping",
                                "reason": "mapping ID not found in FASTA",
                            }
                            for old_id in rename_plan["unused_mapping_ids"]
                        ]
                        report_path = rename_report_path_for_output(output_path)
                        write_rename_report(
                            report_path,
                            report_rows,
                            {
                                "total_sequences": total,
                                "renamed_count": rename_plan["renamed_count"],
                                "unchanged_count": rename_plan["unchanged_count"],
                                "unused_mapping_ids": rename_plan["unused_mapping_ids"],
                                "collisions": rename_plan["collisions"],
                            },
                        )
                        self.log_message(f"Rename report saved to: {report_path}", "INFO")
                    return

            if rename_plan["renamed_count"] == 0:
                self.log_message(
                    "No FASTA IDs matched the mapping file; nothing was renamed",
                    "ERROR",
                )
                if export_report:
                    report_rows = rename_plan["rename_rows"] + [
                        {
                            "old_id": old_id,
                            "new_id": mapping[old_id],
                            "status": "unused_mapping",
                            "reason": "mapping ID not found in FASTA",
                        }
                        for old_id in rename_plan["unused_mapping_ids"]
                    ]
                    report_path = rename_report_path_for_output(output_path)
                    write_rename_report(
                        report_path,
                        report_rows,
                        {
                            "total_sequences": total,
                            "renamed_count": 0,
                            "unchanged_count": rename_plan["unchanged_count"],
                            "unused_mapping_ids": rename_plan["unused_mapping_ids"],
                            "collisions": rename_plan["collisions"],
                        },
                    )
                    self.log_message(f"Rename report saved to: {report_path}", "INFO")
                return

            for row in rename_plan["rename_rows"]:
                if row["status"] == "renamed":
                    row["record"].header = row["new_id"]

            # Save
            self.show_status("Saving results...")
            if not processor.save_file(output_path):
                self.log_message("Failed to save file", "ERROR")
                return
            if export_report:
                report_rows = rename_plan["rename_rows"] + [
                    {
                        "old_id": old_id,
                        "new_id": mapping[old_id],
                        "status": "unused_mapping",
                        "reason": "mapping ID not found in FASTA",
                    }
                    for old_id in rename_plan["unused_mapping_ids"]
                ]
                report_path = rename_report_path_for_output(output_path)
                write_rename_report(
                    report_path,
                    report_rows,
                    {
                        "total_sequences": total,
                        "renamed_count": rename_plan["renamed_count"],
                        "unchanged_count": rename_plan["unchanged_count"],
                        "unused_mapping_ids": rename_plan["unused_mapping_ids"],
                        "collisions": rename_plan["collisions"],
                    },
                )
                self.log_message(f"Rename report saved to: {report_path}", "INFO")
            self.log_message(
                f"Renaming complete! Processed {total} sequences, renamed {rename_plan['renamed_count']}, unchanged {rename_plan['unchanged_count']}. Saved to: {output_path}",
                "INFO",
            )
            self.show_status("Complete")
        except Exception as e:
            import traceback

            self.log_message(f"Error during renaming: {e}\n{traceback.format_exc()}", "ERROR")
            self.show_status("Error")
        finally:
            self.set_running_state(False)

    def clear_all(self):
        self.input_edit.clear()
        self.mapping_edit.clear()
        self.output_edit.clear()
        self.header_checkbox.setChecked(True)
        self.export_report_checkbox.setChecked(False)
        self.block_on_collisions_checkbox.setChecked(True)
        self.export_ids_btn.setEnabled(False)
        self.preview_panel.clear()
        if hasattr(self, "log_area"):
            self.log_area.clear()
        self.show_status("Cleared")

    def set_running_state(self, running: bool):
        super().set_running_state(running)
        self.run_btn.setEnabled(not running)
        self.preview_btn.setEnabled(not running)
        self.input_btn.setEnabled(not running)
        self.mapping_btn.setEnabled(not running)
        self.export_ids_btn.setEnabled(not running and bool(self.input_edit.text().strip()))
        self.output_btn.setEnabled(not running)
        self.header_checkbox.setEnabled(not running)
        self.export_report_checkbox.setEnabled(not running)
        self.block_on_collisions_checkbox.setEnabled(not running)
        self.example_btn.setEnabled(not running)

    def show_help(self):
        """显示帮助信息"""
        help_text = """
<h2>Rename IDs &mdash; Batch Rename FASTA Sequence IDs</h2>

<p><b>What does this tool do?</b><br>
It renames FASTA sequence IDs in bulk using a mapping file. You create a simple
two-column table (old ID → new ID), and the tool applies all the remapping at once.</p>

<h3>Quick Start for Beginners</h3>
<ol>
<li>Select a FASTA file using <b>Browse</b> or drag-and-drop.</li>
<li>Click <b>Export Current IDs</b> — this creates a template file (Excel, CSV,
or TSV) listing every ID in your FASTA with an empty "new ID" column.</li>
<li>Open the template in Excel or any text editor and fill in the new IDs
you want in the second column.</li>
<li>Save and come back to the tool. Select your edited file as the
<b>ID mapping file</b>.</li>
<li>Click <b>Preview</b> to verify the first few renamings look correct.</li>
<li>Choose an output file, then click <b>Run</b>.</li>
</ol>

<h3>Mapping File Format</h3>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>old_id</b></td><td><b>new_id</b></td></tr>
<tr><td>sequence_001</td><td>Gene_A</td></tr>
<tr><td>sequence_002</td><td>Gene_B</td></tr>
<tr><td>NM_001101.5</td><td>RefSeq_001</td></tr>
</table>
<p>Supported formats: CSV (<code>.csv</code>), TSV/TXT (<code>.tsv .txt</code>),
Excel (<code>.xlsx .xls</code>) when pandas is installed.</p>

<h3>Options</h3>
<ul>
<li><b>Mapping file contains header row</b> &mdash; uncheck if your file has no
header and the first row is data.</li>
<li><b>Block on collisions</b> &mdash; stop if two old IDs map to the same new ID.
This prevents accidental duplicate sequence IDs. Turn off only if you are
sure duplicates are acceptable.</li>
<li><b>Export rename report</b> &mdash; save a TSV file showing every old→new
mapping, whether it was applied, and why.</li>
</ul>

<h3>Tips</h3>
<ul>
<li>Click <b>Example</b> to load the bundled cytb FASTA plus a ready-made
ID mapping file (Excel, <code>old_id → new_id</code>) — great for a first try.</li>
<li>Always <b>Preview</b> before running — mapping errors are easy to miss.</li>
<li>Only the primary FASTA ID (the part before the first space) is replaced;
descriptions are preserved.</li>
<li>IDs not listed in the mapping file stay unchanged.</li>
<li>If no IDs match the mapping file, no FASTA output is written (a rename report is still saved if that option is enabled).</li>
</ul>
        """

        self.show_help_dialog("Help - Rename IDs", help_text, 600, 480)
