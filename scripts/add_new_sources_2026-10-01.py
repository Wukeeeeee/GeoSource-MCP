#!/usr/bin/env python3
"""一次性入库：2026-10-01 缺口对账 + 网搜后新收录的 3 条数据源（全部实测后才收）。

实测证据（2026-10-01）：
- S5P-PAL STAC /api/s5p-l2 返回真实 stac_version 1.0.0 Catalog JSON（含 conformsTo）
- CEMS On-Demand Mapping /activations 返回 200（激活列表页）
- CEMS EWDS global-flood 门户返回 200（取数经 cdsapi，需免费注册）
"""
import sqlite3
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

TODAY = "2026-10-01"

NEW_ROWS = [
    {
        "service_id": "STAC-0051",
        "service_name": "S5P-PAL Sentinel-5P 产品存档 STAC API",
        "country": "国际组织", "region": "全球",
        "provider": "ESA S5P-PAL (Sentinel-5P Product Algorithm Laboratory)",
        "category": "遥感", "service_type": "时空目录",
        "protocol": "STAC v1",
        "official_url": "https://data-portal.s5p-pal.com/",
        "service_url": "https://data-portal.s5p-pal.com/api/s5p-l2",
        "docs_url": "https://data-portal.s5p-pal.com/apidoc",
        "data_description": "Sentinel-5P L2/L3 大气成分产品(NO2/O3/CO/SO2/气溶胶等)的 STAC 1.0.0 目录；L2 目录 /api/s5p-l2，L3 再处理产品 /api/s5p-l3，支持 STAC search",
        "spatial_coverage": "全球", "temporal_coverage": "2018年4月至今",
        "crs": "EPSG:4326", "resolution": "星下点约3.5×7km", "update_frequency": "准实时(延迟约1-2天)",
        "format": "NetCDF;COG", "auth": "无需认证(公开存档)", "api_key_required": "否",
        "registration_required": "否", "free": "是", "commercial_use": "是(Copernicus许可)",
        "redistribution": "是", "attribution": "ESA Copernicus S5P-PAL",
        "need_no_reg": "是", "need_no_key": "是", "is_free": "是",
        "support_api": "是", "support_spatial_query": "是", "support_temporal_query": "是",
        "support_batch": "否", "support_download": "是", "support_geojson": "是", "support_json": "是",
        "is_vector": "否", "is_raster": "是", "is_realtime": "否",
        "global_coverage": "是", "region_coverage": "否",
        "status": "已验证", "verify_method": "protocol-probe:strong", "last_verified": TODAY,
        "notes": "实测 /api/s5p-l2 返回 stac_version 1.0.0 Catalog JSON 且含 conformsTo(2026-10-01)；目录名 s5p-l2/s5p-l3 由门户 HTML 引用确认",
    },
    {
        "service_id": "DS-1197",
        "service_name": "CEMS 应急制图按需服务门户(On-Demand Mapping)",
        "country": "国际组织", "region": "全球",
        "provider": "哥白尼应急管理服务(Copernicus EMS / DG ECHO)",
        "category": "灾害", "service_type": "数据门户",
        "protocol": "HTTP下载",
        "official_url": "https://mapping.emergency.copernicus.eu/",
        "service_url": "https://mapping.emergency.copernicus.eu/activations",
        "docs_url": "https://riskandrecovery.emergency.copernicus.eu/",
        "data_description": "全球灾害事件(洪水/火灾/地震/火山/冲突等)按需制图激活列表，每次激活提供 Rapid Mapping(交付数小时~数天内)与 Risk&Recovery 制图的矢量/栅格包下载",
        "spatial_coverage": "全球(按激活事件)", "temporal_coverage": "2012年4月至今",
        "crs": "EPSG:4326(产品多为UTM)", "resolution": "混合(遥感解译矢量+影响栅格)", "update_frequency": "事件驱动",
        "format": "Shapefile;GeoTIFF;PDF", "auth": "无需认证", "api_key_required": "否",
        "registration_required": "否", "free": "是", "commercial_use": "是(注明出处)",
        "redistribution": "是", "attribution": "Copernicus EMS",
        "need_no_reg": "是", "need_no_key": "是", "is_free": "是",
        "support_api": "部分(Risk&Recovery 提供OpenAPI规范)", "support_spatial_query": "否",
        "support_temporal_query": "否", "support_batch": "否", "support_download": "是",
        "support_geojson": "否", "support_json": "否",
        "is_vector": "是", "is_raster": "是", "is_realtime": "是",
        "global_coverage": "是", "region_coverage": "否",
        "status": "已验证", "verify_method": "protocol-probe:weak", "last_verified": TODAY,
        "notes": "实测 /activations 返回 200 激活列表页(2026-10-01)；主门户 emergency.copernicus.eu 已有独立条目 DS-0319，本条是其按需制图子服务",
    },
    {
        "service_id": "DS-1198",
        "service_name": "CEMS 洪水预警数据店(EWDS / GloFAS)",
        "country": "国际组织", "region": "全球",
        "provider": "哥白尼应急管理服务 / ECMWF",
        "category": "洪水", "service_type": "数据API",
        "protocol": "REST/JSON",
        "official_url": "https://global-flood.emergency.copernicus.eu/",
        "service_url": "https://global-flood.emergency.copernicus.eu/",
        "docs_url": "https://confluence.ecmwf.int/display/CEMS",
        "data_description": "全球洪水感知系统(GloFAS)与欧洲洪水感知系统(EFAS)历史再分析/预报/实时数据，经 cdsapi(含 2025-09 新版 v0.7.7)取数；径流/土壤湿度/洪水风险指标等",
        "spatial_coverage": "全球(GloFAS)/欧洲(EFAS)", "temporal_coverage": "1984至今(再分析)+滚动预报",
        "crs": "EPSG:4326", "resolution": "约5km(GloFas30)", "update_frequency": "每日",
        "format": "NetCDF;GRIB", "auth": "免费注册 ECMWF 账号+API Key", "api_key_required": "是",
        "registration_required": "是", "free": "是", "commercial_use": "是(Copernicus许可)",
        "redistribution": "是", "attribution": "Copernicus EMS/ECMWF",
        "need_no_reg": "否", "need_no_key": "否", "is_free": "是",
        "support_api": "是", "support_spatial_query": "是", "support_temporal_query": "是",
        "support_batch": "是", "support_download": "是", "support_geojson": "否", "support_json": "否",
        "is_vector": "否", "is_raster": "是", "is_realtime": "是",
        "global_coverage": "是", "region_coverage": "是",
        "status": "已验证", "verify_method": "protocol-probe:weak", "last_verified": TODAY,
        "notes": "实测门户返回 200(2026-10-01)；批量取数需注册 ECMWF 账号拿 cdsapi key，未注册匿名拿不到数据",
    },
]

conn = sqlite3.connect("gis_services.db")
cur = conn.cursor()
cols = [r[1] for r in cur.execute("PRAGMA table_info(master)")]
for row in NEW_ROWS:
    values = {c: None for c in cols}
    for k, v in row.items():
        if k in cols:
            values[k] = v
    values.setdefault("caching_allowed", "未知")
    values.setdefault("rate_limit", "未知")
    values.setdefault("query_limit", "未知")
    values.setdefault("download_limit", "未知")
    values.setdefault("pagination", "未知")
    values.setdefault("batch_query", "未知")
    placeholders = ",".join("?" for _ in cols)
    cur.execute(f"INSERT INTO master ({','.join(cols)}) VALUES ({placeholders})",
                [values[c] for c in cols])
conn.commit()
n = cur.execute("select count(*) from master").fetchone()[0]
print(f"插入 {len(NEW_ROWS)} 条，master 总数 -> {n}")
for r in cur.execute("select service_id,service_name,status,verify_method from master where service_id in ('STAC-0051','DS-1197','DS-1198')"):
    print(" ", r)
conn.close()
