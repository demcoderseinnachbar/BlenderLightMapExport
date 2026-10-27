# SPDX-License-Identifier: MIT
"""Structured logging for console, log file and UI reports."""

from __future__ import annotations

import logging
import os
import sys
from typing import List, Optional, Tuple

LOGGER_NAME = "blme"
_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


class CollectHandler(logging.Handler):
    """Collects warnings and errors so the UI can show them after a run."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.records: List[Tuple[str, str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append((record.levelname, self.format(record)))

    def clear(self) -> None:
        self.records.clear()


def get_logger(name: str = "") -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME + ("." + name if name else ""))
    root = logging.getLogger(LOGGER_NAME)
    if not getattr(root, "_blme_initialised", False):
        root.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_FORMAT, datefmt="%H:%M:%S"))
        handler.set_name("blme_console")
        root.addHandler(handler)
        root.propagate = False
        root._blme_initialised = True  # type: ignore[attr-defined]
    return logger


def set_level(level: str) -> None:
    logging.getLogger(LOGGER_NAME).setLevel(getattr(logging, level.upper(), logging.INFO))


def add_file_handler(path: str) -> logging.Handler:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter(_FORMAT))
    logging.getLogger(LOGGER_NAME).addHandler(handler)
    return handler


def remove_handler(handler: Optional[logging.Handler]) -> None:
    if handler is None:
        return
    root = logging.getLogger(LOGGER_NAME)
    root.removeHandler(handler)
    try:
        handler.close()
    except Exception:
        pass


def add_collector() -> CollectHandler:
    handler = CollectHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger(LOGGER_NAME).addHandler(handler)
    return handler
