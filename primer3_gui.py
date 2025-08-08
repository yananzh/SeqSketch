# -*- coding: utf-8 -*-

"""
PCR Primer Designer GUI using PyQt6 and primer3-py.

This application provides a user-friendly interface to design PCR primers
for different scenarios:
1. Standard PCR: Design primers for a sub-region within a template.
2. Specific Region PCR: Force primer design within a defined start/end coordinate.
3. Full-length Cloning: Design primers to amplify the entire given template.

It uses a worker thread (QThread) to run the primer3 calculations,
ensuring the GUI remains responsive during the design process.
"""

import sys
import importlib
try:
    p3_bindings = importlib.import_module("primer3.bindings")
except Exception:
    p3_bindings = None
from pprint import pformat

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QGroupBox, QFormLayout, QLineEdit, QPushButton, QPlainTextEdit,
    QSpinBox, QDoubleSpinBox, QRadioButton, QTableWidget, QTableWidgetItem,
    QTabWidget, QStatusBar, QHeaderView, QMessageBox, QLabel
)
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QIcon


class Worker(QObject):
    """
    后台工作线程，负责运行 Primer3 核心算法。
    继承自 QObject 以便能够被移动到 QThread 中并使用信号/槽机制。
    """
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, seq_args, global_args):
        super().__init__()
        self.seq_args = seq_args
        self.global_args = global_args

    def run(self):
        """执行引物设计"""
        try:
            self.progress.emit("正在调用 Primer3 核心库进行计算...")
            if p3_bindings is None:
                self.error.emit("未能导入 primer3 库，请先安装: pip install primer3-py")
                return
            # primer3-py 推荐使用 design_primers（snake_case）
            if hasattr(p3_bindings, 'design_primers'):
                results = p3_bindings.design_primers(
                    seq_args=self.seq_args,
                    global_args=self.global_args
                )
            else:
                results = p3_bindings.designPrimers(
                    seq_args=self.seq_args,
                    global_args=self.global_args
                )
            self.progress.emit("计算完成。")
            self.finished.emit(results)
        except Exception as e:
            # 捕获任何可能发生的错误，包括 primer3 找不到引物时的错误
            self.error.emit(f"发生错误: {str(e)}")


