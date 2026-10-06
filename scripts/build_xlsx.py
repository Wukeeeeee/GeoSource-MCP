#!/usr/bin/env python3
"""从 gis_services.db 重建两个 Excel 交付物（改库后重跑，与 build_viewer.py 同理）。

- global_gis_services.xlsx：21 个 sheet。数据 sheet 全部重灌；说明README 里的统计段重写；
  数据组合 / 格式协议指南 为人工策划内容，原样保留。
- global_datasource_map.xlsx：16 个 sheet，同策略。

用法：python scripts/build_xlsx.py
"""
import io
import re
import sqlite3
import sys
from pathlib import Path

import openpyxl

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "gis_services.db"

MASTER_COLS = [r[1] for r in sqlite3.connect(DB).execute("PRAGMA table_info(master)")]


def fetch_all(conn, where="1=1", args=()):
    return conn.execute(
        f"SELECT {','.join(MASTER_COLS)} FROM master WHERE {where}", args).fetchall()


def refill(ws, rows, cols):
    ws.delete_rows(2, ws.max_row)
    for r in rows:
        ws.append([c for c in r])


def sheet_filter(conn, name):
    """每个数据 sheet 的取数规则，全部现查现写。"""
    q = lambda s, a=(): conn.execute(s, a).fetchall()
    if name == "总表Master":
        return fetch_all(conn)
    if name in ("WMS 服务",):
        return fetch_all(conn, "protocol LIKE 'OGC WMS%'")
    if name == "WFS 服务":
        return fetch_all(conn, "protocol LIKE 'OGC WFS%'")
    if name == "WMTS与瓦片":
        return fetch_all(conn, "protocol LIKE 'OGC WMTS%' OR service_type IN ('XYZ-Tile','PMTiles','MVT','Basemap','ArcGIS-Tile','瓦片服务')")
    if name == "ArcGIS REST":
        return fetch_all(conn, "protocol LIKE 'ArcGIS%' OR service_type LIKE 'ArcGIS-%'")
    if name == "OGC API":
        return fetch_all(conn, "protocol LIKE 'OGC API%'")
    if name == "STAC 数据":
        return fetch_all(conn, "protocol LIKE 'STAC%' OR service_type='STAC'")
    if name == "地理编码Gazetteer":
        return fetch_all(conn, "service_type IN ('Geocoding','ReverseGeocoding','Gazetteer') OR service_id LIKE 'GEOCODE-%'")
    if name == "路线交通API":
        return fetch_all(conn, "service_type IN ('Routing','Isochrone','RouteMatrix','PublicTransport','Railway','Flight','MarineAIS') OR service_id LIKE 'ROUTE-%'")
    if name == "3D GIS":
        return fetch_all(conn, "service_type IN ('3DTiles','I3S','CityGML') OR service_id LIKE 'T3D-%'")
    if name == "历史地图":
        return fetch_all(conn, "service_type='HistoricalMap' OR service_id LIKE 'HIST-%' OR service_id LIKE 'R2HIST-%' OR service_id LIKE 'R3HIST-%'")
    if name == "政府GIS":
        return fetch_all(conn, "category IN ('政府','开放政府数据','综合/政府开放数据','综合政务/公共数据','综合/自然资源')")
    if name == "大学科研GIS":
        return fetch_all(conn, "category IN ('大学科研','政府/大学科研','科研','科技/资源共享')")
    if name == "冷门服务":
        return fetch_all(conn,
            "category NOT IN ('政府','开放政府数据','综合/政府开放数据','综合政务/公共数据','综合/自然资源',"
            "'大学科研','政府/大学科研','科研','科技/资源共享')")
    if name == "API限制":
        return conn.execute(
            "SELECT service_id,service_name,provider,service_type,service_url,rate_limit,query_limit,"
            "download_limit,pagination,batch_query,caching_allowed,api_key_required FROM master").fetchall()
    if name == "License商业使用":
        return conn.execute(
            "SELECT service_id,service_name,provider,service_type,free,commercial_use,redistribution,"
            "commercial_ok,cache_ok,redistribute_ok,attribution,auth FROM master").fetchall()
    if name == "可直接接入清单":
        return conn.execute(
            "SELECT service_id,service_name,provider,country,region,service_type,protocol,service_url,format,"
            "free,commercial_use,support_spatial_query,support_download,api_key_required,registration_required "
            "FROM master WHERE status='已验证' AND api_key_required='否' AND registration_required='否' AND is_free='是'").fetchall()
    if name == "生态关系":
        return conn.execute("SELECT * FROM ecosystem").fetchall()
    if name == "总表":
        return fetch_all(conn)
    if name == "API数据源":
        return fetch_all(conn, "support_api LIKE '是%'")
    if name == "可批量下载":
        return fetch_all(conn, "support_download LIKE '是%' OR support_batch LIKE '是%'")
    if name == "免费数据源":
        return fetch_all(conn, "is_free='是'")
    if name == "GIS数据源":
        return fetch_all(conn, "protocol LIKE 'OGC%' OR protocol LIKE 'ArcGIS%' OR service_type IN ('WMS','WFS','WMTS','XYZ-Tile','STAC')")
    if name == "交通数据源":
        return fetch_all(conn, "category IN ('交通','公交','道路','铁路','地铁','航空','船舶') OR service_type IN ('Routing','PublicTransport','Railway','Flight','MarineAIS','Isochrone','RouteMatrix')")
    if name == "旅游数据源":
        return fetch_all(conn, "category IN ('旅游','POI','街景','文化遗产')")
    if name == "城市数据源":
        return fetch_all(conn, "category IN ('城市','住建/房地产/城市建设','人口','人口/社会经济','行政区划','社区')")
    if name == "卫星遥感数据源":
        return fetch_all(conn, "category LIKE '遥感%' OR protocol LIKE 'STAC%' OR service_type='STAC' OR category='土地覆盖'")
    if name == "历史数据源":
        return fetch_all(conn, "category='历史' OR service_type='HistoricalMap' OR service_id LIKE 'HIST-%'")
    if name == "科研数据源":
        return fetch_all(conn, "category IN ('科研','大学科研','政府/大学科研','科技/资源共享','生物/基因组学')")
    if name == "3D数据源":
        return fetch_all(conn, "service_type IN ('3DTiles','I3S','CityGML') OR service_id LIKE 'T3D-%'")
    if name == "冷门数据源":
        return fetch_all(conn,
            "category NOT IN ('交通','公交','道路','铁路','地铁','航空','船舶','旅游','POI','街景','文化遗产',"
            "'城市','住建/房地产/城市建设','人口','人口/社会经济','行政区划','社区','遥感','遥感/影像','土地覆盖','历史')")
    if name == "API限制库":
        return conn.execute(
            "SELECT service_id,service_name,auth,rate_limit,query_limit,pagination,batch_query,download_limit,"
            "attribution,commercial_use,caching_allowed,redistribution FROM master").fetchall()
    if name == "数据许可库":
        return conn.execute(
            "SELECT service_id,service_name,commercial_use,redistribution,format,free,api_key_required,notes "
            "FROM master").fetchall()
    return None  # 策划类 sheet，保留


