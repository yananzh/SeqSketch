# UI language packs

SeqSketch keeps its source strings in English and translates the UI at runtime,
so English stays the single source of truth and no `tr(...)` wrappers are needed
around static widget text.

- `utils/i18n.py` owns loading, matching and widget translation.
- `resources/i18n/<language>/` holds one or more JSON packs per language.
- `resources/i18n/<language>/help/` holds translated help-dialog bodies.
- The language is stored in `Settings` as `ui.language` (`en` or `zh-CN`) and is
  selected from **Settings → Language**. A restart applies the change.

## Pack format

Each `*.json` file is a flat object mapping the **exact English source string**
to the target-language string:

```json
{
  "Input FASTA file:": "输入 FASTA 文件：",
  "Loaded {count} sequences": "已载入 {count} 条序列"
}
```

Packs are merged per language. The same source key may appear in two packs only
if the translations are identical; `LanguagePack.problems` reports conflicts.
`utils/i18n.py` also exposes `language_pack(code).problems`, which must stay
empty (tests enforce this).

### Exact keys versus patterns

- A key without `{placeholders}` is an exact match.
- A key with `{name}` placeholders becomes a pattern. At runtime the placeholder
  captures one or more characters and is substituted back into the translation.
  Keep the placeholder names identical in key and value.
- Patterns are tried longest-literal-first, so a specific template wins over a
  generic one.
- Do not add keys whose translation is identical to the English source (product
  names, file names, code tokens). Leaving them out is what makes coverage
  reporting accurate.

## How translation is applied

`install_ui_translator(app)` installs an application event filter. When a widget
is shown while a non-English language is active, `translate_widget()` rewrites:

- window titles, tooltips, `QLabel` / button text, group-box titles,
  placeholders, spin-box special-value text, tab titles, table header labels,
  message-box text, and menus.

Charts are a special case: matplotlib's default font has no CJK glyphs, so
`activate_saved_language()` switches `font.sans-serif` to an installed system CJK
family (Microsoft YaHei, SimHei, PingFang SC, Noto Sans CJK SC, …) when a Chinese
language is active.

This covers static text built in a constructor. Text that changes **after** the
widget is already visible is not covered, so those call sites translate
explicitly:

```python
from utils.i18n import tr_format, tr_ui

self._set_status(tr_ui("Analyzing..."))
self._set_status(tr_format("Loaded: {path}", path=path))
```

`tr_format(template, **values)` translates the template first, then calls
`.format(**values)`; the English output must stay byte-identical. Do not use
`tr_format` on strings containing literal braces that are not placeholders.

### Rules of thumb

- **Static constructor text** (labels, buttons, group titles, placeholders,
  tooltips, dialog titles): add a pack key only, no code change.
- **Late-bound text** (status labels, log lines, table/tree cells, dynamically
  built labels): wrap with `tr_ui` / `tr_format`.
- **Do not translate** file names, extensions, paths, internal keys, dict keys,
  enum values, command-line arguments, or data written to output files.
- **Do not translate** the body argument of `show_help_dialog(...)`; help pages
  are handled separately (see below).
- **Combo-box items are data.** Translating them would break code that compares
  `currentText()`. Their surrounding labels and tooltips are translated.
- Never write CJK characters into Python source; all translated text lives in
  packs.

## Style guide (zh-CN)

- Use full-width punctuation in Chinese prose: `：，。；（）` and `“”`.
  Keep `%`, `°C`, `bp`, `kb`, `nt`, `aa` and numerals as-is.
- Put a space between Chinese and Latin letters/numbers: `已载入 3 条序列`,
  `比对与 BLAST`。
- Keep product, tool and file-format names untranslated: `BLAST`, `MAFFT`,
  `MUSCLE`, `IQ-TREE`, `trimAl`, `Sanger`, `FASTA`, `DNA`, `RNA`, `CSV`,
  `Excel`, `JSON`, `HTML`, `Tm`, `GC`, `E-value`.
- Keep `{placeholder}` names, newlines, leading/trailing spaces and em dashes
  (`—`) intact.
- Match the wording already used by the existing packs; do not invent a second
  translation for a term that is already translated.

### Glossary

| English | 中文 |
| --- | --- |
| alignment | 比对 |
| multiple sequence alignment (MSA) | 多序列比对 |
| pairwise alignment | 双序列比对 |
| sequence | 序列 |
| record | 记录 |
| input / output | 输入 / 输出 |
| file / folder / directory | 文件 / 文件夹 / 目录 |
| run | 运行 |
| example | 示例 |
| browse | 浏览 |
| clear | 清空 |
| preview | 预览 |
| stop | 停止 |
| export / import | 导出 / 导入 |
| error / warning | 错误 / 警告 |
| database | 数据库 |
| query / subject | 查询序列 / 目标序列 |
| primer / primer pair | 引物 / 引物对 |
| template | 模板 |
| melting temperature (Tm) | 解链温度（Tm） |
| phylogenetic tree | 系统发育树 |
| tree visualization | 系统树可视化 |
| distance tree | 距离树 |
| maximum likelihood (ML) | 最大似然 |
| bootstrap | 自举 |
| model | 模型 |
| substitution model | 替换模型 |
| alignment trimming | 比对修剪 |
| gap | 空位 |
| consensus | 共有序列 |
| identity | 一致性 |
| coverage | 覆盖度 |
| strand | 链 |
| feature / annotation | 特征 / 注释 |
| chromatogram | 色谱图 |
| sequence assembly | 序列拼接 |
| base call | 碱基判定 |
| quality score | 质量值 |
| bookmark | 书签 |
| category | 分类 |
| threshold | 阈值 |
| parameter / option / value | 参数 / 选项 / 值 |
| score / length | 得分 / 长度 |
| result | 结果 |
| completed | 已完成 |
| processing / loading | 处理中 / 正在载入 |
| failed | 失败 |
| not found | 未找到 |

## Help pages

Help dialogs are localized without touching the English HTML:

- The dialog title is translated through the pack (`"Help - Rename IDs"`).
- `_localize_help_body()` derives a file name from the **English** window title:
  `help_slug("Help - Rename IDs")` → `help_rename_ids.html`.
- Put the translated body at
  `resources/i18n/zh-CN/help/help_<slug>.html`.
- The body starts with `<h2>标题 &mdash; 一句话说明</h2>`, keeps the section
  structure (`本工具有什么用？`, `快速入门`, reference tables, `使用技巧`) and
  uses the same HTML tags as the source. Inline code and button names follow the
  UI translation (`<b>运行</b>`).

## Verifying

```powershell
# List UI literals without a translation (per file summary)
$env:PYTHONIOENCODING='utf-8'; py scripts/extract_ui_strings.py --summary

# Inspect one file
py scripts/extract_ui_strings.py modules/example_tab.py

# Catch malformed packs / placeholder mismatches
py -c "from utils.i18n import language_pack; print(language_pack('zh-CN').problems)"

# No CJK in Python source, no trailing periods in status messages
py -m pytest tests/test_status_messages.py -q
```

The extractor understands common UI calls (`setText`, `setWindowTitle`,
`addTab`, `show_status`, `QMessageBox.*`, …). It reports f-string templates as
`[dynamic]`; those need `tr_format` (or a `{placeholder}` pattern key) to be
translated at runtime. Some reported literals are not UI text (dict keys, file
names, help bodies); leave those alone.
