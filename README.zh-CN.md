<p align="center">
  <img src="window_logo.png" width="120" alt="SeqSketch logo" />
</p>

<h1 align="center">SeqSketch</h1>

<p align="center">
  <strong>点开即用的序列分析桌面应用 — 从原始 FASTA 到可直接发表的进化树。</strong><br/>
  基于 PyQt6，把完整研究流程 — FASTA 处理、DNA/RNA/蛋白分析、多序列比对、BLAST、引物设计、
  建树与可视化 — 收进一个标签页式图形界面，全程无需命令行。
</p>

<p align="center">
  <a href="#功能总览">功能总览</a> ·
  <a href="#下载即用">下载即用</a> ·
  <a href="#快速上手">快速上手</a> ·
  <a href="#教学示例数据">示例数据</a> ·
  <a href="#开发与测试">开发与测试</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.1-2563eb" alt="Version 1.0.1" />
  <img src="https://img.shields.io/badge/license-GPL--3.0-8b5cf6" alt="GPL-3.0" />
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS-10b981" alt="Windows | macOS" />
  <img src="https://img.shields.io/badge/python-3.10%2B-f59e0b" alt="Python 3.10+" />
</p>

[English](README.md) | 简体中文

---

SeqSketch 把生信研究人员真正在用的命令行工具 — **MAFFT、MUSCLE 5、trimAl、IQ-TREE 和 NCBI BLAST+** —
封装进图形界面，学生和科研人员无需终端即可完成完整分析。每次外部工具运行都会在输出目录的
`run_log.txt` 中记录来源信息（工具、探测到的版本、完整命令、时间戳），结果可追溯、可复现。

## 亮点

- **零配置** — Windows 与 macOS 便携版，五个外部工具随包内置
- **45 个功能 Tab** — 一个 Tab 一个功能，多任务并行
- **一步式多基因系统发育分析** — 基因 FASTA 进，串联多基因树出，一键完成
- **教学友好** — 内置示例数据集，核心工具页一键载入
- **默认可复现** — 每次工具调用都在 `run_log.txt` 留下来源记录

## 功能总览

| 模块 | 内容 |
| --- | --- |
| FASTA 工具 | 序列统计、重命名 / 简化 ID、按 ID / 正则 / 长度筛选、去重、合并、拆分、排序、FASTA ↔ Excel/CSV、NCBI 批量下载 |
| DNA / RNA | 互补 / 反向互补、转 RNA、翻译、ORF 查找、密码子偏好、限制性内切酶、CpG 岛、SSR / 微卫星、GC 含量绘图 |
| 蛋白分析 | 氨基酸组成、理化性质、疏水性绘图、蛋白酶切割位点、序列 Logo — 另有一键直达 UniProt、InterPro、AlphaFold、SWISS-MODEL、PDB、STRING 等在线数据库 |
| 序列比对 | 双序列比对、点阵图、MAFFT 与 MUSCLE 5、MSA 可视化（pyMSAviz）、比对格式转换 |
| BLAST | NCBI 在线 BLAST，或完全本地化的 blastn / blastp（含自建数据库） |
| 引物设计 | qPCR 引物（Primer3）、带酶切位点接头的克隆引物、Tm / 发夹 / 二聚体分析 |
| 系统发育 | trimAl 比对修剪、分区 / 串联、距离法建树（UPGMA / NJ）、IQ-TREE 最大似然法、树可视化（PNG / SVG 导出） |
| 桑格测序 | 峰图（色谱图）查看器、序列拼接与编辑 |
| 其他 | 收藏夹管理器（JSON / HTML 导入导出）、操作日志、检查更新 |

## 下载即用

