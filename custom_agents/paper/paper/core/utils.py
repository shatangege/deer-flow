from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


_SPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)


def normalize_title(value: str) -> str:
    text = _SPACE_RE.sub(" ", (value or "").strip())
    text = _NON_WORD_RE.sub("", text.lower())
    return text


def ensure_parent_dir(path: str | os.PathLike[str]) -> Path:
    resolved = Path(path).expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def write_json(path: str | os.PathLike[str], payload: Any) -> str:
    output = ensure_parent_dir(path)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(output)


def read_json(path: str | os.PathLike[str]) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))
