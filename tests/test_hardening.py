"""Pruebas de robustez: aislamiento de errores, importador de listas M3U, guardias, add-on de Stremio e higiene.

Diseño: las pruebas del importador M3U son OBLIGATORIAS (si falta `m3u_entries`, fallan a propósito).
Las que dependen de `manual_entries` (entradas manuales heredadas) son OPCIONALES: si esa función no
existe en tools/build_movies.py, se saltan en vez de romper la compilación.

Ejecutar:  python -m unittest discover -s tests -v
"""
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_movies  # noqa: E402
import build_stremio  # noqa: E402
import common  # noqa: E402
import export_m3u  # noqa: E402
import guard  # noqa: E402
import verify  # noqa: E402


HAS_MANUAL = unittest.skipUnless(hasattr(build_movies, "manual_entries"),
                                 "build_movies ya no expone manual_entries (entradas manuales heredadas)")


def src(url="https://x.example/a.m3u8", status="ok", **kw):
    return {"url": url, "type": "hls", "status": status, "reason": "", **kw}


class IsolationTests(unittest.TestCase):
    def test_safe_check_converts_any_exception_into_dead(self):
        with mock.patch.object(verify, "check_source", side_effect=UnicodeEncodeError("ascii", "ñ", 0, 1, "x")):
            r = verify.safe_check(src(status="unchecked"))
        self.assertEqual(r["status"], common.STATUS_DEAD)
        self.assertIn("Error interno", r["reason"])

    def test_one_crashing_source_does_not_stop_the_catalog(self):
        def fake(source, timeout=10):
            if "boom" in source["url"]:
                raise RuntimeError("explotó")
            return {"status": "ok", "reason": "ok", "http": 200, "checked": "t", "flags": []}
        catalog = {"items": [{"id": "a", "sources": [src("https://x/ok1.m3u8", "unchecked")]},
                             {"id": "b", "sources": [src("https://x/boom.m3u8", "unchecked")]},
                             {"id": "c", "sources": [src("https://x/ok2.m3u8", "unchecked")]}]}
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "live.json"
            p.write_text(json.dumps(catalog))
            with mock.patch.object(verify, "check_source", side_effect=fake):
                verify.verify_catalog(p, {})
            out = json.loads(p.read_text())
        statuses = [i["sources"][0]["status"] for i in out["items"]]
        self.assertEqual(statuses, ["ok", "dead", "ok"])
        self.assertIn("verified_at", out)

    def test_external_sources_are_not_verified(self):
        self.assertEqual(verify.check_source({"url": "http://www.cine.ar/", "type": "external", "status": "external"}), {})

    @HAS_MANUAL
    def test_broken_manual_json_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "m.json"
            p.write_text("{ esto no es json")
            self.assertEqual(build_movies.manual_entries(p, "movie"), [])

    @HAS_MANUAL
    def test_manual_entry_that_is_not_an_object_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "m.json"
            p.write_text(json.dumps(["texto suelto", {"title": "Ok", "rights": "CC BY", "sources": [{"url": "https://x"}]}]))
            self.assertEqual([e["title"] for e in build_movies.manual_entries(p, "movie")], ["Ok"])


@HAS_MANUAL
class ManualDataTests(unittest.TestCase):
    """Valida data/manual/*.json SI existen (son opcionales). No exige ningún contenido en particular."""

    def entries(self):
        out = []
        for name, kind in (("movies.json", "movie"), ("series.json", "series")):
            path = ROOT / "data/manual" / name
            if path.exists():
                out += build_movies.manual_entries(path, kind)
        return out

    def test_entries_are_well_formed(self):
        for e in self.entries():
            self.assertTrue(e.get("title"))
            self.assertTrue(e.get("rights"), e["title"])
            self.assertTrue(e.get("sources") or e.get("seasons"), e["title"])

    def test_nothing_starts_as_ok(self):
        for e in self.entries():
            for s in e.get("sources", []):
                self.assertNotEqual(s["status"], common.STATUS_OK)  # "ok" solo lo da el verificador


