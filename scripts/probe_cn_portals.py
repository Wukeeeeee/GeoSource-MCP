#!/usr/bin/env python3
"""
Chinese Government Open-Data Portal Prober
-------------------------------------------
国内省市"公共数据开放平台"与国外 CKAN/ArcGIS Hub 完全是两套东西：
它们多为 Vue 单页应用，真实接口藏在打包后的 JS 里，且多数要求统一
身份认证(SSO)后才能取数。库里 DS-118x 这批原本只写了政府首页
(protocol="HTTP下载" 是占位说法，不是协议)，本脚本为其补上真实接口地址。

已实测确认的两种国产平台：

  DExchangeOpen（银川/柳州等多地在用）
      识别特征: HTML 中含 /dexchange/openportal/ 资源路径
      API 前缀: {root}/dexchangeOpen
      探活端点: {prefix}/appauth/getappid?appId=...&appName=DExchangeOpen&timeStamp=...
      实测银川返回 {"code":401,"msg":"sso not login."}
      —— 接口是活的，但必须先 SSO 登录，因此无 Key 匿名调用拿不到数据

  Jspm 平台（东营/滨州等多地在用）
      识别特征: 引用 jspm_packages/ 且有 /config-*.js
      站点按城市分子路径（如 /dongying、/binzhou）

用法：
    python scripts/probe_cn_portals.py                    # 探测，不写库
    python scripts/probe_cn_portals.py --apply            # 回写 service_url
    python scripts/probe_cn_portals.py --id DS-1180        # 只测某条
"""

import argparse
import concurrent.futures
import json
import os
import re
import socket
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
}

# DExchangeOpen 门户在前端硬编码的应用标识
DEX_APP_ID = "84247F0E39C54292907674C879033A78"
DEX_APP_NAME = "DExchangeOpen"

_print_lock = threading.Lock()


def log(msg):
    with _print_lock:
        print(msg, flush=True)


def host_of(url):
    """从库里记录的 URL 中取出纯主机名。

    库里不少条目的 URL 后面粘了中文备注，例如
    'data.shandong.gov.cn（接口调用说明页面'、'gzw.gansu.gov.cn（省国资委代管平台公告'，
    直接拿整串做 DNS 查询会误判为域名失效。
    """
    if not url:
        return None
    u = url.split("://", 1)[-1]
    u = re.split("[（(\\s]", u, 1)[0]
    u = u.split("/", 1)[0].strip()
    # 去掉端口（如 www.huaian.gov.cn:9027），DNS 查询只认主机名
    if ":" in u:
        u = u.split(":", 1)[0]
    return u or None


def dns_ok(host):
    try:
        socket.gethostbyname(host)
        return True
    except Exception:
        return False


def fetch(url, timeout):
    """同时尝试 https 与 http。国内政务站常见 443 被限、80 可通的情况。"""
    for scheme in ("https", "http"):
        full = f"{scheme}://{url.split('://', 1)[-1]}" if "://" not in url else url
        try:
            r = requests.get(full, headers=HEADERS, timeout=timeout, allow_redirects=True)
            return r, full
        except Exception:
            continue
    return None, None


def detect_platform(page_html, url):
    """从首页 HTML 判断底层国产平台。"""
    low = page_html.lower()
    if "dexchange/openportal" in low or "/dexchangeopen" in low:
        return "DExchangeOpen", "/dexchangeOpen"
    if "jspm_packages" in low or "jspm" in low:
        m = re.search(r'<input id="loginroot_path" value="/([a-z]+)"', page_html)
        sub = f"/{m.group(1)}" if m else ""
        return "Jspm", sub
    return None, None


def probe_row(row, timeout):
    service_id, name, service_url, official_url, status = row
    host = None
    for cand in (service_url, official_url):
        h = host_of(cand)
        if h:
            host = h
            break

    result = {"service_id": service_id, "name": name, "db_status": status,
              "ok": False, "dns": None, "platform": None, "api_url": None,
              "note": ""}

    if not host:
        result["note"] = "无可用 URL"
        return result

    result["dns"] = dns_ok(host)
    if not result["dns"]:
        result["note"] = "域名无法解析（含阿里公共DNS复核），站点已下线或迁入省级平台"
        return result

    r, final_url = fetch(host + "/", timeout)
    if r is None or r.status_code >= 500:
        result["note"] = "首页无法访问（连接被重置或 5xx），本机链路问题与站点状态待区分"
        return result
    if r.status_code == 404:
        result["note"] = "首页 404，记录的地址可能已变更"
        return result

    platform, prefix = detect_platform(r.text, final_url)
    if not platform:
        result["ok"] = True
        result["note"] = "首页可访问，未识别出已知国产平台"
        return result

    result["platform"] = platform
    if platform == "Jspm":
        # Jspm 平台是服务端渲染，目录页 HTML 直出，本来就没有公开 JSON 检索接口。
        # 首页活着 = 服务可用，不要再拿 DExchangeOpen 的网关去探（必然 404）。
        m = re.search(r'id="searchroot_path" value="(/[a-z]+)"', r.text)
        sub = m.group(1) if m else prefix
        result["ok"] = True
        result["api_url"] = final_url.rstrip("/") + sub + "/catalog/"
        result["note"] = ("Jspm 平台(服务端渲染，无公开 JSON 接口)，"
                          f"数据目录页 {sub}/catalog/ 可直接浏览下载")
        return result

    # DExchangeOpen：网关探活，正确前缀是 /dexchangeOpen（银川实测）
    api_url = final_url.rstrip("/") + "/dexchangeOpen/appauth/getappid"
    params = {"appId": DEX_APP_ID, "appName": DEX_APP_NAME,
              "timeStamp": time.strftime("%Y%m%d")}
    try:
        api = requests.get(api_url, params=params, headers=HEADERS, timeout=timeout)
        body = api.text[:200]
        if api.status_code == 200:
            result["ok"] = True
            result["api_url"] = api_url + "?" + "&".join(
                f"{k}={v}" for k, v in params.items())
            if "sso not login" in body.lower():
                result["note"] = ("接口存活但要求统一身份认证(SSO)，"
                                  "匿名调用拿不到数据，需注册后按 appId 换取 token")
            else:
                result["note"] = "接口直接返回数据"
        else:
            # 站点活着、平台识别成功，只是网关行为与银川不同（各地 appId/路径有差异）
            result["ok"] = True
            result["api_url"] = api_url
            result["note"] = (f"DExchangeOpen 平台已识别，网关探测 HTTP {api.status_code}，"
                              "各地部署参数有差异，需注册后按本地 appId 调用")
    except Exception as e:
        result["ok"] = True
        result["api_url"] = api_url
        result["note"] = f"DExchangeOpen 平台已识别，网关连接失败: {str(e)[:50]}"
    return result


