import os
import sys
import json
import sqlite3
import re
from pathlib import Path
from datetime import date

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "gis_services.db"
HTML = ROOT / "viewer.html"
WORLD_GEO = ROOT / "assets" / "world_boundaries.geojson"
CHINA_GEO = ROOT / "assets" / "china_provinces.geojson"
ISO_MAP = ROOT / "assets" / "country_iso_map.json"
# 兼容旧版：若存在其他会话的 scratch payload 仍优先使用
PAYLOAD_PATH = Path(r"C:\Users\13469\.gemini\antigravity\brain\28484e4b-0b0c-410d-90c6-bbad4205cc15\scratch\map_payload.json")

FIELD_MAP = [
    ("service_id", "id"),
    ("service_name", "name"),
    ("country", "country"),
    ("region", "region"),
    ("provider", "provider"),
    ("category", "cat"),
    ("service_type", "type"),
    ("protocol", "proto"),
    ("service_url", "url"),
    ("official_url", "off"),
    ("docs_url", "doc"),
    ("layer_or_endpoint", "layer"),
    ("data_description", "desc"),
    ("spatial_coverage", "spat"),
    ("temporal_coverage", "temp"),
    ("crs", "crs"),
    ("format", "fmt"),
    ("update_frequency", "upd"),
    ("auth", "auth"),
    ("api_key_required", "key"),
    ("registration_required", "reg"),
    ("free", "free"),
    ("commercial_use", "comm"),
    ("redistribution", "redist"),
    ("rate_limit", "rate"),
    ("status", "status"),
    ("last_verified", "verified"),
    ("verify_method", "vmethod"),
    ("need_no_reg", "noregun"),
    ("need_no_key", "nokey"),
    ("is_free", "isfree"),
    ("support_api", "api"),
    ("support_spatial_query", "squery"),
    ("support_temporal_query", "tquery"),
    ("support_batch", "batch"),
    ("support_download", "dl"),
    ("support_geojson", "geo"),
    ("support_json", "json"),
    ("is_vector", "vec"),
    ("is_raster", "rast"),
    ("is_realtime", "real"),
    ("global_coverage", "glob"),
    ("region_coverage", "reg2"),
    ("commercial_ok", "commok"),
    ("cache_ok", "cache"),
    ("redistribute_ok", "redistok"),
    ("notes", "notes"),
]

def build_data(conn):
    rows = []
    for rec in conn.execute(f"SELECT {','.join(c for c, _ in FIELD_MAP)} FROM master"):
        d = {}
        for (col, short), val in zip(FIELD_MAP, rec):
            if val is not None:
                d[short] = str(val)
        rows.append(d)
    return rows

def build_map_payload(conn):
    """从 gis_services.db 现算地图 payload：边界取自 assets/，计数与服务列表取自库。
    国家→ISO 映射见 assets/country_iso_map.json；映射不到的区域型条目（全球/欧洲/多国等）
    归入全球公共池。中国条目按省名匹配进 34 省级池，未命中归 china_national。
    """
    world_geo = json.loads(WORLD_GEO.read_text(encoding="utf-8"))
    provinces_geo = json.loads(CHINA_GEO.read_text(encoding="utf-8"))
    iso_map = json.loads(ISO_MAP.read_text(encoding="utf-8"))
    CN_POOL = {"CN", "HK", "MO", "TW"}

    # —— 全国行，按短名匹配省份 ——
    PROVS = [f["properties"]["short"] for f in provinces_geo["features"]]
    prov_services = {p: [] for p in PROVS}
    prov_services[""] = []
    china_national = []
    intl = {}

    rows = conn.execute(
        "SELECT service_id,service_name,country,region,provider,category,service_type,protocol,"
        "official_url,service_url,data_description,spatial_coverage,status,verify_method,"
        "need_no_key,is_free,global_coverage,free FROM master"
    ).fetchall()
    cols = ["id", "name", "country", "region", "provider", "cat", "type", "proto", "off",
            "url", "desc", "spat", "status", "vmethod", "nokey", "isfree", "glob", "free"]

    def card(r):
        d = dict(zip(cols, r))
        return {k: d[k] for k in ("id", "name", "proto", "cat", "free", "nokey", "url",
                                  "status", "desc") if d.get(k) is not None}

    for r in rows:
        d = dict(zip(cols, r))
        country = (d["country"] or "").strip()
        iso = iso_map.get(country)
        card_r = card(r)
        if iso in CN_POOL or country in ("中国", "中国香港", "中国台湾", "中国澳门", "香港", "澳门", "台湾", "Taiwan"):
            text = "".join(str(x) for x in (d["region"], d["name"], d["desc"], d["spat"],
                                            d["provider"], d["country"]))
            hit = next((p for p in PROVS if p and p in text), None)
            if hit:
                prov_services[hit].append(card_r)
            else:
                prov_services[""].append(card_r)
                china_national.append(card_r)
        elif iso:
            intl.setdefault(iso, []).append(card_r)

    # 每国列表按 已验证→strong 优先排序并截断，防止 payload 膨胀
    def trim(lst, cap=40):
        lst.sort(key=lambda s: (s.get("status") != "已验证", "strong" not in (s.get("vmethod") or "")))
        return lst[:cap]

    for k in list(prov_services):
        prov_services[k] = trim(prov_services[k])
    china_national = trim(china_national)
    for k in list(intl):
        intl[k] = trim(intl[k])

    # —— 全球公共池：非国家型条目（映射不到 ISO 的区域/多国/全球）+ 全球覆盖行 ——
    c = conn.cursor()
    glob_q = """
        SELECT service_id,service_name,protocol,category,service_url,data_description,status
        FROM master
        WHERE (global_coverage='是' OR country LIKE '全球%' OR country IN
              ('国际组织','国际','欧洲','北美','南美','南极','北极','非洲(区域)','加勒比','未知',
               '大洋洲','亚洲','拉丁美洲/加勒比','西非/萨赫勒','区域(东非/南部非洲)','欧洲空间局',
               '欧盟','Oceania','Latin America')
              OR country LIKE '多国%' OR country LIKE '%/全球%' OR country LIKE '全球/%'
              OR country LIKE '%/欧洲%' OR country LIKE '欧盟%' OR country LIKE '%欧洲'
              OR country LIKE '德国%' OR country LIKE '美国/%' OR country LIKE '%/中国%'
              OR country LIKE '%奥地利%' OR country LIKE '%丹麦%' OR country LIKE '%瑞典%'
              OR country LIKE '芬兰%' OR country LIKE '英国%' OR country LIKE '荷兰%'
              OR country LIKE '葡萄牙%' OR country LIKE '卢森堡%' OR country LIKE '法国%'
              OR country LIKE '匈牙利%' OR country LIKE '日本%' OR country LIKE '韩国%'
              OR country LIKE '%;%' OR country LIKE '%地区%')
        ORDER BY CASE WHEN status='已验证' THEN 0 ELSE 1 END
    """
    global_rows = c.execute(glob_q).fetchall()
    global_services = [
        {"id": r[0], "name": r[1], "proto": r[2], "cat": r[3], "url": r[4],
         "desc": r[5], "status": r[6]}
        for r in global_rows[:80]
    ]
    global_data = {"name": "跨国与全球公共数据", "count": len(global_rows),
                   "verified": c.execute(
                       "SELECT count(*) FROM master WHERE status='已验证' AND "
                       "(global_coverage='是' OR country LIKE '全球%' OR country IN ('国际组织','国际'))"
                   ).fetchone()[0],
                   "services": global_services}

    # —— 世界要素计数（按 ISO 从库现算） ——
    stat = {}
    for (cty, n_v, n_a, n_f) in conn.execute(
        "SELECT country, "
        "sum(CASE WHEN status='已验证' THEN 1 ELSE 0 END), count(*), "
        "sum(CASE WHEN is_free='是' THEN 1 ELSE 0 END) FROM master GROUP BY country"
    ):
        iso = iso_map.get((cty or "").strip())
        if iso:
            s = stat.setdefault(iso, {"count": 0, "verified": 0, "free": 0})
            s["count"] += n_a; s["verified"] += n_v; s["free"] += n_f

    for f in world_geo["features"]:
        pr = f["properties"]
        iso = pr.get("iso")
        if iso == "CN":
            cn = stat.get("CN", {"count": 0, "verified": 0, "free": 0})
            for k2 in ("HK", "MO", "TW"):
                s2 = stat.get(k2)
                if s2:
                    cn["count"] += s2["count"]; cn["verified"] += s2["verified"]
                    cn["free"] += s2["free"]
            pr.update(count=cn["count"], verified=cn["verified"], free=cn["free"], is_china=True)
        else:
            s = stat.get(iso, {})
            pr.update(count=s.get("count", 0), verified=s.get("verified", 0),
                      free=s.get("free", 0), is_china=False)
    for f in provinces_geo["features"]:
        pr = f["properties"]
        lst = prov_services.get(pr["short"], [])
        pr.update(count=len(lst), verified=sum(1 for s in lst if s.get("status") == "已验证"))

    return {"world_geo": world_geo, "provinces_geo": provinces_geo,
            "intl_services": intl, "prov_services": prov_services,
            "china_national": china_national, "global_data": global_data}


