#!/usr/bin/env python3
"""Check that every link in README.md resolves (HTTP HEAD succeeds).

Exit code 0 means all links are reachable; non-zero means at least one failed.
"""

import re
import sys
import urllib.request
import urllib.error
import ssl

README_PATH = "README.md"
TIMEOUT = 15
RETRIES = 2
RETRY_DELAY = 3

# Domains known to block automated HEAD requests — fall back to GET
USE_GET_DOMAINS = {"github.com", "bitbucket.org"}


def extract_links(path: str) -> list[str]:
    """Return all http(s) URLs found in the given markdown file."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    return re.findall(r"https?://[^\s)>\]\"]+", text)


def check_url(url: str, use_get: bool = False) -> tuple[bool, str]:
    """Return (ok, detail) for a single URL."""
    method = "GET" if use_get else "HEAD"
    headers = {"User-Agent": "awesome-link-checker/1.0"}

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for attempt in range(1, RETRIES + 1):
        try:
            req = urllib.request.Request(url, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
                if resp.status < 400:
                    return True, f"{resp.status} OK"
        except urllib.error.HTTPError as exc:
            # For HEAD failures on GitHub-like hosts, retry with GET
            if not use_get and exc.code in (403, 405, 406, 501):
                return check_url(url, use_get=True)
            return False, f"HTTP {exc.code}"
        except Exception as exc:
            if attempt < RETRIES:
                import time
                time.sleep(RETRY_DELAY)
                continue
            return False, str(exc)

    return False, "unknown error"


def main() -> int:
    links = extract_links(README_PATH)
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for link in links:
        if link not in seen:
            seen.add(link)
            unique.append(link)

    print(f"Checking {len(unique)} unique links from {README_PATH}...\n")

    failures: list[tuple[str, str]] = []
    for url in unique:
        domain = url.split("//")[1].split("/")[0]
        use_get = any(domain.endswith(d) for d in USE_GET_DOMAINS)
        ok, detail = check_url(url, use_get=use_get)
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {detail:20s} {url}")
        if not ok:
            failures.append((url, detail))

    print(f"\n{'='*60}")
    print(f"Total: {len(unique)}  Passed: {len(unique) - len(failures)}  Failed: {len(failures)}")

    if failures:
        print("\nBroken links:")
        for url, detail in failures:
            print(f"  - {url}  ({detail})")
        return 1

    print("\nAll links are reachable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
