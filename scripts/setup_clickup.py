"""
setup_clickup.py — Idempotent ClickUp schema verifier/creator for
Zuha's Wedding Registry Intelligence list.

Usage:
    python scripts/setup_clickup.py

Env vars required:
    CLICKUP_API_TOKEN   — ClickUp personal API token
    CLICKUP_SPACE_NAME  — Space name to target (default: "zuha")
"""

import json
import os
import sys
import time
from pathlib import Path

import requests

BASE_URL = "https://api.clickup.com/api/v2"
LIST_ID = "1300320000015716"
SPACE_ID = "1300320000001326"
CONFIG_PATH = Path(__file__).parent.parent / "config" / "clickup_ids.json"

REQUIRED_FIELD_NAMES = [
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
]

REQUIRED_STATUS_NAMES = [
    "RAW URL DROPPED", "NEEDS QUICK DETAILS", "AI ENRICHED", "SHORTLISTED",
    "ASSIGNED TO FAMILY", "ON PUBLIC REGISTRY", "PURCHASED / GIFTED",
    "REJECTED / CLUTTER",
]

REQUIRED_VIEW_NAMES = [
    "Master Decision Matrix", "High-ROI 7-Yr Shortlist",
    "Hype & Paywall Audit", "Family & Relatives Gift Menu",
    "WV vs. TX Match Toggle", "Gift Cockpit & Thank-You Tracker",
]


def get_headers(token: str) -> dict:
    return {"Authorization": token, "Content-Type": "application/json"}


def api_get(path: str, token: str, params: dict = None, retries: int = 3) -> dict:
    """GET with 429 retry backoff."""
    url = f"{BASE_URL}{path}"
    for attempt in range(retries):
        resp = requests.get(url, headers=get_headers(token), params=params, timeout=15)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 2 ** attempt))
            print(f"  Rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"GET {path} failed after {retries} retries")


def check_list(token: str) -> dict:
    print(f"Checking list {LIST_ID}...")
    data = api_get(f"/list/{LIST_ID}", token)
    print(f"  List: {data.get('name')} (id={data.get('id')})")
    return data


def check_fields(token: str) -> tuple[list, list]:
    """Returns (found_names, missing_names)."""
    print("Checking custom fields...")
    data = api_get(f"/list/{LIST_ID}/field", token)
    fields = data.get("fields", [])
    found = {f["name"] for f in fields}
    missing = [n for n in REQUIRED_FIELD_NAMES if n not in found]
    print(f"  Found {len(found)} fields, {len(missing)} missing")
    if missing:
        print(f"  Missing: {missing}")
    return list(found), missing


def check_statuses(token: str) -> tuple[list, list]:
    print("Checking statuses...")
    data = api_get(f"/list/{LIST_ID}", token)
    statuses = data.get("statuses", [])
    found = {s["status"] for s in statuses}
    missing = [n for n in REQUIRED_STATUS_NAMES if n not in found]
    print(f"  Found {len(found)} statuses, {len(missing)} missing")
    if missing:
        print(f"  Missing: {missing}")
        if "NEEDS QUICK DETAILS" in missing:
            print("  NOTE: 'NEEDS QUICK DETAILS' must be added manually in ClickUp UI.")
    return list(found), missing


def check_views(token: str) -> tuple[list, list]:
    print("Checking views...")
    data = api_get(f"/list/{LIST_ID}/view", token)
    views = data.get("views", [])
    found = {v["name"] for v in views}
    missing = [n for n in REQUIRED_VIEW_NAMES if n not in found]
    print(f"  Found {len(found)} views, {len(missing)} missing")
    if missing:
        print(f"  Missing: {missing}")
    return list(found), missing


def save_ids(token: str) -> None:
    print("Saving updated clickup_ids.json...")
    list_data = api_get(f"/list/{LIST_ID}", token)
    field_data = api_get(f"/list/{LIST_ID}/field", token)
    view_data = api_get(f"/list/{LIST_ID}/view", token)

    statuses = {s["status"]: s["id"] for s in list_data.get("statuses", [])}
    views = {v["name"]: v["id"] for v in view_data.get("views", [])}
    fields = {}
    for f in field_data.get("fields", []):
        entry = {"id": f["id"], "type": f["type"]}
        if f["type"] in ("drop_down", "labels"):
            opts = f.get("type_config", {}).get("options", [])
            entry["options"] = {o["name"]: o["id"] for o in opts}
        fields[f["name"]] = entry

    ids = {
        "workspace_id": "90161547829",
        "space_id": SPACE_ID,
        "list_id": LIST_ID,
        "list_url": f"https://app.clickup.com/90161547829/v/l/li/{LIST_ID}",
        "statuses": statuses,
        "views": views,
        "fields": fields,
    }
    CONFIG_PATH.write_text(json.dumps(ids, indent=2))
    print(f"  Saved to {CONFIG_PATH}")


def main() -> None:
    token = os.environ.get("CLICKUP_API_TOKEN")
    if not token:
        print("ERROR: CLICKUP_API_TOKEN env var not set")
        sys.exit(1)

    print("=== Zuha Wedding Registry — ClickUp Schema Verifier ===\n")

    check_list(token)
    found_fields, missing_fields = check_fields(token)
    found_statuses, missing_statuses = check_statuses(token)
    found_views, missing_views = check_views(token)

    print("\n=== Summary ===")
    print(f"Fields:   {len(found_fields)}/40 found, {len(missing_fields)} missing")
    real_missing_statuses = [s for s in missing_statuses if s != "NEEDS QUICK DETAILS"]
    print(f"Statuses: {len(found_statuses)}/8 found, {len(real_missing_statuses)} missing (NEEDS QUICK DETAILS = manual UI step)")
    print(f"Views:    {len(found_views)}/6 found, {len(missing_views)} missing")

    if not missing_fields and not real_missing_statuses and not missing_views:
        print("\nAll schema components verified.")
        save_ids(token)
        print("Done.")
    else:
        print("\nSchema incomplete. Fix missing items then re-run.")
        sys.exit(1)


if __name__ == "__main__":
    main()
