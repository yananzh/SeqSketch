"""Replace text output only after a complete successful write."""

import os
import tempfile
from pathlib import Path


def write_text_atomic(path, text, encoding="utf-8"):
    target = Path(path).absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding=encoding, dir=target.parent, delete=False
        ) as handle:
            temporary = handle.name
            handle.write(text)
        os.replace(temporary, target)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
