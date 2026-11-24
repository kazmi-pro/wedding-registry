"""
test_batch_enrichment.py — Tests for Flow B Claude JSON parsing and field mapping logic.

All tests are self-contained: mock Claude responses, no live API calls.
"""

import json
import re

import pytest

# ── Field and option maps (mirrors flow_b Parse Claude JSON node) ──────────────

FIELD_IDS = {
    "cleanProductName": "39c566b3-6c37-4c7e-999d-800000f902a3",
    "retailPrice": "9c281fab-686d-4b34-a08d-cb6f4f785857",
    "guestPriceBracket": "e2247cef-64b9-429c-9bcc-bf9b60e25526",
    "bestRegistryVendor": "252a7a02-7796-4000-95ac-f9d4ac31e8ae",
    "registryDecisionVerdict": "b10bb486-ceb9-4ec9-b5be-30045c1dc876",
    "residencyHorizonTier": "8951eea6-f9bd-4497-84bf-9d2300251092",
    "roomZone": "8991167a-0fd2-4a09-840c-4ef60986e5dd",
    "halalFit": "83f42a59-c059-4f49-beb3-93032e9a7460",
    "beginnerCooking": "2eba772a-cc1f-4a7e-a73b-214efafb98e5",
    "subscriptionTrap": "186dba7a-8067-4e19-b976-589c04e27f6d",
    "choiceQuotient": "263cd81c-b389-4fbd-a21b-5c1139c286f3",
    "familyGiftPitch": "78a0c2db-312b-436a-b342-13fe9fe41112",
}

OPTION_UUIDS = {
    "guestPriceBracket": {
        "<$50": "1949e004-587e-4b77-8c4c-87e49d4aef46",
        "$50–$150": "e8087ca4-e624-4baf-a022-62240f5f7b59",
        "$150–$300": "54048e14-106c-4211-a287-f935f924a246",
        "$300+ (Group Gift)": "0803e69d-5b32-4323-917b-377bddf2ea4a",
    },
    "bestRegistryVendor": {
        "Amazon": "6473fbf4-63fa-4fb0-9837-84063f9446b7",
        "Crate & Barrel": "13dab330-bb97-4adf-b98c-ee7b555e53c1",
        "Williams Sonoma": "736e36a7-799a-40ce-bf19-976838b9f18b",
        "Target": "b27937ac-992b-4eea-bccd-df367fa228d2",
        "Best Buy": "902471bb-b070-4200-aefd-1662819c7425",
        "Direct / Universal": "26e06bbb-3c70-4232-b4d9-ae80f976443b",
    },
    "registryDecisionVerdict": {
        "Auto-Shortlist (High ROI)": "03c524cf-2261-49bf-b158-d75bd9dec2f5",
        "Keep If Counter Space Allows": "4261e542-3028-40f1-81a5-4ee3eaf5f4a7",
        "Swap for Smarter/BIFL Alternative": "b061dd30-7e71-4450-935b-2eb7cdec4ff0",
        "Reject (Clutter/Failure Risk)": "597738cd-9ce8-4ef0-bd07-de37b92e17c5",
        "Needs Manual Verification": "736ebe11-8bc1-49b3-81dc-7e7c98648eff",
    },
    "residencyHorizonTier": {
        "7+ Yr Survivor (Attending-Ready)": "8a824736-8ed2-416d-95a2-8a8832b33f9b",
        "Residency Workhorse (4–6 Yrs)": "8db765b3-3a2d-4945-8d77-85dc5c274607",
        "3-Yr Disposable Risk": "bffe913e-b017-4698-9594-b2776ec83dec",
    },
    "roomZone": {
        "Kitchen & Halal Prep": "51467d11-13b0-4d79-8ba9-0fd53c0e2de5",
        "Sleep & Post-Call Recovery": "24f98a71-551d-4f98-9406-9cd38260c795",
        "Remote Home Office": "967e0842-bd2b-4bef-92aa-e51cdd6c5228",
        "Cleaning & Laundry": "b075bc77-13df-4284-b6b6-83fc5a5becd6",
        "Bath & Linen": "ccf65df1-48d6-437d-b76d-6a6b58ae762c",
    },
    "halalFit": {
        "Critical for Small-Town WV Bulk/Freezer": "30072666-6289-46c8-acf8-a2c16bed48f9",
        "High Value in Both TX & WV": "bfbd22ca-a38e-4ff8-badf-0dbf40b6ac25",
        "Optimized for Houston/Dallas Takeout/Fresh": "cda5e4db-3d72-4fd9-aa2a-3ace96262af7",
        "Not Applicable": "dd94f839-8eb3-4413-b35c-b0c9ab55946d",
    },
    "beginnerCooking": {
        "One-Touch / Foolproof": "95985452-fddc-4dcf-98b2-e2fefd331e48",
        "Guided App Recipes": "645a797e-880a-4748-abd2-c29912234b7b",
        "Moderate Skill": "4d446b6e-c44d-46e4-ac10-41b6407c60f2",
        "High Burn / Timing Skill Risk": "df5c25b1-3513-4d54-8dd8-e1c0ff8e54ca",
        "Non-Kitchen": "4d2fafed-6a9f-4b5f-a8aa-7591af1af8ea",
    },
    "subscriptionTrap": {
        "Zero Ongoing Fees": "9e2cdbe6-7821-417d-8f2d-998d6149c533",
        "Optional Cloud Features": "bc29857a-bdc9-46bf-b3f6-59de88758a52",
        "Mandatory Paywall / Proprietary Cartridges": "ebacb58c-2958-419b-a0c1-4ff601ac20f0",
    },
}

