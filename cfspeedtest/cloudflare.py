"""
Library for the Cloudflare speedtest suite.

This uses endpoints from speed.cloudflare.com.
"""

from __future__ import annotations

import logging
import statistics
import time
from collections import UserDict
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


def bits_to_megabits(bits: int) -> float:
    """Convert bits to megabits, rounded to 2 decimal places."""
    return round(bits / 1e6, 2)


class SuiteResults(UserDict):
    """The results of a test suite."""

    def __init__(self, *, megabits: bool = False):
        super().__init__()
        self.setdefault("tests", {})
        self._megabits = megabits

    @property
    def meta(self) -> TestMetadata:
        return self["meta"]

    @meta.setter
    def meta(self, value: TestMetadata) -> None:
        self["meta"] = value
        for meta_field, meta_value in value._asdict().items():
            log.info("%s: %s", meta_field, meta_value)

    @property
    def tests(self) -> dict[str, TestResult]:
        return self["tests"]

    def add_test(self, label: str, result: TestResult):
        self.tests[label] = result
        log.info("%s: %s", label, result.value)

    @property
    def percentile_90th_down_bps(self) -> TestResult:
        return self["90th_percentile_down_bps"]

    @property
    def percentile_90th_up_bps(self) -> TestResult:
        return self["90th_percentile_up_bps"]

    def to_full_dict(self) -> dict:
        return {
            "meta": self.meta._asdict(),
            "tests": {k: v._asdict() for k, v in self.tests.items()},
            "90th_percentile_down_bps": self.percentile_90th_down_bps,
            "90th_percentile_up_bps": self.percentile_90th_up_bps,
        }


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
        self.results = results or SuiteResults()
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
                float(r.headers["Server-Timing"].split("=")[1].split(",")[0]) / 1e3
            )
            coll.request.append(
                r.elapsed.seconds + r.elapsed.microseconds / 1e6
            )
        return coll

    def run_test_latency(self, test: TestSpec) -> None:
        """Run a test specification and collect latency results."""
        timers = self.run_test(test)
        latencies = timers.to_latencies()
        jitter = timers.jitter_from(latencies)
        if jitter:
            jitter = round(jitter, 2)
        self.results.add_test(
            "latency", TestResult(round(statistics.mean(latencies), 2))
        )
        self.results.add_test("jitter", TestResult(jitter))

    def run_test_speed(self, test: TestSpec) -> list[int]:
        """Run a test specification and collect speed results."""
        speeds = self.run_test(test).to_speeds(test)
        self.results.add_test(
            f"{test.name}_{test.type.name.lower()}_bps",
            TestResult(int(statistics.mean(speeds))),
        )
        return speeds

    def run_all(self) -> SuiteResults:
        """Run the full test suite."""
        self.results.meta = self.metadata()

        data = {"down": [], "up": []}
        for test in self.tests:
            if test.name == "latency":
                self.run_test_latency(test)
                continue
            data[test.type.name.lower()].extend(self.run_test_speed(test))

        for k, v in data.items():
            result = None
            if len(v) > 0:
                result = int(_calculate_percentile(v, 0.9))
            self.results[f"90th_percentile_{k}_bps"] = TestResult(result)

        return self.results
