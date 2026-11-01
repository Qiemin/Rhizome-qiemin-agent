from dataclasses import dataclass


@dataclass(frozen=True)
class CommandResult:
    command: str
    cwd: str
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    truncated: bool = False
    
     