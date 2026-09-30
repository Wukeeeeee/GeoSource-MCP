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
  <img src="https://img.shields.io/badge/Catalog-2%2C198%20Services-blue.svg" alt="Services">
  <img src="https://img.shields.io/badge/Verified-1%2C495%20Active-green.svg" alt="Verified">
  <img src="https://img.shields.io/badge/Layers-1%2C561-purple.svg" alt="Layers">
</p>

---

<a name="english"></a>
## 🌐 English

### Overview
**GeoSource MCP** is an open-source [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server providing structured access to an indexed catalog of **2,198 global GIS spatial services** and **1,561 sub-layers**.

When developers build maps, spatial analysis pipelines, or GIS crawlers using AI assistants (Claude Desktop, Cursor, Windsurf, etc.), large language models frequently struggle to locate real-world endpoints or generate non-functional URLs. GeoSource MCP connects AI environments directly to an indexed local SQLite database (`gis_services.db`), enabling low-latency, multi-criteria discovery of verified spatial services across OGC WMS, WFS, WMTS, XYZ Tiles, ArcGIS REST, STAC, and Open Data APIs.

### Key Engineering Features
- **Structured Discovery**: Helps AI models locate existing, functional endpoints rather than guessing URLs.
- **Low-Overhead Retrieval**: Fetches only matching records (typically 200 ~ 500 tokens per search) on demand, avoiding the cost and latency of loading megabytes of raw files into prompts.
- **Transparent Verification**: Tracks explicit availability statuses:
  - **1,495 Verified Active** (68.0%): Confirmed accessible via automated connectivity checks or authoritative official documentation.
  - **649 Pending / Unverified** (29.5%): Cataloged entries awaiting further verification or restricted by network boundaries.
  - **54 Deprecated / Inactive** (2.5%): Documented legacy services retained for reference.
- **Two-Way Maintenance**: Supports Excel synchronization and provides tools for AI agents to report status updates and new endpoints.

### Catalog Contents & Protocols

| Category | Protocols Supported | Notable Data Sources |
| :--- | :--- | :--- |
| **Open Data Portals (1,190)** | CKAN, Socrata, DKAN, ArcGIS Hub, REST API | Data.gov, Eurostat, Open Data DC, regional open data hubs |
| **OGC Standard Services (147)** | WMS 1.1.1/1.3.0, WFS 1.0/2.0, WMTS 1.0.0 | PDOK (Netherlands), geo.admin.ch (Switzerland), MML (Finland) |
| **Transit & Routing (151)** | GTFS, GTFS-RT, OSRM, REST API | OpenRouteService, Transitland, city transit agencies |
| **Basemap Tiles (65)** | XYZ Slippy Maps, WMTS, Vector Tiles | OpenStreetMap, Carto, Stadia, OpenTopoMap, MapTiler |
| **ArcGIS Platforms (100)** | ArcGIS Server REST, FeatureServer, MapServer | Esri Living Atlas, federal & municipal ArcGIS REST endpoints |
| **Remote Sensing / STAC (67)** | STAC API 1.0, OGC API Records, COG | Earth Search, Microsoft Planetary Computer, USGS Landsat |
| **3D Geospatial (31)** | 3D Tiles, CityGML, I3S | Cesium ion open assets, municipal 3D building models |

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
python scripts/verify_services.py --dry-run --limit 50
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
**GeoSource MCP** 是一个基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io) 标准的开源数据服务程序。它为各类 AI 编程与分析助手（Claude Desktop、Cursor、Windsurf 等）提供对本地结构化索引的 **2,198 个全球真实 GIS 空间服务** 与 **1,561 个地图图层** 的检索工具。

在开发地图应用或编写空间数据处理脚本时，大模型通常无法准确掌握全球各机构公开的实时服务接口，容易推断出不可用的链接。GeoSource MCP 直接连接本地 SQLite 数据库（`gis_services.db`），帮助 AI 快速检索真实的可用服务与图层参数。

### 工程特性与设计原则
- **结构化发现，降低幻觉**：提供经过结构化收录的真实服务端点，辅助 AI 编写准确的地图调用代码。
- **按需低开销检索**：每次仅检索返回匹配的 3~5 条记录（约 200~500 Tokens），避免将数兆字节的原始表格强行填入上下文窗口。
- **透明的可用性状态**：
  - **已验证**（1,495 条，占比 68.0%）：经自动化连通性探测或官方文档确认为可用。
  - **未验证**（649 条，占比 29.5%）：已整理归类，待进一步探测或受跨国网络连通性限制。
  - **已停止**（54 条，占比 2.5%）：已下线或历史归档服务，保留供查阅追溯。
- **双向维护支持**：支持与 Excel 表格双向数据同步，并提供更新接口供 AI 助手汇报失效链接与新地址。

### 数据分类与协议支持

| 分类 | 协议类型 | 典型代表 |
| :--- | :--- | :--- |
| **开放数据门户 (1,190 条)** | CKAN, Socrata, DKAN, ArcGIS Hub, REST API | Data.gov、欧盟数据门户、开放广东、各级城市开放数据中心 |
| **OGC 标准服务 (147 条)** | OGC WMS (1.1.1/1.3.0), WFS, WMTS | 荷兰 PDOK、瑞士联邦地图、芬兰测绘局等国家级测绘局 |
| **交通与路网 (151 条)** | GTFS, GTFS-RT, OSRM, REST API | OpenRouteService、Transitland、各地铁公交调度 API |
| **底图瓦片 (65 条)** | XYZ 栅格瓦片, WMTS, 矢量瓦片 | OpenStreetMap, Carto, Stadia Maps, OpenTopoMap |
| **ArcGIS 平台 (100 条)** | ArcGIS REST (MapServer, FeatureServer) | Esri Living Atlas、各国政府与水务气象机构 REST 服务 |
| **遥感时空资产 (67 条)** | STAC API 1.0, OGC API Records, COG | Earth Search、行星计算机、USGS Landsat 卫星时空目录 |
| **三维空间数据 (31 条)** | 3D Tiles, CityGML, I3S | Cesium ion 开放资产、城市级白模与倾斜摄影服务 |

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
python scripts/verify_services.py --dry-run --limit 50
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
