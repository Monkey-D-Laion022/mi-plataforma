"""Pruebas de las listas M3U de películas y series (sin internet).  python -m unittest discover -s tests -v"""
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import common  # noqa: E402
import export_m3u  # noqa: E402
import guard  # noqa: E402


def ok(url, **kw):
    return {"url": url, "type": "mp4", "status": "ok", **kw}


MOVIES = [
    {"id": "m-b", "title": "Beta, la película", "genres": ["drama"], "poster": "https://p/b.jpg", "rights": "Propio",
     "sources": [{"url": "https://s/b-dead.mp4", "status": "dead"}, ok("https://s/b.mp4")]},
    {"id": "m-a", "title": "Alfa", "genres": [], "license": "CC BY 3.0", "sources": [ok("http://s/a.m3u8", referrer="https://r/")]},
    {"id": "m-x", "title": "Sin derechos declarados", "sources": [ok("https://s/x.mp4")]},
    {"id": "m-d", "title": "Caída", "rights": "Propio", "sources": [{"url": "https://s/d.mp4", "status": "dead"}]},
    {"id": "m-e", "title": "Externa", "rights": "Oficial", "sources": [{"url": "http://www.cine.ar/", "type": "external", "status": "external"}]},
    {"id": "m-f", "title": "De prueba", "rights": "x", "sources": [{"url": "https://e.invalid/f.mp4", "status": "fixture"}]},
    {"id": "m-u", "title": "Sin verificar", "rights": "x", "sources": [{"url": "https://s/u.mp4", "status": "unchecked"}]},
]
SERIES = [{"id": "s-1", "title": "Mi \"Serie\"", "poster": "https://p/s.jpg", "rights": "Propio", "seasons": [
    {"number": 2, "episodes": [{"number": 1, "title": "Episodio 1", "sources": [ok("https://s/s2e1.mp4")]}]},
    {"number": 1, "episodes": [{"number": 2, "title": "Segundo", "sources": [ok("https://s/s1e2.mp4")]},
                               {"number": 1, "title": "Piloto", "sources": [ok("https://s/s1e1.mp4")]},
                               {"number": 3, "title": "Caído", "sources": [{"url": "https://s/s1e3.mp4", "status": "dead"}]}]}]}]


class VodRenderTests(unittest.TestCase):
    def setUp(self):
        self.entries = export_m3u.vod_entries(MOVIES, SERIES)

    def test_only_ok_publishable_items_are_exported(self):
        names = [e["name"] for e in self.entries if e["kind"] == "movie"]
        self.assertEqual(names, ["Alfa", "Beta, la película"])  # orden alfabético; sin derechos/caída/externa/prueba/sin verificar

    def test_series_episodes_are_sorted_and_named(self):
        names = [e["name"] for e in self.entries if e["kind"] == "series"]
        self.assertEqual(names, ['Mi "Serie" S01E01 - Piloto', 'Mi "Serie" S01E02 - Segundo', 'Mi "Serie" S02E01'])

    def test_text_is_valid_m3u(self):
        text, n = export_m3u.render_vod(self.entries)
        self.assertEqual(n, 5)
        lines = text.splitlines()
        self.assertEqual(lines[0], "#EXTM3U")
        self.assertEqual(sum(1 for ln in lines if ln.startswith("#EXTINF")), 5)
        for i, ln in enumerate(lines):
            if ln.startswith("#EXTINF"):
                self.assertEqual(ln.count(","), 1, ln)  # una sola coma: la que separa atributos y nombre
                nxt = next(x for x in lines[i + 1:] if not x.startswith("#EXTVLCOPT"))
                self.assertTrue(nxt.startswith(("http://", "https://")))

    def test_groups_and_attributes(self):
        text, _ = export_m3u.render_vod(self.entries)
        self.assertIn('group-title="Películas / Drama"', text)
        self.assertIn('group-title="Películas / Sin Género"', text)
        self.assertIn("group-title=\"Series / Mi 'Serie'\"", text)  # las comillas dobles se neutralizan
        self.assertIn('tvg-logo="https://p/b.jpg"', text)
        self.assertIn("#EXTVLCOPT:http-referrer=https://r/", text)

    def test_dead_sources_never_appear(self):
        text, _ = export_m3u.render_vod(self.entries)
        for bad in ("b-dead", "s1e3", "e.invalid", "u.mp4", "cine.ar", "/x.mp4", "/d.mp4"):
            self.assertNotIn(bad, text)


class VodEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)
        d = Path("public/data")
        d.mkdir(parents=True)
        live = [{"id": "A.ar", "name": "Canal A", "country": "AR", "country_name": "Argentina", "categories": ["news"],
                 "sources": [ok("https://c/a.m3u8", type="hls")]}]
        (d / "live.json").write_text(json.dumps({"origin": "iptv-org/api", "items": live}))
        (d / "movies.json").write_text(json.dumps({"origin": "x", "items": MOVIES}))
        (d / "series.json").write_text(json.dumps({"origin": "x", "items": SERIES}))

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def digest(self):
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path("public/data").glob("*.json")}

    def test_export_creates_all_files_and_does_not_touch_the_pwa_catalogs(self):
        before = self.digest()
        self.assertEqual(export_m3u.main(), 0)
        self.assertEqual(self.digest(), before)  # la PWA lee estos JSON: siguen idénticos
        for name in ("live-ar.m3u", "live-latam.m3u", "movies.m3u", "series.m3u", "vod.m3u"):
            self.assertTrue((Path("public/lists") / name).is_file(), name)
        self.assertEqual(guard.count_m3u(Path("public/lists/vod.m3u")), 5)
        self.assertEqual(guard.count_m3u(Path("public/lists/movies.m3u")), 2)
        self.assertEqual(guard.count_m3u(Path("public/lists/series.m3u")), 3)

    def test_guard_accepts_consistent_lists(self):
        export_m3u.main()
        self.assertEqual(guard.main(["lists"]), 0)
        rep = json.loads(Path("public/data/report.json").read_text())
        self.assertEqual(rep["lists"]["vod_m3u"], 5)

    def test_guard_detects_empty_vod_by_process_error(self):
        export_m3u.main()
        Path("public/lists/vod.m3u").write_text("#EXTM3U\n")
        self.assertEqual(guard.main(["lists"]), 1)

    def test_empty_catalogs_produce_valid_empty_lists(self):
        for n in ("movies.json", "series.json"):
            Path("public/data", n).write_text(json.dumps({"origin": "x", "items": []}))
        export_m3u.main()
        self.assertEqual(Path("public/lists/vod.m3u").read_text(), "#EXTM3U\n")
        self.assertEqual(guard.main(["lists"]), 0)

    def test_missing_catalog_files_do_not_crash(self):
        Path("public/data/movies.json").unlink()
        Path("public/data/series.json").unlink()
        self.assertEqual(export_m3u.main(), 0)


class PwaUnaffectedTests(unittest.TestCase):
    def test_pwa_reads_json_catalogs_not_m3u_files(self):
        js = (ROOT / "public/app.js").read_text(encoding="utf-8")
        for name in ("live", "movies", "series"):
            self.assertIn(name, js)
        self.assertIn("data/${n}.json", js)
        self.assertNotIn(".m3u\"", js.replace("m3u8", ""))  # la app no consume las listas exportadas


if __name__ == "__main__":
    unittest.main()