def build_stats(conn):
    q = lambda s: conn.execute(s).fetchone()[0]
    return {
        "today": date.today().isoformat(),
        "total": q("SELECT count(*) FROM master"),
        "verified": q("SELECT count(*) FROM master WHERE status='已验证'"),
        "strong": q("SELECT count(*) FROM master WHERE verify_method LIKE '%strong%'"),
        "unverified": q("SELECT count(*) FROM master WHERE status='未验证'"),
        "countries": q("SELECT count(distinct country) FROM master"),
        "direct": q(
            "SELECT count(*) FROM master WHERE need_no_reg='是' AND is_free='是'"
            " AND support_api LIKE '是%'"
        ),
    }

print("Loading database data and map payload...")
conn = sqlite3.connect(DB)
data = build_data(conn)
st = build_stats(conn)
map_payload = build_map_payload(conn)
conn.close()

payload_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
map_payload_json = json.dumps(map_payload, ensure_ascii=False, separators=(",", ":"))

html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>GeoSource</title>
  <link rel="stylesheet" href="https://cdn.bootcdn.net/ajax/libs/leaflet/1.9.4/leaflet.css" />
  <script src="https://cdn.bootcdn.net/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
  <style>
    :root {{
      --bg: #0d0d0d;
      --panel: #141414;
      --panel2: #1a1a1a;
      --ink: #f0f0f0;
      --mut: #9a9a9a;
      --mut2: #6a6a6a;
      --line: #3a3a3a;
      --line2: #2a2a2a;
      --accent: #ffffff;
      --border: 1px solid var(--line);
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: "SF Mono", "JetBrains Mono", "Consolas", "Menlo", "Courier New", ui-monospace, monospace;
      background: var(--bg);
      color: var(--ink);
      font-size: 12px;
      line-height: 1.4;
      border-radius: 0;
    }}
    header {{
      padding: 14px 20px;
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      border-radius: 0;
    }}
    h1 {{
      margin: 0 0 3px;
      font-size: 16px;
      font-weight: 600;
      letter-spacing: -0.3px;
      border-radius: 0;
    }}
    .sub {{ color: var(--mut); font-size: 11px; }}
    .stats {{
      display: flex;
      gap: 0;
      margin-top: 12px;
      flex-wrap: wrap;
      border: 1px solid var(--line);
      border-radius: 0;
    }}
    .stat {{
      background: var(--panel);
      padding: 8px 16px;
      border-right: 1px solid var(--line);
      border-radius: 0;
    }}
    .stat:last-child {{ border-right: none; }}
    .stat b {{ font-size: 16px; color: var(--ink); font-weight: 600; }}

    .tabs {{
      display: flex;
      gap: 0;
      padding: 0 20px;
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      border-radius: 0;
    }}
    .tab {{
      padding: 9px 16px;
      cursor: pointer;
      border: none;
      background: none;
      color: var(--mut);
      font-size: 12px;
      border-right: 1px solid var(--line);
      border-bottom: 2px solid transparent;
      font-family: inherit;
      border-radius: 0;
    }}
    .tab.act {{
      color: var(--ink);
      border-bottom-color: var(--ink);
      background: var(--bg);
    }}
    .tab:hover {{ color: var(--ink); }}

    .main {{ padding: 14px 20px; }}
    .filters {{
      display: grid;
      grid-template-columns: 2fr 1fr 1fr 1fr 1fr 1fr;
      gap: 0;
      margin-bottom: 10px;
      border: 1px solid var(--line);
      border-radius: 0;
    }}
    .filters input, .filters select {{
      background: var(--panel);
      border: none;
      border-right: 1px solid var(--line);
      color: var(--ink);
      padding: 7px 9px;
      font-size: 12px;
      font-family: inherit;
      border-radius: 0;
      appearance: none;
    }}
    .filters select {{
      background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6'><path d='M0 0l5 6 5-6' fill='%239a9a9a'/></svg>");
      background-repeat: no-repeat;
      background-position: right 8px center;
      padding-right: 22px;
    }}
    .filters input:focus, .filters select:focus {{
      outline: none;
      background: var(--panel2);
    }}
    .filters input:last-child, .filters select:last-child {{ border-right: none; }}

    table {{ width: 100%; border-collapse: collapse; font-size: 12px; border-radius: 0; }}
    th {{
      background: var(--panel);
      position: sticky;
      top: 0;
      text-align: left;
      padding: 7px 8px;
      border: 1px solid var(--line);
      cursor: pointer;
      white-space: nowrap;
      z-index: 2;
      font-weight: 600;
      color: var(--ink);
      border-radius: 0;
    }}
    td {{
      padding: 5px 8px;
      border: 1px solid var(--line2);
      vertical-align: top;
      border-radius: 0;
    }}
    tr:hover td {{ background: var(--panel2); }}

    .badge {{
      display: inline-block;
      padding: 0 6px;
      border: 1px solid;
      font-size: 11px;
      line-height: 1.5;
      border-radius: 0;
    }}
    .v-已验证 {{ background: #12200f; color: #7bc46a; border-color: #3a5a2e; }}
    .v-未验证 {{ background: #22200f; color: #d4c25a; border-color: #5a522a; }}
    .v-历史服务 {{ background: #1a1a1a; color: #b0b0b0; border-color: #4a4a4a; }}
    .v-已停止 {{ background: #240f0f; color: #d47a7a; border-color: #5a2e2e; }}

    .tag {{
      display: inline-block;
      background: transparent;
      color: var(--mut);
      padding: 0 5px;
      border: 1px solid var(--line);
      margin: 1px;
      font-size: 11px;
      border-radius: 0;
    }}
    a {{ color: var(--ink); text-decoration: underline; text-underline-offset: 2px; }}
    a:hover {{ background: var(--ink); color: var(--bg); text-decoration: none; }}
    .count {{ color: var(--mut); margin: 0 0 8px; font-size: 11px; }}
    .hidden {{ display: none !important; }}

    .detail {{
      position: fixed;
      right: 20px;
      top: 60px;
      width: 420px;
      max-height: 85vh;
      overflow: auto;
      background: var(--panel);
      border: 1px solid var(--ink);
      padding: 14px;
      z-index: 2000;
      display: none;
      border-radius: 0;
    }}
    .detail h3 {{ margin-top: 0; color: var(--ink); font-size: 13px; border-radius: 0; }}
    .detail .close {{ float: right; cursor: pointer; color: var(--mut); }}
    .detail .close:hover {{ color: var(--ink); }}
    .drow {{ margin: 3px 0; }}
    .dk {{ color: var(--mut); display: inline-block; min-width: 90px; }}

    .chips {{
      display: flex;
      gap: 0;
      flex-wrap: wrap;
      margin-bottom: 10px;
      border: 1px solid var(--line);
      border-radius: 0;
    }}
    .chip {{
      padding: 5px 12px;
      background: var(--panel);
      border: none;
      border-right: 1px solid var(--line);
      cursor: pointer;
      font-size: 11px;
      color: var(--mut);
      font-family: inherit;
      border-radius: 0;
    }}
    .chip:last-child {{ border-right: none; }}
    .chip.act {{ background: var(--ink); color: var(--bg); }}
    .chip:hover {{ color: var(--ink); }}
    .chip.act:hover {{ color: var(--bg); }}

    /* ========================================================
       直角黑白灰地图模块样式 (MAP PANE)
       ======================================================== */
    #pane-map {{
      padding: 0;
      height: calc(100vh - 120px);
      display: flex;
      position: relative;
      border-bottom: 1px solid var(--line);
    }}
    #map {{
      flex: 1;
      height: 100%;
      background: #000000;
    }}

    .map-sidebar {{
      width: 420px;
      height: 100%;
      background: var(--panel);
      border-left: 1px solid var(--line);
      display: flex;
      flex-direction: column;
      z-index: 1000;
      border-radius: 0;
    }}

    .map-sidebar-head {{
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      background: var(--panel2);
    }}

    .map-title-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 4px;
    }}

    .map-region-name {{
      font-size: 14px;
      font-weight: 600;
      color: var(--ink);
    }}

    .map-count-badge {{
      font-size: 11px;
      padding: 1px 6px;
      background: var(--bg);
      border: 1px solid var(--line);
      color: var(--ink);
      border-radius: 0;
    }}

    .map-sub-text {{
      font-size: 11px;
      color: var(--mut);
      line-height: 1.4;
    }}

    .map-search-row {{
      margin-top: 10px;
      display: flex;
      gap: 0;
      border: 1px solid var(--line);
    }}

    .map-input {{
      flex: 1;
      height: 28px;
      background: var(--bg);
      border: none;
      color: var(--ink);
      padding: 0 8px;
      font-family: inherit;
      font-size: 11px;
      outline: none;
      border-radius: 0;
    }}

    .map-select {{
      height: 28px;
      background: var(--bg);
      border: none;
      border-left: 1px solid var(--line);
      color: var(--ink);
      padding: 0 8px;
      font-family: inherit;
      font-size: 11px;
      outline: none;
      cursor: pointer;
      border-radius: 0;
    }}

    .map-services-list {{
      flex: 1;
      overflow-y: auto;
      padding: 12px 16px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}

    .map-service-card {{
      background: var(--bg);
      border: 1px solid var(--line);
      padding: 10px;
      transition: background 0.15s, border-color 0.15s;
      border-radius: 0;
    }}

    .map-service-card:hover {{
      border-color: var(--ink);
      background: var(--panel2);
    }}

    .map-card-head {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 4px;
    }}

    .map-card-name {{
      font-size: 12px;
      font-weight: 600;
      color: var(--ink);
    }}

    .map-card-desc {{
      font-size: 11px;
      color: var(--mut);
      line-height: 1.4;
      margin-bottom: 8px;
    }}

    .map-url-box {{
      display: flex;
      border: 1px solid var(--line);
      border-radius: 0;
    }}

    .map-url-text {{
      flex: 1;
      font-size: 10px;
      padding: 4px 6px;
      background: var(--panel);
      color: var(--mut);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      user-select: all;
    }}

    .map-copy-btn {{
      background: var(--ink);
      color: var(--bg);
      border: none;
      padding: 4px 8px;
      font-family: inherit;
      font-size: 10px;
      font-weight: 600;
      cursor: pointer;
      border-radius: 0;
    }}
    .map-copy-btn:hover {{ background: #ffffff; }}

    /* 地图浮动工具条 (直角黑白灰) */
    .map-nav-bar {{
      position: absolute;
      top: 12px;
      left: 12px;
      z-index: 999;
      display: flex;
      gap: 0;
      border: 1px solid var(--line);
      border-radius: 0;
    }}

    .map-nav-btn {{
      background: var(--panel);
      border: none;
      border-right: 1px solid var(--line);
      color: var(--mut);
      padding: 6px 12px;
      font-family: inherit;
      font-size: 11px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 4px;
      border-radius: 0;
    }}
    .map-nav-btn:last-child {{ border-right: none; }}
    .map-nav-btn.act {{
      background: var(--ink);
      color: var(--bg);
      font-weight: 600;
    }}
    .map-nav-btn:hover:not(.act) {{
      background: var(--panel2);
      color: var(--ink);
    }}

    /* 直角黑白灰图例 */
    .map-legend {{
      position: absolute;
      bottom: 16px;
      left: 12px;
      z-index: 999;
      background: var(--panel);
      border: 1px solid var(--line);
      padding: 8px 12px;
      display: flex;
      flex-direction: column;
      gap: 6px;
      border-radius: 0;
    }}
    .map-legend-title {{
      font-size: 10px;
      color: var(--mut);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .map-legend-steps {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .map-scale-step {{
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 10px;
      color: var(--mut);
    }}
    .map-scale-block {{
      width: 12px;
      height: 8px;
      border: 1px solid var(--line);
      border-radius: 0;
    }}

    /* Leaflet 直角黑白灰强制样式重载 */
    .leaflet-tooltip {{
      background: var(--panel) !important;
      color: var(--ink) !important;
      border: 1px solid var(--ink) !important;
      border-radius: 0 !important;
      box-shadow: none !important;
      font-family: inherit !important;
      font-size: 11px !important;
      padding: 4px 8px !important;
    }}
    .leaflet-tooltip-top:before {{ border-top-color: var(--ink) !important; }}
    .leaflet-tooltip-bottom:before {{ border-bottom-color: var(--ink) !important; }}
    .leaflet-tooltip-left:before {{ border-left-color: var(--ink) !important; }}
    .leaflet-tooltip-right:before {{ border-right-color: var(--ink) !important; }}

    .leaflet-bar a {{
      background-color: var(--panel) !important;
      border-bottom: 1px solid var(--line) !important;
      color: var(--ink) !important;
      border-radius: 0 !important;
    }}
    .leaflet-bar a:hover {{
      background-color: var(--panel2) !important;
      color: #fff !important;
    }}
    .leaflet-control-zoom {{
      border: 1px solid var(--line) !important;
      border-radius: 0 !important;
    }}
  </style>
</head>
<body>
<header>
  <h1>GeoSource</h1>
  <div class="sub">真实存在 · 可程序化访问 · 已 HTTP 实测验证 · 更新日期 {st['today']}</div>
  <div class="stats" id="stats"></div>
</header>

<div class="tabs">
  <button class="tab act" data-t="db">[01] 服务查询库</button>
  <button class="tab" data-t="map">[02] 全球态势地图</button>
  <button class="tab" data-t="help">[03] 使用说明</button>
</div>

<!-- TAB 1: 表格服务查询库 -->
<div class="main" id="pane-db">
  <div class="chips" id="quickchips"></div>
  <div class="filters">
    <input id="q" placeholder="搜索名称/机构/国家/描述…">
    <select id="f-type"><option value="">全部类型</option></select>
    <select id="f-country"><option value="">全部国家/地区</option></select>
    <select id="f-status"><option value="">全部状态</option><option>已验证</option><option>未验证</option><option>历史服务</option><option>已停止</option></select>
    <select id="f-free"><option value="">免费/付费</option><option value="是">免费</option><option value="否">付费</option></select>
    <select id="f-key"><option value="">API Key</option><option value="是">需要 Key</option><option value="否">无需 Key</option></select>
  </div>
  <div class="count" id="cnt"></div>
  <div style="max-height:75vh;overflow:auto">
  <table id="tbl"><thead><tr>
    <th data-k="id">ID</th><th data-k="name">服务名称</th><th data-k="provider">机构</th>
    <th data-k="country">国家/地区</th><th data-k="type">类型</th><th data-k="free">免费</th>
    <th data-k="key">需Key</th><th data-k="status">状态</th><th data-k="url">服务URL</th><th>操作</th>
  </tr></thead><tbody></tbody></table>
  </div>
</div>

<!-- TAB 2: 直角黑白灰全球态势地图 (支持一个中国省区下钻) -->
<div class="hidden" id="pane-map">
  <div id="map"></div>

  <!-- 顶部直角导航栏 -->
  <div class="map-nav-bar">
    <button class="map-nav-btn act" id="mbtn-world">[ 全球视图 ]</button>
    <button class="map-nav-btn" id="mbtn-drillup" style="display:none;">[ ↖ 返回全球 ]</button>
    <button class="map-nav-btn" id="mbtn-china">[ 🇨🇳 中国及省级下钻 ]</button>
    <button class="map-nav-btn" id="mbtn-global">[ 🌐 跨国/全球公共池 ({map_payload['global_data']['count']}) ]</button>
  </div>

  <!-- 直角黑白灰图例 -->
  <div class="map-legend">
    <div class="map-legend-title" id="mlegend-title">GIS 服务收录量密度</div>
    <div class="map-legend-steps" id="mlegend-steps">
      <div class="map-scale-step"><div class="map-scale-block" style="background:#0d0d0d;"></div>0</div>
      <div class="map-scale-step"><div class="map-scale-block" style="background:#262626;"></div>1-10</div>
      <div class="map-scale-step"><div class="map-scale-block" style="background:#525252;"></div>10-100</div>
      <div class="map-scale-step"><div class="map-scale-block" style="background:#8c8c8c;"></div>100-500</div>
      <div class="map-scale-step"><div class="map-scale-block" style="background:#e0e0e0;"></div>500+</div>
    </div>
  </div>

  <!-- 侧边服务探查器 -->
  <div class="map-sidebar">
    <div class="map-sidebar-head">
      <div class="map-title-row">
        <span class="map-region-name" id="m-side-title">正在载入...</span>
        <span class="map-count-badge" id="m-side-badge">0 服务</span>
      </div>
      <div class="map-sub-text" id="m-side-sub">在地图上点击任意国家或省份版图查看服务条目</div>
      <div class="map-search-row">
        <input type="text" id="m-search" class="map-input" placeholder="过滤服务名称 / 描述 / URL..." />
        <select id="m-proto" class="map-select">
          <option value="">全部协议</option>
          <option value="WMS">OGC WMS</option>
          <option value="WFS">OGC WFS</option>
          <option value="ArcGIS">ArcGIS REST</option>
          <option value="CKAN">CKAN / API</option>
          <option value="STAC">STAC / 遥感</option>
          <option value="Tile">瓦片 / XYZ</option>
        </select>
      </div>
    </div>
    <div class="map-services-list" id="m-services-list">
      <div style="text-align:center;padding:40px;color:var(--mut);">载入中...</div>
    </div>
  </div>
</div>

<!-- TAB 3: 使用说明 -->
<div class="main hidden" id="pane-help">
  <h3>使用说明</h3>
  <p>1. 「服务查询库」支持全文搜索与多条件筛选；点击任意行可在右侧弹窗查看完整字段。</p>
  <p>2. 「全球态势地图」严格遵循<b>一个中国原则</b>，支持国际版图点击交互与国内 34 个省级行政区（含台湾省、香港、澳门）的无缝下钻，统一采用黑白灰直角极简工程美学。</p>
  <p>3. 状态徽章：<span class="badge v-已验证">已验证</span> = 探测拿到了协议级响应（GetCapabilities / ?f=json / 门户 API 返回真实数据）；<span class="badge v-未验证">未验证</span> = 域名真实存在，但未找到可匿名调用的接口。</p>
  <p>4. 数据由 <code>scripts/build_viewer.py</code> 从 <code>gis_services.db</code> 生成，改库后重跑该脚本即可刷新本页。</p>
</div>

<div class="detail" id="detail"><span class="close" onclick="document.getElementById('detail').style.display='none'">✕</span><div id="dbody"></div></div>

<script>
DATA = {payload_json};
const ST = {json.dumps(st)};
const MAP_DATA = {map_payload_json};

// stats
document.getElementById('stats').innerHTML = [
  ['总记录', ST.total], ['已验证', ST.verified], ['协议级强证据', ST.strong],
  ['未验证', ST.unverified], ['覆盖国家/地区', ST.countries],
  ['无需注册+免费+可API', ST.direct]
].map(([k,v])=>`<div class="stat"><b>${{v}}</b><div style="color:var(--mut);font-size:11px">${{k}}</div></div>`).join('');

// 快速筛选项
const chips = [
  ['全部', () => true],
  ['已验证可直接调用', d => d.status === '已验证' && d.vmethod.includes('strong')],
  ['开放数据门户 (API)', d => d.type === 'OpenData' || d.proto.includes('API') || d.proto.includes('CKAN')],
  ['WMS 地图服务', d => d.type === 'WMS'],
  ['WFS 要素下载', d => d.type === 'WFS'],
  ['中国数据源', d => d.country && d.country.includes('中国')],
  ['全球覆盖', d => d.country === '全球' || d.glob === '是'],
  ['免注册免Key免费', d => d.noregun === '是' && d.nokey === '是' && d.isfree === '是'],
];
const chipBox = document.getElementById('quickchips');
chips.forEach(([lbl, fn], i) => {{
  const b = document.createElement('button');
  b.className = 'chip' + (i === 0 ? ' act' : '');
  b.textContent = lbl;
  b.onclick = () => {{
    document.querySelectorAll('.chip').forEach(x => x.classList.remove('act'));
    b.classList.add('act');
    activeChip = fn;
    render();
  }};
  chipBox.appendChild(b);
}});

let activeChip = chips[0][1];
let sortK = 'id', sortDir = 1;

// 初始化下拉
const types = [...new Set(DATA.map(d => d.type).filter(Boolean))].sort();
const countries = [...new Set(DATA.map(d => d.country).filter(Boolean))].sort();
document.getElementById('f-type').innerHTML += types.map(t => `<option>${{t}}</option>`).join('');
document.getElementById('f-country').innerHTML += countries.map(c => `<option>${{c}}</option>`).join('');

function filterData() {{
  const q = document.getElementById('q').value.toLowerCase().trim();
  const ft = document.getElementById('f-type').value;
  const fc = document.getElementById('f-country').value;
  const fs = document.getElementById('f-status').value;
  const ff = document.getElementById('f-free').value;
  const fk = document.getElementById('f-key').value;
  return DATA.filter(d => {{
    if (!activeChip(d)) return false;
    if (ft && d.type !== ft) return false;
    if (fc && d.country !== fc) return false;
    if (fs && d.status !== fs) return false;
    if (ff && d.free !== ff) return false;
    if (fk && d.key !== fk) return false;
    if (q) {{
      const hit = (d.name||'').toLowerCase().includes(q) ||
                  (d.provider||'').toLowerCase().includes(q) ||
                  (d.country||'').toLowerCase().includes(q) ||
                  (d.desc||'').toLowerCase().includes(q) ||
                  (d.url||'').toLowerCase().includes(q) ||
                  (d.id||'').toLowerCase().includes(q);
      if (!hit) return false;
    }}
    return true;
  }});
}}

function render() {{
  const rows = filterData();
  rows.sort((a,b) => {{
    const va = a[sortK]||'', vb = b[sortK]||'';
    return va.localeCompare(vb, 'zh') * sortDir;
  }});
  document.getElementById('cnt').textContent = `匹配到 ${{rows.length}} / ${{DATA.length}} 条记录`;
  const view = rows.slice(0, 100);
  document.querySelector('#tbl tbody').innerHTML = view.map(d => `<tr>
    <td>${{d.id}}</td><td><a href="#" onclick="show('${{d.id}}');return false">${{esc(d.name)}}</a></td>
    <td>${{esc(d.provider)}}</td><td>${{esc(d.country)}}</td>
    <td><span class="tag">${{esc(d.type)}}</span></td>
    <td>${{d.free||'未知'}}</td><td>${{d.key||'未知'}}</td>
    <td><span class="badge v-${{d.status}}">${{d.status}}</span></td>
    <td style="max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"><a href="${{esc(d.url)}}" target="_blank">${{esc(d.url.replace(/^https?:\\/\\//,'').slice(0,50))}}</a></td>
    <td><a href="#" onclick="show('${{d.id}}');return false">详情</a></td>
  </tr>`).join('');
}}

function esc(s){{ return (s||'').replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c])); }}

function show(id) {{
  const d = DATA.find(x => x.id === id); if(!d) return;
  const rows = [
    ['服务ID', d.id], ['服务名称', d.name], ['机构', d.provider], ['国家/地区', d.country + ' / ' + d.region],
    ['类别', d.cat], ['服务类型', d.type], ['协议', d.proto],
    ['服务URL', `<a href="${{esc(d.url)}}" target="_blank">${{esc(d.url)}}</a>`],
    ['官方首页', `<a href="${{esc(d.off)}}" target="_blank">${{esc(d.off)}}</a>`],
    ['文档', d.doc && d.doc !== '未知' ? `<a href="${{esc(d.doc)}}" target="_blank">${{esc(d.doc)}}</a>` : '未知'],
    ['图层/端点', esc(d.layer)], ['数据描述', esc(d.desc)], ['空间覆盖', d.spat], ['时间覆盖', d.temp],
    ['坐标系', d.crs], ['格式', d.fmt], ['更新频率', d.upd],
    ['认证', d.auth], ['需Key', d.key], ['需注册', d.reg], ['免费', d.free],
    ['商业使用', d.comm], ['二次分发', d.redist], ['限流', d.rate],
    ['状态', d.status], ['验证日期', d.verified], ['验证方式', d.vmethod],
    ['无需注册', d.noregun], ['无需Key', d.nokey], ['支持API', d.api],
    ['空间查询', d.squery], ['时间查询', d.tquery], ['批量', d.batch], ['下载', d.dl],
    ['GeoJSON', d.geo], ['JSON', d.json], ['矢量', d.vec], ['栅格', d.rast], ['实时', d.real],
    ['全球覆盖', d.glob], ['区域覆盖', d.reg2], ['商业使用OK', d.commok], ['允许缓存', d.cache], ['允许再分发', d.redistok],
    ['备注', esc(d.notes)]
  ];
  document.getElementById('dbody').innerHTML = '<h3>' + esc(d.name) + '</h3>' + rows.map(([k,v]) => `<div class="drow"><span class="dk">${{k}}:</span><span>${{v||'未知'}}</span></div>`).join('');
  document.getElementById('detail').style.display = 'block';
}}

document.querySelectorAll('th').forEach(th => th.onclick = () => {{
  const k = th.dataset.k; if(!k) return;
  if (sortK === k) sortDir *= -1; else {{ sortK = k; sortDir = 1; }}
  render();
}});

['q','f-type','f-country','f-status','f-free','f-key'].forEach(i => document.getElementById(i).onchange = render);
document.getElementById('q').oninput = render;

// ========================================================
// 直角黑白灰地图模块逻辑 (CHOROPLETH + ONE-CHINA DRILLDOWN)
// ========================================================
let map = null;
let worldLayer = null;
let provinceLayer = null;
let selectedLayer = null;
let currentMapServices = [];
let currentMapLevel = 'world'; // 'world' | 'china_province'

function getMonoColor(cnt, isProv = false) {{
  if (isProv) {{
    if (cnt >= 5) return '#e0e0e0';
    if (cnt >= 3) return '#8c8c8c';
    if (cnt >= 1) return '#404040';
    return '#141414';
  }}
  if (cnt >= 500) return '#e0e0e0';
  if (cnt >= 100) return '#8c8c8c';
  if (cnt >= 10)  return '#525252';
  if (cnt > 0)    return '#262626';
  return '#0d0d0d';
}}

function initMap() {{
  if (map) return;
  map = L.map('map', {{
    center: [30, 20],
    zoom: 3,
    minZoom: 2,
    maxZoom: 12,
    zoomControl: false
  }});
  L.control.zoom({{ position: 'bottomright' }}).addTo(map);

  // 极简纯黑暗色底图 (Carto Dark)
  L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
    attribution: '&copy; CartoDB & GeoSource',
    maxZoom: 19
  }}).addTo(map);

  function worldStyle(f) {{
    const p = f.properties;
    const cnt = p.count || 0;
    const isChina = p.is_china;
    return {{
      fillColor: isChina ? '#d4d4d4' : getMonoColor(cnt),
      weight: isChina ? 1.5 : 1,
      opacity: 0.8,
      color: isChina ? '#ffffff' : (cnt > 0 ? '#404040' : '#262626'),
      fillOpacity: cnt > 0 ? 0.75 : 0.3
    }};
  }}

  function onEachWorldFeature(f, layer) {{
    const p = f.properties;
    const tip = p.is_china 
      ? `<b>[ 🇨🇳 中华人民共和国 ]</b><br>收录 ${{p.count}} 项服务<br><span style="color:#ffffff;">[ 点击下钻查看 34 个省区市分布 ]</span>`
      : `<b>[ ${{p.name}} ]</b><br>收录: ${{p.count}} 项 · 实测已验证: ${{p.verified}} 项`;
    layer.bindTooltip(tip, {{ sticky: true, opacity: 0.95 }});

    layer.on({{
      mouseover: e => {{
        if (e.target !== selectedLayer) {{
          e.target.setStyle({{ weight: 2, color: '#ffffff', fillOpacity: 0.9 }});
        }}
      }},
      mouseout: e => {{
        if (e.target !== selectedLayer) {{
          worldLayer.resetStyle(e.target);
        }}
      }},
      click: e => {{
        if (p.is_china) {{
          drillDownToChina();
        }} else {{
          selectMapCountry(e.target);
        }}
      }}
    }});
  }}

  worldLayer = L.geoJson(MAP_DATA.world_geo, {{
    style: worldStyle,
    onEachFeature: onEachWorldFeature
  }}).addTo(map);

  // 默认侧边栏展示全球公共池
  displayMapGlobalPool();
}}

function selectMapCountry(layer) {{
  if (selectedLayer && selectedLayer !== layer) {{
    worldLayer.resetStyle(selectedLayer);
  }}
  selectedLayer = layer;
  layer.setStyle({{ weight: 2, color: '#ffffff', fillOpacity: 0.95 }});

  const p = layer.feature.properties;
  document.getElementById('m-side-title').textContent = p.name;
  document.getElementById('m-side-badge').textContent = `${{p.count}} 项服务`;
  document.getElementById('m-side-sub').textContent = p.count > 0 
    ? `收录 ${{p.count}} 条空间服务 · ${{p.verified}} 条实测已验证`
    : `当前地区暂未收录独立空间服务`;

  currentMapServices = MAP_DATA.intl_services[p.iso] || [];
  filterAndRenderMapList();
  map.fitBounds(layer.getBounds(), {{ maxZoom: 6, padding: [30, 30] }});
}}

function selectMapProvince(layer) {{
  if (selectedLayer && selectedLayer !== layer) {{
    provinceLayer.resetStyle(selectedLayer);
  }}
  selectedLayer = layer;
  layer.setStyle({{ weight: 2, color: '#ffffff', fillOpacity: 0.95 }});

  const p = layer.feature.properties;
  document.getElementById('m-side-title').textContent = p.name;
  document.getElementById('m-side-badge').textContent = `${{p.count}} 项服务`;
  document.getElementById('m-side-sub').textContent = p.count > 0 
    ? `包含该省/直辖市及所属地级市的公共数据与空间服务`
    : `当前省份主要调用国家级数据服务接口 (如天地图/国家气象网)`;

  currentMapServices = MAP_DATA.prov_services[p.short] || [];
  filterAndRenderMapList();
  map.fitBounds(layer.getBounds(), {{ maxZoom: 7, padding: [40, 40] }});
}}

function drillDownToChina() {{
  currentMapLevel = 'china_province';
  map.removeLayer(worldLayer);
  if (!provinceLayer) {{
    function provStyle(f) {{
      const cnt = f.properties.count || 0;
      return {{
        fillColor: getMonoColor(cnt, true),
        weight: 1,
        opacity: 0.85,
        color: '#525252',
        fillOpacity: cnt > 0 ? 0.8 : 0.35
      }};
    }}
    function onEachProv(f, layer) {{
      const p = f.properties;
      layer.bindTooltip(`<b>[ ${{p.name}} ]</b><br>收录: ${{p.count}} 项省/市级服务`, {{ sticky: true, opacity: 0.95 }});
      layer.on({{
        mouseover: e => {{
          if (e.target !== selectedLayer) e.target.setStyle({{ weight: 2, color: '#ffffff', fillOpacity: 0.95 }});
        }},
        mouseout: e => {{
          if (e.target !== selectedLayer) provinceLayer.resetStyle(e.target);
        }},
        click: e => selectMapProvince(e.target)
      }});
    }}
    provinceLayer = L.geoJson(MAP_DATA.provinces_geo, {{
      style: provStyle,
      onEachFeature: onEachProv
    }});
  }}
  provinceLayer.addTo(map);

  document.getElementById('mbtn-drillup').style.display = 'flex';
  document.getElementById('mbtn-world').classList.remove('act');
  document.getElementById('mbtn-china').classList.add('act');
  document.getElementById('mbtn-global').style.display = 'none';

  document.getElementById('mlegend-title').textContent = '中国省级服务收录量';
  document.getElementById('mlegend-steps').innerHTML = `
    <div class="map-scale-step"><div class="map-scale-block" style="background:#141414;"></div>0</div>
    <div class="map-scale-step"><div class="map-scale-block" style="background:#404040;"></div>1-2</div>
    <div class="map-scale-step"><div class="map-scale-block" style="background:#8c8c8c;"></div>3-4</div>
    <div class="map-scale-step"><div class="map-scale-block" style="background:#e0e0e0;"></div>5+</div>
  `;

  document.getElementById('m-side-title').textContent = "中国全国空间数据与省级分布";
  document.getElementById('m-side-badge').textContent = `${{(MAP_DATA.world_geo.features.find(f=>f.properties.iso==='CN')||{{properties:{{count:0}}}}).properties.count}} 项收录`;
  document.getElementById('m-side-sub').textContent = "坚持一个中国原则，涵盖台湾省、香港、澳门及全国34个省级行政区空间开放数据。点击任意省区可查看属地化服务。";

  currentMapServices = MAP_DATA.china_national;
  filterAndRenderMapList();
  map.setView([35.86, 104.19], 4);
}}

function drillUpToWorld() {{
  currentMapLevel = 'world';
  if (provinceLayer) map.removeLayer(provinceLayer);
  worldLayer.addTo(map);

  document.getElementById('mbtn-drillup').style.display = 'none';
  document.getElementById('mbtn-world').classList.add('act');
  document.getElementById('mbtn-china').classList.remove('act');
  document.getElementById('mbtn-global').style.display = 'flex';

  document.getElementById('mlegend-title').textContent = 'GIS 服务收录量密度';
  document.getElementById('mlegend-steps').innerHTML = `
    <div class="map-scale-step"><div class="map-scale-block" style="background:#0d0d0d;"></div>0</div>
    <div class="map-scale-step"><div class="map-scale-block" style="background:#262626;"></div>1-10</div>
    <div class="map-scale-step"><div class="map-scale-block" style="background:#525252;"></div>10-100</div>
    <div class="map-scale-step"><div class="map-scale-block" style="background:#8c8c8c;"></div>100-500</div>
    <div class="map-scale-step"><div class="map-scale-block" style="background:#e0e0e0;"></div>500+</div>
  `;

  displayMapGlobalPool();
}}

document.getElementById('mbtn-drillup').addEventListener('click', drillUpToWorld);
document.getElementById('mbtn-world').addEventListener('click', () => {{
  if (currentMapLevel === 'china_province') drillUpToWorld();
}});
document.getElementById('mbtn-china').addEventListener('click', () => {{
  if (currentMapLevel !== 'china_province') drillDownToChina();
}});

function displayMapGlobalPool() {{
  if (selectedLayer && worldLayer) {{
    worldLayer.resetStyle(selectedLayer);
    selectedLayer = null;
  }}
  document.getElementById('m-side-title').textContent = MAP_DATA.global_data.name;
  document.getElementById('m-side-badge').textContent = `${{MAP_DATA.global_data.count}} 汇聚项`;
  document.getElementById('m-side-sub').textContent = "涵盖 NASA、ESA、OpenStreetMap、STAC 等全球性开放空间数据接口";
  currentMapServices = MAP_DATA.global_data.services || [];
  filterAndRenderMapList();
  map.setView([28, 20], 3);
}}

document.getElementById('mbtn-global').addEventListener('click', displayMapGlobalPool);

function filterAndRenderMapList() {{
  const q = document.getElementById('m-search').value.toLowerCase().trim();
  const proto = document.getElementById('m-proto').value.toLowerCase().trim();

  const filtered = currentMapServices.filter(s => {{
    const matchQ = !q || (s.name && s.name.toLowerCase().includes(q)) || 
                         (s.desc && s.desc.toLowerCase().includes(q)) || 
                         (s.url && s.url.toLowerCase().includes(q));
    const matchProto = !proto || (s.proto && s.proto.toLowerCase().includes(proto));
    return matchQ && matchProto;
  }});

  const container = document.getElementById('m-services-list');
  if (!filtered || filtered.length === 0) {{
    container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--mut);">暂无匹配的空间服务条目</div>';
    return;
  }}

  container.innerHTML = filtered.map(s => `
    <div class="map-service-card">
      <div class="map-card-head">
        <div class="map-card-name">${{esc(s.name)}}</div>
        <span class="badge v-${{s.status}}">${{s.status}}</span>
      </div>
      <div style="margin:4px 0;">
        <span class="tag">${{esc(s.proto)}}</span>
        ${{s.cat ? `<span class="tag">${{esc(s.cat)}}</span>` : ''}}
        ${{s.scope ? `<span class="tag">${{esc(s.scope)}}</span>` : ''}}
        ${{s.free === '是' ? '<span class="tag">免费</span>' : ''}}
        ${{s.nokey === '是' ? '<span class="tag">免Key</span>' : ''}}
      </div>
      ${{s.desc ? `<div class="map-card-desc">${{esc(s.desc)}}</div>` : ''}}
      <div class="map-url-box">
        <div class="map-url-text" title="${{esc(s.url)}}">${{esc(s.url)}}</div>
        <button class="map-copy-btn" onclick="navigator.clipboard.writeText('${{esc(s.url)}}');alert('已复制！');">复制</button>
      </div>
    </div>
  `).join('');
}}

document.getElementById('m-search').addEventListener('input', filterAndRenderMapList);
document.getElementById('m-proto').addEventListener('change', filterAndRenderMapList);

// Tab 切换逻辑
document.querySelectorAll('.tab').forEach(t => t.onclick = () => {{
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('act'));
  t.classList.add('act');
  ['db', 'map', 'help'].forEach(p => {{
    const el = document.getElementById('pane-' + p);
    if (el) el.classList.add('hidden');
  }});
  const activePane = document.getElementById('pane-' + t.dataset.t);
  if (activePane) activePane.classList.remove('hidden');

  if (t.dataset.t === 'map') {{
    initMap();
    setTimeout(() => map && map.invalidateSize(), 150);
  }}
}});

render();
</script>
</body>
</html>
"""

print("Writing updated unified viewer.html...")
HTML.write_text(html_content, encoding="utf-8", newline="")
print(f"viewer.html successfully updated! ({HTML.stat().st_size / 1024 / 1024:.2f} MB)")
