#!/usr/bin/env python3
"""
Protocol-aware Service Verifier for GeoSource
---------------------------------------------
对 master 表中非门户类条目，按其协议做**语义级**连通性验证——
不是"URL 能不能打开"，而是"这个服务是否真的以声明的协议应答"。

验证手法：
  OGC WMS      GET {url}?service=WMS&request=GetCapabilities  -> 响应含 <WMS_Capabilities> 或 WMT_MS_Capabilities
  OGC WFS      GET {url}?service=WFS&request=GetCapabilities  -> 响应含 <WFS_Capabilities> 或 WFS_Capabilities
  OGC WMTS     GET {url}                                     -> 响应含 <Capabilities> 且含 WMTS 关键字
  OGC API      GET {url}(+?f=json)                            -> JSON 且含 "links" 或 "collections"/"features"
  STAC         GET {root}/stac 或 {url}                       -> JSON 含 "stac_version" 或 links 指向 /conformance
  ArcGIS REST  GET {url}?f=json                              -> JSON 含 "layers"/"tables"/"services"/"folders"/"currentVersion"
  XYZ 瓦片     GET {url 模板中的 {z}/{x}/{y} 替换为 0/0/0}     -> 200 且 Content-Type 为图片
  GTFS         GET {url}                                     -> ZIP magic "PK"
  其他 HTTP    仅做连通性检查并标注为 weak

用法：
    python scripts/verify_services.py --dry-run --limit 50
    python scripts/verify_services.py --apply --workers 20
    python scripts/verify_services.py --apply --id WMS-0001
    python scripts/verify_services.py --apply --only-status 已验证   # 复验已标"已验证"的条目
"""

import argparse
import concurrent.futures
import json
import os
import re
import sqlite3
import sys
import threading
import time

import requests

if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "gis_services.db")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GeoSource-Verify/2.0",
    "Accept": "*/*",
}

_print_lock = threading.Lock()


def log(msg):
    with _print_lock:
        print(msg, flush=True)


def _get(url, timeout, accept=None):
    h = dict(HEADERS)
    if accept:
        h["Accept"] = accept
    try:
        r = requests.get(url, headers=h, timeout=timeout, allow_redirects=True)
        return r
    except Exception:
        return None


def verify_wms(url, timeout):
    sep = "&" if "?" in url else "?"
    test = f"{url}{sep}service=WMS&request=GetCapabilities"
    r = _get(test, timeout)
    if r is None or r.status_code != 200:
        return False, "weak"
    body = r.text[:3000]
    if "WMS_Capabilities" in body or "WMT_MS_Capabilities" in body:
        return True, "strong"
    return False, "weak"


def verify_wfs(url, timeout):
    sep = "&" if "?" in url else "?"
    r = _get(f"{url}{sep}service=WFS&request=GetCapabilities", timeout)
    if r is None or r.status_code != 200:
        return False, "weak"
    if "WFS_Capabilities" in r.text[:3000]:
        return True, "strong"
    return False, "weak"


def verify_wmts(url, timeout):
    r = _get(url, timeout)
    if r is None or r.status_code != 200:
        return False, "weak"
    body = r.text[:3000]
    if "<Capabilities" in body and ("WMTS" in body or "wmts" in body):
        return True, "strong"
    return False, "weak"


def verify_ogcapi(url, timeout):
    for test in (url, url + ("&" if "?" in url else "?") + "f=json"):
        r = _get(test, timeout, accept="application/json")
        if r is None or r.status_code != 200:
            continue
        body = r.text[:2000]
        if any(k in body for k in ('"links"', '"collections"', '"features"', '"conformsTo"')):
            return True, "strong"
    return False, "weak"


def verify_stac(url, timeout):
    candidates = [url]
    if url.rstrip("/").endswith("/stac"):
        candidates.append(url + "/conformance")
    else:
        candidates.append(url.rstrip("/") + "/conformance")
    for test in candidates:
        r = _get(test, timeout, accept="application/json")
        if r is None or r.status_code != 200:
            continue
        body = r.text[:2000]
        if "stac_version" in body or "conformsTo" in body:
            return True, "strong"
    return False, "weak"


def verify_arcgis(url, timeout):
    test = url + ("&" if "?" in url else "?") + "f=json"
    r = _get(test, timeout, accept="application/json")
    if r is None or r.status_code != 200:
        return False, "weak"
    body = r.text[:2000]
    if any(k in body for k in ('"layers"', '"tables"', '"services"', '"folders"',
                               '"currentVersion"', '"type": "FeatureService"')):
        return True, "strong"
    return False, "weak"


def verify_xyz(url, timeout):
    if not re.search(r"\{[xyz]\}|%7B[xyz]%7D|\$\{[xyz]\}", url):
        return False, "skipped"
    test = re.sub(r"\{[xyz]\}|%7B([xyz])%7D|\$\{([xyz])\}", "0", url)
    r = _get(test, timeout)
    if r is None or r.status_code != 200:
        return False, "weak"
    ct = r.headers.get("Content-Type", "")
    if ct.startswith("image/") or ct in ("application/octet-stream", "application/x-protobuf"):
        return True, "strong"
    return False, "weak"


def verify_gtfs(url, timeout):
    r = _get(url, timeout)
    if r is None:
        return False, "weak"
    if r.status_code != 200:
        return False, "weak"
    if r.content[:2] == b"PK":
        return True, "strong"
    return False, "weak"


