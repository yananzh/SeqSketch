from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QFileDialog, QGroupBox, QSplitter, QLineEdit, QMessageBox, QScrollArea, QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import numpy as np
import os
try:
    from Bio import SeqIO
except ImportError:
    SeqIO = None
try:
    from scipy.ndimage import gaussian_filter1d
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

# Chromas风格颜色 - 更专业的配色
BASE_COLOR = {'A': '#00C000', 'T': '#C00000', 'C': '#0000C0', 'G': '#000000'}

# 设置matplotlib字体，支持中文
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'sans-serif']
matplotlib.rcParams['axes.unicode_minus'] = False

class SangerTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.quality_group = self.init_quality_ui()
        splitter.addWidget(self.quality_group)
        self.assembly_group = self.init_assembly_ui()
        splitter.addWidget(self.assembly_group)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        main_layout.addWidget(splitter)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close_tab)
        main_layout.addWidget(close_btn)
        self.setLayout(main_layout)

    def close_tab(self):
        parent = self.parent()
        if hasattr(parent, 'removeTab'):
            idx = parent.indexOf(self)
            parent.removeTab(idx)

    def init_quality_ui(self):
        group = QGroupBox("质量可视化 (支持.ab1)")
        vbox = QVBoxLayout()
        self.ab1_path = ""
        self.ab1_btn = QPushButton("加载 .ab1 文件")
        self.ab1_btn.clicked.connect(self.load_ab1_file)
        vbox.addWidget(self.ab1_btn)
        
        # 添加质量分数显示选项
        self.show_quality_cb = QCheckBox("显示质量分数")
        self.show_quality_cb.setChecked(True)
        self.show_quality_cb.toggled.connect(self.update_plot)
        vbox.addWidget(self.show_quality_cb)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.fig, self.ax = plt.subplots(figsize=(12, 5))
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setMinimumHeight(350)
        self.canvas_widget = QWidget()
        self.canvas_layout = QVBoxLayout(self.canvas_widget)
        self.canvas_layout.setContentsMargins(0, 0, 0, 0)
        self.canvas_layout.addWidget(self.canvas)
        self.scroll_area.setWidget(self.canvas_widget)
        vbox.addWidget(self.scroll_area, stretch=1)
        select_hbox = QHBoxLayout()
        self.select_label = QLabel("选择区间: ")
        self.select_start = QLineEdit()
        self.select_start.setPlaceholderText("起始")
        self.select_start.setFixedWidth(60)
        self.select_end = QLineEdit()
        self.select_end.setPlaceholderText("终止")
        self.select_end.setFixedWidth(60)
        self.export_seq_btn = QPushButton("导出选定序列")
        self.export_seq_btn.clicked.connect(self.export_selected_seq)
        self.export_qual_btn = QPushButton("导出质量分数")
        self.export_qual_btn.clicked.connect(self.export_selected_qual)
        select_hbox.addWidget(self.select_label)
        select_hbox.addWidget(self.select_start)
        select_hbox.addWidget(self.select_end)
        select_hbox.addWidget(self.export_seq_btn)
        select_hbox.addWidget(self.export_qual_btn)
        select_hbox.addStretch()
        vbox.addLayout(select_hbox)
        group.setLayout(vbox)
        self.ab1_seq = ""
        self.ab1_qual = []
        self.ab1_bases = []
        self.ab1_colors = []
        self.ab1_start = 0
        self.ab1_end = 0
        self.ab1_peaks = []
        self.canvas.mpl_connect('button_press_event', self.on_canvas_click)
        return group

    def load_ab1_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择.ab1文件", "", "AB1文件 (*.ab1)")
        if not file_path:
            return
        if SeqIO is None:
            QMessageBox.warning(self, "依赖缺失", "未安装biopython，无法解析.ab1文件。请先安装biopython。")
            return
        try:
            record = SeqIO.read(file_path, "abi")
            self.ab1_seq = str(record.seq)
            self.ab1_qual = record.letter_annotations["phred_quality"]
            self.ab1_bases = list(record.seq)
            trace = record.annotations["abif_raw"]
            self.ab1_colors = [trace["DATA9"], trace["DATA10"], trace["DATA11"], trace["DATA12"]]  # GATC顺序
            self.ab1_path = file_path
            self.ab1_start = record.annotations.get("start_base", 0)
            self.ab1_end = self.ab1_start + len(self.ab1_seq)
            # 获取主峰位置（PLOC1或PLOC2）
            self.ab1_peaks = []
            for key in ("PLOC2", "PLOC1"):
                if key in trace:
                    self.ab1_peaks = list(trace[key])
                    break
            self.plot_ab1_chromas_style()
        except Exception as e:
            QMessageBox.warning(self, "文件解析错误", str(e))

    def update_plot(self):
        if self.ab1_seq:
            self.plot_ab1_chromas_style()

    def plot_ab1_chromas_style(self):
        self.ax.clear()
        if not self.ab1_colors or not self.ab1_seq:
            self.ax.set_title("请先加载.ab1文件")
            self.canvas.draw()
            return
        
        base_len = len(self.ab1_seq)
        if not self.ab1_peaks or len(self.ab1_peaks) != base_len:
            self.ax.set_title("无法获取主峰位置信息")
            self.canvas.draw()
            return
        
        # 标准模式：横坐标为碱基编号
        base_positions = np.arange(1, base_len + 1)
        
        # 设置图形大小 - 每碱基固定宽度
        px_per_base = 25  # 更紧凑，专业软件风格
        fig_width = max(8, base_len * px_per_base / 100)
        self.fig.set_size_inches(fig_width, 5)
        
        # 颜色映射
        color_map = ['#00C000', '#0000C0', '#C00000', '#000000']  # G,A,T,C
        base_map = ['G', 'A', 'T', 'C']
        
        # 提取主峰区间信号并平滑
        peak_window = 20  # 每个主峰前后±20个点
        all_x = []
        all_signals = []
        
        for i, (base, peak_x) in enumerate(zip(self.ab1_bases, self.ab1_peaks)):
            # 确保主峰位置有效
            if peak_x < 0 or peak_x >= len(self.ab1_colors[0]):
                continue
                
            # 提取主峰区间信号
            start_idx = max(0, peak_x - peak_window)
            end_idx = min(len(self.ab1_colors[0]), peak_x + peak_window + 1)
            
            # 为每个碱基创建相对坐标
            local_x = np.linspace(-peak_window, peak_window, end_idx - start_idx)
            
            # 获取该碱基对应的信号通道
            base_idx = base_map.index(base) if base in base_map else 0
            signal = self.ab1_colors[base_idx][start_idx:end_idx]
            
            # 高斯平滑
            if SCIPY_AVAILABLE and len(signal) > 3:
                signal = gaussian_filter1d(signal, sigma=0.8)
            
            # 绘制该碱基的信号
            self.ax.plot(local_x + i + 1, signal, color=color_map[base_idx], 
                        alpha=0.85, linewidth=1.2, label=base if i == 0 else "")
        
        # 设置x轴为碱基编号
        self.ax.set_xlim(0.5, base_len + 0.5)
        self.ax.set_xticks(base_positions[::max(1, base_len//20)])
        self.ax.set_xticklabels([str(i) for i in base_positions[::max(1, base_len//20)]], fontsize=8)
        
        # 添加质量分数（可选）
        if self.show_quality_cb.isChecked():
            self.ax2 = self.ax.twinx()
            self.ax2.plot(base_positions, self.ab1_qual, 'k-', alpha=0.4, linewidth=0.8)
            self.ax2.set_ylabel("质量分数", fontsize=9)
            self.ax2.spines['top'].set_visible(False)
            self.ax2.spines['right'].set_visible(False)
        
        # 标注碱基字母
        max_y = self.ax.get_ylim()[1]
        for i, (base, peak_x) in enumerate(zip(self.ab1_bases, self.ab1_peaks)):
            if peak_x < 0 or peak_x >= len(self.ab1_colors[0]):
                continue
                
            # 获取该碱基信号的最大值
            base_idx = base_map.index(base) if base in base_map else 0
            start_idx = max(0, peak_x - peak_window)
            end_idx = min(len(self.ab1_colors[0]), peak_x + peak_window + 1)
            signal = self.ab1_colors[base_idx][start_idx:end_idx]
            
            if len(signal) > 0:
                max_signal = max(signal)
                
                # 主峰竖线（细、半透明）
                self.ax.vlines(i + 1, 0, max_signal, color=BASE_COLOR.get(base, 'gray'), 
                              linestyle='-', alpha=0.6, linewidth=0.8, zorder=2)
                
                # 碱基字母（大、粗、在主峰顶端）
                self.ax.text(i + 1, max_signal + 0.08 * max_y, base, 
                            ha='center', va='bottom', fontsize=14, fontweight='bold', 
                            color=BASE_COLOR.get(base, 'black'), zorder=3)
                
                # 碱基编号（小、灰色）
                self.ax.text(i + 1, -0.15 * max_y, str(i + 1), 
                            ha='center', va='top', fontsize=7, color='#666666', zorder=3)
        
        # 设置标签和标题
        self.ax.set_xlabel("碱基位置", fontsize=10)
        self.ax.set_ylabel("荧光信号强度", fontsize=10)
        self.ax.set_title(os.path.basename(self.ab1_path), fontsize=12, fontweight='bold')
        
        # 图例（只显示碱基）
        handles, labels = self.ax.get_legend_handles_labels()
        if handles:
            self.ax.legend(handles, labels, loc='upper right', fontsize=9, framealpha=0.8)
        
        # 去除边框，专业外观
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['left'].set_visible(True)
        self.ax.spines['bottom'].set_visible(True)
        
        # 设置网格（柔和）
        self.ax.grid(True, alpha=0.1, linestyle='-', linewidth=0.5)
        
        self.canvas.draw()
        self.canvas_widget.setMinimumWidth(int(fig_width * self.fig.dpi))

    def on_canvas_click(self, event):
        if event.xdata is not None:
            idx = int(event.xdata)
            self.select_start.setText(str(idx))
            self.select_end.setText(str(idx+20))

    def export_selected_seq(self):
        try:
            start = int(self.select_start.text())
            end = int(self.select_end.text())
            seq = self.ab1_seq[start-1:end]  # 碱基编号从1开始
        except Exception:
            QMessageBox.warning(self, "区间错误", "请输入有效的起止区间")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "导出序列", "selected_seq.txt", "文本文件 (*.txt)")
        if file_path:
            with open(file_path, 'w') as f:
                f.write(seq)
            QMessageBox.information(self, "导出成功", f"已导出到: {file_path}")

    def export_selected_qual(self):
        try:
            start = int(self.select_start.text())
            end = int(self.select_end.text())
            qual = self.ab1_qual[start-1:end]  # 碱基编号从1开始
        except Exception:
            QMessageBox.warning(self, "区间错误", "请输入有效的起止区间")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "导出质量分数", "selected_qual.csv", "CSV文件 (*.csv)")
        if file_path:
            with open(file_path, 'w') as f:
                f.write(','.join(map(str, qual)))
            QMessageBox.information(self, "导出成功", f"已导出到: {file_path}")

    def init_assembly_ui(self):
        group = QGroupBox("序列拼接")
        vbox = QVBoxLayout()
        fwd_hbox = QHBoxLayout()
        self.fwd_edit = QTextEdit()
        self.fwd_edit.setPlaceholderText("粘贴正向测序序列")
        self.fwd_load_btn = QPushButton("加载正向序列文件")
        self.fwd_load_btn.clicked.connect(lambda: self.load_seq_file(self.fwd_edit))
        fwd_hbox.addWidget(QLabel("正向序列:"))
        fwd_hbox.addWidget(self.fwd_edit)
        fwd_hbox.addWidget(self.fwd_load_btn)
        vbox.addLayout(fwd_hbox)
        rev_hbox = QHBoxLayout()
        self.rev_edit = QTextEdit()
        self.rev_edit.setPlaceholderText("粘贴反向测序序列")
        self.rev_load_btn = QPushButton("加载反向序列文件")
        self.rev_load_btn.clicked.connect(lambda: self.load_seq_file(self.rev_edit))
        rev_hbox.addWidget(QLabel("反向序列:"))
        rev_hbox.addWidget(self.rev_edit)
        rev_hbox.addWidget(self.rev_load_btn)
        vbox.addLayout(rev_hbox)
        run_hbox = QHBoxLayout()
        self.assemble_btn = QPushButton("运行拼接")
        self.assemble_btn.clicked.connect(self.run_assembly)
        run_hbox.addWidget(self.assemble_btn)
        run_hbox.addStretch()
        vbox.addLayout(run_hbox)
        self.assembly_result = QTextEdit()
        self.assembly_result.setReadOnly(True)
        vbox.addWidget(QLabel("拼接结果："))
        vbox.addWidget(self.assembly_result)
        save_hbox = QHBoxLayout()
        self.save_assembly_btn = QPushButton("保存拼接序列到文件")
        self.save_assembly_btn.clicked.connect(self.save_assembly_result)
        save_hbox.addWidget(self.save_assembly_btn)
        save_hbox.addStretch()
        vbox.addLayout(save_hbox)
        group.setLayout(vbox)
        return group

    def load_seq_file(self, edit_widget):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择序列文件", "", "FASTA/TXT文件 (*.fasta *.fa *.txt)")
        if file_path:
            with open(file_path, 'r') as f:
                seq = ''.join([line.strip() for line in f if not line.startswith('>')])
            edit_widget.setPlainText(seq)

    def run_assembly(self):
        fwd = self.fwd_edit.toPlainText().strip().upper().replace('U', 'T')
        rev = self.rev_edit.toPlainText().strip().upper().replace('U', 'T')
        if not fwd or not rev:
            QMessageBox.warning(self, "输入错误", "请粘贴或加载正向和反向序列")
            return
        rev_rc = self.reverse_complement(rev)
        overlap, merged = self.auto_assemble(fwd, rev_rc)
        if overlap < 10:
            QMessageBox.warning(self, "拼接警告", "未检测到明显重叠，直接拼接两端")
        self.assembly_result.setPlainText(merged)

    def reverse_complement(self, seq):
        comp_map = str.maketrans('ACGT', 'TGCA')
        return seq.translate(comp_map)[::-1]

    def auto_assemble(self, fwd, rev_rc):
        max_overlap = min(len(fwd), len(rev_rc))
        overlap = 0
        for i in range(max_overlap, 9, -1):
            if fwd[-i:] == rev_rc[:i]:
                overlap = i
                break
        if overlap > 0:
            merged = fwd + rev_rc[overlap:]
        else:
            merged = fwd + rev_rc
        return overlap, merged

    def save_assembly_result(self):
        seq = self.assembly_result.toPlainText().strip()
        if not seq:
            QMessageBox.warning(self, "无拼接结果", "请先运行拼接")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "保存拼接序列", "assembled_seq.fasta", "FASTA文件 (*.fasta);;文本文件 (*.txt)")
        if file_path:
            with open(file_path, 'w') as f:
                f.write(seq)
            QMessageBox.information(self, "保存成功", f"已保存到: {file_path}")

    def show_help(self):
        QMessageBox.information(self, "桑格测序数据处理 帮助", "\n- 质量分数可视化\n- 选择高质量区域\n- 序列拼接\n\n本功能支持.ab1文件电泳图、质量分数可视化、区域导出、正反向序列拼接。") 