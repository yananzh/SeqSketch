"""
通用工作线程基类和常用组件
减少代码重复，提供统一的错误处理和信号机制
"""
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                           QTextEdit, QFileDialog, QMessageBox)
from typing import Any, Dict, Optional
import logging
import os


class BaseWorker(QObject):
    """
    通用工作线程基类
    所有后台任务继承此类，减少重复代码
    """
    finished = pyqtSignal(str)  # 完成信号，传递结果消息
    error = pyqtSignal(str)     # 错误信号，传递错误消息
    progress = pyqtSignal(str)  # 进度信号，传递进度信息
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def emit_progress(self, message: str):
        """发送进度信息"""
        self.progress.emit(message)
        self.logger.info(f"进度: {message}")
    
    def emit_error(self, error_msg: str, exception: Optional[Exception] = None):
        """发送错误信息"""
        if exception:
            self.logger.exception(f"错误: {error_msg}")
        else:
            self.logger.error(error_msg)
        self.error.emit(error_msg)
    
    def emit_finished(self, result_msg: str):
        """发送完成信息"""
        self.logger.info(f"任务完成: {result_msg}")
        self.finished.emit(result_msg)
    
    def run(self):
        """子类必须重写此方法"""
        raise NotImplementedError("子类必须实现run方法")


class DataWorker(BaseWorker):
    """
    数据处理工作线程基类
    用于返回处理结果数据的任务
    """
    data_finished = pyqtSignal(dict)  # 完成信号，传递数据结果
    
    def emit_data_finished(self, data: Dict[str, Any], message: str = "处理完成"):
        """发送数据完成信号"""
        self.logger.info(f"数据任务完成: {message}")
        self.data_finished.emit(data)
        self.finished.emit(message)


