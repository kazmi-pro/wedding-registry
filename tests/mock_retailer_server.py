"""
mock_retailer_server.py — Local HTTP server for unit testing scraping logic.
Port: 8089

Endpoints:
  /amazon-product         → Amazon CAPTCHA HTML (robot check)
  /og-product             → Valid OG tag HTML with og:title and og:price:amount
  /generic-storefront     → Generic storefront (no useful OG tags)
  /forbidden              → 403 Forbidden
  /slug-product/breville-smart-oven-air-fryer-pro/  → 403 (slug is rescuable)

Usage:
    python tests/mock_retailer_server.py
    # In another terminal: curl http://localhost:8089/og-product

Or import and use as a context manager in tests:
    from mock_retailer_server import MockRetailerServer
    with MockRetailerServer() as server:
        url = server.url('/og-product')
        ...
"""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8089

AMAZON_CAPTCHA_HTML = b"""<!DOCTYPE html>
<html>
<head><title>Robot Check</title></head>
<body>
<p>To discuss automated access to Amazon data please contact api-services-support@amazon.com.</p>
<p>Refer to our <a href="/gp/help/customer/display.html?nodeId=G2G2MC3CQKQKCE9J">Conditions of Use</a> and our <a href="/gp/help/customer/display.html?nodeId=G">Privacy Notice</a>.</p>
<form action="/errors/validateCaptcha">
<div class="a-row a-spacing-double-large">
<label>Type the characters you see in this image:</label>
<div class="a-row a-spacing-micro"><img src="/captcha/01/abc/captcha.jpg" /></div>
<div class="a-section"><input type="text" name="field-keywords" /></div>
<button type="submit">Continue shopping</button>
</div>
</form>
</body>
</html>"""

OG_PRODUCT_HTML = b"""<!DOCTYPE html>
<html>
<head>
<title>Zojirushi NS-TSC10 Micom Rice Cooker</title>
<meta property="og:title" content="Zojirushi NS-TSC10 5.5-Cup Micom Rice Cooker and Warmer" />
<meta property="og:price:amount" content="149.99" />
<meta property="og:price:currency" content="USD" />
<meta property="og:image" content="https://example.com/product.jpg" />
<meta property="og:description" content="Advanced fuzzy logic technology automatically adjusts cooking temperature." />
</head>
<body>
<h1>Zojirushi NS-TSC10 5.5-Cup Micom Rice Cooker and Warmer</h1>
<p>Price: $149.99</p>
</body>
</html>"""

GENERIC_STOREFRONT_HTML = b"""<!DOCTYPE html>
<html>
<head>
<title>Amazon.com</title>
</head>
<body>
<h1>Welcome to Amazon</h1>
<p>Millions of products, delivered to your door.</p>
</body>
</html>"""


class MockHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress access logs

    def do_GET(self):
        path = self.path.rstrip("/")

        if path == "/amazon-product":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(AMAZON_CAPTCHA_HTML)

        elif path == "/og-product":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(OG_PRODUCT_HTML)

        elif path == "/generic-storefront":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(GENERIC_STOREFRONT_HTML)

        elif path == "/forbidden":
            self.send_response(403)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"403 Forbidden")

        elif "/breville-smart-oven-air-fryer-pro" in path:
            # 403 but URL slug is rescuable by the parser
            self.send_response(403)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"403 Forbidden")

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")


class MockRetailerServer:
    """Context manager that runs the mock server in a background thread."""

    def __init__(self, port: int = PORT):
        self.port = port
        self._server = None
        self._thread = None

    def url(self, path: str) -> str:
        return f"http://localhost:{self.port}{path}"

    def __enter__(self):
        self._server = HTTPServer(("127.0.0.1", self.port), MockHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *args):
        if self._server:
            self._server.shutdown()


if __name__ == "__main__":
    print(f"Mock retailer server running on http://localhost:{PORT}")
    print("Endpoints:")
    print("  /amazon-product         → CAPTCHA")
    print("  /og-product             → Valid OG tags")
    print("  /generic-storefront     → No OG tags")
    print("  /forbidden              → 403")
    print("  /slug-product/breville-smart-oven-air-fryer-pro/ → 403 + rescuable slug")
    server = HTTPServer(("127.0.0.1", PORT), MockHandler)
    server.serve_forever()