def verify_weak(url, timeout):
    r = _get(url, timeout)
    if r is not None and r.status_code in (200, 201, 202, 204, 301, 302, 401, 403):
        return True, "weak"
    return False, "weak"


def pick_verifier(protocol, service_url):
    p = (protocol or "").lower()
    u = (service_url or "").lower()
    if "wms" in p or "wms" in u:
        return verify_wms
    if "wfs" in p or "wfs" in u:
        return verify_wfs
    if "wmts" in p or "wmts" in u:
        return verify_wmts
    if "stac" in p or "/stac" in u:
        return verify_stac
    if "ogc api" in p or "features" in p or "records" in p:
        return verify_ogcapi
    if "arcgis" in p or "mapserver" in u or "featureserver" in u or "/arcgis/rest/" in u:
        return verify_arcgis
    if "xyz" in p or "tile" in p or "tiles" in p:
        return verify_xyz
    if "gtfs" in p:
        return verify_gtfs
    return verify_weak


def verify_row(row, timeout):
    service_id, name, url, protocol, status = row
    if not url or not url.startswith("http"):
        return {"service_id": service_id, "name": name, "ok": False,
                "level": "skipped", "error": "无 http 地址", "protocol": protocol}
    verifier = pick_verifier(protocol, url)
    try:
        ok, level = verifier(url, timeout)
    except Exception as e:
        return {"service_id": service_id, "name": name, "ok": False,
                "level": "weak", "error": str(e)[:100], "protocol": protocol}
    return {"service_id": service_id, "name": name, "ok": ok, "level": level,
            "url": url, "protocol": protocol, "db_status": status}


def select_rows(conn, limit, only_ids, only_status):
    cur = conn.cursor()
    if only_ids:
        qs = ",".join("?" * len(only_ids))
        sql = ("SELECT service_id, service_name, service_url, protocol, status FROM master "
               f"WHERE service_id IN ({qs})")
        rows = cur.execute(sql, only_ids).fetchall()
    else:
        sql = ("SELECT service_id, service_name, service_url, protocol, status FROM master "
               "WHERE service_url LIKE 'http%'")
        params = []
        if only_status:
            sql += " AND status = ?"
            params.append(only_status)
        rows = cur.execute(sql, params).fetchall()
    if limit:
        rows = rows[:limit]
    return rows


def main():
    ap = argparse.ArgumentParser(description="按协议语义验证 GeoSource 服务可用性")
    ap.add_argument("--apply", action="store_true", help="把验证结果写回 status/last_verified/verify_method")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--id", action="append", dest="ids")
    ap.add_argument("--only-status", help="只验证某个状态的条目，如 已验证")
    ap.add_argument("--timeout", type=float, default=12.0)
    ap.add_argument("--workers", type=int, default=20)
    ap.add_argument("--out", default=os.path.join(ROOT, "service_verify_results.json"))
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    rows = select_rows(conn, args.limit or None, args.ids, args.only_status)
    log(f"待验证 {len(rows)} 条，超时 {args.timeout}s，并发 {args.workers}\n")
    if not rows:
        return

    t0 = time.time()
    results = []
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(verify_row, r, args.timeout) for r in rows]
        for fut in concurrent.futures.as_completed(futs):
            res = fut.result()
            results.append(res)
            done += 1
            tag = "强" if res["level"] == "strong" else ("弱" if res["level"] == "weak" else "跳")
            flag = "PASS" if res["ok"] else "FAIL"
            log(f"[{flag}/{tag}] {res['service_id']:<12} {(res.get('name') or '')[:24]:<24} "
                f"{(res.get('protocol') or '')[:20]:<20} {res.get('error','')[:40]}")
            if done % 50 == 0:
                log(f"  ... 进度 {done}/{len(rows)} 用时 {int(time.time()-t0)}s")

    strong = [r for r in results if r["ok"] and r["level"] == "strong"]
    weak = [r for r in results if r["ok"] and r["level"] == "weak"]
    failed = [r for r in results if not r["ok"] and r["level"] != "skipped"]
    skipped = [r for r in results if r["level"] == "skipped"]

    log("\n" + "=" * 72)
    log(f"完成：协议级确认 {len(strong)} | 仅连通 {len(weak)} | 失败 {len(failed)} | 跳过 {len(skipped)} "
        f"| 用时 {int(time.time()-t0)}s")

    # 现状对比：有多少"已验证"其实只靠弱连通性支撑
    unverifiable = [r for r in results if r["db_status"] == "已验证" and r["level"] == "weak"]
    log(f"其中标为『已验证』但仅弱连通：{len(unverifiable)} 条")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    log(f"明细已写入 {args.out}")

    if args.apply:
        cur = conn.cursor()
        today = time.strftime("%Y-%m-%d")
        n_status = n_lv = 0
        for r in results:
            if r["level"] == "skipped":
                continue
            new_status = "已验证" if r["ok"] else "未验证"
            method = f"protocol-probe:{r['level']}"
            cur.execute(
                "UPDATE master SET status = ?, verify_method = ?, last_verified = ? WHERE service_id = ?",
                (new_status, method, today, r["service_id"]))
            n_status += cur.rowcount
        conn.commit()
        log(f"已写回 {n_status} 条（status/verify_method/last_verified={today}）")
    else:
        log("dry-run 模式，未修改数据库。加 --apply 执行回写。")

    conn.close()


if __name__ == "__main__":
    main()
