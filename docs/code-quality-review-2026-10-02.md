**SeqSketch 代码质量评估与问题清单 — 2026-10-02**

本次评估基于 `F:\SeqSketch` 当前工作区（HEAD `55c4edd`），包括尚未提交的更新检查实现。已有的 `main_window.py`、`menus.py` 修改，以及 `utils/update_check.py`、`tests/test_update_check.py`、`docs/vibe-coding-guide.md` 均未改动。本轮仅新增本报告。

总体判断：项目已经有良好的桌面工具基础，模块划分、共享 FASTA 处理、路径解析、示例数据、运行溯源和回归测试均有实质建设。主要风险集中在科学计算定义、数据身份保持、后台任务生命周期和异常恢复。建议先修复这些问题，再继续扩展功能；当前测试通过不能直接作为科研结果可靠性的保证。

**范围与验证依据**

检查了启动入口、主窗口和菜单、共享组件、FASTA IO、外部工具调用、NCBI 下载、序列分析、比对、拼接与树构建、运行日志、打包及 CI。生产代码统计范围为 `modules/*.py`、`utils/*.py` 和三个入口/窗口文件，共 64 个文件、35,547 行；测试目录有 23 个 `test_*.py` 文件。审阅重点是高风险执行路径与边界条件，不声称逐行证明所有模块正确。

| 检查 | 结果 | 含义 |
| --- | --- | --- |
| `ruff check .` | 通过 | 满足当前仓库的 lint 配置 |
| `py -m pytest -q`，Python 3.13.2、Windows 默认编码 | 513 通过、1 失败、7 条警告 | 工具下载测试发生 GBK 解码错误 |
| 单独重跑失败测试 | 再次失败 | 不是本轮偶发的测试执行顺序问题 |
| `$env:PYTHONUTF8='1'; py -m pytest -q` | 514 通过、6 条警告 | 编码显式统一后，现有回归测试全通过 |
| 最小输入与模拟工具/网络复现 | 见下方 15 项 | 多项错误没有被现有测试发现 |
| 后台任务关闭复现 | 隔离子进程异常退出 | 捕获 `QThread: Destroyed while thread '' is still running` |

所有网络下载复现使用 mock；工具适配器复现模拟外部程序。没有运行完整的真实 MAFFT → trimAl → IQ-TREE 链，没有做 macOS 或打包产物的实际启动验证，也没有压力测试到内存耗尽。报告中的性能、发布和架构建议与已复现 bug 分开理解。

优先级：P1 表示建议发布前处理，涉及崩溃、数据丢失、科学结果错误或越界写入；P2 表示明确的功能、恢复、报告或开发环境问题。排序综合了影响和常见程度，不是漏洞严重度评分。

**1. [P1] ENC 使用已出现的氨基酸家族数量作权重，偏离声明的 Wright 定义**

位置：[codon_usage_tab.py:502](F:/SeqSketch/modules/codon_usage_tab.py:502)，错误权重在第 530 行；对应测试：[test_computation_validation.py:228](F:/SeqSketch/tests/test_computation_validation.py:228)。

复现输入：`{c: 10 for c in ['TTT', 'ATT', 'GCT', 'CTT', 'ATG', 'TGG']}`。包含 2、3、4、6 重简并类别，每个已采样家族只使用一种密码子，因此各类别的 F 为 1。当前 `_compute_enc(..., 1)` 返回 **6.0**；标准代码下的 Wright 权重给出 `2 + 9 + 1 + 5 + 3 = 20`。现有测试甚至将只含 Met/Trp 的结果固定为 2，并将只含 Leu 的计算称为 Wright 参考值。

