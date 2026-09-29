#!/usr/bin/env python3
"""
Endpoint Verification Script for GeoSource
------------------------------------------
Performs HTTP connectivity checks on cataloged GIS service URLs.
Supports sampling, specific service IDs, and timeout configuration.

Usage:
    python scripts/verify_endpoints.py --sample 5
    python scripts/verify_endpoints.py --id WMS-0001
"""

import sys
import os
import sqlite3
import json
import argparse
import urllib.request
import urllib.error
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gis_services.db")


def check_url(url: str, timeout: float = 6.0) -> dict:
    """Send an HTTP HEAD/GET request to test endpoint connectivity."""
    if not url or not url.startswith("http"):
        return {"ok": False, "code": 0, "error": "Invalid URL"}

    start_time = time.time()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GeoSource-Verification/1.0"
    }

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            latency_ms = int((time.time() - start_time) * 1000)
            code = response.getcode()
            return {"ok": code in (200, 201, 202, 204, 301, 302), "code": code, "ms": latency_ms}
    except urllib.error.HTTPError as e:
        latency_ms = int((time.time() - start_time) * 1000)
        return {"ok": False, "code": e.code, "ms": latency_ms, "error": f"HTTP {e.code}"}
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        return {"ok": False, "code": 0, "ms": latency_ms, "error": str(e)[:100]}


def main():
    parser = argparse.ArgumentParser(description="Verify GeoSource endpoint availability")
    parser.add_argument("--sample", type=int, default=5, help="Number of random services to check")
    parser.add_argument("--id", type=str, help="Specific service ID to check (e.g. WMS-0001)")
    parser.add_argument("--timeout", type=float, default=6.0, help="HTTP timeout in seconds")
    args = parser.parse_args()

    conn = sqlite3.connect(f"file:{os.path.abspath(DB_PATH).replace(os.sep, '/')}?mode=ro", uri=True)
    cur = conn.cursor()

    if args.id:
        cur.execute("SELECT service_id, service_name, service_url, status FROM master WHERE service_id = ? COLLATE NOCASE", (args.id.strip(),))
        rows = cur.fetchall()
    else:
        cur.execute("SELECT service_id, service_name, service_url, status FROM master WHERE service_url LIKE 'http%' ORDER BY RANDOM() LIMIT ?", (args.sample,))
        rows = cur.fetchall()

    conn.close()

    if not rows:
        print(f"No services found matching the criteria.")
        return

    print(f"\nVerifying {len(rows)} endpoint(s)...\n" + "-" * 70)
    for sid, name, url, db_status in rows:
        res = check_url(url, timeout=args.timeout)
        flag = "[PASS]" if res.get("ok") else "[FAIL]"
        code = res.get("code", 0)
        latency = res.get("ms", 0)
        err = f" ({res['error']})" if "error" in res and not res.get("ok") else ""
        print(f"{flag} {sid}: {name[:30]:<30} | {code} in {latency}ms{err}")
        print(f"       URL: {url[:70]}")

    print("-" * 70)
    print("Verification completed.")


if __name__ == "__main__":
    main()
