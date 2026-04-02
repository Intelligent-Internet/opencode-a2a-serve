"""A2A wrapper for opencode."""

import logging
from importlib.metadata import PackageNotFoundError, version

UNKNOWN_VERSION = "0+unknown"
logger = logging.getLogger("opencode_a2a")
logger.addHandler(logging.NullHandler())


def get_package_version() -> str:
    try:
        return version("opencode-a2a")
    except PackageNotFoundError:
        return UNKNOWN_VERSION


__version__ = get_package_version()
