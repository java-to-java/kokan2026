import logging
import logging.handlers
import os


def setup_logging(log_cfg: dict) -> None:
    """Configure root logger from the 'logging' config section."""
    level_name = log_cfg.get("level", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    fmt = log_cfg.get("format", "%(asctime)s [%(levelname)s] %(name)s — %(message)s")
    date_fmt = log_cfg.get("date_format", "%Y-%m-%d %H:%M:%S")

    handlers: list[logging.Handler] = []

    if log_cfg.get("console_output", True):
        handlers.append(logging.StreamHandler())

    log_file = log_cfg.get("file")
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        handlers.append(
            logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=log_cfg.get("max_file_size_bytes", 10 * 1024 * 1024),
                backupCount=log_cfg.get("backup_count", 5),
                encoding="utf-8",
            )
        )

    logging.basicConfig(level=level, format=fmt, datefmt=date_fmt, handlers=handlers)
