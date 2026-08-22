# SeqSketch

**版本 1.0.0** · **License: MIT**

一个基于 PyQt6 的生物信息学序列分析桌面应用，集成本地计算与在线数据库工具，覆盖 **FASTA 处理 → DNA/RNA/蛋白分析 → 多序列比对 → BLAST → 引物设计 → 系统发育树构建与可视化 → 桑格测序** 的完整研究流程。无需命令行，全部功能通过图形界面（Tab 页）完成。

---

## 功能总览

### 📁 FASTA 工具

| 功能 | 说明 |
| --- | --- |
| FASTA 统计 | 序列数、长度分布、GC 含量等统计信息 |
| 重命名 ID / 简化序列头 | 批量重命名、精简冗余注释 |
| 筛选 | 按 ID 列表、正则表达式、长度筛选序列 |
| 去重 / 合并 / 拆分 / 排序 | 常用 FASTA 文件整理操作 |
| FASTA ↔ 表格 | 与 Excel/CSV 表格双向转换 |
| NCBI 下载 | 在线按 accession 批量下载序列 |

### 🧬 DNA / RNA 分析

- 转换为 RNA、互补 / 反向互补、翻译（Translate）、ORF 查找
- 密码子偏好分析、限制性内切酶分析、CpG 岛查找、SSR/微卫星查找
- GC 含量 / GC 偏移绘图
- 桑格测序：峰图（色谱图）查看器、序列拼接与组装

### 🥚 蛋白分析

**本地分析**
- 氨基酸组成、理化性质（等电点/分子量等）、疏水性绘图、蛋白酶切割位点预测、序列 Logo 生成

**在线数据库链接（浏览器直达）**
- 注释与功能：UniProtKB、UniProt ID Mapping、InterPro、NCBI CD-Search、ScanProsite、MEME Suite、SignalP 6.0、DeepTMHMM 1.0、DeepLoc 2.1
- 结构与功能：PSIPRED、Jpred4、SWISS-MODEL、AlphaFold Server、AlphaFold DB、RCSB PDB、Foldseek Search、RCSB Pairwise Alignment
- 相互作用：STRING、MobiDB、HMMER (phmmer)

### 🔗 比对（Alignment）

- 双序列比对（Pairwise）、点阵图（DotPlot）
- 多序列比对：**MAFFT**、**Muscle5**
- MSA 可视化（pyMSAviz）、比对格式转换、序列 Logo（Logomaker）

### 🎯 BLAST

- NCBI 在线 BLAST（浏览器）
- 本地 BLAST（blastn / blastp 等，支持自建数据库与运行参数配置）

### 🧪 引物设计

- qPCR 引物设计（Primer3 引擎）
- 克隆引物设计（限制性酶切位点接头 PCR 引物）
- 引物分析（Tm、发夹、二聚体等）

### 🌳 系统发育

- 比对修剪：**trimAl**
- 序列拼接：分区 / 串联（Partition / Concatenation）
- 建树：距离法（UPGMA/NJ）、最大似然法（**IQ-TREE**）
- **一步式多基因系统发育分析**（One-Step MultiGenePhy）：从基因序列到多基因树的一键流程
- 树可视化（**Toytree**，支持 PNG/SVG 导出）

### ⭐ 其他

- 收藏夹管理器：书签分类管理、导入/导出 JSON / HTML、拖放排序
- 操作日志记录、检查更新、关于对话框

---

## 安装与运行

**要求：Python 3.10+（Windows）**

```bash
# 1. 克隆 / 解压项目后进入根目录，安装依赖
pip install -r requirements.txt

# 2. 安装开发依赖（pytest、ruff，可选）
pip install -r dev-requirements.txt

# 3. 启动应用
python main.py
```

> 💡 启动时若根目录存在 `start_logo.png` 会显示启动画面（可选）。任务栏图标使用 `window_logo.ico`。

---

## 快速上手

应用采用菜单 + 可关闭 Tab 的界面：

1. 通过顶部菜单栏打开对应工具（FASTA Tools / DNA Analysis / Protein Analysis / Alignment / BLAST / Primer Design / Phylogenetic Tree / Bookmarks）
2. 每个工具独立成 Tab，支持同时打开多个任务；重复打开同一工具时会聚焦已有 Tab
3. 文件类工具：选择输入文件 → 设置参数 → 点击运行；结果与操作日志显示在界面底部
4. 序列类工具：直接在文本框粘贴序列即可分析

### 教学示例数据

`examples/` 目录内置只读教学数据集，多数工具页提供 **"示例"（Example）按钮**，一键载入：

- `examples/phylo/`：8 物种 cytb 数据集（CDS、蛋白、比对、Newick 树），覆盖 FASTA 统计、翻译、理化性质、MAFFT、trimAl、IQ-TREE、树可视化 7 个教学工具链
- `examples/dna/`、`examples/protein/`、`examples/blast/`、`examples/sanger/`：各类工具的演示数据

文件类工具会先把示例复制到用户数据目录（`user_data_dir()/example_work/`）再加载，保证输出可写。

