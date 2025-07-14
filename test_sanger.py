#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
桑格测序数据处理模块测试脚本
测试.ab1文件解析和可视化功能
"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.sanger_tab import SangerTab

def test_sanger_tab():
    """测试桑格测序数据处理模块"""
    app = QApplication(sys.argv)
    
    # 创建桑格测序Tab
    sanger_tab = SangerTab()
    sanger_tab.show()
    
    print("桑格测序数据处理模块测试")
    print("功能包括：")
    print("1. .ab1文件加载和解析")
    print("2. 四通道信号可视化（G/A/T/C）")
    print("3. 碱基峰图显示（类似SnapGene）")
    print("4. 质量分数显示")
    print("5. 序列区域选择和导出")
    print("6. 正反向序列拼接")
    print("\n请点击'加载.ab1文件'按钮来测试功能")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    test_sanger_tab() 