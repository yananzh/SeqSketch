# SeqSketch

一个基于 PyQt6 的生物信息学序列分析桌面应用，集成多种本地和在线分析工具，覆盖 FASTA 处理、DNA/RNA/蛋白分析、多序列比对、BLAST、引物设计、系统发育树构建与可视化、桑格测序等完整工作流。

## 主要特性

### FASTA 工具
- 序列统计、批量重命名 ID、简化序列头、按 ID / 正则 / 长度筛选
- 去重、合并 FASTA、NCBI 在线下载

### DNA / RNA 分析
- 转换为 RNA、互补/反向互补、翻译、ORF 查找
- 密码子偏好分析、限制性内切酶分析、GC 含量绘图
- 桑格测序峰图查看与序列拼接

### 蛋白分析
- 氨基酸组成、疏水性绘图、蛋白酶切割位点预测
- 理化性质分析、序列 Logo 生成

### 比对与系统发育
- 双序列比对（Pairwise）、多序列比对（MAFFT / MUSCLE）
- MSA 可视化、比对格式转换
- trimAl 修剪、分区拼接（Partition / Concatenation）
- IQ-TREE 建树、toytree 树可视化、距离矩阵树
- 一步式多基因系统发育分析（One-Step Multi-Gene Phylogeny）

### BLAST
- 本地 BLAST 搜索（需配置 BLAST+ 数据库）
- 建库对话框

### 其他
- 点阵图（Dotplot）、引物分析（Primer3）
- 克隆引物设计（限制性酶切位点接头 PCR 引物）
- 收藏夹管理器（书签分类、导入/导出 JSON / HTML、拖放排序）
- 操作日志记录、浅色/深色主题切换

## 安装与运行

```bash
# 安装依赖
pip install -r requirements.txt

# 安装开发依赖（pytest、ruff）
pip install -r dev-requirements.txt

# 启动
python main.py
```

## 测试

```bash
# 运行全部测试
py -m pytest -q

# 按模块运行
py -m pytest tests/test_fasta_tools_tabs.py -q
py -m pytest tests/test_dna_analysis_tabs.py -q
py -m pytest tests/test_example_data.py -q
py -m pytest tests/test_blast_tabs.py -q
py -m pytest tests/test_primer_tabs.py -q
py -m pytest tests/test_cloning_primer_tab.py -q
py -m pytest tests/test_toytree_tab.py -q
py -m pytest tests/test_one_step_multigenephy_tab.py -q
py -m pytest tests/test_one_step_multigenephy_workflow.py -q

# 代码检查
ruff check .
```

## Windows 打包

```powershell
.\scripts\build_onedir.ps1
```

产物为 `dist/SeqSketch/`，是一个自包含便携文件夹，可直接复制到任意位置运行。

## 目录结构

```
main.py              # 程序入口，启动画面
main_window.py       # 主窗口，QTabWidget 管理
menus.py             # 菜单栏定义
styles.qss           # 主样式表
config.ini           # 外部工具路径覆盖
SeqSketch.spec       # PyInstaller 打包配置
modules/             # 功能模块（~40 个独立 Tab）
utils/               # 基础组件、路径工具、示例数据加载
scripts/             # 构建脚本
examples/            # 教学示例数据（phylo/、dna/、protein/、blast/、sanger/）
softwares/           # 捆绑的外部工具（BLAST、IQTree、MAFFT、MUSCLE、TrimAl）
resources/           # 图标和样式
tests/               # Pytest 回归测试
config/              # 设置管理
docs/                # 设计文档
```

## 技术栈

- **GUI**: PyQt6
- **科学计算**: NumPy、Matplotlib、Pandas、Biopython
- **引物设计**: Primer3-py
- **序列 Logo**: Logomaker
- **打包**: PyInstaller (onedir)
- **测试**: Pytest (timeout 60s, QT_QPA_PLATFORM=offscreen)
- **代码检查**: Ruff