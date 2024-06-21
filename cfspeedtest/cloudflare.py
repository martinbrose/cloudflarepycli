"""
Library for the Cloudflare speedtest suite.

This uses endpoints from speed.cloudflare.com.
"""

from __future__ import annotations

import logging
import statistics
import time
from enum import Enum
from typing import Any, NamedTuple

import requests

log = logging.getLogger("cfspeedtest")


class TestType(Enum):
    """The type of an individual test."""

    Down = "GET"
    Up = "POST"


class TestSpec(NamedTuple):
    """The specifications of an individual test."""

    size: int
    """The size of the test in bytes."""
    iterations: int
    name: str
    type: TestType

    @property
    def bits(self) -> int:
        """The size of the test in bits."""
        return self.size * 8


TestSpecs = tuple[TestSpec, ...]

DOWNLOAD_TESTS: TestSpecs = (
    TestSpec(100_000, 10, "100kB", TestType.Down),
    TestSpec(1_000_000, 8, "1MB", TestType.Down),
    TestSpec(10_000_000, 6, "10MB", TestType.Down),
    TestSpec(25_000_000, 4, "25MB", TestType.Down),
)
UPLOAD_TESTS: TestSpecs = (
    TestSpec(100_000, 8, "100kB", TestType.Up),
    TestSpec(1_000_000, 6, "1MB", TestType.Up),
    TestSpec(10_000_000, 4, "10MB", TestType.Up),
)
DEFAULT_TESTS: TestSpecs = (
    TestSpec(1, 20, "latency", TestType.Down),
    *DOWNLOAD_TESTS,
    *UPLOAD_TESTS,
)


class TestResult(NamedTuple):
    """The result of an individual test."""

    value: Any
    time: float = time.time()


class TestTimers(NamedTuple):
    """A collection of test timer collections, measured in seconds."""

    full: list[float]
    """The times taken to prepare and perform the requests."""
    server: list[float]
    """The times taken to process the requests as reported by the worker."""
    request: list[float]
    """The internal client times elapsed to complete the requests."""

    def to_speeds(self, test: TestSpec) -> list[int]:
        """Compute the test speeds in bits per second from its type and size."""
        if test.type == TestType.Up:
            return [int(test.bits / server_time) for server_time in self.server]
        return [
            int(test.bits / (full_time - server_time))
            for full_time, server_time in zip(self.full, self.server)
        ]

    def to_latencies(self) -> list[float]:
        """Compute the test latencies in milliseconds."""
        return [
            (request_time - server_time) * 1e3
            for request_time, server_time in zip(self.request, self.server)
        ]

    @staticmethod
    def jitter_from(latencies: list[float]) -> float | None:
        """Compute jitter as average deviation between consecutive latencies."""
        if len(latencies) < 2:
            return None
        return statistics.mean(
            [
                abs(latencies[i] - latencies[i - 1])
                for i in range(1, len(latencies))
            ]
        )


class TestMetadata(NamedTuple):
    """The metadata of a test suite."""

    ip: str
    isp: str
    location_code: str
    region: str
    city: str


def _calculate_percentile(data: list[float], percentile: float) -> float:
    """Find the percentile of a list of values."""
    data = sorted(data)
    idx = (len(data) - 1) * percentile
    rem = idx % 1

    if rem == 0:
        return data[int(idx)]

    edges = (data[int(idx)], data[int(idx) + 1])
    return edges[0] + (edges[1] - edges[0]) * rem


SuiteResults = dict[str, dict[str, TestResult]]


