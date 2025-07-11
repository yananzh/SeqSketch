from .base_tab import BaseTabWidget
from PyQt6.QtWidgets import QMessageBox, QLabel, QPushButton

class SangerTab(BaseTabWidget):
    def __init__(self, parent=None):
        super().__init__("桑格测序数据处理", parent)
        self.quality_label = QLabel("[质量分数可视化区域 - 待实现]")
        self.layout().insertWidget(1, self.quality_label)
        self.select_btn = QPushButton("选择高质量区域（待实现）")
        self.layout().insertWidget(2, self.select_btn)
        self.assemble_btn = QPushButton("序列拼接（待实现）")
        self.layout().insertWidget(3, self.assemble_btn)

    def run(self):
        self.status_label.setText("桑格测序数据处理功能待完善。请参考帮助说明。")
        self.output_text.setPlainText("[此处将显示质量分数图、拼接结果等]")

    def show_help(self):
        QMessageBox.information(self, "桑格测序数据处理 帮助", "\n- 质量分数可视化\n- 选择高质量区域\n- 序列拼接\n\n本功能支持测序质量分数图表、区域选择和序列拼接，后续将完善更多细节。") 