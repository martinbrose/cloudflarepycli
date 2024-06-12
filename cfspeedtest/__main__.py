"""The cfspeedtest CLI implementation."""

import json
import sys

from cfspeedtest.cloudflare import CloudflareSpeedtest
from cfspeedtest.logger import log, set_verbosity
from cfspeedtest.version import __version__


def cfspeedtest() -> None:
    """Run a network speedtest suite via Cloudflare."""
    args = sys.argv[1:]

    set_verbosity(debug="--debug" in args)

    if "--version" in args:
        log.info("cfspeedtest %s", __version__)
        log.debug("Python %s", sys.version)
        sys.exit(0)

    use_json = "--json" in args
    results = CloudflareSpeedtest(logger=None if use_json else log).run_all()

    if use_json:
        log.info(json.dumps(CloudflareSpeedtest.results_to_dict(results)))


if __name__ == "__main__":
    cfspeedtest()
