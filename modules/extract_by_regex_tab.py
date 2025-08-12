from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QFileDialog)
from PyQt6.QtCore import Qt
from utils.common_components import FASTAWorker, BaseTabWidget
import translations
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
        input_layout.addWidget(QLabel(translations.tr("输入FASTA文件:")))
        self.input_edit = QLineEdit()
        self.input_btn = QPushButton(translations.tr("选择文件"))
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(self.input_btn)
        
        # 正则表达式输入
        regex_layout = QHBoxLayout()
        regex_layout.addWidget(QLabel(translations.tr("正则表达式:")))
        self.regex_edit = QLineEdit()
        self.regex_edit.setPlaceholderText(translations.tr("例如: gene.*protein, ^chr[0-9]+, .*hypothetical.*"))
        regex_layout.addWidget(self.regex_edit)
        
        # 输出文件选择
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel(translations.tr("输出文件:")))
        self.output_edit = QLineEdit()
        self.output_btn = QPushButton(translations.tr("选择位置"))
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        self.run_btn = QPushButton(translations.tr("开始提取"))
        self.clear_btn = QPushButton(translations.tr("清空"))
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
        self.show_status(translations.tr("已清空"))
    
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
    
    def show_help(self):
        """显示帮助信息"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QScrollArea
        from PyQt6.QtCore import Qt
        
        help_text = """
<h3>正则表达式提取序列工具</h3>
<p><b>功能说明：</b></p>
<p>使用正则表达式模式匹配序列ID，从FASTA文件中提取符合条件的序列。</p>

<p><b>使用方法：</b></p>
<ol>
<li>选择源FASTA文件</li>
<li>指定提取结果的保存位置</li>
<li>输入正则表达式模式</li>
<li>点击"开始提取"按钮</li>
</ol>

<p><b>正则表达式示例：</b></p>
<ul>
<li><code>^NM_.*</code> - 匹配以"NM_"开头的序列ID</li>
<li><code>.*gene.*</code> - 匹配包含"gene"的序列ID</li>
<li><code>seq_\\d+</code> - 匹配"seq_"后跟数字的序列ID</li>
<li><code>(protein|enzyme)</code> - 匹配包含"protein"或"enzyme"的序列ID</li>
<li><code>^[A-Z]{2}_\\d{6}$</code> - 匹配格式为"XX_123456"的序列ID</li>
</ul>

<p><b>常用正则符号：</b></p>
<ul>
<li><code>^</code> - 字符串开始</li>
<li><code>$</code> - 字符串结束</li>
<li><code>.*</code> - 匹配任意字符（贪婪模式）</li>
<li><code>\\d</code> - 匹配数字</li>
<li><code>\\w</code> - 匹配字母、数字、下划线</li>
<li><code>[A-Z]</code> - 匹配大写字母</li>
<li><code>+</code> - 匹配前面字符一次或多次</li>
<li><code>|</code> - 或运算符</li>
</ul>

<p><b>应用场景：</b></p>
<ul>
<li>按基因命名规律提取特定类型序列</li>
<li>筛选符合特定格式的序列ID</li>
<li>灵活的模式匹配和序列分组</li>
</ul>

<p><b>注意事项：</b></p>
<p>正则表达式区分大小写，请确保模式表达式的正确性。</p>
        """
        
        # 创建自定义对话框
        dialog = QDialog(self)
        dialog.setWindowTitle(translations.tr("帮助 - 正则表达式提取序列"))
        dialog.setFixedSize(820, 550)
        
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
            self.run_btn.setText(translations.tr("开始提取"))
        if hasattr(self, 'clear_btn'):
            self.clear_btn.setText(translations.tr("清空"))
        
        # Update labels
        for widget in self.findChildren(QLabel):
            text = widget.text()
            if "输入FASTA文件:" in text or "Input FASTA File:" in text:
                widget.setText(translations.tr("输入FASTA文件:"))
            elif "正则表达式:" in text or "Regular Expression:" in text:
                widget.setText(translations.tr("正则表达式:"))
            elif "输出文件:" in text or "Output File:" in text:
                widget.setText(translations.tr("输出文件:"))
            elif "状态:" in text or "Status:" in text:
                widget.setText(translations.tr("状态:"))
        
        # Update placeholder text
        if hasattr(self, 'regex_edit'):
            self.regex_edit.setPlaceholderText(translations.tr("例如: gene.*protein, ^chr[0-9]+, .*hypothetical.*"))
            
        # Call base class update_language for common elements
        super().update_language()
