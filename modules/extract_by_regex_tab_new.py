from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QFileDialog)
from PyQt6.QtCore import Qt
from utils.common_components import FASTAWorker, BaseTabWidget
import os
import re


class ExtractByRegexWorker(FASTAWorker):
    """根据正则表达式提取序列的工作线程"""
    
    def __init__(self, input_path, regex, output_path):
        super().__init__(input_path, output_path)
        self.regex = regex
    
    def run(self):
        if not self.validate_files():
            return
        
        try:
            self.emit_progress("正在加载FASTA文件...")
            processor = self.load_fasta_processor()
            if not processor:
                return
            
            self.emit_progress("正在验证正则表达式...")
            try:
                pattern = re.compile(self.regex)
            except Exception as e:
                self.emit_error(f"正则表达式无效: {e}")
                return
            
            self.emit_progress("正在匹配序列...")
            matched = []
            for record in processor.records:
                # 用完整ID行（不含>）匹配
                if pattern.search(record.header):
                    matched.append(record)
            
            if not matched:
                self.emit_error("未匹配到任何序列")
                return
            
            self.emit_progress("正在保存结果...")
            if not processor.save_file(self.output_path, matched):
                self.emit_error("保存文件失败")
                return
            
            self.emit_finished(f"提取完成，找到{len(matched)}条序列，结果已保存到: {self.output_path}")
        except Exception as e:
            self.emit_error(f"提取过程中发生错误: {e}")


class ExtractByRegexTab(BaseTabWidget):
    """根据正则表达式提取序列功能Tab"""
    
    def __init__(self):
        super().__init__("根据正则表达式提取序列", "file")
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
        
        # 正则表达式输入
        regex_layout = QHBoxLayout()
        regex_layout.addWidget(QLabel("正则表达式:"))
        self.regex_edit = QLineEdit()
        self.regex_edit.setPlaceholderText("例如: gene.*protein, ^chr[0-9]+, .*hypothetical.*")
        regex_layout.addWidget(self.regex_edit)
        
        # 输出文件选择
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("输出文件:"))
        self.output_edit = QLineEdit()
        self.output_btn = QPushButton("选择位置")
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        self.run_btn = QPushButton("开始提取")
        self.clear_btn = QPushButton("清空")
        control_layout.addWidget(self.run_btn)
        control_layout.addWidget(self.clear_btn)
        control_layout.addStretch()
        
        # 添加到内容区域
        self.add_content_layout(input_layout)
        self.add_content_layout(regex_layout)
        self.add_content_layout(output_layout)
        self.add_content_layout(control_layout)
    
    def connect_signals(self):
        self.input_btn.clicked.connect(self.select_input_file)
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_extract)
        self.clear_btn.clicked.connect(self.clear_all)
    
    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择FASTA文件", "", "FASTA文件 (*.fasta *.fa *.fas);;所有文件 (*)"
        )
        if file_path:
            self.input_edit.setText(file_path)
            base = os.path.splitext(os.path.basename(file_path))[0]
            self.output_edit.setText(os.path.join(os.path.dirname(file_path), base + "_regex_extracted.fasta"))
    
    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存提取的序列", "", "FASTA文件 (*.fasta *.fa *.fas);;所有文件 (*)"
        )
        if file_path:
            self.output_edit.setText(file_path)
    
    def clear_all(self):
        self.input_edit.clear()
        self.output_edit.clear()
        self.regex_edit.clear()
        self.log_area.clear()
        self.show_status("已清空")
    
    def set_running_state(self, running: bool):
        """重写以禁用相关按钮"""
        super().set_running_state(running)
        self.run_btn.setEnabled(not running)
        self.input_btn.setEnabled(not running)
        self.output_btn.setEnabled(not running)
        self.regex_edit.setEnabled(not running)
    
    def run_extract(self):
        input_path = self.input_edit.text().strip()
        output_path = self.output_edit.text().strip()
        regex = self.regex_edit.text().strip()
        
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
        
        if not regex:
            self.log_message("请输入正则表达式", "ERROR")
            return
        
        # 启动工作线程
        worker = ExtractByRegexWorker(input_path, regex, output_path)
        self.start_worker(worker)
