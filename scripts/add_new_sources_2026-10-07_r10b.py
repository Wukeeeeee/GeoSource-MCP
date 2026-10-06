#!/usr/bin/env python3
"""一次性入库：2026-10-07 第十轮追加批次（awesome-erddap 登记册）新增 23 条。

登记册：github.com/IrishMarineInstitute/awesome-erddap，45 台中 32 台未收录，
实测 21 台 search API 返回规范 CSV 头(strong) + 1 台页面 200(weak)；
10 台 404/502/超时不收（apdrc、axiom、incois、bco-dmo、iode、psmfc、ioos.github、
ooi、streamlit 示例、oregonstate）。
ERDDAP 判据：/erddap/search/index.csv?page=1&itemsPerPage=3&searchFor=... 返回
"griddap,Subset,tabledap,..." CSV 头行。
"""
import json
import sqlite3
import sys
from urllib.parse import urlsplit

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

TODAY = "2026-10-07"

META = {
    "http://cwcgom.aoml.noaa.gov/erddap": ("NOAA AOML（大西洋海洋气象实验室）", "美国", "北美", "NOAA AOML", "美国东南/墨西哥湾/加勒比"),
    "http://dap.onc.uvic.ca/erddap": ("Ocean Networks Canada（ONC）", "加拿大", "北美", "Ocean Networks Canada", "东北太平洋/加拿大沿岸"),
    "http://erddap.oceantrack.org/erddap": ("Ocean Tracking Network（OTN）", "加拿大", "北美", "Ocean Tracking Network", "全球动物追踪网络"),
    "http://erddap.secoora.org/erddap": ("SECOORA（美国东南海洋观测区）", "美国", "北美", "SECOORA", "美国东南沿岸"),
    "http://osmc.noaa.gov/erddap": ("NOAA OSMC（观测系统监测中心）", "美国", "北美", "NOAA", "全球海洋观测元数据"),
    "http://sccoos.org/erddap": ("SCCOOS（南加州海岸海洋观测系统）", "美国", "北美", "SCCOOS", "南加州沿岸"),
    "http://tds.marine.rutgers.edu/erddap": ("Rutgers 大学海洋观测中心（RUCOOL）", "美国", "北美", "Rutgers University", "美国东北沿岸/中大西洋湾"),
    "https://atn.ioos.us/erddap": ("IOOS ATN（动物遥测网络节点）", "美国", "北美", "IOOS/NOAA ATN", "太平洋/美国沿岸"),
    "https://data.neracoos.org/erddap": ("NERACOOS（东北大西洋沿岸观测系统）", "美国", "北美", "NERACOOS", "美国东北沿岸/缅因湾"),
    "https://erddap.bio-oracle.org/erddap": ("Bio-Oracle（海洋环境图层项目）", "国际组织", "全球", "Bio-Oracle 项目", "全球海洋环境栅格"),
    "https://erddap.griidc.org/erddap": ("GRIIDC（海湾研究计划数据中心）", "美国", "北美", "GRIIDC/Harte Research Institute", "墨西哥湾"),
    "https://erddap.marine.ie/erddap": ("Marine Institute（爱尔兰海洋研究所）", "爱尔兰", "欧洲", "Marine Institute Ireland", "爱尔兰及周边海域"),
    "https://erddap.observations.voiceoftheocean.org/erddap": ("Voice of the Ocean 基金会（瑞典）", "瑞典", "欧洲", "Voice of the Ocean Foundation", "波罗的海/卡特加特"),
    "https://erddap.ondeckdata.com/erddap": ("OnDeck Data（商业海洋数据服务）", "美国", "北美", "OnDeck Data", "美国沿岸渔业环境"),
    "https://gliders.ioos.us/erddap": ("IOOS Gliders（国家滑翔机数据组装中心）", "美国", "北美", "IOOS", "美国沿岸/全球滑翔机剖面"),
    "https://linkedsystems.uk/erddap": ("UK Met Office Linked Systems（英国气象局）", "英国", "欧洲", "Met Office", "英国海域/全球模式"),
    "https://oceanview.pfeg.noaa.gov/erddap": ("NOAA SWFSC ERDDAP（OceanView 节点）", "美国", "北美", "NOAA SWFSC", "东北太平洋/加州沿岸"),
    "https://pae-paha.pacioos.hawaii.edu/erddap": ("PACIOOS（太平洋岛屿海洋观测系统）", "美国", "大洋洲", "PACIOOS/University of Hawaii", "夏威夷/太平洋岛屿"),
    "https://polarwatch.noaa.gov/erddap": ("NOAA PolarWatch（极地观测节点）", "美国", "全球(极地为主)", "NOAA PolarWatch", "北极/南极海域卫星产品"),
    "https://spraydata.ucsd.edu/erddap": ("SIO/UCSD Spray 水下滑翔机项目", "美国", "北美", "Scripps Institution of Oceanography", "加州沿岸/东太平洋"),
    "https://upwell.pfeg.noaa.gov/erddap": ("NOAA SWFSC ERDDAP（Upwell 节点）", "美国", "北美", "NOAA SWFSC", "东北太平洋生态/上升流"),
    "https://www.smartatlantic.ca/erddap": ("SmartAtlantic（北大西洋海洋观测）", "加拿大", "北美", "SmartAtlantic Alliance", "加拿大东部沿岸/北大西洋"),
}

