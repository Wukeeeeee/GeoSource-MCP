#!/usr/bin/env python3
"""一次性入库：2026-09-30 缺口对账后新收录的 6 条数据源（全部实测后才收）。"""
import sqlite3
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

TODAY = "2026-09-30"

# 字段顺序与 master 表一致；None 之外的字段尽量按既有条目风格填写
NEW_ROWS = [
    {
        "service_id": "DS-1191",
        "service_name": "GEBCO 全球海底测深网格 WMS",
        "country": "国际组织", "region": "全球",
        "provider": "GEBCO/IHO-UNESCO IOC 海底地形图工作组",
        "category": "海洋", "service_type": "地图服务",
        "protocol": "OGC WMS 1.3.0",
        "official_url": "https://www.gebco.net/data-products/gridded-bathymetry-data",
        "service_url": "https://wms.gebco.net/mapserv?request=GetCapabilities&service=WMS",
        "docs_url": "https://www.gebco.net/data-and-products/online-gis",
        "data_description": "GEBCO 2024 全球整合海底地形网格(15弧秒)在线 WMS 服务，可按图层渲染测深/地形；网格数据可从下载门户按区域获取",
        "spatial_coverage": "全球", "temporal_coverage": "静态(年度更新版次)",
        "crs": "EPSG:4326", "resolution": "15弧秒网格", "update_frequency": "年度",
        "format": "PNG;GeoTIFF", "auth": "无需认证", "api_key_required": "否",
        "registration_required": "否", "free": "是", "commercial_use": "是(注明出处)",
        "redistribution": "是", "attribution": "GEBCO Compilation Group",
        "need_no_reg": "是", "need_no_key": "是", "is_free": "是",
        "support_api": "是", "support_spatial_query": "否", "support_temporal_query": "否",
        "support_batch": "否", "support_download": "是", "support_geojson": "否", "support_json": "否",
        "is_vector": "否", "is_raster": "是", "is_realtime": "否",
        "global_coverage": "是", "region_coverage": "否",
        "status": "已验证", "verify_method": "protocol-probe:strong", "last_verified": TODAY,
        "notes": "实测 WMS GetCapabilities 返回标准能力文档(2026-09-30)；下载门户实测 200",
    },
    {
        "service_id": "DS-1192",
        "service_name": "AWS Terrain Tiles 全球地形瓦片(Terrarium)",
        "country": "美国", "region": "全球",
        "provider": "AWS Open Data (Mapzen 开源地形瓦片)",
        "category": "DEM", "service_type": "瓦片服务",
        "protocol": "XYZ",
        "official_url": "https://registry.opendata.aws/terrain-tiles/",
        "service_url": "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png",
        "docs_url": "https://github.com/tilezen/joerd/blob/master/docs/data-sources.md",
        "data_description": "全球高程瓦片(Terrarium 编码：高程 = R*256+G+B-32768)，聚合 SRTM/GMTED/ETOPO1 等源，zoom 0-15；另有 normal/quantized-mesh 编码层",
        "spatial_coverage": "全球", "temporal_coverage": "静态",
        "crs": "EPSG:3857(Web墨卡托)", "resolution": "约30m(依 zoom)", "update_frequency": "静态",
        "format": "PNG(Terrarium编码)", "auth": "无需认证", "api_key_required": "否",
        "registration_required": "否", "free": "是", "commercial_use": "是",
        "redistribution": "是", "attribution": "Mapzen/AWS Open Data",
        "need_no_reg": "是", "need_no_key": "是", "is_free": "是",
        "support_api": "是", "support_spatial_query": "否", "support_temporal_query": "否",
        "support_batch": "否", "support_download": "是", "support_geojson": "否", "support_json": "否",
        "is_vector": "否", "is_raster": "是", "is_realtime": "否",
        "global_coverage": "是", "region_coverage": "否",
        "status": "已验证", "verify_method": "protocol-probe:strong", "last_verified": TODAY,
        "notes": "实测请求 terrarium/1/0/0.png 返回 200 image/png 真实瓦片(2026-09-30)；免 Key 直连",
    },
    {
        "service_id": "DS-1193",
        "service_name": "NASA POWER 气象与气候 API",
        "country": "美国", "region": "全球",
        "provider": "NASA Langley Research Center",
        "category": "气象", "service_type": "数据API",
        "protocol": "REST/JSON",
        "official_url": "https://power.larc.nasa.gov/",
        "service_url": "https://power.larc.nasa.gov/api/temporal/climatology/point",
        "docs_url": "https://power.larc.nasa.gov/docs/services/api/",
        "data_description": "气象/太阳能/可持续建筑三类参数，支持 point/regional 查询与日值/月值/气候态时间尺度；农业社区(AG)参数含 T2M/降水/辐射等数百项，免 Key",
        "spatial_coverage": "全球", "temporal_coverage": "1981至今",
        "crs": "EPSG:4326", "resolution": "0.5°×0.625°(MERRA-2)；太阳能约1°", "update_frequency": "日更(延迟数天)",
        "format": "JSON;CSV;NETCDF", "auth": "无需认证", "api_key_required": "否",
        "registration_required": "否", "free": "是", "commercial_use": "是",
        "redistribution": "是", "attribution": "NASA POWER",
        "need_no_reg": "是", "need_no_key": "是", "is_free": "是",
        "support_api": "是", "support_spatial_query": "是", "support_temporal_query": "是",
        "support_batch": "是(regional)", "support_download": "是", "support_geojson": "否", "support_json": "是",
        "is_vector": "否", "is_raster": "否", "is_realtime": "否",
        "global_coverage": "是", "region_coverage": "否",
        "status": "已验证", "verify_method": "protocol-probe:strong", "last_verified": TODAY,
        "notes": "实测 point 气候态查询返回 200 JSON(2026-09-30)；免 Key 直连",
    },
    {
        "service_id": "DS-1194",
        "service_name": "GADM 全球行政区划边界",
        "country": "国际组织", "region": "全球",
        "provider": "GADM 项目(University of California, Davis)",
        "category": "行政区划", "service_type": "数据下载",
        "protocol": "HTTP下载",
        "official_url": "https://gadm.org/",
        "service_url": "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_CHN_0.json.zip",
        "docs_url": "https://gadm.org/license.html",
        "data_description": "全球各国 0-3 级行政边界(GADM 4.1)，按国家打包下载，提供 Shapefile/GeoPackage/GeoJSON/KML；命名规则 gadm41_{ISO}_{LVL}.json.zip",
        "spatial_coverage": "全球(分国家)", "temporal_coverage": "静态(版本更新)",
        "crs": "EPSG:4326", "resolution": "0-3级行政", "update_frequency": "不定期",
        "format": "Shapefile;GeoPackage;GeoJSON;KML", "auth": "无需认证", "api_key_required": "否",
        "registration_required": "否", "free": "是", "commercial_use": "否(学术/个人免费，商用需授权)",
        "redistribution": "否", "attribution": "GADM 项目",
        "need_no_reg": "是", "need_no_key": "是", "is_free": "是",
        "support_api": "否", "support_spatial_query": "否", "support_temporal_query": "否",
        "support_batch": "否", "support_download": "是", "support_geojson": "是", "support_json": "否",
        "is_vector": "是", "is_raster": "否", "is_realtime": "否",
        "global_coverage": "是", "region_coverage": "否",
        "status": "已验证", "verify_method": "protocol-probe:strong", "last_verified": TODAY,
        "notes": "实测 gadm41_CHN_0.json.zip 返回 200 zip(335KB)(2026-09-30)；注意边界仅限学术用途且不含用户主张",
    },
    {
        "service_id": "DS-1195",
        "service_name": "腾讯位置服务 WebService API",
        "country": "中国", "region": "亚洲",
        "provider": "腾讯",
        "category": "POI", "service_type": "数据API",
        "protocol": "HTTP/REST",
        "official_url": "https://lbs.qq.com/",
        "service_url": "https://apis.map.qq.com/ws/place/v1/search",
        "docs_url": "https://lbs.qq.com/service/webService/webServiceGuide/webServiceGuide",
        "data_description": "地点搜索/关键词输入提示/逆地理编码/路线规划/静态地图等 WebService API；个人开发者认证后免费配额(部分接口日万次级)，需申请 Key",
        "spatial_coverage": "国家级", "temporal_coverage": "实时",
        "crs": "GCJ-02", "resolution": "POI级", "update_frequency": "实时",
        "format": "JSON", "auth": "API Key(SN签名可选)", "api_key_required": "是",
        "registration_required": "是", "free": "是", "commercial_use": "需企业认证",
        "redistribution": "否",
        "need_no_reg": "否", "need_no_key": "否", "is_free": "是",
        "support_api": "是", "support_spatial_query": "是", "support_temporal_query": "否",
        "support_batch": "否", "support_download": "否", "support_geojson": "否", "support_json": "是",
        "is_vector": "是", "is_raster": "否", "is_realtime": "是",
        "global_coverage": "否", "region_coverage": "是",
        "status": "已验证", "verify_method": "protocol-probe:weak", "last_verified": TODAY,
        "notes": "门户实测 200(2026-09-30)；API 需 Key，取数须配额内调用，坐标系 GCJ-02 注意与 WGS84 转换",
    },
    {
        "service_id": "DS-1196",
        "service_name": "Esri Living Atlas 专题内容门户",
        "country": "美国", "region": "全球",
        "provider": "Esri",
        "category": "综合/自然资源", "service_type": "数据门户",
        "protocol": "ArcGIS REST",
        "official_url": "https://livingatlas.arcgis.com/",
        "service_url": "https://livingatlas.arcgis.com/en/",
        "docs_url": "https://developers.arcgis.com/documentation/mapping-apis-and-services/search/",
        "data_description": "Esri 官方策展的全球专题图层目录(影像/人口/气候/边界/实时 sensor 等数千图层)，多数图层可经 ArcGIS Online REST 免费调用",
        "spatial_coverage": "全球", "temporal_coverage": "混合",
        "crs": "EPSG:3857/4326", "resolution": "混合", "update_frequency": "持续",
        "format": "ArcGIS REST;影像;矢量", "auth": "部分图层需 AGOL 账号", "api_key_required": "否",
        "registration_required": "部分", "free": "是", "commercial_use": "未知",
        "need_no_reg": "未知", "need_no_key": "是", "is_free": "是",
        "support_api": "是", "support_spatial_query": "是", "support_temporal_query": "是",
        "support_batch": "未知", "support_download": "部分", "support_geojson": "是", "support_json": "是",
        "is_vector": "是", "is_raster": "是", "is_realtime": "是",
        "global_coverage": "是", "region_coverage": "否",
        "status": "未验证", "verify_method": "protocol-probe:unreachable", "last_verified": TODAY,
        "notes": "本机网络不可达(2026-09-30，疑似跨境链路)，按单次失败不改判原则收录为未验证，待复测；底层 services.arcgis.com 实测可达",
    },
]

FLAG_FIELDS = [
    "commercial_use", "redistribution", "rate_limit", "query_limit", "download_limit",
    "pagination", "batch_query", "caching_allowed", "attribution",
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
    cur.execute(
        f"INSERT INTO master ({','.join(cols)}) VALUES ({placeholders})",
        [values[c] for c in cols])
conn.commit()
n = cur.execute("select count(*) from master").fetchone()[0]
print(f"插入 {len(NEW_ROWS)} 条，master 总数 -> {n}")
for r in cur.execute("select service_id,service_name,status,verify_method from master where service_id like 'DS-119%'"):
    print(" ", r)
conn.close()
