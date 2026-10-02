**SeqSketch 修复计划 — 2026-10-02**

状态：已实施 15 项修复，版本更新为 1.0.1。Windows 交付验证见[验证记录](release-validation-1.0.1.md)；macOS 原生验证仍需 macOS CI/设备执行。

依据：[代码质量评估中的 15 项问题](F:/SeqSketch/docs/code-quality-review-2026-10-02.md)。以下编号与评估报告一致。目标是消除已复现的崩溃和结果错误，建立可验证的数据与任务约束，再完成发布验证。

实施保留现有英语 UI、Tab 单实例/多实例约定、FASTA 的 ID/description 语义、缺失基因填 gap 的策略、工具路径覆盖与配置迁移，以及 portable onedir 的数据位置。现有更新检查修改纳入兼容测试。

| 阶段 | 覆盖问题 | 交付结果 | 进入下一阶段的条件 |
| --- | --- | --- | --- |
| 0. 建立稳定基线 | 15 | 默认中文 Windows 环境可运行测试 | 编码问题的回归通过 |
| 1. 修复任务退出 | 2 | 标签页和窗口关闭有明确的取消、等待、销毁流程 | 隔离进程关闭测试正常退出 |
| 2. 修复科学计算 | 1、4、10 | ENC、无有效位点距离、IUPAC 反向互补遵循明确的数据定义 | 独立参考值与边界测试通过 |
| 3. 保证数据身份与路径 | 3、5、6、8、11 | 重复/多记录输入被识别，样本身份稳定，文件与分区名安全唯一 | 所有身份与路径回归通过 |
| 4. 修复恢复、保存与报告 | 7、9、12、13、14 | 任务使用固定参数，真实产物支持恢复，报告与输出一致 | 生产适配器契约及异常保存测试通过 |
| 5. 发布验证 | 全部问题 | 源码、真实工具链、打包产物均有验证记录 | 满足文末发布门槛 |

阶段 1–3 完成所有 P1 问题；阶段 2–3 同时处理直接相关的 P2，减少同一数据边界反复修改。

**阶段 0：建立稳定测试基线**

修改范围：[test_fetch_softwares.py](F:/SeqSketch/tests/test_fetch_softwares.py)、[run_provenance.py](F:/SeqSketch/utils/run_provenance.py)、[BLAST worker](F:/SeqSketch/modules/blast_run_dialog.py)、[makeblastdb worker](F:/SeqSketch/modules/blast_make_db_dialog.py)。

1. 为 PowerShell 测试输出显式指定 UTF-8 解码，并对非正常字节采用替换策略；保留原始脚本退出码和错误消息。
2. 清点 subprocess 的输出编码，给 BLAST 和版本探测建立一致的解码边界。选择 bytes 捕获或明确 encoding，确保非 ASCII 路径的错误信息不会触发二次异常。
3. 将报告中的最小输入转为后续阶段的回归样例；会导致 Qt 原生退出的用例在隔离子进程运行。

验收：失败的工具下载测试能读取真实的 trimAl 缺失信息；默认环境通过，无需依赖 `PYTHONUTF8=1` 才能得到正确结果。

**阶段 1：修复后台任务生命周期**

修改范围：[main_window.py](F:/SeqSketch/main_window.py)、[common_components.py](F:/SeqSketch/utils/common_components.py)、[process_control.py](F:/SeqSketch/utils/process_control.py)，以及拥有线程的 Tab/嵌套组件。

