# GeoSource MCP 🌍

<p align="center">
  <b>A Model Context Protocol (MCP) Server for Global GIS Services & Spatial Layers</b><br>
  <b>面向全球 GIS 空间服务与图层目录的 MCP 标准数据检索接口</b>
</p>

<p align="center">
  <a href="#english">English</a> •
  <a href="#chinese">中文说明</a>
</p>

<p align="center">
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-Model%20Context%20Protocol-blue.svg" alt="MCP"></a>
  <a href="https://glama.ai/mcp/servers"><img src="https://img.shields.io/badge/Glama-Approved-10b981.svg" alt="Glama Approved"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10+-brightgreen.svg" alt="Python"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/Catalog-11%2C054%20Services-blue.svg" alt="Services">
  <img src="https://img.shields.io/badge/Verified-5%2C771%20Active-green.svg" alt="Verified">
  <img src="https://img.shields.io/badge/Layers-18%2C292-purple.svg" alt="Layers">
  <a href="https://mcpservers.org/servers/wukeeeeee/geosource-mcp"><img src="https://mcpservers.org/badge.svg"></a>
</p>

> 🗺️ **交互与检索看板**: 访问 [viewer.html](viewer.html) 即可在纯黑白灰工程风界面中查询 11,054 条空间服务，或切换到「全球态势地图」进行多边形面交互与中国 34 省级行政区无缝下钻。

---

<a name="english"></a>
## 🌐 English

