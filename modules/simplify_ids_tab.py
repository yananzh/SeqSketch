from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog)
from PyQt6.QtCore import Qt
from utils.common_components import FASTAWorker, BaseTabWidget
import os


class SimplifyIDsWorker(FASTAWorker):
    """简化序列ID的工作线程"""
    
    def run(self):
        if not self.validate_files():
            return
        
        try:
            self.emit_progress("正在加载FASTA文件...")
            processor = self.load_fasta_processor()
            if not processor:
                return
            
            self.emit_progress("正在简化序列ID...")
            for record in processor.records:
                record.header = record.header.split()[0]
                record.description = ""
            
            self.emit_progress("正在保存结果...")
            if not processor.save_file(self.output_path):
                self.emit_error("保存文件失败")
                return
            
            self.emit_finished(f"简化完成，结果已保存到: {self.output_path}")
        except Exception as e:
            self.emit_error(f"处理过程中发生错误: {e}")

class SimplifyIDsTab(BaseTabWidget):
    """简化序列ID功能Tab"""
    
    def __init__(self):
        super().__init__("简化序列ID", "file")
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
        output_layout.addWidget(QLabel("输出文件:"))
        self.output_edit = QLineEdit()
        self.output_btn = QPushButton("选择位置")
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        self.run_btn = QPushButton("开始简化")
        self.clear_btn = QPushButton("清空")
        control_layout.addWidget(self.run_btn)
        control_layout.addWidget(self.clear_btn)
        control_layout.addStretch()
        
        # 添加到内容区域
        self.add_content_layout(input_layout)
        self.add_content_layout(output_layout)
        self.add_content_layout(control_layout)
    
    def connect_signals(self):
        self.input_btn.clicked.connect(self.select_input_file)
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_simplify)
        self.clear_btn.clicked.connect(self.clear_all)
    
    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择FASTA文件", "", "FASTA文件 (*.fasta *.fa *.fas);;所有文件 (*)"
        )
        if file_path:
            self.input_edit.setText(file_path)
            base = os.path.splitext(os.path.basename(file_path))[0]
            self.output_edit.setText(os.path.join(os.path.dirname(file_path), base + "_simplified.fasta"))
    
    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存简化后的文件", "", "FASTA文件 (*.fasta *.fa *.fas);;所有文件 (*)"
        )
        if file_path:
            self.output_edit.setText(file_path)
    
    def clear_all(self):
        self.input_edit.clear()
        self.output_edit.clear()
        self.log_area.clear()
        self.show_status("已清空")
    
    def set_running_state(self, running: bool):
        """重写以禁用相关按钮"""
        super().set_running_state(running)
        self.run_btn.setEnabled(not running)
        self.input_btn.setEnabled(not running)
        self.output_btn.setEnabled(not running)
    
    def run_simplify(self):
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
        worker = SimplifyIDsWorker(input_path, output_path)
        self.start_worker(worker)
    
    def show_help(self):
        """显示帮助信息"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QScrollArea
        from PyQt6.QtCore import Qt
        
        help_text = """
<h3>序列ID简化工具</h3>
<p><b>功能说明：</b></p>
<p>简化FASTA文件中复杂的序列ID，只保留第一个词作为序列标识符。</p>

<p><b>处理效果：</b></p>
<ul>
<li><b>原始ID：</b>gi|123456|ref|NM_001101.5| hypothetical protein [Homo sapiens]</li>
<li><b>简化后：</b>gi|123456|ref|NM_001101.5|</li>
</ul>

<p><b>使用方法：</b></p>
<ol>
<li>选择要处理的FASTA文件</li>
<li>指定输出文件的保存位置</li>
<li>点击"开始简化"按钮</li>
</ol>

<p><b>应用场景：</b></p>
<ul>
<li>清理从数据库下载的复杂序列ID</li>
<li>为后续分析准备简洁的序列标识符</li>
<li>减少文件大小，提高处理效率</li>
</ul>

<p><b>注意事项：</b></p>
<p>简化过程会移除序列描述信息，请确保简化后的ID仍能唯一标识序列。</p>
        """
        
        # 创建自定义对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("帮助 - 序列ID简化")
        dialog.setFixedSize(780, 470)
        
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
        ok_button = QPushButton("确定")
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)
        
        dialog.setLayout(layout)
        dialog.exec() 