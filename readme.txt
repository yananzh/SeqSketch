# BioSeq Analyzer

一个基于PyQt6的生物信息学序列分析软件，支持FASTA、FASTQ、GenBank等格式，集成多种本地和在线分析工具，界面美观，支持中英文切换。

## 主要特性
- 丰富的序列分析工具（FASTA、DNA、蛋白、比对、BLAST、引物、进化分析、收藏夹）
- 拖放文件、批量处理、结果导出、操作历史
- 现代化UI，支持浅色/深色主题
- 国际化支持（中英文）

## 安装依赖
```bash
pip install -r requirements.txt
```

## 启动方法
```bash
python main.py
```

## 目录结构
- main.py: 程序入口
- ui/: 界面相关代码
- modules/: 功能模块
  - fasta_processor.py: FASTA文件处理模块
  - sequence_analyzer.py: 序列分析模块
  - example_usage.py: 使用示例
  - test_fasta_modules.py: 测试文件
- utils/: 工具函数
- resources/: 图标和语言包