# Zuha's Wedding Registry Intelligence System

Automated wedding registry management combining ClickUp Enterprise, n8n workflows, and Claude AI.

---

## Prerequisites

1. Python 3.11+
2. n8n instance (self-hosted or cloud)
3. ClickUp Enterprise workspace (`zuha` space, list `Wedding Registry Intelligence`)
4. Gmail account for Flow C (order tracking)

---

## Environment Variables

Create a `.env` file or set these in your shell:

```env
# ClickUp
CLICKUP_API_TOKEN=pk_xxxxxxxxxxxxxxxxxxxx

# n8n
N8N_BASE_URL=https://your-n8n.example.com
N8N_API_KEY=n8n_xxxxxxxxxxxxxxxxxxxx

# Optional: for E2E tests after deploy
N8N_FORM_URL=https://your-n8n.example.com/form/zuhas-wedding-registry
```

> **Never commit `.env` to git.** The `.gitignore` excludes it.

---

## MANUAL STEP — Add "NEEDS QUICK DETAILS" Status

The ClickUp API does not support adding statuses via API on existing lists. Add it manually:

1. Open ClickUp → `zuha` space → `Wedding Registry Intelligence` list
2. Click the status dropdown → **Edit Statuses**
3. Add a new status: **NEEDS QUICK DETAILS** (color: orange)
4. Save

This is the only step that cannot be automated.

---

## Setup

### 1. Verify ClickUp schema

```powershell
$env:CLICKUP_API_TOKEN = "<your-token>"
python scripts/setup_clickup.py
```

Expected output: `All schema components verified.`

### 2. Deploy n8n workflows

```powershell
$env:N8N_BASE_URL = "https://your-n8n.example.com"
$env:N8N_API_KEY = "<your-key>"
python scripts/deploy_n8n.py
```

The script deploys all three workflows and prints the form URL.

### 3. Configure n8n credentials

After deploy, in the n8n UI:

| Credential name | Type | Value |
|---|---|---|
| ClickUp API | HTTP Header Auth | Header: `Authorization`, Value: your `CLICKUP_API_TOKEN` |
| Anthropic API | HTTP Header Auth | Header: `x-api-key`, Value: your Anthropic key |
| Gmail OAuth2 | Gmail OAuth2 | Authorize with Zuha's Gmail account |

---

## Form URL

After deploy, the intake form is at:

```
https://your-n8n.example.com/form/zuhas-wedding-registry
```

Bookmark this. Share with Zuha and fiancé.

---

## 7-Card ClickUp Dashboard — "Registry Intelligence Command Center"

Build this 2-minute native dashboard on the `Wedding Registry Intelligence` list.

In ClickUp: **Dashboards** → **Add Dashboard** → name it **Registry Intelligence Command Center** → **Add widget** for each card:

| # | Card | Widget type | Config |
|---|---|---|---|
| 1 | Task Count by Status | Bar chart | Group by: Status |
| 2 | Items by Guest Price Bracket | Pie chart | Group by: Guest Price Bracket field |
| 3 | Items by Best Registry Vendor | Bar chart | Group by: Best Registry Vendor field |
| 4 | Items by Registry Decision Verdict | Pie chart | Group by: Registry Decision Verdict field |
| 5 | Items by Residency Horizon Tier | Bar chart | Group by: Residency Horizon Tier field |
| 6 | AI Enriched vs RAW | Number tile (×2) | Filter: status = AI ENRICHED / RAW URL DROPPED |
| 7 | Purchased / Gifted count | Number tile | Filter: status = PURCHASED / GIFTED |

---

## Testing

```powershell
# Install test dependencies
pip install -r requirements.txt
playwright install chromium

# Run all offline tests (no live APIs needed)
pytest tests/test_url_parser.py tests/test_batch_enrichment.py -v

# Run ClickUp schema tests (requires CLICKUP_API_TOKEN)
pytest tests/test_clickup_schema.py -v

# Run E2E form tests (requires N8N_FORM_URL after deploy)
pytest tests/test_e2e_intake_form.py -v

# Run everything
pytest -v tests/
```

### Test coverage

| File | Tests | Live API? |
|---|---|---|
| `test_url_parser.py` | 13 | No |
| `test_batch_enrichment.py` | 12 | No |
| `test_clickup_schema.py` | 5 | Yes (ClickUp) |
| `test_e2e_intake_form.py` | 7 | Yes (n8n form) |

---

## Workflow Overview

```
Flow A — Intake Form
  Form Trigger (zuhas-wedding-registry)
    → Parse & Validate URLs (1–20, dedupe, vendor detect)
    → Scrape OG Tags (batch=5, timeout=3.5s)
    → Extract OG Title & Price
    → Create ClickUp Tasks (status=RAW URL DROPPED, batch=5, interval=1.1s)
    → Aggregate Results
    → If blocked: Manual Entry Fallback Form
    → Post Digest Comment to list

Flow B — Nightly AI Enrichment (2 AM daily)
  Schedule Trigger
    → Fetch RAW URL DROPPED tasks
    → Build Claude batch prompt
    → Claude claude-sonnet-4-6 enrichment call
    → Parse JSON response
    → Update tasks → AI ENRICHED (batch=5, interval=1.1s)

Flow C — Order Cockpit
  Gmail Trigger (order confirmation emails)
    → Extract retailer, item, tracking
    → Search ClickUp tasks by name
    → Update matched task → PURCHASED / GIFTED
    → Post AI-drafted thank-you comment
```

---

## ClickUp List Details

- **Workspace:** 90161547829
- **Space:** zuha (1300320000001326)
- **List:** Wedding Registry Intelligence (1300320000015716)
- **URL:** https://app.clickup.com/90161547829/v/l/li/1300320000015716
- **Custom fields:** 40
- **Statuses:** 8 (7 via API + NEEDS QUICK DETAILS manual)
- **Views:** 6

---

## Repo Structure

```
wedding-registry/
├── config/
│   └── clickup_ids.json        # All field/status/view IDs
├── prompts/
│   └── claude_enrichment_prompt.md
├── scripts/
│   ├── deploy_n8n.py
│   └── setup_clickup.py
├── tests/
│   ├── mock_retailer_server.py
│   ├── test_batch_enrichment.py
│   ├── test_clickup_schema.py
│   ├── test_e2e_intake_form.py
│   └── test_url_parser.py
├── workflows/
│   ├── flow_a_intake_form.json
│   ├── flow_b_nightly_ai.json
│   └── flow_c_order_cockpit.json
├── requirements.txt
└── README.md
```
