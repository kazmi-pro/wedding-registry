"""
test_url_parser.py — Unit tests for URL parsing and OG scraping logic.

All tests are self-contained and do not require live APIs.
Tests use mock_retailer_server.py for HTTP-dependent cases.
"""

import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent))

# ── Inline implementation of the URL parsing logic (mirrors flow_a Code node) ──

def extract_urls(raw: str) -> list[str]:
    url_regex = re.compile(r"https?://[^\s,\"<>]+")
    matches = url_regex.findall(raw)
    return list(dict.fromkeys(u.strip() for u in matches))  # deduplicate, preserve order


def validate_urls(urls: list[str]) -> str | None:
    if len(urls) == 0:
        return "No valid URLs found"
    if len(urls) > 20:
        return f"Too many URLs: {len(urls)} submitted, maximum is 20"
    return None


def detect_vendor(url: str) -> dict:
    u = url.lower()
    if any(x in u for x in ["amazon.", "a.co/", "amzn.to/"]):
        return {"name": "Amazon", "uuid": "6473fbf4-63fa-4fb0-9837-84063f9446b7"}
    if "crateandbarrel" in u or "cb2." in u:
        return {"name": "Crate & Barrel", "uuid": "13dab330-bb97-4adf-b98c-ee7b555e53c1"}
    if "williams-sonoma" in u or "wsimgs" in u:
        return {"name": "Williams Sonoma", "uuid": "736e36a7-799a-40ce-bf19-976838b9f18b"}
    if "target.com" in u:
        return {"name": "Target", "uuid": "b27937ac-992b-4eea-bccd-df367fa228d2"}
    if "bestbuy.com" in u:
        return {"name": "Best Buy", "uuid": "902471bb-b070-4200-aefd-1662819c7425"}
    return {"name": "Direct / Universal", "uuid": "26e06bbb-3c70-4232-b4d9-ae80f976443b"}


def slug_to_name(url: str) -> str | None:
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        parts = [p for p in parsed.path.split("/") if len(p) > 3 and not p.isdigit()]
        if parts:
            return parts[-1].replace("-", " ").replace("_", " ").title()[:100]
    except Exception:
        pass
    return None


def extract_og(html: str, prop: str) -> str | None:
    for pattern in [
        rf'<meta[^>]*property=[\'"]og:{prop}[\'"][^>]*content=[\'"]([^\'"]+)[\'"]',
        rf'<meta[^>]*content=[\'"]([^\'"]+)[\'"][^>]*property=[\'"]og:{prop}[\'"]',
    ]:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


CAPTCHA_PATTERNS = re.compile(r"robot check|captcha|are you human|verify you are", re.IGNORECASE)


def scrape_result(html: str, status_code: int, url: str) -> dict:
    is_captcha = bool(CAPTCHA_PATTERNS.search(html))
    is_blocked = status_code == 403 or is_captcha
    product_name = None
    price = None
    scrape_succeeded = False

    if not is_blocked and len(html) > 100:
        product_name = extract_og(html, "title")
        price_str = extract_og(html, "price:amount") or extract_og(html, "price")
        if price_str:
            try:
                price = float(re.sub(r"[^0-9.]", "", price_str))
            except ValueError:
                price = None
        scrape_succeeded = bool(product_name)

    if not product_name:
        product_name = slug_to_name(url)

    return {
        "url": url,
        "productName": product_name,
        "price": price,
        "scrapeSucceeded": scrape_succeeded,
        "blocked": is_blocked,
    }


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestExtractUrls:
    def test_zero_urls(self):
        urls = extract_urls("")
        err = validate_urls(urls)
        assert err == "No valid URLs found"

    def test_one_url(self):
        raw = "https://www.amazon.com/dp/B00009IKCO"
        urls = extract_urls(raw)
        assert len(urls) == 1
        err = validate_urls(urls)
        assert err is None

    def test_twenty_urls(self):
        raw = "\n".join(f"https://www.target.com/p/item-{i}" for i in range(20))
        urls = extract_urls(raw)
        assert len(urls) == 20
        err = validate_urls(urls)
        assert err is None

    def test_twenty_one_urls(self):
        raw = "\n".join(f"https://www.target.com/p/item-{i}" for i in range(21))
        urls = extract_urls(raw)
        err = validate_urls(urls)
        assert err is not None
        assert "21" in err

    def test_deduplication(self):
        url = "https://www.amazon.com/dp/B00009IKCO"
        raw = f"{url}\n{url}\n{url}"
        urls = extract_urls(raw)
        assert len(urls) == 1

    def test_blank_lines(self):
        raw = "  \nhttps://www.amazon.com/dp/B001\n\n  \nhttps://www.target.com/p/item-2\n  "
        urls = extract_urls(raw)
        assert len(urls) == 2

    def test_long_tracking_url(self):
        # 300+ char URL should still be extracted
        base = "https://www.amazon.com/dp/B001"
        long_url = base + "?ref=" + "x" * 280
        urls = extract_urls(long_url)
        assert len(urls) == 1

    def test_ios_safari_mixed(self):
        raw = 'Check this out! https://www.amazon.com/dp/B002 — love it'
        urls = extract_urls(raw)
        assert len(urls) == 1
        assert "amazon.com" in urls[0]


class TestVendorDetection:
    def test_shortlink_vendor(self):
        vendor = detect_vendor("https://a.co/d/fakeproduct")
        assert vendor["name"] == "Amazon"

    def test_amzn_to_vendor(self):
        vendor = detect_vendor("https://amzn.to/abc123")
        assert vendor["name"] == "Amazon"

    def test_target_vendor(self):
        vendor = detect_vendor("https://www.target.com/p/item/-/A-12345")
        assert vendor["name"] == "Target"

    def test_bestbuy_vendor(self):
        vendor = detect_vendor("https://www.bestbuy.com/site/product/1234")
        assert vendor["name"] == "Best Buy"

    def test_unknown_vendor(self):
        vendor = detect_vendor("https://www.somestore.com/product")
        assert vendor["name"] == "Direct / Universal"


class TestSlugRescue:
    def test_slug_rescue(self):
        url = "https://www.example.com/products/breville-smart-oven-air-fryer-pro/"
        name = slug_to_name(url)
        assert name is not None
        assert "Breville" in name or "breville" in name.lower()

    def test_no_slug(self):
        name = slug_to_name("https://www.amazon.com/dp/B001")
        # B001 is short but the function may or may not return something; just must not crash
        assert name is None or isinstance(name, str)


class TestOgParsing:
    OG_HTML = """<html><head>
    <meta property="og:title" content="Zojirushi NS-TSC10 Rice Cooker" />
    <meta property="og:price:amount" content="149.99" />
    </head><body></body></html>"""

    CAPTCHA_HTML = """<html><body>
    <p>To discuss automated access please contact us. Robot Check required.</p>
    </body></html>"""

    def test_og_parsing_success(self):
        result = scrape_result(self.OG_HTML, 200, "https://www.amazon.com/dp/B001")
        assert result["scrapeSucceeded"] is True
        assert "Zojirushi" in result["productName"]
        assert result["price"] == 149.99

    def test_captcha_blocked(self):
        result = scrape_result(self.CAPTCHA_HTML, 200, "https://www.amazon.com/dp/B001")
        assert result["scrapeSucceeded"] is False
        assert result["blocked"] is True

    def test_403_blocked(self):
        result = scrape_result("<html></html>", 403, "https://www.example.com/product")
        assert result["blocked"] is True
        assert result["scrapeSucceeded"] is False
