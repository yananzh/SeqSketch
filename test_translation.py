#!/usr/bin/env python3
"""
测试翻译系统是否正常工作
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import translations

def test_translations():
    """测试翻译功能"""
    print("测试翻译系统...")
    
    # 测试中文翻译
    print(f"当前语言: {translations.get_current_language()}")
    
    # 测试一些关键翻译
    test_keys = [
        "从NCBI下载序列",
        "数据库:",
        "邮箱地址:",
        "NCBI要求提供邮箱地址",
        "检索号列表（每行一个）:",
        "输入检索号，每行一个\n例如:\nNM_001101.5\nNP_001092.1\nAF123456",
        "输出文件:",
        "选择位置",
        "开始下载",
        "清空",
        "保存下载的序列",
        "FASTA文件 (*.fasta *.fa *.fas);;所有文件 (*)",
        "NCBI序列下载工具",
        "功能说明：",
        "使用方法：",
        "支持的数据库：",
        "检索号格式示例：",
        "邮箱要求：",
        "应用场景：",
        "注意事项：",
        "输出格式："
    ]
    
    print("\n中文翻译测试:")
    for key in test_keys:
        translated = translations.tr(key)
        print(f"  {key} -> {translated}")
    
    # 切换到英文
    print(f"\n切换到英文...")
    translations.set_language('en_US')
    print(f"当前语言: {translations.get_current_language()}")
    
    print("\n英文翻译测试:")
    for key in test_keys:
        translated = translations.tr(key)
        print(f"  {key} -> {translated}")
    
    # 切换回中文
    print(f"\n切换回中文...")
    translations.set_language('zh_CN')
    print(f"当前语言: {translations.get_current_language()}")
    
    print("\n翻译系统测试完成!")

if __name__ == "__main__":
    test_translations()


