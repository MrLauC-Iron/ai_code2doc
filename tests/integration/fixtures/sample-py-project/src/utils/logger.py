"""Logger setup for the sample project."""

import logging


def setup_logger(name: str = "sample_app", level: int = logging.INFO) -> logging.Logger:
    """Create and return a configured logger."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
    return logger
