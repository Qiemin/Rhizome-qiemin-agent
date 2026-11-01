"""Local Windows execution. A Job is NOT filesystem/network security isolation."""

import math
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID

from ..workspace.workspace import Workspace
from .models import CommandResult
from .output import OutputBuffer, read_stream

# The trusted worker waits for G. The parent assigns it to a Job before opening
# that gate, so the task payload cannot spawn before being managed.
_WORKER = r"""
import os, pathlib, subprocess, sys, venv
if sys.stdin.buffer.read(1) != b'G':
    raise SystemExit(125)
sys.stdin.close()
runtime = pathlib.Path(sys.argv[1])
python = runtime / 'Scripts' / 'python.exe'
ready = runtime / '.rhizome-ready'
if not python.is_file() or not ready.is_file():
    print('Preparing workspace Python environment...', file=sys.stderr, flush=True)
    venv.EnvBuilder(with_pip=True).create(runtime)
    ready.write_text('ready', encoding='ascii')
environment = os.environ.copy()
environment['VIRTUAL_ENV'] = str(runtime)
environment['PATH'] = str(runtime / 'Scripts') + os.pathsep + environment.get('PATH', '')
environment['PYTHONIOENCODING'] = 'utf-8'
environment['PYTHONUTF8'] = '1'
completed = subprocess.run(sys.argv[2:], stdin=subprocess.DEVNULL, env=environment)
raise SystemExit(completed.returncode)
"""


def _process_environment() -> dict[str, str]:
    allowed = {
        "SYSTEMROOT", "WINDIR", "COMSPEC", "SYSTEMDRIVE", "TEMP", "TMP",
        "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PATHEXT", "PATH",
    }
    environment = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUTF8"] = "1"
    return environment


def execute_command(command: str, workspace: Workspace, *, timeout: float = 60,
                    runtime_root: Path | None = None) -> CommandResult:
    if sys.platform != "win32":
        raise ValueError("当前终端执行器只支持 Windows")
    if workspace.execution_mode != "local" or not workspace.writable:
        raise PermissionError("工作区未明确启用本地终端执行")
    if not command.strip() or len(command) > 8000 or "\0" in command:
        raise ValueError("命令不能为空、包含空字符或超过 8000 个字符")
    if not math.isfinite(timeout) or not 0 < timeout <= 120:
        raise ValueError("执行超时必须大于 0 且不超过 120 秒")
    try:
        workspace_id = str(UUID(workspace.workspace_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("终端执行需要一个已登记的工作区 ID") from exc
    try:
        from .windows_job import WindowsJob
    except ImportError as exc:
        raise RuntimeError("请先安装 pywin32==312") from exc

    if runtime_root is None:
        runtime_root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Rhizome" / "runtimes"
    runtime_root = Path(runtime_root).resolve()
    runtime = (runtime_root / workspace_id).resolve()
    if not runtime.is_relative_to(runtime_root):
        raise PermissionError("Python 运行环境路径无效")
    shell = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    base_python = str(Path(getattr(sys, "_base_executable", sys.executable)).resolve())
    script = (
        "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
        "$OutputEncoding = [Console]::OutputEncoding; " + command
    )
    stdout_buffer, stderr_buffer = OutputBuffer(), OutputBuffer()
    timed_out = False

    job = WindowsJob()
    try:
        with subprocess.Popen(
            [base_python, "-I", "-S", "-c", _WORKER, str(runtime), str(shell),
             "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
            cwd=workspace.root, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=_process_environment(), creationflags=subprocess.CREATE_NO_WINDOW,
        ) as process:
            try:
                # CPython/Windows keeps the original native handle.
                handle = getattr(process, "_handle", None)
                if handle is None:
                    raise RuntimeError("当前 Python 不支持 Windows 进程句柄管理")
                job.add_process(int(handle))
                assert process.stdin is not None
                assert process.stdout is not None
                assert process.stderr is not None
                with ThreadPoolExecutor(max_workers=2) as readers:
                    stdout_task = readers.submit(read_stream, process.stdout, stdout_buffer)
                    stderr_task = readers.submit(read_stream, process.stderr, stderr_buffer)
                    try:
                        process.stdin.write(b"G")
                        process.stdin.flush()
                        process.stdin.close()
                        exit_code = process.wait(timeout=timeout)
                    except subprocess.TimeoutExpired:
                        timed_out = True
                        job.terminate()
                        exit_code = process.wait()
                    except BaseException:
                        job.close()
                        if process.poll() is None:
                            process.kill()
                        process.wait()
                        raise
                    finally:
                        # Remove ordinary background descendants before
                        # waiting for pipe EOF, even on a normal exit.
                        job.close()
                    stdout_task.result()
                    stderr_task.result()
            except BaseException:
                job.close()
                if process.poll() is None:
                    process.kill()
                process.wait()
                raise
    finally:
        job.close()

    return CommandResult(
        command=command, cwd=str(workspace.root), exit_code=exit_code,
        stdout=stdout_buffer.text, stderr=stderr_buffer.text, timed_out=timed_out,
        truncated=stdout_buffer.truncated or stderr_buffer.truncated,
    )
