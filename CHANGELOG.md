# Changelog

All notable changes to this project will be documented in this file.

# cloudflarepycli@2.1.6-rc

## Change

- Fix incorrect upload speed calculation. The Cloudflare Speed Test __up endpoint now returns a new response header: cf-meta-upload-bytes — the actual number of bytes the server accepted for the upload (in bytes).

# cloudflarepycli@2.1.5-rc

## Change

- fix: Return 0.0 and log a debug message when the Server-Timing header lacks a valid duration, instead of raising a ValueError.

# cloudflarepycli@2.1.4-rc

## Change

- feat: Enhance `Server-Timing` header parsing for robustness and add checks for empty test samples.

# cloudflarepycli@2.1.3-rc

## Change

- Fix ZeroDivisionError

# cloudflarepycli@2.1.2-rc

## Change

- fix response timing processing

# cloudflarepycli@2.1.1-rc

## Change

- add referer header to fix 400 error

# cloudflarepycli@2.1.0

## Change

- test metadata is now treated as optional to ensure a speedtest is not failing

# cloudflarepycli@2.0.0

## Refactor

- **BREAKING CHANGE:** separate library and logging functionality
- **BREAKING CHANGE:** remove getcolo, getcolodetails, getisp, getfulldata in
  favour of get_metadata
- **BREAKING CHANGE:** change cloudflareclass module to cloudflare
- **BREAKING CHANGE:** change cloudflare class to CloudflareSpeedtest
- **BREAKING CHANGE:** remove download and upload in favour of run_test
- **BREAKING CHANGE:** remove runalltests in favour of run_all
- **BREAKING CHANGE:** change function signature of CloudflareSpeedtest
  - remove thedict, debug, printit, downtests, uptests, latencyreps
  - add results (previously thedict)
  - add tests (previously downtests & uptests) including latency
- **BREAKING CHANGE:** change result keys
  - change all results to use bits instead of megabits by default
    - this can be overriden by using the megabits argument of run_all, which
      changes the suffix of test keys from "bps" to "mbps" accordingly
  - metadata is now stored under "meta"
  - test results are now stored under "tests"
  - "your ip" -> "ip"
  - "your ISP" -> "isp"
  - "test location code" -> "location_code"
  - "test location city" -> "location_city"
  - "test location region" -> "location_region"
  - "latency ms" -> "latency"
  - "Jitter ms" -> "jitter"
  - "{x} download Mbps" -> "{x}_down_bps"
  - "{x} upload Mbps" -> "{x}_up_bps"
  - "90th percentile download Mbps" -> "90th_percentile_down_bps"
  - "90th percentile upload Mbps" -> "90th_percentile_up_bps"
- **BREAKING CHANGE:** change return type of run_all to use new TestResult type

## Features

- add logger
- add TestType enum
- add TestSpec named tuple for easily defining new tests
- add TestResult named tuple for working with test results
- add TestTimers named tuple for timer collections
- add TestMetadata named tuple for working with metadata

# cloudflarepycli@1.8.1

## Refactor

- Remove dependency on numpy ([bc4b10f](https://github.com/tevslin/cloudflarepycli/commit/bc4b10fc7423408a21907636dbaef274bf975d22))

# cloudflarepycli@1.8.0

## Refactor

- Remove dependency on ipdatabase.com
- Deprecate getcolo, getcolodetails and getisp

## Features

- Add getfulldata to get all data about test locations and ISP from cloudflare