---

## 外部工具与配置

以下外部二进制默认随应用捆绑在 `softwares/` 目录：

| 工具 | 路径 | 用途 |
| --- | --- | --- |
| BLAST | `softwares/ncbi-blast-2.17.0+/bin` | 本地 BLAST 搜索 / 建库 |
| IQ-TREE | `softwares/iqtree-3.0.1-Windows/bin` | 最大似然建树 |
| MAFFT | `softwares/mafft-win_v7.526` | 多序列比对 |
| MUSCLE | `softwares/muscle-win64.v5.3.exe` | 多序列比对（Muscle5） |
| TrimAl | `softwares/trimAl_Windows_v1.5.1` | 比对修剪 |

如需使用自定义安装路径，编辑根目录 `config.ini`（相对路径相对于应用根目录解析）：

```ini
[BLAST]
bin_dir = softwares/ncbi-blast-2.17.0+/bin   ; 改为绝对路径即使用自定义安装
```

---

## 测试

```bash
# 运行全部测试（每个用例自动超时 60s，offscreen 模式运行 GUI）
py -m pytest -q

# 按模块运行
py -m pytest tests/test_fasta_tools_tabs.py -q    # FASTA 文件工具
py -m pytest tests/test_dna_analysis_tabs.py -q   # 序列分析 + 窗口/菜单接线
py -m pytest tests/test_example_data.py -q        # 示例数据加载
py -m pytest tests/test_blast_tabs.py -q
py -m pytest tests/test_primer_tabs.py -q
py -m pytest tests/test_cloning_primer_tab.py -q
py -m pytest tests/test_iqtree_tab.py -q
py -m pytest tests/test_toytree_tab.py -q
py -m pytest tests/test_distance_tree_tab.py -q
py -m pytest tests/test_partition_concat_tab.py -q
py -m pytest tests/test_one_step_multigenephy_tab.py -q
py -m pytest tests/test_one_step_multigenephy_workflow.py -q
py -m pytest tests/test_fasta_processor.py -q     # FASTA I/O 核心
py -m pytest tests/test_build_spec.py -q          # 打包配置完整性

# 代码检查
ruff check .
```

> NCBI 相关测试默认基于 mock，不会发起真实网络请求；需要联网时请自行显式开启。

---

## 打包发布（Windows 便携版）

```powershell
.\scripts\build_onedir.ps1
```

产物为 `dist/SeqSketch/`，是一个**自包含便携文件夹**（PyInstaller onedir），可整体复制到任意 Windows 机器直接运行，无需安装 Python 或外部工具。

---

## 项目结构

```
SeqSketch/
├── main.py                 # 程序入口：QApplication 引导、启动画面、全局异常捕获
├── main_window.py          # 主窗口：QTabWidget 管理、open_*_tab 方法、主题加载
├── menus.py                # 菜单栏 QAction 定义与接线
├── styles.qss              # 主样式表
├── config.ini              # 外部工具路径覆盖（可选）
├── SeqSketch.spec          # PyInstaller 打包配置
├── version_info.txt        # Windows 版本资源
├── modules/                # 功能模块（45 个独立 Tab + 支撑模块）
│   ├── fasta_processor.py  # FASTA I/O 核心（统一解析/写出）
│   ├── *_tab.py            # 各功能 Tab（共 45 个，含 primer3_gui、favorites_manager）
│   └── one_step_multigenephy_*.py  # 一步式多基因分析（io/models/workflow/tab 拆分）
├── utils/                  # 共享基础组件（BaseTabWidget/BaseWorker）、路径工具、示例数据加载
├── scripts/                # 构建脚本
├── examples/               # 教学示例数据（phylo/、dna/、protein/、blast/、sanger/）
├── softwares/              # 捆绑外部工具（BLAST、IQTree、MAFFT、MUSCLE、TrimAl）
├── resources/              # 图标、语言包、备用主题
├── config/                 # 设置管理（JSON 持久化）
├── docs/                   # 设计文档（superpowers specs/plans）
└── tests/                  # Pytest 回归测试（14 个测试文件 + conftest.py）
```

---

## 技术栈

| 类别 | 技术 |
| --- | --- |
| GUI | PyQt6 |
| 科学计算 | NumPy、Matplotlib、Pandas、Biopython |
| 引物设计 | Primer3-py |
| 序列 Logo | Logomaker |
| 系统发育可视化 | Toytree |
| MSA 可视化 | pyMSAviz |
| 表格导出 | openpyxl（Excel） |
| 打包 | PyInstaller（onedir 便携版） |
| 测试 | Pytest（timeout 60s，`QT_QPA_PLATFORM=offscreen`） |
| 代码检查 | Ruff（line-length 100，target py310） |

---

## 许可证

本项目基于 **MIT License** 开源。

## 开发者文档

- [AGENTS.md](AGENTS.md) — 架构、Tab 约定、线程与测试指导
- [docs/superpowers/specs](docs/superpowers/specs/) — 功能设计文档
- [docs/superpowers/plans](docs/superpowers/plans/) — 实施计划
