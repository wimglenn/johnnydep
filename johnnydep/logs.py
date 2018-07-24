# coding: utf-8
from __future__ import unicode_literals

import logging.config

import structlog


def configure_logging(verbosity=0):
    level = "DEBUG" if verbosity > 1 else "INFO" if verbosity == 1 else "WARNING"
    timestamper = structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S")
    # Add the log level and a timestamp to the event_dict if the log entry is not from structlog
    pre_chain = [structlog.stdlib.add_log_level, timestamper]
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "plain": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.dev.ConsoleRenderer(colors=False),
                    "foreign_pre_chain": pre_chain,
                },
                "colored": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.dev.ConsoleRenderer(colors=True),
                    "foreign_pre_chain": pre_chain,
                },
            },
            "handlers": {
                "default": {
                    "level": level,
                    "class": "logging.StreamHandler",
                    "formatter": "colored",
                },
                # "file": {
                #     "level": "DEBUG",
                #     "class": "logging.handlers.WatchedFileHandler",
                #     "filename": "johnnydep.log",
                #     "formatter": "plain",
                # },
            },
            "loggers": {
                "": {
                    "handlers": ["default"],
                    # "handlers": ["default", "file"],
                    "level": "DEBUG",
                    "propagate": True,
                }
            },
        }
    )
    structlog.configure(
        processors=[
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            timestamper,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
