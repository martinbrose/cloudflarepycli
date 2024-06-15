"""Logger utility for the cfspeedtest CLI."""

import logging
from http.client import HTTPConnection

log = logging.getLogger("cfspeedtest")


def setup_log(*, silent: bool = False) -> None:
    """Initialise the log."""
    if not silent:
        log.setLevel(logging.INFO)
        logging.basicConfig(format="%(message)s")


def set_verbosity(*, debug: bool = False) -> None:
    """Set the logger to debug mode."""
    if debug:
        HTTPConnection.debuglevel = 1
        log.setLevel(logging.DEBUG)
        logging.basicConfig(
            format="[%(levelname)s] (%(asctime)s) %(name)s: %(message)s"
        )
        requests_log = logging.getLogger("urllib3")
        requests_log.setLevel(logging.DEBUG)
        requests_log.propagate = True
