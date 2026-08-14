## 计划：修正日志与帮助文档中笼统的工具兼容性表述

文件：`modules/partition_concat_tab.py` + `tests/test_partition_concat_tab.py`

### 1. worker 完成摘要改为格式感知（:463）
`_ConcatPartitionWorker.run()` 末尾的 `"Ready for IQ-TREE, MrBayes, or RAxML-NG with partition-aware models."` 改为按 `self.partition_format` 分支：
- `"iqtree"` → `"Ready for IQ-TREE with partition-aware models (load the .nex with -p). For MrBayes, switch the partition format to 'NEXUS DATA (MrBayes)'."`
- `"mrbayes"` → `"Ready for MrBayes with partition-aware models (the .nex data file is also readable by IQ-TREE -p)."`
不再笼统并列提及 RAxML-NG。

### 2. 帮助文档与 docstring 收窄口径（5 处）
统一为"明确支持 IQ-TREE 与 MrBayes"：
- 模块 docstring（:5-6）："a NEXUS-format partition file compatible with IQ-TREE (-p) and MrBayes"；
- "What does this tool do?"（:914）：去掉 RAxML-NG；
- Quick Start（:939-940）：改为 "or open them directly in MrBayes"；
- Output Files（:978）：改为 "Ready for IQ-TREE (-p) or MrBayes, depending on the selected partition format"；
- Next Steps（:983-984）：去掉 RAxML-NG。

### 3. 测试（`tests/test_partition_concat_tab.py`）
新增两个单元测试，直接构造 `_ConcatPartitionWorker`（`iqtree` / `mrbayes` 各一），连接 `finished` 信号捕获完成摘要：
- iqtree 模式：摘要含 "Ready for IQ-TREE"、不含 "Ready for IQ-TREE, MrBayes, or RAxML-NG"；
- mrbayes 模式：摘要含 "Ready for MrBayes"。

### 4. 验证
`py -m pytest tests/test_partition_concat_tab.py -q` → 全量 `py -m pytest -q` → `ruff check`（改动文件无新增问题）。