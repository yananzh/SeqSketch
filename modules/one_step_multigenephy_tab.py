from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.one_step_multigenephy_io import parse_excel_sheet, read_excel_columns
from modules.one_step_multigenephy_models import ProjectInput
from modules.one_step_multigenephy_workflow import (
    OneStepMultiGenePhyRunner,
    WorkflowWorker,
    build_default_tool_adapters,
)
from utils.common_components import BaseTabWidget


def _wrap_layout(layout) -> QWidget:
    container = QWidget()
    container.setLayout(layout)
    return container


class OneStepMultiGenePhyTab(BaseTabWidget):
    def __init__(self, status_callback=None):
        self._status_callback = status_callback
        self.gene_columns: list[str] = []
        self._worker: WorkflowWorker | None = None
        super().__init__("One Step MultiGenePhy", "file")
        self._build_ui()

    def _build_ui(self) -> None:
        # ── Input section ──
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
        self.summary_view.setPlaceholderText(
            self.tr("Imported workbook summary will appear here.")
        )

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

        self.add_content_widget(input_group)

        # ── Parameters section ──
        param_group = QGroupBox(self.tr("Pipeline Options"))
        param_form = QFormLayout(param_group)

        # MAFFT alignment mode
        self.mafft_mode_combo = QComboBox()
        self.mafft_mode_combo.addItems([
            "--auto",
            "--localpair",
            "--globalpair",
            "--genafpair",
        ])
        self.mafft_mode_combo.setCurrentText("--auto")
        self.mafft_mode_combo.setToolTip(
            self.tr(
                "--auto: automatic selection; --localpair: local alignment; "
                "--globalpair: global alignment; --genafpair: conserved region alignment"
            )
        )
        param_form.addRow(self.tr("MAFFT mode:"), self.mafft_mode_combo)

        # trimAl trimming strategy
        self.trimal_mode_combo = QComboBox()
        self.trimal_mode_combo.addItems([
            "automated1",
            "nogaps",
            "gappyout",
            "strict",
            "strictplus",
        ])
        self.trimal_mode_combo.setCurrentText("automated1")
        self.trimal_mode_combo.setToolTip(
            self.tr(
                "automated1: heuristic trimming; nogaps: remove columns with gaps; "
                "gappyout: adaptive gap-based trimming; strict/strictplus: conservative trimming"
            )
        )
        param_form.addRow(self.tr("trimAl mode:"), self.trimal_mode_combo)

        # IQ-TREE bootstrap
        self.bootstrap_spin = QSpinBox()
        self.bootstrap_spin.setRange(0, 10000)
        self.bootstrap_spin.setValue(1000)
        self.bootstrap_spin.setSpecialValueText(self.tr("0 (disabled)"))
        self.bootstrap_spin.setToolTip(
            self.tr("Number of ultrafast bootstrap replicates (0 = skip bootstrap)")
        )
        param_form.addRow(self.tr("Bootstrap:"), self.bootstrap_spin)

        # Thread count
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(0, 256)
        self.threads_spin.setValue(0)
        self.threads_spin.setSpecialValueText("AUTO")
        self.threads_spin.setToolTip(
            self.tr("CPU threads for MAFFT/IQ-TREE (0 = auto-detect)")
        )
        param_form.addRow(self.tr("Threads:"), self.threads_spin)

        # Keep intermediate files
        self.keep_intermediates_check = QCheckBox(
            self.tr("Preserve intermediate files (normalized, aligned, trimmed)")
        )
        self.keep_intermediates_check.setChecked(True)
        param_form.addRow(self.tr("Intermediate files:"), self.keep_intermediates_check)

        self.add_content_widget(param_group)

        # ── Run Monitor section ──
        run_monitor_group = QGroupBox(self.tr("Run Monitor"))
        run_monitor_layout = QFormLayout(run_monitor_group)

        self.current_step_label = QLabel(self.tr("No step updates yet."))
        self.step_status_view = QTextEdit()
        self.step_status_view.setReadOnly(True)
        self.step_status_view.setMaximumHeight(120)
        self.step_status_view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.step_status_view.setPlaceholderText(
            self.tr("Per-step workflow results will appear here.")
        )
        self.artifact_list = QListWidget()
        self.artifact_list.setMinimumHeight(90)

        run_monitor_layout.addRow(self.tr("Current step:"), self.current_step_label)
        run_monitor_layout.addRow(self.tr("Step results:"), self.step_status_view)
        run_monitor_layout.addRow(self.tr("Artifacts:"), self.artifact_list)

        self.add_content_widget(run_monitor_group)

        # ── Actions row (bottom-left) ──
        actions_row = QHBoxLayout()
        self.start_btn = QPushButton(self.tr("▶  Start Workflow"))
        self.start_btn.setMinimumHeight(36)
        self.start_btn.clicked.connect(self.start_run)
        actions_row.addWidget(self.start_btn)
        actions_row.addStretch()
        self.content_area.addLayout(actions_row)
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
            self.log_message(
                self.tr("Select an Excel file before previewing columns."), "WARNING"
            )
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
            "\n".join([
                self.tr("Strains: {count}").format(
                    count=summary.get("strain_count", 0)
                ),
                self.tr("Genes: {count}").format(count=summary.get("gene_count", 0)),
                self.tr("Accessions: {count}").format(
                    count=summary.get("accession_count", 0)
                ),
                self.tr("Raw sequences: {count}").format(
                    count=summary.get("sequence_count", 0)
                ),
                self.tr("Missing: {count}").format(
                    count=summary.get("missing_count", 0)
                ),
                self.tr("Invalid: {count}").format(
                    count=summary.get("invalid_count", 0)
                ),
            ])
        )

    def _handle_step_update(self, step_name: str, status: str) -> None:
        message = f"{step_name}: {status}"
        self.current_step_label.setText(message)
        self.show_status(message)
        if self._status_callback is not None:
            self._status_callback(message)

    def _render_step_status(self, step_status: dict[str, str]) -> None:
        if not step_status:
            self.step_status_view.clear()
            return

        self.step_status_view.setPlainText(
            "\n".join(
                f"{step_name}: {status}" for step_name, status in step_status.items()
            )
        )

    def _append_log(self, line: str) -> None:
        self.log_message(line)

    def _handle_run_failed(self, message: str) -> None:
        self.show_status(self.tr("Workflow failed"))
        self.log_message(message, "ERROR")
        if self._status_callback is not None:
            self._status_callback(message)

    def _handle_run_completed(self, result) -> None:
        self._render_step_status(dict(getattr(result, "step_status", {})))
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
        excel_path = self.excel_path_edit.text().strip()
        sheet_name = self.sheet_name_edit.text().strip() or "Sheet1"
        strain_column = self.strain_column_edit.text().strip()
        output_dir = self.output_dir_edit.text().strip()
        ncbi_email = self.email_edit.text().strip()

        try:
            parsed = parse_excel_sheet(
                excel_path,
                sheet_name,
                strain_column,
                list(self.gene_columns),
            )
        except Exception as exc:
            self.show_status(self.tr("Failed to parse workbook"))
            self.log_message(str(exc), "ERROR")
            return

        self._render_import_summary(parsed.summary)

        project = ProjectInput(
            excel_path=excel_path,
            sheet_name=sheet_name,
            strain_column=strain_column,
            gene_columns=list(self.gene_columns),
            output_dir=output_dir,
            ncbi_email=ncbi_email,
            mafft_mode=self.mafft_mode_combo.currentText(),
            trimal_mode=self.trimal_mode_combo.currentText(),
            iqtree_bootstrap=self.bootstrap_spin.value(),
            threads=str(self.threads_spin.value())
            if self.threads_spin.value() > 0
            else "AUTO",
            keep_intermediates=self.keep_intermediates_check.isChecked(),
        )
        runner = OneStepMultiGenePhyRunner(adapters=build_default_tool_adapters())
        worker = WorkflowWorker(
            runner,
            project,
            parsed.cells,
            parsed.strain_order,
        )
        worker.completed.connect(self._handle_run_completed)
        worker.failed.connect(self._handle_run_failed)
        worker.step_changed.connect(self._handle_step_update)
        worker.log_line.connect(self._append_log)

        self._worker = worker
        self.show_status(self.tr("Workflow running"))
        self.log_message(self.tr("Workflow started"))
        worker.start()

    def show_help(self) -> None:
        QMessageBox.information(
            self,
            self.tr("One Step MultiGenePhy Help"),
            self.tr(
                "One Step MultiGenePhy imports a gene-by-gene workbook and runs download/normalize, alignment, trimming, concatenation, and tree building in one workflow.\n\n"
                "Workbook format:\n"
                "- The first row must be the header row in the selected Excel sheet.\n"
                "- One column contains the strain name, usually Strain.\n"
                "- Each remaining selected gene column contains either an accession, a raw sequence, or a blank cell.\n"
                "- Public data should be provided as accession values; your own data can be pasted directly as sequences.\n\n"
                "Recommended steps:\n"
                "1. Select the Excel workbook and confirm the sheet name.\n"
                "2. Enter the strain column name and click Preview Columns.\n"
                "3. Review the detected gene columns and import summary.\n"
                "4. Enter an NCBI email if any gene cells use accession values.\n"
                "5. Select an output directory and click Start Workflow.\n\n"
                "Pipeline outputs:\n"
                "- Per-gene normalized, aligned, and trimmed FASTA files\n"
                "- Concatenated alignment and partition definitions when usable genes remain\n"
                "- IQ-TREE result files, including the final tree when tree building succeeds\n"
                "- A run_manifest.json summary plus a text report in the reports folder\n\n"
                "Notes:\n"
                "- Genes with too few usable sequences can be skipped with a warning.\n"
                "- The step monitor shows the current stage, while the log records warnings and failures.\n"
                "- If every gene fails before concatenation, the workflow stops and reports the reason."
            ),
        )
