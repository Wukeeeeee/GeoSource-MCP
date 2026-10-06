#!/usr/bin/env python3
"""一次性入库：2026-10-07 第十轮 STAC 批次（STAC Index 登记册）新增 54 条。

登记册：stacindex.org/api/catalogs，148 个目录里 public 且未收录 73 个。
判据：响应含 "stac_version" → STAC（带 /collections 或 conformsTo 为 API 型，否则静态 catalog.json）。
实测 53 个确认 STAC + GEE catalog(全量读取确认 stac_version 1.0.0)。
FGDC 5 个端点响应为 OGC API Records Collection(itemType=record)，按 OGC API Records 收。
14 个死/拒（404/403/超时）不收；GISTDA 2 个因 URL 内嵌 api_key 按规则不收。
"""
import json
import re
import sqlite3
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

TODAY = "2026-10-07"

# url -> (名称, 国家, 区域, 机构, 类别, 描述)
META = {
    "https://aerialdataset.com/stac": ("AerialDataset STAC", "德国", "欧洲", "AerialDataset", "遥感/影像", "无人机航拍影像场景目录（商业许可，元数据公开）"),
    "https://digital-atlas.s3.amazonaws.com/stac/public_stac/catalog.json": ("African Agriculture Adaptation Atlas STAC", "国际组织", "非洲", "African Agriculture Adaptation Atlas", "农业/农村经济", "非洲农业适应图集的静态 STAC 目录：气候、农业与适应数据集"),
    "https://eod-catalog-svc-prod.astraea.earth/": ("Astraea Earth OnDemand STAC API", "美国", "北美", "Astraea, Inc.", "遥感/影像", "Astraea Earth OnDemand 商业影像目录 API"),
    "https://s3-west.nrp-nautilus.io/public-data/stac/catalog.json": ("Boettiger Lab 地理数据 STAC", "美国", "北美", "Boettiger Lab (UC Berkeley)", "综合/自然资源", "Boettiger 实验室公开地理数据集静态 STAC 目录"),
    "https://stac.geobon.org/": ("BON in a Box STAC API", "加拿大", "北美", "GEO BON（生物多样性观测网络）", "生物多样性", "GEO BON 生物多样性基线与指标数据 STAC API"),
    "https://storage.googleapis.com/cfo-public/catalog.json": ("California Forest Observatory STAC", "美国", "北美", "California Forest Observatory (Salo Sciences)", "森林/林业", "加州森林观测：森林结构与 wildfire 风险栅格的静态 STAC 目录"),
    "https://capella-open-data.s3.us-west-2.amazonaws.com/stac/catalog.json": ("Capella Space 开放 SAR 数据 STAC", "美国", "北美", "Capella Space", "遥感/影像", "Capella Space 开放 SAR 影像样本静态 STAC 目录"),
    "https://vims.univ-nantes.fr/stac/catalog.json": ("Cassini VIMS-IR STAC", "法国", "欧洲", "Nantes Université / NASA PDS", "其他", "卡西尼号土星 VIMS 红外影像 STAC 目录（行星科学）"),
    "https://stac.scitekno.com.br/v100/": ("CBERS/Amazonia-1 AWS STAC API", "巴西", "南美", "SciEKO / INPE", "遥感/影像", "中巴资源卫星 CBERS 与 Amazonia-1 影像的 AWS 开放目录 API"),
    "https://ciesin.github.io/sci-apps-stac/stac/catalog.json": ("CIESIN STAC", "美国", "北美", "CIESIN (Columbia University)", "人口/社会经济", "CIESIN 人口与环境数据应用的静态 STAC 目录"),
    "https://coclico.blob.core.windows.net/stac/v1/catalog.json": ("CoCliCo STAC Catalog", "国际组织", "欧洲", "CoCliCo (Coastal Climate Core Service)", "海平面", "欧盟海岸气候服务 CoCliCo 的海岸风险数据 STAC 目录"),
    "https://spatio-temporal-asset-catalog.s3.ap-south-1.amazonaws.com/CorestackCatalogs_merged_collection/catalog.json": ("CoRE Stack STAC", "国际组织", "南亚", "CoRE Stack (Sustainability Sat Lab)", "环境", "南亚生态恢复监测数据（树木覆盖、水、土地）STAC 目录"),
    "https://esa.pages.eox.at/cubes-and-clouds-catalog/MOOC_Cubes_and_clouds/catalog.json": ("Cubes and Clouds 雪盖 STAC", "国际组织", "欧洲", "ESA / EOX", "冰川", "ESA 开放科学课程配套雪盖数据静态 STAC 目录"),
    "https://stac.cyverse.org/": ("CyVerse STAC API", "美国", "北美", "CyVerse (UA/NCSA)", "科研", "CyVerse 科学科研数据 STAC API"),
    "https://hda.data.destination-earth.eu/stac/v2": ("Destination Earth 数据湖 STAC API", "国际组织", "欧洲", "Destination Earth (EU)", "气象", "欧盟 Destination Earth 数据湖(DEDL) STAC API"),
    "https://explorer.sandbox.dea.ga.gov.au/stac/": ("Digital Earth Australia STAC API", "澳大利亚", "大洋洲", "Geoscience Australia (DEA)", "遥感/影像", "澳大利亚数字地球(DEA)分析就绪影像 STAC API"),
    "https://dop.stac.lgln.niedersachsen.de": ("下萨克森州正射影像 STAC", "德国", "欧洲", "LGLN Niedersachsen", "遥感/影像", "德国下萨克森州数字正射影像(DOP20) STAC API"),
    "https://stac.earthgenome.org/": ("Earth Genome Sentinel-2 镶嵌 STAC API", "美国", "北美", "Earth Genome", "遥感/影像", "Sentinel-2 L2A 时间序列镶嵌 STAC API"),
    "https://stac.easierdata.info": ("EasierData STAC API", "美国", "北美", "EasierData Initiative", "科研", "EasierData 开放科研数据 STAC API"),
    "https://s3.eu-central-1.wasabisys.com/stac/odse/catalog.json": ("EcoDataCube.eu STAC", "国际组织", "欧洲", "OpenGeoHub", "环境", "欧洲 1km 环境与土地数据立方体静态 STAC 目录"),
    "https://s3.gptl.ru/stac-web-free/catalog.json": ("俄罗斯 ERS 开放数据 STAC", "俄罗斯", "欧洲/亚洲", "GPTL", "遥感/影像", "俄罗斯遥感开放数据静态 STAC 目录"),
    "https://eocat.esa.int/eo-catalogue/": ("ESA EO Catalogue STAC API", "国际组织", "全球", "ESA", "遥感/影像", "ESA 官方对地观测目录 eocat STAC API"),
    "https://storage.googleapis.com/carto-portolan-ide-extremadura/catalog.json": ("埃斯特雷马杜拉 SDI STAC", "西班牙", "欧洲", "IDE Extremadura (CICTEX)", "综合/政府开放数据", "西班牙埃斯特雷马杜拉大区空间数据基础设施静态 STAC 目录"),
    "https://stacapi.eoxhub.fairicube.eu/": ("FAIRiCUBE Hub STAC API", "国际组织", "欧洲", "FAIRiCUBE (EU Horizon)", "环境", "FAIRiCUBE 城市环境用例数据 STAC API"),
    "https://fiboa.org/stac/catalog.json": ("fiboa 田块边界 STAC", "国际组织", "全球", "fiboa 项目", "农业/农村经济", "全球农田边界(field boundary)开放标准数据静态 STAC 目录"),
    "https://pta.data.lit.fmi.fi/stac/root.json": ("FMI ARD 芬兰 STAC", "芬兰", "欧洲", "Finnish Meteorological Institute", "遥感/影像", "芬兰气象研究所分析就绪影像(PTA) STAC 目录"),
    "https://geofiles.be.ch/geoportal/pub/stac/de/catalog.json": ("伯尔尼州地理数据 STAC", "瑞士", "欧洲", "Kanton Bern", "综合/政府开放数据", "瑞士伯尔尼州官方地理数据静态 STAC 目录"),
    "https://gep-supersites-stac.terradue.com/": ("GEP Supersites CSK/CSG STAC API", "国际组织", "全球", "Geohazards Exploitation Platform (ESA)", "灾害", "地质灾害 supersites COSMO-SkyMed 数据 STAC API"),
    "https://earthengine.openeo.org/v1.0/": ("Google Earth Engine openEO API", "美国", "全球", "Google", "遥感/影像", "GEE 的 openEO 接口（openEO 协议，可按 STAC 语义交互）"),
    "https://rawcdn.githack.com/IDE-FCyT/IDE-FCyT/main/docs/catalog/stac_catalog.json": ("UADER 理工学院 STAC", "阿根廷", "南美", "UADER IDE", "综合/政府开放数据", "阿根廷 Entre Ríos 省立大学信息基础设施静态 STAC 目录"),
    "https://gis.ktn.gv.at/api/stac/v1/": ("KAGIS 克恩顿州 STAC API", "奥地利", "欧洲", "KAGIS Kärnten", "综合/政府开放数据", "奥地利克恩顿州地理信息系统官方 STAC API"),
    "https://ard.maxar.com/samples/catalog.json": ("Maxar ARD 样本 STAC", "美国", "北美", "Maxar Technologies", "遥感/影像", "Maxar 分析就绪数据(ARD)样本静态 STAC 目录"),
    "https://maxar-opendata.s3.amazonaws.com/events/catalog.json": ("Maxar 开放数据(灾害事件) STAC", "美国", "全球", "Maxar Technologies", "灾害", "Maxar 重大灾害事件开放影像静态 STAC 目录"),
    "https://mideafind.com/data/stac/catalog.json": ("MideaFind 德国建材门店 STAC", "德国", "欧洲", "MideaFind", "POI", "德国 DIY 建材门店位置数据静态 STAC 目录"),
    "https://stac-server.dev2prod.co/": ("MISTEO STAC Server", "未知", "其他", "MISTEO", "遥感/影像", "MISTEO STAC 服务器 API"),
    "https://datacloud.icgc.cat/stac-catalog/catalog.json": ("加泰罗尼亚 Sentinel-2 月度镶嵌 STAC", "西班牙", "欧洲", "ICGC（加泰罗尼亚制图院）", "遥感/影像", "加泰罗尼亚monthly Sentinel-2 镶嵌静态 STAC 目录"),
    "https://api.stac.teledetection.fr": ("Theia Teledetection STAC API", "法国", "欧洲", "THEIA (CNES)", "遥感/影像", "法国 THEIA 地面段多源卫星数据 STAC API"),
    "https://nasa-iserv.s3-us-west-2.amazonaws.com/catalog/catalog.json": ("NASA ISERV STAC", "美国", "全球", "NASA", "遥感/影像", "NASA ISS SERVIR 环境系统与影像获取(ISERV)静态 STAC 目录"),
    "data.source.coop/nlebovits/moldova-geodata/catalog.json": ("摩尔多瓦国家地理数据 STAC", "摩尔多瓦", "欧洲", "source.coop 镜像", "综合/政府开放数据", "摩尔多瓦国家地理数据静态 STAC 目录（source.coop 托管）"),
    "https://nz-coastal.s3.ap-southeast-2.amazonaws.com/catalog.json": ("新西兰海岸高程 STAC", "新西兰", "大洋洲", "Toitū Te Whenua LINZ", "海平面", "新西兰海岸带测深/高程静态 STAC 目录"),
    "https://nz-elevation.s3.ap-southeast-2.amazonaws.com/catalog.json": ("新西兰高程 STAC", "新西兰", "大洋洲", "Toitū Te Whenua LINZ", "DEM", "新西兰全国 DEM/LiDAR 派生高程静态 STAC 目录"),
    "https://nz-imagery.s3.ap-southeast-2.amazonaws.com/catalog.json": ("新西兰影像 STAC", "新西兰", "大洋洲", "Toitū Te Whenua LINZ", "遥感/影像", "新西兰全国航空正射影像静态 STAC 目录"),
    "https://noaadata.apps.nsidc.org/NOAA/G02202_V6/stac/catalog.json": ("NOAA/NSIDC 海冰 CDR STAC", "美国", "全球(极地为主)", "NOAA / NSIDC", "海平面", "NOAA/NSIDC 海冰指数气候数据记录 V6 静态 STAC 目录"),
    "https://api.imagery.hotosm.org/stac": ("OpenAerialMap STAC API", "国际组织", "全球", "HOT OSM", "遥感/影像", "OpenAerialMap 无人机/航拍开放影像 STAC API"),
    "https://s3.eu-central-1.wasabisys.com/stac/openlandmap/catalog.json": ("OpenLandMap STAC", "国际组织", "全球", "OpenGeoHub", "土壤", "OpenLandMap 全球土壤/土地性质栅格静态 STAC 目录"),
    "https://esa-earthcode.github.io/open-science-catalog-metadata/catalog.json": ("ESA Open Science Catalog", "国际组织", "全球", "ESA Φ-lab", "科研", "ESA 开放科学目录(EO 项目产品)静态 STAC 目录"),
    "https://stac.overturemaps.org/catalog.json": ("Overture Maps 发布 STAC", "美国", "全球", "Overture Maps Foundation", "POI", "Overture Maps 建筑与主题发布数据的静态 STAC 目录"),
    "https://paituli.csc.fi/geoserver/ogc/stac/v1": ("Paituli STAC (芬兰)", "芬兰", "欧洲", "CSC / Paituli", "综合/政府开放数据", "芬兰 Paituli 空间数据下载服务 STAC API（GeoServer OGC API 承载）"),
    "https://api.panoramax.xyz/api/": ("Panoramax 街景 STAC API", "法国", "欧洲", "IGN France / Panoramax", "街景", "Panoramax 开放街景影像联邦 API（含 STAC 语义）"),
    "https://stac.pgc.umn.edu/api/v1/": ("PGC 极地数据目录 STAC API", "美国", "全球(极地为主)", "Polar Geospatial Center (UMN)", "DEM", "明尼苏达大学极地地理空间中心影像/DEM STAC API"),
    "https://pgc-opendata-dems.s3.us-west-2.amazonaws.com/pgc-data-stac.json": ("PGC 开放 DEM STAC", "美国", "全球(极地为主)", "Polar Geospatial Center (UMN)", "DEM", "PGC 极地 DEM (ArcticDEM/REMA) 开放数据静态 STAC 目录"),
    "https://radiantearth.blob.core.windows.net/mlhub/rapidai4eo/stac-v1.0/catalog.json": ("RapidAI4EO STAC", "国际组织", "欧洲", "Radiant Earth Foundation", "遥感/影像", "RapidAI4EO 机器学习训练数据静态 STAC 目录"),
    "https://rosetta-3dcomet.cnes.fr/stac/collection.json": ("罗塞塔彗星 67P 双_resolution STAC", "法国", "其他", "CNES", "其他", "罗塞塔任务 OSIRIS 彗星 67P 核 3D 双分辨率影像 STAC 目录"),
    "https://meeo-s3.s3.amazonaws.com/catalog.json": ("Sentinel-3 L2/L3 AWS STAC", "卢森堡", "欧洲", "MEEO (ESA Clayton 改造)", "遥感/影像", "Sentinel-3 Level 2/3 产品 AWS 镜像静态 STAC 目录"),
    "https://meeo-s5p.s3.amazonaws.com/catalog.json": ("Sentinel-5P L2 AWS STAC", "卢森堡", "欧洲", "MEEO (ESA)", "环境/空气质量/水质", "Sentinel-5P 对流层污染物 L2 产品 AWS 镜像静态 STAC 目录"),
    "https://worldbank.github.io/DECAT_Space2Stats/stac/catalog.json": ("世界银行 Space2Stats STAC", "国际组织", "全球", "World Bank DECAT", "人口/社会经济", "世界银行格网化社会经济统计数据静态 STAC 目录"),
    "https://canada-spot-ortho.s3.amazonaws.com/canada_spot_orthoimages/catalog.json": ("加拿大 SPOT 正射影像 STAC", "加拿大", "北美", "CCRS (Natural Resources Canada)", "遥感/影像", "加拿大 2005-2010 SPOT 正射影像静态 STAC 目录"),
    "https://console.semablu.com/py/stac": ("Semablu Sentinel-2 2.5m 超分 STAC API", "未知", "其他", "Semablu", "遥感/影像", "Sentinel-2 2.5m 超分辨率商业 API 的 STAC 端点"),
    "https://eodata.thuenen.de/stac/api/v1/": ("Thünen 卫星数据(ThEO) STAC API", "德国", "欧洲", "Thünen-Institut", "遥感/影像", "Thünen 研究所卫星影像分析就绪数据 STAC API"),
    "https://gws-access.jasmin.ac.uk/public/nceo_ard/NCEO_ARD_STAC/catalog.json": ("UK NCEO ARD STAC", "英国", "欧洲", "NCEO (UKRI)", "遥感/影像", "英国国家地球观测中心分析就绪数据静态 STAC 目录"),
    "https://s3.us-west-2.amazonaws.com/umbra-open-data-catalog/stac/catalog.json?.language=en": ("Umbra 开放 SAR 数据 STAC", "美国", "全球", "Umbra Space", "遥感/影像", "Umbra 商业 SAR 开放数据集静态 STAC 目录"),
    "https://stac.sage.uvt.ro": ("UVT STAC Catalog", "罗马尼亚", "欧洲", "West University of Timișoara", "科研", "蒂米什瓦拉西部大学科研数据 STAC API"),
    "https://wyvern-odp.com/catalog.json": ("Wyvern 开放数据 STAC", "加拿大", "北美", "Wyvern Space", "遥感/影像", "Wyvern 高光谱商业星座开放数据集静态 STAC 目录"),
    # FGDC OGC API Records
    "https://api.fgdc.gov/ngda/address/": ("美国国家地理数据地址主题 API", "美国", "北美", "Federal Geographic Data Committee", "地址", "FGDC NGDA 地址主题数据集（OGC API Records，itemType=record）"),
    "https://api.fgdc.gov/ngda/cadastre/": ("美国国家地理数据地籍主题 API", "美国", "北美", "Federal Geographic Data Committee", "土地", "FGDC NGDA 地籍主题数据集（OGC API Records）"),
    "https://api.fgdc.gov/states/al/": ("阿拉巴马州开放数据 API (GeoPlatform)", "美国", "北美", "Alabama GIS / GeoPlatform", "综合/政府开放数据", "GeoPlatform 聚合的阿拉巴马州开放数据资源（OGC API Records）"),
    "https://api.fgdc.gov/states/ak/": ("阿拉斯加州地理资源 API (GeoPlatform)", "美国", "北美", "Alaska / GeoPlatform", "综合/政府开放数据", "GeoPlatform 聚合的阿拉斯加州地理资源（OGC API Records）"),
    "https://api.fgdc.gov/states/ca/": ("加州地理数据 API (GeoPlatform)", "美国", "北美", "California / GeoPlatform", "综合/政府开放数据", "GeoPlatform 聚合的加州地理数据（OGC API Records）"),
}

