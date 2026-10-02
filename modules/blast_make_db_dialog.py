import os
import subprocess

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from utils.app_paths import exe_name
from utils.process_control import kill_process_tree
from utils.run_provenance import record_tool_run

from .blast_config import get_blast_bin_dir, set_blast_bin_dir


class _MakeDbThread(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, bin_dir, fasta, dbtype, outpath):
        super().__init__()
        self.bin_dir = bin_dir
        self.fasta = fasta
        self.dbtype = dbtype
        self.outpath = outpath
        self._proc = None
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        if self._proc and self._proc.poll() is None:
            kill_process_tree(self._proc)

    def run(self):
        if self._cancelled:
            self.finished.emit(False, "Cancelled by user.")
            return
        exe = os.path.join(self.bin_dir, exe_name("makeblastdb"))
        cmd = [
            exe,
            "-in",
            os.path.abspath(self.fasta),
            "-dbtype",
            self.dbtype,
            "-out",
            os.path.abspath(self.outpath),
            "-title",
            os.path.basename(self.outpath),
            "-blastdb_version",
            "4",
        ]
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                start_new_session=os.name != "nt",
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if self._cancelled:
                kill_process_tree(self._proc)
            stdout, stderr = self._proc.communicate(timeout=300)
            if self._cancelled:
                self.finished.emit(False, "Cancelled by user.")
            elif self._proc.returncode == 0:
                record_tool_run(
                    os.path.dirname(self.outpath),
                    tool="makeblastdb",
                    exe=exe,
                    cmd=cmd,
                    output_path=os.path.abspath(self.outpath),
                )
                self.finished.emit(True, stdout.strip())
            else:
                self.finished.emit(False, (stderr or stdout).strip())
        except subprocess.TimeoutExpired:
            kill_process_tree(self._proc)
            self._proc.communicate()
            self.finished.emit(False, "makeblastdb timed out after 300 seconds.")
        except Exception as exc:
            self.finished.emit(False, str(exc))