def row_for(base, level, evidence):
    org, country, region, provider, coverage = META[base]
    p = urlsplit(base)
    root = f"{p.scheme}://{p.netloc}"
    name_core = org.split("（")[0]
    return dict(
        service_name=f"{name_core} ERDDAP 数据服务",
        country=country, region=region, provider=org,
        category="海洋", service_type="数据API", protocol="ERDDAP",
        official_url=root + "/", service_url=base.rstrip("/") + "/erddap/index.html" if not base.rstrip("/").endswith("/erddap") else base.rstrip("/") + "/index.html",
        docs_url=base.rstrip("/") + "/index.html",
        layer_or_endpoint="/erddap/（search/tabledap/griddap/wms/files）",
        data_description=f"{name_core} 的 ERDDAP 服务器：海洋观测/遥感/模式数据集，支持 tabledap/griddap 结构化查询、WMS 取图与 CSV/NetCDF 下载",
        spatial_coverage=coverage, temporal_coverage="持续更新",
        crs="EPSG:4326", resolution="未标注", update_frequency="持续更新",
        format="CSV;NetCDF;GeoJSON", auth="无", api_key_required="否", registration_required="否",
        free="是", commercial_use="是", redistribution="是", attribution=name_core,
        need_no_reg="是", need_no_key="是", is_free="是",
        support_api="是", support_spatial_query="未知", support_temporal_query="是",
        support_batch="未知", support_download="是", support_geojson="是", support_json="是",
        is_vector="是", is_raster="是", is_realtime="是",
        global_coverage="否", region_coverage="是",
        status="已验证",
        verify_method="protocol-probe:strong" if level == "strong" else "protocol-probe:weak",
        last_verified=TODAY,
        notes=f"awesome-erddap 登记册候选，实测 {evidence}(2026-10-07)；search API: {base.rstrip('/')}/search/index.csv",
    )

results = json.load(open(r"E:/tmp/erddap_results.json", encoding="utf-8"))
live = [r for r in results if r["level"] and r["base"] in META]

conn = sqlite3.connect("gis_services.db")
cur = conn.cursor()
cols = [r[1] for r in cur.execute("PRAGMA table_info(master)")]
nxt = cur.execute("select max(cast(substr(service_id,5) as int)) from master where service_id like 'R10-%'").fetchone()[0] or 18
inserted = []
for r in live:
    nxt += 1
    row = row_for(r["base"], r["level"], r["evidence"])
    row["service_id"] = f"R10-{nxt:04d}"
    from urllib.parse import urlsplit as us
    pa = us(row["service_url"])
    root = f"{pa.scheme}://{pa.netloc}".lower()
    dup = cur.execute("SELECT service_id FROM master WHERE LOWER(service_url) LIKE ? OR LOWER(official_url) LIKE ?",
                      (root + "/%", root + "/%")).fetchone()
    if dup:
        print(f"查重跳过 {row['service_id']} {row['service_name']} -> {dup[0]}")
        continue
    values = {c: None for c in cols}
    for k, v in row.items():
        if k in cols:
            values[k] = v
    for k in ("caching_allowed", "rate_limit", "query_limit", "download_limit", "pagination",
              "batch_query", "commercial_ok", "cache_ok", "redistribute_ok"):
        values.setdefault(k, "未知")
    cur.execute(f"INSERT INTO master ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
                [values[c] for c in cols])
    inserted.append(row["service_id"])

conn.commit()
n = cur.execute("select count(*) from master").fetchone()[0]
print(f"插入 {len(inserted)} 条，master 总数 -> {n}")
conn.close()