1. 建立任务清单，覆盖 NCBI、更新检查、MAFFT/MUSCLE 单文件与批量、trimAl、IQ-TREE、One Step、嵌套 BLAST 建库/查询、引物、距离树、限制性酶、密码子分析、Sanger 查看与树图渲染/导出。
2. 每个任务明确 worker、线程、子进程和完成信号的所有者；将 `stop()`、`cancel()`、`requestInterruption()` 等现有协议收敛到一个明确的取消入口。
3. 关闭标签页时先进入 closing 状态并申请取消。标签页可以先从界面移除，但任务对象与必要的 owner 必须保留到实际线程结束；关闭后完成回调不得再弹对话框或更新已销毁控件。
4. 主窗口通过 `closeEvent` 统一处理所有任务。仍有任务时延迟退出，通过信号完成收尾，使 GUI 保持响应；避免在 GUI 线程无限 `wait()`，也不使用 `QThread.terminate()`。
5. 为网络操作设置有限超时；取消中的阻塞请求可以等待其超时，但线程不能被提前销毁。外部工具取消应终止整个进程树并完成回收；Windows 沿用现有进程树处理，macOS 的进程组处理需配套验证。
6. 仅在真实完成后清理引用、释放 QObject/QThread；对重复取消、刚启动即关闭和多个同时运行的任务确保收尾只执行一次。

测试：新增隔离进程生命周期测试，验证慢 NCBI、慢更新检查、模拟外部工具、嵌套 BLAST、多任务退出；包含正常完成、错误、超时、取消和关闭竞态。子进程设置总超时并检查退出码，模拟子进程结束后检查没有残留。

验收：报告中的两种关闭操作退出码为 0；无 `QThread: Destroyed while thread is still running`，无关闭后的模态弹窗；等待收尾期间界面可以处理事件，计算工具不遗留。

**阶段 2：修复科学计算边界**

修改范围：[codon_usage_tab.py](F:/SeqSketch/modules/codon_usage_tab.py)、[distance_tree_tab.py](F:/SeqSketch/modules/distance_tree_tab.py)、[sanger_tab.py](F:/SeqSketch/modules/sanger_tab.py)、[test_computation_validation.py](F:/SeqSketch/tests/test_computation_validation.py)。

1. ENC 先确定并记录使用的文献算法。标准遗传密码表按类别权重实现，修正当前以已出现家族数作权重的代码；替换报告指出的错误测试预期。
2. 缺少必要类别或样本不足时默认返回“不可估计”，以 `None` 等明确状态贯穿结果模型。同步处理摘要、比较表、CSV 和 Nc 图，让它们显示 `N/A` 或跳过无法绘制的点，并说明原因。
3. 非标准遗传密码表的 ENC 系数必须从对应密码表推导并独立核验；尚无可靠定义或验证的组合给出不可估计状态。实现前完成公式与估计条件核查，避免简单钳制到 20 掩盖错误。
4. JC69/K80 在比较位点为零时抛出包含样本 ID 的输入错误，在建树前拦截；报告每对有效位点数。第一版硬性拒绝零位点，低覆盖情况提示有效位点数，避免未经验证新增任意过滤阈值。统一将 RNA 的 U 规范化为 T。
5. Sanger 复用 Biopython 的 IUPAC 反向互补。identity 的模糊碱基处理需有明确说明与测试：N/N 不作为可靠的匹配证据，不能仅以字符相等抬高重叠可信度。

测试：ENC 极端偏好、均匀使用、缺失类别、无密码子、终止密码子及非标准表；距离的相同序列、无重叠、全 gap/全 N、U/T；完整 IUPAC 映射。科学参考值来自文献或独立参考实现，而非复制待测函数的逻辑。

验收：报告中六种密码子各 10 次的标准代码输入 ENC 为 20；短输入不会显示误导性的有效 ENC；无共同有效位点不能生成距离树；`ARYK` 的反向互补为 `MRYT`。

**阶段 3：保证记录身份、名称和路径**

修改范围：[fasta_processor.py](F:/SeqSketch/modules/fasta_processor.py)、[mafft_alignment_tab.py](F:/SeqSketch/modules/mafft_alignment_tab.py)、[one_step_multigenephy_io.py](F:/SeqSketch/modules/one_step_multigenephy_io.py)、[one_step_multigenephy_workflow.py](F:/SeqSketch/modules/one_step_multigenephy_workflow.py)、[partition_concat_tab.py](F:/SeqSketch/modules/partition_concat_tab.py)、[sanger_tab.py](F:/SeqSketch/modules/sanger_tab.py)。

