import json
import struct
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase, override_settings


class PwaTests(SimpleTestCase):
    def test_public_shell_has_manifest_but_no_per_browser_csrf_token(self):
        with override_settings(GEMINI_API_KEY="test-key-must-not-appear"):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'rel="manifest" href="/manifest.json"')
        self.assertContains(response, 'id="prompt"')
        self.assertNotContains(response, "csrfmiddlewaretoken")
        self.assertNotContains(response, "test-key-must-not-appear")
        self.assertNotIn("csrftoken", response.cookies)

    def test_manifest_provides_standalone_root_launch_and_real_icons(self):
        response = self.client.get("/manifest.json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/manifest+json")
        manifest = json.loads(response.content)
        self.assertEqual(manifest["name"], "AI Assistant")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["start_url"], "/")
        self.assertEqual(manifest["scope"], "/")
        self.assertEqual(manifest["id"], "/")
        self.assertEqual({icon["sizes"] for icon in manifest["icons"]}, {"192x192", "512x512"})
        for icon in manifest["icons"]:
            self.assertEqual(icon["type"], "image/png")
            filename = finders.find(icon["src"].removeprefix(settings.STATIC_URL))
            self.assertIsNotNone(filename)
            raw = Path(filename).read_bytes()
            self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n")
            size = int(icon["sizes"].split("x")[0])
            self.assertEqual(struct.unpack(">II", raw[16:24]), (size, size))

    def test_worker_is_root_scoped_javascript_and_revalidated(self):
        response = self.client.get("/serviceworker.js")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/javascript")
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertEqual(response["Cache-Control"], "no-cache")

    def test_worker_precache_assets_are_collectable(self):
        assets = [
            "vendor/bootstrap.min.css", "assistant/css/app.css", "assistant/js/app.js",
            "assistant/img/icon.svg", "assistant/img/icon-192.png", "assistant/img/icon-512.png",
        ]
        for asset in assets:
            with self.subTest(asset=asset):
                self.assertIsNotNone(finders.find(asset))
