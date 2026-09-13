from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .brief import ResearchBrief


@dataclass(frozen=True)
class AgentRunResult:
    status: str
    command: list[str]
    runtime_seconds: float
    stdout_path: str
    return_code: int | None
    error: str | None = None


class AgentGateway:
    """Runs a user-selected provider without shell expansion or hidden state."""

    def __init__(self, timeout_seconds: int = 300):
        self.timeout_seconds = timeout_seconds

    def run(self, command: str | Sequence[str], *, brief: ResearchBrief, parent: Path,
            candidate: Path, run_dir: Path) -> AgentRunResult:
        argv = shlex.split(command) if isinstance(command, str) else list(command)
        if not argv or not any("{candidate}" in token for token in argv) or not any("{brief}" in token for token in argv):
            raise ValueError("gateway command must contain {candidate} and {brief} placeholders")
        argv = [token.replace("{candidate}", str(candidate)).replace("{brief}", str(run_dir / "brief.json")) for token in argv]
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "brief.json").write_text(json.dumps(brief.to_dict(), ensure_ascii=False, indent=2))
        stdout_path = run_dir / "agent.log"
        started = time.monotonic()
        process = None
        try:
            with stdout_path.open("w") as output:
                process = subprocess.Popen(argv, cwd=run_dir, stdout=output, stderr=subprocess.STDOUT,
                                           start_new_session=True, env=dict(os.environ, PYTHONHASHSEED="42"))
                try:
                    return_code = process.wait(timeout=self.timeout_seconds)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    return AgentRunResult("timeout", argv, time.monotonic() - started, str(stdout_path), None, "agent timeout")
                except BaseException:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    raise
        except OSError as exc:
            return AgentRunResult("crash", argv, time.monotonic() - started, str(stdout_path), None, str(exc))
        return AgentRunResult("success" if return_code == 0 else "crash", argv,
                              time.monotonic() - started, str(stdout_path), return_code,
                              None if return_code == 0 else f"provider exit {return_code}")
