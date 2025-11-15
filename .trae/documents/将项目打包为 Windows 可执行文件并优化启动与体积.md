# 总体思路
- 基线方案：使用 PyInstaller 生成稳定的 Windows 可执行文件（优先 onedir 提升启动速度；onefile 提升分发便利）
- 进阶方案：使用 Nuitka 编译（更快启动、更小体积，但构建时间长、配置更复杂）
- 代码层优化：按需加载重型模块、减少初始化导入、裁剪未用资源与插件，确保在不改变功能的前提下优化启动与体积

## 方案A：PyInstaller（推荐起步）
- onedir（更快启动）：`pyinstaller -y --clean --name BioSeqAnalyzer --noconfirm --onedir --windowed main.py`
- onefile（更便携）：`pyinstaller -y --clean --name BioSeqAnalyzer --noconfirm --onefile --windowed main.py`
- 体积与启动的权衡：
  - onefile 会在首次或每次启动解压，启动更慢；onedir 直接运行文件夹内容，启动更快
  - 使用 UPX 可显著减小体积，但会略微增加启动时间

### PyInstaller 进一步优化
- 排除未用模块：
  - `--exclude-module PyQt6.QtQml --exclude-module PyQt6.QtNetwork --exclude-module PyQt6.QtWebEngineWidgets`（项目未使用 QML/WebEngine/Network）
  - 排除测试与示例：`--exclude-module matplotlib.tests --exclude-module Bio.tests` 等
- 精选 Qt 插件：只打包 `qwindows.dll`（平台插件）与必需样式，避免整套 Qt 插件
- 数据裁剪：
  - Matplotlib 的 `mpl-data` 很大；保留所需字体（如 `DejaVuSans.ttf`），排除未用字体与样式
  - 排除 SciPy（可选）：项目在 `sanger_tab.py` 已做降级处理（缺省平滑），若不影响你的使用场景，可剔除以大幅减小体积
- 其它开关：
  - `--optimize 2`（移除断言与 docstring；对功能无影响）
  - `--upx-dir <UPX路径> --upx`（压缩二进制减小体积；谨慎启用以免影响少数 DLL）
- 外部依赖打包：将 `softwares\ncbi-blast-2.16.0+\bin` 加入运行时路径或随包放置，并在启动时用相对路径查找
- 使用 .spec 文件细化：将 `datas`、`binaries`、`excludes` 写入 .spec 以可重复构建

## 方案B：Nuitka（更高优化）
- 优势：更小体积、C 编译提升启动速度，依赖分析更彻底
- 基本命令：
  - `python -m nuitka --standalone --onefile --enable-plugin=pyqt6 --enable-plugin=numpy --enable-plugin=matplotlib --nofollow-imports --lto=yes --clang --windows-disable-console --output-dir=dist main.py`
- 优化点：
  - `--noinclude-default` 排除默认数据；用 `--include-data-files` 精选需要的 `mpl-data` 字体
  - 仅包含 `Qt6Core/Gui/Widgets` 必需 DLL，剔除未用 Qt 组件
  - 排除 SciPy（可选）或仅保留所用子模块
- 代价：构建时间更长，首次配置复杂；适合追求启动速度和体积的发布版

## 代码层优化（不改变功能）
- 延迟导入重型库：
  - `modules/__init__.py` 目前在包导入时就加载大量 Tab（如 `sanger_tab` → Matplotlib；`primer3_gui` → primer3），增加启动时间与体积分析开销
  - 调整为“按需导入”：在各 `open_xxx_tab` 槽函数内部使用 `from modules.<xxx> import Class`，移除 `modules/__init__.py` 对所有模块的顶层导入
- 只在使用时导入：
  - `matplotlib` 与 `primer3` 在具体 Tab 或对话框打开时再 import；主进程启动只载入 PyQt6 基础
- 可选组件降级（保功能不变）：
  - `sanger_tab` 已在缺少 SciPy 时平滑降级；打包时可选择不含 SciPy 以减小体积（若你仍需要平滑，请保留 SciPy）
- 精简资源：
  - Qt 翻译包、帮助文档、未用图标全部排除
  - 仅保留必要的样式与字体（QSS/主题与单字库）

## 启动速度改进建议
- 优先使用 onedir（PyInstaller/Nuitka）减少解压开销
- 启动过程减少顶层导入（见代码层优化）
- 将耗时初始化放入用户操作后再执行（如首次打开某个 Tab 时初始化其模型）
- 如果使用 UPX 压缩，注意其对启动的细微影响，按需权衡

## 构建与验证流程
1. 创建虚拟环境并安装当前 `requirements.txt`
2. 先用 PyInstaller onedir 构建，验证功能与外部 BLAST 工具调用路径
3. 应用排除/裁剪开关，检查体积与启动时间差异
4. 记录 .spec 并固化构建脚本
5. 需要更高优化时，评估使用 Nuitka，逐步迁移并验证

## 我将为你执行的具体步骤（确认后）
- 为 PyInstaller 生成可复用的 `.spec`（含必需的 `datas/binaries/excludes`）
- 调整 `modules/__init__.py` 为按需导入，更新主窗口槽函数的导入路径（不改变功能）
- 试构建 onedir 与 onefile 两个版本，衡量启动与体积；选择最佳作为默认
- 如需最小体积版本，制作“无 SciPy”构建变体（功能保持，平滑降级）
- 输出详细的构建说明与对比数据，为后续发布提供脚本与文档
