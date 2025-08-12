from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QFileDialog, QGridLayout)
from PyQt6.QtCore import Qt, pyqtSignal
from utils.common_components import FASTAWorker, BaseTabWidget
import translations
import os


class SequenceStatisticsWorker(FASTAWorker):
    """序列长度统计分析工作线程"""
    stats_finished = pyqtSignal(dict)  # 统计数据完成信号
    
    def is_dna_sequence(self, sequence):
        """判断序列是否为DNA序列"""
        # 计算DNA碱基比例
        dna_bases = set('ATGCN')
        total_chars = len(sequence)
        dna_chars = sum(1 for char in sequence.upper() if char in dna_bases)
        return (dna_chars / total_chars) > 0.9 if total_chars > 0 else False
    
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
            total_length = sum(lengths)
            min_len = min(lengths) if lengths else 0
            max_len = max(lengths) if lengths else 0
            
            global_stats = {
                'total': total,
                'total_length': total_length,
                'min_len': min_len,
                'max_len': max_len
            }
            
            self.emit_progress("正在生成详细统计...")
            # 每条序列统计
            stats_lines = ["Sequence_ID\tLength\tGC_Content(%)"]
            for record in records:
                seq_id = record.header.split()[0]
                L = record.length
                
                # 只对DNA序列计算GC含量
                if self.is_dna_sequence(record.sequence):
                    gc = record.sequence.count('G') + record.sequence.count('C')
                    gc_content = (gc / L * 100) if L else 0
                    stats_lines.append(f"{seq_id}\t{L}\t{gc_content:.2f}")
                else:
                    stats_lines.append(f"{seq_id}\t{L}\tN/A")
            
            self.emit_progress("正在保存结果...")
            with open(self.output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(stats_lines))
            
            # 发送全局统计数据和完成消息
            self.stats_finished.emit(global_stats)
            self.emit_finished(f"统计完成，结果已保存到: {self.output_path}")
        except Exception as e:
            self.emit_error(f"统计过程中发生错误: {e}")


class SequenceStatisticsTab(BaseTabWidget):
    """序列长度统计分析Tab"""
    
    def __init__(self):
        super().__init__("序列长度统计分析", "file")
        self.init_ui()
        self.connect_signals()
    
    def init_ui(self):
        # 输入文件选择
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel(translations.tr("输入FASTA文件:")))
        self.input_edit = QLineEdit()
        self.input_btn = QPushButton(translations.tr("选择文件"))
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(self.input_btn)
        
        # 输出文件选择
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel(translations.tr("输出统计文件:")))
        self.output_edit = QLineEdit()
        self.output_btn = QPushButton(translations.tr("选择位置"))
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        
        # 全局统计信息显示区
        stats_layout = QGridLayout()
        self.stat_labels = {}
        stats = [
            (translations.tr("总序列数"), 'total'),
            (translations.tr("总长度"), 'total_length'),
            (translations.tr("最小长度"), 'min_len'),
            (translations.tr("最大长度"), 'max_len')
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
        self.run_btn = QPushButton(translations.tr("开始统计"))
        self.clear_btn = QPushButton(translations.tr("清空"))
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
        self.show_status(translations.tr("已清空"))
    
    def set_running_state(self, running: bool):
        """重写以禁用相关按钮"""
        super().set_running_state(running)
        self.run_btn.setEnabled(not running)
        self.input_btn.setEnabled(not running)
        self.output_btn.setEnabled(not running)
    
    def update_statistics(self, stats: dict):
        """更新统计信息显示"""
        self.stat_labels['total'].setText(str(stats.get('total', 0)))
        self.stat_labels['total_length'].setText(str(stats.get('total_length', 0)))
        self.stat_labels['min_len'].setText(str(stats.get('min_len', 0)))
        self.stat_labels['max_len'].setText(str(stats.get('max_len', 0)))
    
    def show_help(self):
        """显示帮助信息"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QScrollArea
        from PyQt6.QtCore import Qt
        
        help_text = """
<h3>序列长度统计分析工具</h3>
<p><b>功能说明：</b></p>
<p>对FASTA文件中的序列进行长度统计分析，生成详细的统计报告。</p>

<p><b>主要功能：</b></p>
<ul>
<li><b>全局统计：</b>计算总序列数、总长度、最小/最大长度</li>
<li><b>详细报告：</b>为每条序列生成长度统计，对DNA序列计算GC含量</li>
</ul>

<p><b>使用方法：</b></p>
<ol>
<li>选择输入的FASTA文件（支持.fasta/.fa/.fas格式）</li>
<li>指定输出统计文件的保存位置</li>
<li>点击"开始统计"按钮</li>
<li>查看实时统计结果和详细日志</li>
</ol>

<p><b>输出格式：</b></p>
<p>生成TSV格式的统计文件，包含每条序列的ID、长度，对于DNA序列还包含GC含量(%)。</p>
        """
        
        # 创建自定义对话框
        dialog = QDialog(self)
        dialog.setWindowTitle(translations.tr("帮助 - 序列长度统计分析"))
        dialog.setFixedSize(750, 450)
        
        layout = QVBoxLayout()
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 创建文本标签
        label = QLabel(help_text)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(False)  # 禁用自动换行
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        label.setMargin(20)
        
        scroll_area.setWidget(label)
        layout.addWidget(scroll_area)
        
        # 添加确定按钮
        ok_button = QPushButton(translations.tr("确定"))
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)
        
        dialog.setLayout(layout)
        dialog.exec()
    
    def update_language(self):
        """Update UI elements when language changes"""
        # Update button texts
        if hasattr(self, 'input_btn'):
            self.input_btn.setText(translations.tr("选择文件"))
        if hasattr(self, 'output_btn'):
            self.output_btn.setText(translations.tr("选择位置"))
        if hasattr(self, 'run_btn'):
            self.run_btn.setText(translations.tr("开始统计"))
        if hasattr(self, 'clear_btn'):
            self.clear_btn.setText(translations.tr("清空"))
        if hasattr(self, 'help_btn'):
            self.help_btn.setText(translations.tr("帮助"))
            
        # Update labels - find all QLabel widgets and update their text
        for widget in self.findChildren(QLabel):
            text = widget.text()
            # Update specific labels by checking their current text
            if "输入FASTA文件:" in text or "Input FASTA File:" in text:
                widget.setText(translations.tr("输入FASTA文件:"))
            elif "输出统计文件:" in text or "Output Statistics File:" in text:
                widget.setText(translations.tr("输出统计文件:"))
            elif "状态:" in text or "Status:" in text:
                widget.setText(translations.tr("状态:"))
            elif text in ["总序列数:", "Total Sequences:", "总长度:", "Total Length:", "最小长度:", "Min Length:", "最大长度:", "Max Length:"]:
                # Handle statistics labels
                if "总序列数" in text or "Total Sequences" in text:
                    widget.setText(translations.tr("总序列数") + ": ")
                elif "总长度" in text or "Total Length" in text:
                    widget.setText(translations.tr("总长度") + ": ")
                elif "最小长度" in text or "Min Length" in text:
                    widget.setText(translations.tr("最小长度") + ": ")
                elif "最大长度" in text or "Max Length" in text:
                    widget.setText(translations.tr("最大长度") + ": ")
        
        # Update status label
        if hasattr(self, 'status_label') and self.status_label.text() in ["就绪", "Ready"]:
            self.status_label.setText(translations.tr("就绪"))
            
        # Update log area placeholder if exists
        if hasattr(self, 'log_area'):
            self.log_area.setPlaceholderText(translations.tr("操作日志将显示在此处..."))
    
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
