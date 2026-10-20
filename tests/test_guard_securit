"""Pruebas de la guardia de seguridad y de la tolerancia de build_live a caídas de la API (sin internet).

Ejecutar:  python -m unittest discover -s tests -v
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_live  # noqa: E402
import guard  # noqa: E402


class SecurityGuardTests(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)
        Path("public/data").mkdir(parents=True)
        Path("data/manual").mkdir(parents=True)
        Path("config.json").write_text(json.dumps({"ia_queries": [], "m3u_lists": []}))

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def run_guard(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = guard.main(["security", *args])
        return rc, buf.getvalue()

    def test_clean_project_passes(self):
        Path("public/data/movies.json").write_text(json.dumps({"items": [{"sources": [{"url": "https://s/a.mp4"}]}]}))
        self.assertEqual(self.run_guard()[0], 0)

    def test_password_in_public_file_is_blocked_and_value_is_never_printed(self):
        Path("public/data/movies.json").write_text(
            json.dumps({"items": [{"sources": [{"url": "http://h:8080/get.php?username=ZZUSER&password=ZZSECRET&type=m3u"}]}]}))
        rc, out = self.run_guard("--public")
        self.assertEqual(rc, 1)
        self.assertNotIn("ZZSECRET", out)
        self.assertNotIn("ZZUSER", out)
        self.assertIn("movies.json", out)

    def test_exported_m3u_is_scanned(self):
        Path("public/lists").mkdir()
        Path("public/lists/vod.m3u").write_text("#EXTM3U\n#EXTINF:-1,Peli\nhttp://h/x?password=abc\n")
        self.assertEqual(self.run_guard("--public")[0], 1)

    def test_user_colon_password_at_host_is_blocked(self):
        Path("public/data/live.json").write_text('{"u": "http://usuario:clave123@servidor.example/x.m3u8"}')
        self.assertEqual(self.run_guard("--public")[0], 1)

    def test_json_credential_fields_in_config_are_blocked(self):
        Path("config.json").write_text(json.dumps({"m3u_lists": [{"url": "https://l/x.m3u", "password": "abc", "rights": "x"}]}))
        rc, out = self.run_guard("--source")
        self.assertEqual(rc, 1)
        self.assertIn("config.json", out)
        self.assertNotIn("abc", out.replace("abc.", ""))

    def test_manual_entries_are_scanned_in_source_mode(self):
        Path("data/manual/movies.json").write_text('[{"sources":[{"url":"http://h/get.php?username=a&password=b"}]}]')
        self.assertEqual(self.run_guard("--source")[0], 1)
        self.assertEqual(self.run_guard("--public")[0], 0)  # --public solo mira public/

    def test_normal_app_files_do_not_trigger_false_positives(self):
        # el campo de la clave de TMDB y la llamada a su API no son credenciales guardadas
        Path("public/index.html").write_text('<input id="tmdb-key" type="password" autocomplete="off">')
        Path("public/app.js").write_text("const url = `https://api.themoviedb.org/3/search/movie?api_key=${key}`;")
        self.assertEqual(self.run_guard("--public")[0], 0)

    def test_real_project_files_are_clean(self):
        os.chdir(ROOT)
        self.assertEqual(self.run_guard()[0], 0)


class BuildLiveToleranceTests(unittest.TestCase):
    def test_api_failure_writes_empty_catalog_with_api_error_and_exits_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "live.json"
            argv = ["build_live.py", "--out", str(out), "--allowlist", str(Path(tmp) / "none.txt")]
            with mock.patch.object(sys, "argv", argv), \
                    mock.patch.object(build_live, "get_json", side_effect=RuntimeError("No se pudo obtener channels.json: timeout")):
                self.assertEqual(build_live.main(), 0)
            data = json.loads(out.read_text())
        self.assertEqual(data["items"], [])
        self.assertIn("timeout", data["api_error"])

    def test_guard_turns_that_catalog_into_a_skipped_publication(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                Path("public/data").mkdir(parents=True)
                Path("public/data/live.json").write_text(json.dumps({"api_error": "timeout", "items": []}))
                gh = Path(tmp) / "out.txt"
                with mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(gh)}), contextlib.redirect_stdout(io.StringIO()):
                    rc = guard.main(["catalogs", "--strict"])
                self.assertEqual(rc, 0)
                self.assertIn("publish=false", gh.read_text())
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()

