#!/usr/bin/env python3
"""从 gis_services.db 重新生成 viewer.html 的内嵌数据与统计块。

viewer.html 里的 DATA / ST 是写死的 JSON 快照，扩库后不会自动跟着变。
本脚本按固定的分隔标记定位并整段替换，保留页面其余部分（CSS / HTML / 渲染逻辑）。

用法：python scripts/build_viewer.py
"""
import json
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "gis_services.db"
HTML = ROOT / "viewer.html"

# master 列 -> viewer 短字段名，顺序即 JSON 里字段的输出顺序
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

STATS = """
// stats
document.getElementById('stats').innerHTML = [
  ['总记录', ST.total], ['已验证', ST.verified], ['协议级强证据', ST.strong],
  ['未验证', ST.unverified], ['覆盖国家/地区', ST.countries],
  ['无需注册+免费+可API', ST.direct]
].map(([k,v])=>`<div class="stat"><b>${v}</b><div style="color:var(--mut);font-size:11px">${k}</div></div>`).join('');
"""

OLD_STATS_RE = re.compile(
    r"\r?\n// stats\r?\ndocument\.getElementById\('stats'\)\.innerHTML = \[.*?\.join\(''\);\r?\n",
    re.S,
)


def build_data(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(master)")]
    missing = [c for c, _ in FIELD_MAP if c not in cols]
    if missing:
        raise SystemExit(f"master 缺列，viewer 会渲染空白：{missing}")

    rows = []
    for rec in conn.execute(f"SELECT {','.join(c for c, _ in FIELD_MAP)} FROM master"):
        d = {}
        for (col, short), val in zip(FIELD_MAP, rec):
            if val is not None:
                d[short] = str(val)
        rows.append(d)
    return rows


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


def main():
    conn = sqlite3.connect(DB)
    data = build_data(conn)
    st = build_stats(conn)
    conn.close()

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    html = HTML.read_text(encoding="utf-8", newline="")

    m = re.search(r"\bDATA\s*=\s*\[", html)
    if not m:
        raise SystemExit("viewer.html 里找不到 DATA 赋值标记")
    st_pos = html.index("const ST", m.end())
    # DATA 数组的结尾是 ST 声明之前最后一个 "];"，不能用 index() 往后找——
    # 后面的 chips 数组也以 "];" 结尾，会连带吃掉中间整段脚本。
    # 停在 "]" 而非 "];" 上，让数组的收尾 ";;" 留在 html 里继续往后拼。
    end = html.rindex("];", 0, st_pos) + 1
    html = html[: m.start()] + "DATA   = " + payload + html[end:]

    html = re.sub(r"const ST\s*=\s*\{.*?\};", "const ST   = " + json.dumps(st) + ";", html, count=1, flags=re.S)
    html, n = OLD_STATS_RE.subn(STATS, html, count=1)
    if n != 1:
        raise SystemExit("viewer.html 里找不到统计渲染块")

    # 备注/描述可能含 < > & $ {，插入 DOM 前必须转义，否则会破坏页面
    html = html.replace("['备注',d.notes]", "['备注',esc(d.notes)]")
    html = html.replace("['数据描述',d.desc]", "['数据描述',esc(d.desc)]")
    html = html.replace("['图层/端点',d.layer]", "['图层/端点',esc(d.layer)]")

    html = re.sub(r"已 HTTP 实测验证 · 更新日期 \d{4}-\d{2}-\d{2}",
                  "已 HTTP 实测验证 · 更新日期 " + st["today"], html)

    with HTML.open("w", encoding="utf-8", newline="") as f:
        f.write(html.replace("\r\n", "\n"))
    print(f"viewer.html 已更新：{len(data)} 条记录，{len(payload)/1048576:.1f} MB 数据块，{HTML.stat().st_size/1048576:.1f} MB 文件")
    print("统计：", st)


if __name__ == "__main__":
    main()