M3U_TEXT = (
    "#EXTM3U\n"
    '#EXTINF:-1 tvg-logo="https://x/p.png" group-title="Documental",Mi Video\n'
    "https://s/a.mp4\n"
    "#EXTINF:-1,Película Dos\n"
    "https://s/b.m3u8\n"
    "#EXTINF:-1,Sin web\n"
    "magnet:?xt=urn:btih:abc\n"
    "#EXTINF:-1,Canal raro\n"
    "acestream://123\n"
    "#EXTINF:-1,Mi Serie S01E02 - Segundo\n"
    "https://s/s1e2.mp4\n"
    "#EXTINF:-1,Mi Serie S01E01 - Primero\n"
    "https://s/s1e1.mp4\n"
    "#EXTINF:-1,Mi Serie 2x01\n"
    "https://s/s2e1.mkv\n"
    "#EXTINF:-1 tvg-id=\"x\",Con cabeceras\n"
    "#EXTVLCOPT:http-referrer=https://r/\n"
    "#EXTVLCOPT:http-user-agent=UA/1\n"
    "https://s/h.m3u8\n"
)
CFG = {"name": "Mi lista", "url": "https://l/x.m3u", "rights": "Contenido propio"}


def run_m3u(cfg=None, text=M3U_TEXT, result=None):
    result = result or (200, {}, text.encode(), None)
    with mock.patch.object(build_movies, "http_get", return_value=result):
        return build_movies.m3u_entries(cfg or CFG)


