#!/usr/bin/env python3
"""
GeoSource MCP Server
--------------------
A Model Context Protocol (MCP) server providing structured access to a curated
database of 2,204 global GIS spatial services, layers, and open geospatial endpoints.
"""

import os
import sys
import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from mcp.server.fastmcp import FastMCP

# Ensure stdout/stderr handles UTF-8 properly on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Initialize FastMCP Server
mcp = FastMCP(
    "geosource-mcp",
    instructions=(
        "GeoSource provides structured access to 2,204 global GIS services "
        "(WMS, WFS, WMTS, XYZ Tiles, ArcGIS REST, STAC APIs) and 1,561 spatial layers. "
        "Use these tools to discover, search, filter, and inspect verified geospatial endpoints."
    )
)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gis_services.db")

VALID_STATUSES = {"已验证", "未验证", "已停止", "历史服务"}


def get_db_connection(read_only: bool = True) -> sqlite3.Connection:
    """
    Create an SQLite connection with dictionary-like row access.
    
    Args:
        read_only: If True, opens SQLite in URI read-only mode to prevent accidental writes.
    """
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found at {DB_PATH}")

    if read_only:
        uri = f"file:{os.path.abspath(DB_PATH).replace(os.sep, '/')}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=10.0)
    else:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)

    conn.row_factory = sqlite3.Row
    return conn