1. 在记录列表转字典之前增加可复用的唯一 ID 校验。MAFFT 单文件与批量都检查主 ID，包括“同一 ID、不同 description”的情况；默认拒绝重复并指出记录位置，保留共享 `as_dict()` 已声明的覆盖行为。
2. 核对外部工具输入/输出记录集合，重复、意外 ID 和非预期丢失必须显式报告；保留正常的输入顺序控制。
3. 一键建树第一版按照既有帮助，强制样本 ID 仅含字母、数字、下划线，非法名称在运行前报错并列出行号。自动改名是后续独立功能，需完整映射，避免本轮引入隐式身份转换。
4. 普通基因显示名允许保留空格和括号；生成确定的安全内部 ID，分别用于文件名与分区，保存显示名映射。拒绝绝对路径、目录跳转与路径分隔符；处理 Windows 保留名及大小写文件名碰撞。
5. 每个自动生成的文件路径 resolve 后验证处于选定运行目录内。各阶段使用同一名称映射，使恢复指纹和 manifest 也采用一致身份。
6. 修复 `_sanitize_gene_names()` 的全局唯一性；新名称必须避开所有已分配名称，不能只增加某个原始名称的计数。测试已有 `_2` 后缀和多个名称规范化到相同字符串的情况。
7. Sanger FASTA 输入统一经 FASTAProcessor 读取并强制恰好一条有效记录；原始文本规范化空白并校验 IUPAC 字母表。错误输入不能覆盖上一轮有效结果而假装生成新 contig。

测试：精确重复 ID、同 ID 不同描述、空 header、带空格样本名、普通括号基因名、`../` 和 Windows 路径、大小写及保留名、名称后缀碰撞、Sanger 多记录输入。路径测试全部使用临时目录。

验收：三条重复输入在启动工具之前被拒绝；所有规范化名称唯一且能追踪到原名称；没有文件写出运行目录；分区数、记录数与有效输入一致；Sanger 多记录输入得到明确错误。

**阶段 4：修复任务快照、恢复和结果报告**

修改范围：NCBI、MAFFT/MUSCLE、BLAST worker 与 Tab、One Step workflow、run_provenance。

1. 提交任务时捕获输入、参数、绝对输出路径和报告选项，完成回调仅使用该任务的数据。运行中禁用会改变本次任务的控件与 Clear；以任务标识避免旧回调改变下一次任务状态。
2. 统一 success/error/cancel/save-error 的收尾。MAFFT 保存失败也要恢复全部控件，保留计算结果以便另存；计算完成与保存完成的状态分别表述。
3. 输入无版本的 NCBI accession 按基础 accession 匹配实际版本；显式版本必须严格匹配。保存请求到返回 ID 的映射，让文件、成功列表、失败列表和条数一致。
4. One Step 恢复从 manifest 的真实 artifact 路径读取，或通过统一命名函数生成路径；修复 `ITS.fasta` 与 `ITS.trimmed.fasta` 不一致。
5. 恢复时校验输入指纹、名称映射、样本集合、序列长度和 artifact 完整性。部分中间产物失效后，按依赖关系重新计算下游，避免新修剪结果配旧 supermatrix；旧 manifest 缺少必要信息时明确提示并安全重新运行。
6. 外部工具 provenance 使用最终绝对输出 parent，单文件相对路径也创建 run_log.txt。记录写入发生在 worker 中；无法写入日志时保留分析结果并显式提示。
7. 将结果写入同目录临时文件后再替换目标文件，保存失败保留已有目标。输入输出同路径和覆盖行为集中校验；多文件产物只有通过必要完整性检查后才能标为成功。

测试：运行后修改控件、Clear 与旧回调、PermissionError、磁盘写入异常、报告写入异常、相对/中文/空格路径、无版本/错版本 accession、默认适配器首次运行再恢复，以及某个 artifact 被删除或损坏后的恢复。