无需安装 Python，直接从 [Releases](https://github.com/yananzh/SeqSketch/releases) 下载便携版：

| 平台 | 下载文件 | 解压后运行 |
| --- | --- | --- |
| Windows 10/11 (x64) | `SeqSketch-windows.zip` | 双击 `SeqSketch.exe` |
| macOS 11+（Apple Silicon） | `SeqSketch-Mac-arm64.zip` | 双击 `SeqSketch.app` |
| macOS 11+（Intel） | `SeqSketch-Mac-x86_64.zip` | 双击 `SeqSketch.app` |

解压后的文件夹完全便携，可任意移动；首次运行会在程序目录旁创建 `user_data/`，存放配置与收藏夹。

> [!TIP]
> 不确定用哪个 Mac 版本？点左上角苹果菜单 →「关于本机」：**芯片**显示 *Apple M…* 就选 `arm64`，
> 显示 *Intel* 就选 `x86_64`。

> [!WARNING]
> **当前构建未做代码签名，首次运行会被系统拦截。**
>
> - **Windows** — SmartScreen 提示「Windows 已保护你的电脑」：点*更多信息* → *仍要运行*。
> - **macOS** — 提示「无法打开，因为 Apple 无法检查其是否包含恶意软件」：在 Finder 中右键点 App → *打开*（只需一次）。
>
> 想彻底消除提示需要代码签名（Windows 需 OV/EV 证书；macOS 需 Apple Developer 账号，$99/年）。

## 快速上手

应用采用「菜单栏 + 可关闭 Tab」的界面：

1. 从菜单栏打开工具（FASTA Tools / DNA Analysis / Protein Analysis / Alignment / BLAST /
   Primer Design / Phylogenetic Tree / Bookmarks）
2. 每个工具独立成 Tab；重复打开同一工具会聚焦已有 Tab
3. **文件类工具** — 选择输入文件 → 设置参数 → 运行；结果与操作日志显示在 Tab 底部
4. **序列类工具** — 直接把序列粘贴进文本框即可分析

## 教学示例数据

`examples/` 内置只读教学数据集，每个核心工具页都有 **Example（示例）按钮**，一键载入：

- `examples/phylo/` — 8 物种 cytb 数据集（CDS、蛋白、比对结果、Newick 树），贯穿 7 个教学工具链：
  FASTA 统计 → 翻译 → 理化性质 → MAFFT → trimAl → IQ-TREE → 树可视化
- `examples/dna/`、`examples/protein/`、`examples/blast/`、`examples/sanger/` — 其余工具的演示数据

文件类工具会先把示例复制到 `user_data/example_work/` 再加载，保证输出可写。

## 从源码运行

需要 **Python 3.10+**。

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 开发依赖（pytest、ruff）— 可选
pip install -r dev-requirements.txt

# 3. 拉取外部工具二进制（约 580 MB，已 gitignore）
powershell -ExecutionPolicy Bypass -File scripts/fetch_softwares.ps1

# 4. 启动应用
python main.py
```

> [!NOTE]
> 跳过第 3 步应用仍能启动，但外部工具类功能会提示 "not found"。
> 仓库为私有时需先 `gh auth login`。脚本也支持完全离线安装：
> `./scripts/fetch_softwares.ps1 -Archive <压缩包路径> -Force`。

## 外部工具与配置

外部二进制按平台存放在 `softwares/` 子目录（不纳入版本控制，以 Release 资产分发）。
路径由 `utils/tool_paths.py` 按平台自动解析，工具目录名带版本号，升级后无需改代码：

| 工具 | 版本 | 用途 |
| --- | --- | --- |
| NCBI BLAST+ | 2.17.0+ | 本地 BLAST 搜索 / 建库 |
| MAFFT | v7.526 | 多序列比对 |
| MUSCLE | v5.3 | 多序列比对（Muscle5） |
| IQ-TREE | 3.1.3 | 最大似然法建树 |
| trimAl | 1.5.1 | 比对修剪 |

如需使用自定义安装（例如系统已装 BLAST+），编辑根目录 `config.ini`（留空即使用捆绑副本）：

```ini
[BLAST]
bin_dir = C:/tools/ncbi-blast-2.17.0+/bin
```

## 开发与测试

```bash
py -m pytest -q                   # 全量测试（每个用例 60s 超时，GUI 以 offscreen 模式运行）
ruff check .                      # 代码检查
.\scripts\build_onedir.ps1 -Zip   # 构建便携版 + 发布 zip
```

- 测试全部基于 fixture，外部工具与网络调用均已 mock；CI 在 `windows-latest` 和 `macos-15` 上运行。
- 打 tag 发布（`git tag v1.0.0 && git push origin v1.0.0`）会触发 `.github/workflows/release.yml`，
  分别在 Windows、macOS Apple Silicon 和 Intel 上构建并上传 `SeqSketch-windows.zip`、
  `SeqSketch-Mac-arm64.zip`、`SeqSketch-Mac-x86_64.zip` 到对应 GitHub Release。
  工作流从 `tools-v1` Release 拉取工具包（由 `scripts/pack_softwares.ps1` 生成并上传）。

项目结构：

```
SeqSketch/
├── main.py / main_window.py / menus.py   # 程序引导、Tab 管理、菜单接线
├── modules/        # 功能 Tab（每个 Tab 一个文件；fasta_processor.py 为 FASTA I/O 核心）
├── utils/          # 共享 UI 基类、路径与工具解析、示例数据加载
├── examples/       # 内置教学数据集
├── scripts/        # 构建 / 拉取 / 打包脚本
├── softwares/      # 外部工具（需拉取，已 gitignore）
└── tests/          # pytest 回归测试
```

## 许可与来源

Copyright (C) 2026 yananzh

本项目以 GNU General Public License v3.0（SPDX：`GPL-3.0-only`）发布，完整条款见 [LICENSE](LICENSE)：
SeqSketch 链接的 PyQt6 为 GPL-3.0-only，因此整体作品必须以相同条款分发。随包的命令行工具均为
未修改的官方发行版，许可证文本随各自目录一同分发；完整依赖许可清单见
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)。注意 MAFFT 扩展组件禁止以收费方式再分发 —
详见 MAFFT 目录内的 `MAFFT-EXTENSIONS-NOTICE.txt`。