影响：ENC 和 Nc 图可产生低于标准指标范围的值，造成密码子偏好判断错误；测试固定了错误预期。Wright 原论文说明 Nc 在标准代码下为 20–61，且意在不受氨基酸组成影响。[Wright, 1990](https://pubmed.ncbi.nlm.nih.gov/2110097/)

建议：按明确选定的文献定义实现各简并类别的权重；缺少足够类别数据时给出不可估计状态或注明估计方法，不能简单用已出现家族的数目替代。补充独立文献/参考实现对照，重新审查上述测试；不能仅将结果下限钳制到 20。

**2. [P1] 后台任务运行时关闭标签页或主窗口会销毁仍在运行的 QThread**

位置：[main_window.py:120](F:/SeqSketch/main_window.py:120)、[common_components.py:264](F:/SeqSketch/utils/common_components.py:264)、[common_components.py:320](F:/SeqSketch/utils/common_components.py:320)、[download_from_ncbi_tab.py:545](F:/SeqSketch/modules/download_from_ncbi_tab.py:545)、[main_window.py:461](F:/SeqSketch/main_window.py:461)。

复现：将 `Entrez.efetch().read()` 模拟为等待 2 秒，启动下载后 100 ms 调用 `MainWindow.close_tab(0)`。隔离进程捕获 Qt 的 `QThread: Destroyed while thread '' is still running`，退出码 **3221226505（0xC0000409）**。更新检查模拟等待 2 秒后，在 100 ms 关闭主窗口也异常退出；等待检查完成再关闭的对照进程正常退出（0）。

根因：NCBI 的线程以标签页为 Qt parent，标签页随 `deleteLater()` 销毁；`park_qthread()` 并没有解除 parent 关系或建立可靠的任务所有权。共享停止函数检查 `stop()`，NCBI worker 使用的是 `cancel()`。`QThread.quit()` 不会中断正在运行的阻塞函数。主窗口也没有统一的退出收尾入口。

影响：正常的关闭操作会终止整个应用，其他标签页的未保存结果也会丢失。

建议：统一任务所有权、取消协议与完成收尾，线程应存活到实际 `finished`；关闭期间先申请取消并延迟销毁相关对象。主窗口退出需要覆盖全部任务、更新检查及嵌套 BLAST worker。用隔离进程测试关闭、取消、超时、刚启动就关闭等竞态，避免把崩溃测试放进主 pytest 进程。

**3. [P1] MAFFT 单文件模式静默覆盖重复 FASTA 记录**

位置：[mafft_alignment_tab.py:1032](F:/SeqSketch/modules/mafft_alignment_tab.py:1032)，调用的解析器：[fasta_processor.py:124](F:/SeqSketch/modules/fasta_processor.py:124)。

复现输入：`>a\nAAAA\n>a\nTTTT\n>b\nCCCC\n`。拦截 `start_worker()` 后，实际传入 worker 的 FASTA 只剩 `a=TTTT`、`b=CCCC`，原来第一条 `a=AAAA` 已丢失。当前模式先转字典，再重写输入，因此丢失发生在 MAFFT 执行之前。

影响：三条输入变为两条而用户没有收到错误；后续比对、统计和建树的数据集合发生变化。

建议：进入字典前以记录列表检查重复 ID，拒绝重复或经用户明确选择生成唯一 ID，并保留映射。还应检查单文件和批量输出的记录数与身份一致性。共享 `as_dict()` 已明确声明覆盖行为，修复应落在需要唯一身份的调用边界。

**4. [P1] JC69/K80 把没有可比较位点的序列对记成零距离**

位置：[distance_tree_tab.py:282](F:/SeqSketch/modules/distance_tree_tab.py:282)。

复现：三条比对序列 `A=AAAA----`、`B=----TTTT`、`C=AAAATTTT`。A/B 没有任何共同的有效碱基位点，两个模型都返回 `distance(A,B)=0.0`。

影响：缺少比较依据被当作“完全相同”，产生误导性的距离矩阵和 NJ/UPGMA 拓扑。

建议：在建树前统计序列对的有效比较位点数，对零位点或低于明确阈值的输入拒绝计算并列出样本对；不能直接将 NaN 放入现有建树算法后继续运行。补充全 gap、全 N、互不重叠以及低覆盖输入。

**5. [P1] 一键建树接受带空格的样本名，FASTA 往返时身份丢失**

位置：[one_step_multigenephy_io.py:51](F:/SeqSketch/modules/one_step_multigenephy_io.py:51)、[one_step_multigenephy_workflow.py:169](F:/SeqSketch/modules/one_step_multigenephy_workflow.py:169)、[one_step_multigenephy_workflow.py:36](F:/SeqSketch/modules/one_step_multigenephy_workflow.py:36)。

复现：Excel 样本名为 `Sample A`、`Sample B`，ITS 为 `AAAA`、`TTTT`。`parse_excel_sheet()` 接受它们；写成 FASTA 后通过生产解析函数读回得到 `{'Sample': 'TTTT'}`；按原始样本列表排序则得到 `{}`。

影响：样本 ID 被截断，出现碰撞、丢失或被当作缺失数据，基因可能被跳过。界面的 Check Inputs 仅警告，实际运行没有强制约束；帮助中的“字母、数字、下划线”要求没有形成数据契约。

建议：运行前强制验证 ID，或生成稳定的内部安全 ID 并保存原始名称映射；外部工具输出必须核对所有预期样本。不要通过改变共享 FASTA 的 ID/description 语义来补救。

**6. [P1] 一键建树将 Excel 基因名直接用作文件路径和 NEXUS 标识符**

位置：[one_step_multigenephy_workflow.py:927](F:/SeqSketch/modules/one_step_multigenephy_workflow.py:927)、[one_step_multigenephy_workflow.py:237](F:/SeqSketch/modules/one_step_multigenephy_workflow.py:237)、[one_step_multigenephy_workflow.py:443](F:/SeqSketch/modules/one_step_multigenephy_workflow.py:443)。

复现：基因列名为 `../../escaped` 时，`01_normalized/../../escaped.fasta` 的解析后路径落在用户选定运行目录之外；在临时目录中已验证写入。`ITS (rDNA)` 生成 `charset ITS (rDNA) = 1-4;`，原始名称未经转换直接进入分区语法。含 `/`、`\\`、Windows 保留字符或规范化碰撞的列名也没有统一处理。

影响：工作簿能够触发输出目录之外的文件写入或覆盖；普通带括号/空格的列名还可能导致下游工具无法解析。这是本地输入到路径的约束缺失，未发现或声称远程代码执行。

建议：把显示名、内部基因 ID、文件名和分区标识符分开；规范化后全局去重，保存映射。对每个输出路径 resolve 后检查仍位于指定运行根目录内；禁止绝对路径和目录跳转。

**7. [P2] NCBI 已返回数据，但无版本 accession 被报告为失败**

位置：[download_from_ncbi_tab.py:256](F:/SeqSketch/modules/download_from_ncbi_tab.py:256)。

复现：请求 `AB123`，模拟返回 `>AB123.1 example\nATGC\n`。报告显示 `sequences_returned=1`，但 `succeeded_accessions=[]`、`failed_accessions=['AB123']`。

影响：下载文件与成功/失败报告相互矛盾，用户可能重复下载或误认为数据缺失。无版本 accession 指向最新版本，是 NCBI 定义的正常行为。[NCBI Sequence Identifiers](https://www.ncbi.nlm.nih.gov/genbank/sequenceids/)

建议：请求无版本时可按 accession 基础部分匹配；请求显式版本时必须继续严格匹配版本。报告保留“请求 ID → 实际返回 accession.version”映射，支持旧式管道分隔头的规范化。

**8. [P2] 拼接模块的基因名称去重会与已有后缀名碰撞**

位置：[partition_concat_tab.py:151](F:/SeqSketch/modules/partition_concat_tab.py:151)。

复现：`_sanitize_gene_names(['gene', 'gene', 'gene_2'])` 返回 `['gene', 'gene_2', 'gene_2']`。完整 NEXUS 数据块中出现这两条同名 charset 后，Biopython 解析结果只保留最后一段 `gene_2` 范围。

影响：不同基因对应同一分区名，分区可被覆盖或遭下游工具拒绝。文件来自不同文件夹时，同名 stem 是正常输入场景。

建议：用“所有已分配名称”的集合控制唯一性，分配后缀时循环查冲突；覆盖已有后缀、规范化碰撞和多次重复的测试。

**9. [P2] 一键建树的 tree 恢复模式查找的 trimmed 文件名与实际输出不一致**

位置：[one_step_multigenephy_workflow.py:276](F:/SeqSketch/modules/one_step_multigenephy_workflow.py:276)、[one_step_multigenephy_workflow.py:1022](F:/SeqSketch/modules/one_step_multigenephy_workflow.py:1022)、[one_step_multigenephy_workflow.py:1052](F:/SeqSketch/modules/one_step_multigenephy_workflow.py:1052)。

复现：保留默认生产适配器，只模拟工具执行。第一次运行输出 `03_trimmed/ITS.trimmed.fasta`；第二次以 `resume_mode='tree'` 运行、输入指纹一致，仍依次调用 align、trim、tree。恢复检查寻找的是 `ITS.fasta`。同一次恢复中 Concatenate 又被标为 skipped。

影响：用户选择仅重建树仍重复耗时的比对/修剪；新计算的中间产物与直接复用的 supermatrix 分属不同执行批次。使用理想化文件名的 mock 容易隐藏这种生产契约错误。

建议：按 manifest 中的真实 artifact 路径恢复，或统一命名函数。将“默认适配器首次运行 → 同指纹恢复 → 应只调用 IQ-TREE”加入契约测试，并检查中间文件完整性。

**10. [P2] Sanger 反向互补未实现 IUPAC 模糊碱基转换**

位置：[sanger_tab.py:536](F:/SeqSketch/modules/sanger_tab.py:536)。

复现：`reverse_complement('ARYK')` 返回 `KYRT`，Biopython 对同一输入返回 `MRYT`。当前函数只映射 A/C/G/T，R/Y/K/M 等被原样保留。

影响：含模糊碱基的测序读段在反向互补后错误，影响重叠判定和输出序列。输入路径没有拒绝这些字符。

建议：复用 Biopython 的 IUPAC 反向互补或建立共享完整映射，并明确模糊碱基在 identity 中如何处理。补充所有 IUPAC 字符的测试。

**11. [P2] Sanger 接受多记录 FASTA 并将所有记录直接拼为一条读段**

位置：[sanger_tab.py:281](F:/SeqSketch/modules/sanger_tab.py:281)。

复现：`_sequence_from_input('>one\nAAAA\n>two\nTTTT\n')` 返回 `AAAATTTT`。解析仅过滤所有 header，不保留记录边界，也不确认文件只有一条序列。

影响：不同样本可被混成一个 forward/reverse 输入，产生外观正常的 assembled_contig。

建议：FASTA 使用 `FASTAProcessor` 读取，Sanger 当前单样本模式强制恰好一条记录；原始文本也应校验字母表和空白。多样本支持需要独立的匹配与批量模式。

**12. [P2] 运行中输出路径仍可修改，完成处理读取的是当前控件值**

位置：[download_from_ncbi_tab.py:468](F:/SeqSketch/modules/download_from_ncbi_tab.py:468)、[download_from_ncbi_tab.py:576](F:/SeqSketch/modules/download_from_ncbi_tab.py:576)、[mafft_alignment_tab.py:1002](F:/SeqSketch/modules/mafft_alignment_tab.py:1002)、[mafft_alignment_tab.py:1133](F:/SeqSketch/modules/mafft_alignment_tab.py:1133)。

复现：NCBI 在 running 状态下 `output_edit.isEnabled()` 和 Clear 按钮仍为 True。起始设置 original.fasta，运行中改为 changed.fasta，再触发生产完成处理，实际只生成 changed.fasta。MAFFT 也允许手工修改路径，worker 保存的原路径用于 provenance，完成回调却重新读取控件。

影响：结果写到意外位置，Clear 后可能保存失败；MAFFT 的日志目录与输出目录也可能不一致。

建议：提交任务时冻结输入、参数、输出路径与报告选项，完成回调使用任务快照；运行中禁用会改变任务语义的控件与 Clear。结果保存尽可能由同一任务完成，UI 只展示确定的结果路径。

**13. [P2] MAFFT 计算完成但保存失败后没有恢复全部按钮状态**

位置：[mafft_alignment_tab.py:1082](F:/SeqSketch/modules/mafft_alignment_tab.py:1082)。

复现：先设 running 状态，再将 `_write_single_file_output` 模拟为 `PermissionError`。完成回调退出后 Run 为 enabled，但 Clear 和 Upload File 仍 disabled。

影响：用户修复目录权限或调整输入的常规操作受阻，界面状态与真实任务状态不一致。

建议：用 `finally` 或统一的完成/失败状态转换恢复所有控件，并保留已经算出的 alignment 供另存。测试计算失败、保存失败和日志失败，不能只覆盖成功分支。

**14. [P2] 只填写相对输出文件名时，MAFFT/MUSCLE/BLAST 可缺失 run_log.txt**

位置：[mafft_alignment_tab.py:249](F:/SeqSketch/modules/mafft_alignment_tab.py:249)、[multiple_sequence_alignment_tab.py:118](F:/SeqSketch/modules/multiple_sequence_alignment_tab.py:118)、[blast_run_dialog.py:122](F:/SeqSketch/modules/blast_run_dialog.py:122)、[run_provenance.py:111](F:/SeqSketch/utils/run_provenance.py:111)。

复现：输出为 `result.fasta` 时 `os.path.dirname(output_path)` 为 `''`；在临时 cwd 中调用同样的 provenance 路径，未创建 run_log.txt。共享函数在 output_dir 为空时直接返回。

影响：数据产物能够存在，版本与命令记录却缺失，违反项目对每次外部工具运行的溯源约定。

建议：在提交任务时先将输出路径转换为绝对路径，日志目录取实际输出 parent。补充相对路径、含空格/中文路径与保存失败时的状态测试；日志无法写入应向用户给出可辨识的警告。

**15. [P2] 工具下载回归测试依赖默认系统编码，在中文 Windows 可确定失败**

位置：[test_fetch_softwares.py:47](F:/SeqSketch/tests/test_fetch_softwares.py:47)。

复现：默认环境全套测试和单独运行 `test_fetch_rejects_a_macos_bundle_without_trimal` 均失败。`subprocess.run(text=True)` 用 GBK 解码 PowerShell 的 UTF-8 错误输出，reader thread 产生 UnicodeDecodeError，随后第 100 行拼接 `None + str` 抛 TypeError。UTF-8 模式下全套 514 项通过。

影响：开发者在中文系统上拿不到真实脚本错误信息，并误以为项目回归失败。它是开发环境兼容问题，不等同于所有 GUI 操作失败。

建议：该测试显式设置 `encoding='utf-8', errors='replace'`，或先捕获 bytes 再统一解码。同步审查 BLAST 和版本探测中依赖默认编码的 subprocess 调用。

**从开发者角度的评价与建议**

| 维度 | 现状评价 | 应采取的行动 |
| --- | --- | --- |
| 模块与架构 | 独立 Tab、懒加载、共享 IO 和路径工具是有效基础；部分文件和函数负担过重 | 保留现有单实例/多实例约定，逐步分离计算、任务、文件写入和 UI |
| 科学正确性 | 有计算验证测试，但 ENC 说明“手算”测试仍可能复刻错误公式 | 引入文献、成熟参考工具的独立对照与有效输入域检查 |
| 测试 | 514 项回归覆盖大量正常流程、UI、帮助、示例和输出；未测得覆盖率 | 优先补任务生命周期、身份保持、恢复命名、I/O 异常等契约测试 |
| 可维护性 | 共 35,547 行；最大的 Tab 为 1,680 行，workflow.run 为 496 行 | 将长工作流拆为明确阶段，减少共享可变状态与隐式控件读取 |
| 可复现性 | 已有版本探测、run_log、manifest、报告和输入指纹 | 记录随机 seed、输入 checksum、实际 accession.version、真实 artifact 路径 |
| 交付 | 双平台测试、三种发行目标、工具许可证与依赖许可证检查已有基础 | 加入打包后启动、工具发现与极小真实分析的 smoke test |
| 用户体验 | 统一底部按钮、日志、示例和 Help 对教学有帮助 | 使失败、取消、部分成功、保存失败的状态和后续动作一致 |

建议按以下顺序实施，而不是一次性重构整个项目：

1. **先修结果与崩溃。** 处理问题 1–6，为每项建立独立失败样例；对已输出的 ENC 与零位点距离结果明确标注需要重新计算。
2. **建立任务和文件契约。** 统一取消/退出协议、任务快照、结果对象和收尾；所有完成状态应区分“计算成功”“文件已保存”“部分失败”“已取消”。
3. **强化输入身份。** 共用 FASTAProcessor，但在调用边界选择严格程度：拒绝重复、空记录、多记录输入或不支持的字母表，并报告变换/丢弃计数。
4. **加强独立验证。** 用小型固定数据对照公式与参考工具；默认测试继续 mock 网络，同时覆盖真实生产适配器的文件命名和 manifest；生命周期测试使用子进程。
5. **稳定发布。** 保留开发依赖的合理范围，为发行构建记录/锁定已验证依赖组合与工具包摘要；在源码测试之后测试打包产物。对科学算法使用随机数的流程提供 seed。
6. **渐进拆分。** 优先拆 workflow.run 和比对 worker，形成可无 Qt 测试的计算层；不为统一形式改变现有 Tab 复用行为。启用额外 lint 规则应逐步进行，318 条 B/UP/SIM 提示多为风格与现代化事项，不能当作 318 个实际 bug。
7. **统一文档约束。** [pyqt-tabs.instructions.md:17](F:/SeqSketch/.github/instructions/pyqt-tabs.instructions.md:17) 仍建议 `self.tr(...)`，与 AGENTS.md 的 English-only 决策冲突，应同步修正，保留当前英语 UI 决策。配置管理模块目前 unused，不应误认为它的长度上限等配置已实际保护计算流程。

对文件写入还建议采用同目录临时文件写完再替换的模式，集中处理输入/输出同路径、已有文件覆盖和多文件结果的失败收尾。这是从现有直接 `open(..., 'w')` 路径得出的改进建议，本轮没有人为制造磁盘故障来证明所有写入点都会损坏原文件。

性能上，[DotPlot 的矩阵构建](F:/SeqSketch/modules/dotplot_tab.py:223) 和 [Pairwise 的比对计算](F:/SeqSketch/modules/pairwise_alignment_tab.py:483) 仍在 GUI 线程进行。DotPlot 已有大矩阵确认提示，但提示不能保证 UI 可响应；重复 k-mer 还会增加大量绘制矩阵的操作。建议使用 worker、资源预算和稀疏/降采样表示，再按真实教学与研究数据做性能基准。本轮没有执行极大输入以验证内存上限。

**从使用者角度的建议**

项目适合以示例数据学习流程；重要分析目前需要增加核对环节。科学结果校验应在应用内明确呈现，不能长期依赖使用者手工规避。

1. 修复前避免在任务运行中直接关闭标签页或退出应用，等待任务结束；不要在运行中修改输出路径或点击 Clear。
2. 一键建树暂用唯一的字母/数字/下划线样本 ID，基因列名使用简洁安全字符。保留原始样本名与内部 ID 对照；每一步核对样本数、基因数和缺失数据。
3. MAFFT 输入先检查重复记录。Sanger 的两个文件各只放一条读段；含模糊碱基的反向序列需要使用正确 IUPAC 转换核对。
4. ENC 结果暂不直接用于科研解释；含无共同有效位点的距离树应重新检查。重要结果用独立参考实现或工具作交叉验证。
5. NCBI 尽量记录返回的完整 accession.version；当前失败列表不能作为是否拿到数据的唯一依据，需要对照实际 FASTA。
6. 每次分析使用独立输出目录，保留原始输入、结果、run_log 和 manifest；tree 恢复模式目前可能重复计算，不能根据选择名称判断实际跳过了哪些步骤。

产品层面建议显示输入预检摘要（类型、条数、重复、缺失、字母表）、计算资源预估、清晰的部分成功说明，以及可以直接另存/重试的失败界面。自动生成的报告应包括数据身份和过滤说明，使用户能够理解最后用了哪些样本与基因。

**建议的验收标准**

修复后首先要求：标准代码 ENC 的参考数据正确；关闭任何运行中的任务不崩溃且不留下后台工具；重复 ID 不静默丢失；零比较位点被明确拒绝；所有生成路径留在指定运行目录内；FASTA 往返保持样本身份；生产文件命名支持真正恢复；相对路径也生成完整溯源。之后再验证小型真实工具链及 Windows/macOS 的打包产物。
