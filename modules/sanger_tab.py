from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QFileDialog, QGroupBox, QSplitter, QLineEdit, QMessageBox, QScrollArea, QCheckBox
)
from PyQt6.QtCore import Qt
from utils.common_components import BaseTabWidget
import translations
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

class SangerTab(BaseTabWidget):
    def __init__(self, parent=None):
        super().__init__(translations.tr("桑格测序数据处理"), "sequence")
        self.init_sanger_ui()

    def init_sanger_ui(self):
        """初始化桑格测序数据处理UI"""
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.quality_group = self.init_quality_ui()
        splitter.addWidget(self.quality_group)
        self.selection_group = self.init_selection_ui()
        splitter.addWidget(self.selection_group)
        self.assembly_group = self.init_assembly_ui()
        splitter.addWidget(self.assembly_group)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 2)
        self.add_content_widget(splitter)

    # 1. 质量可视化
    def init_quality_ui(self):
        group = QGroupBox(translations.tr("质量可视化 (支持.ab1)"))
        vbox = QVBoxLayout()
        self.ab1_path = ""
        self.ab1_btn = QPushButton(translations.tr("加载 .ab1 文件"))
        self.ab1_btn.clicked.connect(self.load_ab1_file)
        vbox.addWidget(self.ab1_btn)
        # 导出图片按钮
        self.export_img_btn = QPushButton(translations.tr("导出图片"))
        self.export_img_btn.clicked.connect(self.export_trace_figure)
        vbox.addWidget(self.export_img_btn)
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
        group.setLayout(vbox)
        self.ab1_seq = ""
        self.ab1_qual = []
        self.ab1_bases = []
        self.ab1_colors = []
        self.ab1_peaks = []
        return group

    def export_trace_figure(self):
        if not self.ab1_seq:
            QMessageBox.warning(self, translations.tr("未加载数据"), translations.tr("请先加载.ab1文件后再导出图片"))
            return
        file_path, sel = QFileDialog.getSaveFileName(self, translations.tr("导出图片"), "trace_figure.png", "PNG图片 (*.png);;PDF文件 (*.pdf);;TIFF图片 (*.tiff *.tif)")
        if not file_path:
            return
        # 根据选择的格式自动补后缀
        if sel.startswith("PNG") and not file_path.lower().endswith(".png"):
            file_path += ".png"
        elif sel.startswith("PDF") and not file_path.lower().endswith(".pdf"):
            file_path += ".pdf"
        elif sel.startswith("TIFF") and not (file_path.lower().endswith(".tiff") or file_path.lower().endswith(".tif")):
            file_path += ".tiff"
        # 临时去除title
        old_title = self.ax.get_title()
        self.ax.set_title("")
        self.fig.tight_layout()
        try:
            self.fig.savefig(file_path, dpi=300, bbox_inches='tight')
            QMessageBox.information(self, translations.tr("导出成功"), translations.tr("图片已保存到: {path}").format(path=file_path))
        except Exception as e:
            QMessageBox.warning(self, translations.tr("导出失败"), str(e))
        finally:
            self.ax.set_title(old_title)
            self.canvas.draw()

    # 2. 序列选择
    def init_selection_ui(self):
        group = QGroupBox(translations.tr("序列选择与导出"))
        vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        self.select_label = QLabel(translations.tr("选择区间: "))
        self.select_start = QLineEdit()
        self.select_start.setPlaceholderText(translations.tr("起始"))
        self.select_start.setFixedWidth(60)
        self.select_end = QLineEdit()
        self.select_end.setPlaceholderText(translations.tr("终止"))
        self.select_end.setFixedWidth(60)
        self.export_seq_btn = QPushButton(translations.tr("导出选定序列"))
        self.export_seq_btn.clicked.connect(self.export_selected_seq)
        hbox.addWidget(self.select_label)
        hbox.addWidget(self.select_start)
        hbox.addWidget(self.select_end)
        hbox.addWidget(self.export_seq_btn)
        hbox.addStretch()
        vbox.addLayout(hbox)
        group.setLayout(vbox)
        return group

    # 3. 序列拼接
    def init_assembly_ui(self):
        group = QGroupBox(translations.tr("序列拼接"))
        vbox = QVBoxLayout()
        fwd_hbox = QHBoxLayout()
        self.fwd_edit = QTextEdit()
        self.fwd_edit.setPlaceholderText(translations.tr("粘贴正向测序序列"))
        self.fwd_load_btn = QPushButton(translations.tr("加载正向序列文件"))
        self.fwd_load_btn.clicked.connect(lambda: self.load_seq_file(self.fwd_edit))
        fwd_hbox.addWidget(QLabel(translations.tr("正向序列:")))
        fwd_hbox.addWidget(self.fwd_edit)
        fwd_hbox.addWidget(self.fwd_load_btn)
        vbox.addLayout(fwd_hbox)
        rev_hbox = QHBoxLayout()
        self.rev_edit = QTextEdit()
        self.rev_edit.setPlaceholderText(translations.tr("粘贴反向测序序列"))
        self.rev_load_btn = QPushButton(translations.tr("加载反向序列文件"))
        self.rev_load_btn.clicked.connect(lambda: self.load_seq_file(self.rev_edit))
        rev_hbox.addWidget(QLabel(translations.tr("反向序列:")))
        rev_hbox.addWidget(self.rev_edit)
        rev_hbox.addWidget(self.rev_load_btn)
        vbox.addLayout(rev_hbox)
        run_hbox = QHBoxLayout()
        self.assemble_btn = QPushButton(translations.tr("运行拼接"))
        self.assemble_btn.clicked.connect(self.run_assembly)
        run_hbox.addWidget(self.assemble_btn)
        run_hbox.addStretch()
        vbox.addLayout(run_hbox)
        self.assembly_result = QTextEdit()
        self.assembly_result.setReadOnly(True)
        vbox.addWidget(QLabel(translations.tr("拼接结果：")))
        vbox.addWidget(self.assembly_result)
        save_hbox = QHBoxLayout()
        self.save_assembly_btn = QPushButton(translations.tr("保存拼接序列到文件"))
        self.save_assembly_btn.clicked.connect(self.save_assembly_result)
        save_hbox.addWidget(self.save_assembly_btn)
        save_hbox.addStretch()
        vbox.addLayout(save_hbox)
        group.setLayout(vbox)
        return group

    def load_ab1_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, translations.tr("选择.ab1文件"), "", "AB1文件 (*.ab1)")
        if not file_path:
            return
        if SeqIO is None:
            QMessageBox.warning(self, translations.tr("依赖缺失"), translations.tr("未安装biopython，无法解析.ab1文件。请先安装biopython。"))
            return
        try:
            record = SeqIO.read(file_path, "abi")
            self.ab1_seq = str(record.seq)
            self.ab1_qual = record.letter_annotations["phred_quality"]
            self.ab1_bases = list(record.seq)
            trace = record.annotations["abif_raw"]
            self.ab1_colors = [
                np.array(trace["DATA9"], dtype=np.int32),  # G
                np.array(trace["DATA10"], dtype=np.int32), # A
                np.array(trace["DATA11"], dtype=np.int32), # T
                np.array(trace["DATA12"], dtype=np.int32)  # C
            ]
            self.ab1_peaks = trace["PLOC2"] if "PLOC2" in trace else trace["PLOC1"]
            self.ab1_path = file_path
            self.plot_ab1_trace_aligned()
        except Exception as e:
            QMessageBox.warning(self, translations.tr("文件解析错误"), str(e))

    def plot_ab1_trace_aligned(self):
        self.ax.clear()
        if not self.ab1_colors or not self.ab1_seq:
            self.ax.set_title(translations.tr("请先加载.ab1文件"))
            self.canvas.draw()
            return
        try:
            # 读取主叫碱基位置信息与序列
            peak_locations = np.array(self.ab1_peaks, dtype=np.int32).flatten()
            called_bases = self.ab1_bases
            total_bases = len(peak_locations)
            if total_bases == 0:
                self.ax.set_title(translations.tr("ab1文件无有效主叫碱基"))
                self.canvas.draw()
                return
            # 横坐标为碱基编号（1,2,3...）
            base_x = np.arange(1, total_bases + 1)
            # 4色通道
            trace = {
                'G': np.array(self.ab1_colors[0], dtype=np.int32),
                'A': np.array(self.ab1_colors[1], dtype=np.int32),
                'T': np.array(self.ab1_colors[2], dtype=np.int32),
                'C': np.array(self.ab1_colors[3], dtype=np.int32)
            }
            base_colors = {'A': '#00C000', 'T': '#C00000', 'G': '#000000', 'C': '#0000C0'}
            window = 5
            max_y = 1
            y_vals = []
            for i, (base, peak) in enumerate(zip(called_bases, peak_locations)):
                x_peak = np.linspace(i+1-0.4, i+1+0.4, 2*window+1)
                idx_range = np.arange(peak-window, peak+window+1)
                valid = (idx_range >= 0) & (idx_range < len(trace[base]))
                idx_range = idx_range[valid]
                x_peak = x_peak[valid]
                y_peak = trace[base][idx_range]
                if SCIPY_AVAILABLE and len(y_peak) > 3:
                    y_peak = gaussian_filter1d(y_peak, sigma=0.5)
                y_peak = np.concatenate(([0], y_peak, [0]))
                x_peak = np.concatenate(([x_peak[0]-(x_peak[1]-x_peak[0])], x_peak, [x_peak[-1]+(x_peak[-1]-x_peak[-2])]))
                self.ax.plot(x_peak, y_peak, color=base_colors[base], linewidth=2.2, alpha=0.98, zorder=5)
                if len(y_peak) > 0:
                    y_val = max(y_peak)
                    y_vals.append(y_val)
                    max_y = max(max_y, y_val)
            # 统一主峰字母的y坐标
            label_y = max_y + 0.08 * max_y
            for i, base in enumerate(called_bases):
                self.ax.text(i+1, label_y, base, color=base_colors.get(base, 'gray'), fontsize=16, fontweight='bold', ha='center', va='bottom', zorder=10)
                self.ax.text(i+1, -0.18 * max_y, str(i+1), ha='center', va='top', fontsize=8, color='#666666', zorder=3)
            self.ax.set_xlim(0.5, total_bases + 0.5)
            self.ax.set_ylim(-0.3 * max_y, max_y * 1.12)
            self.ax.set_xlabel(translations.tr("碱基编号"), fontsize=12)
            self.ax.set_ylabel(translations.tr("荧光信号强度"), fontsize=12)
            # 不再设置title
            # self.ax.set_title(os.path.basename(self.ab1_path), fontsize=14, fontweight='bold')
            self.ax.grid(True, linestyle="--", alpha=0.3)
            self.ax.spines['top'].set_visible(False)
            self.ax.spines['right'].set_visible(False)
            self.ax.spines['left'].set_visible(True)
            self.ax.spines['bottom'].set_visible(True)
            self.canvas.draw()
            # 自适应宽度
            fig_width = max(12, total_bases * 40 / 100)
            min_width = int(fig_width * self.fig.dpi)
            self.canvas_widget.setMinimumWidth(min_width)
            self.canvas.setMinimumWidth(min_width)
        except Exception as e:
            self.ax.set_title(translations.tr("文件解析错误: {error}").format(error=str(e)))
            self.canvas.draw()

    def export_selected_seq(self):
        try:
            start = int(self.select_start.text())
            end = int(self.select_end.text())
            if start < 1 or end > len(self.ab1_seq) or start > end:
                raise ValueError
            seq = self.ab1_seq[start-1:end]  # 碱基编号从1开始
        except Exception:
            QMessageBox.warning(self, translations.tr("区间错误"), translations.tr("请输入有效的起止区间"))
            return
        file_path, _ = QFileDialog.getSaveFileName(self, translations.tr("导出序列"), "selected_seq.txt", "文本文件 (*.txt)")
        if file_path:
            with open(file_path, 'w') as f:
                f.write(seq)
            QMessageBox.information(self, translations.tr("导出成功"), translations.tr("已导出到: {path}").format(path=file_path))

    def load_seq_file(self, edit_widget):
        file_path, _ = QFileDialog.getOpenFileName(self, translations.tr("选择序列文件"), "", "FASTA/TXT文件 (*.fasta *.fa *.txt)")
        if file_path:
            with open(file_path, 'r') as f:
                seq = ''.join([line.strip() for line in f if not line.startswith('>')])
            edit_widget.setPlainText(seq)

    def run_assembly(self):
        fwd = self.fwd_edit.toPlainText().strip().upper().replace('U', 'T')
        rev = self.rev_edit.toPlainText().strip().upper().replace('U', 'T')
        if not fwd or not rev:
            QMessageBox.warning(self, translations.tr("输入错误"), translations.tr("请粘贴或加载正向和反向序列"))
            return
        rev_rc = self.reverse_complement(rev)
        overlap, merged = self.auto_assemble(fwd, rev_rc)
        if overlap < 10:
            QMessageBox.warning(self, translations.tr("拼接警告"), translations.tr("未检测到明显重叠，直接拼接两端"))
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
            QMessageBox.warning(self, translations.tr("无拼接结果"), translations.tr("请先运行拼接"))
            return
        file_path, _ = QFileDialog.getSaveFileName(self, translations.tr("保存拼接序列"), "assembled_seq.fasta", "FASTA文件 (*.fasta);;文本文件 (*.txt)")
        if file_path:
            with open(file_path, 'w') as f:
                f.write(seq)
            QMessageBox.information(self, translations.tr("保存成功"), translations.tr("已保存到: {path}").format(path=file_path))
    
    def update_language(self):
        """Update UI elements when language changes"""
        # Update GroupBox titles
        if hasattr(self, 'quality_group'):
            self.quality_group.setTitle(translations.tr("质量可视化 (支持.ab1)"))
        if hasattr(self, 'selection_group'):
            self.selection_group.setTitle(translations.tr("序列选择与导出"))
        if hasattr(self, 'assembly_group'):
            self.assembly_group.setTitle(translations.tr("序列拼接"))
        
        # Update button texts
        if hasattr(self, 'ab1_btn'):
            self.ab1_btn.setText(translations.tr("加载 .ab1 文件"))
        if hasattr(self, 'export_img_btn'):
            self.export_img_btn.setText(translations.tr("导出图片"))
        if hasattr(self, 'export_seq_btn'):
            self.export_seq_btn.setText(translations.tr("导出选定序列"))
        if hasattr(self, 'fwd_load_btn'):
            self.fwd_load_btn.setText(translations.tr("加载正向序列文件"))
        if hasattr(self, 'rev_load_btn'):
            self.rev_load_btn.setText(translations.tr("加载反向序列文件"))
        if hasattr(self, 'assemble_btn'):
            self.assemble_btn.setText(translations.tr("运行拼接"))
        if hasattr(self, 'save_assembly_btn'):
            self.save_assembly_btn.setText(translations.tr("保存拼接序列到文件"))
        
        # Update label texts
        if hasattr(self, 'select_label'):
            self.select_label.setText(translations.tr("选择区间: "))
            
        # Update placeholder texts
        if hasattr(self, 'select_start'):
            self.select_start.setPlaceholderText(translations.tr("起始"))
        if hasattr(self, 'select_end'):
            self.select_end.setPlaceholderText(translations.tr("终止"))
        if hasattr(self, 'fwd_edit'):
            self.fwd_edit.setPlaceholderText(translations.tr("粘贴正向测序序列"))
        if hasattr(self, 'rev_edit'):
            self.rev_edit.setPlaceholderText(translations.tr("粘贴反向测序序列"))
            
        # Update all QLabel widgets
        for widget in self.findChildren(QLabel):
            text = widget.text()
            if "正向序列:" in text or "Forward Sequence:" in text:
                widget.setText(translations.tr("正向序列:"))
            elif "反向序列:" in text or "Reverse Sequence:" in text:
                widget.setText(translations.tr("反向序列:"))
            elif "拼接结果：" in text or "Assembly Result:" in text:
                widget.setText(translations.tr("拼接结果："))
