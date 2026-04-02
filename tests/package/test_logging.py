import logging

from opencode_a2a import logger


def test_package_logger_installs_null_handler() -> None:
    handlers = logger.handlers

    assert any(isinstance(handler, logging.NullHandler) for handler in handlers)
