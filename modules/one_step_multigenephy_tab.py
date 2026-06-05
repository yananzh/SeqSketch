from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.one_step_multigenephy_io import (
    parse_excel_sheet,
    read_excel_columns,
    read_excel_sheet_names,
)
from modules.one_step_multigenephy_models import ProjectInput
from modules.one_step_multigenephy_workflow import (
    OneStepMultiGenePhyRunner,
    WorkflowWorker,
    _iqtree_executable,
    _mafft_executable,
    _trimal_executable,
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
        self._loading = False
        super().__init__("One Step MultiGenePhy", "file")
        self._build_ui()

    def _build_ui(self) -> None:
        # ── Input section ──
        input_group = QGroupBox(self.tr("Input"))
        input_form = QFormLayout(input_group)

        self.excel_path_edit = QLineEdit()
        self.excel_path_edit.setPlaceholderText(self.tr("Select an Excel workbook"))
        self.sheet_name_combo = QComboBox()
        self.sheet_name_combo.setEditable(True)
        self.sheet_name_combo.addItem("Sheet1")
        self.sheet_name_combo.setToolTip(
            self.tr("Sheet name — auto-populated after Preview Columns")
        )
        self.strain_column_combo = QComboBox()
        self.strain_column_combo.setEditable(True)
        self.strain_column_combo.addItem("Strain")
        self.strain_column_combo.setToolTip(
            self.tr("Strain identifier column — auto-populated after Preview Columns")
        )
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText(self.tr("name@example.com"))
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText(self.tr("Select an output directory"))

        self.gene_list = QListWidget()
        self.gene_list.setFlow(QListView.Flow.LeftToRight)
        self.gene_list.setWrapping(True)
        self.gene_list.setMinimumHeight(36)
        self.gene_list.setMaximumHeight(64)
        self.gene_list.setSpacing(4)

        browse_excel_btn = QPushButton(self.tr("Browse"))
        browse_output_btn = QPushButton(self.tr("Browse"))

        browse_excel_btn.clicked.connect(self._choose_excel)
        browse_output_btn.clicked.connect(self._choose_output_dir)

        excel_row = QHBoxLayout()
        excel_row.setContentsMargins(0, 0, 0, 0)
        excel_row.addWidget(self.excel_path_edit)
        excel_row.addWidget(browse_excel_btn)

        output_row = QHBoxLayout()
        output_row.setContentsMargins(0, 0, 0, 0)
        output_row.addWidget(self.output_dir_edit)
        output_row.addWidget(browse_output_btn)

        input_form.addRow(self.tr("Excel file:"), _wrap_layout(excel_row))

        # Sheet / Strain / Email in a single horizontal row
        detail_row = QHBoxLayout()
        detail_row.setContentsMargins(0, 0, 0, 0)
        sheet_lbl = QLabel(self.tr("Select Sheet:"))
        strain_lbl = QLabel(self.tr("Select Strain Column:"))
        email_lbl = QLabel(self.tr("Email:"))
        self.sheet_name_combo.setMinimumWidth(110)
        self.strain_column_combo.setMinimumWidth(110)
        detail_row.addWidget(sheet_lbl)
        detail_row.addWidget(self.sheet_name_combo, 1)
        detail_row.addWidget(strain_lbl)
        detail_row.addWidget(self.strain_column_combo, 1)
        detail_row.addWidget(email_lbl)
        detail_row.addWidget(self.email_edit, 2)
        input_form.addRow(self.tr("Details:"), _wrap_layout(detail_row))

        # Auto-refresh gene list when sheet or strain changes
        self.sheet_name_combo.currentTextChanged.connect(self._on_detail_changed)
        self.strain_column_combo.currentTextChanged.connect(self._on_detail_changed)

        input_form.addRow(self.tr("Gene list:"), self.gene_list)
        input_form.addRow(self.tr("Output directory:"), _wrap_layout(output_row))

        # Validate button row
        validate_btn = QPushButton(self.tr("🔍  Validate Inputs"))
        validate_btn.clicked.connect(self._check_inputs)
        validate_row = QHBoxLayout()
        validate_row.setContentsMargins(0, 0, 0, 0)
        validate_row.addWidget(validate_btn)
        validate_row.addStretch()
        input_form.addRow(QWidget(), _wrap_layout(validate_row))

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
        self.bootstrap_mode_combo = QComboBox()
        self.bootstrap_mode_combo.addItems([
            self.tr("UFBoot (ultrafast bootstrap)"),
            self.tr("UFBoot + SH-aLRT"),
            self.tr("Standard nonparametric bootstrap"),
        ])
        self.bootstrap_mode_combo.setCurrentIndex(0)
        self.bootstrap_mode_combo.setToolTip(
            self.tr(
                "UFBoot: ultrafast (-B); UFBoot+SH-aLRT: ultrafast + branch test (-B -alrt); "
                "Standard: nonparametric (-b)"
            )
        )
        self.bootstrap_spin = QSpinBox()
        self.bootstrap_spin.setRange(0, 10000)
        self.bootstrap_spin.setValue(1000)
        self.bootstrap_spin.setSpecialValueText(self.tr("0 (disabled)"))
        self.bootstrap_spin.setToolTip(
            self.tr("Number of bootstrap replicates (0 = skip)")
        )
        boot_row = QHBoxLayout()
        boot_row.setContentsMargins(0, 0, 0, 0)
        boot_row.addWidget(self.bootstrap_mode_combo, 1)
        boot_row.addWidget(self.bootstrap_spin)
        param_form.addRow(self.tr("IQ-TREE Bootstrap:"), _wrap_layout(boot_row))

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

        # ── Actions row (bottom-left) ──
        actions_row = QHBoxLayout()
        self.start_btn = QPushButton(self.tr("▶  Start Workflow"))
        self.start_btn.setMinimumHeight(36)
        self.start_btn.clicked.connect(self.start_run)
        self.cancel_btn = QPushButton(self.tr("■  Cancel"))
        self.cancel_btn.setMinimumHeight(36)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel_workflow)
        actions_row.addWidget(self.start_btn)
        actions_row.addWidget(self.cancel_btn)
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
            self.load_sheet_columns()

    def _on_detail_changed(self) -> None:
        """Auto-refresh gene list when sheet or strain column changes."""
        if self._loading:
            return
        excel_path = self.excel_path_edit.text().strip()
        if excel_path:
            self.load_sheet_columns()

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
        sheet_name = self.sheet_name_combo.currentText().strip() or "Sheet1"
        strain_column = self.strain_column_combo.currentText().strip()

        if not excel_path:
            return

        self._loading = True
        try:
            sheet_names = read_excel_sheet_names(excel_path)
            self.sheet_name_combo.clear()
            self.sheet_name_combo.addItems(sheet_names)
            if sheet_name in sheet_names:
                self.sheet_name_combo.setCurrentText(sheet_name)
            columns = read_excel_columns(excel_path, sheet_name)

            # Populate strain column dropdown with all columns
            self.strain_column_combo.clear()
            self.strain_column_combo.addItems(columns)
            if strain_column in columns:
                self.strain_column_combo.setCurrentText(strain_column)

            gene_names = [
                column for column in columns if column != strain_column
            ]
            self._populate_gene_columns(gene_names)
            self.show_status(self.tr("Loaded sheet columns"))
            self.log_message(
                self.tr(
                    "Loaded {count} candidate gene columns from sheet \"{sheet}\"."
                ).format(count=len(gene_names), sheet=sheet_name)
            )
        except Exception as exc:
            self.show_status(self.tr("Failed to load workbook columns"))
            self.log_message(str(exc), "ERROR")
        finally:
            self._loading = False

    def _populate_gene_columns(self, gene_names: list[str]) -> None:
        self.gene_list.clear()
        self.gene_columns = list(gene_names)
        for name in self.gene_columns:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.gene_list.addItem(item)

    def _select_all_genes(self) -> None:
        for i in range(self.gene_list.count()):
            self.gene_list.item(i).setCheckState(Qt.CheckState.Checked)

    def _deselect_all_genes(self) -> None:
        for i in range(self.gene_list.count()):
            self.gene_list.item(i).setCheckState(Qt.CheckState.Unchecked)

    def _checked_gene_columns(self) -> list[str]:
        return [
            self.gene_list.item(i).text()
            for i in range(self.gene_list.count())
            if self.gene_list.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _log_import_summary(self, summary: dict[str, int]) -> None:
        self.log_message(self.tr("── Import Summary ──"))
        self.log_message(
            self.tr("Strains: {count}").format(
                count=summary.get("strain_count", 0)
            )
        )
        self.log_message(
            self.tr("Genes: {count}").format(count=summary.get("gene_count", 0))
        )
        self.log_message(
            self.tr("Accessions: {count}").format(
                count=summary.get("accession_count", 0)
            )
        )
        self.log_message(
            self.tr("Raw sequences: {count}").format(
                count=summary.get("sequence_count", 0)
            )
        )
        self.log_message(
            self.tr("Missing: {count}").format(
                count=summary.get("missing_count", 0)
            )
        )
        self.log_message(
            self.tr("Invalid: {count}").format(
                count=summary.get("invalid_count", 0)
            )
        )

    def _handle_step_update(self, step_name: str, status: str) -> None:
        message = f"{step_name}: {status}"
        self.show_status(message)
        self.log_message(message)
        if self._status_callback is not None:
            self._status_callback(message)

    def _append_log(self, line: str) -> None:
        self.log_message(line)

    def _handle_run_failed(self, message: str) -> None:
        self.show_status(self.tr("Workflow failed"))
        self.log_message(message, "ERROR")
        self._set_running_state(False)
        if self._status_callback is not None:
            self._status_callback(message)

    def _handle_run_completed(self, result) -> None:
        step_status = dict(getattr(result, "step_status", {}))
        self.log_message(self.tr("── Run Summary ──"))
        for step_name, status in step_status.items():
            self.log_message(f"  {step_name}: {status}")

        # Log artifact paths
        artifacts = getattr(result, "artifacts", None)
        if artifacts:
            self.log_message(self.tr("── Artifacts ──"))
            for label, attr in [
                ("Tree file", "treefile_path"),
                ("HTML report", "html_report_path"),
                ("Manifest", "manifest_path"),
                ("Text report", "report_path"),
            ]:
                path = getattr(artifacts, attr, "")
                if path:
                    self.log_message(f"  {label}: {path}")

        warnings = list(getattr(result, "warnings", []))
        self.show_status(
            self.tr("Completed with warnings") if warnings else self.tr("Completed")
        )
        for warning in warnings:
            self.log_message(warning, "WARNING")
        self._set_running_state(False)

    # ------------------------------------------------------------------
    # Button state management
    # ------------------------------------------------------------------
    def _set_running_state(self, running: bool) -> None:
        self.start_btn.setVisible(not running)
        self.cancel_btn.setVisible(running)

    # ------------------------------------------------------------------
    # Pre-run validation
    # ------------------------------------------------------------------
    def _validate_inputs(
        self, excel_path: str, output_dir: str, checked_genes: list[str], ncbi_email: str
    ) -> bool:
        if not excel_path or not os.path.isfile(excel_path):
            self.show_status(self.tr("Excel file not found"))
            self.log_message(
                self.tr("The selected Excel file does not exist."), "ERROR"
            )
            return False

        if not output_dir:
            self.show_status(self.tr("No output directory"))
            self.log_message(
                self.tr("Please select an output directory."), "WARNING"
            )
            return False

        if not checked_genes:
            self.show_status(self.tr("No genes selected"))
            self.log_message(
                self.tr("Select at least one gene column before running."), "WARNING"
            )
            return False

        if not ncbi_email:
            reply = QMessageBox.question(
                self,
                self.tr("Missing NCBI Email"),
                self.tr(
                    "No NCBI email was provided. If any gene cells contain "
                    "accession values (public data), the fetch will fail.\n\n"
                    "Continue without an email?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return False

        return True

    # ------------------------------------------------------------------
    # Input validation & tool checks
    # ------------------------------------------------------------------
    def _check_inputs(self) -> None:
        """Validate file format and external tool availability."""
        excel_path = self.excel_path_edit.text().strip()
        sheet_name = self.sheet_name_combo.currentText().strip() or "Sheet1"
        strain_column = self.strain_column_combo.currentText().strip()

        self.log_message(self.tr("── Input Validation ──"))

        # 1. Check Excel file
        if not excel_path or not os.path.isfile(excel_path):
            self.log_message(self.tr("✗ Excel file not found"), "ERROR")
            self.show_status(self.tr("Validation failed"))
            return
        self.log_message(self.tr("✓ Excel file: {path}").format(path=excel_path))

        # 2. Check strain names for spaces / special chars
        try:
            import pandas as pd
            df = pd.read_excel(excel_path, sheet_name=sheet_name, header=0)
            if strain_column not in df.columns:
                self.log_message(
                    self.tr("✗ Strain column \"{col}\" not found").format(
                        col=strain_column
                    ),
                    "ERROR",
                )
                self.show_status(self.tr("Validation failed"))
                return

            strain_names = df[strain_column].fillna("").astype(str).str.strip()
            bad_names: list[str] = []
            for name in strain_names:
                if not name:
                    bad_names.append("(blank)")
                elif name != name.replace(" ", "_").replace("/", "_").replace("\\", "_"):
                    bad_names.append(name)
            if bad_names:
                self.log_message(
                    self.tr(
                        "⚠ {count} strain name(s) contain spaces or special chars "
                        "(may cause issues with downstream tools):"
                    ).format(count=len(bad_names)),
                    "WARNING",
                )
                for name in bad_names[:10]:
                    self.log_message(f"    • {name}", "WARNING")
                if len(bad_names) > 10:
                    self.log_message(
                        self.tr("    … and {n} more").format(
                            n=len(bad_names) - 10
                        ),
                        "WARNING",
                    )
            else:
                self.log_message(self.tr("✓ Strain names: all valid"))
        except Exception as exc:
            self.log_message(
                self.tr("⚠ Could not check strain names: {error}").format(error=exc),
                "WARNING",
            )

        # 3. Check external tools
        self.log_message(self.tr("── Tool Availability ──"))
        tools = [
            ("MAFFT", _mafft_executable()),
            ("trimAl", _trimal_executable()),
            ("IQ-TREE", _iqtree_executable()),
        ]
        all_ok = True
        for tool_name, tool_path in tools:
            if os.path.isfile(tool_path):
                self.log_message(
                    self.tr("✓ {tool}: {path}").format(
                        tool=tool_name, path=tool_path
                    )
                )
            else:
                self.log_message(
                    self.tr("✗ {tool}: NOT FOUND ({path})").format(
                        tool=tool_name, path=tool_path
                    ),
                    "ERROR",
                )
                all_ok = False

        if all_ok:
            self.show_status(self.tr("Validation passed"))
        else:
            self.show_status(self.tr("Validation failed — see log"))

    # ------------------------------------------------------------------
    # Cancel support
    # ------------------------------------------------------------------
    def _cancel_workflow(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()
            self._worker._abort = True
            self.log_message(self.tr("Cancellation requested — waiting for current step to finish…"), "WARNING")
            self.show_status(self.tr("Cancelling…"))

    def _cleanup_worker(self) -> None:
        if self._worker is not None:
            if self._worker.isRunning():
                self._worker.requestInterruption()
                self._worker._abort = True
                self._worker.wait(5000)
            self._worker = None

    # ------------------------------------------------------------------
    # Run workflow
    # ------------------------------------------------------------------
    def start_run(self) -> None:
        excel_path = self.excel_path_edit.text().strip()
        sheet_name = self.sheet_name_combo.currentText().strip() or "Sheet1"
        strain_column = self.strain_column_combo.currentText().strip()
        output_dir = self.output_dir_edit.text().strip()
        ncbi_email = self.email_edit.text().strip()
        checked_genes = self._checked_gene_columns()

        if not self._validate_inputs(excel_path, output_dir, checked_genes, ncbi_email):
            return

        try:
            parsed = parse_excel_sheet(
                excel_path,
                sheet_name,
                strain_column,
                checked_genes,
            )
        except Exception as exc:
            self.show_status(self.tr("Failed to parse workbook"))
            self.log_message(str(exc), "ERROR")
            return

        self._log_import_summary(parsed.summary)

        project = ProjectInput(
            excel_path=excel_path,
            sheet_name=sheet_name,
            strain_column=strain_column,
            gene_columns=checked_genes,
            output_dir=output_dir,
            ncbi_email=ncbi_email,
            mafft_mode=self.mafft_mode_combo.currentText(),
            trimal_mode=self.trimal_mode_combo.currentText(),
            iqtree_bootstrap=self.bootstrap_spin.value(),
            iqtree_bootstrap_mode=["ufboot", "ufboot_shalrt", "standard"][
                self.bootstrap_mode_combo.currentIndex()
            ],
            threads=str(self.threads_spin.value())
            if self.threads_spin.value() > 0
            else "AUTO",
            keep_intermediates=self.keep_intermediates_check.isChecked(),
        )
        commands: list[str] = []
        runner = OneStepMultiGenePhyRunner(
            adapters=build_default_tool_adapters(commands=commands),
            commands=commands,
        )
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

        self._cleanup_worker()
        self._worker = worker
        self._set_running_state(True)
        self.show_status(self.tr("Workflow running"))
        self.log_message(self.tr("Workflow started"))
        worker.start()

    def show_help(self) -> None:
        QMessageBox.information(
            self,
            self.tr("One Step MultiGenePhy Help"),
            self.tr(
                "One Step MultiGenePhy imports a gene-by-gene Excel workbook and runs "
                "download/normalize, alignment, trimming, concatenation, and tree building "
                "in one automated workflow.\n\n"
                "Workbook format:\n"
                "- First row = header; one column = strain IDs; remaining columns = genes.\n"
                "- Each gene cell: NCBI accession (e.g. ON123456.1), raw DNA sequence, or blank.\n\n"
                "Quick start:\n"
                "1. Browse to select an Excel workbook → sheet & strain column auto-populate.\n"
                "2. Check/uncheck gene columns as needed.\n"
                "3. Enter NCBI email if using accessions.\n"
                "4. (Optional) Click Validate Inputs to check file format and tool availability.\n"
                "5. Adjust pipeline options if desired (MAFFT, trimAl, IQ-TREE bootstrap).\n"
                "6. Select an output directory and click Start Workflow.\n\n"
                "Pipeline outputs (in <output>/06_reports/):\n"
                "- run_report.html — full HTML report with step status, warnings, and tool commands\n"
                "- summary.txt — plain-text summary\n"
                "- run_manifest.json — machine-readable manifest\n\n"
                "Notes:\n"
                "- Strain names with spaces or special characters are flagged by Validate Inputs; "
                "IQ-TREE requires clean names (alphanumeric + underscore).\n"
                "- Genes with fewer than 2 usable sequences are skipped with a warning.\n"
                "- Intermediate files (normalized/aligned/trimmed) are preserved by default.\n"
                "- The Operation Log records all progress, warnings, and errors."
            ),
        )
