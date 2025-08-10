from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QFileDialog, QGridLayout)
from PyQt6.QtCore import Qt, pyqtSignal
from utils.common_components import FASTAWorker, BaseTabWidget
import os


class SequenceStatisticsWorker(FASTAWorker):
    """序列统计分析工作线程"""
    stats_finished = pyqtSignal(dict)  # 统计数据完成信号
    
    def run(self):
        if not self.validate_files():
            return
        
        try:
            self.emit_progress("正在加载FASTA文件...")
            processor = self.load_fasta_processor()
            if not processor:
                return
            
            self.emit_progress("正在计算统计信息...")
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
            
            self.emit_progress("正在生成详细统计...")
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
            
            self.emit_progress("正在保存结果...")
            with open(self.output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(stats_lines))
            
            # 发送全局统计数据和完成消息
            self.stats_finished.emit(global_stats)
            self.emit_finished(f"统计完成，结果已保存到: {self.output_path}")
        except Exception as e:
            self.emit_error(f"统计过程中发生错误: {e}")


class SequenceStatisticsTab(BaseTabWidget):
    """序列统计分析Tab"""
    
    def __init__(self):
        super().__init__("序列统计分析", "file")
        self.init_ui()
        self.connect_signals()
    
    def init_ui(self):
        # 输入文件选择
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("输入FASTA文件:"))
        self.input_edit = QLineEdit()
        self.input_btn = QPushButton("选择文件")
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(self.input_btn)
        
        # 输出文件选择
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("输出统计文件:"))
        self.output_edit = QLineEdit()
        self.output_btn = QPushButton("选择位置")
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        
        # 全局统计信息显示区
        stats_layout = QGridLayout()
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
            row, col = i // 2, (i % 2) * 2
            l = QLabel(f"{label}: ")
            v = QLabel("--")
            v.setStyleSheet("font-weight: bold; color: #2196F3;")
            stats_layout.addWidget(l, row, col)
            stats_layout.addWidget(v, row, col + 1)
            self.stat_labels[key] = v
        
        # 控制按钮
        control_layout = QHBoxLayout()
        self.run_btn = QPushButton("开始统计")
        self.clear_btn = QPushButton("清空")
        control_layout.addWidget(self.run_btn)
        control_layout.addWidget(self.clear_btn)
        control_layout.addStretch()
        
        # 添加到内容区域
        self.add_content_layout(input_layout)
        self.add_content_layout(output_layout)
        self.add_content_layout(stats_layout)
        self.add_content_layout(control_layout)
    
    def connect_signals(self):
        self.input_btn.clicked.connect(self.select_input_file)
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_statistics)
        self.clear_btn.clicked.connect(self.clear_all)
    
    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择FASTA文件", "", "FASTA文件 (*.fasta *.fa *.fas);;所有文件 (*)"
        )
        if file_path:
            self.input_edit.setText(file_path)
            base = os.path.splitext(os.path.basename(file_path))[0]
            self.output_edit.setText(os.path.join(os.path.dirname(file_path), base + "_statistics.txt"))
    
    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存统计结果", "", "文本文件 (*.txt);;所有文件 (*)"
        )
        if file_path:
            self.output_edit.setText(file_path)
    
    def clear_all(self):
        self.input_edit.clear()
        self.output_edit.clear()
        self.log_area.clear()
        for label in self.stat_labels.values():
            label.setText("--")
        self.show_status("已清空")
    
    def set_running_state(self, running: bool):
        """重写以禁用相关按钮"""
        super().set_running_state(running)
        self.run_btn.setEnabled(not running)
        self.input_btn.setEnabled(not running)
        self.output_btn.setEnabled(not running)
    
    def update_statistics(self, stats: dict):
        """更新统计信息显示"""
        self.stat_labels['total'].setText(str(stats.get('total', 0)))
        self.stat_labels['avg_len'].setText(f"{stats.get('avg_len', 0):.1f}")
        self.stat_labels['min_len'].setText(str(stats.get('min_len', 0)))
        self.stat_labels['max_len'].setText(str(stats.get('max_len', 0)))
        self.stat_labels['gc_content'].setText(f"{stats.get('gc_content', 0):.2f}")
        self.stat_labels['n_content'].setText(f"{stats.get('n_content', 0):.2f}")
    
    def run_statistics(self):
        input_path = self.input_edit.text().strip()
        output_path = self.output_edit.text().strip()
        
        # 验证输入
        from utils.common_components import validate_input_path, validate_output_path
        
        valid, error = validate_input_path(input_path, ['.fasta', '.fa', '.fas'])
        if not valid:
            self.log_message(error, "ERROR")
            return
        
        valid, error = validate_output_path(output_path)
        if not valid:
            self.log_message(error, "ERROR")
            return
        
        # 启动工作线程
        worker = SequenceStatisticsWorker(input_path, output_path)
        worker.stats_finished.connect(self.update_statistics)
        self.start_worker(worker)
