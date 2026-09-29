-- 全球 GIS 空间服务数据库 — SQLite schema
-- 可直接用于 SQLite，亦可迁入 PostgreSQL/PostGIS（见末尾说明）
-- 生成日期 2026-09-28

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS master;
CREATE TABLE master (
    service_id TEXT PRIMARY KEY,
    service_name TEXT,
    country TEXT,
    region TEXT,
    provider TEXT,
    category TEXT,
    service_type TEXT,
    protocol TEXT,
    official_url TEXT,
    service_url TEXT,
    docs_url TEXT,
    layer_or_endpoint TEXT,
    data_description TEXT,
    spatial_coverage TEXT,
    temporal_coverage TEXT,
    crs TEXT,
    resolution TEXT,
    update_frequency TEXT,
    format TEXT,
    auth TEXT,
    api_key_required TEXT,
    registration_required TEXT,
    free TEXT,
    commercial_use TEXT,
    redistribution TEXT,
    rate_limit TEXT,
    query_limit TEXT,
    download_limit TEXT,
    pagination TEXT,
    batch_query TEXT,
    caching_allowed TEXT,
    attribution TEXT,
    last_verified TEXT,
    status TEXT,
    verify_method TEXT,
    notes TEXT,
    need_no_reg TEXT,
    need_no_key TEXT,
    is_free TEXT,
    support_api TEXT,
    support_spatial_query TEXT,
    support_temporal_query TEXT,
    support_batch TEXT,
    support_download TEXT,
    support_geojson TEXT,
    support_json TEXT,
    is_vector TEXT,
    is_raster TEXT,
    is_realtime TEXT,
    global_coverage TEXT,
    region_coverage TEXT,
    commercial_ok TEXT,
    cache_ok TEXT,
    redistribute_ok TEXT
);

DROP TABLE IF EXISTS layers;
CREATE TABLE layers (
    service_id TEXT NOT NULL,
    layer_idx  INTEGER NOT NULL,
    layer_name TEXT NOT NULL,
    PRIMARY KEY (service_id, layer_idx),
    FOREIGN KEY (service_id) REFERENCES master(service_id)
);

DROP TABLE IF EXISTS ecosystem;
CREATE TABLE ecosystem (
    id TEXT PRIMARY KEY,
    source TEXT,
    service TEXT,
    library TEXT,
    software TEXT,
    db TEXT,
    note TEXT
);

-- 索引（常用筛选字段）
CREATE INDEX idx_master_service_type ON master(service_type);
CREATE INDEX idx_master_protocol ON master(protocol);
CREATE INDEX idx_master_country ON master(country);
CREATE INDEX idx_master_region ON master(region);
CREATE INDEX idx_master_status ON master(status);
CREATE INDEX idx_master_api_key ON master(api_key_required);
CREATE INDEX idx_master_free ON master(free);
CREATE INDEX idx_master_category ON master(category);
CREATE INDEX idx_master_provider ON master(provider);
CREATE INDEX idx_layers_service ON layers(service_id);

-- 迁入 PostgreSQL/PostGIS 说明：
-- 1) 将 TEXT 字段保留；如需空间几何，可另建 geom GEOMETRY 列并用 ST_GeomFromGeoJSON 从 service_url 关联数据填充；
-- 2) 主键 service_id 已是 TEXT；
-- 3) 上述索引语法在 PostgreSQL 同样有效（CREATE INDEX 语法一致）。
