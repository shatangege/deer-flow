from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


SERVER_NAME = "formatter-paper"
SERVER_VERSION = "0.2.0"
PROTOCOL_VERSION = "2024-11-05"


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "formatter_paper" / "convert.py").exists():
            return parent
    return current.parents[5]


def _formatter_root() -> Path:
    if configured := os.getenv("FORMATTER_PAPER_ROOT"):
        return Path(configured).expanduser().resolve()
    return (_repo_root() / "formatter_paper").resolve()


def _convert_script() -> Path:
    return _formatter_root() / "convert.py"


def _write_message(payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


def _read_message() -> dict[str, Any] | None:
    headers: dict[str, str] = {}

    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        header = line.decode("utf-8").strip()
        if ":" not in header:
            continue
        key, value = header.split(":", 1)
        headers[key.strip().lower()] = value.strip()

    length_header = headers.get("content-length")
    if not length_header:
        return None

    body = sys.stdin.buffer.read(int(length_header))
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def _make_error(code: int, message: str, data: Any | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return error


def _tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "format_paper",
            "description": "Format a thesis or paper DOCX using a template DOCX via the local formatter_paper pipeline.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "source_docx_path": {
                        "type": "string",
                        "description": "Absolute or workspace-relative path to the source paper DOCX file.",
                    },
                    "template_docx_path": {
                        "type": "string",
                        "description": "Absolute or workspace-relative path to the template DOCX file.",
                    },
                    "output_docx_path": {
                        "type": "string",
                        "description": "Absolute or workspace-relative path where the formatted DOCX should be written.",
                    },
                    "python_executable": {
                        "type": "string",
                        "description": "Optional Python executable to use. Defaults to the current interpreter.",
                    },
                },
                "required": ["source_docx_path", "template_docx_path", "output_docx_path"],
                "additionalProperties": False,
            },
        }
    ]


def _resolve_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def _run_format_paper(arguments: dict[str, Any]) -> dict[str, Any]:
    formatter_root = _formatter_root()
    convert_script = _convert_script()

    if not formatter_root.exists() or not convert_script.exists():
        return {
            "isError": True,
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "success": False,
                            "reason": "formatter_paper package not found",
                            "formatter_root": str(formatter_root),
                            "expected_convert_script": str(convert_script),
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                }
            ],
            "structuredContent": {
                "success": False,
                "formatter_root": str(formatter_root),
                "expected_convert_script": str(convert_script),
            },
        }

    source_path = _resolve_path(arguments["source_docx_path"])
    template_path = _resolve_path(arguments["template_docx_path"])
    output_path = _resolve_path(arguments["output_docx_path"])
    python_executable = arguments.get("python_executable") or sys.executable

    missing = [str(path) for path in (source_path, template_path) if not path.exists()]
    if missing:
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"Input file not found: {', '.join(missing)}"}],
            "structuredContent": {"success": False, "missing_inputs": missing},
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        python_executable,
        str(convert_script),
        "pipeline",
        str(source_path),
        str(template_path),
        str(output_path),
    ]

    completed = subprocess.run(
        command,
        cwd=str(formatter_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    success = completed.returncode == 0 and output_path.exists()

    structured = {
        "success": success,
        "command": command,
        "formatter_root": str(formatter_root),
        "source_docx_path": str(source_path),
        "template_docx_path": str(template_path),
        "output_docx_path": str(output_path),
        "returncode": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }

    return {
        "isError": not success,
        "content": [{"type": "text", "text": json.dumps(structured, ensure_ascii=False, indent=2)}],
        "structuredContent": structured,
    }


def _handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")

    if method == "notifications/initialized":
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": _tool_definitions()}}

    if method == "tools/call":
        params = request.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name != "format_paper":
            return {"jsonrpc": "2.0", "id": request_id, "error": _make_error(-32601, f"Unknown tool: {tool_name}")}

        try:
            result = _run_format_paper(arguments)
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except KeyError as exc:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": _make_error(-32602, f"Missing required argument: {exc.args[0]}"),
            }
        except Exception as exc:  # pragma: no cover
            return {"jsonrpc": "2.0", "id": request_id, "error": _make_error(-32603, f"format_paper failed: {exc}")}

    return {"jsonrpc": "2.0", "id": request_id, "error": _make_error(-32601, f"Method not found: {method}")}


def main() -> int:
    while True:
        request = _read_message()
        if request is None:
            return 0
        response = _handle_request(request)
        if response is not None:
            _write_message(response)


if __name__ == "__main__":
    raise SystemExit(main())

