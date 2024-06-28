"""cfspeedtest, a Cloudflare speedtest suite in Python."""

from cfspeedtest.cloudflare import (
    CloudflareSpeedtest,
    SuiteResults,
    TestSpec,
    TestType,
)

__all__ = ("CloudflareSpeedtest", "SuiteResults", "TestSpec", "TestType")
