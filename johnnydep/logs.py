import inspect
import logging
import re
import sys

from loguru import logger


def formatter(record):
    escaped = [(k, re.sub("(<.*?>)", r"\\\1", str(v))) for k, v in record["extra"].items()]
    kv = [f"<c>{k}</>=<m>{v}</>" for k, v in escaped]
    kv = " ".join(kv)
    context = f" {kv}" if kv else ""
    ts = f"<d><w>{record['time']:YYYY-MM-DD HH:mm:ss}</></>"
    lvl = f"[<lvl>{record['level'].name}</>]"
    result = f"{ts} {lvl} {record['message']}{context}\n"
    return result


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # plumb stdlib log events through loguru (for formatting consistency)
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = inspect.currentframe(), 0
        while frame:
            filename = frame.f_code.co_filename
            is_logging = filename == logging.__file__
            is_frozen = "importlib" in filename and "_bootstrap" in filename
            if depth > 0 and not (is_logging or is_frozen):
                break
            frame = frame.f_back
            depth += 1
        log = logger.opt(depth=depth, exception=record.exc_info)
        log.log(level, record.getMessage())


def configure_logging(verbosity=0):
    logger.remove()
    level = "DEBUG" if verbosity >= 2 else "INFO" if verbosity >= 1 else "WARNING"
    logger.add(sys.stderr, format=formatter, level=level)
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.NOTSET, force=True)
    if verbosity < 2:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("unearth.collector").setLevel(logging.ERROR)
