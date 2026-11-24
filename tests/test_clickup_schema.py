"""
test_clickup_schema.py — Live ClickUp API tests for Zuha's Wedding Registry.

Requires CLICKUP_API_TOKEN env var. Skips gracefully if not set.
"""

import json
import os
import time
from pathlib import Path

import pytest
import requests

LIST_ID = "1300320000015716"
BASE_URL = "https://api.clickup.com/api/v2"
CONFIG_PATH = Path(__file__).parent.parent / "config" / "clickup_ids.json"

REQUIRED_FIELD_NAMES = {
    "Product URL", "Clean Product Name", "Retail Price", "Guest Price Bracket",
    "Best Registry Vendor", "Added By", "Registry Decision Verdict",
    "Residency Horizon Tier", "Room / Zone", "Halal Supply-Chain & City Fit",
    "Beginner Cooking Safety & Automation", "Apartment Spatial Footprint",
    "Chore Offload Quotient", "Cultural & Hosting Utility",
    "Dual-Career WFH Noise & Focus Score", "Spice, Oil & Apartment Odor Control",
    "Smart Ecosystem & Protocol", "Ecosystem Alignment",
    "Subscription / Consumable Trap", "AI Subscription Redundancy Flag",
    "Autonomy & AI Capability", "Renter / Apartment Install Friction",
    "Moveability & Box Footprint", "Purchase & Shipping Timing",
    "Residency Location Trigger", "Review Divergence Flag",
    "Duplicate / Overlap Cluster", "Known Failure Mode & MTBF",
    "Editorial Lab Rating", "Crowdsourced Longevity Score",
    "Regret & Friction Tags", "Schedule Impact Role",
    "Family Assignment Tier", "Off-Registry Buyability",
    "Family Gift Pitch (1-Liner)", "Completion Discount Eligible",
    "Gifted By / Buyer Name", "Order / Tracking Number",
    "Delivery Status", "Thank-You Note Status",
}

REQUIRED_VIEW_NAMES = {
    "Master Decision Matrix",
    "High-ROI 7-Yr Shortlist",
    "Hype & Paywall Audit",
    "Family & Relatives Gift Menu",
    "WV vs. TX Match Toggle",
    "Gift Cockpit & Thank-You Tracker",
}

KEY_FIELD_OPTIONS = {
    "Guest Price Bracket": {"<$50", "$50–$150", "$150–$300", "$300+ (Group Gift)"},
    "Best Registry Vendor": {"Amazon", "Crate & Barrel", "Williams Sonoma", "Target", "Best Buy", "Direct / Universal"},
    "Added By": {"Zuha", "Fiancé"},
}


@pytest.fixture(scope="module")
def api_token():
    token = os.environ.get("CLICKUP_API_TOKEN")
    if not token:
        pytest.skip("CLICKUP_API_TOKEN not set")
    return token


@pytest.fixture(scope="module")
def headers(api_token):
    return {"Authorization": api_token, "Content-Type": "application/json"}


def api_get(path, headers, params=None):
    resp = requests.get(f"{BASE_URL}{path}", headers=headers, params=params, timeout=15)
    if resp.status_code == 429:
        time.sleep(int(resp.headers.get("Retry-After", 2)))
        resp = requests.get(f"{BASE_URL}{path}", headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def test_all_statuses(headers):
    data = api_get(f"/list/{LIST_ID}", headers)
    statuses = {s["status"].upper() for s in data.get("statuses", [])}
    # At least 7 statuses must exist (NEEDS QUICK DETAILS may be missing — manual step)
    assert len(statuses) >= 7, f"Expected >=7 statuses, found {len(statuses)}: {statuses}"
    required_known = {
        "RAW URL DROPPED", "AI ENRICHED", "SHORTLISTED",
        "ASSIGNED TO FAMILY", "ON PUBLIC REGISTRY",
        "PURCHASED / GIFTED", "REJECTED / CLUTTER",
    }
    missing = required_known - statuses
    assert not missing, f"Missing statuses: {missing}"


def test_all_40_fields(headers):
    data = api_get(f"/list/{LIST_ID}/field", headers)
    found_names = {f["name"] for f in data.get("fields", [])}
    missing = REQUIRED_FIELD_NAMES - found_names
    assert not missing, f"Missing {len(missing)} fields: {sorted(missing)}"


def test_field_option_uuids(headers):
    data = api_get(f"/list/{LIST_ID}/field", headers)
    fields_by_name = {f["name"]: f for f in data.get("fields", [])}

    for field_name, expected_options in KEY_FIELD_OPTIONS.items():
        assert field_name in fields_by_name, f"Field '{field_name}' not found"
        field = fields_by_name[field_name]
        opts = field.get("type_config", {}).get("options", [])
        opt_names = {o["name"] for o in opts}
        missing_opts = expected_options - opt_names
        assert not missing_opts, f"Field '{field_name}' missing options: {missing_opts}"
        # All options must have UUIDs (non-empty id)
        for opt in opts:
            assert opt.get("id"), f"Option '{opt.get('name')}' in field '{field_name}' has no UUID"


def test_6_views(headers):
    data = api_get(f"/list/{LIST_ID}/view", headers)
    found_names = {v["name"] for v in data.get("views", [])}
    missing = REQUIRED_VIEW_NAMES - found_names
    assert not missing, f"Missing views: {missing}"


def test_create_and_delete_qa_task(headers):
    # Create a [QA TEST] task with 6 fields populated
    payload = {
        "name": "[QA TEST] Auto-delete Registry Item",
        "status": "RAW URL DROPPED",
        "custom_fields": [
            {"id": "5afbee8e-16bc-4c70-9acd-7647ffad17e4", "value": "https://www.amazon.com/dp/B00TEST"},
            {"id": "39c566b3-6c37-4c7e-999d-800000f902a3", "value": "QA Test Product"},
            {"id": "12ae86f2-737f-4258-a457-6c87297c4cab", "value": "bac4e09e-7cf7-4f0f-b0f9-bac89528a23a"},  # Zuha
            {"id": "252a7a02-7796-4000-95ac-f9d4ac31e8ae", "value": "6473fbf4-63fa-4fb0-9837-84063f9446b7"},  # Amazon
            {"id": "9c281fab-686d-4b34-a08d-cb6f4f785857", "value": 49.99},
            {"id": "e2247cef-64b9-429c-9bcc-bf9b60e25526", "value": "1949e004-587e-4b77-8c4c-87e49d4aef46"},  # <$50
        ],
    }
    create_resp = requests.post(
        f"{BASE_URL}/list/{LIST_ID}/task",
        headers=headers,
        json=payload,
        timeout=15,
    )
    assert create_resp.status_code in (200, 201), f"Create failed: {create_resp.text}"
    task = create_resp.json()
    task_id = task["id"]

    try:
        # Read back and verify fields
        read_resp = requests.get(f"{BASE_URL}/task/{task_id}", headers=headers, timeout=15)
        assert read_resp.status_code == 200
        read_task = read_resp.json()
        assert read_task["name"] == "[QA TEST] Auto-delete Registry Item"
        custom_fields = {f["id"]: f for f in read_task.get("custom_fields", [])}
        url_field = custom_fields.get("5afbee8e-16bc-4c70-9acd-7647ffad17e4")
        assert url_field is not None
        assert "B00TEST" in str(url_field.get("value", ""))
    finally:
        # Always clean up
        del_resp = requests.delete(f"{BASE_URL}/task/{task_id}", headers=headers, timeout=15)
        assert del_resp.status_code in (200, 204), f"Delete failed: {del_resp.text}"
