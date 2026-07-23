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

from cfspeedtest.version import __version__

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
    upload_bytes: list[int] | None = None
    """Per-iteration server-accepted upload bytes from cf-meta-upload-bytes."""

    def to_speeds(self, test: TestSpec) -> list[int]:
        """Compute the test speeds in bits per second from its type and size.

        For uploads, uses the server-accepted byte count from the
        cf-meta-upload-bytes response header when available, falling back to
        the requested payload size.
        """
        if test.type == TestType.Up:
            return [
                int((ub * 8 if ub else test.bits) / st)
                if st > 0
                else int((ub * 8 if ub else test.bits) / max(ft, 1e-6))
                for st, ft, ub in zip(
                    self.server,
                    self.full,
                    self.upload_bytes or [None] * len(self.server),
                )
            ]
        return [
            int(test.bits / (ft - st)) if (ft - st) > 0 else int(test.bits / max(ft, 1e-6))
            for ft, st in zip(self.full, self.server)
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

    ip: Optional[str]
    isp: Optional[str]
    location_code: Optional[str]
    region: Optional[str]
    city: Optional[str]


def _calculate_percentile(data: list[float], percentile: float) -> float:
    """Find the percentile of a list of values."""
    data = sorted(data)
    idx = (len(data) - 1) * percentile
    rem = idx % 1

    if rem == 0:
        return data[int(idx)]

    edges = (data[int(idx)], data[int(idx) + 1])
    return edges[0] + (edges[1] - edges[0]) * rem


def _with_units(
    base_label: str, value: float, *, megabits: bool
) -> tuple[str, TestResult]:
    """Append a unit suffix to a `base_label` and convert the `value`."""
    suffix = "mbps" if megabits else "bps"
    if megabits:
        value = round(value / 1e6, 2)
    return (f"{base_label}_{suffix}", TestResult(value))


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
        self.request_sess.headers.update(
            {
                "Referer": "https://speed.cloudflare.com/",
                "User-Agent": f"cloudflarepycli/{__version__}",
            }
        )
        self.timeout = timeout

    @staticmethod
    def _parse_server_timing(header_value: str) -> float:
        """Parse the server timing header into seconds."""
        worker_dur: float | None = None
        fallback_dur: float | None = None
        metrics = [m.strip() for m in header_value.split(",") if m.strip()]
        for metric in metrics:
            metric_name = metric.split(";")[0].strip().lower()
            params = [p.strip() for p in metric.split(";") if p.strip()]
            for param in params:
                if "=" not in param:
                    continue
                name, value = param.split("=", 1)
                if name.strip().lower() == "dur":
                    try:
                        clean_value = value.strip().strip('"').strip("'")
                        dur = float(clean_value) / 1e3
                    except (ValueError, TypeError):
                        continue
                    if metric_name == "cfSpeedWorker":
                        worker_dur = dur
                    fallback_dur = dur
        if worker_dur is not None:
            return worker_dur
        if fallback_dur is not None:
            return fallback_dur
        log.debug(
            "Server-Timing header did not include a valid duration: %s. Falling back to 0.0",
            header_value,
        )
        return 0.0

    def metadata(self) -> TestMetadata:
        """Retrieve test location code, IP address, ISP, city, and region."""
        response = self.request_sess.get(
            "https://speed.cloudflare.com/meta", timeout=self.timeout
        )
        response.raise_for_status()
        result_data: dict[str, str] = response.json()
        return TestMetadata(
            result_data.get("clientIp"),
            result_data.get("asOrganization"),
            result_data.get("colo"),
            result_data.get("region"),
            result_data.get("city"),
        )

    def run_test(self, test: TestSpec) -> TestTimers:
        """Run a test specification iteratively and collect timers."""
        coll = TestTimers([], [], [])
        upload_bytes: list[int] = []
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
            r.raise_for_status()

            if test.type == TestType.Down and len(r.content) < test.size:
                raise ValueError(
                    "Download response size smaller than expected"
                )

            full_time = time.time() - start
            server_timing_header = r.headers.get("Server-Timing")
            if not server_timing_header:
                raise ValueError("Missing Server-Timing header")

            server_time = self._parse_server_timing(server_timing_header)
            request_time = r.elapsed.total_seconds()

            if server_time >= full_time:
                log.warning(
                    "Server timing >= full time (server=%s, full=%s); clamping.",
                    server_time,
                    full_time,
                )
                server_time = max(full_time - 1e-6, 0.0)

            if server_time >= request_time:
                server_time = max(request_time - 1e-6, 0.0)

            coll.full.append(full_time)
            coll.server.append(server_time)
            coll.request.append(request_time)

            if test.type == TestType.Up:
                ub = r.headers.get("cf-meta-upload-bytes")
                if ub is not None:
                    try:
                        upload_bytes.append(int(ub))
                    except (ValueError, TypeError):
                        pass

        return TestTimers(
            coll.full, coll.server, coll.request, upload_bytes or None
        )

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
                if not latencies:
                    log.error("No samples recorded for latency test")
                    continue
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
            if not speeds:
                log.error("No samples recorded for test: %s", test.name)
                continue
            data[test.type.name.lower()].extend(speeds)
            self._sprint(
                *_with_units(
                    f"{test.name}_{test.type.name.lower()}",
                    int(statistics.mean(speeds)),
                    megabits=megabits,
                )
            )

        for k, v in data.items():
            result = None
            if len(v) > 0:
                result = int(_calculate_percentile(v, 0.9))
            label, value = _with_units(
                f"90th_percentile_{k}", result or 0, megabits=megabits
            )
            self._sprint(
                label,
                value if result else TestResult(None),
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
