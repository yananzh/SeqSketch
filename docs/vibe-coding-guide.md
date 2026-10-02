# 用 Vibe Coding 从零复现 SeqSketch —— 零基础逐步指南

> **这份指南写给谁**：不会编程、也没做过生物信息学，但想亲手"复刻"出 SeqSketch 这个序列分析桌面软件的人。
> **你不需要**：任何编程经验。**你需要**：一台 Windows 或 Mac 电脑、能上网、愿意一步步照着做。
> **预计投入**：跟随本指南走完全部里程碑，约 3~7 个工作日（每天 2~4 小时）。

---

## 目录

1. [什么是 Vibe Coding](#1-什么是-vibe-coding)
2. [你要复现的东西长什么样](#2-你要复现的东西长什么样)
3. [术语速查表](#3-术语速查表)
4. [准备工作：装好三样东西](#4-准备工作装好三样东西)
5. [和 AI 打交道的核心心法](#5-和-ai-打交道的核心心法)
6. [里程碑 0：让第一个窗口弹出来](#里程碑-0让第一个窗口弹出来)
7. [里程碑 1：主窗口 + 菜单 + 第一个功能页](#里程碑-1主窗口--菜单--第一个功能页)
8. [里程碑 2：FASTA 文件工具箱](#里程碑-2fasta-文件工具箱)
9. [里程碑 3：DNA / RNA / 蛋白分析页](#里程碑-3dna--rna--蛋白分析页)
10. [里程碑 4：接入外部工具（比对与建树）](#里程碑-4接入外部工具比对与建树)
11. [里程碑 5：本地 BLAST](#里程碑-5本地-blast)
12. [里程碑 6：引物设计与桑格测序](#里程碑-6引物设计与桑格测序)
13. [里程碑 7：示例数据、收藏夹与外观](#里程碑-7示例数据收藏夹与外观)
14. [里程碑 8：自动化测试与代码检查](#里程碑-8自动化测试与代码检查)
15. [里程碑 9：打包成免安装的 exe](#里程碑-9打包成免安装的-exe)
16. [全部功能页与里程碑对照表](#全部功能页与里程碑对照表)
17. [常见问题排查（FAQ）](#常见问题排查faq)
18. [附录：给 AI 的"项目宪法"（可整段复制）](#附录给-ai-的项目宪法可整段复制)

---

## 1. 什么是 Vibe Coding

**Vibe coding**（氛围编程 / 凭感觉编程）是一种新的编程方式：**你用自然语言告诉 AI 你想要什么，AI 负责写代码，你负责验收结果**。你不逐行读懂代码，而是像产品经理一样：

- 说清楚"我要一个什么样的功能"；
- 运行程序，检查它是否照做；
- 不对就把**报错信息或现象**贴回给 AI，让它修。

术语解释（现在出现，后面不再重复）：

| 术语 | 意思 |
| --- | --- |
| **AI 编程助手** | 能读写你电脑上文件、执行命令的 AI 工具，如 ZCode、Claude Code、Cursor 等。本指南的提示词对哪款都适用。 |
| **提示词（Prompt）** | 你发给 AI 的指令文字。本指南每个里程碑都给了可直接复制的提示词。 |
| **验收（Acceptance）** | 用"看得见的行为"判断功能是否合格，例如"粘贴序列后点 Run，输出框里出现反向互补序列"。 |

> ⚠️ **本指南的一个约定**：所有让 AI 生成的界面文字都用**英文**（按钮叫 "Run" 而不是"运行"）。这是 SeqSketch 项目本身的设计决定（界面只做英文），照做可以避免编码乱码问题。

---

## 2. 你要复现的东西长什么样

SeqSketch 是一个**桌面图形界面程序**（就是你双击打开、有窗口和按钮的那种），面向生物学教学与科研，覆盖一条完整的序列分析流程：

```
拿到序列(FASTA文件)
   ↓
FASTA 整理（统计 / 重命名 / 筛选 / 去重 / 合并拆分）
   ↓
DNA / RNA / 蛋白分析（翻译、GC含量、理化性质……）
   ↓
多序列比对（MAFFT / MUSCLE）→ 修剪（trimAl）
   ↓
BLAST 比对搜索（本地数据库）
   ↓
引物设计（Primer3）/ 桑格测序峰图
   ↓
系统发育树（距离法 / IQ-TREE 最大似然）→ 树可视化
```

它有 **45 个功能页（Tab）**，通过顶部菜单打开。本指南带你先把**骨架和最典型的 7 页教学链**做出来（里程碑 0~4），其余页面照着对照表批量复刻即可——因为它们高度相似，AI 会越写越快。

---

## 3. 术语速查表

### 3.1 编程侧术语

| 术语 | 一句话解释 |
| --- | --- |
| **Python** | 一种编程语言，语法接近英语，适合快速开发。本项目的"母语"。 |
| **解释器** | 运行 `.py` 文件的程序。装 Python = 装这个解释器。命令 `python xxx.py` 就是让它执行文件。 |
| **pip** | Python 的"应用商店"命令行工具，用来安装别人写好的代码包。`pip install PyQt6` 就是下载安装 PyQt6。 |
| **包 / 依赖（package / dependency）** | 别人写好、可直接复用的代码库。你的程序"依赖"它们，所以要一次性列在 `requirements.txt` 里。 |
| **虚拟环境（venv）** | 一个隔离的"沙盒"文件夹，把你这个项目装的包和其他项目分开，避免版本冲突。 |
| **终端 / 命令行（Terminal）** | 一个用打字代替点鼠标的操作界面。Windows 上推荐 PowerShell；本指南所有命令都在这里输入。 |
| **Git** | 代码"存档系统"：每个阶段 `git commit` 打一个存档点，写坏了随时回退。GitHub 是存放存档的网站。 |
| **GUI** | Graphical User Interface，图形用户界面，即"有窗口按钮的程序"（区别于黑乎乎的命令行程序）。 |
| **PyQt6** | 一个 Python 库，用来画 GUI。窗口、按钮、菜单、表格都由它提供。 |
| **Widget（控件）** | 界面上的一个零件：按钮、输入框、下拉框都是 widget。 |
| **Tab（标签页）** | 浏览器那种"一排可切换、可关闭的页面"。本项目每个功能就是一个 Tab。 |
| **信号与槽（signal / slot）** | PyQt 的事件机制："当按钮被**点击**（信号），就执行**这个函数**（槽）"。 |
| **主线程 / 工作线程（thread）** | 线程 = 干活的工人。界面由"主线程"绘制；耗时的计算如果也在主线程做，窗口会"卡死"，所以要派一个"工作线程"在后台算。 |
| **模块 / import** | 一个 `.py` 文件就是一个模块。`import xxx` 表示"借用另一个文件里的代码"。 |
| **类（class）与对象** | 类是"图纸"，对象是按图纸造出的"实物"。例如 `MainWindow` 是图纸，程序启动时 `MainWindow()` 造出真正的窗口。 |
| **pytest** | 自动化测试工具：写一些小程序自动检查功能是否正常，改代码后跑一遍就知道有没有改坏。 |
| **ruff** | 代码"体检工具"：检查代码风格问题（如一行太长），不查功能对错。 |
| **PyInstaller** | 把 Python 程序 + Python 本身 + 所有依赖打成一个**免安装文件夹**（里面有个 exe 可双击）的工具。 |
| **subprocess** | Python 里"调用另一个外部程序"的方法。本项目用它调用 MAFFT、BLAST 等命令行工具。 |

### 3.2 生物信息侧术语

| 术语 | 一句话解释 |
| --- | --- |
| **序列（sequence）** | 一串生物大分子的字母表示。DNA 用 A/T/C/G，蛋白用 20 个氨基酸单字母缩写。 |
| **FASTA 格式** | 存序列最通用的文本格式：第一行以 `>` 开头是名字（header），下面若干行是序列本身。 |
| **header / ID** | `>` 后面那行。第一个空格前是 ID（编号），后面是描述。很多工具靠 ID 匹配序列。 |
| **GC 含量** | 序列里 G 和 C 占的百分比——GC 比 AT 结合更牢，含量常与基因表达、物种相关。 |
| **互补 / 反向互补** | DNA 双链配对规则 A↔T、G↔C。"反向互补"是设计引物时最常用的变换。 |
| **翻译（Translate）** | 把 DNA 按密码子表翻成蛋白序列（每 3 个碱基对应 1 个氨基酸）。 |
| **ORF** | Open Reading Frame，开放阅读框：从起始密码子到终止密码子、能翻译出蛋白的一段 DNA。 |
| **密码子偏好（codon usage）** | 不同物种偏爱用不同的同义密码子，可用来预测基因来源物种。 |
| **IUPAC 模糊码** | 除 ACGT 外的歧义碱基字母，如 R=A或G，N=任意碱基。 |
| **限制性内切酶（restriction enzyme）** | 在特定短序列处切断 DNA 的酶（如 EcoRI 切 GAATTC），克隆实验用它来"剪"DNA。 |
| **引物（primer）** | 一小段人工合成的单链 DNA，PCR 扩增的"起点"。设计引物要算 Tm（解链温度）、避免发夹和引物二聚体。 |
| **qPCR** | 实时定量 PCR，用引物扩增并测量目标 DNA 的量。 |
| **比对（alignment）** | 把多条序列"上下对齐"，让相同/相似的字母对齐到同一列，用来比较相似度、找保守位点。 |
| **MSA（Multiple Sequence Alignment）** | 多序列比对，2 条以上。**MAFFT** 和 **MUSCLE** 是两个最常用的比对软件。 |
| **比对修剪（trim）** | 比对结果里有些列全是空位或质量差，建树前把它剪掉。工具叫 **trimAl**。 |
| **BLAST** | "用一条序列在数据库里搜相似序列"的工具，生信里最经典的搜索。本地版 = 把数据库下载/建在自己电脑上。 |
| **系统发育树（phylogenetic tree）** | 表示物种/序列进化关系的"家谱树"。常用建树方法：距离法（UPGMA/NJ）、最大似然法（**IQ-TREE**）。 |
| **Newick 格式** | 树文件的文本格式，如 `(A:0.1,(B:0.2,C:0.3):0.4);`，括号表示分支嵌套。 |
| **自展值（bootstrap）** | 建树时反复重抽样来评估每个分支的可信度，数值越高越可信（通常 >70 算可靠）。 |
| **SSR / 微卫星** | 短序列重复多次（如 ATATAT…），常用作分子标记。 |
| **CpG 岛** | GC 含量高、C 后常跟 G 的区域，多位于基因启动子附近。 |
| **桑格测序（Sanger sequencing）** | 经典一代测序，产出 `.ab1` 峰图文件（chromatogram），本项目的查看器/拼接器就是处理它。 |

---

## 4. 准备工作：装好三样东西

### 4.1 安装 Python（约 5 分钟）

1. 打开 <https://www.python.org/downloads/>，下载 **Python 3.10 或更高版本**（本项目要求 3.10+）。
2. Windows 安装时**务必勾选 "Add python.exe to PATH"**（把它加入系统路径，终端才能认识 `python` 命令）。
3. 验证：打开 PowerShell（Windows 键 → 输入 powershell → 回车），输入：

```powershell
python --version    # 应显示 Python 3.10.x 或更高
```

> Mac 用户把 `python` 换成 `python3` 即可。

### 4.2 安装 AI 编程助手（约 10 分钟）

任选其一并按官网指引安装：**ZCode** / **Claude Code** / **Cursor**。安装后，在**你的项目文件夹**里启动它——AI 助手会以当前文件夹为"工作区"读写文件。

### 4.3 建立项目文件夹并让 AI 初始化（约 5 分钟）

在资源管理器里新建一个空文件夹，例如 `F:\SeqSketch-MyBuild`，然后**在其中打开终端和 AI 助手**，输入第一条提示词：

```text
我要在当前空文件夹里从零复现一个名为 SeqSketch 的生物信息学桌面应用（Python + PyQt6）。
请帮我完成项目初始化：
1. 用 git init 初始化版本控制；
2. 创建虚拟环境 .venv 并告诉我如何激活；
3. 创建 requirements.txt，内容为：PyQt6、biopython、numpy、matplotlib、pandas、
   primer3-py、openpyxl、logomaker、toytree、pymsaviz；
4. 在虚拟环境中安装这些依赖；
5. 创建空的目录骨架：modules/、utils/、tests/、examples/、scripts/，每个目录放一个空的 .gitkeep；
6. 创建 .gitignore（忽略 .venv/、__pycache__/、dist/、build/、softwares/、user_data/）；
7. 完成后告诉我每一步的验证方法。
界面文字请一律使用英文。
```

> **术语**：`.gitignore` 是"别存档这些文件"的清单；`softwares/` 稍后放第三方工具的成品程序（体积大，不进 git）。

**验收**：`pip list` 能看到 PyQt6 等包；文件夹里出现 `modules/` 等目录。

> 💡 如果 `pip install` 很慢或失败，对 AI 说："pip 安装很慢，请帮我配置国内镜像源（清华 TUNA）再重试。"

---

## 5. 和 AI 打交道的核心心法

记住这个循环，整个项目就是把它重复几十次：

```
① 提需求（复制本指南的提示词，或自己描述）
      ↓
② AI 改代码
      ↓
③ 你按"验收清单"运行检查
      ↓
④ 通过 → git commit 存档 ｜ 不通过 → 把报错原文/截图贴回给 AI → 回到②
```

五条经验，比任何提示词技巧都重要：

1. **小步走**。一次只让 AI 做一个里程碑里的一件事。功能大了，AI 容易"脑补"出错。
2. **验收先行**。提示词里写清"完成后我要如何验证"。看得见的行为才是标准，"代码写完了"不算。
3. **报错原文是金子**。终端里的红色报错（Traceback）整段复制给 AI，不要自己转述。报错最后一行通常直接说明原因。
4. **卡住就降级**。如果 AI 连续两次修不好，说："把刚才的改动回退，我们换一个更简单的实现方式。"（所以要用 git，随时能回退。）
5. **每完成一步就存档**：

```powershell
git add -A
git commit -m "M0: first PyQt window"    # 引号里写这步做了什么
```

---

## 里程碑 0：让第一个窗口弹出来

**目标**：运行 `python main.py`，弹出一个 920×700 的空白窗口，标题 SeqSketch，带菜单栏占位和底部状态栏。

把这段给 AI：

```text
创建最小可运行的 PyQt6 应用，两个文件：

1. main.py：
   - 创建 QApplication 和主窗口，加载全局异常钩子（未捕获异常弹窗并写入 startup.log）；
   - 启动时若根目录存在 start_logo.png 则显示 3 秒启动画面（QSplashScreen），没有就跳过。

2. main_window.py：
   - MainWindow 类继承 QMainWindow，标题 "SeqSketch"，默认与最小尺寸 920x700；
   - 中央是一个 QTabWidget（标签可关闭，点 X 触发 tabCloseRequested）；
   - 底部一个 QStatusBar，提供 show_message(text, error=False) 方法：普通消息显示在状态栏 5 秒，error=True 弹 critical 对话框。

验收：python main.py 能弹出窗口；手动关掉窗口程序正常退出、无报错。
```

**验收清单**

- [ ] `python main.py` 弹出窗口
- [ ] 窗口尺寸约 920×700，标题 SeqSketch
- [ ] 关闭窗口后终端无红色报错

**新术语**：**QApplication** 是 Qt 程序的"总管家"；`app.exec()` 启动**事件循环**——程序停在那里等用户点鼠标、敲键盘，事件来了分发给对应控件处理。窗口程序不退出的秘密就是它。

存档后进入下一步。

---

## 里程碑 1：主窗口 + 菜单 + 第一个功能页

这是整个项目**最重要**的里程碑：确立"菜单 → 打开 Tab"的架构。之后每个功能都是复制这个模式。

### 1a. 菜单栏与 Tab 管理架构

```text
继续完善 MainWindow，并新建 menus.py，确立如下架构（之后 40+ 个功能都走这个模式）：

1. main_window.py：为每个功能提供一个 open_xxx_tab() 方法，内部调用统一的
   _find_or_open(tab_class, title) 帮助方法：
   - 若已有同类型 Tab 打开，聚焦它（单实例）；
   - 否则创建新 Tab 加进 QTabWidget（多实例功能则允许重复打开）。

2. menus.py：提供 create_menus(window) 函数，在菜单栏建这些顶级菜单（先建菜单骨架，
   具体条目随功能逐步添加）：FASTA Tools / DNA Analysis / Protein Analysis /
   Alignment / BLAST / Primer Design / Phylogenetic Tree / Bookmarks / Help / Settings。
   每个条目用 QAction，triggered 信号连接到 window.open_xxx_tab()。

3. Tab 关闭时调用 tab 的 shutdown() 方法（若存在），用于将来停止后台线程。

验收：python main.py 后能看到全部顶级菜单；点击一个尚未实现的条目不报错（暂时提示 coming soon）。
```

### 1b. 造"Tab 基类"——所有功能页的公共骨架

先理解为什么：45 个功能页的界面长得都差不多（上面输入、中间参数、底下 Run 按钮 + 状态栏）。如果每页都重写一遍这些零件，又累又不一致。所以先做一个 **`BaseTabWidget` 基类**（图纸中的图纸）：

```text
新建 utils/common_components.py，实现 BaseTabWidget(QWidget) 基类：

构造参数 BaseTabWidget(title, tab_type)，tab_type 有两种：
- "sequence"：序列粘贴模式。上部是输入区（QGroupBox "Input Sequence" 内含一个大
  QTextEdit 输入框 self.input_text，支持拖入 FASTA 文件自动读入）+ 底部一行按钮
  （Run / Clear / Help），中部留给子类放参数（self._param_layout），下部输出区
  （QGroupBox "Output" 内含 self.output_text），底部状态行 self.status_label。
- "file"：文件处理模式。上部 "Input File" 区（路径输入框 + Browse 按钮，
  支持拖放），中部 self._param_layout 放参数，下部是操作日志 self.log_text
  （QTextEdit 只读），底部 Run / Clear / Help 按钮与状态行。

提供公共方法：
- run()：占位，子类覆盖，点击 Run 时执行；
- clear()：清空输入输出与状态；
- show_help()：弹出一个帮助对话框（子类可覆盖）；
- show_status(text)：更新状态行；
- validate_input_path(path) / validate_output_path(path)：检查路径合法性，
  非法时弹警告框并返回 False；
- is_fasta_path(path)：按扩展名 .fasta/.fa/.fas/.fna/.ffn/.faa/.frn/.txt 判断。
- shutdown()：安全停止后台线程的占位实现。

验收：单独写一个临时测试脚本，用 BaseTabWidget("Test","sequence") 创建实例，
run() 不报错，能看到输入输出框和 Run/Clear/Help 按钮。
```

### 1c. 第一个功能页：互补 / 反向互补

```text
新建 modules/complement_tab.py，实现第一个真实功能页，并接进菜单：

1. ComplementTab 继承 BaseTabWidget，构造为 ("Complement/Reverse Complement", "sequence")。
2. 参数区：一个 QComboBox 下拉框，选项 "Complement" 和 "Reverse Complement"。
3. run() 逻辑：
   - 输入框为空 → show_status 提示并返回；
   - 若包含 ">"（FASTA 文本）→ 按 header/序列逐条转换，写出同样格式的 FASTA；
   - 否则视为裸序列，校验只含 IUPAC 碱基（ACGTN 加模糊码 RYMKSWBDHV 及小写），
     非法字符则提示 "Invalid characters: IUPAC bases only"；
   - 互补用 Python str.translate 查表：A↔T, G↔C, R↔Y, M↔K, S→S, W→W, B↔V, D↔H, N→N；
     反向互补在互补后 [::-1] 翻转。
4. Help 按钮弹出说明：该工具用途、配对规则表、输入输出示例。
5. main_window.py 加 open_complement_tab()（单实例），menus.py 的 DNA Analysis
   菜单加 "Complement / Reverse Complement" 条目。

验收：粘贴 ATGCGATCG 选 Complement 得 TACGCTAGC；选 Reverse Complement 得 CGATCGCAT；
粘贴 >s1\nATGC 多条 FASTA 也逐条转换；输入含字母 Z 的序列得到明确报错提示。
```

**新术语**：**`[::-1]`** 是 Python 的"序列反转"写法。**单实例/多实例**：有的功能（如反向互补）重复点菜单就聚焦已有页，有的（如比对）允许同时开好几个任务——复现时先全部按单实例处理即可。

到这里你已经掌握了"加一个新功能页"的完整套路。**后面所有 Tab 本质上都是它的变体。**

---

## 里程碑 2：FASTA 文件工具箱

**目标**：做出"文件模式"的一批功能页。它们处理磁盘上的 `.fasta` 文件，模式统一：选文件 → 设参数 → Run → 底部日志区显示结果，输出写到文件。

### 2a. FASTA 读写核心（先造地基）

```text
新建 modules/fasta_processor.py，实现全项目统一的 FASTA 读写类 FASTAProcessor：

- parse_text(text)：解析 FASTA 文本为记录列表。每条记录拆 header：
  第一个空格前是 record.id，其余是 record.description，序列拼接为一行。
- read_file(path)：先按 UTF-8 读，失败则退回 Latin-1 再解析（宽容处理老文件）。
- save_file(records, path)：写出 FASTA，id 与 description 用空格重组回 header。
- 另提供辅助函数 parse_fasta_tuples(text)（返回 (id, seq) 列表）和
  parse_fasta_dict(text)（id→seq 字典）。
- 新建 tests/test_fasta_processor.py 覆盖：标准解析、无 description、
  空行容忍、UTF-8/Latin-1、读写往返一致。

验收：pytest tests/test_fasta_processor.py -q 全绿。
```

**为什么要先做这个**：45 个功能里只要碰 FASTA 文件的都走它，ID 的拆分/重组规则只写一次，所有页面行为才一致。

### 2b. 第一批文件工具页

```text
新建以下 Tab（都继承 BaseTabWidget(..., "file")；完成后接进 menus.py 的
FASTA Tools 菜单和 main_window.py 的 open_xxx_tab）：

1. sequence_statistics_tab "FASTA Statistics"：
   输入 FASTA 文件，Run 后在日志区输出：序列总数、总长度、最长/最短/平均长度、
   N50、每条的 GC 含量，并用 QMessageBox 弹出汇总。
2. deduplicate_tab "Deduplicate"：按 ID 去重（保留第一条），输出到新文件；
   日志写明去掉了多少条、重复的 ID 列表。
3. concat_fasta_tab "Concatenate FASTA"：多选若干 FASTA 文件合并为一个输出文件。
4. split_fasta_tab "Split FASTA"：把一个文件按每 N 条序列拆成多个输出文件。
5. sort_fasta_tab "Sort FASTA"：按 ID 字典序或按长度（升/降序）排序后写出。
6. batch_rename_ids_tab "Rename IDs"：读入一个两列映射表（CSV/TSV/xlsx，
   旧ID 新ID），按表重命名；缺映射的 ID 保留原名并在日志警告。
7. filter_by_length_tab "Filter by Length"：输入最小/最大长度，筛选序列写出。
8. extract_by_id_tab "Filter by IDs"：输入 ID 列表文件（每行一个），提取匹配序列。
9. extract_by_regex_tab "Regex Filter"：输入正则表达式，对 header 匹配筛选。

通用要求：
- 每个 file 模式 Tab 在主控件布局末尾调用 self.content_area.addStretch()，
  让日志区贴底；
- 路径一律走 validate_input_path / validate_output_path；
- 处理前检查输入文件存在且非空；处理后日志写清输入条数、输出条数、输出文件路径。

验收：用你手工造的小 FASTA（3~5 条序列）逐个页面跑通；文件模式 Tab 的日志区
停在界面底部不悬空。
```

> **术语**：**N50** 是评估序列集合长度的指标——把所有序列从长到短排，累加到总长一半时的那条序列的长度。**正则表达式（regex）** 是一种"模式匹配"写法，如 `^gyrB_.*` 匹配所有以 gyrB_ 开头的名字。

### 2c. 在线下载与表格互转

```text
继续两个文件模式 Tab：

1. download_from_ncbi_tab "NCBI Download"：
   输入 accession 编号列表（逗号/换行分隔），选择数据库（Nucleotide/Protein），
   通过 NCBI E-utilities 的 efetch 接口（https://eutils.ncbi.nlm.nih.gov/entrez/
   eutils/efetch.fcgi，rettype=fasta，retmode=text）批量下载并保存为 FASTA。
   - 用 requests 库（需加入 requirements.txt）；
   - 请求间隔 0.34 秒以上（NCBI 限速：无 API key 最多 3 次/秒）；
   - 下载失败（网络错误、无效 accession）逐条报告，不中断整批；
   - 界面上注明：批量下载建议申请 NCBI API key 并填入。
2. fasta_table_converter_tab "FASTA ↔ Table"：
   FASTA → Excel/CSV（列为 ID、Description、Length、GC%、Sequence）；
   Excel/CSV → FASTA（读 ID 和 Sequence 两列重组）。
   用 openpyxl 读写 xlsx，pandas 读写 CSV。

验收：下载 2 个真实 accession（如 NC_000913.3 的一段）成功保存；表格互转往返后
序列内容不变。NCBI 下载需要联网。
```

---

## 里程碑 3：DNA / RNA / 蛋白分析页

这批页面是"序列粘贴模式"（继承 `BaseTabWidget(..., "sequence")`），计算全在 Python 内完成（主要靠 **Biopython** 库——生信最著名的 Python 库，提供翻译、碱基统计等现成函数）。它们通常运行很快，可以直接在主线程算；但**写法上要留好"以后搬进工作线程"的结构**。

```text
新建以下 sequence 模式 Tab（接进 DNA Analysis / Protein Analysis 菜单）：

1. rna_tab "Transcribe to RNA"：DNA→RNA（T 替换为 U），支持 FASTA 文本。
2. translate_tab "Translate"：选密码子表（默认 Standard，可选线粒体等，
   用 Biopython Seq.translate），可选 1/3 位偏移（读取框 +0/+1/+2），
   输出蛋白序列， ambiguities 按表处理。
3. orf_tab "ORF Finder"：在输入 DNA 的 6 个阅读框（正反链各 3 个）里找
   从 ATG 到终止密码子的 ORF，列出位置、长度、翻译出的蛋白，按长度排序。
4. gc_plot_tab "GC Content & Skew"：滑窗计算 GC 含量与 GC skew（(G-C)/(G+C)），
   用 matplotlib 画曲线并显示在界面内（FigureCanvasQTAgg 嵌入）。
5. codon_usage_tab "Codon Usage"：统计编码序列的 64 个密码子使用频率，
   输出表格（可保存 CSV）。
6. restriction_enzyme_tab "Restriction Analysis"：内置常见酶切位点表
   （EcoRI GAATTC、BamHI GGATCC、HindIII AAGCTT、XhoI CTCGAG、PstI CTGCAG、
   SalI GTCGAC、NotI GCGGCCGC、SmaI CCCGGG、KpnI GGTACC、NcoI CCATGG 等），
   报告每条序列上每种酶的切点位置，支持"环状序列"（位置回绕）。
7. cpg_island_tab "CpG Island"：滑窗找 GC≥50% 且 CpG 观测/期望比 ≥0.6 的区域。
8. ssr_finder_tab "SSR Finder"：找 1~6 碱基单元连续重复 ≥N 次（阈值可调）的
   微卫星位点，输出位置与重复单元。
9. amino_acid_composition_tab "Amino Acid Composition"：统计 20 种氨基酸占比，
   matplotlib 条形图展示。
10. physicochemical_properties_tab "Physicochemical Properties"：用
    Biopython ProtParam 计算 MW（分子量）、pI（等电点）、GRAVY（疏水指数）、
    不稳定指数、芳香性，输出汇总表。
11. hydrophobicity_plot_tab "Hydrophobicity Plot"：用 Kyte-Doolittle 疏水标度
    滑窗画曲线，峰值区提示可能是跨膜区。
12. protease_cleavage_tab "Protease Cleavage"：报告胰蛋白酶（K/R 后非 P）、
    胰凝乳蛋白酶（F/W/Y 后非 P）、GluC（E 后）等酶切位点与片段大小。
13. dotplot_tab "DotPlot"：两条序列滑窗打点图（window/阈值可调），
    matplotlib 显示对角线即重复/相似区域。
14. pairwise_alignment_tab "Pairwise Alignment"：用 Biopython PairwiseAligner
    做全局/局部双序列比对，显示比对得分与对齐结果（含 match 行）。

通用要求：
- 计算逻辑放在 Tab 的独立方法里（如 _compute_xxx），不要内联在按钮回调中，
  便于将来搬进工作线程；
- matplotlib 图表用 FigureCanvasQTAgg 嵌入 Tab，提供 "Save Image" 按钮导出 PNG；
- 所有 protein 相关计算先校验输入是蛋白字母表，DNA 相关先校验 DNA。

验收：每页用一条你认识的短序列人工核对一个数字/输出
（例如 translate_tab 输入 ATGGCC 得 MA；EcoRI 在 GAATTC 处报切点）。
```

> **术语**：**阅读框（reading frame）**：DNA 每次往后错 1 个碱基，三三分组的结果完全不同，所以一条链有 3 种读法，正反链共 6 种。**GRAVY**：整条序列疏水性均值，正数偏疏水。**pI（等电点）**：蛋白净电荷为 0 时的 pH，低于它带正电。

**到这里，纯 Python 计算类功能就齐了。接下来是最难也最有含金量的部分：调用外部程序。**

---

## 里程碑 4：接入外部工具（比对与建树）

MAFFT、MUSCLE、trimAl、IQ-TREE 都是**独立的命令行程序**（不是 Python 库）。Python 的角色是"调度员"：拼好命令行 → 用 subprocess 启动它们 → 等它们算完 → 读取输出文件。这类调用可能跑几分钟到几小时，所以**必须放到工作线程**，否则界面卡死。

### 4a. 外部工具的"安装"与路径解析

外部工具是第三方成品，不进 git。先决定你从哪拿：

- **方案 A（推荐，最省事）**：对 AI 说"帮我把官方下载地址整理出来"，从各家官网下载对应平台压缩包，解压到项目下 `softwares/windows/`（或 `softwares/Mac/`）。预期目录结构（目录名带版本号）：

  | 工具 | Windows 下目录 | 用途 |
  | --- | --- | --- |
  | BLAST+ | `softwares/windows/ncbi-blast-2.17.0+/bin/blastn.exe` | 序列搜索（里程碑 5） |
  | IQ-TREE | `softwares/windows/iqtree-3.1.3-Windows/bin/iqtree3.exe` | 最大似然建树 |
  | MAFFT | `softwares/windows/mafft-win_v7.526/mafft.bat` | 多序列比对 |
  | MUSCLE | `softwares/windows/muscle-win64.v5.3.exe` | 多序列比对 |
  | trimAl | `softwares/windows/trimAl_Windows_v1.5.1/trimal.exe` | 比对修剪 |

- **方案 B**：只要 AI 生成的代码支持"在 config.ini 里手填工具路径"，你把工具放在任何地方都行。

```text
新建 utils/tool_paths.py，统一解析外部工具路径：

- 提供 mafft_launcher()、muscle_executable()、trimal_executable()、
  iqtree_executable()、blast_executable(name) 等函数；
- 解析顺序：① config.ini 里 [BLAST]/[MAFFT]/... 节的手动覆盖（非空则用）；
  ② 按当前平台探测 softwares/<platform>/ 下带版本号的目录（用 glob 匹配
  版本通配符，如 ncbi-blast-*，这样将来升级版本号无需改代码）；
  ③ PATH 环境变量里找（用户自行安装的情况）；
  ④ 都找不到返回 None，调用方据此提示 "tool not found"。
- Windows 与 macOS 的目录名、可执行文件名都不同，全部封装在本模块内；
  其他代码禁止出现 hard-coded 的 softwares 路径或 .exe 后缀。
- 新建 tests/test_tool_paths.py：用临时目录伪造 softwares 结构，验证各函数
  在 Windows/macOS 两种布局下都能解析（monkeypatch 平台判断）。

验收：把 MAFFT 解压到 softwares/ 后，python -c "from utils.tool_paths import
mafft_launcher; print(mafft_launcher())" 打印出正确路径。
```

### 4b. 后台线程与"溯源日志"基础设施

```text
1. 在 utils/common_components.py 加 BaseWorker(QObject) 基类，配套 QThread 使用：
   - 信号：progress(str)、finished(object)、error(str)；
   - 标准用法：worker.moveToThread(thread)，thread.started.connect(worker.run)，
     run() 结束发 finished/error；Tab 收到信号后更新 UI 并 park 线程；
   - 提供 stop_worker_object(thread) / park_qthread(thread) 帮助函数，
     BaseTabWidget.shutdown() 调用它们安全关线程。
2. 新建 utils/run_provenance.py：record_tool_run(output_dir, tool, exe, cmd, ...)。
   每次成功调用外部工具后，向输出目录的 run_log.txt 追加一个"溯源块"：
   工具名、探测到的版本号（subprocess 跑 -version 获取，结果按 exe 缓存，
   失败记 unknown）、完整命令行（用 list2cmdline 拼接便于复制重跑）、时间戳。
   版本探测绝不能在 GUI 线程跑，且绝不能抛异常。
3. 在 BaseTabWidget 加通用的 _start_worker(worker, thread) 封装，自动接线信号、
   禁用 Run 按钮防止重复点击、结束后恢复。

验收：先写一个假外部工具（一个打印版本号的 .bat/.sh）接入任一 Tab 跑通：
运行期间界面可拖动（不卡死），结束后 run_log.txt 出现溯源块，重复点击 Run 不会
开出两个线程。
```

**新术语**：**QThread** 是 Qt 提供的线程类。**信号跨线程**：工作线程发信号，Qt 自动把处理切回主线程执行——这就是为什么"线程里不能直接碰界面控件，只能发信号"。

### 4c. 比对 → 修剪 → 建树 → 看树：教学主链

这是项目的灵魂链条，7 个核心教学页中的后 4 个。强烈建议按顺序做、每做一个验收一个。

```text
按以下顺序新建 4 个文件模式 Tab（都走 BaseWorker + QThread，都写 run_log.txt）：

1. mafft_alignment_tab "MAFFT Alignment"（Alignment 菜单）：
   - 单文件模式：输入一个 FASTA，MAFFT 输出比对后的 FASTA；
   - 命令行：mafft --auto input > output（Windows 上 mafft.bat 需要用
     shell 方式调用或直接调 mafft.bat，stdout 重定向到输出文件）；
   - 批处理模式：选择文件夹，对其中每个 FASTA 逐一比对，输出到批量目录；
   - 运行中用 progress 信号显示当前文件；结束记录 run_log.txt。

2. trimal_tab "trimAl"：输入比对好的 FASTA，gt 阈值参数可调（默认 0.8，
   即保留在 ≥80% 序列中都有残基的列），命令行 trimal -in in.fasta -out
   out.fasta -gt 0.8。支持批量。每个任务单独记录 run_log.txt。

3. iqtree_tab "IQ-TREE"：输入修剪后的比对文件，参数区提供模型选择
   （默认 MFP 自动选模）、bootstrap 次数（默认 -B 1000）、随机种子。
   命令行：iqtree3 -s aln.fasta -m MFP -B 1000 --prefix out/iqtree -T AUTO。
   结束后解析 *.treefile（Newick 树文件）路径展示，输出目录下有 .iqtree
   报告、.contree 一致树等。IQ-TREE 运行较久，必须全程在工作线程，
   且界面显示"运行中"状态。

4. tree_visualization_toytree_tab "Tree Visualization"：
   - 输入 Newick 树文件（或粘贴 Newick 文本）；
   - 用 toytree 读取并绘制（支持显示 bootstrap 支持值），嵌入 Tab 显示；
   - 提供 PNG / SVG 导出按钮；
   - 内置一个 Example 按钮载入示例树。

同时给 distance_tree_tab "Distance Tree (UPGMA/NJ)"：输入比对文件，
用 Biopython 的 DistanceTreeConstructor 基于距离法快速建树（无需外部工具），
作为 IQ-TREE 的轻量替代，同样用 toytree/Biopython 绘制。

验收（用一条真实数据走通全链）：从 NCBI 下载 5~8 个物种的 COI 或 cytb 基因
CDS 序列存为一个 FASTA → MAFFT 比对成功 → trimAl 修剪后列数变少 →
IQ-TREE 建树（几十秒到几分钟）→ Tree Visualization 显示树并导出 PNG。
每一步输出目录都有 run_log.txt 溯源块。
```

> **术语**：**MFP** = ModelFinder Plus，IQ-TREE 自动挑选最合适的替换模型；**prefix** 参数让 IQ-TREE 所有输出文件共用一个文件名前缀。

### 4d. 其余比对相关页

```text
继续：
1. multiple_sequence_alignment_tab "MUSCLE Alignment"：结构与 MAFFT 页相同，
   调 muscle5（命令 muscle -align input.fasta -output output.fasta），支持批量。
2. msa_visualization_tab "MSA Visualization"：用 pymsaviz 把比对结果渲染成
   带染色的一致性图，嵌入 Tab，支持导出。
3. alignment_format_converter_tab "Alignment Format Converter"：比对文件在
   FASTA / Clustal / Phylip / Nexus / Stockholm 间互转（用 Biopython
   AlignIO）。
4. partition_concat_tab "Partition / Concatenation"：多基因联合建树的前置——
   读入多个比对文件 + 一个分区表（哪个基因占哪些列），按 ID 顺序对齐合并成
   一个超矩阵，同时生成 IQ-TREE 的 partition 文件（Nexus CHARSET 格式）。
   关键规则：缺某基因的物种用 N/问号填补（缺失数据）。

验收：MUSCLE 比对结果能被 MSA Visualization 打开；两个基因的分区合并后
总列数 = 各基因列数之和，分区文件列区间正确。
```

> **术语**：**超矩阵 / 串联（supermatrix / concatenation）**：把多个基因的比对首尾拼成一个大矩阵一起建树，能利用更多位点；**分区模型（partition model）** 允许每个基因用不同的进化模型。

---

## 里程碑 5：本地 BLAST

BLAST 分"在线"和"本地"两块。在线版只需打开浏览器链接（10 分钟做完）；本地版要先用 `makeblastdb` 建数据库，再跑 `blastn`/`blastp` 搜索。

```text
1. 新建 modules/blast_config.py：
   - 解析项目根目录 config.ini 的 [BLAST] bin_dir（空 = 自动探测捆绑副本）；
     若用户填了自定义路径，把解析结果持久化到用户数据目录的配置文件
     （下次优先读取），保留 config.ini 作为 legacy 回退。
   - 提供获取 blastn/blastp/makeblastdb 可执行文件路径的方法。

2. 新建 modules/blast_make_db_dialog.py "Make BLAST Database"（对话框 QDialog）：
   - 选一个 FASTA 作为数据库来源，选类型 nucleotide/protein，
     输出目录选好后运行 makeblastdb -in db.fasta -dbtype nucl -out <目录/库名>；
   - 成功后在用户配置里登记这个库（名字、路径、类型、分子类型）。

3. 新建 modules/blast_run_dialog.py + blast_local_tab.py "Local BLAST"：
   - Tab 页：query 粘贴区（sequence 模式）+ 从已登记库里选一个；
   - 参数区：program（blastn/blastp 自动随库类型）、e-value 阈值（默认 1e-5）、
     max target sequences（默认 50）、输出格式（outfmt 6 表格，列含
     qseqid sseqid pident length qstart qend sstart send evalue bitscore）；
   - 把 query 存临时文件，工作线程运行 blastn -query tmp.fasta -db <库>
     -outfmt 6 -evalue 1e-5 -max_target_seqs 50 -out result.tsv；
   - 结果用 QTableView 显示（pandas 读取 TSV），提供导出 TSV/Excel；
   - 记录 run_log.txt 溯源。

4. Protein Analysis 菜单加 "Online BLAST / Web Links" 分组：一组 QAction，
   用 QDesktopServices.openUrl 打开浏览器（NCBI BLAST、UniProt 等）。

验收：用 examples/blast/ 的 E.coli 蛋白建库后，粘贴一条查询蛋白运行 blastp，
表格出现带 e-value 的命中结果；换 e-value=1e-50 结果变少。
```

> **术语**：**e-value（期望值）**：随机情况下出现这么好命中的次数期望，越小越可信，1e-5 是常用门槛。**outfmt 6** 是制表符分隔的无表头表格，程序最好处理。**QDialog** 是模态对话框（弹出来必须先处理它）。

---

## 里程碑 6：引物设计与桑格测序

```text
1. modules/primer3_gui.py "qPCR Primer Design"：
   - 输入 DNA 模板（粘贴或文件），参数区暴露 primer3 核心参数：产物长度范围
     （默认 80-200 bp）、引物长度（18-25）、Tm 范围（58-62）、GC%（40-60）；
   - 用 primer3-py 的 bindings 设计引物（primer3.bindings.design_primers）；
   - 结果表列出每对引物：Forward/Reverse 序列、Tm、GC%、产物大小、位置；
   - 序列视图区把引物结合位置在模板上高亮标出。

2. modules/cloning_primer_tab "Cloning Primer Design"：
   - 输入：载体序列、插入片段序列、选限制性酶（如 EcoRI / BamHI）；
   - 生成带酶切位点接头的引物（载体端加酶位点 + 保护碱基），说明输出的
   引物顺序合成即可用。

3. modules/primer_analysis_tab "Primer Analysis"：
   - 粘贴任意引物序列，计算 Tm（primer3 calc_tm）、GC%、分子量，
   - 检测发夹（hairpin）、引物二聚体（self/self 与 self/reverse complement），
     按自由能阈值给 Pass/Warning 标记。

4. modules/sanger_viewer_tab "Sanger Chromatogram Viewer"：
   - 打开 .ab1 文件（pip install sangerseq-viewer 或用 Bio.SeqIO 解析 abi），
     用 matplotlib 画四色峰图（A绿/C蓝/G黑/T红），可水平滚动缩放，
     显示该段碱基调用序列。

5. modules/sanger_tab "Sanger Assembly"：
   - 上传正反向两条 .ab1（或粘贴序列），做双向拼接：反向序列先反向互补，
     再与正向做重叠比对（用 Biopython pairwise 或 difflib），合并成一致序列，
     报告重叠区长度与不一致碱基（不一致处列出双峰证据）。

验收：用一段含 EcoRI 位点的插入序列 + pBR322 载体序列（examples/dna/ 有示例），
生成的引物两端确实含 GAATTC 接头；Sanger 页载入 .ab1 能看到四色峰。
```

> **术语**：**Tm（解链温度）**：一半引物与模板解离的温度，上下游引物 Tm 要接近。**发夹（hairpin）**：引物自身回折配对，会浪费引物；**二聚体（dimer）**：两条引物互配，PCR 的头号敌人。**保护碱基**：接在酶切位点外侧的几个额外碱基，帮助酶结合到 DNA 末端。

---

## 里程碑 7：示例数据、收藏夹与外观

### 7a. 教学示例数据（"Example" 按钮）

新手用软件最大的障碍是"没数据"。本项目给每个教学页配了 **Example 按钮**，一键载入内置数据。

```text
1. 新建 utils/example_data.py，作为示例数据的唯一入口：
   - example_path(*parts)：返回 examples/ 下只读文件的绝对路径
     （打包后也能找到，用 sys._MEIPASS 兼容 PyInstaller）；
   - stage_example(*parts)：把示例复制到用户可写目录（user_data/example_work/）
     并返回新路径——文件模式 Tab 的输出要能写盘，所以先"抄写"一份再加载；
   - load_example_text(*parts)：直接读文本，给序列粘贴模式用。
   - 用户数据目录定位：Windows 用 %APPDATA%/SeqSketch，macOS 用
     ~/Library/Application Support/SeqSketch；新建 utils/app_paths.py 统一管理
     （resource_path() / user_data_dir() / user_data_file()）。
2. 制作示例数据集（可以从原版项目拷贝，或让 AI 生成合成数据）：
   examples/phylo/（8 物种 cytb：CDS、蛋白、比对、Newick 树）、
   examples/dna/、examples/protein/、examples/blast/、examples/sanger/。
3. 给 7 个核心教学页加 Example 按钮，统一模式：load → 空数据时弹
   QMessageBox.information 提示加载失败 → 填入本页输入控件 →
   show_status("Example loaded: <文件名>")。
4. 新建 tests/test_example_data.py 验证每个示例文件存在且能被加载。

验收：清空输入后点 Example，输入区立即填好数据且状态栏提示；文件模式页
加载的是可写副本（对它 Run 不会报权限错误）。
```

### 7b. 收藏夹、帮助与主题

```text
1. modules/favorites_manager.py：书签对话框——分类管理常用在线数据库链接
   （UniProt、NCBI、PDB 等），支持增删改、拖放排序、导入导出 JSON/HTML，
   数据存用户目录 JSON 文件。Bookmarks 菜单打开。
2. Help 菜单：About 对话框（版本号、许可 GPL-3.0、第三方工具清单）、
   Check Update（访问 GitHub Releases API 比较版本号，无网静默失败）。
3. 根目录 styles.qss：全局样式表（统一按钮悬停色、输入框聚焦高亮、
   Tab 栏样式、滚动条样式）。MainWindow._load_style() 启动时加载。
   提供 Settings 菜单切换主主题与 resources/styles/modern_theme.qss 备用主题。
4. 准备 window_logo.png/.ico 与 start_logo.png（AI 可以生成占位图，
   例如用 matplotlib/PIL 画一个简单 logo）。

验收：换主题后重启仍生效或立即刷新；About 对话框信息正确；收藏夹导入导出
的 JSON 可再次导入。
```

> **术语**：**QSS** = Qt Style Sheet，语法与网页的 CSS 几乎一样，用来给界面"化妆"。**user_data**：程序运行中产生的可写文件（配置、收藏夹、示例工作副本）绝不能写进安装目录——打包后的目录可能没有写权限，所以放到系统给每个用户准备的 AppData 里。

---

## 里程碑 8：自动化测试与代码检查

功能多了以后，**改一处坏一处**是必然的。测试就是你雇来的"验收员"：每次改完跑一遍，谁坏了立刻知道。

```text
为本项目补齐 pytest 测试体系：

1. tests/conftest.py：
   - 设置环境变量 QT_QPA_PLATFORM=offscreen（CI 服务器没有显示器也能跑 GUI）；
   - 提供作用域为 session 的 qapp fixture（整个测试进程共享一个 QApplication）。
2. 为两类 Tab 分别建立测试文件：
   - tests/test_fasta_tools_tabs.py：file 模式页——构造临时输入文件 →
     直接调用 tab.run() → 断言输出文件内容与日志文本；
   - tests/test_dna_analysis_tabs.py：sequence 模式页——setPlainText 输入 →
     run() → 断言输出框文本与状态栏提示；另外覆盖 MainWindow 的 Tab 复用
     （open 两次得到同一个实例）与菜单接线（菜单条目数正确）。
3. 外部工具类测试一律 mock：monkeypatch tool_paths 函数返回一个假脚本，
   验证命令行拼接正确、超时有 TimeoutExpired 处理、失败路径有用户提示；
   不真跑 MAFFT/IQ-TREE。
4. pyproject.toml 配置：pytest addopts = -q --timeout=60（每个用例 60 秒超时，
   防止 GUI 测试挂死拖垮 CI）；ruff line-length=100、target-version=py310。
5. ruff check . 清零所有告警。

验收：pytest -q 全绿且总耗时 <2 分钟；ruff check . 无输出。
```

**怎么跑**：

```powershell
py -m pytest -q          # 全部测试（Windows；Mac 用 python3 -m pytest -q）
py -m pytest tests/test_fasta_tools_tabs.py -k deduplicate -q   # 只跑某个
ruff check .             # 代码体检
```

> **术语**：**fixture**：pytest 的"预备步骤"（比如先把 QApplication 准备好）。**mock（打桩）**：把真实的外部依赖换成假货——测"我们有没有正确地调用工具"，不测"工具本身算得对不对"。**monkeypatch**：pytest 临时替换函数实现的机制。

---

## 里程碑 9：打包成免安装的 exe

最后一步，把它变成"发给同学，解压双击就能用"的绿色软件。

```text
用 PyInstaller 把应用打成 onedir 便携版：

1. pip install pyinstaller。
2. 编写 SeqSketch.spec：
   - 入口 main.py；name=SeqSketch；
   - datas：styles.qss、resources/、examples/、third_party_licenses/ 一起打包；
   - 隐藏导入：toytree、pymsaviz、logomaker、primer3 的动态导入模块；
   - matplotlib 使用后端 Agg 兜底；排除 tests/、build/；
   - Windows 加 window_logo.ico 图标与 version_info.txt 版本资源。
3. 编写 scripts/build_onedir.ps1：
   - 激活虚拟环境 → pyinstaller SeqSketch.spec --noconfirm；
   - 把 softwares/<platform>/ 整体复制进 dist/SeqSketch/（让便携版自带工具）；
   - 可选 -Zip 参数：打包后压缩成 dist/SeqSketch-windows.zip 并打印 SHA256。
4. dist/SeqSketch/SeqSketch.exe 双击应能启动全部功能（外部工具按相对路径
   softwares/ 找到）。注意 main.py 里 frozen 模式（getattr(sys,"frozen",False)）
   的路径处理：打包后 __file__ 不可靠，要用 sys.executable 定位。

验收：把 dist/SeqSketch/ 整个文件夹拷到另一台没装 Python 的电脑上，
双击 exe 能启动，MAFFT 比对和树可视化都能正常跑。
```

> **术语**：**PyInstaller** 打包 = 把 Python 解释器 + 你的代码 + 全部依赖复制进一个文件夹。**onedir** 模式产物是一整个文件夹（比单 exe 启动快、杀毒软件误报少）。**spec 文件** 是打包配方。**frozen 模式**：代码被打包后运行时的状态，此时没有真正的 `.py` 文件。

> ⚠️ 若要把软件**发给别人**：项目是 GPL-3.0（因为 PyQt6 是 GPL），随包分发第三方工具时必须把各自许可证文件放进对应工具文件夹，并附 THIRD-PARTY-NOTICES。自己学习复现不受影响。

---

## 全部功能页与里程碑对照表

走完前面里程碑后，对照此表把剩余页面批量复刻（提示词模板见下）。每完成一行，验收 + 存档一次。

| 菜单 | Tab（建议复刻顺序） | 模式 | 所属里程碑 |
| --- | --- | --- | --- |
| DNA Analysis | Complement / Reverse Complement | sequence | M1 ✅ |
| DNA Analysis | Transcribe to RNA → Translate → ORF Finder | sequence | M3 ✅ |
| DNA Analysis | Codon Usage → Restriction Analysis → CpG Island → SSR Finder → GC Content & Skew | sequence | M3 ✅ |
| FASTA Tools | FASTA Statistics → Rename IDs → Simplify Headers → Filter by IDs → Filter by Length → Regex Filter → NCBI Download → Deduplicate → Concatenate → Split → Sort → FASTA ↔ Table | file | M2 ✅（Simplify Headers 与 Rename 同理） |
| Protein Analysis | Amino Acid Composition → Physicochemical → Hydrophobicity → Protease Cleavage → DotPlot → Pairwise Alignment | sequence | M3 ✅ |
| Protein Analysis | Sequence Logo（logomaker，输入比对或同源序列） | sequence | 补做 |
| Alignment | MAFFT → MUSCLE → MSA Visualization → Format Converter → DotPlot | file/sequence | M4 ✅ |
| BLAST | Online Links → Make DB → Local BLAST | dialog+sequence | M5 ✅ |
| Primer Design | qPCR Primer Design → Cloning Primer → Primer Analysis | sequence | M6 ✅ |
| Phylogenetic Tree | trimAl → Partition/Concatenation → Distance Tree → IQ-TREE → One-Step MultiGenePhy → Tree Visualization | file | M4 ✅（One-Step 见下） |
| Sanger | Chromatogram Viewer → Assembly | file | M6 ✅ |
| Bookmarks | Favorites Manager | dialog | M7 ✅ |

**One-Step MultiGenePhy**（一步式多基因建树，项目里最复杂的功能）：把"多个基因 FASTA + 物种对照表 → 各自比对 → 修剪 → 分区串联 → IQ-TREE 联合建树 → HTML 报告"串成一个向导式 Tab。因为步骤多（IO / 数据模型 / 流程 / 界面），拆成 4 个文件：`one_step_multigenephy_io.py / _models.py / _workflow.py / _tab.py`。做完前面所有页之后单独用一个会话复刻它，提示词：

```text
复刻 One-Step MultiGenePhy 功能，拆为 4 个模块文件：
- _io.py：读取输入（多个基因 FASTA 文件 + 一个 xlsx/csv 物种×文件对照表），
  校验：每个基因至少 4 个物种、ID 不含特殊字符；
- _models.py：GeneInput / PipelineConfig / StepResult 等 dataclass，
  流程状态与 UI 解耦；
- _workflow.py：纯逻辑工作流（不 import PyQt6）：对每个基因调 MAFFT → trimAl →
  分区串联 → 生成 IQ-TREE 命令并执行 → 收集树文件；每步产出 StepResult；
  全程可取消（检查 cancel_event）；最终把命令清单写入 run_manifest.json 并生成
  一个 HTML 结果报告（嵌树图 PNG + 每步日志 + 输入清单）；
- _tab.py：file 模式向导界面（选输入目录与对照表 → 参数 → 运行 → 步骤进度表 →
  完成后打开报告），QThread 跑 _workflow。
复用 utils/tool_paths 与 run_provenance。验收：用 2 个基因 × 6 个物种的小数据集
端到端跑通并生成 HTML 报告。
```

---

## 常见问题排查（FAQ）

遇到问题先自己查这表，再问 AI。**问 AI 时永远附上报错原文。**

| 现象 | 原因与解法 |
| --- | --- |
| `'python' 不是内部或外部命令` | 安装时没勾 Add to PATH。重装勾选，或改用 `py` 命令（Windows 启动器）。 |
| `pip install` 半天不动 / 超时 | 网络问题。让 AI 帮你换国内镜像源（清华 TUNA）。 |
| `ModuleNotFoundError: No module named 'PyQt6'` | 忘了激活虚拟环境，或装到了全局。先 `.\.venv\Scripts\activate` 再跑。 |
| 窗口一闪而过 / 无响应 | 看终端报错。常见：某 Tab 的 `__init__` 抛异常——把 traceback 给 AI。 |
| 界面点 Run 后卡死 | 计算跑在主线程了。该功能没走 BaseWorker + QThread（里程碑 4b）。 |
| 中文/特殊字符乱码 | 让 AI 检查：所有 `open()` 是否都带 `encoding="utf-8"`；文件是否混入了 CJK 字符（本项目界面文字全英文）。 |
| MAFFT/BLAST `not found` | 工具没解压到 `softwares/<平台>/`，或目录名与 `tool_paths.py` 的通配符不匹配。用 `python -c "from utils.tool_paths import mafft_launcher; print(mafft_launcher())"` 检查解析结果。 |
| 外部工具一启动就被杀 | Windows 杀毒/SmartScreen 拦截。把 `softwares/` 加入白名单。 |
| `pytest` 里 GUI 测试挂住超时 | 忘了 `QT_QPA_PLATFORM=offscreen` 或弹了真对话框等确认。检查 conftest.py 与弹窗逻辑是否 mock。 |
| 打包后启动崩溃，日志报 `Failed to execute script` | 看 `dist/SeqSketch/` 旁的 `startup.log` 与终端输出。最常见：`resource_path` 没用 `_MEIPASS`、隐藏导入漏了（spec 加 `hiddenimports`）。 |
| toytree/pymsaviz 打包后 import 失败 | 它们动态导入子模块。在 spec 的 `hiddenimports` 里补齐（让 AI 帮你枚举）。 |
| Mac 上双击 App 提示无法验证 | Finder 里右键 App → 打开（一次即可）。 |
| 改坏了想回退 | `git log --oneline` 找到上一个好存档，`git checkout <hash> .` 或对 AI 说"回退上一次改动"。 |

---

## 附录：给 AI 的"项目宪法"（可整段复制）

在每个新会话开始时（或存成项目里的 `AGENTS.md`，AI 助手会自动读取）粘贴下面的内容，能显著减少 AI 跑偏：

```text
# 项目约定（SeqSketch 复刻版）

## 技术栈
Python 3.10+ / PyQt6 / Biopython / numpy / matplotlib / pandas / primer3-py /
logomaker / toytree / pymsaviz / openpyxl。打包用 PyInstaller onedir。

## 架构
- main.py 启动 QApplication；main_window.py 的 MainWindow 管理 QTabWidget；
- menus.py 用 QAction 把菜单项接到 MainWindow.open_xxx_tab()；
- 每个功能一个 modules/xxx_tab.py，类名 PascalCaseTab；
- 所有 Tab 继承 utils/common_components.py 的 BaseTabWidget(title, "file"|"sequence")；
- FASTA 读写一律走 modules/fasta_processor.py 的 FASTAProcessor，不自己写解析；
- 路径工具用 utils/app_paths.py（resource_path / user_data_dir）；
- 外部工具（MAFFT/MUSCLE/trimAl/IQ-TREE/BLAST）路径一律经 utils/tool_paths.py
  解析，禁止硬编码 softwares 目录名或 .exe 后缀；
- 耗时操作（外部工具、网络）必须 BaseWorker + QThread，工作线程只发信号不碰控件；
- 每次成功调用外部工具后用 utils/run_provenance.py 写 run_log.txt（工具、版本、
  完整命令行、时间戳）。

## 代码风格
- 界面与状态文字一律英文，不使用 self.tr()，不混入 CJK 字符；
- ruff line-length=100；类型注解尽量写；
- 每个文件顶部写一句 docstring 说明职责。

## 工作方式
- 每次只做我明确要求的一个改动，改完告诉我如何验证；
- 不确定需求时先问，不要脑补大段功能；
- 改动后运行相关 pytest；涉及多个 Tab 时跑 tests/test_fasta_tools_tabs.py
  与 tests/test_dna_analysis_tabs.py；
- GUI 测试必须能在无显示器环境运行（QT_QPA_PLATFORM=offscreen），
  外部工具调用必须可 mock。
```

---

### 最后：复现完成后的下一步

- **读代码**：让 AI 逐文件给你讲解（"解释 modules/mafft_alignment_tab.py 每个方法的作用"）——vibe coding 的下半场是"看懂 AI 写的什么"。
- **加自己的功能**：挑一个你实验室真的需要的工具（比如某类专有格式转换），按里程碑 1c 的套路让 AI 新增一个 Tab。
- **回看原版**：拿你复刻的行为与原版 SeqSketch 对比差异，把差异点列给 AI 讨论哪个实现更好——这是最快的进阶方式。
