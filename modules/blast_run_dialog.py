import os
import subprocess

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from utils.app_paths import exe_name
from utils.run_provenance import record_tool_run

from .blast_config import get_blast_bin_dir, set_blast_bin_dir

# outfmt 6 column names (header written to TSV)
_TSV_HEADER = (
    "qseqid\tsseqid\tpident\tlength\tmismatch\tgapopen"
    "\tqstart\tqend\tsstart\tsend\tevalue\tbitscore\n"
)

_PROG_TIPS = {
    "blastn": "Nucleotide vs. Nucleotide  — search DNA/RNA query against a nucleotide database.",
    "blastp": "Protein vs. Protein  — search amino acid query against a protein database.",
    "blastx": "Translated Nucleotide vs. Protein  — translate a DNA query in all 6 frames and search a protein database.",
    "tblastn": "Protein vs. Translated Nucleotide  — search protein query against a translated nucleotide database.",
    "tblastx": "Translated Nucleotide vs. Translated Nucleotide  — both query and database are translated.",
}


class _RunBlastThread(QThread):
    finished = pyqtSignal(bool, str, str)  # success, out_file, message

    def __init__(
        self,
        bin_dir,
        program,
        db,
        evalue,
        query_seq,
        out_file,
        num_threads,
        num_hits,
        outfmt="6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore",
    ):
        super().__init__()
        self.bin_dir = bin_dir
        self.program = program
        self.db = db
        self.evalue = evalue
        self.query_seq = query_seq
        self.out_file = out_file
        self.num_threads = str(num_threads)
        self.num_hits = str(num_hits)
        self.outfmt = outfmt
        self._proc = None
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        if self._proc and self._proc.poll() is None:
            self._proc.kill()

    def run(self):
        self._cancelled = False
        exe = os.path.join(self.bin_dir, exe_name(self.program))
        query_tmp = self.out_file + ".query.tmp.fasta"
        tmp_out = self.out_file + ".tmp"

        try:
            with open(query_tmp, "w", encoding="utf-8") as f:
                f.write(self.query_seq)

            cmd = [
                exe,
                "-query",
                query_tmp,
                "-db",
                self.db,
                "-evalue",
                self.evalue,
                "-out",
                tmp_out,
                "-outfmt",
                self.outfmt,
                "-num_threads",
                self.num_threads,
                "-max_target_seqs",
                self.num_hits,
            ]

            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            stdout, stderr = self._proc.communicate(timeout=3600)

            if self._cancelled:
                self.finished.emit(False, "", "Cancelled by user.")
            elif self._proc.returncode == 0:
                with open(self.out_file, "w", encoding="utf-8") as fout:
                    # Column names only make sense for tabular output; a TSV
                    # header would corrupt pairwise (0) or XML (5) files.
                    if self.outfmt.startswith("6"):
                        fout.write(_TSV_HEADER)
                    if os.path.exists(tmp_out):
                        with open(tmp_out, "r", encoding="utf-8") as fin:
                            fout.write(fin.read())
                record_tool_run(
                    os.path.dirname(self.out_file),
                    tool="BLAST",
                    exe=exe,
                    cmd=cmd,
                    output_path=self.out_file,
                )
                self.finished.emit(True, self.out_file, "")
            else:
                self.finished.emit(False, "", (stderr or stdout).strip())

        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.communicate()
            self.finished.emit(False, "", "BLAST search timed out after 3600 seconds.")
        except Exception as exc:
            self.finished.emit(False, "", str(exc))
        finally:
            for p in (query_tmp, tmp_out):
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
