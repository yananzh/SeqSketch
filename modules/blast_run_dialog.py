from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QComboBox, QMessageBox, QTextEdit)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import os
import subprocess
from .blast_config import get_blast_bin_dir, set_blast_bin_dir

class RunBlastThread(QThread):
    finished = pyqtSignal(bool, str, str)
    def __init__(self, bin_dir, program, db, evalue, query_seq, out_file, num_threads, num_hits):
        super().__init__()
        self.bin_dir = bin_dir
        self.program = program
        self.db = db
        self.evalue = evalue
        self.query_seq = query_seq
        self.out_file = out_file
        self.num_threads = num_threads
        self.num_hits = num_hits
    def run(self):
        exe = os.path.join(self.bin_dir, self.program + ('.exe' if os.name=='nt' else ''))
        query_file = self.out_file + '.query.tmp.fasta'
        with open(query_file, 'w', encoding='utf-8') as f:
            f.write(self.query_seq)
        # 先运行blast，输出到临时文件
        tmp_out = self.out_file + '.tmp'
        cmd = [exe, '-query', query_file, '-db', self.db, '-evalue', self.evalue, '-out', tmp_out, '-outfmt',
               '6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore',
               '-num_threads', self.num_threads, '-max_target_seqs', self.num_hits]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode == 0:
                # 写表头+内容到最终输出文件
                header = 'qseqid\tsseqid\tpident\tlength\tmismatch\tgapopen\tqstart\tqend\tsstart\tsend\tevalue\tbitscore\n'
                with open(self.out_file, 'w', encoding='utf-8') as fout:
                    fout.write(header)
                    with open(tmp_out, 'r', encoding='utf-8') as fin:
                        for line in fin:
                            fout.write(line)
                self.finished.emit(True, self.out_file, proc.stdout)
            else:
                self.finished.emit(False, self.out_file, proc.stderr or proc.stdout)
        except Exception as e:
            self.finished.emit(False, self.out_file, str(e))
        finally:
            if os.path.exists(query_file):
                os.remove(query_file)
            if os.path.exists(tmp_out):
                os.remove(tmp_out)