class BaseTabWidget(QWidget):
    """
    通用Tab基类
    提供统一的UI模式和错误处理
    """
    
    def __init__(self, title: str = "分析工具", tab_type: str = "file"):
        super().__init__()
        self.title = title
        self.tab_type = tab_type  # "file" 或 "sequence"
        self.worker_thread: Optional[QThread] = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self.init_common_ui()
        self.connect_common_signals()
    
    def init_common_ui(self):
        """初始化通用UI组件"""
        self.main_layout = QVBoxLayout(self)
        
        # 为子类预留内容区域
        self.content_area = QVBoxLayout()
        self.main_layout.addLayout(self.content_area)
        
        if self.tab_type == "sequence":
            # 为序列处理Tab创建输入输出区域
            self.init_sequence_ui()
        
        # 状态区域
        self.status_layout = QHBoxLayout()
        self.status_label = QLabel("就绪")
        self.status_layout.addWidget(QLabel("状态:"))
        self.status_layout.addWidget(self.status_label)
        self.status_layout.addStretch()
        
        # 日志区域（仅文件处理模式显示）
        if self.tab_type == "file":
            self.log_area = QTextEdit()
            self.log_area.setMaximumHeight(100)
            self.log_area.setReadOnly(True)
            self.log_area.setPlaceholderText("操作日志将显示在此处...")
            self.main_layout.addWidget(self.log_area)
        
        # 添加状态到布局
        self.main_layout.addLayout(self.status_layout)
    
    def init_sequence_ui(self):
        """初始化序列处理UI"""
        # 输入区域
        self.input_label = QLabel("输入序列或上传文件：")
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("粘贴DNA/RNA序列，或点击下方按钮上传文件...")
        self.upload_btn = QPushButton("上传文件")
        self.upload_btn.clicked.connect(self.open_file)
        self.input_hint = QLabel("")
        self.input_hint.setStyleSheet("color: #888;")

        input_layout = QVBoxLayout()
        input_layout.addWidget(self.input_label)
        input_layout.addWidget(self.input_text)
        input_layout.addWidget(self.upload_btn)
        input_layout.addWidget(self.input_hint)

        # 输出区域
        self.output_label = QLabel("输出结果：")
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.export_btn = QPushButton("导出结果")
        self.copy_btn = QPushButton("复制到剪贴板")
        self.export_btn.clicked.connect(self.export_result)
        self.copy_btn.clicked.connect(self.copy_result)

        output_btn_layout = QHBoxLayout()
        output_btn_layout.addWidget(self.export_btn)
        output_btn_layout.addWidget(self.copy_btn)

        output_layout = QVBoxLayout()
        output_layout.addWidget(self.output_label)
        output_layout.addWidget(self.output_text)
        output_layout.addLayout(output_btn_layout)

        # 控制按钮
        self.run_btn = QPushButton("运行")
        self.clear_btn = QPushButton("清空")
        self.help_btn = QPushButton("帮助")
        self.run_btn.clicked.connect(self.run)
        self.clear_btn.clicked.connect(self.clear)
        self.help_btn.clicked.connect(self.show_help)

        ctrl_btn_layout = QHBoxLayout()
        ctrl_btn_layout.addWidget(self.run_btn)
        ctrl_btn_layout.addWidget(self.clear_btn)
        ctrl_btn_layout.addWidget(self.help_btn)
        ctrl_btn_layout.addStretch()

        # 添加到内容区域
        self.add_content_layout(input_layout)
        self.add_content_layout(output_layout)
        self.add_content_layout(ctrl_btn_layout)
    
    def open_file(self):
        """打开文件（序列处理模式）"""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择序列文件", "", 
            "FASTA/TXT/GenBank (*.fasta *.fa *.txt *.gb *.gbk);;所有文件 (*)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.input_text.setPlainText(content)
                self.input_hint.setText(f"已加载文件: {file_path}")
            except Exception as e:
                QMessageBox.warning(self, "文件读取错误", str(e))

    def export_result(self):
        """导出结果（序列处理模式）"""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出结果", "result.txt", 
            "文本文件 (*.txt);;FASTA文件 (*.fasta);;CSV文件 (*.csv)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.output_text.toPlainText())
                self.status_label.setText(f"结果已导出: {file_path}")
            except Exception as e:
                QMessageBox.warning(self, "导出错误", str(e))

    def copy_result(self):
        """复制结果到剪贴板（序列处理模式）"""
        self.output_text.selectAll()
        self.output_text.copy()
        self.status_label.setText("结果已复制到剪贴板")
    
    def run(self):
        """由子类实现的主要运行方法"""
        pass
        
    def clear(self):
        """清空内容"""
        if hasattr(self, 'input_text'):
            self.input_text.clear()
        if hasattr(self, 'output_text'):
            self.output_text.clear()
        if hasattr(self, 'input_hint'):
            self.input_hint.clear()
        if hasattr(self, 'log_area'):
            self.log_area.clear()
        self.show_status("已清空")
        
    def show_help(self):
        """由子类实现的帮助方法"""
        pass
    
    def add_content_layout(self, layout):
        """子类可以使用此方法添加内容布局"""
        self.content_area.addLayout(layout)
    
    def add_content_widget(self, widget):
        """子类可以使用此方法添加内容控件"""
        self.content_area.addWidget(widget)
    
    def connect_common_signals(self):
        """连接通用信号 - 子类可重写"""
        pass
    
    def show_status(self, message: str):
        """显示状态信息"""
        self.status_label.setText(message)
        self.logger.info(message)
    
    def log_message(self, message: str, level: str = "INFO"):
        """添加日志消息（仅文件处理模式）"""
        if not hasattr(self, 'log_area'):
            return
            
        prefix = {
            "INFO": "[信息]",
            "ERROR": "[错误]",
            "WARNING": "[警告]"
        }.get(level, "[信息]")
        
        self.log_area.append(f"{prefix} {message}")
        
        if level == "ERROR":
            self.logger.error(message)
        elif level == "WARNING":
            self.logger.warning(message)
        else:
            self.logger.info(message)
    
    def set_running_state(self, running: bool):
        """设置运行状态 - 子类应重写以禁用特定按钮"""
        self.show_status("处理中..." if running else "就绪")
    
    def handle_worker_finished(self, message: str):
        """处理工作线程完成"""
        if hasattr(self, 'log_area'):
            self.log_message(message)
        else:
            self.show_status("完成")
        self.set_running_state(False)
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None
    
    def handle_worker_error(self, error_msg: str):
        """处理工作线程错误"""
        if hasattr(self, 'log_area'):
            self.log_message(error_msg, "ERROR")
        else:
            self.show_status(f"错误: {error_msg}")
        self.set_running_state(False)
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None
    
    def start_worker(self, worker: BaseWorker):
        """启动工作线程的通用方法"""
        if self.worker_thread and self.worker_thread.isRunning():
            error_msg = "任务正在运行中，请等待完成"
            if hasattr(self, 'log_area'):
                self.log_message(error_msg, "WARNING")
            else:
                self.show_status(error_msg)
            return False
        
        self.worker_thread = QThread()
        worker.moveToThread(self.worker_thread)
        
        # 连接信号
        self.worker_thread.started.connect(worker.run)
        worker.finished.connect(self.handle_worker_finished)
        worker.error.connect(self.handle_worker_error)
        worker.finished.connect(self.worker_thread.quit)
        worker.error.connect(self.worker_thread.quit)
        
        # 如果有进度信号，连接到状态显示
        if hasattr(worker, 'progress'):
            worker.progress.connect(self.show_status)
        
        self.set_running_state(True)
        self.worker_thread.start()
        return True