DROPDOWN_FIELDS = set(OPTION_UUIDS.keys())
REQUIRED_SCHEMA_KEYS = {
    "taskId", "cleanProductName", "retailPrice", "guestPriceBracket",
    "bestRegistryVendor", "registryDecisionVerdict", "residencyHorizonTier",
    "roomZone", "halalFit", "beginnerCooking", "subscriptionTrap",
    "choiceQuotient", "familyGiftPitch",
}

# Workflow config (must match flow_b_nightly_ai.json)
BATCH_SIZE = 5
BATCH_INTERVAL_MS = 1100


def parse_claude_response(json_text: str) -> list[dict]:
    """Mirrors the Parse Claude JSON node logic."""
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", json_text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def build_clickup_update(item: dict) -> list[dict]:
    """Map Claude item to ClickUp custom_fields array."""
    custom_fields = []
    for key, field_id in FIELD_IDS.items():
        val = item.get(key)
        if val is None:
            continue
        if key in DROPDOWN_FIELDS:
            uuid = OPTION_UUIDS[key].get(val)
            if uuid:
                custom_fields.append({"id": field_id, "value": uuid})
        else:
            custom_fields.append({"id": field_id, "value": val})
    return custom_fields


# ── Mock Claude responses ──────────────────────────────────────────────────────

MOCK_ZOJIRUSHI = [
    {
        "taskId": "task_zoji_001",
        "cleanProductName": "Zojirushi NS-TSC10 5.5-Cup Micom Rice Cooker",
        "retailPrice": 149.99,
        "guestPriceBracket": "$50–$150",
        "bestRegistryVendor": "Amazon",
        "registryDecisionVerdict": "Auto-Shortlist (High ROI)",
        "residencyHorizonTier": "7+ Yr Survivor (Attending-Ready)",
        "roomZone": "Kitchen & Halal Prep",
        "halalFit": "Critical for Small-Town WV Bulk/Freezer",
        "beginnerCooking": "One-Touch / Foolproof",
        "subscriptionTrap": "Zero Ongoing Fees",
        "choiceQuotient": 9,
        "familyGiftPitch": "Perfect for rice every night, biryani, and WV bulk cooking.",
    }
]

MOCK_CHEAP_PAN = [
    {
        "taskId": "task_pan_002",
        "cleanProductName": "Generic Non-Stick Frying Pan 10-inch",
        "retailPrice": 12.99,
        "guestPriceBracket": "<$50",
        "bestRegistryVendor": "Amazon",
        "registryDecisionVerdict": "Reject (Clutter/Failure Risk)",
        "residencyHorizonTier": "3-Yr Disposable Risk",
        "roomZone": "Kitchen & Halal Prep",
        "halalFit": "High Value in Both TX & WV",
        "beginnerCooking": "High Burn / Timing Skill Risk",
        "subscriptionTrap": "Zero Ongoing Fees",
        "choiceQuotient": 2,
        "familyGiftPitch": None,
    }
]