class BlastRunDialog(QDialog):
    def __init__(self, parent=None, get_query_seq=None, status_callback=None, result_callback=None):
        super().__init__(parent)
        self.setWindowTitle("Run Local BLAST Query")
        self.status_callback = status_callback
        self.result_callback = result_callback
        self.resize(560, 420)
        layout = QVBoxLayout(self)
        # 查询序列输入区
        query_layout = QHBoxLayout()
        self.query_edit = QTextEdit()
        self.query_edit.setPlaceholderText("Paste FASTA sequence or choose a file")
        self.query_edit.setMinimumHeight(100)
        query_file_btn = QPushButton("Choose File")
        query_file_btn.clicked.connect(self.choose_query_file)
        query_layout.addWidget(QLabel("Query Sequence:"))
        query_layout.addWidget(self.query_edit)
        query_layout.addWidget(query_file_btn)
        # BLAST程序
        prog_layout = QHBoxLayout()
        self.prog_combo = QComboBox()
        self.prog_combo.addItems(["blastp", "blastn", "blastx", "tblastn", "tblastx"])
        prog_layout.addWidget(QLabel("BLAST Program:"))
        prog_layout.addWidget(self.prog_combo)
        # 数据库
        db_layout = QHBoxLayout()
        self.db_edit = QLineEdit()
        self.db_edit.setReadOnly(True)
        db_btn = QPushButton("Browse...")
        db_btn.clicked.connect(self.choose_db)
        db_layout.addWidget(QLabel("Choose local database:"))
        db_layout.addWidget(self.db_edit)
        db_layout.addWidget(db_btn)
        # 参数设置
        param_layout = QHBoxLayout()
        self.threads_edit = QLineEdit("2")
        self.eval_edit = QLineEdit("1e-5")
        self.numhits_edit = QLineEdit("200")
        param_layout.addWidget(QLabel("Threads:"))
        param_layout.addWidget(self.threads_edit)
        param_layout.addWidget(QLabel("E-value:"))
        param_layout.addWidget(self.eval_edit)
        param_layout.addWidget(QLabel("Num of Hits:"))
        param_layout.addWidget(self.numhits_edit)
        # 输出文件
        out_layout = QHBoxLayout()
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("Choose output file path")
        out_btn = QPushButton("Choose Output File")
        out_btn.clicked.connect(self.choose_outfile)
        out_layout.addWidget(QLabel("Output File:"))
        out_layout.addWidget(self.out_edit)
        out_layout.addWidget(out_btn)
        # 查询按钮
        self.run_btn = QPushButton("Run")
        self.run_btn.clicked.connect(self.start_run)
        # 组装
        layout.addLayout(query_layout)
        layout.addLayout(prog_layout)
        layout.addLayout(db_layout)
        layout.addLayout(param_layout)
        layout.addLayout(out_layout)
        layout.addWidget(self.run_btn)
        self.setLayout(layout)
        self.thread = None
        self.get_query_seq = get_query_seq
        self.check_blast_bin()
    def check_blast_bin(self):
        bin_dir = get_blast_bin_dir()
        if not bin_dir or not os.path.isdir(bin_dir):
            while True:
                ret = QMessageBox.question(self, "First Use", "Please specify BLAST+ bin directory (contains blastp, etc.)", QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
                if ret == QMessageBox.StandardButton.Cancel:
                    self.reject()
                    return
                dir_ = QFileDialog.getExistingDirectory(self, "Choose BLAST+ bin directory")
                if dir_ and os.path.isdir(dir_):
                    set_blast_bin_dir(dir_)
                    break
    def choose_db(self):
        file, _ = QFileDialog.getOpenFileName(self, "Choose database primary file", "", "BLAST Database Primary File (*)")
        if file:
            self.db_edit.setText(os.path.splitext(file)[0])
    def choose_query_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select FASTA sequence file", "", "FASTA Files (*.fasta *.fa *.faa *.txt);;All Files (*)")
        if file:
            with open(file, 'r', encoding='utf-8') as f:
                seq = f.read()
            self.query_edit.setPlainText(seq)
    def choose_outfile(self):
        file, _ = QFileDialog.getSaveFileName(self, "Choose output file", "blast_result.tsv", "TSV Files (*.tsv);;All Files (*)")
        if file:
            self.out_edit.setText(file)
    def start_run(self):
        program = self.prog_combo.currentText()
        db = self.db_edit.text().strip()
        evalue = self.eval_edit.text().strip()
        num_threads = self.threads_edit.text().strip()
        num_hits = self.numhits_edit.text().strip()
        bin_dir = get_blast_bin_dir()
        query_seq = self.query_edit.toPlainText().strip()
        out_file = self.out_edit.text().strip()
        if not db:
            QMessageBox.warning(self, "Input Error", "Please choose a local database.")
            return
        if not evalue:
            QMessageBox.warning(self, "Input Error", "Please enter an E-value threshold.")
            return
        if not num_threads.isdigit() or int(num_threads) < 1:
            QMessageBox.warning(self, "Input Error", "Threads must be a positive integer.")
            return
        if not num_hits.isdigit() or int(num_hits) < 1:
            QMessageBox.warning(self, "Input Error", "Num of Hits must be a positive integer.")
            return
        if not bin_dir or not os.path.isdir(bin_dir):
            QMessageBox.warning(self, "Configuration Error", "BLAST+ bin directory is not configured.")
            return
        if not query_seq or not query_seq.strip().startswith('>'):
            QMessageBox.warning(self, "Invalid Sequence", "Please input a valid FASTA query sequence.")
            return
        if not out_file:
            QMessageBox.warning(self, "Output Error", "Please choose an output file path.")
            return
        self.run_btn.setEnabled(False)
        if self.status_callback:
            self.status_callback("Running BLAST query, please wait...")
        self.thread = RunBlastThread(bin_dir, program, db, evalue, query_seq, out_file, num_threads, num_hits)
        self.thread.finished.connect(self.on_run_finished)
        self.thread.start()
    def on_run_finished(self, success, out_file, msg):
        self.run_btn.setEnabled(True)
        if self.status_callback:
            self.status_callback("")
        if success:
            QMessageBox.information(self, "Success", f"BLAST query finished. Results saved to:\n{out_file}")
            self.accept()
        else:
            QMessageBox.critical(self, "Failed", f"BLAST query failed:\n{msg}") 
