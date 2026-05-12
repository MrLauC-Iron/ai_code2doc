from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(level: str = "INFO") -> None:
    """Configure structlog with rich console output.

    This sets up:
    - Standard library ``logging`` at the given *level* for the
      ``ai_code2doc`` namespace.
    - structlog processors that produce coloured, human-readable output
      when attached to a TTY, and JSON otherwise.

    Parameters
    ----------
    level:
        The log level string (e.g. ``"DEBUG"``, ``"INFO"``, ``"WARNING"``).
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Configure standard library logging to route ai_code2doc logs to stderr.
    std_logger = logging.getLogger("ai_code2doc")
    std_logger.setLevel(log_level)

    # Avoid duplicate handlers when setup_logging is called more than once.
    if not std_logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(log_level)
        std_logger.addHandler(handler)

    # Prevent propagation to the root logger to avoid double output.
    std_logger.propagate = False

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    # Choose a renderer based on whether stderr is a TTY.
    if sys.stderr.isatty():
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(
            colors=True,
        )
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Attach the final renderer to the stdlib handler(s).
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    for handler in std_logger.handlers:
        handler.setFormatter(formatter)
