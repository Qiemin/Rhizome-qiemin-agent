from ..execution.runner import execute_command
from .terminal import build_terminal_tool

# The tool manages workspace exclusion and permission refresh before execution.
TOOLS = [build_terminal_tool(execute_command)]
