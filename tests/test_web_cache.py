"""The console must never be served from a browser cache after an update."""

from __future__ import annotations

import unittest
import urllib.request
from pathlib import Path

from flow8.lan_hub import Flow8LanHub
from flow8.service import Flow8Service

ROOT = Path(__file__).resolve().parent.parent


class CacheHeaderTests(unittest.TestCase):
    def setUp(self):
        self.service = Flow8Service(auto_connect=False)
        self.hub = Flow8LanHub(self.service, host="127.0.0.1", port=0)
        self.port = self.hub.start()
        self.addCleanup(self.hub.stop)

    def get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as response:
            return response.headers, response.read()

    def assert_no_store(self, headers):
        cache = (headers.get("Cache-Control") or "").lower()
        self.assertIn("no-store", cache)
        self.assertIn("no-cache", cache)
        self.assertEqual(headers.get("Pragma"), "no-cache")
        self.assertEqual(headers.get("Expires"), "0")

    def test_index_is_never_cached(self):
        headers, body = self.get("/")
        self.assert_no_store(headers)
        self.assertIn(b"FLOW 8", body)

    def test_app_js_and_styles_are_never_cached(self):
        for path in ("/app.js", "/styles.css"):
            with self.subTest(path=path):
                headers, body = self.get(path)
                self.assert_no_store(headers)
                self.assertGreater(len(body), 1000)

    def test_cache_busting_query_still_serves_the_asset(self):
        headers, body = self.get("/app.js?v=20261119")
        self.assert_no_store(headers)
        self.assertGreater(len(body), 1000)
        headers, body = self.get("/styles.css?v=1")
        self.assert_no_store(headers)
        self.assertGreater(len(body), 1000)

    def test_api_and_sse_are_not_cached(self):
        headers, _ = self.get("/api/session")
        cache = (headers.get("Cache-Control") or "").lower()
        self.assertIn("no-store", cache)

    def test_text_assets_are_gzipped_only_when_asked(self):
        import gzip
        plain_headers, plain = self.get("/app.js")
        self.assertIsNone(plain_headers.get("Content-Encoding"))
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}/app.js", headers={"Accept-Encoding": "gzip"})
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(response.headers.get("Content-Encoding"), "gzip")
            self.assertEqual(response.headers.get("Vary"), "Accept-Encoding")
            self.assertEqual(gzip.decompress(response.read()), plain)

    def test_unknown_asset_is_a_404_json(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/nope.js")
        self.assertEqual(ctx.exception.code, 404)
        ctx.exception.close()


if __name__ == "__main__":
    unittest.main()
