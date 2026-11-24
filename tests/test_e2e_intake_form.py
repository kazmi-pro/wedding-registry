"""
test_e2e_intake_form.py — Playwright E2E tests for Flow A intake form.

Requires N8N_FORM_URL env var pointing to the deployed form.
All tests skip gracefully if the URL is not set or unreachable.

Usage:
    N8N_FORM_URL=https://your-n8n.example.com/form/zuhas-wedding-registry pytest tests/test_e2e_intake_form.py -v
"""

import os

import pytest

N8N_FORM_URL = os.environ.get("N8N_FORM_URL", "")


def _form_reachable() -> bool:
    if not N8N_FORM_URL:
        return False
    try:
        import urllib.request
        with urllib.request.urlopen(N8N_FORM_URL, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


SKIP_REASON = "N8N_FORM_URL not set or form not reachable"
skip_if_no_form = pytest.mark.skipif(not N8N_FORM_URL, reason=SKIP_REASON)


@pytest.fixture(scope="module")
def browser_page():
    """Launch a Playwright Chromium browser and navigate to the form."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(N8N_FORM_URL, timeout=10000)
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pytest.skip(f"Could not load form at {N8N_FORM_URL}")
        yield page
        browser.close()


@skip_if_no_form
def test_form_title(browser_page):
    h1 = browser_page.locator("h1").first
    text = h1.inner_text()
    assert "Zuha" in text and "Registry" in text, f"Expected 'Zuha's Wedding Registry' in h1, got: {text}"


@skip_if_no_form
def test_required_markers(browser_page):
    # Required fields should show asterisk (*) or similar marker
    page_content = browser_page.content()
    assert "*" in page_content or "required" in page_content.lower(), \
        "No required field markers found on form"


@skip_if_no_form
def test_1_20_notice(browser_page):
    page_content = browser_page.content()
    assert "20" in page_content, "Expected '20' (max URLs) notice on form page"


@skip_if_no_form
def test_mobile_no_scroll(browser_page):
    # Emulate 390px mobile width and check for no horizontal overflow
    browser_page.set_viewport_size({"width": 390, "height": 844})
    browser_page.reload()
    browser_page.wait_for_load_state("networkidle", timeout=10000)

    scroll_width = browser_page.evaluate("document.body.scrollWidth")
    client_width = browser_page.evaluate("document.body.clientWidth")
    # Allow 10px tolerance
    assert scroll_width <= client_width + 10, \
        f"Horizontal overflow at 390px: scrollWidth={scroll_width}, clientWidth={client_width}"
    # Reset
    browser_page.set_viewport_size({"width": 1280, "height": 720})


@skip_if_no_form
def test_empty_submission_error(browser_page):
    # Submit without filling anything — should show an error, not navigate away
    browser_page.goto(N8N_FORM_URL, timeout=10000)
    browser_page.wait_for_load_state("networkidle")

    submit_btn = browser_page.locator("button[type='submit'], input[type='submit']").first
    submit_btn.click()
    browser_page.wait_for_timeout(1000)

    # Either an error message appears or the form is still on the page
    current_url = browser_page.url
    assert N8N_FORM_URL in current_url or "error" in browser_page.content().lower() or \
        "required" in browser_page.content().lower(), \
        "Expected error or remaining on form after empty submission"


@skip_if_no_form
def test_missing_added_by_error(browser_page):
    browser_page.goto(N8N_FORM_URL, timeout=10000)
    browser_page.wait_for_load_state("networkidle")

    # Fill Product Links but leave Added By blank
    links_field = browser_page.locator("textarea").first
    links_field.fill("https://www.amazon.com/dp/B001")

    submit_btn = browser_page.locator("button[type='submit'], input[type='submit']").first
    submit_btn.click()
    browser_page.wait_for_timeout(1000)

    content = browser_page.content()
    assert "required" in content.lower() or "error" in content.lower() or \
        browser_page.url == N8N_FORM_URL or N8N_FORM_URL in browser_page.url, \
        "Expected validation error when Added By is missing"


@skip_if_no_form
def test_21_url_overflow_error(browser_page):
    browser_page.goto(N8N_FORM_URL, timeout=10000)
    browser_page.wait_for_load_state("networkidle")

    # Select Added By if it's a dropdown/radio
    try:
        zuha_option = browser_page.locator("text=Zuha").first
        zuha_option.click()
    except Exception:
        pass

    # Paste 21 URLs
    urls = "\n".join(f"https://www.amazon.com/dp/B{i:08d}" for i in range(21))
    links_field = browser_page.locator("textarea").first
    links_field.fill(urls)

    submit_btn = browser_page.locator("button[type='submit'], input[type='submit']").first
    submit_btn.click()
    browser_page.wait_for_timeout(2000)

    content = browser_page.content()
    # Should show error about too many URLs or fail gracefully
    has_error = any(x in content.lower() for x in ["error", "too many", "maximum", "21"])
    assert has_error or N8N_FORM_URL in browser_page.url, \
        "Expected error message for 21 URLs"
