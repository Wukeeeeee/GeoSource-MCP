"""
Unit and Integration Tests for GeoSource MCP Server
"""

import os
import json
import sqlite3
import pytest
from datetime import datetime

# Import functions directly from server
from server import (
    search_gis_services,
    get_service_detail,
    list_categories_and_stats,
    query_gis_sql,
    update_service_status,
    probe_service_api,
    get_db_connection,
    VALID_STATUSES
)


def test_list_categories_and_stats():
    """Verify statistics return accurate counts and breakdown."""
    res_str = list_categories_and_stats()
    data = json.loads(res_str)

    assert data["total_services"] == 2207
    assert data["total_layers"] == 1561
    assert "status_distribution" in data
    assert "已验证" in data["status_distribution"]
    assert "未验证" in data["status_distribution"]
    assert len(data["top_categories"]) > 0
    assert len(data["top_protocols"]) > 0


def test_search_gis_services():
    """Verify search returns expected fields and handles limit properly."""
    res_str = search_gis_services(keyword="DEM", limit=5)
    data = json.loads(res_str)

    assert "total_returned" in data
    assert len(data["results"]) <= 5
    assert len(data["results"]) > 0

    first_item = data["results"][0]
    assert "service_id" in first_item
    assert "service_name" in first_item
    assert "provider" in first_item
    assert "service_url" in first_item
    assert "protocol" in first_item


def test_get_service_detail_case_insensitive():
    """Verify detail retrieval works with lowercase service_id."""
    res_str = get_service_detail("ds-0001")
    data = json.loads(res_str)

    assert "error" not in data
    assert data["service_id"] == "DS-0001"
    assert "service_name" in data
    assert "layers" in data
    assert isinstance(data["layers"], list)


def test_get_service_detail_not_found():
    """Verify non-existent service returns clear error."""
    res_str = get_service_detail("NON_EXISTENT_ID_9999")
    data = json.loads(res_str)

    assert "error" in data
    assert "not found" in data["error"].lower()


def test_query_gis_sql_readonly_and_safety():
    """Verify query_gis_sql allows safe SELECT and blocks dangerous commands."""
    # Safe query
    safe_res = query_gis_sql("SELECT service_id, service_name FROM master LIMIT 3")
    safe_data = json.loads(safe_res)
    assert safe_data.get("row_count") == 3

    # Forbidden INSERT
    insert_res = query_gis_sql("INSERT INTO master (service_id) VALUES ('TEST')")
    assert "error" in json.loads(insert_res)

    # Forbidden DROP
    drop_res = query_gis_sql("DROP TABLE master")
    assert "error" in json.loads(drop_res)

    # Forbidden PRAGMA
    pragma_res = query_gis_sql("PRAGMA table_info(master)")
    assert "error" in json.loads(pragma_res)

    # Forbidden multiple statements
    multi_res = query_gis_sql("SELECT 1; SELECT 2;")
    assert "error" in json.loads(multi_res)


def test_probe_service_api_offline_safety():
    """Verify probe_service_api returns a structured error for bad input without raising."""
    missing = json.loads(probe_service_api(service_id="NON_EXISTENT_ID_9999"))
    assert "error" in missing

    # 明显不是 http 的地址，不应抛异常
    bad = json.loads(probe_service_api(url="not-a-url", timeout=3))
    assert "reachable" in bad and bad["reachable"] is False


def test_probe_service_api_detects_known_portal():
    """Live-probe a well-known ArcGIS Hub portal; requires network access."""
    import pytest

    data = json.loads(probe_service_api(url="https://opendata.dc.gov", timeout=20))
    if not data.get("reachable"):
        pytest.skip(f"网络不可达，跳过在线探测: {data.get('error')}")
    assert data["detected_platform"] == "ArcGIS Hub"
    assert data["api_url"].startswith("https://opendata.dc.gov/api/v3/")


def test_update_service_status_validation():
    """Verify update_service_status validates enum, updates last_verified, and cleans up."""
    # Backup original state
    conn = get_db_connection(read_only=False)
    cur = conn.cursor()
    cur.execute("SELECT status, notes, last_verified FROM master WHERE service_id = 'DS-0001'")
    orig = cur.fetchone()
    orig_status = orig["status"]
    orig_notes = orig["notes"]
    orig_lv = orig["last_verified"]

    try:
        # Invalid status
        invalid_res = update_service_status(service_id="DS-0001", status="非法状态")
        assert "error" in json.loads(invalid_res)

        # Valid status update with case-insensitivity
        valid_res = update_service_status(
            service_id="ds-0001",
            status="已验证",
            notes="Automated test check"
        )
        result = json.loads(valid_res)
        assert result.get("success") is True
        assert result.get("service_id") == "DS-0001"
        assert result.get("last_verified") == datetime.now().strftime("%Y-%m-%d")
    finally:
        # Restore original state
        cur.execute("UPDATE master SET status = ?, notes = ?, last_verified = ? WHERE service_id = 'DS-0001'", (orig_status, orig_notes, orig_lv))
        conn.commit()
        conn.close()
