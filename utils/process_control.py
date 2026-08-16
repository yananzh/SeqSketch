"""Helpers for terminating external-tool subprocess trees on Windows.

Launchers such as mafft.bat spawn cmd.exe as the direct child, with the real
worker processes (mafft.exe etc.) below it. Killing only the direct child
orphans the grandchildren, which keep consuming CPU and hold temp files open.
taskkill /T /F takes down the whole tree; on POSIX, fall back to terminate().
"""

import logging
import subprocess

logger = logging.getLogger(__name__)


def kill_process_tree(proc: subprocess.Popen) -> None:
    """Kill *proc* and all of its descendants.

    Safe to call on an already-exited process (no-op).
    """
    if proc is None:
        return
    if proc.poll() is not None:
        return
    try:
        if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):  # Windows
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:  # POSIX
            proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        # Last resort — kill at least the direct child so run() can unwind.
        try:
            proc.kill()
        except OSError:
            pass
    logger.info("Killed process tree of PID %s", proc.pid)