class CloudflareSpeedtest:
    """Suite of speedtests."""

    def __init__(  # noqa: D417
        self,
        results: SuiteResults | None = None,
        tests: TestSpecs = DEFAULT_TESTS,
        timeout: tuple[float, float] | float = (10, 25),
    ) -> None:
        """
        Initialize the test suite.

        Arguments:
        ---------
        - `results`: A dictionary of test results. This can be used to include
        results from previous runs.
        - `tests`: The specifications (see `TestSpec`) for all tests to run.
        - `timeout`: The timeout settings for all requests. See the Timeouts
        page of the `requests` documentation for more information.
        - `logger`: The logger that `CloudflareSpeedtest` will use when it
        runs tests, exclusively via `run_all`. When this is set to None,
        no logging will occur.

        """
        self.results = results or {}
        self.results.setdefault("tests", {})
        self.results.setdefault("meta", {})

        self.tests = tests
        self.request_sess = requests.Session()
        self.timeout = timeout

    def metadata(self) -> TestMetadata:
        """Retrieve test location code, IP address, ISP, city, and region."""
        result_data: dict[str, str] = self.request_sess.get(
            "https://speed.cloudflare.com/meta"
        ).json()
        return TestMetadata(
            result_data["clientIp"],
            result_data["asOrganization"],
            result_data["colo"],
            result_data["region"],
            result_data["city"],
        )

    def run_test(self, test: TestSpec) -> TestTimers:
        """Run a test specification iteratively and collect timers."""
        coll = TestTimers([], [], [])
        url = f"https://speed.cloudflare.com/__down?bytes={test.size}"
        data = None
        if test.type == TestType.Up:
            url = "https://speed.cloudflare.com/__up"
            data = b"".zfill(test.size)

        for _ in range(test.iterations):
            start = time.time()
            r = self.request_sess.request(
                test.type.value, url, data=data, timeout=self.timeout
            )
            coll.full.append(time.time() - start)
            coll.server.append(
                float(r.headers["Server-Timing"].split("=")[1]) / 1e3
            )
            coll.request.append(
                r.elapsed.seconds + r.elapsed.microseconds / 1e6
            )
        return coll

    def _sprint(
        self, label: str, result: TestResult, *, meta: bool = False
    ) -> None:
        """Add an entry to the suite results and log it."""
        log.info("%s: %s", label, result.value)
        save_to = self.results["meta"] if meta else self.results["tests"]
        save_to[label] = result

    def run_all(self, *, megabits: bool = False) -> SuiteResults:
        """Run the full test suite."""
        meta = self.metadata()
        self._sprint("ip", TestResult(meta.ip), meta=True)
        self._sprint("isp", TestResult(meta.isp))
        self._sprint("location_code", TestResult(meta.location_code), meta=True)
        self._sprint("location_city", TestResult(meta.city), meta=True)
        self._sprint("location_region", TestResult(meta.region), meta=True)

        data = {"down": [], "up": []}
        for test in self.tests:
            timers = self.run_test(test)

            if test.name == "latency":
                latencies = timers.to_latencies()
                jitter = timers.jitter_from(latencies)
                if jitter:
                    jitter = round(jitter, 2)
                self._sprint(
                    "latency",
                    TestResult(round(statistics.mean(latencies), 2)),
                )
                self._sprint("jitter", TestResult(jitter))
                continue

            speeds = timers.to_speeds(test)
            data[test.type.name.lower()].extend(speeds)
            # TODO: reduce code duplication of megabits reporting
            mean_speed = int(statistics.mean(speeds))
            label_suffix = "bps"
            if megabits:
                mean_speed = round(mean_speed / 1e6, 2)
                label_suffix = "mbps"
            self._sprint(
                f"{test.name}_{test.type.name.lower()}_{label_suffix}",
                TestResult(mean_speed),
            )

        for k, v in data.items():
            result = None
            if len(v) > 0:
                result = int(_calculate_percentile(v, 0.9))
            label_suffix = "bps"
            if megabits:
                result = round(result / 1e6, 2) if result else result
                label_suffix = "mbps"
            self._sprint(
                f"90th_percentile_{k}_{label_suffix}",
                TestResult(result),
            )

        return self.results

    @staticmethod
    def results_to_dict(
        results: SuiteResults,
    ) -> dict[str, dict[str, dict[str, float]]]:
        """Convert the test results to a full dictionary."""
        return {
            k: {sk: sv._asdict()}
            for k, v in results.items()
            for sk, sv in v.items()
        }
