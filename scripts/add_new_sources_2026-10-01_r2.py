#!/usr/bin/env python3
"""一次性入库：2026-10-01 第二轮（网搜 + 实测）新增 2 条。

实测证据（2026-10-01）：
- SWOT 任务官网 https://swot.jpl.nasa.gov/ 返回 200（90534 字节）
- WorldCereal 门户 https://worldcereal.com/（含 /lander）返回 200（236KB 真实页面）
未收录（实测不通过/无公开数据）：
- Foursquare OS Places：公开桶仅剩 LICENSE/NOTICE，数据分发已移走，docs 页 404
- PO.DAAC SWOT 产品页：本机不可达（疑似链路），按铁律不以单次失败入库，写入 SWOT 条目备注
注意：本轮按用户要求不执行 git 提交。
"""
import sqlite3
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

TODAY = "2026-10-01"

NEW_ROWS = [
    {
        "service_id": "DS-1199",
        "service_name": "SWOT 地表水与海洋地形任务",
        "country": "美国", "region": "全球",
        "provider": "NASA/CNES JPL",
        "category": "遥感", "service_type": "数据门户",
        "protocol": "HTTP下载",
        "official_url": "https://swot.jpl.nasa.gov/",
        "service_url": "https://swot.jpl.nasa.gov/",
        "docs_url": "https://swot.jpl.nasa.gov/data/",
        "data_description": "全球湖泊/河流/水库水面高程与面积(KaRin 雷达干涉，宽幅120km)，海洋与陆地水循环研究的最新一代卫星；数据存档在 PO.DAAC，可经 NASA Earthdata Search 检索",
        "spatial_coverage": "全球", "temporal_coverage": "2023年7月至今",
        "crs": "EPSG:4326", "resolution": "约15-50m(水体高程)", "update_frequency": "21天重访周期",
        "format": "NetCDF;HDF5", "auth": "免费注册 Earthdata 账号", "api_key_required": "否",
        "registration_required": "是", "free": "是", "commercial_use": "是",
        "redistribution": "是", "attribution": "NASA/CNES SWOT",
        "need_no_reg": "否", "need_no_key": "是", "is_free": "是",
        "support_api": "是(Earthdata CMR 检索)", "support_spatial_query": "是",
        "support_temporal_query": "是", "support_batch": "否", "support_download": "是",
        "support_geojson": "否", "support_json": "是",
        "is_vector": "否", "is_raster": "是", "is_realtime": "否",
        "global_coverage": "是", "region_coverage": "否",
        "status": "已验证", "verify_method": "protocol-probe:weak", "last_verified": TODAY,
        "notes": "实测任务官网返回 200(2026-10-01)；PO.DAAC 产品页(podaac.jpl.nasa.gov)本机探测未通(疑似跨境链路)，取数可走 search.earthdata.nasa.gov(同日实测 200)",
    },
    {
        "service_id": "DS-1200",
        "service_name": "ESA WorldCereal 全球作物分类系统",
        "country": "国际组织", "region": "全球",
        "provider": "ESA / WorldCereal 项目",
        "category": "农业/农村经济", "service_type": "数据门户",
        "protocol": "HTTP下载",
        "official_url": "https://worldcereal.com/",
        "service_url": "https://worldcereal.com/lander",
        "docs_url": "https://esa-worldcereal.readthedocs.io/",
        "data_description": "Sentinel-1/2 驱动的全球动态作物制图(冬麦/春麦/玉米/灌溉识别等)，按 AEZ 分区季度更新，提供开放下载与在线浏览，另有 10m 级产品",
        "spatial_coverage": "全球(分农业生态区)", "temporal_coverage": "2020年起逐季",
        "crs": "EPSG:4326", "resolution": "10m", "update_frequency": "季度",
        "format": "GeoTIFF;COG", "auth": "无需认证(公开产品)", "api_key_required": "否",
        "registration_required": "否", "free": "是", "commercial_use": "是(CC-BY 4.0)",
        "redistribution": "是", "attribution": "ESA WorldCereal",
        "need_no_reg": "是", "need_no_key": "是", "is_free": "是",
        "support_api": "部分", "support_spatial_query": "否", "support_temporal_query": "否",
        "support_batch": "否", "support_download": "是", "support_geojson": "否", "support_json": "否",
        "is_vector": "否", "is_raster": "是", "is_realtime": "否",
        "global_coverage": "是", "region_coverage": "否",
        "status": "已验证", "verify_method": "protocol-probe:weak", "last_verified": TODAY,
        "notes": "实测门户与 /lander 返回 200 真实页面(2026-10-01)；在线地图 map.rythm.io 本机未通(疑似链路)，具体产品下载入口以门户内文档为准",
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
for r in cur.execute("select service_id,service_name,status,verify_method from master where service_id in ('DS-1199','DS-1200')"):
    print(" ", r)
conn.close()
