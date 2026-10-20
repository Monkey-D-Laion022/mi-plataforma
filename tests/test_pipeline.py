"""Pruebas sin internet: levantan un servidor HTTP local que simula fuentes buenas y malas.

Ejecutar:  python -m unittest discover -s tests -v
"""
from __future__ import annotations

import http.server
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_live  # noqa: E402
import build_movies  # noqa: E402
import common  # noqa: E402
import export_m3u  # noqa: E402
import verify  # noqa: E402

MASTER = "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=800000\nvariant.m3u8\n"
MEDIA = "#EXTM3U\n#EXT-X-TARGETDURATION:6\n#EXTINF:6.0,\nseg1.ts\n"


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):  # silencio
        pass

    def _send(self, code, body=b"", ctype="text/plain"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        p = self.path
        if p == "/master.m3u8":
            self._send(200, MASTER.encode(), "application/vnd.apple.mpegurl")
        elif p == "/variant.m3u8":
            self._send(200, MEDIA.encode(), "application/vnd.apple.mpegurl")
        elif p == "/broken-master.m3u8":
            self._send(200, b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1\nmissing.m3u8\n")
        elif p == "/missing.m3u8":
            self._send(404, b"nope")
        elif p == "/media.m3u8":
            self._send(200, MEDIA.encode(), "application/x-mpegURL")
        elif p == "/html":
            self._send(200, b"<html>login</html>", "text/html")
        elif p == "/gone.m3u8":
            self._send(404, b"gone")
        elif p == "/forbidden.m3u8":
            self._send(403, b"geo")
        elif p == "/error.m3u8":
            self._send(503, b"busy")
        elif p == "/movie.mp4":
            self._send(206, b"\x00" * 1024, "video/mp4")
        elif p == "/fake.mp4":
            self._send(200, b"<html>", "text/html")
        elif p == "/needs-referrer.m3u8":
            if self.headers.get("Referer") == "https://allowed.example/":
                self._send(200, MEDIA.encode(), "application/vnd.apple.mpegurl")
            else:
                self._send(403, b"referer")
        else:
            self._send(404)


class VerifyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def check(self, path, **extra):
        return verify.check_source({"url": self.base + path, "type": extra.pop("type", "hls"), **extra}, timeout=5)

    def test_master_playlist_ok(self):
        r = self.check("/master.m3u8")
        self.assertEqual(r["status"], common.STATUS_OK, r)

    def test_media_playlist_ok(self):
        self.assertEqual(self.check("/media.m3u8")["status"], common.STATUS_OK)

    def test_master_with_dead_variant(self):
        self.assertEqual(self.check("/broken-master.m3u8")["status"], common.STATUS_DEAD)

    def test_html_is_bad_format(self):
        self.assertEqual(self.check("/html")["status"], common.STATUS_BAD_FORMAT)

    def test_404_is_dead(self):
        self.assertEqual(self.check("/gone.m3u8")["status"], common.STATUS_DEAD)

    def test_403_is_restricted_not_dead(self):
        r = self.check("/forbidden.m3u8")
        self.assertEqual(r["status"], common.STATUS_RESTRICTED)
        self.assertIn("geobloqueo", r["reason"])

    def test_503_is_dead(self):
        self.assertEqual(self.check("/error.m3u8")["status"], common.STATUS_DEAD)

    def test_mp4_ok_and_fake_mp4(self):
        self.assertEqual(self.check("/movie.mp4", type="mp4")["status"], common.STATUS_OK)
        self.assertEqual(self.check("/fake.mp4", type="mp4")["status"], common.STATUS_BAD_FORMAT)

    def test_referrer_is_sent_and_flagged(self):
        r = self.check("/needs-referrer.m3u8", referrer="https://allowed.example/")
        self.assertEqual(r["status"], common.STATUS_OK)
        self.assertIn("exige_cabeceras", r["flags"])
        self.assertEqual(self.check("/needs-referrer.m3u8")["status"], common.STATUS_RESTRICTED)

    def test_http_flag(self):
        self.assertIn("http_sin_cifrar", self.check("/media.m3u8")["flags"])

    def test_unreachable_is_dead(self):
        r = verify.check_source({"url": "http://nohost.invalid/x.m3u8", "type": "hls"}, timeout=3)
        self.assertEqual(r["status"], common.STATUS_DEAD)

    def test_fixture_is_never_verified(self):
        r = verify.check_source({"url": "https://ejemplo.invalid/a.m3u8", "status": common.STATUS_FIXTURE})
        self.assertEqual(r, {})


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.api = ROOT / "data" / "fixtures" / "api"

    def build(self):
        ch, st, bl = build_live.load_api(self.api, build_live.API_BASE)
        return build_live.build(ch, st, bl, common.LATAM_COUNTRIES, fixture=True)

    def test_filters(self):
        cat = self.build()
        ids = {i["id"] for i in cat["items"]}
        self.assertEqual(ids, {"PruebaNoticiasAR.ar", "PruebaDeportesAR.ar", "PruebaCulturaAR.ar",
                               "PruebaInfantilUY.uy", "PruebaMusicaMX.mx"})
        self.assertEqual(cat["skipped"], {"nsfw": 1, "cerrado": 1, "blocklist": 1, "sin_fuentes": 1,
                                          "fuera_de_allowlist": 0})

    def test_allowlist_mode(self):
        ch, st, bl = build_live.load_api(self.api, build_live.API_BASE)
        cat = build_live.build(ch, st, bl, common.LATAM_COUNTRIES, fixture=True, allowlist={"PruebaNoticiasAR.ar"})
        self.assertEqual([i["id"] for i in cat["items"]], ["PruebaNoticiasAR.ar"])
        self.assertEqual(cat["skipped"]["fuera_de_allowlist"], 5)

    def test_read_allowlist_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.txt"
            p.write_text("# comentario\nCanalA.ar  # oficial\n\nCanalB.uy\n")
            self.assertEqual(build_live.read_allowlist(p), {"CanalA.ar", "CanalB.uy"})
        self.assertEqual(build_live.read_allowlist(Path("no-existe.txt")), set())

    def test_argentina_first(self):
        cat = self.build()
        self.assertEqual([i["country"] for i in cat["items"]], ["AR", "AR", "AR", "UY", "MX"])

    def test_fixture_sources_are_marked(self):
        for item in self.build()["items"]:
            for s in item["sources"]:
                self.assertEqual(s["status"], common.STATUS_FIXTURE)

    def test_real_build_starts_unchecked(self):
        ch, st, bl = build_live.load_api(self.api, build_live.API_BASE)
        cat = build_live.build(ch, st, bl, ["AR"], fixture=False)
        for item in cat["items"]:
            for s in item["sources"]:
                self.assertEqual(s["status"], common.STATUS_UNCHECKED)


class VerifiedStampTests(unittest.TestCase):
    def test_fixture_catalog_gets_no_verified_at(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "live.json"
            p.write_text(json.dumps({"items": [{"id": "x", "sources": [{"url": "https://e.invalid/a.m3u8", "status": "fixture"}]}],
                                     "verified_at": "2020-01-01T00:00:00+00:00"}))
            verify.verify_catalog(p, {})
            self.assertNotIn("verified_at", json.loads(p.read_text()))


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)
        Path("public/data").mkdir(parents=True)

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def test_m3u_only_ok_sources(self):
        items = [
            {"id": "A.ar", "name": "Canal, A", "country": "AR", "country_name": "Argentina", "categories": ["news"],
             "sources": [{"url": "https://a/x.m3u8", "status": "ok", "referrer": "https://r/"}]},
            {"id": "B.ar", "name": "Canal B", "country": "AR", "country_name": "Argentina", "categories": ["news"],
             "sources": [{"url": "https://b/x.m3u8", "status": "dead"}]},
            {"id": "C.ar", "name": "Canal C", "country": "AR", "country_name": "Argentina", "categories": ["news"],
             "sources": [{"url": "https://c/x.m3u8", "status": "fixture"}]},
        ]
        text, n = export_m3u.render(items)
        self.assertEqual(n, 1)
        self.assertIn("https://a/x.m3u8", text)
        self.assertIn("#EXTVLCOPT:http-referrer=https://r/", text)
        self.assertNotIn("https://b/x.m3u8", text)
        self.assertNotIn("https://c/x.m3u8", text)
        self.assertIn("Canal  A", text)


class M3UParserTests(unittest.TestCase):
    def test_parse(self):
        text = ('#EXTM3U\n#EXTINF:-1 tvg-id="X.ar" tvg-logo="http://l/x.png" group-title="Noticias",Canal X\n'
                '#EXTVLCOPT:http-referrer=https://r/\n#EXTVLCOPT:http-user-agent=UA/1\nhttps://x/live.m3u8\n')
        e = common.parse_m3u(text)[0]
        self.assertEqual((e["name"], e["url"], e["referrer"], e["user_agent"]),
                         ("Canal X", "https://x/live.m3u8", "https://r/", "UA/1"))
        self.assertEqual(e["attrs"]["tvg-id"], "X.ar")


if __name__ == "__main__":
    unittest.main()
    