### Overview
**GeoSource MCP** is an open-source [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server providing structured access to an indexed catalog of **11,054 global GIS spatial services** and **18,292 sub-layers**.

When developers build maps, spatial analysis pipelines, or GIS crawlers using AI assistants (Claude Desktop, Cursor, Windsurf, etc.), large language models frequently struggle to locate real-world endpoints or generate non-functional URLs. GeoSource MCP connects AI environments directly to an indexed local SQLite database (`gis_services.db`), enabling low-latency, multi-criteria discovery of verified spatial services across OGC WMS, WFS, WMTS, XYZ Tiles, ArcGIS REST, STAC, and Open Data APIs.

### Key Engineering Features
- **Structured Discovery**: Helps AI models locate existing, functional endpoints rather than guessing URLs.
- **Interactive Global Map & Explorer**: Browse services visually via [viewer.html](viewer.html) with dark brutalist monochrome aesthetics, boundary polygon highlighting, One-China compliant provincial drilldown, and one-click URL copying.
- **Low-Overhead Retrieval**: Fetches only matching records (typically 200 ~ 500 tokens per search) on demand, avoiding the cost and latency of loading megabytes of raw files into prompts.
- **Transparent Verification**: Tracks explicit availability statuses, each backed by a recorded method in `verify_method`:
  - **5,771 Verified Active**: Confirmed accessible. 4,749 of them carry protocol-level proof (a WMS that actually returns `WMS_Capabilities`, a STAC API that returns `stac_version`, an ArcGIS REST service document).
  - **5,245 Pending / Unverified**: Cataloged entries whose portal is reachable but no anonymous protocol-level endpoint was found in a six-path probe (GeoServer/CKAN/ArcGIS Hub/REST/GeoNode/Socrata); each entry records the probe result in `notes`.
  - **54 Deprecated / Inactive**: Documented legacy services retained for reference.
  - A failed probe never downgrades an entry on its own: a single failure cannot distinguish a dead service from a blocked cross-border route or UA filtering, so the reason is recorded instead.
- **Two-Way Maintenance**: Supports Excel synchronization and provides tools for AI agents to report status updates and new endpoints.

### Catalog Contents & Protocols

| Category | Protocols Supported | Notable Data Sources |
| :--- | :--- | :--- |
| **Open Data Portals (9,832)** | CKAN, DKAN, ArcGIS Hub, REST API, HTTP download | Data.gov, Eurostat, Thai DSD, Indonesian Satu Data, county/municipal ArcGIS hubs |
| **OGC Standard Services (687)** | WMS 1.1.1/1.3.0, WFS 1.0/2.0, WMTS 1.0.0, OGC API Features/Records | PDOK (Netherlands), geo.admin.ch (Switzerland), municipal GeoServers worldwide |
| **ArcGIS Platforms (295)** | ArcGIS Server REST, FeatureServer, MapServer, ImageServer | Esri Living Atlas, federal & municipal ArcGIS REST endpoints |
| **Basemap Tiles (86)** | XYZ Slippy Maps, TMS, WMTS, PMTiles, Entwine | OpenStreetMap, Carto, Stadia, OpenTopoMap, MapTiler |
| **Remote Sensing / STAC (72)** | STAC API 1.0, OGC API Records, COG | Earth Search, Microsoft Planetary Computer, USGS Landsat |
| **3D Geospatial (20)** | 3D Tiles, CityGML, I3S, Cesium terrain | Cesium ion open assets, municipal 3D building models |
| **Transit & Routing (14)** | GTFS, GTFS-RT, OSRM, Valhalla | OpenRouteService, Transitland, city transit agencies |

Protocol strings are grouped by family and overlap slightly (e.g. an ArcGIS Hub portal is also an
open-data portal). A per-category breakdown is available from `list_categories_and_stats`; the
catalog spans **319 countries/regions** across **102 categories**.

### Available MCP Tools

| Tool | Parameters | Purpose |
| :--- | :--- | :--- |
| `search_gis_services` | `keyword`, `country`, `protocol`, `category`, `is_free`, `need_no_key`, `status`, `limit` | Searches services based on multiple criteria with case-insensitive matching. |
| `get_service_detail` | `service_id` | Retrieves full metadata (50+ fields) and child layers for a specific service ID (case-insensitive). |
| `list_categories_and_stats` | *(None)* | Returns summary statistics of categories, protocols, countries, and verification statuses. |
| `query_gis_sql` | `query` | Executes safe, read-only `SELECT` queries against the SQLite database (capped at 100 rows). |
| `probe_service_api` | `service_id`, `url`, `timeout` | **Live-probes** an entry and auto-detects its open-data platform (CKAN / DKAN / ArcGIS Hub / Socrata), returning the working JSON API entry. Use before recommending an unverified portal. |
| `update_service_status` | `service_id`, `new_url`, `status`, `notes` | Updates service availability, URLs, or notes with validated status enums. |

### Verification Scripts

Two scripts back the "verified" claims with real evidence rather than a bare HTTP 200:

```bash
# Platform detection for open-data portals -> writes the real API URL into service_url
python scripts/probe_portal_api.py --dry-run            # probe only
python scripts/probe_portal_api.py --apply --workers 20 # probe and write back

# Protocol-aware service verification -> writes status / verify_method / last_verified
python scripts/verify_services.py --limit 50             # no --apply means probe only
python scripts/verify_services.py --apply --workers 20
python scripts/verify_services.py --apply --only-status 已验证   # re-audit existing claims
```

`verify_services.py` checks that a service answers *in its declared protocol* — a WMS endpoint must
return `WMS_Capabilities`, a STAC endpoint must return `stac_version`, an ArcGIS REST endpoint must
return a `?f=json` service document, and so on. Results are graded `strong` (protocol-level proof) or
`weak` (reachable but unproven), and the grade is stored in `verify_method`.

The detection rules for each platform:

| Platform | Probe | Positive signal |
| :--- | :--- | :--- |
| CKAN | `GET {root}/api/3/action/status_show` | `"ckan_version"` in JSON |
| DKAN | `GET {root}/api/3/action/package_search?rows=1` | `"result"` + `"success": true` |
| ArcGIS Hub | `GET {root}/api/v3/datasets?page[size]=1` | `"data"` array in JSON |
| Socrata | `GET {root}/api/catalog/v1` | dataset array or `resultsSetSize` |

A third script keeps the offline viewer in step with the database:

```bash
# Rebuild the inlined dataset inside viewer.html from gis_services.db -> always run after a DB change
python scripts/build_viewer.py
```

`scripts/verify_endpoints.py` is a separate, read-only reachability check (`--sample N` or `--id
WMS-0001`). It reports HTTP status only and never writes to the database.

### Chinese Government Portals Are a Different Animal

Domestic 省市"公共数据开放平台" do not run CKAN-style catalogs. `scripts/probe_cn_portals.py`
handles them separately (matches entries whose URL is under `gov.cn`):

- **DExchangeOpen** (Yinchuan, Xuzhou, …): Vue SPA; the real gateway is
  `{root}/dexchangeOpen/appauth/getappid` — live, but every data call requires SSO login
  and an `appId` token, so anonymous API access returns `{"code":401,"msg":"sso not login."}`.
- **Jspm platform** (Dongying, Binzhou, Weihai, Shandong, …): server-rendered pages with the
  data catalog HTML delivered directly (`/{city}/catalog/`). There is no public JSON search API
  to register; the site itself is the interface.
- Entries whose domain no longer resolves anywhere (checked against both the local resolver and
  AliDNS DoH `223.5.5.5`) are recorded as `cn-probe:dns-dead` in `verify_method` with the evidence
  in `notes` — status is left untouched, because several cities folded their portals into
  provincial platforms (e.g. Guangdong's `gddata.gd.gov.cn`, Jiangsu's `data.jiangsu.gov.cn`)
  and the entry should follow the new address rather than be declared dead.

Statuses after the 2026-09-30 pass over 118 domestic entries: 96 alive (13 with a concrete API or
catalog URL written into `service_url`), 12 domains confirmed gone.

```bash
python scripts/probe_cn_portals.py            # probe only
python scripts/probe_cn_portals.py --apply    # write back status/verify_method/notes
```

### Bulk Harvesting from a Portal Registry

The 2026-10-02 expansion admitted 8,845 services in one pass by harvesting the
[dataportals-registry](https://github.com/datenoio/dataportals-registry) (43k catalog records),
filtering to geospatial platforms, de-duplicating against `service_url` domains already in the
database, then live-probing every remaining host with the platform-appropriate request
(`/api/3/action/status_show` for CKAN, `/api/v3/datasets` for ArcGIS Hub, `/geoserver/wms` for
GeoServer, …). Roughly 35,000 real HTTP requests ran; only hosts returning a protocol-level
response were admitted as `protocol-probe:strong`, and hosts answering with a real page but no
discoverable endpoint were admitted as `protocol-probe:weak` with the reason recorded in `notes`.

Two failure modes worth knowing if you rerun this:

- Writing a URL list from Python in text mode leaves `\r` line endings, which makes every `curl`
  call fail with HTTP 000 in ~0.03 ms — it looks exactly like "every host is dead". Strip them
  (`tr -d '\r'`) or write with `newline='\n'`.
- CKAN returns `"success":true` with no space. Matching on `"success": true` silently drops
  hundreds of live CKAN portals.

The admission scripts are kept per batch under `scripts/add_new_sources_*.py`.

### Catalog Maintenance Pass (2026-10-02)

A data-quality pass normalized the catalog after the bulk harvest:

- `verify_method` was reduced from 40 ad-hoc strings to 8 canonical values
  (`protocol-probe:strong|weak|unreachable`, `metadata-only`, `cn-probe:*`); the original free-text
  evidence was preserved in `notes`.
- `protocol` was normalized from 132 spellings to 40 protocol families (e.g. `OGC WMS 1.3.0` and
  `ArcGIS WMS` both fold into `OGC WMS`); originals are recorded in `notes` as `[protocol归一]`.
- 5,097 portal entries that only pointed at a homepage were re-probed with six common service paths
  (~30k requests). 239 entries were upgraded to `protocol-probe:strong` with the discovered endpoint
  written into `service_url`; 4,668 homepages-only entries were honestly re-classified as
  **未验证** with the probe result in `notes`.
- `crs` no longer claims `EPSG:4326` where it was a placeholder: platform-API portals read
  `随数据集`, and WMS/WFS rows carry the CRS list parsed from their live Capabilities (254 rows);
  unresolved ones are marked 待复测.
- Layers: WMS/WFS GetCapabilities responses were parsed and their layer lists inserted, growing
  `layers` from 1,561 to **18,292** rows across 1,201 services.

### `viewer.html` Is a Build Artifact (2026-10-03)

`viewer.html` is a single self-contained offline browser UI — its dataset is **inlined as a JSON
literal**, not fetched at runtime. It does not track the database: through the entire bulk harvest
it still showed the 2026-09-29 snapshot (2,198 records / 1,495 verified) while the catalog held
11,054 / 5,755. Regenerate it after any database change:

```bash
python scripts/build_viewer.py
```

The script locates the `DATA = [...]` block and the `ST` stats object by marker and replaces only
those, so the page's CSS, markup and static help text survive. It is idempotent — running it twice
produces the same file. Two things it also fixes:

- The detail panel used to splice `data_description`, `layer_or_endpoint` and `notes` straight into
  `innerHTML`; bulk-harvested notes legitimately contain `$` and `>`, which broke the page. All three
  are escaped now.
- The stats bar gains a **protocol-level strong evidence** column (4,749) alongside the others.

Gotchas if you modify the generator: find the end of the `DATA` array with
`rindex("];", 0, <position of "const ST">)` — searching *forward* with `index` matches the `];` of
the later `chips` array and silently deletes the whole script between them. And stop the replaced
slice at `]`, not `];`, so the array's own terminator is preserved.

### Connectivity Baseline (2026-10-03)

A 500-row random sample of verified services, probed with real requests at 40-way concurrency,
returned **97.2% reachable** (p50 2.0 s, p90 2.9 s). Read that number with care: 12 of the 14
non-200 responses were `400` (endpoint requires parameters), `401`/`403` (API key required or
bot-blocking) or `412`/`418` (WAF) — all of which prove the server is alive. Only **2 endpoints
(0.4%) genuinely timed out**. Per the project rule, a single failed probe never downgrades an entry,
so no status was changed.

70 catalog rows (`TILE-*`, `HIST-*`) carry `{z}/{x}/{y}` placeholders in `service_url`. That is the
standard published form for a tile endpoint, not an error, but a probe must substitute real tile
numbers to mean anything: with `z=11` substituted, 24 of the 44 verified tile services returned a
real 200 image, and the rest answered 401/403 for want of a key — which the catalog already records.


### Getting Started

#### 1. Requirements & Installation
Requires Python 3.10+:
```bash
git clone https://github.com/Wukeeeeee/GeoSource-MCP.git
cd GeoSource-MCP
pip install -r requirements.txt
```

#### 2. Run Self-Test
Verify that the database and all MCP tools function as expected:
```bash
python server.py --test
```
You should see: `[TEST] All tests passed! Ready for MCP clients.`

#### 3. Client Configuration

##### Claude Desktop
Add to your `claude_desktop_config.json`:
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "geosource": {
      "command": "python",
      "args": ["<FULL_PATH_TO_GEOSOURCE>/server.py"]
    }
  }
}
```

##### Cursor / IDEs
In your IDE's MCP settings, add a new stdio server:
- **Command**: `python`
- **Args**: `<FULL_PATH_TO_GEOSOURCE>/server.py`

---

<a name="chinese"></a>
## 🇨🇳 中文说明

### 项目简介
**GeoSource MCP** 是一个基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io) 标准的开源数据服务程序。它为各类 AI 编程与分析助手（Claude Desktop、Cursor、Windsurf 等）提供对本地结构化索引的 **11,054 个全球真实 GIS 空间服务** 与 **18,292 个地图图层** 的检索工具。

在开发地图应用或编写空间数据处理脚本时，大模型通常无法准确掌握全球各机构公开的实时服务接口，容易推断出不可用的链接。GeoSource MCP 直接连接本地 SQLite 数据库（`gis_services.db`），帮助 AI 快速检索真实的可用服务与图层参数。

### 工程特性与设计原则
- **结构化发现，降低幻觉**：提供经过结构化收录的真实服务端点，辅助 AI 编写准确的地图调用代码。
- **集成全球态势地图与属地化下钻**：在 [viewer.html](viewer.html) 内置直角黑白灰工程风交互地图，支持国际版图多边形高亮交互，严格遵循一个中国原则并支持全国 34 省级行政区无缝下钻与服务条目筛选复制。
- **按需低开销检索**：每次仅检索返回匹配的 3~5 条记录（约 200~500 Tokens），避免将数兆字节的原始表格强行填入上下文窗口。
- **透明的可用性状态**（每条的验证方式都记录在 `verify_method` 字段，可逐条追溯）：
  - **已验证**（5,771 条）：经探测确认为可用。其中 4,749 条带**协议级实证**——WMS 真的返回了 `WMS_Capabilities`、STAC 真的返回了 `stac_version`、ArcGIS REST 真的返回了服务文档。
  - **未验证**（5,245 条）：门户可达但未探到匿名可调用的协议级接口（六条常见路径探测无果），或受跨国网络连通性限制；每条的探测结果都写在 `notes`。
  - **已停止**（54 条）：已下线或历史归档服务，保留供查阅追溯。
  - **探测失败不会直接改判为"未验证"**：单次失败无法区分"服务真下线"、"本地到该站的跨境链路被阻断"、"对脚本 UA 返回 403 但浏览器正常"这三种情况，因此只记录失败原因，保留原状态。
- **双向维护支持**：支持与 Excel 表格双向数据同步，并提供更新接口供 AI 助手汇报失效链接与新地址。

### 数据分类与协议支持

| 分类 | 协议类型 | 典型代表 |
| :--- | :--- | :--- |
| **开放数据门户 (9,832 条)** | CKAN, DKAN, ArcGIS Hub, REST API, HTTP 下载 | Data.gov、欧盟数据门户、开放广东、泰国 DSD、印尼 Satu Data、各县市开放数据门户 |
| **OGC 标准服务 (687 条)** | OGC WMS (1.1.1/1.3.0), WFS, WMTS, OGC API Features/Records | 荷兰 PDOK、瑞士联邦地图、芬兰测绘局，以及各国市政 GeoServer |
| **ArcGIS 平台 (295 条)** | ArcGIS REST (MapServer, FeatureServer, ImageServer) | Esri Living Atlas、各国政府与水务气象机构 REST 服务 |
| **底图瓦片 (86 条)** | XYZ 栅格瓦片, TMS, WMTS, PMTiles, Entwine | OpenStreetMap, Carto, Stadia Maps, OpenTopoMap |
| **遥感时空资产 (72 条)** | STAC API 1.0, OGC API Records, COG | Earth Search、行星计算机、USGS Landsat |
| **三维空间数据 (20 条)** | 3D Tiles, CityGML, I3S, Cesium terrain | Cesium ion 开放资产、城市级白模与倾斜摄影服务 |
| **交通与路网 (14 条)** | GTFS, GTFS-RT, OSRM, Valhalla | OpenRouteService、Transitland、各地铁公交调度 API |

协议按族群归类、彼此有少量重叠（例如 ArcGIS Hub 门户同时也算开放数据门户）。按细分类目的实时
分布可通过 `list_categories_and_stats` 获取；当前目录覆盖 **319 个国家/地区**、**102 个分类**。

### MCP 工具一览

| 工具名称 | 输入参数 | 功能说明 |
| :--- | :--- | :--- |
| `search_gis_services` | `keyword`, `country`, `protocol`, `category`, `is_free`, `need_no_key`, `status`, `limit` | 多条件筛选查询空间服务（支持大小写无关模糊匹配）。 |
| `get_service_detail` | `service_id` | 获取该服务的 50 余项详细元数据与关联子图层列表。 |
| `list_categories_and_stats` | 无 | 获取数据库总体量、各大类、协议分布及验证状态统计。 |
| `query_gis_sql` | `query` | 对 SQLite 数据库执行只读 `SELECT` SQL 查询（内置上限 100 行保护）。 |
| `probe_service_api` | `service_id`, `url`, `timeout` | **实时探测**条目是否真的可访问，并自动识别底层平台（CKAN / DKAN / ArcGIS Hub / Socrata），返回真正能调用的 JSON 接口地址。推荐未验证的门户前先调用它，避免给出死链。 |
| `update_service_status` | `service_id`, `new_url`, `status`, `notes` | 经枚举校验后更新服务的可用状态、新 URL 或备注信息。 |

### 数据可信度是怎么做出来的

"已验证"不是随手贴的标签，而是有脚本用真实请求跑出来的。两个脚本：

```bash
# 1) 门户接口识别：探测底层平台，把真正能调用的 API 地址写回 service_url
python scripts/probe_portal_api.py --dry-run            # 只探测不写库
python scripts/probe_portal_api.py --apply --workers 20 # 探测并回写