class M3UImportTests(unittest.TestCase):
    def test_function_is_exposed(self):
        self.assertTrue(callable(getattr(build_movies, "m3u_entries", None)))

    def test_movies_series_and_discards(self):
        out = run_m3u()
        movies = [m for m in out if m["kind"] == "movie"]
        series = [m for m in out if m["kind"] == "series"]
        self.assertEqual([m["title"] for m in movies], ["Mi Video", "Película Dos", "Con cabeceras"])
        self.assertEqual([m["title"] for m in series], ["Mi Serie"])  # magnet y acestream descartados

    def test_series_are_grouped_and_sorted(self):
        serie = [m for m in run_m3u() if m["kind"] == "series"][0]
        self.assertEqual([s["number"] for s in serie["seasons"]], [1, 2])
        self.assertEqual([e["number"] for e in serie["seasons"][0]["episodes"]], [1, 2])
        self.assertEqual(serie["seasons"][0]["episodes"][0]["title"], "Primero")
        self.assertEqual(serie["seasons"][1]["episodes"][0]["title"], "Episodio 1")

    def test_every_source_starts_unchecked_with_declared_rights(self):
        for item in run_m3u():
            self.assertEqual(item["rights"], "Contenido propio")
            sources = item.get("sources") or [s for se in item["seasons"] for ep in se["episodes"] for s in ep["sources"]]
            self.assertTrue(sources)
            for s in sources:
                self.assertEqual(s["status"], common.STATUS_UNCHECKED)
                self.assertTrue(s["url"].startswith(("http://", "https://")))

    def test_source_types_and_metadata(self):
        by_title = {m["title"]: m for m in run_m3u()}
        self.assertEqual(by_title["Mi Video"]["sources"][0]["type"], "mp4")
        self.assertEqual(by_title["Película Dos"]["sources"][0]["type"], "hls")
        self.assertEqual(by_title["Mi Video"]["genres"], ["documental"])
        self.assertEqual(by_title["Mi Video"]["poster"], "https://x/p.png")
        h = by_title["Con cabeceras"]["sources"][0]
        self.assertEqual((h["referrer"], h["user_agent"]), ("https://r/", "UA/1"))

    def test_ids_are_unique(self):
        ids = [m["id"] for m in run_m3u()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_list_without_rights_is_skipped(self):
        self.assertEqual(run_m3u({"url": "https://l/x.m3u"}), [])

    def test_non_http_list_url_is_skipped(self):
        self.assertEqual(run_m3u({"url": "file:///etc/passwd", "rights": "x"}), [])

    def test_download_failures_return_empty(self):
        self.assertEqual(run_m3u(result=(404, {}, b"", None)), [])
        self.assertEqual(run_m3u(result=(None, {}, b"", "URLError: timeout")), [])

    def test_unexpected_exception_is_isolated(self):
        with mock.patch.object(build_movies, "http_get", side_effect=RuntimeError("boom")):
            self.assertEqual(build_movies.m3u_entries(CFG), [])

    def test_garbage_content_returns_empty(self):
        self.assertEqual(run_m3u(text="<html>no soy una lista</html>"), [])

    def test_max_items_limits_entries(self):
        out = run_m3u({**CFG, "max_items": 1})
        self.assertEqual([m["title"] for m in out], ["Mi Video"])

    def test_dedupe_keeps_first(self):
        a, b = {"id": "x", "title": "A"}, {"id": "x", "title": "B"}
        self.assertEqual(build_movies.dedupe([a, b]), [a])

    def test_catalog_flows_through_verifier_and_guard_rules(self):
        """Lo importado debe poder pasar por verify.safe_check (red simulada: la prueba no usa internet)."""
        item = run_m3u()[0]
        with mock.patch.object(verify, "http_get", return_value=(206, {"Content-Type": "video/mp4"}, b"\x00", None)):
            res = verify.safe_check(item["sources"][0], timeout=1)
        self.assertEqual(res["status"], common.STATUS_OK)


def write_catalog(tmp, live_items, movies_items=None, origin="iptv-org/api"):
    d = Path(tmp) / "public/data"
    d.mkdir(parents=True, exist_ok=True)
    (d / "live.json").write_text(json.dumps({"origin": origin, "items": live_items}))
    (d / "movies.json").write_text(json.dumps({"origin": "x", "items": movies_items or []}))
    (d / "series.json").write_text(json.dumps({"origin": "x", "items": []}))


def chan(cid, country, *sources):
    return {"id": cid, "name": cid, "country": country, "country_name": country, "categories": ["news"],
            "sources": list(sources)}


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def run_guard(self, *args):
        return guard.main(["catalogs", *args])

    def test_healthy_catalog_passes(self):
        write_catalog(".", [chan("A.ar", "AR", src()), chan("B.ar", "AR", src(status="dead", reason="HTTP 404"))])
        self.assertEqual(self.run_guard("--strict"), 0)
        rep = json.loads(Path("public/data/report.json").read_text())
        self.assertEqual(rep["live_ok"], {"argentina": 1, "latam": 1})

    def test_empty_live_fails(self):
        write_catalog(".", [])
        self.assertEqual(self.run_guard(), 1)

    def test_no_argentina_fails(self):
        write_catalog(".", [chan("A.mx", "MX", src())])
        self.assertEqual(self.run_guard(), 1)

    def test_network_outage_is_detected_as_process_error(self):
        dead = [chan(f"C{i}.ar", "AR", src(status="dead", reason="Sin respuesta (URLError: timeout)")) for i in range(30)]
        write_catalog(".", dead)
        self.assertEqual(self.run_guard(), 1)

    def test_all_checked_but_none_ok_fails(self):
        dead = [chan(f"C{i}.ar", "AR", src(status="dead", reason="HTTP 404")) for i in range(25)]
        write_catalog(".", dead)
        self.assertEqual(self.run_guard(), 1)

    def test_fixture_data_blocks_real_run_only_in_strict(self):
        write_catalog(".", [chan("A.ar", "AR", src(status="fixture"))], origin="DATOS DE PRUEBA locales")
        self.assertEqual(self.run_guard("--strict"), 1)
        self.assertEqual(self.run_guard(), 0)

    def test_ar_without_ok_is_only_a_warning(self):
        write_catalog(".", [chan("A.ar", "AR", src(status="restricted")), chan("B.mx", "MX", src())])
        self.assertEqual(self.run_guard("--strict"), 0)
        rep = json.loads(Path("public/data/report.json").read_text())
        self.assertTrue(any("Argentina" in w for w in rep["warnings"]))

    def test_m3u_mismatch_is_detected(self):
        write_catalog(".", [chan("A.ar", "AR", src()), chan("B.ar", "AR", src())])
        Path("public/lists").mkdir(parents=True)
        Path("public/lists/live-ar.m3u").write_text("#EXTM3U\n")  # vacía por "error del proceso"
        Path("public/lists/live-latam.m3u").write_text("#EXTM3U\n")
        self.assertEqual(guard.main(["lists"]), 1)

    def test_m3u_roundtrip_matches(self):
        items = [chan("A.ar", "AR", src()), chan("B.ar", "AR", src(status="dead")), chan("C.mx", "MX", src())]
        write_catalog(".", items)
        Path("public/lists").mkdir(parents=True)
        for fname, subset in (("live-ar.m3u", [i for i in items if i["country"] == "AR"]), ("live-latam.m3u", items)):
            Path("public/lists", fname).write_text(export_m3u.render(subset)[0])
        self.assertEqual(guard.main(["lists"]), 0)


class StremioStructureTests(unittest.TestCase):
    """Comprueba la estructura contra los campos requeridos del manifest oficial del SDK de Stremio."""

    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)
        movies = [{"id": "m1", "title": "Peli OK", "year": 2010, "genres": ["animación"], "overview": "x",
                   "poster": "https://p/x.jpg", "license": "CC BY 3.0",
                   "sources": [{"url": "https://a/x.mp4", "type": "mp4", "status": "ok"}]},
                  {"id": "m2", "title": "Peli caída", "sources": [{"url": "https://a/y.mp4", "type": "mp4", "status": "dead"}]},
                  {"id": "m3", "title": "Peli http", "sources": [{"url": "http://a/z.mp4", "type": "mp4", "status": "ok"}]},
                  {"id": "m4", "title": "Externa", "sources": [{"url": "https://s/", "type": "external", "status": "external"}]}]
        live = [chan("A.ar", "AR", src("https://c/a.m3u8")),
                chan("B.ar", "AR", src("https://c/b.m3u8", referrer="https://r/")),
                chan("C.ar", "AR", src("https://c/c.m3u8", status="unchecked"))]
        write_catalog(".", live, movies)
        build_stremio.main()
        self.out = Path("public/stremio")

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def test_manifest_has_all_required_fields(self):
        m = json.loads((self.out / "manifest.json").read_text())
        for field in ("id", "name", "description", "version", "types", "catalogs", "resources"):
            self.assertIn(field, m)
        self.assertRegex(m["id"], r"^[a-z0-9]+(\.[a-z0-9]+)+$")          # id con puntos
        self.assertRegex(m["version"], r"^\d+\.\d+\.\d+$")                 # semver
        self.assertTrue(set(m["types"]) <= {"movie", "series", "channel", "tv"})
        for cat in m["catalogs"]:
            self.assertIn(cat["type"], m["types"])
            self.assertTrue(cat["id"] and cat["name"])
        self.assertEqual(len({c["id"] for c in m["catalogs"]}), len(m["catalogs"]))  # ids únicos

    def test_only_verified_https_without_headers_is_published(self):
        movies = json.loads((self.out / "catalog/movie/iptvp_movies.json").read_text())["metas"]
        self.assertEqual([x["name"] for x in movies], ["Peli OK"])
        tv = json.loads((self.out / "catalog/tv/iptvp_live.json").read_text())["metas"]
        self.assertEqual([x["name"] for x in tv], ["A.ar"])  # B exige cabeceras, C no está verificado

    def test_every_catalog_entry_has_meta_and_stream_files(self):
        for typ, cat in (("movie", "iptvp_movies"), ("tv", "iptvp_live")):
            for meta in json.loads((self.out / f"catalog/{typ}/{cat}.json").read_text())["metas"]:
                self.assertTrue(meta["id"].startswith("iptvp_"))
                self.assertEqual(json.loads((self.out / f"meta/{typ}/{meta['id']}.json").read_text())["meta"]["id"], meta["id"])
                streams = json.loads((self.out / f"stream/{typ}/{meta['id']}.json").read_text())["streams"]
                self.assertTrue(streams and all(s["url"].startswith("https://") for s in streams))