class FASTAWorker(BaseWorker):
    """
    FASTA文件处理专用工作线程基类
    """
    
    def __init__(self, input_path: str, output_path: str):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
    
    def validate_files(self) -> bool:
        """验证输入输出文件路径"""
        import os
        
        if not self.input_path or not os.path.isfile(self.input_path):
            self.emit_error("输入文件无效或不存在")
            return False
        
        if not self.output_path:
            self.emit_error("输出文件路径不能为空")
            return False
        
        # 检查输出目录是否存在，不存在则创建
        output_dir = os.path.dirname(self.output_path)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                self.emit_error(f"无法创建输出目录: {e}")
                return False
        
        return True
    
    def load_fasta_processor(self):
        """加载FASTA处理器"""
        try:
            from modules.fasta_processor import FASTAProcessor
            processor = FASTAProcessor()
            if not processor.read_file(self.input_path):
                self.emit_error("无法读取FASTA文件")
                return None
            return processor
        except Exception as e:
            self.emit_error(f"加载FASTA处理器失败: {e}")
            return None


# 常用工具函数
def setup_logging():
    """设置项目日志"""
    import logging
    import os
    from datetime import datetime
    
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, f"bioseq_{datetime.now().strftime('%Y%m%d')}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


def validate_input_path(path: str, file_types: list | None = None) -> tuple[bool, str]:
    """
    验证输入文件路径
    
    Args:
        path: 文件路径
        file_types: 允许的文件扩展名列表，如 ['.fasta', '.fa', '.fas']
    
    Returns:
        (是否有效, 错误消息)
    """
    import os
    
    if not path or not path.strip():
        return False, "文件路径不能为空"
    
    if not os.path.isfile(path):
        return False, "文件不存在或不是有效文件"
    
    if file_types:
        ext = os.path.splitext(path)[1].lower()
        if ext not in file_types:
            return False, f"不支持的文件类型，请选择: {', '.join(file_types)}"
    
    return True, ""


def validate_output_path(path: str) -> tuple[bool, str]:
    """
    验证输出文件路径
    
    Returns:
        (是否有效, 错误消息)
    """
    import os
    
    if not path or not path.strip():
        return False, "输出路径不能为空"
    
    output_dir = os.path.dirname(path)
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
        except Exception as e:
            return False, f"无法创建输出目录: {e}"
    
    return True, ""
