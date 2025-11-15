from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QRadioButton, QButtonGroup, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import os
import subprocess
from .blast_config import get_blast_bin_dir, set_blast_bin_dir

class MakeBlastDBThread(QThread):
    finished = pyqtSignal(bool, str)
    def __init__(self, bin_dir, fasta, dbtype, outname):
        super().__init__()
        self.bin_dir = bin_dir
        self.fasta = fasta
        self.dbtype = dbtype
        self.outname = outname
    def run(self):
        exe = os.path.join(self.bin_dir, 'makeblastdb.exe' if os.name=='nt' else 'makeblastdb')
        cmd = [exe, '-in', self.fasta, '-dbtype', self.dbtype, '-out', self.outname, '-title', os.path.basename(self.outname)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode == 0:
                self.finished.emit(True, proc.stdout)
            else:
                self.finished.emit(False, proc.stderr or proc.stdout)
        except Exception as e:
            self.finished.emit(False, str(e))

class BlastMakeDbDialog(QDialog):
    def __init__(self, parent=None, status_callback=None):
        super().__init__(parent)
        self.setWindowTitle("Build Local BLAST Database")
        self.status_callback = status_callback
        self.resize(480, 260)
        layout = QVBoxLayout(self)
        # FASTA文件
        file_layout = QHBoxLayout()
        self.fasta_edit = QLineEdit()
        self.fasta_edit.setReadOnly(True)
        file_btn = QPushButton("Browse...")
        file_btn.clicked.connect(self.choose_fasta)
        file_layout.addWidget(QLabel("Input FASTA file:"))
        file_layout.addWidget(self.fasta_edit)
        file_layout.addWidget(file_btn)
        # 数据库类型
        type_layout = QHBoxLayout()
        self.prot_radio = QRadioButton("Protein (prot)")
        self.nucl_radio = QRadioButton("Nucleotide (nucl)")
        self.prot_radio.setChecked(True)
        self.type_group = QButtonGroup()
        self.type_group.addButton(self.prot_radio)
        self.type_group.addButton(self.nucl_radio)
        type_layout.addWidget(QLabel("Database type:"))
        type_layout.addWidget(self.prot_radio)
        type_layout.addWidget(self.nucl_radio)
        # 输出目录
        outdir_layout = QHBoxLayout()
        self.outdir_edit = QLineEdit()
        self.outdir_edit.setReadOnly(True)
        outdir_btn = QPushButton("Choose Directory")
        outdir_btn.clicked.connect(self.choose_outdir)
        outdir_layout.addWidget(QLabel("Database output directory:"))
        outdir_layout.addWidget(self.outdir_edit)
        outdir_layout.addWidget(outdir_btn)
        # 输出名称
        out_layout = QHBoxLayout()
        self.out_edit = QLineEdit()
        out_layout.addWidget(QLabel("Output database name:"))
        out_layout.addWidget(self.out_edit)
        # 构建按钮
        self.build_btn = QPushButton("Build")
        self.build_btn.clicked.connect(self.start_build)
        # 组装
        layout.addLayout(file_layout)
        layout.addLayout(type_layout)
        layout.addLayout(outdir_layout)
        layout.addLayout(out_layout)
        layout.addWidget(self.build_btn)
        self.setLayout(layout)
        self.thread = None
        self.check_blast_bin()
    def check_blast_bin(self):
        bin_dir = get_blast_bin_dir()
        if not bin_dir or not os.path.isdir(bin_dir):
            while True:
                ret = QMessageBox.question(self, "First Use", "Please specify BLAST+ bin directory (contains makeblastdb, etc.)", QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
                if ret == QMessageBox.StandardButton.Cancel:
                    self.reject()
                    return
                dir_ = QFileDialog.getExistingDirectory(self, "Choose BLAST+ bin directory")
                if dir_ and os.path.isdir(dir_):
                    set_blast_bin_dir(dir_)
                    break
    def choose_fasta(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select FASTA file", "", "FASTA Files (*.fasta *.fa *.faa *.txt);;All Files (*)")
        if file:
            self.fasta_edit.setText(file)
            # 自动建议输出名和目录
            base = os.path.splitext(os.path.basename(file))[0]
            self.out_edit.setText(base + "_db")
            self.outdir_edit.setText(os.path.dirname(file))
    def choose_outdir(self):
        dir_ = QFileDialog.getExistingDirectory(self, "Choose database output directory")
        if dir_:
            self.outdir_edit.setText(dir_)
    def start_build(self):
        fasta = self.fasta_edit.text().strip()
        dbtype = 'prot' if self.prot_radio.isChecked() else 'nucl'
        outname = self.out_edit.text().strip()
        outdir = self.outdir_edit.text().strip()
        bin_dir = get_blast_bin_dir()
        if not fasta or not os.path.isfile(fasta):
            QMessageBox.warning(self, "Input Error", "Please choose a valid FASTA file.")
            return
        if not outname:
            QMessageBox.warning(self, "Input Error", "Please enter an output database name.")
            return
        if not outdir or not os.path.isdir(outdir):
            QMessageBox.warning(self, "Input Error", "Please choose a database output directory.")
            return
        if not bin_dir or not os.path.isdir(bin_dir):
            QMessageBox.warning(self, "Configuration Error", "BLAST+ bin directory is not configured.")
            return
        outpath = os.path.join(outdir, outname)
        self.build_btn.setEnabled(False)
        if self.status_callback:
            self.status_callback("Building database, please wait...")
        self.thread = MakeBlastDBThread(bin_dir, fasta, dbtype, outpath)
        self.thread.finished.connect(self.on_build_finished)
        self.thread.start()
    def on_build_finished(self, success, msg):
        self.build_btn.setEnabled(True)
        if self.status_callback:
            self.status_callback("")
        if success:
            QMessageBox.information(self, "Success", "Database built successfully.\n" + msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Failed", "Database build failed:\n" + msg)
