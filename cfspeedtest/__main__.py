"""The cfspeedtest CLI implementation."""

import json
import sys
from argparse import ArgumentParser

from cfspeedtest.cloudflare import CloudflareSpeedtest
from cfspeedtest.logger import log, set_verbosity
from cfspeedtest.version import __version__


def cfspeedtest() -> None:
    """Run a network speedtest suite via Cloudflare."""
    parser = ArgumentParser(prog="cfspeedtest", description=cfspeedtest.__doc__)
    parser.add_argument("--debug", action="store_true", help="Log network I/O.")
    parser.add_argument(
        "--json", action="store_true", help="Write JSON to stdout."
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show program's version and exit.",
    )
    args = parser.parse_args()

    set_verbosity(debug=args.debug)

    if args.version:
        log.info("cfspeedtest %s", __version__)
        log.debug("Python %s", sys.version)
        sys.exit(0)

    results = CloudflareSpeedtest(logger=None if args.json else log).run_all()

    if args.json:
        log.info(json.dumps(CloudflareSpeedtest.results_to_dict(results)))


if __name__ == "__main__":
    cfspeedtest()