class MainWindow(QMainWindow):
    """主窗口类"""
    def __init__(self):
        super().__init__()
        self.worker = None
        self.thread = None
        self.primer_pair_details = [] # 存储返回的引物对详细信息
        
        self.init_ui()
        self.connect_signals()
        self.update_ui_for_mode() # 初始化UI状态
        # 移除菜单栏
        self.setMenuBar(None)

    def init_ui(self):
        """初始化UI界面"""
        self.setWindowTitle("PCR 引物设计助手 (PyQt6)")
        self.setGeometry(100, 100, 1200, 700)
        
        # --- 创建菜单栏 ---
        self.create_menu()

        # --- 主布局 ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- 左侧面板：参数设置 ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setFixedWidth(400)

        # 序列输入框
        seq_group = QGroupBox("1. 粘贴模板序列 (DNA)")
        seq_layout = QVBoxLayout(seq_group)
        self.seq_input = QPlainTextEdit()
        self.seq_input.setPlaceholderText("在此处粘贴FASTA或原始DNA序列...")
        self.seq_len_label = QLabel("序列长度: 0 bp")
        seq_layout.addWidget(self.seq_input)
        seq_layout.addWidget(self.seq_len_label)

        # 设计模式
        mode_group = QGroupBox("2. 选择设计模式")
        mode_layout = QVBoxLayout(mode_group)
        self.rb_standard = QRadioButton("常规引物设计 (扩增内部片段)")
        self.rb_specific = QRadioButton("特定区域设计 (在指定区域内)")
        self.rb_cloning = QRadioButton("全长克隆设计 (扩增完整模板)")
        self.rb_standard.setChecked(True)
        mode_layout.addWidget(self.rb_standard)
        mode_layout.addWidget(self.rb_specific)
        mode_layout.addWidget(self.rb_cloning)

        # 目标区域
        self.region_group = QGroupBox("目标区域 (Target Region)")
        region_layout = QFormLayout(self.region_group)
        self.region_start_spin = QSpinBox(minimum=1, maximum=999999)
        self.region_end_spin = QSpinBox(minimum=1, maximum=999999)
        region_layout.addRow("起始位置 (Start):", self.region_start_spin)
        region_layout.addRow("结束位置 (End):", self.region_end_spin)

        # 常规参数
        general_group = QGroupBox("3. 产物与引物通用参数")
        general_layout = QFormLayout(general_group)
        self.prod_size_min = QSpinBox(minimum=50, maximum=10000, value=150)
        self.prod_size_max = QSpinBox(minimum=50, maximum=10000, value=300)
        self.num_primers_spin = QSpinBox(minimum=1, maximum=10, value=5)
        general_layout.addRow("产物大小范围 (Min/Max):", QHBoxLayout())
        general_layout.itemAt(0, QFormLayout.ItemRole.FieldRole).addWidget(self.prod_size_min)
        general_layout.itemAt(0, QFormLayout.ItemRole.FieldRole).addWidget(self.prod_size_max)
        general_layout.addRow("返回引物对数量:", self.num_primers_spin)

        # 引物特性参数
        primer_spec_group = QGroupBox("4. 引物特性参数")
        primer_spec_layout = QFormLayout(primer_spec_group)
        self.p_len_min = QSpinBox(minimum=15, maximum=30, value=18)
        self.p_len_opt = QSpinBox(minimum=15, maximum=30, value=20)
        self.p_len_max = QSpinBox(minimum=15, maximum=30, value=25)
        self.p_tm_min = QDoubleSpinBox(minimum=40.0, maximum=80.0, value=57.0, decimals=1)
        self.p_tm_opt = QDoubleSpinBox(minimum=40.0, maximum=80.0, value=60.0, decimals=1)
        self.p_tm_max = QDoubleSpinBox(minimum=40.0, maximum=80.0, value=63.0, decimals=1)
        self.p_gc_min = QDoubleSpinBox(minimum=20.0, maximum=80.0, value=40.0, decimals=1)
        self.p_gc_opt = QDoubleSpinBox(minimum=20.0, maximum=80.0, value=50.0, decimals=1)
        self.p_gc_max = QDoubleSpinBox(minimum=20.0, maximum=80.0, value=60.0, decimals=1)
        
        primer_spec_layout.addRow("引物长度 (Min/Opt/Max):", self.create_hbox_for_spins(self.p_len_min, self.p_len_opt, self.p_len_max))
        primer_spec_layout.addRow("引物Tm (°C) (Min/Opt/Max):", self.create_hbox_for_spins(self.p_tm_min, self.p_tm_opt, self.p_tm_max))
        primer_spec_layout.addRow("引物GC含量 (%) (Min/Opt/Max):", self.create_hbox_for_spins(self.p_gc_min, self.p_gc_opt, self.p_gc_max))

        # 操作按钮
        self.design_button = QPushButton("开始设计引物")
        self.design_button.setStyleSheet("font-size: 16px; padding: 10px;")

        left_layout.addWidget(seq_group)
        left_layout.addWidget(mode_group)
        left_layout.addWidget(self.region_group)
        left_layout.addWidget(general_group)
        left_layout.addWidget(primer_spec_group)
        left_layout.addStretch()
        left_layout.addWidget(self.design_button)

        # --- 右侧面板：结果展示 ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.tabs = QTabWidget()
        
        # Tab 1: 引物对列表
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(7)
        self.results_table.setHorizontalHeaderLabels([
            "Pair #", "Type", "Sequence", "Length", "Tm", "GC%", "Product Size"
        ])
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setStretchLastSection(True)

        # Tab 2: 详细信息
        self.details_view = QPlainTextEdit()
        self.details_view.setReadOnly(True)
        self.details_view.setPlaceholderText("点击上方表格中的引物对以查看详细技术参数...")
        
        self.tabs.addTab(self.results_table, "引物对列表")
        self.tabs.addTab(self.details_view, "详细信息")
        right_layout.addWidget(self.tabs)

        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)

        # --- 状态栏 ---
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("准备就绪。")

    def create_hbox_for_spins(self, spin1, spin2, spin3):
        """辅助函数，创建包含三个spinbox的水平布局"""
        hbox = QHBoxLayout()
        hbox.addWidget(spin1)
        hbox.addWidget(spin2)
        hbox.addWidget(spin3)
        return hbox

    def create_menu(self):
        pass  # 不创建任何菜单栏

    def open_primer_designer(self):
        """打开引物设计工具窗口（占位实现，可后续扩展为弹窗或新窗口）"""
        QMessageBox.information(self, "引物设计", "这里将打开引物设计工具窗口。\n(可在此集成 modules/primer3_designer.py 的功能)")

    def connect_signals(self):
        """连接所有信号与槽"""
        self.design_button.clicked.connect(self.start_design_task)
        
        # 模式切换时更新UI
        self.rb_standard.toggled.connect(self.update_ui_for_mode)
        self.rb_specific.toggled.connect(self.update_ui_for_mode)
        self.rb_cloning.toggled.connect(self.update_ui_for_mode)
        
        # 序列变化时更新长度标签和克隆模式下的产物大小
        self.seq_input.textChanged.connect(self.on_sequence_changed)
        
        # 点击表格行显示详细信息
        self.results_table.cellClicked.connect(self.display_detailed_results)

    def update_ui_for_mode(self):
        """根据选择的设计模式更新UI控件的可用状态"""
        is_standard = self.rb_standard.isChecked()
        is_specific = self.rb_specific.isChecked()
        is_cloning = self.rb_cloning.isChecked()
        
        self.region_group.setEnabled(is_specific)
        self.prod_size_min.setEnabled(is_standard or is_specific)
        self.prod_size_max.setEnabled(is_standard or is_specific)

        if is_cloning:
            self.update_cloning_product_size()

    def on_sequence_changed(self):
        """当序列输入框内容改变时调用"""
        seq_len = len(self.seq_input.toPlainText().strip())
        self.seq_len_label.setText(f"序列长度: {seq_len} bp")
        if self.rb_cloning.isChecked():
            self.update_cloning_product_size()
    
    def update_cloning_product_size(self):
        """在克隆模式下，根据序列长度自动更新产物大小"""
        seq_len = len(self.seq_input.toPlainText().strip())
        if seq_len > 0:
            self.prod_size_min.setValue(max(50, seq_len - 50))
            self.prod_size_max.setValue(seq_len + 50) # 允许一些冗余
        else:
            self.prod_size_min.setValue(150)
            self.prod_size_max.setValue(300)

    def start_design_task(self):
        """开始引物设计任务，准备参数并启动后台线程"""
        raw_text = self.seq_input.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "输入错误", "请输入有效的DNA模板序列。")
            return

        # 1. 解析FASTA格式，仅提取纯DNA序列
        if raw_text.startswith('>'):
            lines = raw_text.splitlines()
            seq_lines = [line.strip() for line in lines if not line.startswith('>')]
            sequence = ''.join(seq_lines).replace(' ', '').replace('\r', '').replace('\n', '').upper()
        else:
            sequence = raw_text.replace(' ', '').replace('\r', '').replace('\n', '').upper()

        if not sequence or any(c not in 'ACGTUN' for c in sequence):
            QMessageBox.warning(self, "输入错误", "请输入有效的DNA模板序列（仅包含ACGTU字母）。")
            return

        # 禁用按钮，清空旧结果
        self.design_button.setEnabled(False)
        self.statusBar.showMessage("正在准备参数...")
        self.results_table.setRowCount(0)
        self.details_view.clear()
        self.primer_pair_details.clear()

        # 2. 准备序列参数 (SEQUENCE_ID, SEQUENCE_TEMPLATE)
        seq_args = {
            'SEQUENCE_ID': 'MyTemplate',
            'SEQUENCE_TEMPLATE': sequence
        }

        # 3. 根据不同模式准备全局参数
        global_args = {
            'PRIMER_OPT_SIZE': self.p_len_opt.value(),
            'PRIMER_MIN_SIZE': self.p_len_min.value(),
            'PRIMER_MAX_SIZE': self.p_len_max.value(),
            'PRIMER_OPT_TM': self.p_tm_opt.value(),
            'PRIMER_MIN_TM': self.p_tm_min.value(),
            'PRIMER_MAX_TM': self.p_tm_max.value(),
            'PRIMER_MIN_GC': self.p_gc_min.value(),
            'PRIMER_MAX_GC': self.p_gc_max.value(),
            'PRIMER_OPT_GC_PERCENT': self.p_gc_opt.value(),
            'PRIMER_NUM_RETURN': self.num_primers_spin.value(),
            'PRIMER_EXPLAIN_FLAG': 1, # 返回详细解释信息
        }

        seq_len = len(sequence)

        if self.rb_specific.isChecked():
            start_pos = self.region_start_spin.value()
            end_pos = self.region_end_spin.value()
            if start_pos >= end_pos or end_pos > seq_len:
                self.show_error_message("特定区域范围无效，请检查起始/结束位置。")
                return
            # primer3 使用 0-based index 和 (start, length)
            included_region = f"{start_pos - 1},{end_pos - start_pos + 1}"
            seq_args['SEQUENCE_INCLUDED_REGION'] = included_region
            global_args['PRIMER_PRODUCT_SIZE_RANGE'] = [
                self.prod_size_min.value(), self.prod_size_max.value()
            ]
        elif self.rb_cloning.isChecked():
            # 关键参数: 强制目标为整个序列
            seq_args['SEQUENCE_TARGET'] = f"0,{seq_len}"
            global_args['PRIMER_PRODUCT_SIZE_RANGE'] = [
                max(50, seq_len - 50), seq_len + 50
            ]
        else: # 标准模式
            global_args['PRIMER_PRODUCT_SIZE_RANGE'] = [
                self.prod_size_min.value(), self.prod_size_max.value()
            ]

        # 4. 创建并启动工作线程
        self.thread = QThread()
        self.worker = Worker(seq_args, global_args)
        self.worker.moveToThread(self.thread)

        # 连接工作线程的信号到主线程的槽
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.update_results_table)
        self.worker.error.connect(self.show_error_message)
        self.worker.progress.connect(self.statusBar.showMessage)

        # 线程结束后自动清理
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()
        self.statusBar.showMessage("后台任务已启动，正在设计引物...")
    
    def update_results_table(self, results):
        """当收到 finished 信号时，用结果填充表格"""
        num_returned = results.get('PRIMER_PAIR_NUM_RETURNED', 0)
        if num_returned == 0:
            self.show_error_message("未找到符合条件的引物对。请尝试放宽参数。")
            return

        self.results_table.setRowCount(num_returned * 2)
        self.primer_pair_details = []
        for i in range(num_returned):
            fwd_seq = results.get(f'PRIMER_LEFT_{i}_SEQUENCE', '')
            rev_seq = results.get(f'PRIMER_RIGHT_{i}_SEQUENCE', '')
            prod_size = results.get(f'PRIMER_PAIR_{i}_PRODUCT_SIZE', '')
            fwd_list = results.get(f'PRIMER_LEFT_{i}', [])
            rev_list = results.get(f'PRIMER_RIGHT_{i}', [])
            fwd_len = fwd_list[1] if isinstance(fwd_list, list) and len(fwd_list) > 1 else ''
            rev_len = rev_list[1] if isinstance(rev_list, list) and len(rev_list) > 1 else ''
            fwd_tm = results.get(f'PRIMER_LEFT_{i}_TM', '')
            fwd_gc = results.get(f'PRIMER_LEFT_{i}_GC_PERCENT', '')
            rev_tm = results.get(f'PRIMER_RIGHT_{i}_TM', '')
            rev_gc = results.get(f'PRIMER_RIGHT_{i}_GC_PERCENT', '')
            # 存储详细信息以备后用
            pair_info = results.get(f'PRIMER_PAIR_{i}', {})
            pair_info['LEFT'] = fwd_list
            pair_info['RIGHT'] = rev_list
            self.primer_pair_details.append(pair_info)
            # 正向引物行
            self.results_table.setItem(i*2, 0, QTableWidgetItem(str(i + 1)))
            self.results_table.setItem(i*2, 1, QTableWidgetItem("Fwd"))
            self.results_table.setItem(i*2, 2, QTableWidgetItem(fwd_seq))
            self.results_table.setItem(i*2, 3, QTableWidgetItem(str(fwd_len)))
            self.results_table.setItem(i*2, 4, QTableWidgetItem(f"{fwd_tm:.2f}" if isinstance(fwd_tm, (float, int)) else str(fwd_tm)))
            self.results_table.setItem(i*2, 5, QTableWidgetItem(f"{fwd_gc:.2f}" if isinstance(fwd_gc, (float, int)) else str(fwd_gc)))
            self.results_table.setItem(i*2, 6, QTableWidgetItem(str(prod_size)))
            # 反向引物行
            self.results_table.setItem(i*2+1, 0, QTableWidgetItem(str(i + 1)))
            self.results_table.setItem(i*2+1, 1, QTableWidgetItem("Rev"))
            self.results_table.setItem(i*2+1, 2, QTableWidgetItem(rev_seq))
            self.results_table.setItem(i*2+1, 3, QTableWidgetItem(str(rev_len)))
            self.results_table.setItem(i*2+1, 4, QTableWidgetItem(f"{rev_tm:.2f}" if isinstance(rev_tm, (float, int)) else str(rev_tm)))
            self.results_table.setItem(i*2+1, 5, QTableWidgetItem(f"{rev_gc:.2f}" if isinstance(rev_gc, (float, int)) else str(rev_gc)))
            self.results_table.setItem(i*2+1, 6, QTableWidgetItem(str(prod_size)))
        
        self.statusBar.showMessage(f"成功找到 {num_returned} 对引物。")
        self.design_button.setEnabled(True)

    def show_error_message(self, message):
        """显示错误信息对话框"""
        QMessageBox.critical(self, "错误", message)
        self.statusBar.showMessage("任务失败或未找到结果。")
        self.design_button.setEnabled(True)

    def display_detailed_results(self, row, column):
        """当用户点击表格行时，在右侧显示详细信息"""
        if row < len(self.primer_pair_details):
            details = self.primer_pair_details[row]
            # 使用 pprint.pformat 来美化字典输出
            self.details_view.setPlainText(pformat(details, indent=4))
    
    def show_about_dialog(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于 PCR 引物设计助手",
            "版本: 1.0\n"
            "作者: Gemini (Google AI)\n\n"
            "一个使用 PyQt6 和 primer3-py 构建的GUI工具，用于辅助PCR引物设计。"
        )

    def closeEvent(self, event):
        """关闭窗口时只关闭当前Tab或窗口，不关闭主界面"""
        # 如果作为独立窗口弹出，则直接关闭窗口
        # 如果作为Tab嵌入主界面，可在主界面实现Tab关闭逻辑
        self.hide()
        event.ignore()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())