from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from deerflow.config.paths import VIRTUAL_PATH_PREFIX, get_paths


SERVER_NAME = "formatter-paper"
SERVER_VERSION = "0.2.0"


def _log_debug(message: str, **fields: Any) -> None:
    payload = {"message": message, **fields}
    sys.stderr.write(f"[formatter-paper-mcp] {json.dumps(payload, ensure_ascii=False)}\n")
    sys.stderr.flush()


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


def _resolve_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def _iter_thread_ids() -> list[str]:
    threads_dir = get_paths().base_dir / "threads"
    if not threads_dir.exists():
        return []
    return sorted(
        [entry.name for entry in threads_dir.iterdir() if entry.is_dir()],
        key=lambda thread_id: (threads_dir / thread_id).stat().st_mtime,
        reverse=True,
    )


def _resolve_virtual_path_for_thread(raw_path: str, thread_id: str) -> Path:
    return get_paths().resolve_virtual_path(thread_id, raw_path)


def _locate_virtual_input_path(raw_path: str) -> tuple[Path, str | None]:
    if not raw_path.startswith(VIRTUAL_PATH_PREFIX):
        resolved = _resolve_path(raw_path)
        return resolved, None

    candidates: list[tuple[Path, str]] = []
    for thread_id in _iter_thread_ids():
        candidate = _resolve_virtual_path_for_thread(raw_path, thread_id)
        if candidate.exists():
            candidates.append((candidate, thread_id))

    if not candidates:
        resolved = _resolve_path(raw_path)
        return resolved, None

    chosen_path, chosen_thread_id = candidates[0]
    if len(candidates) > 1:
        _log_debug(
            "virtual_input_ambiguous",
            raw_path=raw_path,
            chosen_thread_id=chosen_thread_id,
            candidate_thread_ids=[thread_id for _, thread_id in candidates[:10]],
        )
    else:
        _log_debug("virtual_input_resolved", raw_path=raw_path, thread_id=chosen_thread_id, resolved_path=str(chosen_path))
    return chosen_path, chosen_thread_id


def _resolve_output_like_path(raw_path: str, thread_id: str | None) -> Path:
    if not raw_path.startswith(VIRTUAL_PATH_PREFIX):
        return _resolve_path(raw_path)

    if thread_id is not None:
        resolved = _resolve_virtual_path_for_thread(raw_path, thread_id)
        _log_debug("virtual_output_resolved", raw_path=raw_path, thread_id=thread_id, resolved_path=str(resolved))
        return resolved

    thread_ids = _iter_thread_ids()
    if thread_ids:
        resolved = _resolve_virtual_path_for_thread(raw_path, thread_ids[0])
        _log_debug(
            "virtual_output_fallback_thread",
            raw_path=raw_path,
            thread_id=thread_ids[0],
            resolved_path=str(resolved),
        )
        return resolved

    return _resolve_path(raw_path)