records = json.load(open(r"E:/tmp/stac_results.json", encoding="utf-8"))
live = []
for u, title, code, kind, n in records:
    if not str(kind).startswith("stac"):
        continue
    if u not in META:
        print("META 缺失，跳过:", u)
        continue
    live.append((u, kind, n))

conn = sqlite3.connect("gis_services.db")
cur = conn.cursor()
cols = [r[1] for r in cur.execute("PRAGMA table_info(master)")]
from urllib.parse import urlsplit
nxt = cur.execute("select max(cast(substr(service_id,5) as int)) from master where service_id like 'R10-%'").fetchone()[0]
inserted, skipped = [], []
for u, kind, n in live:
    nxt += 1
    name, country, region, provider, cat, desc = META[u]
    is_api = kind == "stac-api"
    sid = f"R10-{nxt:04d}"
    p = urlsplit("https://" + u if not u.startswith("http") else u)
    root = f"{p.scheme}://{p.netloc}"
    dup = cur.execute("SELECT service_id FROM master WHERE LOWER(service_url) LIKE ? OR LOWER(official_url) LIKE ?",
                      (root + "/%", root + "/%")).fetchone()
    if dup:
        skipped.append((sid, name, dup[0]))
        continue
    values = {c: None for c in cols}
    row = dict(
        service_id=sid, service_name=name, country=country, region=region, provider=provider,
        category=cat, service_type="STAC", protocol="STAC",
        official_url=u if u.startswith("http") else "https://" + u,
        service_url=u if u.startswith("http") else "https://" + u,
        docs_url=None,
        layer_or_endpoint=f"STAC 目录({'API 型' if is_api else '静态 catalog.json'}，首响应含 {n} 个 id 字段)" if n else "STAC 目录",
        data_description=desc,
        spatial_coverage=region, temporal_coverage="静态目录与持续更新",
        crs="随数据集", resolution="随数据集", update_frequency="随数据集",
        format="GeoTIFF;COG;GeoJSON;Parquet", auth="无", api_key_required="否",
        registration_required="否", free="是", commercial_use="随数据集", redistribution="随数据集",
        attribution=provider, need_no_reg="是", need_no_key="是", is_free="是",
        support_api="是", support_spatial_query="未知", support_temporal_query="未知",
        support_batch="未知", support_download="是", support_geojson="否", support_json="是",
        is_vector="否", is_raster="是", is_realtime="否",
        global_coverage="否", region_coverage="否",
        status="已验证", verify_method="protocol-probe:strong", last_verified=TODAY,
        notes=f"STAC Index 登记册候选，实测响应含 stac_version({kind})(2026-10-07)"
              + ("；GEE catalog.json 经全量读取确认 stac_version=1.0.0" if "earthengine" in u else ""),
    )
    for k, v in row.items():
        if k in cols:
            values[k] = v
    for k in ("caching_allowed", "rate_limit", "query_limit", "download_limit", "pagination",
              "batch_query", "commercial_ok", "cache_ok", "redistribute_ok"):
        values.setdefault(k, "未知")
    cur.execute(f"INSERT INTO master ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
                [values[c] for c in cols])
    inserted.append(sid)

conn.commit()
total = cur.execute("select count(*) from master").fetchone()[0]
print(f"插入 {len(inserted)} 条，查重跳过 {len(skipped)}，master 总数 -> {total}")
for s in skipped: print("  跳过:", s)
conn.close()
