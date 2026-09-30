#!/usr/bin/env python3
"""
Portal API Prober for GeoSource
--------------------------------
对 master 表中的"开放数据门户"类条目，自动识别其底层平台
(CKAN / DKAN / ArcGIS Hub(AGOL) / Socrata)，并探测该平台的标准
JSON 接口是否真实可用，把确认过的接口地址回写到 service_url。

平台标准接口约定：
  CKAN    GET {root}/api/3/action/status_show        -> {"success":true,"result":{"ckan_version":...}}
  DKAN    GET {root}/api/3/action/status_show        -> 同上（DKAN 兼容 CKAN action API）
  AGOL    GET {root}/api/v3/datasets?page[size]=1    -> {"data":[...]}  (ArcGIS Hub API v3)
           GET {root}/sharing/rest/portals/self      -> {"id":...,"urlKey":...}
  Socrata GET {root}/api/catalog/v1                  -> [ {...}, ... ]

用法：
    python scripts/probe_portal_api.py --dry-run              # 只探测不写库
    python scripts/probe_portal_api.py --apply                 # 探测并回写 service_url
    python scripts/probe_portal_api.py --apply --limit 100     # 限量试跑
    python scripts/probe_portal_api.py --apply --id DS-0026    # 只测指定 ID
    python scripts/probe_portal_api.py --apply --workers 16
"""

import argparse
import concurrent.futures
import json
import os
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GeoSource-Probe/1.0",
    "Accept": "application/json",
}

# 明显不是门户的协议，不浪费探测请求
SKIP_PROTOCOLS = (
    "ogc wms", "ogc wfs", "ogc wmts", "xyz", "wms", "wfs", "wmts",
    "gtfs", "3d tiles", "cog", "kml", "wcs",
)

_print_lock = threading.Lock()


def log(msg):
    with _print_lock:
        print(msg, flush=True)


