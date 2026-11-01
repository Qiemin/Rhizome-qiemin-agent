"""Optional Windows process checks; only owned temporary files, no .env/DB/LLM."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.execution.runner import execute_command
from agent.tools.terminal import build_terminal_tool
from agent.workspace.workspace import open_workspace


def assert_exited(pid):
    import pywintypes
    import win32api
    import win32con
    import win32process
    try:
        handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, pid)
    except pywintypes.error as exc:
        assert exc.winerror == 87, exc
    else:
        try:
            assert win32process.GetExitCodeProcess(handle) != 259, 'owned child is still active'
        finally:
            handle.Close()


def main():
    if sys.platform != "win32":
        raise SystemExit("Windows only")
    owned_root = (ROOT / ".test-artifacts").resolve()
    owned_root.relative_to(ROOT.resolve())
    owned_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="terminal-", dir=owned_root) as temporary:
        root = Path(temporary).resolve()
        root.relative_to(owned_root)  # verify the recursive-cleanup target
        files = root / "files"
        files.mkdir()
        workspace_id = str(uuid4())
        workspace = open_workspace(files, writable=True, workspace_id=workspace_id, execution_mode="local")
        options = {"runtime_root": root / "runtimes"}

        result = execute_command(
            'python -c "import sys,pathlib; print(sys.prefix); pathlib.Path(\'marker.txt\').write_text(\'persist\')"',
            workspace, **options,
        )
        assert result.exit_code == 0, result.stderr
        assert str(root / "runtimes" / workspace_id).casefold() in result.stdout.casefold(), result.stdout
        print("PASS: dedicated workspace Python environment and real file creation", flush=True)

        restored = open_workspace(files, writable=True, workspace_id=workspace_id, execution_mode="local")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "offline-must-not-inherit"}):
            result = execute_command("Get-Content .\\marker.txt; Write-Output '中文'; Write-Output $env:OPENAI_API_KEY", restored, **options)
        assert result.exit_code == 0, result.stderr
        assert "persist" in result.stdout and "中文" in result.stdout, repr(result.stdout)
        assert "offline-must-not-inherit" not in result.stdout + result.stderr
        print("PASS: restoration across commands, UTF-8, and filtered environment", flush=True)

        terminal = build_terminal_tool(lambda command, context: execute_command(command, context, **options))
        invoked = terminal.invoke(
            {"command": "Write-Output 'tool ready'"},
            config={"configurable": {"workspace": restored}},
        )
        assert invoked['exit_code'] == 0 and 'tool ready' in invoked['stdout'], invoked
        print("PASS: actual @tool invocation reaches the managed terminal", flush=True)

        result = execute_command("Write-Output ('A' * 70000)", restored, **options)
        assert result.truncated and len(result.stdout.encode("utf-8")) == 64 * 1024
        print("PASS: bounded output during execution", flush=True)

        result = execute_command("exit 7", restored, **options)
        assert result.exit_code == 7, result
        print("PASS: exit-code propagation", flush=True)

        (files / 'spawn_background.py').write_text(
            "import pathlib,subprocess,sys\n"
            "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],"
            "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
            "pathlib.Path('background.pid').write_text(str(child.pid),encoding='ascii')\n",
            encoding='utf-8',
        )
        result = execute_command('python .\\spawn_background.py', restored, **options)
        assert result.exit_code == 0, result.stderr
        assert_exited(int((files / 'background.pid').read_text(encoding='ascii')))
        print('PASS: normal command exit cleans up owned background children', flush=True)

        spawn = files / "spawn_child.py"
        spawn.write_text(
            "import pathlib,subprocess,sys,time\n"
            "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])\n"
            "pathlib.Path('child.pid').write_text(str(child.pid),encoding='ascii')\n"
            "time.sleep(60)\n", encoding="utf-8",
        )
        result = execute_command("python .\\spawn_child.py", restored, timeout=4, **options)
        assert result.timed_out
        pid_file = files / "child.pid"
        assert pid_file.is_file(), "test payload did not start within timeout"
        pid = int(pid_file.read_text(encoding="ascii"))
        assert_exited(pid)
        print("PASS: timeout terminates the managed parent and owned child", flush=True)
    print("Local process checks passed. No real .env, database or model was used.", flush=True)


if __name__ == "__main__":
    main()
