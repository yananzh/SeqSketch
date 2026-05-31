from __future__ import annotations

from PyQt6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTextEdit,
    QWidget,
)

from modules.one_step_multigenephy_io import read_excel_columns
from utils.common_components import BaseTabWidget


def _wrap_layout(layout) -> QWidget:
    container = QWidget()
    container.setLayout(layout)
    return container


class OneStepMultiGenePhyTab(BaseTabWidget):
    def __init__(self, status_callback=None):
        self._status_callback = status_callback
        self.gene_columns: list[str] = []
        super().__init__("One Step MultiGenePhy", "file")
        self._build_ui()

    def _build_ui(self) -> None:
        input_group = QGroupBox(self.tr("Input"))
        input_form = QFormLayout(input_group)

        self.excel_path_edit = QLineEdit()
        self.excel_path_edit.setPlaceholderText(self.tr("Select an Excel workbook"))
        self.sheet_name_edit = QLineEdit("Sheet1")
        self.strain_column_edit = QLineEdit("Strain")
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText(self.tr("name@example.com"))
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText(self.tr("Select an output directory"))

        self.gene_list = QListWidget()
        self.gene_list.setMinimumHeight(110)

        self.summary_view = QTextEdit()
        self.summary_view.setReadOnly(True)
        self.summary_view.setMaximumHeight(120)
        self.summary_view.setPlaceholderText(self.tr("Imported workbook summary will appear here."))

        browse_excel_btn = QPushButton(self.tr("Browse"))
        preview_columns_btn = QPushButton(self.tr("Preview Columns"))
        browse_output_btn = QPushButton(self.tr("Browse"))

        browse_excel_btn.clicked.connect(self._choose_excel)
        preview_columns_btn.clicked.connect(self.load_sheet_columns)
        browse_output_btn.clicked.connect(self._choose_output_dir)

        excel_row = QHBoxLayout()
        excel_row.setContentsMargins(0, 0, 0, 0)
        excel_row.addWidget(self.excel_path_edit)
        excel_row.addWidget(browse_excel_btn)
        excel_row.addWidget(preview_columns_btn)

        output_row = QHBoxLayout()
        output_row.setContentsMargins(0, 0, 0, 0)
        output_row.addWidget(self.output_dir_edit)
        output_row.addWidget(browse_output_btn)

        input_form.addRow(self.tr("Excel file:"), _wrap_layout(excel_row))
        input_form.addRow(self.tr("Sheet name:"), self.sheet_name_edit)
        input_form.addRow(self.tr("Strain column:"), self.strain_column_edit)
        input_form.addRow(self.tr("NCBI email:"), self.email_edit)
        input_form.addRow(self.tr("Gene list:"), self.gene_list)
        input_form.addRow(self.tr("Output directory:"), _wrap_layout(output_row))
        input_form.addRow(self.tr("Import summary:"), self.summary_view)

        run_monitor_group = QGroupBox(self.tr("Run Monitor"))
        run_monitor_layout = QFormLayout(run_monitor_group)

        self.step_summary_label = QLabel(
            self.tr(
                "Import -> Fetch/Normalize -> Align per Gene -> Trim per Gene -> Concatenate -> Build Tree -> Summarize"
            )
        )
        self.artifact_list = QListWidget()
        self.artifact_list.setMinimumHeight(90)
        self.run_workflow_btn = QPushButton(self.tr("Run Workflow"))
        self.run_workflow_btn.clicked.connect(self.start_run)

        run_monitor_layout.addRow(self.tr("Step summary:"), self.step_summary_label)
        run_monitor_layout.addRow(self.tr("Artifacts:"), self.artifact_list)
        run_monitor_layout.addRow(QWidget(), self.run_workflow_btn)

        self.add_content_widget(input_group)
        self.add_content_widget(run_monitor_group)
        self.content_area.addStretch()

    def _choose_excel(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select Excel file"),
            "",
            self.tr("Excel Files (*.xlsx *.xls);;All Files (*)"),
        )
        if file_path:
            self.excel_path_edit.setText(file_path)

    def _choose_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            self.tr("Select output directory"),
            self.output_dir_edit.text().strip(),
        )
        if directory:
            self.output_dir_edit.setText(directory)

    def load_sheet_columns(self) -> None:
        excel_path = self.excel_path_edit.text().strip()
        sheet_name = self.sheet_name_edit.text().strip() or "Sheet1"
        strain_column = self.strain_column_edit.text().strip()

        if not excel_path:
            self.show_status(self.tr("Select an Excel file first"))
            self.log_message(self.tr("Select an Excel file before previewing columns."), "WARNING")
            return

        try:
            columns = read_excel_columns(excel_path, sheet_name)
        except Exception as exc:
            self.show_status(self.tr("Failed to load workbook columns"))
            self.log_message(str(exc), "ERROR")
            return

        gene_names = [column for column in columns if column != strain_column]
        self._populate_gene_columns(gene_names)
        self.show_status(self.tr("Loaded sheet columns"))
        self.log_message(
            self.tr("Loaded {count} candidate gene columns from the workbook.").format(
                count=len(gene_names)
            )
        )

    def _populate_gene_columns(self, gene_names: list[str]) -> None:
        self.gene_list.clear()
        self.gene_columns = list(gene_names)
        self.gene_list.addItems(self.gene_columns)

    def _render_import_summary(self, summary: dict[str, int]) -> None:
        self.summary_view.setPlainText(
            "\n".join(
                [
                    f"Strains: {summary.get('strain_count', 0)}",
                    f"Genes: {summary.get('gene_count', 0)}",
                    f"Accessions: {summary.get('accession_count', 0)}",
                    f"Raw sequences: {summary.get('sequence_count', 0)}",
                    f"Missing: {summary.get('missing_count', 0)}",
                    f"Invalid: {summary.get('invalid_count', 0)}",
                ]
            )
        )

    def _handle_step_update(self, step_name: str, status: str) -> None:
        message = f"{step_name}: {status}"
        self.step_summary_label.setText(message)
        self.show_status(message)
        if self._status_callback is not None:
            self._status_callback(message)

    def _append_log(self, line: str) -> None:
        self.log_message(line)

    def _handle_run_completed(self, result) -> None:
        self.artifact_list.clear()
        for path in (
            getattr(result.artifacts, "treefile_path", ""),
            getattr(result.artifacts, "manifest_path", ""),
            getattr(result.artifacts, "report_path", ""),
        ):
            if path:
                self.artifact_list.addItem(path)

        warnings = list(getattr(result, "warnings", []))
        self.show_status(
            self.tr("Completed with warnings") if warnings else self.tr("Completed")
        )
        for warning in warnings:
            self.log_message(warning, "WARNING")

    def start_run(self) -> None:
        self.log_message(self.tr("Workflow start requested"))
        self.show_status(self.tr("Mock workflow request queued"))

    def show_help(self) -> None:
        self.log_message(
            self.tr(
                "Load workbook columns, review the import summary, and use Run Workflow once orchestration is connected in a later task."
            )
        )