@mcp.tool()
def search_gis_services(
    keyword: Optional[str] = None,
    country: Optional[str] = None,
    protocol: Optional[str] = None,
    category: Optional[str] = None,
    is_free: Optional[bool] = None,
    need_no_key: Optional[bool] = None,
    status: Optional[str] = None,
    limit: int = 15
) -> str:
    """
    Search global GIS spatial services by keyword, country, protocol, category, and access constraints.

    Args:
        keyword: Keyword matching against service name, provider, description, notes, or category (e.g. 'DEM', 'elevation', 'satellite', 'weather', '高程', '交通')
        country: Filter by country or region (e.g. '中国', '美国', 'Global', '德国', '日本', '全球')
        protocol: Filter by GIS protocol (e.g. 'WMS', 'WFS', 'XYZ', 'REST', 'CKAN', 'STAC')
        category: Filter by data category (e.g. '高程/地形', '交通', '气象', '人口', '开放政府数据', '土地利用', '水利/海洋')
        is_free: If True, filters for free services; If False, filters for non-free services
        need_no_key: If True, filters for services not requiring an API Key; If False, filters for services requiring a Key
        status: Filter by status ('已验证', '未验证', '已停止', '历史服务'); If omitted, returns all with verified first
        limit: Maximum results to return (default: 15, max: 50)
    """
    limit = min(max(1, limit), 50)
    conn = get_db_connection(read_only=True)
    cur = conn.cursor()

    conditions = []
    params = []

    if keyword:
        kw = f"%{keyword.strip()}%"
        conditions.append(
            "(service_name LIKE ? OR data_description LIKE ? OR provider LIKE ? OR notes LIKE ? OR category LIKE ?)"
        )
        params.extend([kw, kw, kw, kw, kw])

    if country:
        conditions.append("(country LIKE ? OR region LIKE ?)")
        params.extend([f"%{country.strip()}%", f"%{country.strip()}%"])

    if protocol:
        conditions.append("protocol LIKE ?")
        params.append(f"%{protocol.strip()}%")

    if category:
        conditions.append("category LIKE ?")
        params.append(f"%{category.strip()}%")

    if is_free is not None:
        if is_free:
            conditions.append("(free = '是' OR is_free = '是')")
        else:
            conditions.append("(free = '否' OR is_free = '否')")

    if need_no_key is not None:
        if need_no_key:
            conditions.append("(need_no_key = '是' OR api_key_required = '否')")
        else:
            conditions.append("(need_no_key = '否' OR api_key_required = '是')")

    if status:
        conditions.append("status = ?")
        params.append(status.strip())

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"""
        SELECT 
            service_id, service_name, provider, country, category, protocol,
            service_url, official_url, is_free, need_no_key, format,
            spatial_coverage, status, data_description
        FROM master
        {where_clause}
        ORDER BY 
            CASE WHEN status = '已验证' THEN 1 WHEN status = '未验证' THEN 2 ELSE 3 END,
            service_id
        LIMIT ?
    """
    params.append(limit)

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    results = [dict(r) for r in rows]
    return json.dumps({
        "total_returned": len(results),
        "results": results
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def get_service_detail(service_id: str) -> str:
    """
    Get full metadata (50+ fields) and child layers for a specific GIS service by its service_id (e.g. 'WMS-0001', 'DS-0001').
    Case-insensitive matching is supported.

    Args:
        service_id: The unique ID of the service (e.g. 'WMS-0001', 'DS-0002')
    """
    cleaned_id = service_id.strip()
    conn = get_db_connection(read_only=True)
    cur = conn.cursor()

    cur.execute("SELECT * FROM master WHERE service_id = ? COLLATE NOCASE", (cleaned_id,))
    service_row = cur.fetchone()

    if not service_row:
        conn.close()
        return json.dumps({"error": f"Service with ID '{service_id}' not found."}, ensure_ascii=False)

    service_data = dict(service_row)
    canonical_id = service_data.get("service_id", cleaned_id)

    cur.execute(
        "SELECT layer_idx, layer_name FROM layers WHERE service_id = ? ORDER BY layer_idx",
        (canonical_id,)
    )
    layer_rows = cur.fetchall()
    conn.close()

    service_data["layers"] = [dict(lr) for lr in layer_rows]
    return json.dumps(service_data, ensure_ascii=False, indent=2)


@mcp.tool()
def list_categories_and_stats() -> str:
    """
    Get an overview of database statistics, including total services, status breakdown (verified, unverified, stopped),
    top categories, protocols, and countries.
    """
    conn = get_db_connection(read_only=True)
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM master")
    total_services = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM layers")
    total_layers = cur.fetchone()[0]

    cur.execute("SELECT status, count(*) as count FROM master GROUP BY status")
    status_distribution = {row["status"]: row["count"] for row in cur.fetchall()}

    cur.execute("SELECT category, count(*) as count FROM master WHERE category != '' GROUP BY category ORDER BY count DESC LIMIT 15")
    top_categories = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT protocol, count(*) as count FROM master WHERE protocol != '' GROUP BY protocol ORDER BY count DESC LIMIT 10")
    top_protocols = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT country, count(*) as count FROM master WHERE country != '' GROUP BY country ORDER BY count DESC LIMIT 15")
    top_countries = [dict(r) for r in cur.fetchall()]

    conn.close()

    return json.dumps({
        "total_services": total_services,
        "total_layers": total_layers,
        "status_distribution": status_distribution,
        "top_categories": top_categories,
        "top_protocols": top_protocols,
        "top_countries": top_countries
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def query_gis_sql(query: str) -> str:
    """
    Execute a safe, read-only SQL SELECT query directly against the SQLite database for custom queries.
    Tables available: 'master', 'layers', 'ecosystem'.
    Results are capped at 100 rows.

    Args:
        query: SQL SELECT query string (e.g. "SELECT service_name, service_url FROM master WHERE protocol LIKE '%XYZ%' LIMIT 5")
    """
    clean_query = query.strip()
    upper_query = clean_query.upper()

    # Basic safety checks: only allow single SELECT / WITH statements
    if not (upper_query.startswith("SELECT") or upper_query.startswith("WITH")):
        return json.dumps({"error": "Only SELECT or WITH read-only queries are allowed."}, ensure_ascii=False)

    # Disallow dangerous statements or multiple statements
    forbidden_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "ATTACH", "DETACH", "REPLACE", "PRAGMA"]
    for kw in forbidden_keywords:
        # Check if keyword exists as a standalone token
        tokens = upper_query.split()
        if kw in tokens:
            return json.dumps({"error": f"Operation '{kw}' is not permitted in read-only queries."}, ensure_ascii=False)

    if ";" in clean_query.rstrip(";"):
        return json.dumps({"error": "Multiple SQL statements are not permitted."}, ensure_ascii=False)

    conn = get_db_connection(read_only=True)
    cur = conn.cursor()
    try:
        cur.execute(clean_query)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        rows = cur.fetchmany(100)
        results = [dict(zip(columns, r)) for r in rows]
        return json.dumps({
            "row_count": len(results),
            "capped_at_100": len(results) == 100,
            "rows": results
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    finally:
        conn.close()


@mcp.tool()
def update_service_status(
    service_id: str,
    new_url: Optional[str] = None,
    status: Optional[str] = None,
    notes: Optional[str] = None
) -> str:
    """
    Update a service's URL, availability status, or notes.
    Valid statuses: '已验证', '未验证', '已停止', '历史服务'.
    Automatically updates the last_verified timestamp. Case-insensitive service_id matching is supported.

    Args:
        service_id: The service ID to update (e.g. 'DS-0001')
        new_url: The new valid service URL if the previous one changed
        status: The verification status ('已验证', '未验证', '已停止', '历史服务')
        notes: Additional notes or remarks to append
    """
    cleaned_id = service_id.strip()

    if status and status.strip() not in VALID_STATUSES:
        return json.dumps({
            "error": f"Invalid status '{status}'. Must be one of: {sorted(list(VALID_STATUSES))}"
        }, ensure_ascii=False)

    conn = get_db_connection(read_only=False)
    cur = conn.cursor()

    cur.execute("SELECT service_id, service_url, status, notes FROM master WHERE service_id = ? COLLATE NOCASE", (cleaned_id,))
    existing = cur.fetchone()
    if not existing:
        conn.close()
        return json.dumps({"error": f"Service with ID '{service_id}' not found."}, ensure_ascii=False)

    canonical_id = existing["service_id"]
    updates = []
    params = []

    if new_url:
        updates.append("service_url = ?")
        params.append(new_url.strip())

    if status:
        updates.append("status = ?")
        params.append(status.strip())

    if notes:
        existing_notes = existing["notes"] or ""
        combined_notes = f"{existing_notes} | [Update]: {notes.strip()}" if existing_notes else notes.strip()
        updates.append("notes = ?")
        params.append(combined_notes)

    # Automatically set last_verified date
    today_str = datetime.now().strftime("%Y-%m-%d")
    updates.append("last_verified = ?")
    params.append(today_str)

    params.append(canonical_id)
    sql = f"UPDATE master SET {', '.join(updates)} WHERE service_id = ?"
    cur.execute(sql, params)
    conn.commit()
    conn.close()

    return json.dumps({
        "success": True,
        "service_id": canonical_id,
        "updated_fields": updates,
        "last_verified": today_str
    }, ensure_ascii=False)


# 站点自定义 JSON 包装层（meta/api version 之类）不等于 Socrata catalog
SOCRATA_MARKERS = ("resultsSetSize", "resourceColumnName", "metadata", "dataset", "Socrata")

PROBE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GeoSource-Probe/1.0",
    "Accept": "application/json",
}


def _http_get(url: str, timeout: float):
    """返回 (状态码, 响应体前 400 字符)；连接失败时状态码为 None。"""
    import requests

    try:
        resp = requests.get(url, headers=PROBE_HEADERS, timeout=timeout, allow_redirects=True)
        return resp.status_code, resp.text[:400]
    except Exception as e:
        return None, str(e)[:120]


def _probe_ckan(root: str, timeout: float):
    url = root + "/api/3/action/status_show"
    code, body = _http_get(url, timeout)
    if code == 200 and '"ckan_version"' in body:
        return "CKAN", url
    return None, None


def _probe_dkan(root: str, timeout: float):
    for path in ("/api/3/action/package_search?rows=1", "/api/3/action/status_show"):
        url = root + path
        code, body = _http_get(url, timeout)
        if code == 200 and '"result"' in body and ('"success": true' in body or '"results"' in body):
            return "DKAN", url
    return None, None


def _probe_agol(root: str, timeout: float):
    for path in ("/api/v3/datasets?page%5Bsize%5D=1", "/sharing/rest/portals/self?f=json"):
        url = root + path
        code, body = _http_get(url, timeout)
        if code == 200 and body.lstrip().startswith("{") and any(
            k in body for k in ('"data"', '"urlKey"', '"id"')
        ):
            return "ArcGIS Hub", url
    return None, None


def _probe_socrata(root: str, timeout: float):
    url = root + "/api/catalog/v1"
    code, body = _http_get(url, timeout)
    if code != 200:
        return None, None
    stripped = body.lstrip()
    # 通用 JSON 404 包装（{".../api/...": 404}）不是 Socrata
    if stripped.startswith("{") and "/api/" in stripped[:60]:
        return None, None
    low = stripped[:200].lower()
    if '"success": false' in low.replace("'", '"') or '"msg"' in low and "not allowed" in low:
        return None, None
    if stripped.startswith("["):
        return "Socrata", url
    if stripped.startswith("{") and any(m in body for m in SOCRATA_MARKERS) and "success" not in low[:40]:
        return "Socrata", url
    return None, None


PORTAL_PROBES = (
    ("CKAN", _probe_ckan),
    ("DKAN", _probe_dkan),
    ("ArcGIS Hub", _probe_agol),
    ("Socrata", _probe_socrata),
)


def _portal_root(url: Optional[str]) -> Optional[str]:
    if not url or not url.startswith("http"):
        return None
    u = url.strip()
    for suffix in ("/pages/api", "/portal/", "/home"):
        if u.endswith(suffix):
            u = u[: -len(suffix)]
    return u.rstrip("/") or None


@mcp.tool()
def probe_service_api(
    service_id: Optional[str] = None,
    url: Optional[str] = None,
    timeout: float = 10.0
) -> str:
    """
    Live-probe a cataloged service to confirm its endpoint is reachable right now, and auto-detect the
    underlying open-data platform (CKAN / DKAN / ArcGIS Hub / Socrata) to return the standard JSON API entry.

    Use this when a service in the catalog is marked 未验证, or before recommending a portal to a user, to
    avoid handing out a dead link. Either pass a service_id from the catalog or a raw url.

    Args:
        service_id: Catalog ID to probe (e.g. 'DS-0026'); its service_url and official_url are both tried
        url: A raw portal root URL to probe directly, if you don't have a catalog ID
        timeout: Per-request timeout in seconds (default: 10, max: 30)
    """
    timeout = min(max(2.0, float(timeout)), 30.0)
    conn = get_db_connection(read_only=True)
    cur = conn.cursor()

    record = None
    if service_id:
        cur.execute(
            "SELECT service_id, service_name, service_url, official_url, status FROM master "
            "WHERE service_id = ? COLLATE NOCASE",
            (service_id.strip(),),
        )
        record = cur.fetchone()
    conn.close()

    if service_id and not record and not url:
        return json.dumps({"error": f"Service with ID '{service_id}' not found."}, ensure_ascii=False)

    roots = []
    if record:
        for candidate in (record["service_url"], record["official_url"]):
            r = _portal_root(candidate)
            if r and r not in roots:
                roots.append(r)
    if url:
        r = _portal_root(url)
        if r and r not in roots:
            roots.append(r)

    if not roots:
        return json.dumps({
            "reachable": False,
            "error": "没有可用于探测的 http(s) 地址",
            "service_id": service_id,
        }, ensure_ascii=False)

    attempts = []
    for root in roots:
        for platform_name, probe_fn in PORTAL_PROBES:
            hit, api_url = probe_fn(root, timeout)
            attempts.append({"root": root, "platform": platform_name, "hit": bool(hit)})
            if hit:
                return json.dumps({
                    "reachable": True,
                    "service_id": record["service_id"] if record else None,
                    "service_name": record["service_name"] if record else None,
                    "db_status": record["status"] if record else None,
                    "detected_platform": platform_name,
                    "api_url": api_url,
                    "note": "service_url 与探测结果不一致，可用 update_service_status 回写",
                }, ensure_ascii=False)

    return json.dumps({
        "reachable": False,
        "service_id": record["service_id"] if record else None,
        "service_name": record["service_name"] if record else None,
        "db_status": record["status"] if record else None,
        "tried_roots": roots,
        "error": "未匹配到 CKAN/DKAN/ArcGIS Hub/Socrata 标准接口（站点可能不可达、需注册或为非标准平台）",
    }, ensure_ascii=False)


def main():
    """Main entrypoint for CLI execution and packaging."""
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("[TEST] Running self-test on GeoSource MCP tools...")
        stats_raw = list_categories_and_stats()
        stats = json.loads(stats_raw)
        print(f"[TEST] Total services: {stats.get('total_services')}")
        print(f"[TEST] Status breakdown: {stats.get('status_distribution')}")

        # Test case-insensitive search
        sample_search = search_gis_services(keyword="elevation", limit=2)
        assert json.loads(sample_search)["total_returned"] > 0, "Keyword search failed"

        # Test case-insensitive detail fetch
        detail_lower = get_service_detail("ds-0001")
        assert "error" not in json.loads(detail_lower), "Case-insensitive detail fetch failed"

        # Probe tool must degrade gracefully offline (no network required for --test to pass)
        probe = json.loads(probe_service_api(service_id="NON_EXISTENT_ID_9999"))
        assert "error" in probe, "probe_service_api should report unknown IDs"

        print("[TEST] All tests passed! Ready for MCP clients.")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
