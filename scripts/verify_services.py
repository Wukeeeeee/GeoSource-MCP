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
    python scripts/verify_services.py --limit 50            # 不加 --apply 即为只探测
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


def _with_query(url, params):
    """把查询参数合并进 URL。

    很多服务地址本身就带着 ?request=GetCapabilities&service=WMS，
    直接再追加一遍会产生重复参数，部分服务端会因此返回 InvalidParameterValue。
    这里先剥掉同名参数再合并。
    """
    base, _, query = url.partition("?")
    existing = []
    for part in query.split("&"):
        if not part:
            continue
        key = part.split("=", 1)[0]
        if key.lower() not in {k.lower() for k in params}:
            existing.append(part)
    merged = existing + [f"{k}={v}" for k, v in params.items()]
    return base + ("?" + "&".join(merged) if merged else "")


def verify_wms(url, timeout):
    r = _get(_with_query(url, {"service": "WMS", "request": "GetCapabilities"}), timeout)
    if r is None or r.status_code != 200:
        return False, "weak"
    body = r.text[:3000]
    if "WMS_Capabilities" in body or "WMT_MS_Capabilities" in body:
        return True, "strong"
    if "ServiceException" in body:
        return False, "weak"
    return False, "weak"


def verify_wfs(url, timeout):
    r = _get(_with_query(url, {"service": "WFS", "request": "GetCapabilities"}), timeout)
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
    for test in (url, _with_query(url, {"f": "json"})):
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
    test = _with_query(url, {"f": "json"})
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
    reason = ""
    if not ok:
        # 记录真实原因，备注里才有排查价值；同时区分"网络到不了"与"服务端拒绝"。
        # 复现验证器实际请求的 URL，否则可能测到另一个地址而得出错误结论。
        probe_url = url
        if verifier is verify_wms:
            probe_url = _with_query(url, {"service": "WMS", "request": "GetCapabilities"})
        elif verifier is verify_wfs:
            probe_url = _with_query(url, {"service": "WFS", "request": "GetCapabilities"})
        elif verifier is verify_arcgis:
            probe_url = _with_query(url, {"f": "json"})
        elif verifier is verify_ogcapi:
            probe_url = _with_query(url, {"f": "json"})
        try:
            r = requests.get(probe_url, headers=HEADERS, timeout=timeout, allow_redirects=True)
            if r.status_code == 403:
                reason = "HTTP 403 服务端拒绝脚本 UA，浏览器可能正常"
            elif r.status_code == 429:
                reason = "HTTP 429 触发限流，非服务不可用"
            elif r.status_code >= 500:
                reason = f"HTTP {r.status_code} 服务端错误，可能是临时故障"
            elif r.status_code == 404:
                reason = "HTTP 404 地址已失效"
            else:
                reason = f"HTTP {r.status_code}，未返回该协议的特征响应"
        except requests.exceptions.ConnectionError as e:
            reason = f"连接失败(疑似链路不可达): {str(e)[:60]}"
        except requests.exceptions.Timeout:
            reason = "连接超时(疑似链路不可达)"
        except Exception as e:
            reason = str(e)[:60]
    return {"service_id": service_id, "name": name, "ok": ok, "level": level,
            "url": url, "protocol": protocol, "db_status": status, "reason": reason}


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
        n_promote = n_record = 0
        for r in results:
            if r["level"] == "skipped":
                continue
            sid = r["service_id"]
            if r["ok"] and r["level"] == "strong":
                # 协议级实证：可升级为"已验证"
                cur.execute(
                    "UPDATE master SET status = '已验证', verify_method = ?, last_verified = ? "
                    "WHERE service_id = ?",
                    (f"protocol-probe:{r['level']}", today, sid))
                n_promote += cur.rowcount
            else:
                # 探测失败**不改判为"未验证"**。单次探测失败无法区分三种情况：
                #   1) 服务真的下线了
                #   2) 本机到该站的跨境链路被阻断（实测 GitHub/部分欧洲站在本机不可达）
                #   3) 对脚本 UA 返回 403/429，浏览器打开却正常（实测 flychicago.com）
                # 把 2、3 类误判成"未验证"会污染目录，故只留证据、不动状态。
                if r["ok"]:
                    cur.execute("UPDATE master SET verify_method = ? WHERE service_id = ?",
                                (f"protocol-probe:{r['level']}", sid))
                else:
                    cur.execute(
                        "UPDATE master SET verify_method = ?, notes = COALESCE(notes,'') || ? "
                        "WHERE service_id = ?",
                        (f"protocol-probe:unreachable",
                         f" | [探测未通过 {today}]: {r.get('error') or '无协议级响应'}（未据此改判状态）", sid))
                n_record += cur.rowcount
        conn.commit()
        log(f"已写回：升级『已验证』{n_promote} 条，仅记录探测证据/备注 {n_record} 条（{today}）")
        log("注意：探测失败不会把条目改判为『未验证』——单次失败无法区分服务下线、"
            "跨境链路阻断与 UA 拦截。")
    else:
        log("dry-run 模式，未修改数据库。加 --apply 执行回写。")

    conn.close()


if __name__ == "__main__":
    main()
