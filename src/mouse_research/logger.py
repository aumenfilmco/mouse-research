"""Structured logging for mouse-research.

Log files: ~/.mouse-research/logs/YYYY-MM-DD.log
Failure log: ~/.mouse-research/logs/failures.jsonl
"""
import json
import logging
from datetime import date, datetime
from pathlib import Path

from rich.logging import RichHandler

LOG_DIR = Path.home() / ".mouse-research" / "logs"
FAILURE_LOG = LOG_DIR / "failures.jsonl"

_logging_configured = False


def setup_logging(verbose: bool = False) -> None:
    """Configure root logger with Rich terminal output and daily file handler.

    Call once at CLI entry (cli.py callback). Idempotent — safe to call multiple times.
    """
    global _logging_configured
    if _logging_configured:
        return
    _logging_configured = True

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"{date.today().isoformat()}.log"
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[
            RichHandler(rich_tracebacks=True, show_path=False),
            logging.FileHandler(str(log_file)),
        ],
    )


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Call setup_logging() first."""
    return logging.getLogger(name)


def log_failure(url: str, reason: str, phase: str) -> None:
    """Append a failed URL record to failures.jsonl for later retry.

    Record format: {"url": str, "reason": str, "phase": str, "timestamp": ISO-8601}
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "url": url,
        "reason": reason,
        "phase": phase,
        "timestamp": datetime.utcnow().isoformat(),
    }
    with open(str(FAILURE_LOG), "a") as f:
        f.write(json.dumps(record) + "\n")
