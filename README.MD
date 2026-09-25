# SeqSketch

**版本 1.0.0** · **GPL-3.0** — 见 [许可与来源](#许可与来源)

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

## 下载即用

不需要安装 Python，直接从 [Releases](https://github.com/yananzh/SeqSketch/releases) 下载对应平台的压缩包：

| 平台 | 下载文件 | 解压后 |
| --- | --- | --- |
| Windows 10/11 (x64) | `SeqSketch-windows.zip` | 双击 `SeqSketch.exe` |
| macOS 11+ — Apple Silicon（M 系列） | `SeqSketch-Mac-arm64.zip` | 双击 `SeqSketch.app` |
| macOS 11+ — Intel | `SeqSketch-Mac-x86_64.zip` | 双击 `SeqSketch.app` |

便携版：解压后整个文件夹可任意移动，首次运行会在程序目录旁创建 `user_data/` 存放配置与收藏夹。
外部工具（BLAST / IQ-TREE / MAFFT / MUSCLE / trimAl）已随包内置，无需单独安装。

> 💡 不确定是哪种 Mac？点左上角  →「关于本机」：「芯片」显示 **Apple M…** 就下 `arm64`，显示 **Intel** 就下 `x86_64`。

> ⚠️ **首次运行会被系统拦截**：当前构建**未做代码签名**，系统会提示来源不明。
>
> - **Windows**：SmartScreen 提示「Windows 已保护你的电脑」→ 点「更多信息」→「仍要运行」
> - **macOS**：提示「无法打开，因为 Apple 无法检查其是否包含恶意软件」→ 在 Finder 中**右键点 App → 打开**（只需一次）
>
> 想消除该提示需要代码签名（Windows OV/EV 证书；macOS 需 Apple Developer 账号，$99/年）。

---

## 从源码运行

如果你要改代码或参与开发：

**要求：Python 3.10+**

```bash
# 1. 克隆 / 解压项目后进入根目录，安装依赖
pip install -r requirements.txt

# 2. 安装开发依赖（pytest、ruff，可选）
pip install -r dev-requirements.txt

# 3. 拉取外部工具二进制（BLAST / IQ-TREE / MAFFT / MUSCLE / trimAl）
#    softwares/ 约 580 MB 且为第三方二进制，未纳入版本控制
powershell -ExecutionPolicy Bypass -File scripts/fetch_softwares.ps1

# 4. 启动应用
python main.py
```

> 💡 跳过第 3 步应用仍能启动，但外部工具类功能会提示 “not found”。
> 仓库为私有，下载需先 `gh auth login`；若已有压缩包可用 `-Archive` 完全离线安装：
> `./scripts/fetch_softwares.ps1 -Archive D:\softwares-windows.zip -Force`

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

外部二进制按平台存放在 `softwares/` 子目录，**不纳入版本控制**（体积大且为第三方二进制），
以 Release 资产分发，由 `scripts/fetch_softwares.ps1` 拉取（自动识别平台）：

| 工具 | Windows | macOS | 用途 |
| --- | --- | --- | --- |
| BLAST | `windows/ncbi-blast-2.17.0+/bin/blastn.exe` | `Mac/ncbi-blast-2.17.0-macOS/bin/blastn` | 本地 BLAST 搜索 / 建库 |
| IQ-TREE | `windows/iqtree-3.1.3-Windows/bin/iqtree3.exe` | `Mac/iqtree-3.1.3-macOS/bin/iqtree3` | 最大似然建树 |
| MAFFT | `windows/mafft-win_v7.526/mafft.bat` | `Mac/mafft-7.526-macOS/mafft.bat` | 多序列比对 |
| MUSCLE | `windows/muscle-win64.v5.3.exe` | `Mac/muscle-5.3-MacOS-<arch>` | 多序列比对（Muscle5） |
| TrimAl | `windows/trimAl_Windows_v1.5.1/trimal.exe` | `Mac/trimAl-1.51-MacOS-<arch>/bin/trimal` | 比对修剪 |

工具路径由 `utils/tool_paths.py` 按平台自动解析（目录名带版本号，升级后无需改代码）。

如需使用自定义安装（例如系统已装 BLAST+），编辑根目录 `config.ini`（留空即自动探测捆绑副本）：

```ini
[BLAST]
bin_dir = C:/tools/ncbi-blast-2.17.0+/bin   ; 改为绝对路径即使用自定义安装
```

维护者升级工具后需重新打包并上传 Release 资产：

```powershell
.\scripts\pack_softwares.ps1                 # 生成 dist/softwares-windows.zip，并打印 SHA256
gh release upload tools-v1 dist/softwares-windows.zip --clobber
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

## 打包发布

本地构建便携版（Windows 与 macOS 均可运行同一脚本，自动识别平台）：

```powershell
.\scripts\build_onedir.ps1 -Zip
```

- Windows 产物：`dist/SeqSketch/` + 发布归档 `dist/SeqSketch-windows.zip`
- macOS 产物：`dist/SeqSketch.app` + 发布归档 `dist/SeqSketch-Mac-<arch>.zip`（`arch` 为 `arm64` 或 `x86_64`）

归档是一个自包含便携包（PyInstaller onedir，已内置外部工具），可直接分发，用户无需安装 Python。

发布正式版本（**需先上传工具包**，见下）：

```bash
git tag v1.0.0
git push origin v1.0.0          # 触发 .github/workflows/release.yml
```

工作流会在 Windows、macOS Apple Silicon 和 macOS Intel 上分别跑测试 → 拉取工具 → 构建 → 打包，
然后把三个 zip 上传到对应的 GitHub Release。

**前置条件：`softwares/` 是 gitignored 的**，CI 通过 `scripts/fetch_softwares.ps1`
从 `tools-v1` Release 拉取。首次发布前必须先创建该 Release 并上传两个工具包：

```powershell
.\scripts\pack_softwares.ps1                  # → dist/softwares-windows.zip
.\scripts\pack_softwares.ps1 -Platform Mac    # → dist/softwares-Mac.zip（需在 macOS 上执行）
gh release create tools-v1 --title 'Bundled tools' --notes 'External tool bundles for SeqSketch'
gh release upload tools-v1 dist/softwares-windows.zip dist/softwares-Mac.zip --clobber
```

升级某个外部工具后重新执行这两步（`--clobber` 会覆盖旧资产），无需修改任何代码。

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
├── scripts/                # 构建脚本（build_onedir / pack_softwares / fetch_softwares）
├── examples/               # 教学示例数据（phylo/、dna/、protein/、blast/、sanger/）
├── softwares/              # 外部工具（BLAST、IQTree、MAFFT、MUSCLE、TrimAl）— 需 fetch 拉取
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

## 许可与来源

本项目以 **GNU General Public License v3.0**（SPDX：`GPL-3.0-only`）发布，完整条款见 [LICENSE](LICENSE)。

```
SeqSketch — Sequence Analysis & Visualization Toolkit
Copyright (C) 2026 yananzh

本程序是自由软件：你可以依据自由软件基金会发布的 GNU 通用公共许可证第 3 版的
条款重新分发和/或修改它。

本程序的分发是希望它有用，但不提供任何担保，甚至没有适销性或特定用途适用性的
默示担保。详见 GNU 通用公共许可证。

你应当已随本程序收到一份 GNU 通用公共许可证副本；如果没有，见
<https://www.gnu.org/licenses/>。
```

**为什么是 GPL-3.0**：应用链接的 **PyQt6 6.10.0** 在安装元数据中声明 `License-Expression: GPL-3.0-only`，
因此打包分发的 SeqSketch 是包含 GPL-3.0-only 组件的组合作品，必须以 GPL-3.0 兼容的条件提供。
其余著佐权组件均兼容：`primer3-py` 为 GPL-2.0-or-later（源码头声明 "or any later version"，可采用
GPL-3.0）、`patchworklib` 为 GPL-3.0；`toytree`（BSD-3-Clause）与 `sangerseq-viewer`（MIT）不产生著佐权
义务。完整依赖清单见 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) 第 3、5 节。

**再分发注意**：源码即本仓库；修改版同样需以 GPL-3.0 发布，并保留版权与许可声明。
若以收费方式分发，请先阅读下方 MAFFT 扩展组件的限制。

### 随包分发的第三方工具

下载包中的 `softwares/` 目录包含下列命令行工具的**未修改**官方发行版。各自的许可证文件随二进制一同分发，
就位于对应工具目录内（例如 `softwares/windows/ncbi-blast-2.17.0+/LICENSE`、
`softwares/Mac/mafft-7.526-macOS/MAFFT-LICENSE.txt`）。

| 工具 | 版本 | 许可证 | 上游来源 |
| --- | --- | --- | --- |
| NCBI BLAST+ | 2.17.0+ | Public Domain（美国政府作品） | <https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/> |
| MAFFT | v7.526 | 核心 BSD-3-Clause；上游将含扩展的包标注为 GPL | <https://mafft.cbrc.jp/alignment/software/> |
| IQ-TREE | 3.1.3 | GPL-2.0 | <https://github.com/iqtree/iqtree3> |
| trimAl | 1.5.1 | GPL-3.0 | <https://github.com/scapella/trimal> |
| MUSCLE | v5.3 | GPL-3.0 | <https://github.com/rcedgar/muscle> |

GPL 组件的完整对应源码可从上表的上游地址按**相同版本**获取；若届时无法获取，可通过
[Issues](https://github.com/yananzh/SeqSketch/issues) 索取，免费提供。命令行工具仅对输入输出做文件级调用，
未做任何修改。

### 许可限制

- **MAFFT 扩展组件**（Vienna RNA package、MXSCARNA、ProbConsRNA）允许免费使用与修改（含商业用途），
  但**不得以任何费用再分发**（媒体成本除外）。SeqSketch 免费提供，符合该条件；若将来改为收费分发，
  须另行取得上游作者授权。详见包内 `MAFFT-EXTENSIONS-NOTICE.txt`。
- 应用本身还打包了若干 Python 组件：PyQt6（GPL-3.0-only）、primer3-py（GPL-2.0-or-later，其源码头声明
  "or any later version"，故可采用 GPL-3.0）、patchworklib（GPL-3.0）为强著佐权许可；其余（NumPy、pandas、
  SciPy、Biopython、Matplotlib、requests、toytree、sangerseq-viewer 等）为 BSD/MIT/Apache 类宽松许可。
  各组件许可正文随应用分发在 `third_party_licenses/python/` 目录下，完整清单见
  [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)。
- Windows 版包含 MinGW-w64 运行时 DLL（`libgcc_s_seh-1.dll`、`libstdc++-6.dll`、`libwinpthread-1.dll`），
  按 GPL-3.0 + GCC Runtime Library Exception 分发，不会限制本程序自身的许可证选择。

## 开发者文档

- [AGENTS.md](AGENTS.md) — 架构、Tab 约定、线程与测试指导
- [docs/superpowers/specs](docs/superpowers/specs/) — 功能设计文档
- [docs/superpowers/plans](docs/superpowers/plans/) — 实施计划