验收：修改控件不会改变已提交任务的目标；保存失败后可以调整输入并另存；NCBI 报告与数据一致；同指纹的有效 tree 恢复只执行 IQ-TREE；所有成功的外部工具运行有对应溯源日志。

**阶段 5：验证、文档与交付**

1. 按模块运行最窄相关测试，再运行对应完整套件；涉及共享组件和主窗口的变更通过全套测试后进入下一批。最终同时验证默认中文 Windows 环境与 UTF-8 模式。
2. 在已有工具 bundle 的环境，用小型固定数据执行 MAFFT → trimAl → 拼接 → IQ-TREE，并检查记录集合、分区覆盖、tree tips 和 provenance。NCBI 默认保持 mock，真实请求验证是可选项。
3. Windows portable 构建后，从含空格/中文的路径启动，验证工具发现、示例、输出、配置覆盖和退出。macOS arm64 与 x86_64 在对应 runner 上分别验证；无法实测时记录限制，不标为通过。
4. 同步 Help/README：ENC 的适用条件、非法输入提示、保存失败恢复、旧 manifest 的兼容处理，以及修复前相关结果可能需要重新核验。修正 scoped instructions 与 English-only 决策的冲突。
5. 更新 APP_VERSION，并记录发行依赖与工具版本；现有配置迁移、许可测试和 example-data 测试保持通过。

建议的提交拆分：

| 提交 | 内容 | 问题编号 |
| --- | --- | --- |
| 1 | subprocess 编码与测试基线 | 15 |
| 2 | 任务关闭、取消与对象收尾 | 2 |
| 3 | ENC 与距离计算定义 | 1、4 |
| 4 | FASTA 唯一性与 Sanger 输入/互补 | 3、10、11 |
| 5 | One Step 名称安全与分区去重 | 5、6、8 |
| 6 | One Step artifact 恢复契约 | 9 |
| 7 | 任务快照与保存失败恢复 | 12、13 |
| 8 | NCBI accession 返回映射 | 7 |
| 9 | 绝对路径溯源、原子保存和交付验证 | 14 及所有回归 |

每个提交先建立能复现问题的回归，再实现修复。涉及真实 subprocess 行为的测试可模拟程序执行，但保留生产适配器的文件命名、路径和结果解析，不用理想化 mock 替代这些契约。

常用验证命令：

```powershell
py -m pytest tests/test_fetch_softwares.py -q
py -m pytest tests/test_computation_validation.py tests/test_distance_tree_tab.py -q
py -m pytest tests/test_dna_analysis_tabs.py -q
py -m pytest tests/test_one_step_multigenephy_workflow.py tests/test_one_step_multigenephy_tab.py tests/test_partition_concat_tab.py -q
py -m pytest tests/test_blast_tabs.py tests/test_update_check.py tests/test_run_provenance.py -q
py -m pytest tests/test_fasta_tools_tabs.py tests/test_fasta_processor.py tests/test_example_data.py -q
py -m pytest -q
ruff check .
.\scripts\build_onedir.ps1
```

生命周期隔离测试已新增，可执行 `py -m pytest tests/test_task_lifecycle.py tests/test_quality_regressions.py -q`。本次完整验证结果与版本依赖见[交付验证记录](release-validation-1.0.1.md)。

发布门槛是 15 项问题均有对应通过的回归；六项 P1 的原始复现均失效；默认编码环境全套 pytest 与 Ruff 通过；真实小型工具链与 Windows 打包验证完成；macOS 结果按实际验证状态记录。已有结果的科学定义发生变化时，应在发行说明中说明，避免用户把新旧 ENC 直接混用。

在这些修复之后另开性能与结构优化工作：将 DotPlot/Pairwise 的长计算移到 worker，增加资源预算、稀疏/降采样方案和固定数据基准；逐步拆分长 workflow 与 Tab。它们需要独立的性能证据与验收，不作为掩盖上述 bug 的大型重构。