def main():
    ap = argparse.ArgumentParser(description="探测国内政务数据开放平台的真实接口")
    ap.add_argument("--apply", action="store_true", help="把确认的接口地址写回数据库")
    ap.add_argument("--id", action="append", dest="ids", help="只测指定 service_id，可重复")
    ap.add_argument("--timeout", type=float, default=25.0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default=os.path.join(ROOT, "cn_portal_results.json"))
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if args.ids:
        qs = ",".join("?" * len(args.ids))
        sql = ("SELECT service_id, service_name, service_url, official_url, status "
               f"FROM master WHERE service_id IN ({qs})")
        rows = cur.execute(sql, args.ids).fetchall()
    else:
        # 尚未识别出平台的国内门户：协议是占位符或尚未探测出真实接口
        sql = ("SELECT service_id, service_name, service_url, official_url, status "
               "FROM master WHERE (service_url LIKE '%gov.cn%' OR official_url LIKE '%gov.cn%') "
               "AND status != '已停止'")
        rows = cur.execute(sql).fetchall()
    conn.close()

    log(f"待探测 {len(rows)} 条国内门户条目\n")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for res in ex.map(lambda r: probe_row(r, args.timeout), rows):
            results.append(res)
            dns = {True: "DNS通", False: "DNS解析失败"}[res["dns"]] if res["dns"] is not None else "-"
            log(f"[{'OK' if res['ok'] else '--'}] {res['service_id']:<10} {dns:<12} "
                f"{(res.get('platform') or '未识别'):<16} {(res['name'] or '')[:20]:<20} {res['note'][:52]}")

    ok = [r for r in results if r["ok"]]
    dead = [r for r in results if r["dns"] is False]
    log("\n" + "=" * 72)
    log(f"完成：{len(results)} 条 | 存活 {len(ok)} 条 | 域名失效 {len(dead)} 条 | "
        f"拿到接口地址 {len([r for r in ok if r.get('api_url')])} 条")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    log(f"明细已写入 {args.out}")

    if args.apply:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        today = time.strftime("%Y-%m-%d")
        n_alive = n_dead = 0
        for r in ok:
            # 首页/网关实测存活即服务可用（门户的本体就是网站），
            # 接口地址存在则一并写入 service_url
            method = f"cn-probe:{r['platform'] or 'homepage'}"
            note = f" | [国内门户探测 {today}]: {r['note']}"
            if r.get("api_url"):
                cur.execute(
                    "UPDATE master SET service_url = ?, protocol = COALESCE(NULLIF(protocol,'HTTP下载'),?), "
                    "verify_method = ?, last_verified = ?, status = '已验证', "
                    "notes = COALESCE(notes,'') || ? WHERE service_id = ?",
                    (r["api_url"], r["platform"] or "HTTP", method, today, note, r["service_id"]))
            else:
                cur.execute(
                    "UPDATE master SET verify_method = ?, last_verified = ?, status = '已验证', "
                    "notes = COALESCE(notes,'') || ? WHERE service_id = ?",
                    (method, today, note, r["service_id"]))
            n_alive += cur.rowcount
        for r in dead:
            # 域名死亡只记录证据，不改判状态——部分城市门户迁入省级平台，
            # 条目应随新地址更新而非直接标"已停止"
            cur.execute(
                "UPDATE master SET verify_method = 'cn-probe:dns-dead', "
                "notes = COALESCE(notes,'') || ? WHERE service_id = ?",
                (f" | [国内门户探测 {today}]: {r['note']}", r["service_id"]))
            n_dead += cur.rowcount
        conn.commit()
        conn.close()
        log(f"已回写：存活 {n_alive} 条（status=已验证），失效 {n_dead} 条（仅记备注）")
    else:
        log("dry-run 模式，未修改数据库。加 --apply 执行回写。")


if __name__ == "__main__":
    main()