def _ensure_pythonnet_available(python_executable: str, formatter_root: Path) -> tuple[bool, str]:
    probe = subprocess.run(
        [python_executable, "-c", "import pythonnet"],
        cwd=str(formatter_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if probe.returncode == 0:
        return True, "pythonnet already available"
    reason = (probe.stderr or probe.stdout or "pythonnet import failed").strip()[:500]
    return (
        False,
        "pythonnet is missing from the backend runtime. Rebuild the backend image or refresh the "
        f"backend .venv volume used by {python_executable}. Details: {reason}",
    )


def _run_format_paper(arguments: dict[str, Any]) -> dict[str, Any]:
    return _run_convert_command("pipeline", arguments)


def _run_pagination_repair(arguments: dict[str, Any]) -> dict[str, Any]:
    return _run_convert_command("pagination-repair", arguments)


def _run_convert_command(subcommand: str, arguments: dict[str, Any]) -> dict[str, Any]:
    formatter_root = _formatter_root()
    convert_script = _convert_script()
    _log_debug(
        "run_convert_command_start",
        subcommand=subcommand,
        formatter_root=str(formatter_root),
        convert_script=str(convert_script),
    )

    if not formatter_root.exists() or not convert_script.exists():
        _log_debug(
            "formatter_root_missing",
            formatter_root=str(formatter_root),
            convert_script=str(convert_script),
        )
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

    source_path, source_thread_id = _locate_virtual_input_path(arguments["source_docx_path"])
    template_path, template_thread_id = _locate_virtual_input_path(arguments["template_docx_path"])
    resolved_thread_id = source_thread_id or template_thread_id
    if source_thread_id and template_thread_id and source_thread_id != template_thread_id:
        _log_debug(
            "virtual_input_thread_mismatch",
            source_thread_id=source_thread_id,
            template_thread_id=template_thread_id,
            source_path=str(source_path),
            template_path=str(template_path),
        )
    output_path = _resolve_output_like_path(arguments["output_docx_path"], resolved_thread_id)
    python_executable = arguments.get("python_executable") or sys.executable
    report_json_path = arguments.get("report_json_path")
    report_path = _resolve_output_like_path(report_json_path, resolved_thread_id) if report_json_path else None
    max_iterations = arguments.get("max_iterations")

    pythonnet_ready, pythonnet_message = _ensure_pythonnet_available(python_executable, formatter_root)
    if not pythonnet_ready:
        _log_debug("pythonnet_unavailable", python_executable=python_executable, reason=pythonnet_message)
        return {
            "isError": True,
            "content": [{"type": "text", "text": pythonnet_message}],
            "structuredContent": {"success": False, "reason": pythonnet_message, "python_executable": python_executable},
        }

    missing = [str(path) for path in (source_path, template_path) if not path.exists()]
    if missing:
        _log_debug("input_missing", missing_inputs=missing, subcommand=subcommand)
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"Input file not found: {', '.join(missing)}"}],
            "structuredContent": {"success": False, "missing_inputs": missing},
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        python_executable,
        str(convert_script),
        subcommand,
        str(source_path),
        str(template_path),
        str(output_path),
    ]
    if report_path is not None:
        command.extend(["--report-json-path", str(report_path)])
    if max_iterations is not None and subcommand == "pagination-repair":
        command.extend(["--max-iterations", str(int(max_iterations))])

    completed = subprocess.run(
        command,
        cwd=str(formatter_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    _log_debug(
        "run_convert_command_complete",
        subcommand=subcommand,
        returncode=completed.returncode,
        stdout=(completed.stdout or "").strip()[:500],
        stderr=(completed.stderr or "").strip()[:500],
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
        "report_json_path": str(report_path) if report_path is not None else None,
        "returncode": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }

    return {
        "isError": not success,
        "content": [{"type": "text", "text": json.dumps(structured, ensure_ascii=False, indent=2)}],
        "structuredContent": structured,
    }


app = FastMCP(name=SERVER_NAME)


@app.tool(name="format_paper", description="Format a thesis or paper DOCX using a template DOCX via the local formatter_paper pipeline.")
def format_paper(
    source_docx_path: str,
    template_docx_path: str,
    output_docx_path: str,
    python_executable: str | None = None,
) -> dict[str, Any]:
    _log_debug("tool_invoked", tool_name="format_paper")
    result = _run_format_paper(
        {
            "source_docx_path": source_docx_path,
            "template_docx_path": template_docx_path,
            "output_docx_path": output_docx_path,
            "python_executable": python_executable,
        }
    )
    _log_debug("tool_complete", tool_name="format_paper", is_error=result.get("isError", False))
    return result


@app.tool(
    name="repair_paper_pagination",
    description="Run the formatter_paper pipeline and then apply iterative pagination repair for headings and captions.",
)
def repair_paper_pagination(
    source_docx_path: str,
    template_docx_path: str,
    output_docx_path: str,
    report_json_path: str | None = None,
    max_iterations: int | None = None,
    python_executable: str | None = None,
) -> dict[str, Any]:
    _log_debug("tool_invoked", tool_name="repair_paper_pagination")
    result = _run_pagination_repair(
        {
            "source_docx_path": source_docx_path,
            "template_docx_path": template_docx_path,
            "output_docx_path": output_docx_path,
            "report_json_path": report_json_path,
            "max_iterations": max_iterations,
            "python_executable": python_executable,
        }
    )
    _log_debug("tool_complete", tool_name="repair_paper_pagination", is_error=result.get("isError", False))
    return result


def main() -> int:
    _log_debug(
        "server_start",
        server_name=SERVER_NAME,
        server_version=SERVER_VERSION,
        formatter_root=str(_formatter_root()),
        python_executable=sys.executable,
        cwd=os.getcwd(),
    )
    try:
        app.run(transport="stdio")
    except KeyboardInterrupt:
        _log_debug("server_keyboard_interrupt")
    except EOFError:
        _log_debug("server_eof")
    except Exception as exc:  # pragma: no cover
        _log_debug("server_exception", error=str(exc))
        raise
    finally:
        _log_debug("server_stop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