def _get(url, timeout):
    """返回 (status_code, body_head) 或 (None, error_str)"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        return resp.status_code, resp.text[:400]
    except requests.exceptions.SSLError as e:
        return None, f"SSL:{str(e)[:80]}"
    except requests.RequestException as e:
        return None, str(e)[:80]


def probe_ckan(root, timeout):
    url = root.rstrip("/") + "/api/3/action/status_show"
    code, body = _get(url, timeout)
    if code == 200 and '"ckan_version"' in body and '"success": true' in body.replace("'", '"'):
        return "CKAN", url, ""
    if code == 200 and '"ckan_version"' in body:
        return "CKAN", url, ""
    return None, None, f"HTTP {code}" if code else str(body)[:60]


def probe_dkan(root, timeout):
    # DKAN 用 /api/3/action/package_search，且站点常有 /api 路径差异
    for cand in (root.rstrip("/") + "/api/3/action/package_search?rows=1",
                 root.rstrip("/") + "/api/3/action/status_show"):
        code, body = _get(cand, timeout)
        if code == 200 and '"result"' in body and ('"success": true' in body or '"results"' in body):
            return "DKAN", cand, ""
    return None, None, f"HTTP {code}" if code else str(body)[:60]


def probe_agol(root, timeout):
    root = root.rstrip("/")
    for cand, kind in (
        (root + "/api/v3/datasets?page%5Bsize%5D=1", "api_v3"),
        (root + "/sharing/rest/portals/self?f=json", "portal_self"),
    ):
        code, body = _get(cand, timeout)
        if code == 200 and body.lstrip().startswith("{"):
            if '"data"' in body or '"urlKey"' in body or '"id"' in body:
                return "ArcGIS Hub", cand, ""
    return None, None, f"HTTP {code}" if code else str(body)[:60]


# 站点自定义的 JSON 包装层（如 meta/api version 之类），不等于 Socrata catalog
SOCRATA_MARKERS = ("resultsSetSize", "resourceColumnName", "metadata", "dataset", "Socrata")


def probe_socrata(root, timeout):
    url = root.rstrip("/") + "/api/catalog/v1"
    code, body = _get(url, timeout)
    if code != 200:
        return None, None, f"HTTP {code}" if code else str(body)[:60]
    stripped = body.lstrip()
    # 拒绝 {"/api/...": 404} 之类的通用 JSON 404 包装
    if stripped.startswith("{") and ('"/api/' in stripped or "/api/" in stripped[:60]):
        return None, None, "非 Socrata 站点(通用 JSON 404)"
    # 拒绝 success:false / error 包装
    low = stripped[:200].lower()
    if '"success": false' in low.replace("'", '"') or '"error"' in low or '"msg"' in low and "not allowed" in low:
        return None, None, "接口返回错误包装"
    if stripped.startswith("["):
        # Socrata catalog 返回数据集数组
        return "Socrata", url, ""
    if stripped.startswith("{"):
        # 对象包装时必须有 Socrata 特有字段
        if any(m in body for m in SOCRATA_MARKERS) and "success" not in low[:40]:
            return "Socrata", url, ""
    return None, None, "响应结构不像 Socrata catalog"


# 顺序即优先级：多数门户是 CKAN 系，其次 AGOL
PROBES = (("CKAN", probe_ckan), ("DKAN", probe_dkan),
          ("ArcGIS Hub", probe_agol), ("Socrata", probe_socrata))


def normalize_root(url):
    """把首页 URL 规整成探测用根地址"""
    if not url or not url.startswith("http"):
        return None
    u = url.strip()
    for suffix in ("/pages/api", "/portal/", "/home"):
        if u.endswith(suffix):
            u = u[: -len(suffix)]
    return u.rstrip("/")


def probe_row(row, timeout):
    service_id, name, service_url, official_url, protocol, status = row
    candidates = []
    for u in (service_url, official_url):
        r = normalize_root(u)
        if r and r not in candidates:
            candidates.append(r)
    if not candidates:
        return {"service_id": service_id, "ok": False, "error": "无可用 URL"}

    errors = []
    for root in candidates:
        for pname, fn in PROBES:
            try:
                platform, api_url, err = fn(root, timeout)
            except Exception as e:  # 单个探测器异常不应中断整批
                err = str(e)[:80]
                platform, api_url = None, None
            if platform:
                return {"service_id": service_id, "name": name, "ok": True,
                        "platform": platform, "root": root, "api_url": api_url,
                        "changed": api_url.rstrip("/") != (service_url or "").rstrip("/")}
            errors.append(f"{pname}:{err}")
        # 第二个候选根也失败就返回
    return {"service_id": service_id, "name": name, "ok": False, "error": "; ".join(errors[:4])}


def is_homepage_only(url):
    """service_url 只是门户首页而非可编程接口时返回 True。

    这类条目才是探测脚本的价值所在：它们需要补上真正的 API 入口。
    """
    if not url or not url.startswith("http"):
        return False
    u = url.lower()
    if any(m in u for m in ("/api/", "getcapabilities", "/stac", "/arcgis/rest/",
                            "?", "/collections", "/v1/", "/v3/", "ogc", "/wms", "/wfs")):
        return False
    path = u.split("://", 1)[-1].split("/", 1)[-1] if "/" in u.split("://", 1)[-1] else ""
    return path.strip("/") == ""


def select_rows(conn, limit=None, only_ids=None, homepage_only=False, prefix=None):
    cur = conn.cursor()
    if only_ids:
        qs = ",".join("?" * len(only_ids))
        sql = (f"SELECT service_id, service_name, service_url, official_url, protocol, status "
               f"FROM master WHERE service_id IN ({qs})")
        return cur.execute(sql, only_ids).fetchall()
    sql = ("SELECT service_id, service_name, service_url, official_url, protocol, status "
           "FROM master WHERE (service_url LIKE 'http%' OR official_url LIKE 'http%')")
    params = []
    if prefix:
        sql += " AND service_id LIKE ?"
        params.append(prefix + "%")
    rows = []
    for r in cur.execute(sql, params):
        if any(p in (r[4] or "").lower() for p in SKIP_PROTOCOLS):
            continue
        if r[5] == "已停止":
            continue
        if homepage_only and not (is_homepage_only(r[2]) or is_homepage_only(r[3])):
            continue
        rows.append(r)
    if limit:
        rows = rows[:limit]
    return rows


def main():
    ap = argparse.ArgumentParser(description="探测并回写 GeoSource 门户的标准 API 接口")
    ap.add_argument("--apply", action="store_true", help="把确认的接口地址写回 service_url")
    ap.add_argument("--dry-run", action="store_true", help="只探测不写库（默认行为）")
    ap.add_argument("--homepage-only", action="store_true",
                    help="只探测 service_url 仅为门户首页的条目（补 API 入口时用）")
    ap.add_argument("--prefix", help="只探测 service_id 以该前缀开头的条目，如 DS-（开放数据门户）")
    ap.add_argument("--limit", type=int, default=0, help="最多探测多少条")
    ap.add_argument("--id", action="append", dest="ids", help="只探测指定 service_id，可重复")
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--out", default=os.path.join(ROOT, "portal_api_results.json"))
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    rows = select_rows(conn, args.limit or None, args.ids, args.homepage_only, args.prefix)
    log(f"待探测 {len(rows)} 条，超时 {args.timeout}s，并发 {args.workers}\n")
    if not rows:
        return

    t0 = time.time()
    results = []
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(probe_row, r, args.timeout): r for r in rows}
        for fut in concurrent.futures.as_completed(futs):
            res = fut.result()
            results.append(res)
            done += 1
            if res["ok"]:
                flag = "改" if res.get("changed") else "同"
                log(f"[OK  {flag}] {res['service_id']:<10} {res['platform']:<12} "
                    f"{(res.get('name') or '')[:26]:<26} -> {res['api_url'][:78]}")
            else:
                log(f"[FAIL   ] {res['service_id']:<10} {(res.get('name') or '')[:26]:<26} "
                    f"{res.get('error','')[:70]}")
            if done % 25 == 0:
                log(f"  ... 进度 {done}/{len(rows)}  用时 {int(time.time()-t0)}s")

    ok = [r for r in results if r["ok"]]
    changed = [r for r in ok if r.get("changed")]
    log("\n" + "=" * 72)
    log(f"探测完成：成功 {len(ok)} / {len(results)}  其中需回写 {len(changed)}  用时 {int(time.time()-t0)}s")

    by_plat = {}
    for r in ok:
        by_plat[r["platform"]] = by_plat.get(r["platform"], 0) + 1
    log("平台分布：" + ", ".join(f"{k}={v}" for k, v in sorted(by_plat.items(), key=lambda x: -x[1])))

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    log(f"明细已写入 {args.out}")

    if args.apply:
        cur = conn.cursor()
        today = time.strftime("%Y-%m-%d")
        n_url = n_status = 0
        for r in ok:
            # 实测通过的接口本身就是验证证据，状态必须同步，否则库里会出现
            # "last_verified 是今天却仍标未验证" 的自相矛盾记录
            cur.execute(
                "UPDATE master SET status = '已验证', verify_method = ?, last_verified = ? "
                "WHERE service_id = ? AND status != '已验证'",
                (f"portal-probe:{r['platform']}", today, r["service_id"]))
            n_status += cur.rowcount
            if r.get("changed"):
                cur.execute(
                    "UPDATE master SET service_url = ?, official_url = COALESCE(NULLIF(official_url,''), ?) "
                    "WHERE service_id = ?",
                    (r["api_url"], r["root"], r["service_id"]))
                n_url += cur.rowcount
        conn.commit()
        log(f"已回写 service_url {n_url} 条，状态升级为『已验证』{n_status} 条（last_verified={today}）")
    else:
        log("dry-run 模式，未修改数据库。加 --apply 执行回写。")

    conn.close()


if __name__ == "__main__":
    main()
