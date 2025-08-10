# BioSeq Analyzer - Modules 功能模块

本目录包含BioSeq Analyzer的各种功能模块，提供生物信息学序列分析的核心功能。

## 模块结构

```
modules/
├── __init__.py              # 模块包初始化文件
├── fasta_processor.py       # FASTA文件处理模块
├── sequence_analyzer.py     # 序列分析模块
├── primer3_gui.py          # Primer3引物设计GUI模块
├── primer_gui.py           # 通用引物设计GUI模块
├── example_usage.py         # 使用示例
├── test_fasta_modules.py    # 测试文件
└── README.md               # 本说明文档
```

## 主要模块

### 1. FASTA文件处理模块 (`fasta_processor.py`)

提供FASTA文件的读取、解析、验证、统计等功能。

#### 主要类和方法：

**FASTARecord类**
- 表示单个FASTA记录
- 包含序列头部、序列内容、描述信息
- 提供GC含量计算、碱基组成统计等方法

**FASTAProcessor类**
- `read_file(file_path)`: 读取FASTA文件
- `validate_file()`: 验证文件格式
- `get_statistics()`: 获取文件统计信息
- `filter_sequences()`: 根据条件过滤序列
- `save_file()`: 保存FASTA文件
- `search_sequences()`: 搜索序列
- `get_sequence_by_id()`: 根据ID获取序列
- `create_reverse_complement_records()`: 创建反向互补序列

**批量处理函数**
- `batch_process_fasta_files()`: 批量处理多个FASTA文件

#### 使用示例：

```python
from modules.fasta_processor import FASTAProcessor

# 创建处理器
processor = FASTAProcessor()

# 读取文件
if processor.read_file("example.fasta"):
    # 获取统计信息
    stats = processor.get_statistics()
    print(f"序列数量: {stats['total_sequences']}")
    
    # 过滤序列
    filtered = processor.filter_sequences(min_length=100, min_gc=40)
    print(f"符合条件的序列: {len(filtered)}")
    
    # 保存结果
    processor.save_file("output.fasta", filtered)
```

### 2. 序列分析模块 (`sequence_analyzer.py`)

提供序列分析、比对、统计等功能，支持DNA和蛋白质序列分析。

#### 主要功能：

**DNA序列分析**
- `analyze_dna_sequence()`: 分析DNA序列
- `translate_dna()`: DNA翻译为蛋白质
- 重复序列检测
- 限制性酶切位点查找

**蛋白质序列分析**
- `analyze_protein_sequence()`: 分析蛋白质序列
- 分子量计算
- 等电点估算
- 疏水性分析
- 二级结构预测

**序列比较**
- `calculate_similarity()`: 计算序列相似性
- `find_motifs()`: 基序搜索

#### 使用示例：

```python
from modules.sequence_analyzer import SequenceAnalyzer

# 创建分析器
analyzer = SequenceAnalyzer()

# DNA序列分析
dna_sequence = "ATGGCCTTTGGTGCAGGCCTCCTGGCCTCTGCTGGCTGCCTGGCTTCTGCCTCGGCCTCTCAGGCATCA"
dna_analysis = analyzer.analyze_dna_sequence(dna_sequence)
print(f"GC含量: {dna_analysis['gc_content']}%")

# DNA翻译
protein = analyzer.translate_dna(dna_sequence, frame=1)
print(f"翻译结果: {protein}")

# 蛋白质分析
protein_analysis = analyzer.analyze_protein_sequence(protein)
print(f"分子量: {protein_analysis['molecular_weight']} Da")

# 序列比较
similarity = analyzer.calculate_similarity(seq1, seq2)
print(f"相似性: {similarity['similarity_percentage']}%")
```

## 安装和依赖

确保已安装以下依赖包：

```bash
pip install -r requirements.txt
```

主要依赖：
- `biopython>=1.81`: 生物信息学工具包
- `numpy>=1.21.0`: 数值计算
- `pathlib2>=2.3.7`: 路径处理
- `typing-extensions>=4.0.0`: 类型提示扩展

## 运行示例

### 运行使用示例：

```bash
cd modules
python example_usage.py
```

### 运行测试：

```bash
cd modules
python test_fasta_modules.py
```

## 功能特性

### FASTA文件处理特性：
- ✅ 支持标准FASTA格式
- ✅ 文件格式验证
- ✅ 序列统计信息
- ✅ 序列过滤和搜索
- ✅ 批量处理
- ✅ 反向互补序列生成
- ✅ 文件保存和导出

### 序列分析特性：
- ✅ DNA序列分析（GC含量、碱基组成、重复序列、限制性酶切位点）
- ✅ DNA翻译（6个阅读框）
- ✅ 蛋白质序列分析（分子量、等电点、疏水性、二级结构预测）
- ✅ 序列相似性计算
- ✅ 基序搜索（支持正则表达式）
- ✅ 编辑距离计算

## 扩展开发

### 添加新的分析功能：

1. 在相应的模块文件中添加新的方法
2. 更新`__init__.py`文件中的导入
3. 添加相应的测试用例
4. 更新文档

### 添加新的文件格式支持：

1. 创建新的处理器类（参考`FASTAProcessor`）
2. 实现标准的接口方法
3. 添加格式验证功能
4. 编写测试用例

### 3. 引物设计模块

#### primer3_gui.py - Primer3引物设计GUI
基于primer3-py库的PCR引物设计工具，提供图形界面。

**主要功能：**
- 常规引物设计（扩增内部片段）
- 特定区域设计（在指定区域内）
- 全长克隆设计（扩增完整模板）
- 引物参数优化（长度、Tm值、GC含量）
- 结果表格显示和导出

**使用示例：**
```python
from modules.primer3_gui import MainWindow as Primer3MainWindow

# 创建Primer3设计窗口
primer_window = Primer3MainWindow()
primer_window.show()
```

#### primer_gui.py - 通用引物设计GUI
另一个引物设计界面实现，提供不同的用户体验。

**主要功能：**
- 基于primer3核心算法
- 详细的参数设置
- 结果可视化
- 引物对评估

**使用示例：**
```python
from modules.primer_gui import MainWindow as PrimerMainWindow

# 创建通用引物设计窗口
primer_window = PrimerMainWindow()
primer_window.show()
```

## 注意事项

1. **文件编码**: 所有文件操作使用UTF-8编码
2. **序列格式**: 序列自动转换为大写字母
3. **内存使用**: 大文件处理时注意内存使用情况
4. **错误处理**: 所有方法都包含适当的错误处理
5. **日志记录**: 使用Python标准logging模块记录操作日志
6. **引物设计依赖**: primer3_gui需要安装primer3-py包

## 贡献指南

1. 遵循PEP 8代码风格
2. 添加适当的类型提示
3. 编写详细的文档字符串
4. 添加单元测试
5. 更新相关文档

## 许可证

本项目采用MIT许可证，详见项目根目录的LICENSE文件。 