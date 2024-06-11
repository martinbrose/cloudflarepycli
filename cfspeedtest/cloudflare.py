"""
Created on Fri Nov  5 15:10:57 2021
class object for connection testing with requests to speed.cloudflare.com
runs tests and stores results in dictionary
cloudflare(thedict=None,debug=False,print=True,downtests=None,uptests=None,latencyreps=20)

thedict: dictionary to store results in
    if not passed in, created here
    if passed in, used and update - allows keeping partial results from previous runs
    each result has a key and the entry is a dict with "time" and "value" items
debug: True turns on io logging for debugging
printit: if true, results are printed as well as added to the dictionary
downtests: tuple of download tests to be performed
    if None, defaultdowntests (see below) is used
    format is ((size, reps, label)......)
        size: size of block to download
        reps: number of times to repeat test
        label: text label for test - also becomes key in the dict
uptests: tuple of upload tests to be performed
    if None, defaultuptests (see below) is used
    format is ((size, reps, label)......)
        size: size of block to upload
        reps: number of times to repeat test
        label: text label for test - also becomes key in the dict
latencyreps: number of repetitions for latency test

@author: /tevslin
"""

from __future__ import annotations

import array
import statistics
import time
from enum import Enum
from typing import TYPE_CHECKING, Any, NamedTuple

import requests

if TYPE_CHECKING:
    from logging import Logger


class TestType(Enum):
    Down = "GET"
    Up = "POST"


class TestSpec(NamedTuple):
    """The specifications of an individual test."""

    size: int
    iterations: int
    name: str
    type: TestType

    @property
    def bits(self) -> int:
        """Convert the size of the test in bytes to bits."""
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
    """A collection of test timer collections."""

    full: list[float]
    server: list[float]
    request: list[float]


class TestMetadata(NamedTuple):
    """The metadata of a test suite."""

    ip: str
    isp: str
    location_code: str
    region: str
    city: str


class CloudflareSpeedtest:
    """Suite of speedtests."""

    def __init__(
        self,
        results: dict[str, TestResult] | None = None,
        tests: TestSpecs = DEFAULT_TESTS,
        timeout: tuple[float, float] = (3.05, 25),
        logger: Logger | None = None,
    ) -> None:
        """Initialize the test suite."""
        self.results = results or {}
        self.tests = tests
        self.request_sess = requests.Session()
        self.timeout = timeout
        self.logger = logger

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

    def sprint(self, label: str, result: TestResult) -> None:
        """Add an entry to the suite results and log it."""
        if self.logger:
            self.logger.info("%s: %s", label, result.value)
        self.results[label] = result

    @staticmethod
    def calculate_percentile(data: list[float], percentile: float) -> float:
        """Find the percentile of a sorted list of values."""
        data = sorted(data)
        idx = (len(data) - 1) * percentile
        rem = idx % 1

        if rem == 0:
            return data[int(idx)]

        edges = (data[int(idx)], data[int(idx) + 1])
        return edges[0] + (edges[1] - edges[0]) * rem

    def run_all(self) -> dict[str, TestResult]:
        """Run the full test suite."""
        meta = self.metadata()
        self.sprint("ip", TestResult(meta.ip))
        self.sprint("isp", TestResult(meta.isp))
        self.sprint("location_code", TestResult(meta.location_code))
        self.sprint("location_city", TestResult(meta.city))
        self.sprint("location_region", TestResult(meta.region))

        data = {"down": [], "up": []}
        for test in self.tests:
            timers = self.run_test(test)

            if test.name == "latency":
                latencies = array.array("f", [
                    (timers.request[i] - timers.server[i]) * 1e3
                    for i in range(len(timers.request))
                ])
                jitter = statistics.median([
                    abs(latencies[i] - latencies[i - 1])
                    for i in range(1, len(latencies))
                ])
                self.sprint(
                    "latency",
                    TestResult(round(statistics.median(latencies), 2))
                )
                self.sprint("jitter", TestResult(round(jitter, 2)))
                continue

            if test.type == TestType.Down:
                speeds = array.array("f", [
                    int(test.bits / (timers.full[i] - timers.server[i]))
                    for i in range(len(timers.full))
                ])
            else:
                speeds = array.array("f", [
                    int(test.bits / server_time)
                    for server_time in timers.server
                ])
            data[test.type.name.lower()].extend(speeds)
            self.sprint(
                f"{test.name}_{test.type.name.lower()}_bps",
                TestResult(int(statistics.mean(speeds)))
            )
        for k, v in data.items():
            self.sprint(
                f"90th_percentile_{k}_bps",
                TestResult(int(self.calculate_percentile(v, 0.9)))
            )

        return self.results
