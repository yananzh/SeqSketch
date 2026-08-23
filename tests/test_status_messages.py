"""Keep tab status-bar messages concise.

Rules enforced over every ``show_status(...)`` / ``status_label.setText(...)``
/ ``_set_status(...)`` literal in ``modules/``:

- no trailing period (ellipsis ``...`` is fine) and no trailing whitespace
- no CJK characters (the UI language is English)
- static text (placeholders removed) stays within ``MAX_STATIC`` characters
"""

import ast
import glob
import os
import re

MAX_STATIC = 48
_CJK = re.compile(r"[\u4e00-\u9fff]")
_PLACEHOLDER = re.compile(r"\{[^{}]*\}")

STATUS_FUNCS = {"show_status", "setText", "_set_status"}


def _status_call_arg(node: ast.Call):
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr in STATUS_FUNCS:
        if func.attr == "setText" and not (
            isinstance(func.value, ast.Name) and func.value.id == "status_label"
        ):
            return None
        if not node.args:
            return None
        arg = node.args[0]
        if isinstance(arg, ast.Call) and arg.args:  # tolerate tr("...") wrappers
            arg = arg.args[0]
        return arg
    return None


def _literal_texts(arg):
    """Return (full_text, tail_text) for a Constant or JoinedStr argument.

    ``tail_text`` contains only the fragments after the last formatted
    placeholder — trailing punctuation/whitespace rules apply to it.
    """
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value, arg.value
    if isinstance(arg, ast.JoinedStr):
        full_parts: list[str] = []
        tail_parts: list[str] = []
        for value in arg.values:
            if isinstance(value, ast.FormattedValue):
                tail_parts = []
            elif isinstance(value, ast.Constant) and isinstance(value.value, str):
                full_parts.append(value.value)
                tail_parts.append(value.value)
        return "".join(full_parts), "".join(tail_parts)
    return "", ""


def test_status_messages_are_concise():
    offenders = []
    files = sorted(glob.glob(os.path.join("modules", "*.py")))
    assert files
    for path in files:
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            arg = _status_call_arg(node)
            if arg is None:
                continue
            full, tail = _literal_texts(arg)
            if not full:
                continue
            where = (os.path.basename(path), node.lineno, full)
            if tail != tail.rstrip():
                offenders.append(("trailing whitespace",) + where)
            stripped = tail.rstrip()
            if stripped.endswith(".") and not stripped.endswith(".."):
                offenders.append(("trailing period",) + where)
            if _CJK.search(full):
                offenders.append(("CJK character",) + where)
            static = _PLACEHOLDER.sub("", full)
            if len(static.rstrip()) > MAX_STATIC:
                offenders.append((f"static text > {MAX_STATIC} chars",) + where)
    assert not offenders, "\n".join(f"{reason}: {f}:{line} {text!r}" for reason, f, line, text in offenders)
