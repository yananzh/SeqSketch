from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QRadioButton, QButtonGroup, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import translations
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
        self.setWindowTitle(translations.tr("构建本地BLAST数据库"))
        self.status_callback = status_callback
        self.resize(480, 260)
        layout = QVBoxLayout(self)
        # FASTA文件
        file_layout = QHBoxLayout()
        self.fasta_edit = QLineEdit()
        self.fasta_edit.setReadOnly(True)
        file_btn = QPushButton(translations.tr("浏览..."))
        file_btn.clicked.connect(self.choose_fasta)
        file_layout.addWidget(QLabel(translations.tr("输入FASTA文件:")))
        file_layout.addWidget(self.fasta_edit)
        file_layout.addWidget(file_btn)
        # 数据库类型
        type_layout = QHBoxLayout()
        self.prot_radio = QRadioButton(translations.tr("蛋白质 (prot)"))
        self.nucl_radio = QRadioButton(translations.tr("核苷酸 (nucl)"))
        self.prot_radio.setChecked(True)
        self.type_group = QButtonGroup()
        self.type_group.addButton(self.prot_radio)
        self.type_group.addButton(self.nucl_radio)
        type_layout.addWidget(QLabel(translations.tr("数据库类型:")))
        type_layout.addWidget(self.prot_radio)
        type_layout.addWidget(self.nucl_radio)
        # 输出目录
        outdir_layout = QHBoxLayout()
        self.outdir_edit = QLineEdit()
        self.outdir_edit.setReadOnly(True)
        outdir_btn = QPushButton(translations.tr("选择目录"))
        outdir_btn.clicked.connect(self.choose_outdir)
        outdir_layout.addWidget(QLabel(translations.tr("数据库储存位置:")))
        outdir_layout.addWidget(self.outdir_edit)
        outdir_layout.addWidget(outdir_btn)
        # 输出名称
        out_layout = QHBoxLayout()
        self.out_edit = QLineEdit()
        out_layout.addWidget(QLabel(translations.tr("输出数据库名称:")))
        out_layout.addWidget(self.out_edit)
        # 构建按钮
        self.build_btn = QPushButton(translations.tr("开始构建"))
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
                ret = QMessageBox.question(self, translations.tr("首次使用"), translations.tr("首次使用，请指定BLAST+的bin目录（包含makeblastdb等）"), QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
                if ret == QMessageBox.StandardButton.Cancel:
                    self.reject()
                    return
                dir_ = QFileDialog.getExistingDirectory(self, translations.tr("选择BLAST+ bin目录"))
                if dir_ and os.path.isdir(dir_):
                    set_blast_bin_dir(dir_)
                    break
    def choose_fasta(self):
        file, _ = QFileDialog.getOpenFileName(self, translations.tr("选择FASTA文件"), "", "FASTA文件 (*.fasta *.fa *.faa *.txt);;所有文件 (*)")
        if file:
            self.fasta_edit.setText(file)
            # 自动建议输出名和目录
            base = os.path.splitext(os.path.basename(file))[0]
            self.out_edit.setText(base + "_db")
            self.outdir_edit.setText(os.path.dirname(file))
    def choose_outdir(self):
        dir_ = QFileDialog.getExistingDirectory(self, translations.tr("选择数据库储存位置"))
        if dir_:
            self.outdir_edit.setText(dir_)
    def start_build(self):
        fasta = self.fasta_edit.text().strip()
        dbtype = 'prot' if self.prot_radio.isChecked() else 'nucl'
        outname = self.out_edit.text().strip()
        outdir = self.outdir_edit.text().strip()
        bin_dir = get_blast_bin_dir()
        if not fasta or not os.path.isfile(fasta):
            QMessageBox.warning(self, translations.tr("输入错误"), translations.tr("请选择有效的FASTA文件！"))
            return
        if not outname:
            QMessageBox.warning(self, translations.tr("输入错误"), translations.tr("请填写输出数据库名称！"))
            return
        if not outdir or not os.path.isdir(outdir):
            QMessageBox.warning(self, translations.tr("输入错误"), translations.tr("请选择数据库储存位置！"))
            return
        if not bin_dir or not os.path.isdir(bin_dir):
            QMessageBox.warning(self, translations.tr("配置错误"), translations.tr("BLAST+ bin目录未配置！"))
            return
        outpath = os.path.join(outdir, outname)
        self.build_btn.setEnabled(False)
        if self.status_callback:
            self.status_callback(translations.tr("正在构建数据库，请稍候..."))
        self.thread = MakeBlastDBThread(bin_dir, fasta, dbtype, outpath)
        self.thread.finished.connect(self.on_build_finished)
        self.thread.start()
    def on_build_finished(self, success, msg):
        self.build_btn.setEnabled(True)
        if self.status_callback:
            self.status_callback("")
        if success:
            QMessageBox.information(self, translations.tr("成功"), translations.tr("数据库构建成功！\n") + msg)
            self.accept()
        else:
            QMessageBox.critical(self, translations.tr("失败"), translations.tr("数据库构建失败：\n") + msg) 