# 2) 协议级可用性验证：写回 status / verify_method / last_verified
python scripts/verify_services.py --limit 50             # 不加 --apply 即为只探测
python scripts/verify_services.py --apply --workers 20
python scripts/verify_services.py --apply --only-status 已验证   # 复审已有的"已验证"
```

`verify_services.py` 判断的是"服务是否以它声明的协议应答"，而不只是"网址能不能打开"：
WMS 必须返回 `WMS_Capabilities`，STAC 必须返回 `stac_version`，ArcGIS REST 必须返回 `?f=json`
的服务文档。结果分两档——`strong`（协议级实证）和 `weak`（能连通但未证实），
档位写进 `verify_method` 字段，任何人都能查某条记录的"已验证"是怎么来的。

各平台的识别规则：

| 平台 | 探测地址 | 判定依据 |
| :--- | :--- | :--- |
| CKAN | `GET {root}/api/3/action/status_show` | JSON 中含 `"ckan_version"` |
| DKAN | `GET {root}/api/3/action/package_search?rows=1` | 含 `"result"` 且 `"success": true` |
| ArcGIS Hub | `GET {root}/api/v3/datasets?page[size]=1` | JSON 中含 `"data"` 数组 |
| Socrata | `GET {root}/api/catalog/v1` | 数据集数组或 `resultsSetSize` 字段 |

还有第三个脚本负责让离线查询页跟上数据库：

```bash
# 3) 重新生成 viewer.html 内嵌的数据 -> 改库后必须执行
python scripts/build_viewer.py
```

`scripts/verify_endpoints.py` 是另一个只读的连通性抽查工具（`--sample N` 或 `--id WMS-0001`），
它只报 HTTP 状态码，永远不写库。

### 从门户登记册批量扩库（2026-10-02）

本轮一次性入库 8,845 条，靠的是 [dataportals-registry](https://github.com/datenoio/dataportals-registry)
（4.3 万条门户记录）：筛出地理空间类平台 → 与库内已有域名去重 → 对每个候选主机发**符合其平台的真实请求**
（CKAN 打 `/api/3/action/status_show`，ArcGIS Hub 打 `/api/v3/datasets`，GeoServer 打 `/geoserver/wms` 等）。
累计发出约 3.5 万次真实请求，只有返回协议级应答的才按 `protocol-probe:strong` 收录；
只返回真实页面、探不到接口的按 `protocol-probe:weak` 收录并在 `notes` 写明原因。

重跑这套流程时有两个坑：

- 用 Python 文本模式写 URL 清单会带上 `\r` 行尾，`curl` 全部报 HTTP 000、耗时 0.03ms，
  看起来像"全站都死了"。要么 `tr -d '\r'` 清洗，要么写文件时加 `newline='\n'`。
- CKAN 返回的是 `"success":true`（无空格）。按 `"success": true`（带空格）匹配会静默漏掉
  几百个活着的 CKAN 门户。

各批次入库脚本留档在 `scripts/add_new_sources_*.py`。

### 数据维护批次（2026-10-02）

批量扩库之后做了一轮数据质量整修：

- `verify_method` 从 40 种随手写法归一成 8 个规范枚举（`protocol-probe:strong|weak|unreachable`、
  `metadata-only`、`cn-probe:*`），原始证据文本移入 `notes` 保留。
- `protocol` 从 132 种拼法归一成 40 个协议族（如 `OGC WMS 1.3.0`、`ArcGIS WMS` 都并入 `OGC WMS`），
  原值以 `[protocol归一]` 标记写进 `notes`。
- 对 5,097 个只指向首页的门户条目补测六条常见服务路径（约 3 万次请求）：239 条找到了真实接口、
  升级为 `protocol-probe:strong` 并把接口写进 `service_url`；4,668 条只有首页可达，如实降为
  **未验证**，探测结果记录在 `notes`。
- `crs` 不再拿 `EPSG:4326` 当占位符：平台型 API 门户标为 `随数据集`；WMS/WFS 按在线 Capabilities
  解析真实 CRS（254 条），解析不出的标 `待复测`。
- 图层：解析 WMS/WFS GetCapabilities 并回填 `layers` 表，从 1,561 行增至 **18,292 行**，
  覆盖 1,201 个服务。

### viewer.html 是生成物（2026-10-03）

`viewer.html` 是一个单文件、离线可用的浏览器查询界面，但里面的数据是**内嵌的 JSON 字面量**，
不会运行时去读数据库——整个批量扩库期间它一直显示 9/29 的快照（2,198 条 / 已验证 1,495），
而库里早已是 11,054 / 5,755。**改库之后必须重新生成**：

```bash
python scripts/build_viewer.py
```

脚本按标记定位 `DATA = [...]` 与 `ST` 统计块，只替换这两段，页面的 CSS、结构和静态说明文字不动。
可重复执行，跑两次结果一致。它同时修掉两个问题：详情面板原先把 `data_description`、
`layer_or_endpoint`、`notes` 直接拼进 `innerHTML`，而批量入库的备注里确实有 `$`、`>` 这类字符，
会破坏页面，现已统一转义；统计栏新增**协议级强证据**一栏（4,749）。

若要改这个生成器，有两个坑：DATA 数组的结尾要用 `rindex("];", 0, <"const ST" 的位置>)` 往前找，
用 `index` 往后找会撞上后面 chips 数组的 `];`，把中间整段脚本悄悄删掉；替换区间要停在 `]` 而不是
`];`，否则数组自己的收尾分号会被一并删掉。

### 联通测试基线（2026-10-03）

随机抽 500 条已验证服务、40 并发发真实请求，**可达率 97.2%**（p50 2.0 秒、p90 2.9 秒）。这个数字要
这么读：14 条非 200 里有 12 条是 `400`（端点缺必填参数）、`401`/`403`（要 API Key 或反爬）、
`412`/`418`（WAF 防护）——它们恰恰证明服务器活着。**真正超时的只有 2 条（0.4%）**。按项目铁律，
单次探测失败不改判，因此未改动任何条目的状态。

目录里有 70 条（`TILE-*`、`HIST-*`）的 `service_url` 含 `{z}/{x}/{y}` 占位符。这是瓦片服务的标准
发布形式、不是错误，但探测时必须替换成真实瓦片号才有意义：代入 `z=11` 后，44 条已验证瓦片服务里
24 条返回了真实的 200 图片，其余 401/403 是缺 Key——而这一点目录里本来就有标注。


### 快速开始

#### 1. 安装依赖
```bash
git clone https://github.com/Wukeeeeee/GeoSource-MCP.git
cd GeoSource-MCP
pip install -r requirements.txt
```

#### 2. 本地快速自测
```bash
python server.py --test
```

#### 3. 配置客户端连接

##### Claude Desktop
编辑配置文件（Windows: `%APPDATA%\Claude\claude_desktop_config.json`，macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`）：
```json
{
  "mcpServers": {
    "geosource": {
      "command": "python",
      "args": ["E:/my_repo/GeoSource/server.py"]
    }
  }
}
```

##### Cursor / 其他 IDE
在 MCP 配置页面添加 stdio 服务：
- **Command**: `python`
- **Args**: `E:/my_repo/GeoSource/server.py`

---

## 📁 数据库表结构 (Database Schema)

- **`master`**：主服务表（主键 `service_id`，包含服务名、提供方、国家、协议、服务地址、格式、认证方式、验证状态等 54 个字段，建有 9 个核心索引）。
- **`layers`**：子图层表（联合主键 `(service_id, layer_idx)`，记录服务所属图层名称）。
- **`ecosystem`**：开源 GIS 软件库、SDK 与数据库工具链表。

---

## 📄 License
[MIT License](LICENSE) © 2026 GeoSource Authors
