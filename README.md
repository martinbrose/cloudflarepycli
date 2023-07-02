# cloudflarepycli

Python CLI and python class for retrieving user's realtime performance statistics.

## Purpose

Retrieve near-term performance data about the service provided to a user by an ISP. The data includes up and download speeds, latency, and jitter. The CLI makes it possible to pipe the data to other processes for possible uploading, analysis etc. and/or to build a GUI for displaying current and past data. The cloudflareclass.py module is useful for varying the types of test that are done. I will use both in future projects to expand the functionality.

## Install

pip install cloudflarepycli
Windows users must also: pip install wres

## CLI usage

Type 'cfspeedtest' in the environment where you installed the package. Note that this is a shell command, not a Python command.

### Options

  -h, --help  show help message and exit
  
  --debug     log network io
  
  --json      write json to sysout instead of formatted results
  
  --version   show program's version number and exit
  
 ## cloudflareclass usage
 
(WIP) For now see the source code.

## Source repository

https://github.com/tevslin/cloudflarepycli

## How it works

Tests for latency are done by requesting one byte packets from Cloudflare, measuring the elapsed time to get a response, and subtracting the server processing time taken from the header in the returned message. Jitter is computed as the mean of the absolute difference between the arrival of consecutive requests.

The cloudflareclass.py module makes Python requests to various subaddresses of [speed.cloudflare.com](https://speed.cloudflare.com). Their API is not documented, as far as I know, and so that is a vulnerability for this code.

Mirroring the performance of the Cloudflare webpage, the CLI does multiple uploads and downloads with different block sizes and the 90th percentile of all these tests is used for calculating up and download times. Results are similar to those obtained from the webpage. Tests can be varied using the cloudflareclass module.

Unlike Ookla's speedtest CLI, Cloudflare does not require downloading a licensed exe. Cloudflare uses test sites from its own network of caching and hosting centers. This is useful because much of the content users would be retrieving is actually coming from these centers. On the other hand, coverage may be thin in some parts of the world.

## Privacy

No identifying information is sent to any website other than the IP address which servers can see in an HTTP request. Cloudflare can probably deduce something from the tests it runs. No results are sent anywhere. Because this an application and not running in a browser, there are no cookies.

Full source is available in this package.

## Background

Billions of federal dollars are being disbursed to improve broadband availability and quality, especially in rural areas. Tools are needed to assure that ISPs deliver the quality they promise. This software is a pro bono contribution to getting those tools written. 

## Disclaimers

No claims of any sort are made for this software. It has been tested on Windows 10 and 11, MacOS, and  Raspberry Pi OS and should work on other Linux versions but not tested. Use and/or redistribute solely at your own risk. No commitment is made to maintain this software. As noted above, changes made by Cloudflare might break the functionality.

I have no affiliation with Cloudflare, any hosting service, or any ISP (except as a customer).


