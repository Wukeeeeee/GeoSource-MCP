#!/usr/bin/env python3
"""
Daily Health Check & Probe Script for GeoSource-MCP
---------------------------------------------------
Runs automated health inspections on sampled endpoints, produces GitHub-compatible
markdown summaries, and tests core MCP server tools.
"""

import sys
import os
import sqlite3
import json
import argparse
import urllib.request
import urllib.error
import time
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gis_services.db")


def check_endpoint(url: str, timeout: float = 8.0) -> dict:
    if not url or not url.startswith("http"):
        return {"ok": False, "code": 0, "error": "Invalid URL"}

    start = time.time()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GeoSource-HealthBot/1.0",
        "Accept": "*/*",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency = int((time.time() - start) * 1000)
            code = resp.getcode()
            # 2xx and 3xx are considered reachable
            return {"ok": code < 400, "code": code, "latency": latency}
    except urllib.error.HTTPError as e:
        latency = int((time.time() - start) * 1000)
        # 400/403/412/418 usually mean server is alive but requires specific params/WAF
        alive = e.code in (400, 403, 412, 418, 429)
        return {"ok": alive, "code": e.code, "latency": latency, "error": f"HTTP {e.code}"}
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        return {"ok": False, "code": 0, "latency": latency, "error": str(e)[:80]}


def run_probe(sample_size: int = 50, output_md: str = None):
    print(f"[HEALTH-CHECK] Starting GeoSource sample probe (sample size: {sample_size})...")
    conn = sqlite3.connect(f"file:{os.path.abspath(DB_PATH).replace(os.sep, '/')}?mode=ro", uri=True)
    cur = conn.cursor()

    cur.execute(
        "SELECT service_id, service_name, service_url, status, protocol, country "
        "FROM master WHERE status = '已验证' AND service_url LIKE 'http%' "
        "ORDER BY RANDOM() LIMIT ?",
        (sample_size,)
    )
    rows = cur.fetchall()
    conn.close()

    total = len(rows)
    passed = 0
    results = []

    for sid, name, url, status, proto, country in rows:
        res = check_endpoint(url)
        is_ok = res.get("ok", False)
        if is_ok:
            passed += 1
        results.append({
            "id": sid,
            "name": name,
            "url": url,
            "proto": proto or "Unknown",
            "country": country or "Global",
            "status": "PASS" if is_ok else "WARN",
            "code": res.get("code", 0),
            "latency": res.get("latency", 0),
            "error": res.get("error", "")
        })
        flag = "✓" if is_ok else "✗"
        print(f"[{flag}] {sid}: {name[:28]:<28} | {res.get('code', 0)} in {res.get('latency', 0)}ms")

    pass_rate = (passed / total * 100) if total > 0 else 0
    print("-" * 60)
    print(f"Summary: {passed}/{total} reachable ({pass_rate:.1f}%)")

    if output_md:
        md = [
            f"## 🩺 GeoSource Daily Health Probe Report",
            f"- **Date**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"- **Sample Size**: {total} random verified endpoints",
            f"- **Success Rate**: **{pass_rate:.1f}%** ({passed}/{total} responded)",
            "",
            "| ID | Service Name | Protocol | Country | Code | Latency | Status |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
        ]
        for r in results:
            status_icon = "🟢 PASS" if r['status'] == "PASS" else f"🟡 WARN ({r['error']})"
            md.append(f"| `{r['id']}` | {r['name'][:30]} | {r['proto']} | {r['country']} | {r['code']} | {r['latency']}ms | {status_icon} |")

        with open(output_md, "w", encoding="utf-8") as f:
            f.write("\n".join(md) + "\n")
        print(f"[HEALTH-CHECK] Markdown report saved to {output_md}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=30)
    parser.add_argument("--output-md", type=str, default="")
    args = parser.parse_args()
    run_probe(sample_size=args.sample, output_md=args.output_md or None)