class HygieneTests(unittest.TestCase):
    TEXT_EXT = {".py", ".js", ".json", ".md", ".yml", ".html", ".css", ".txt", ".webmanifest"}
    SECRET_PATTERNS = [r"ghp_[A-Za-z0-9]{20,}", r"github_pat_[A-Za-z0-9_]{20,}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
                       r"api_key=[0-9a-f]{32}", r"AKIA[0-9A-Z]{16}"]

    def files(self):
        for p in ROOT.rglob("*"):
            if p.is_file() and p.suffix in self.TEXT_EXT and "__pycache__" not in p.parts and ".git" not in p.parts:
                yield p

    def test_no_secrets_in_repository_files(self):
        for p in self.files():
            if p.name == "test_hardening.py":
                continue
            text = p.read_text(encoding="utf-8", errors="ignore")
            for pat in self.SECRET_PATTERNS:
                self.assertIsNone(re.search(pat, text), f"posible secreto en {p.relative_to(ROOT)}")

    def test_only_public_folder_is_deployed(self):
        wf = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
        self.assertRegex(wf, r"upload-pages-artifact@v\d+\s+with:\s+path: public\b")

    def test_workflow_has_guards_and_isolated_movie_step(self):
        wf = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
        for needle in ("guard.py catalogs --strict", "guard.py lists", "continue-on-error: true", "timeout-minutes"):
            self.assertIn(needle, wf)

    def test_tmdb_key_is_never_written_to_repo_files(self):
        js = (ROOT / "public/app.js").read_text(encoding="utf-8")
        self.assertIn("localStorage.setItem(\"tmdb_key\"", js)           # solo en el teléfono
        for p in (ROOT / "public").rglob("*.json"):
            self.assertNotIn("tmdb_key", p.read_text(encoding="utf-8"))

    def test_hls_js_version_is_one_listed_on_cdnjs(self):
        js = (ROOT / "public/app.js").read_text(encoding="utf-8")
        self.assertIn("hls.js/1.5.20/hls.min.js", js)


if __name__ == "__main__":
    unittest.main()
        