MAP_GIS = {  # global_datasource_map 的列映射（源列 -> 输出列序）
    "总表": ["service_id", "service_name", "country", "category", "provider", "official_url",
             "service_url", "docs_url", "format", "free", "registration_required", "api_key_required"],
}

# global_datasource_map 16 个数据 sheet 的输出列（与旧表头一致）
MAP_COLS = ["service_id", "service_name", "country", "category", "provider", "official_url",
            "service_url", "docs_url", "format", "free", "registration_required",
            "api_key_required", "support_batch", "support_api"]


def main():
    conn = sqlite3.connect(DB)
    st = {
        "total": conn.execute("select count(*) from master").fetchone()[0],
        "verified": conn.execute("select count(*) from master where status='已验证'").fetchone()[0],
        "strong": conn.execute("select count(*) from master where verify_method like '%strong%'").fetchone()[0],
        "layers": conn.execute("select count(*) from layers").fetchone()[0],
        "countries": conn.execute("select count(distinct country) from master").fetchone()[0],
    }

    # ---------- global_gis_services.xlsx ----------
    p1 = ROOT / "global_gis_services.xlsx"
    wb = openpyxl.load_workbook(p1)
    for name in wb.sheetnames:
        rows = sheet_filter(conn, name)
        if rows is None:
            continue
        refill(wb[name], rows, None)
    ws = wb["说明README"]
    txt = ws["A1"].value or ""
    txt = re.sub(r"目录共[\d,]+条", f"目录共{st['total']:,}条", txt)
    txt = re.sub(r"已验证[\d,]+条", f"已验证{st['verified']:,}条", txt)
    txt = re.sub(r"其中[\d,]+条", f"其中{st['strong']:,}条", txt)
    txt = re.sub(r"图层[\d,]+行", f"图层{st['layers']:,}行", txt)
    txt = re.sub(r"\d{4}-\d{2}-\d{2}", "2026-10-07", txt)
    ws["A1"] = txt
    wb.save(p1)
    print(f"{p1.name} 已重建：{st}")

    # ---------- global_datasource_map.xlsx ----------
    p2 = ROOT / "global_datasource_map.xlsx"
    wb = openpyxl.load_workbook(p2)
    hdr = [c.value for c in wb["总表"][1]]
    # 旧表头 14 列，按列名对齐 master 字段
    col_map = {}
    alias = {"数据源ID": "service_id", "数据名称": "service_name", "国家/地区": "country",
             "类别标签": "category", "官方机构": "provider", "主页URL": "official_url",
             "API地址/文档": "service_url", "下载地址": "docs_url", "数据格式": "format",
             "是否免费": "free", "是否需注册": "registration_required", "是否需Key": "api_key_required",
             "可否批量下载": "support_batch", "可否程序化获取": "support_api"}
    for i, h in enumerate(hdr):
        if h in alias:
            col_map[i] = alias[h]
    for name in wb.sheetnames:
        if name == "API限制库":
            out = []
            for r in conn.execute(
                    "SELECT service_id,service_name,auth,rate_limit,query_limit,pagination,batch_query,"
                    "download_limit,attribution,commercial_use,caching_allowed,redistribution FROM master"):
                out.append(list(r))
            refill(wb[name], out, None)
            continue
        if name == "数据许可库":
            out = []
            for r in conn.execute(
                    "SELECT service_id,service_name,commercial_use,redistribution,format,free,"
                    "api_key_required,notes FROM master"):
                out.append(list(r))
            refill(wb[name], out, None)
            continue
        rows = sheet_filter(conn, name)
        if rows is None:
            continue
        idx = {c: i for i, c in enumerate(MASTER_COLS)}
        out = []
        for r in rows:
            out.append([r[idx[col_map[i]]] if i in col_map else None for i in range(len(hdr))])
        refill(wb[name], out, None)
    wb.save(p2)
    print(f"{p2.name} 已重建")
    conn.close()


if __name__ == "__main__":
    main()