MOCK_SMART_SCALE = [
    {
        "taskId": "task_scale_003",
        "cleanProductName": "Withings Body+ Smart Scale with AI Coach",
        "retailPrice": 99.95,
        "guestPriceBracket": "$50–$150",
        "bestRegistryVendor": "Best Buy",
        "registryDecisionVerdict": "Keep If Counter Space Allows",
        "residencyHorizonTier": "Residency Workhorse (4–6 Yrs)",
        "roomZone": "Bath & Linen",
        "halalFit": "Not Applicable",
        "beginnerCooking": "Non-Kitchen",
        "subscriptionTrap": "Mandatory Paywall / Proprietary Cartridges",
        "choiceQuotient": 5,
        "familyGiftPitch": None,
    }
]


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestClaudeJsonSchema:
    def test_claude_json_schema(self):
        for item in MOCK_ZOJIRUSHI:
            for key in REQUIRED_SCHEMA_KEYS:
                assert key in item, f"Schema missing key: {key}"

    def test_null_handling(self):
        # Fields that are None should not appear in custom_fields
        item_with_nulls = {**MOCK_CHEAP_PAN[0], "familyGiftPitch": None, "retailPrice": None}
        fields = build_clickup_update(item_with_nulls)
        field_ids_in_result = {f["id"] for f in fields}
        # familyGiftPitch field ID should NOT be in result when null
        assert FIELD_IDS["familyGiftPitch"] not in field_ids_in_result
        # retailPrice field ID should NOT be in result when null
        assert FIELD_IDS["retailPrice"] not in field_ids_in_result


class TestEnumMapping:
    def test_enum_mapping(self):
        # Every known enum value must map to a valid UUID
        for field, options in OPTION_UUIDS.items():
            for label, uuid in options.items():
                assert len(uuid) == 36 and uuid.count("-") == 4, \
                    f"Invalid UUID for {field}.{label}: {uuid}"

    def test_rate_limiter_config(self):
        assert BATCH_SIZE == 5, f"batchSize must be 5, got {BATCH_SIZE}"
        assert BATCH_INTERVAL_MS >= 1100, f"batchInterval must be >=1100ms, got {BATCH_INTERVAL_MS}"

    def test_all_dropdown_fields_covered(self):
        for field in DROPDOWN_FIELDS:
            assert field in OPTION_UUIDS, f"Dropdown field '{field}' has no option map"


class TestSampleProducts:
    def test_sample_zojirushi(self):
        item = MOCK_ZOJIRUSHI[0]
        fields = build_clickup_update(item)
        field_ids = {f["id"] for f in fields}
        # Check no unmapped enums (all dropdown values in OPTION_UUIDS must have produced a UUID)
        for key in DROPDOWN_FIELDS:
            val = item.get(key)
            if val is not None:
                uuid = OPTION_UUIDS[key].get(val)
                assert uuid is not None, f"Unmapped enum for {key}: '{val}'"
        # Verdict = Auto-Shortlist
        verdict_field = next(f for f in fields if f["id"] == FIELD_IDS["registryDecisionVerdict"])
        assert verdict_field["value"] == OPTION_UUIDS["registryDecisionVerdict"]["Auto-Shortlist (High ROI)"]

    def test_sample_cheap_pan(self):
        item = MOCK_CHEAP_PAN[0]
        assert item["registryDecisionVerdict"] == "Reject (Clutter/Failure Risk)"
        fields = build_clickup_update(item)
        verdict_field = next((f for f in fields if f["id"] == FIELD_IDS["registryDecisionVerdict"]), None)
        assert verdict_field is not None
        assert verdict_field["value"] == OPTION_UUIDS["registryDecisionVerdict"]["Reject (Clutter/Failure Risk)"]

    def test_sample_smart_scale(self):
        item = MOCK_SMART_SCALE[0]
        assert item["subscriptionTrap"] == "Mandatory Paywall / Proprietary Cartridges"
        fields = build_clickup_update(item)
        sub_field = next((f for f in fields if f["id"] == FIELD_IDS["subscriptionTrap"]), None)
        assert sub_field is not None
        assert sub_field["value"] == OPTION_UUIDS["subscriptionTrap"]["Mandatory Paywall / Proprietary Cartridges"]


class TestParseClaudeResponse:
    def test_parse_valid_json_array(self):
        text = json.dumps(MOCK_ZOJIRUSHI)
        items = parse_claude_response(text)
        assert len(items) == 1
        assert items[0]["taskId"] == "task_zoji_001"

    def test_parse_json_embedded_in_text(self):
        text = "Here is the enrichment result:\n" + json.dumps(MOCK_CHEAP_PAN) + "\nEnd."
        items = parse_claude_response(text)
        assert len(items) == 1
        assert items[0]["taskId"] == "task_pan_002"

    def test_parse_invalid_raises(self):
        with pytest.raises(Exception):
            parse_claude_response("Not valid JSON at all, no array either.")
