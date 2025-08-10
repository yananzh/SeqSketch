"""
改进的基础Tab类，提供统一的错误处理和UI模式
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
                            QPushButton, QLabel, QProgressBar, QMessageBox,
                            QFileDialog, QApplication)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import logging

class BaseAnalysisTab(QWidget):
    """基础分析Tab类，提供通用功能"""
    
    def __init__(self, title: str = "分析工具"):
        super().__init__()
        self.title = title
        self.logger = logging.getLogger(self.__class__.__name__)
        self.worker_thread = None
        self.init_ui()
        self.connect_signals()
    
    def init_ui(self):
        """初始化UI - 子类可重写"""
        layout = QVBoxLayout(self)
        
        # 输入区域
        self.input_label = QLabel("输入数据:")
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("请输入数据或拖拽文件到此处...")
        
        # 控制按钮
        button_layout = QHBoxLayout()
        self.upload_btn = QPushButton("选择文件")
        self.run_btn = QPushButton("开始分析")
        self.clear_btn = QPushButton("清空")
        self.export_btn = QPushButton("导出结果")
        
        button_layout.addWidget(self.upload_btn)
        button_layout.addWidget(self.run_btn)
        button_layout.addWidget(self.clear_btn)
        button_layout.addWidget(self.export_btn)
        button_layout.addStretch()
        
        # 输出区域
        self.output_label = QLabel("分析结果:")
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        
        # 进度条和状态
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_label = QLabel("就绪")
        
        # 布局
        layout.addWidget(self.input_label)
        layout.addWidget(self.input_text)
        layout.addLayout(button_layout)
        layout.addWidget(self.output_label)
        layout.addWidget(self.output_text)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
    
    def connect_signals(self):
        """连接信号 - 子类可重写"""
        self.upload_btn.clicked.connect(self.select_file)
        self.run_btn.clicked.connect(self.start_analysis)
        self.clear_btn.clicked.connect(self.clear_all)
        self.export_btn.clicked.connect(self.export_results)
    
    def select_file(self):
        """选择文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择输入文件", "", 
            "FASTA文件 (*.fasta *.fa *.fas);;所有文件 (*)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.input_text.setPlainText(content)
                self.show_status(f"已加载文件: {file_path}")
            except Exception as e:
                self.handle_error(f"文件加载失败: {e}")
    
    def start_analysis(self):
        """开始分析 - 子类必须重写"""
        raise NotImplementedError("子类必须实现start_analysis方法")
    
    def clear_all(self):
        """清空所有内容"""
        self.input_text.clear()
        self.output_text.clear()
        self.show_status("已清空")
    
    def export_results(self):
        """导出结果"""
        content = self.output_text.toPlainText()
        if not content.strip():
            self.show_warning("没有可导出的结果")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存结果", "", 
            "文本文件 (*.txt);;所有文件 (*)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.show_status(f"结果已保存到: {file_path}")
            except Exception as e:
                self.handle_error(f"保存失败: {e}")
    
    def show_progress(self, visible: bool = True):
        """显示/隐藏进度条"""
        self.progress_bar.setVisible(visible)
        if visible:
            self.progress_bar.setRange(0, 0)  # 不确定进度
    
    def show_status(self, message: str):
        """显示状态信息"""
        self.status_label.setText(message)
        self.logger.info(message)
    
    def show_warning(self, message: str):
        """显示警告"""
        QMessageBox.warning(self, "警告", message)
        self.logger.warning(message)
    
    def handle_error(self, error_msg: str, exception: Exception | None = None):
        """统一错误处理"""
        self.show_progress(False)
        self.show_status("分析失败")
        
        if exception:
            self.logger.exception(f"错误: {error_msg}")
        else:
            self.logger.error(error_msg)
        
        QMessageBox.critical(self, "错误", error_msg)
    
    def set_running_state(self, running: bool):
        """设置运行状态"""
        self.run_btn.setEnabled(not running)
        self.upload_btn.setEnabled(not running)
        self.show_progress(running)
        
        if running:
            self.show_status("分析中...")
        else:
            self.show_status("分析完成")


class BaseWorker(QThread):
    """基础工作线程类"""
    
    finished = pyqtSignal(str)  # 完成信号
    error = pyqtSignal(str)     # 错误信号
    progress = pyqtSignal(str)  # 进度信号
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def run(self):
        """子类必须重写此方法"""
        raise NotImplementedError("子类必须实现run方法")
    
    def emit_progress(self, message: str):
        """发送进度信息"""
        self.progress.emit(message)
        self.logger.info(f"进度: {message}")
    
    def emit_error(self, error_msg: str, exception: Exception | None = None):
        """发送错误信息"""
        if exception:
            self.logger.exception(f"工作线程错误: {error_msg}")
        else:
            self.logger.error(error_msg)
        self.error.emit(error_msg)
    
    def emit_finished(self, result_msg: str):
        """发送完成信息"""
        self.logger.info(f"任务完成: {result_msg}")
        self.finished.emit(result_msg)
