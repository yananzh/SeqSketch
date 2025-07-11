from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog, QProgressBar, QGridLayout)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import os

class SequenceStatisticsWorker(QThread):
    finished = pyqtSignal(str, dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)
    def __init__(self, input_path, output_path):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
    def run(self):
        try:
            # 仅支持FASTA
            ext = os.path.splitext(self.input_path)[1].lower()
            if ext not in ['.fa', '.fasta', '.fas']:
                self.error.emit("仅支持FASTA文件")
                return
            from modules.fasta_processor import FASTAProcessor
            processor = FASTAProcessor()
            if not processor.read_file(self.input_path):
                self.error.emit("无法读取FASTA文件")
                return
            records = processor.records
            # 全局统计
            total = len(records)
            lengths = [r.length for r in records]
            gc_counts = [r.sequence.count('G') + r.sequence.count('C') for r in records]
            n_counts = [r.sequence.count('N') for r in records]
            total_bases = sum(lengths)
            avg_len = total_bases / total if total else 0
            min_len = min(lengths) if lengths else 0
            max_len = max(lengths) if lengths else 0
            total_gc = sum(gc_counts)
            total_n = sum(n_counts)
            gc_content = (total_gc / total_bases * 100) if total_bases else 0
            n_content = (total_n / total_bases * 100) if total_bases else 0
            global_stats = {
                'total': total,
                'avg_len': avg_len,
                'min_len': min_len,
                'max_len': max_len,
                'gc_content': gc_content,
                'n_content': n_content
            }
            # 每条序列统计
            stats_lines = ["Sequence_ID\tLength\tGC_Content(%)\tN_Content(%)"]
            for record in records:
                seq_id = record.header.split()[0]
                L = record.length
                gc = record.sequence.count('G') + record.sequence.count('C')
                n = record.sequence.count('N')
                gc_content = (gc / L * 100) if L else 0
                n_content = (n / L * 100) if L else 0
                stats_lines.append(f"{seq_id}\t{L}\t{gc_content:.2f}\t{n_content:.2f}")
            with open(self.output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(stats_lines))
            self.finished.emit(f"统计完成，结果已保存到: {self.output_path}", global_stats)
        except Exception as e:
            self.error.emit(str(e))

class SequenceStatisticsTab(QWidget):
    def __init__(self):
        super().__init__()
        self._init_ui()
        self.worker = None
    def _init_ui(self):
        layout = QVBoxLayout()
        # 输入区
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("输入FASTA文件:"))
        self.input_edit = QLineEdit()
        input_layout.addWidget(self.input_edit)
        self.input_btn = QPushButton("浏览...")
        self.input_btn.clicked.connect(self.browse_input)
        input_layout.addWidget(self.input_btn)
        layout.addLayout(input_layout)
        # 输出区
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("输出统计结果:"))
        self.output_edit = QLineEdit()
        output_layout.addWidget(self.output_edit)
        self.output_btn = QPushButton("另存为...")
        self.output_btn.clicked.connect(self.browse_output)
        output_layout.addWidget(self.output_btn)
        layout.addLayout(output_layout)
        # 全局统计信息区
        stats_group = QGridLayout()
        self.stat_labels = {}
        stats = [
            ("总序列数", 'total'),
            ("平均长度", 'avg_len'),
            ("最小长度", 'min_len'),
            ("最大长度", 'max_len'),
            ("GC含量(%)", 'gc_content'),
            ("N含量(%)", 'n_content')
        ]
        for i, (label, key) in enumerate(stats):
            l = QLabel(f"{label}: ")
            v = QLabel("-")
            stats_group.addWidget(l, i, 0)
            stats_group.addWidget(v, i, 1)
            self.stat_labels[key] = v
        layout.addLayout(stats_group)
        # 执行区
        run_layout = QHBoxLayout()
        self.run_btn = QPushButton("开始计算")
        self.run_btn.clicked.connect(self.run_statistics)
        run_layout.addWidget(self.run_btn)
        self.progress = QLabel()
        run_layout.addWidget(self.progress)
        layout.addLayout(run_layout)
        # 日志区
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)
        self.setLayout(layout)
    def browse_input(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择FASTA文件", "", "FASTA files (*.fasta *.fa *.fas);;All files (*)")
        if file_path:
            self.input_edit.setText(file_path)
            base = os.path.splitext(os.path.basename(file_path))[0]
            self.output_edit.setText(os.path.join(os.path.dirname(file_path), base + "_stats.tsv"))
    def browse_output(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "保存统计结果", "", "TSV files (*.tsv);;All files (*)")
        if file_path:
            self.output_edit.setText(file_path)
    def run_statistics(self):
        input_path = self.input_edit.text().strip()
        output_path = self.output_edit.text().strip()
        if not input_path or not os.path.isfile(input_path):
            self.log.append("[错误] 输入文件无效")
            return
        if not output_path:
            self.log.append("[错误] 输出文件路径无效")
            return
        self.run_btn.setEnabled(False)
        self.progress.setText("处理中...")
        self.worker = SequenceStatisticsWorker(input_path, output_path)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()
    def on_finished(self, msg, global_stats):
        self.progress.setText("完成")
        self.log.append(msg)
        # 更新全局统计
        for key, label in self.stat_labels.items():
            val = global_stats.get(key, '-')
            if isinstance(val, float):
                label.setText(f"{val:.2f}")
            else:
                label.setText(str(val))
        self.run_btn.setEnabled(True)
    def on_error(self, err):
        self.progress.setText("错误")
        self.log.append(f"[错误] {err}")
        self.run_btn.setEnabled(True) 