"""Manually invoke the tool using a workspace registration from PostgreSQL."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.config import load_database_url
from agent.execution.runner import execute_command
from agent.storage.workspaces import restore_workspace
from agent.tools.terminal import build_terminal_tool


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--command", default="Write-Output 'terminal ready'")
    args = parser.parse_args()
    workspace = restore_workspace(load_database_url(), args.workspace_id)
    terminal = build_terminal_tool(execute_command)
    result = terminal.invoke(
        {"command": args.command}, config={"configurable": {"workspace": workspace}},
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
