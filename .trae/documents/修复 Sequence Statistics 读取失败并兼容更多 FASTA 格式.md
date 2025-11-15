# 问题诊断
- 现象：Sequence Statistics 无法处理输入文件，可能是文件扩展名不在允许范围或编码不是 UTF-8 导致读取失败。
- 代码位置：`modules/sequence_statistics_tab.py` 使用 `validate_input_path` 严格限制扩展名；`modules/fasta_processor.py` 仅以 UTF-8 打开文件。

# 修复方案
- 扩展支持的扩展名并更新文件选择过滤器：加入 `*.fna, *.ffn, *.faa, *.frn, *.txt`。
- 增加编码回退：读取 FASTA 时在 UTF-8 失败时回退至 `latin-1`（或 cp1252），确保尽量成功解析。
- 保持功能与输出格式不变。

# 具体改动
- `modules/sequence_statistics_tab.py`：
  - `select_input_file` 的过滤器改为支持更多后缀。
  - `run_statistics` 的校验调用使用扩展列表。
- `modules/fasta_processor.py`：
  - `read_file` 在 UTF-8 失败时尝试用 `latin-1` 重试。

# 验证
- 用 `.fna/.faa/.txt` 的 FASTA 文件测试能通过校验并生成 TSV 输出；界面统计数值正常显示。

# 风险与回滚
- 仅扩展容错，不改变统计逻辑；如需更细致编码检测，可后续引入 `chardet`。