from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QFileDialog, QPlainTextEdit)
from PyQt6.QtCore import Qt
from utils.common_components import FASTAWorker, BaseTabWidget
import os


class ExtractByIDWorker(FASTAWorker):
    """根据ID提取序列的工作线程"""
    
    def __init__(self, input_path, id_list, output_path):
        super().__init__(input_path, output_path)
        self.id_list = id_list
    
    def run(self):
        if not self.validate_files():
            return
        
        try:
            self.emit_progress("正在加载FASTA文件...")
            processor = self.load_fasta_processor()
            if not processor:
                return
            
            self.emit_progress("正在处理ID列表...")
            id_set = set(i.strip() for i in self.id_list if i.strip())
            if not id_set:
                self.emit_error("ID列表为空")
                return
            
            self.emit_progress("正在匹配序列...")
            matched = []
            for record in processor.records:
                simple_id = record.header.split()[0]
                if simple_id in id_set:
                    matched.append(record)
            
            if not matched:
                self.emit_error("未找到任何匹配的ID")
                return
            
            self.emit_progress("正在保存结果...")
            if not processor.save_file(self.output_path, matched):
                self.emit_error("保存文件失败")
                return
            
            self.emit_finished(f"提取完成，找到{len(matched)}条序列，结果已保存到: {self.output_path}")
        except Exception as e:
            self.emit_error(f"提取过程中发生错误: {e}")


class ExtractByIDTab(BaseTabWidget):
    """根据ID提取序列功能Tab"""
    
    def __init__(self):
        super().__init__("根据ID提取序列", "file")
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
        
        # ID列表输入区
        id_layout = QVBoxLayout()
        id_layout.addWidget(QLabel("要提取的序列ID列表（每行一个）:"))
        self.id_edit = QPlainTextEdit()
        self.id_edit.setPlaceholderText("输入序列ID，每行一个\n例如:\nseq1\nseq2\nseq3")
        self.id_edit.setMaximumHeight(120)
        id_layout.addWidget(self.id_edit)
        
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
        self.add_content_layout(id_layout)
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
            self.output_edit.setText(os.path.join(os.path.dirname(file_path), base + "_extracted.fasta"))
    
    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存提取的序列", "", "FASTA文件 (*.fasta *.fa *.fas);;所有文件 (*)"
        )
        if file_path:
            self.output_edit.setText(file_path)
    
    def clear_all(self):
        self.input_edit.clear()
        self.output_edit.clear()
        self.id_edit.clear()
        self.log_area.clear()
        self.show_status("已清空")
    
    def set_running_state(self, running: bool):
        """重写以禁用相关按钮"""
        super().set_running_state(running)
        self.run_btn.setEnabled(not running)
        self.input_btn.setEnabled(not running)
        self.output_btn.setEnabled(not running)
        self.id_edit.setEnabled(not running)
    
    def run_extract(self):
        input_path = self.input_edit.text().strip()
        output_path = self.output_edit.text().strip()
        id_text = self.id_edit.toPlainText().strip()
        
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
        
        if not id_text:
            self.log_message("请输入要提取的序列ID", "ERROR")
            return
        
        # 处理ID列表
        id_list = [line.strip() for line in id_text.split('\n') if line.strip()]
        if not id_list:
            self.log_message("ID列表为空", "ERROR")
            return
        
        # 启动工作线程
        worker = ExtractByIDWorker(input_path, id_list, output_path)
        self.start_worker(worker)
