# BioSeq Analyzer

一个基于PyQt6的生物信息学序列分析软件，支持FASTA、FASTQ、GenBank等格式，集成多种本地和在线分析工具，界面美观，支持中英文切换。

## 主要特性
- 丰富的序列分析工具（FASTA、DNA、蛋白、比对、BLAST、引物、进化分析、收藏夹）
- **桑格测序数据处理**：支持.ab1文件解析，专业级峰图可视化，四通道信号显示，序列拼接
- 拖放文件、批量处理、结果导出、操作历史
- 现代化UI，支持浅色/深色主题
- 国际化支持（中英文）

## 桑格测序数据处理功能
- **专业峰图显示**：横坐标为碱基编号，每个主峰在对应碱基位置居中显示
- **四通道信号叠加**：同时显示G/A/T/C四通道荧光信号
- **碱基标注**：每个碱基上方显示对应的碱基字母
- **质量分数可视化**：可选的Phred质量分数显示
- **序列区域选择**：支持选择高质量区域并导出
- **正反向序列拼接**：自动检测重叠区域并拼接序列

## 安装依赖
```bash
pip install -r requirements.txt
```

## 启动方法
```bash
python main.py
```

## Windows 单文件打包（推荐）
在项目根目录执行：

```powershell
.\scripts\build_windows_onefile.ps1 -Profile balanced
```

可选 `Profile`：
- `small`：体积更小，启动略慢
- `balanced`：体积和启动速度平衡（默认）
- `fast`：启动更快，体积更大

打包产物：

```text
dist\BioSeqAnalyzer.exe
```

也可使用批处理：

```bat
scripts\build_windows_onefile.bat balanced
```

## 测试桑格测序功能
```bash
python test_sanger.py
```

## 目录结构
- main.py: 程序入口
- ui/: 界面相关代码
- modules/: 功能模块
  - fasta_processor.py: FASTA文件处理模块
  - sequence_analyzer.py: 序列分析模块
  - sanger_tab.py: **桑格测序数据处理模块**
  - example_usage.py: 使用示例
  - test_fasta_modules.py: 测试文件
- utils/: 工具函数
- resources/: 图标和语言包