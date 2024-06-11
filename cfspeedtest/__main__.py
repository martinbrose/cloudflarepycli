import json
import sys

from cfspeedtest.cloudflare import CloudflareSpeedtest
from cfspeedtest.logger import log, set_verbosity
from cfspeedtest.version import __version__


def cfspeedtest() -> None:
    """Run a network speedtest suite via Cloudflare and ping."""
    args = sys.argv[1:]

    set_verbosity("--debug" in args)

    if "--version" in args:
        log.info("cfspeedtest %s", __version__)
        log.debug("Python %s", sys.version)
        sys.exit(0)

    if "--json" in args:
        print(
            json.dumps(
                {
                    k: v._asdict()
                    for k, v in CloudflareSpeedtest().run_all().items()
                }
            )
        )
    else:
        CloudflareSpeedtest(logger=log).run_all()


if __name__ == "__main__":
    cfspeedtest()
