"""Centralized logging for the Remirdy Blender Studio MCP server."""
from __future__ import annotations

import logging
import os
import sys

_LEVEL = os.environ.get("REMIRDY_LOG_LEVEL", "INFO").upper()


def get_logger(name: str = "remirdy") -> logging.Logger:
    """Return a configured logger that writes to stderr.

    stdout is reserved for the MCP stdio transport, so all log output must go
    to stderr to avoid corrupting the protocol stream.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    handler = logging.StreamHandler(sys.stderr)
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, _LEVEL, logging.INFO))
    logger.propagate = False
    return logger
