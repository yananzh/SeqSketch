from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QFileDialog, QCheckBox)
from PyQt6.QtCore import Qt
from utils.common_components import FASTAWorker, BaseTabWidget
import os


class BatchRenameIDsWorker(FASTAWorker):
    """批量重命名序列ID的工作线程"""
    
    def __init__(self, fasta_path, mapping_path, has_header, output_path):
        super().__init__(fasta_path, output_path)
        self.mapping_path = mapping_path
        self.has_header = has_header
    
    def run(self):
        if not self.validate_files():
            return
        
        try:
            self.emit_progress("正在读取映射文件...")
            
            # 验证映射文件
            if not os.path.exists(self.mapping_path):
                self.emit_error("映射文件不存在")
                return
            
            # 读取映射文件
            try:
                import pandas as pd
                ext = os.path.splitext(self.mapping_path)[1].lower()
                if ext in ['.xls', '.xlsx']:
                    df = pd.read_excel(self.mapping_path, header=0 if self.has_header else None)
                elif ext in ['.csv']:
                    df = pd.read_csv(self.mapping_path, header=0 if self.has_header else None)
                elif ext in ['.tsv', '.txt']:
                    df = pd.read_csv(self.mapping_path, sep='\t', header=0 if self.has_header else None)
                else:
                    self.emit_error("不支持的映射文件格式，请使用Excel、CSV或TSV文件")
                    return
            except ImportError:
                self.emit_error("需要安装pandas库来处理映射文件")
                return
            except Exception as e:
                self.emit_error(f"读取映射文件失败: {e}")
                return
            
            if df.shape[1] < 2:
                self.emit_error("映射文件至少应有两列（旧ID，新ID）")
                return
            
            mapping = dict(zip(df.iloc[:, 0].astype(str), df.iloc[:, 1].astype(str)))
            self.emit_progress(f"读取到{len(mapping)}个ID映射关系")
            
            self.emit_progress("正在加载FASTA文件...")
            processor = self.load_fasta_processor()
            if not processor:
                return
            
            self.emit_progress("正在重命名序列ID...")
            total = len(processor.records)
            renamed_count = 0
            
            for record in processor.records:
                old_id = record.header.split()[0]
                if old_id in mapping:
                    new_id = mapping[old_id]
                    # 保留原有描述信息
                    parts = record.header.split(' ', 1)
                    if len(parts) > 1:
                        record.header = f"{new_id} {parts[1]}"
                    else:
                        record.header = new_id
                    renamed_count += 1
            
            self.emit_progress("正在保存结果...")
            if not processor.save_file(self.output_path):
                self.emit_error("保存文件失败")
                return
            
            self.emit_finished(f"重命名完成，共处理{total}条序列，成功重命名{renamed_count}条，结果已保存到: {self.output_path}")
        except Exception as e:
            self.emit_error(f"重命名过程中发生错误: {e}")


class BatchRenameIDsTab(BaseTabWidget):
    """批量重命名序列ID功能Tab"""
    
    def __init__(self):
        super().__init__("批量重命名序列ID", "file")
        self.init_ui()
        self.connect_signals()
    
    def init_ui(self):
        # 输入FASTA文件选择
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("输入FASTA文件:"))
        self.input_edit = QLineEdit()
        self.input_btn = QPushButton("选择文件")
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(self.input_btn)
        
        # 映射文件选择
        mapping_layout = QHBoxLayout()
        mapping_layout.addWidget(QLabel("ID映射文件:"))
        self.mapping_edit = QLineEdit()
        self.mapping_btn = QPushButton("选择映射文件")
        mapping_layout.addWidget(self.mapping_edit)
        mapping_layout.addWidget(self.mapping_btn)
        
        # 映射文件选项
        option_layout = QHBoxLayout()
        self.header_checkbox = QCheckBox("映射文件包含标题行")
        self.header_checkbox.setChecked(True)
        option_layout.addWidget(self.header_checkbox)
        option_layout.addStretch()
        
        # 输出文件选择
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("输出文件:"))
        self.output_edit = QLineEdit()
        self.output_btn = QPushButton("选择位置")
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        self.run_btn = QPushButton("开始重命名")
        self.clear_btn = QPushButton("清空")
        control_layout.addWidget(self.run_btn)
        control_layout.addWidget(self.clear_btn)
        control_layout.addStretch()
        
        # 添加到内容区域
        self.add_content_layout(input_layout)
        self.add_content_layout(mapping_layout)
        self.add_content_layout(option_layout)
        self.add_content_layout(output_layout)
        self.add_content_layout(control_layout)
    
    def connect_signals(self):
        self.input_btn.clicked.connect(self.select_input_file)
        self.mapping_btn.clicked.connect(self.select_mapping_file)
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_rename)
        self.clear_btn.clicked.connect(self.clear_all)
    
    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择FASTA文件", "", "FASTA文件 (*.fasta *.fa *.fas);;所有文件 (*)"
        )
        if file_path:
            self.input_edit.setText(file_path)
            base = os.path.splitext(os.path.basename(file_path))[0]
            self.output_edit.setText(os.path.join(os.path.dirname(file_path), base + "_renamed.fasta"))
    
    def select_mapping_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择ID映射文件", "", 
            "Excel文件 (*.xlsx *.xls);;CSV文件 (*.csv);;TSV文件 (*.tsv *.txt);;所有文件 (*)"
        )
        if file_path:
            self.mapping_edit.setText(file_path)
    
    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存重命名后的文件", "", "FASTA文件 (*.fasta *.fa *.fas);;所有文件 (*)"
        )
        if file_path:
            self.output_edit.setText(file_path)
    
    def clear_all(self):
        self.input_edit.clear()
        self.mapping_edit.clear()
        self.output_edit.clear()
        self.log_area.clear()
        self.header_checkbox.setChecked(True)
        self.show_status("已清空")
    
    def set_running_state(self, running: bool):
        """重写以禁用相关按钮"""
        super().set_running_state(running)
        self.run_btn.setEnabled(not running)
        self.input_btn.setEnabled(not running)
        self.mapping_btn.setEnabled(not running)
        self.output_btn.setEnabled(not running)
        self.header_checkbox.setEnabled(not running)
    
    def run_rename(self):
        input_path = self.input_edit.text().strip()
        mapping_path = self.mapping_edit.text().strip()
        output_path = self.output_edit.text().strip()
        has_header = self.header_checkbox.isChecked()
        
        # 验证输入
        from utils.common_components import validate_input_path, validate_output_path
        
        valid, error = validate_input_path(input_path, ['.fasta', '.fa', '.fas'])
        if not valid:
            self.log_message(error, "ERROR")
            return
        
        if not mapping_path or not os.path.exists(mapping_path):
            self.log_message("请选择有效的映射文件", "ERROR")
            return
        
        valid, error = validate_output_path(output_path)
        if not valid:
            self.log_message(error, "ERROR")
            return
        
        # 启动工作线程
        worker = BatchRenameIDsWorker(input_path, mapping_path, has_header, output_path)
        self.start_worker(worker)
