**SeqSketch 1.0.1 修复与交付验证 — 2026-10-02**

本次执行[修复计划](code-quality-fix-plan-2026-10-02.md)。修复覆盖评估中的全部 15 项。原有更新检查及菜单修改保留并纳入兼容测试；未创建 Git 提交。

| 问题 | 已实现的结果 | 主要回归证据 |
| --- | --- | --- |
| 1 ENC | 正确类别权重；缺少估计条件/非标准代码为 N/A；显示、图及 CSV 同步处理 | `test_computation_validation.py`、ENC 显示/导出回归 |
| 2 任务关闭 | 所有嵌套任务统一发现；延迟销毁；关闭回调保护；异步取消及进程树回收 | `test_task_lifecycle.py` 的六种隔离进程场景；POSIX 进程组约束回归 |
| 3 重复 ID | FASTA 字典转换前验证主要 ID；单文件及批量比对结果验证 | `test_quality_regressions.py`；DNA Tabs 的原有重复输入回归 |
| 4 无可比位点 | JC69/K80 报出样本对；U/T 归一化 | `test_distance_tree_tab.py` |
| 5 样本名称 | Excel 行号提示并拒绝不稳定 ID；runner 入口再次验证 | Excel 样本 ID 回归 |
| 6 基因名称/路径 | 安全唯一 ID、原名映射、输出路径及链接边界 | 名称安全/冲突回归；生产适配器特殊名称完整运行 |
| 7 NCBI 版本 | 基础 accession 与显式版本不同的匹配规则；报告保留映射 | 版本及旧式 header 回归；原有 mock 下载测试 |
| 8 分区名称 | 全局已分配名称集合，覆盖大小写及后缀冲突 | 分区名称冲突回归 |
| 9 恢复运行 | manifest 的真实路径及文件校验；无效产物触发完整重算 | 生产适配器首次运行/恢复/删除/修改四类契约；真实工具链恢复 |
| 10 IUPAC 互补 | 完整互补，模糊碱基不计可信匹配 | IUPAC 全字符及 N/N 重叠回归 |
| 11 Sanger 多记录 | 单记录约束与字母表验证 | 多记录、空输入及非法字符回归 |
| 12 参数快照 | 运行开始固定输出路径、报告选项及顺序；禁用控件和 Clear | MAFFT/NCBI 路径修改及 Clear 回归；关闭时旧回调隔离测试 |
| 13 保存恢复 | MAFFT 保存失败恢复控件并保留结果 | PermissionError 后控件、状态、数据及再次保存回归 |
| 14 溯源路径 | 相对路径父目录；原子保存；溯源失败有日志提示 | 相对路径溯源、原子保存失败回归；真实中文/空格输出目录 |
| 15 默认编码 | PowerShell、BLAST、版本探测明确解码 | 默认编码全套 pytest；`test_fetch_softwares.py` |

主要新增回归位于 [test_quality_regressions.py](../tests/test_quality_regressions.py) 和 [test_task_lifecycle.py](../tests/test_task_lifecycle.py)。必要的原有测试更新了错误的 ENC 参考值、版本常量、恢复 manifest 和 subprocess mock 参数；没有删除原有覆盖。

验证命令与最终结果在本文件末尾记录。Windows 主测试环境为 Python 3.13.2；打包使用项目 `.venv`，并在该环境重复全套测试。未为测试设置 `PYTHONUTF8=1` 绕过默认编码问题。

真实外部工具验证使用八物种 cytb 教学数据，无网络下载。分别使用普通路径及含中文/空格的输出目录；两次都完成 MAFFT → trimAl → IQ-TREE，并验证第二次建树恢复仅调用 IQ-TREE。工具版本：MAFFT 7.526、trimAl 1.5.rev1、IQ-TREE 3.1.3。原始 manifest、HTML 和树文件位于 `dist/quality-review-2026-10-02/tool-chain/` 及 `dist/quality-review-2026-10-02/工具链 验证/`。

Windows 打包在独立 QA 输出目录执行，不使用会原地裁剪工具 bundle 的 `build_onedir.ps1`。验证中发现环境 PATH 的 Poppler ICU 覆盖 Windows ICU，已在 spec 修复并加入回归。构建后把便携目录改为含中文和空格的名称，并从仓库外的 Temp 工作目录运行 `SeqSketch.exe --smoke-test`：要求退出码 0，十个标签页正常载入，教学资源可读。启动日志写在该便携目录的 `user_data/startup.log`。

打包依赖版本：Python 3.13.2；PyQt6/Qt6 6.10.0；Biopython 1.86；NumPy 2.3.4；Matplotlib 3.10.7；pandas 3.0.1；primer3-py 2.2.0；openpyxl 3.1.5；logomaker 0.8.7；toytree 3.0.11；pymsaviz 0.5.0；PyInstaller 6.22.3。`.venv` 的许可证生成检查通过（18 个文件）。系统 Python 的依赖版本与此不同，许可证检查会提示版本目录不一致；本次交付使用与现有许可证目录相符的 `.venv`。

已知验证边界：macOS 的原生工具、POSIX 实际子进程树和 `.app` 打包尚未在本机验证，需由 macOS CI/设备执行。Sanger 图的 Matplotlib `set_tight_layout` 有既有弃用警告。两个环境的 `pip check` 还检测到非核心/可选旧包的安装问题（`.venv` 的 sangerseq-viewer 缺 python-queen；系统环境的 torchvision、cyclonedx-bom、python-queen 冲突），本次没有改动这些全局或可选包。核心十个标签页的源码和打包 smoke 均作为独立运行检查。

性能和大文件资源预算、DotPlot/Pairwise 的同步计算、进一步拆分长 Tab/workflow，仍按原计划另行优化。

最终验收已完成：

| 验证 | 结果 |
| --- | --- |
| `py -m pytest -q`，默认 Windows 编码环境 | 560 passed，7 条既有 Matplotlib 弃用警告 |
| `.venv/Scripts/python.exe -m pytest -q`，与打包相同的运行依赖 | 560 passed，7 条相同警告 |
| `ruff check .` | 通过 |
| `git diff --check` | 通过（仅 Git 的 LF/CRLF 提示） |
| `.venv` 许可证生成 `--check` | 18 个文件，通过 |
| 真实工具链普通目录/中文空格目录及恢复 | 通过；恢复仅运行 IQ-TREE |
| 已打包工具在中文便携路径中的实际执行 | 通过；源码验证脚本将 resource root 指向实际便携包，使用包内的 MAFFT、trimAl、IQ-TREE 完成分析与恢复 |
| 最新 Windows 包，从仓库外工作目录运行 `--smoke-test` | 退出码 0，十个标签页及资源检查通过 |

最新验证包：[SeqSketch.exe](<../dist/quality-review-2026-10-02/portable/SeqSketch 中文 最终验证/SeqSketch.exe>)，整个所在目录为便携产物。打包日志位于 `dist/quality-review-2026-10-02/build.log`；已打包工具的真实流水线记录位于 `dist/quality-review-2026-10-02/便携工具链 验证/`。现有 `dist/SeqSketch/` 未作为此次构建输出。
