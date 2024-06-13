# Changelog

All notable changes to this project will be documented in this file.

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
  - add logger to enable external logging configuration
- **BREAKING CHANGE:** change result keys
  - change all results to use bits instead of megabits by default
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
