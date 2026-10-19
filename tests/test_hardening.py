"""Pruebas de robustez: aislamiento de errores, guardias, estructura del add-on de Stremio e higiene del repo.

Ejecutar:  python -m unittest discover -s tests -v
"""
from __future__ import annotations

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

    def test_broken_manual_json_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "m.json"
            p.write_text("{ esto no es json")
            self.assertEqual(build_movies.manual_entries(p, "movie"), [])

    def test_manual_entry_that_is_not_an_object_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "m.json"
            p.write_text(json.dumps(["texto suelto", {"title": "Ok", "rights": "CC BY", "sources": [{"url": "https://x"}]}]))
            self.assertEqual([e["title"] for e in build_movies.manual_entries(p, "movie")], ["Ok"])


class RealManualDataTests(unittest.TestCase):
    def setUp(self):
        self.movies = build_movies.manual_entries(ROOT / "data/manual/movies.json", "movie")
        self.series = build_movies.manual_entries(ROOT / "data/manual/series.json", "series")

    def test_entries_are_well_formed(self):
        for e in self.movies + self.series:
            self.assertTrue(e.get("title"))
            self.assertTrue(e.get("rights"), e["title"])
            self.assertTrue(e.get("sources") or e.get("seasons"), e["title"])
        
