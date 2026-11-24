"""
deploy_n8n.py — Deploy all three n8n workflows for Zuha's Wedding Registry.

Usage:
    python scripts/deploy_n8n.py

Env vars required:
    N8N_BASE_URL   — n8n instance base URL (e.g. https://your-n8n.example.com)
                     /api/v1 is appended automatically if not present
    N8N_API_KEY    — n8n API key

Deploys workflows/flow_a_intake_form.json, flow_b_nightly_ai.json,
flow_c_order_cockpit.json.  Upserts by name (POST if new, PUT if exists).
Activates each workflow after deploy.
"""

import json
import os
import sys
import time
from pathlib import Path

import requests

WORKFLOWS_DIR = Path(__file__).parent.parent / "workflows"
FLOW_FILES = [
    "flow_a_intake_form.json",
    "flow_b_nightly_ai.json",
    "flow_c_order_cockpit.json",
]


def build_base(raw: str) -> str:
    base = raw.strip().rstrip("/")
    if not base.endswith("/api/v1"):
        base = f"{base}/api/v1"
    return base


def get_headers(key: str) -> dict:
    return {"X-N8N-API-KEY": key, "Content-Type": "application/json"}


def list_workflows(base: str, key: str) -> list:
    resp = requests.get(f"{base}/workflows", headers=get_headers(key), timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", data) if isinstance(data, dict) else data


def upsert_workflow(base: str, key: str, wf: dict, existing: list) -> dict:
    name = wf.get("name", "")
    match = next((e for e in existing if e.get("name") == name), None)
    if match:
        wf_id = match["id"]
        print(f"  Updating existing workflow '{name}' (id={wf_id})")
        resp = requests.put(
            f"{base}/workflows/{wf_id}",
            headers=get_headers(key),
            json=wf,
            timeout=15,
        )
    else:
        print(f"  Creating new workflow '{name}'")
        resp = requests.post(
            f"{base}/workflows",
            headers=get_headers(key),
            json=wf,
            timeout=15,
        )
    if resp.status_code == 429:
        wait = int(resp.headers.get("Retry-After", 3))
        print(f"  Rate limited, waiting {wait}s...")
        time.sleep(wait)
        return upsert_workflow(base, key, wf, existing)
    resp.raise_for_status()
    return resp.json()


def activate_workflow(base: str, key: str, wf_id: str) -> None:
    resp = requests.patch(
        f"{base}/workflows/{wf_id}/activate",
        headers=get_headers(key),
        timeout=15,
    )
    if resp.status_code == 404:
        resp = requests.post(
            f"{base}/workflows/{wf_id}/activate",
            headers=get_headers(key),
            timeout=15,
        )
    resp.raise_for_status()
    print(f"  Activated workflow id={wf_id}")


def main() -> None:
    raw_url = os.environ.get("N8N_BASE_URL") or os.environ.get("N8N_URL")
    key = os.environ.get("N8N_API_KEY")
    if not raw_url or not key:
        print("ERROR: N8N_BASE_URL (or N8N_URL) and N8N_API_KEY env vars required")
        sys.exit(1)

    base = build_base(raw_url)
    print(f"=== Deploying Zuha Wedding Registry Workflows to {base} ===\n")

    existing = list_workflows(base, key)
    print(f"Found {len(existing)} existing workflow(s) on instance\n")

    form_url = None
    for fname in FLOW_FILES:
        fpath = WORKFLOWS_DIR / fname
        if not fpath.exists():
            print(f"  SKIP: {fpath} not found")
            continue
        wf = json.loads(fpath.read_text())
        result = upsert_workflow(base, key, wf, existing)
        wf_id = result.get("id")
        if wf_id:
            activate_workflow(base, key, wf_id)
        if fname == "flow_a_intake_form.json":
            # Extract the form URL from the trigger node
            nodes = result.get("nodes", [])
            trigger = next(
                (n for n in nodes if n.get("type") == "n8n-nodes-base.formTrigger"),
                None,
            )
            if trigger:
                path = trigger.get("parameters", {}).get("path", "zuhas-wedding-registry")
                host = raw_url.strip().rstrip("/").split("/api/")[0]
                form_url = f"{host}/form/{path}"

    print("\n=== Deploy Complete ===")
    if form_url:
        print(f"\nIntake Form URL: {form_url}")
    else:
        print("\nForm URL: check n8n UI for the Form Trigger URL in flow_a_intake_form")


if __name__ == "__main__":
    main()
