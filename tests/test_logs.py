import logging

from loguru import logger

from johnnydep.logs import configure_logging


def test_intercept_handler(capsys):
    configure_logging()
    log = logging.getLogger("test-logger")
    log.warning("test-msg %d", 123)
    logger.remove()
    out, err = capsys.readouterr()
    assert out == ""
    assert "[WARNING] test-msg 123" in err
