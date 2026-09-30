from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import json
from pathlib import Path
import sys

from app.persistence.json_store import JsonStore


class _StreamToLogger:
    def __init__(self, logger: logging.Logger, level: int):
        self.logger = logger
        self.level = level
        self.pending = ""
        self.encoding = "utf-8"

    def write(self, text):
        self.pending += str(text)
        while "\n" in self.pending:
            line, self.pending = self.pending.split("\n", 1)
            if line:
                self.logger.log(self.level, line.rstrip())
        return len(text)

    def flush(self):
        if self.pending:
            self.logger.log(self.level, self.pending.rstrip())
            self.pending = ""

    def isatty(self):
        return False


def _rotating_handler(path: Path, *, level=logging.INFO):
    handler = RotatingFileHandler(path, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    return handler


def configure_logging(log_dir: Path) -> None:
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    target = str(log_dir / "bot.log").casefold()
    if not any(getattr(handler, "baseFilename", "").casefold() == target for handler in root.handlers):
        root.addHandler(_rotating_handler(log_dir / "bot.log"))
    if not isinstance(sys.stdout, _StreamToLogger):
        sys.stdout = _StreamToLogger(logging.getLogger("stdout"), logging.INFO)
    if not isinstance(sys.stderr, _StreamToLogger):
        sys.stderr = _StreamToLogger(logging.getLogger("stderr"), logging.ERROR)


def configure_nvidia_error_logging(log_dir: Path) -> None:
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("app.nvidia.errors")
    logger.setLevel(logging.ERROR)
    target = str(log_dir / "nvidia_errors.log").casefold()
    for handler in list(logger.handlers):
        current = getattr(handler, "baseFilename", "").casefold()
        if current and current != target:
            logger.removeHandler(handler)
            handler.close()
    if not any(getattr(handler, "baseFilename", "").casefold() == target for handler in logger.handlers):
        logger.addHandler(_rotating_handler(log_dir / "nvidia_errors.log", level=logging.ERROR))


def migrate_json_log(source: Path, destination: Path, default) -> None:
    """Move a legacy root-level log to logs/, preserving any newer entries."""
    source, destination = Path(source), Path(destination)
    if not source.exists():
        return
    try:
        old_data = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(old_data, type(default)):
            raise ValueError("formato JSON inesperado")
        new_store = JsonStore(destination)
        if destination.exists():
            new_data = new_store.load(default)
            if isinstance(old_data, list):
                old_data.extend(new_data)
            else:
                merged = dict(old_data)
                merged.update(new_data)
                merged["__ai_logs__"] = old_data.get("__ai_logs__", []) + new_data.get("__ai_logs__", [])
                old_data = merged
        new_store.save(old_data)
        source.unlink()
    except (OSError, ValueError, TypeError) as error:
        logging.getLogger(__name__).exception("Nao foi possivel migrar o log %s: %s", source, error)
