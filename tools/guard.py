"""Guardia de calidad: evita publicar un catálogo roto o vacío "por error del proceso".

Uso en el workflow (después de verificar y después de exportar las M3U):
    python tools/guard.py catalogs --strict      # falla si el resultado es sospechoso
    python tools/guard.py lists                  # falla si las M3U (live y VOD) no coinciden con lo "ok" del catálogo

Qué hace falta para que FALLE (y por lo tanto NO se publique; el sitio anterior sigue en línea):
  * live.json vacío o sin canales de Argentina  -> la API cambió o no respondió.
  * más del 90 % de las fuentes sin respuesta de red -> falló la red del servidor, no los canales.
  * ninguna fuente "ok" habiendo 20 o más verificadas.
  * (con --strict) datos de prueba mezclados en una corrida real.
Qué solo genera ADVERTENCIA (se publica, pero queda escrito en report.json y se ve en la app):
  * 0 canales "ok" en Argentina; 0 películas; consultas sin resultados.

Siempre escribe public/data/report.json con el resumen.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import STATUS_EXTERNAL, STATUS_FIXTURE, STATUS_OK, load_json, now_iso, save_json  # noqa: E402
from export_m3u import vod_entries  # noqa: E402
from verify import iter_sources  # noqa: E402

DATA = Path("public/data")
REPORT = DATA / "report.json"


def summarize(catalog: dict) -> dict:
    by_status: dict[str, int] = {}
    network_errors = 0
    for _, src in iter_sources(catalog):
        st = src.get("status", "unchecked")
        by_status[st] = by_status.get(st, 0) + 1
        if st == "dead" and str(src.get("reason", "")).startswith("Sin respuesta"):
            network_errors += 1
    return {
        "items": len(catalog.get("items", [])),
        "sources": sum(by_status.values()),
        "by_status": by_status,
        "network_errors": network_errors,
        "origin": catalog.get("origin"),
        "verified_at": catalog.get("verified_at"),
    }


def check_catalogs(strict: bool) -> tuple[dict, list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    live = load_json(DATA / "live.json", {}) or {}
    movies = load_json(DATA / "movies.json", {}) or {}
    series = load_json(DATA / "series.json", {}) or {}
    report = {"generated": now_iso(), "catalogs": {
        "live": summarize(live), "movies": summarize(movies), "series": summarize(series)}}

    items = live.get("items", [])
    ar_items = [c for c in items if c.get("country") == "AR"]
    if not items:
        failures.append("live.json no tiene canales: la API de iptv-org no respondió o cambió de formato.")
    elif not ar_items:
        failures.append("live.json no tiene canales de Argentina (¿cambió el formato de la API?).")

    for name, cat in (("live", live), ("movies", movies), ("series", series)):
        s = report["catalogs"][name]
        real = [st for st in s["by_status"] if st not in (STATUS_FIXTURE, STATUS_EXTERNAL)]
        checked = sum(s["by_status"][st] for st in real if st != "unchecked")
        if strict and (str(cat.get("origin", "")).startswith("DATOS DE PRUEBA") or s["by_status"].get(STATUS_FIXTURE)):
            failures.append(f"{name}: contiene datos de prueba en una corrida real.")
        if checked >= 10 and s["network_errors"] / max(checked, 1) > 0.9:
            failures.append(f"{name}: {s['network_errors']} de {checked} fuentes sin respuesta de red. "
                            "Es casi seguro un fallo de red del servidor, no de los canales.")
        if name == "live" and checked >= 20 and s["by_status"].get(STATUS_OK, 0) == 0:
            failures.append("live: ninguna de las fuentes verificadas dio 'ok'. Revisá el verificador.")

    ar_ok = sum(1 for c in ar_items for s in c["sources"] if s.get("status") == STATUS_OK)
    all_ok = sum(1 for c in items for s in c["sources"] if s.get("status") == STATUS_OK)
    report["live_ok"] = {"argentina": ar_ok, "latam": all_ok}
    if items and ar_ok == 0:
        warnings.append("Ningún canal de Argentina figura como 'funciona' en esta corrida.")
    if not movies.get("items"):
        warnings.append("movies.json está vacío: las consultas a Internet Archive/Commons no devolvieron nada.")
    if not [m for m in movies.get("items", []) if any(s.get("status") == STATUS_OK for s in m.get("sources", []))]:
        warnings.append("Ninguna película figura como 'funciona' en esta corrida.")
    report["warnings"] = warnings
    report["failures"] = failures
    return report, failures, warnings


def count_m3u(path: Path) -> int:
    if not path.exists():
        return -1
    return sum(1 for ln in path.read_text(encoding="utf-8").splitlines() if ln.startswith("#EXTINF"))


def check_lists() -> list[str]:
    live = load_json(DATA / "live.json", {}) or {}
    items = live.get("items", [])

    def expected(sub):
        return sum(1 for c in sub if any(s.get("status") == STATUS_OK for s in c["sources"]))

    problems = []
    for fname, exp in (("live-ar.m3u", expected([c for c in items if c.get("country") == "AR"])),
                       ("live-latam.m3u", expected(items))):
        got = count_m3u(Path("public/lists") / fname)
        print(f"[guard] {fname}: {got} canales en el archivo, {exp} esperados")
        if got != exp:
            problems.append(f"{fname} tiene {got} canales pero el catálogo dice {exp} (error del proceso de exportación).")
    # Listas VOD: lo esperado se calcula con la MISMA función que usa el exportador.
    movies = (load_json(DATA / "movies.json", {}) or {}).get("items", [])
    series = (load_json(DATA / "series.json", {}) or {}).get("items", [])
    entries = vod_entries(movies, series)
    n_movies = sum(1 for e in entries if e["kind"] == "movie")
    n_series = len(entries) - n_movies
    for fname, exp in (("movies.m3u", n_movies), ("series.m3u", n_series), ("vod.m3u", len(entries))):
        got = count_m3u(Path("public/lists") / fname)
        if got == -1 and exp == 0:
            got = 0  # sin contenido que exportar, un archivo ausente no es un error
        print(f"[guard] {fname}: {got} entradas en el archivo, {exp} esperadas")
        if got != exp:
            problems.append(f"{fname} tiene {got} entradas pero el catálogo dice {exp} (error del proceso de exportación).")
    report = load_json(REPORT, {}) or {}
    report["lists"] = {"live_ar_m3u": count_m3u(Path("public/lists/live-ar.m3u")),
                       "live_latam_m3u": count_m3u(Path("public/lists/live-latam.m3u")),
                       "movies_m3u": count_m3u(Path("public/lists/movies.m3u")),
                       "series_m3u": count_m3u(Path("public/lists/series.m3u")),
                       "vod_m3u": count_m3u(Path("public/lists/vod.m3u"))}
    save_json(REPORT, report, indent=2)
    return problems


def main(argv: list[str]) -> int:
    mode = argv[0] if argv else "catalogs"
    if mode == "lists":
        problems = check_lists()
        for p in problems:
            print(f"::error::{p}")
        return 1 if problems else 0
    report, failures, warnings = check_catalogs(strict="--strict" in argv)
    save_json(REPORT, report, indent=2)
    print(f"[guard] live: {report['catalogs']['live']['by_status']}  ok AR={report['live_ok']['argentina']} "
          f"LATAM={report['live_ok']['latam']}")
    print(f"[guard] movies: {report['catalogs']['movies']['by_status']}")
    for w in warnings:
        print(f"::warning::{w}")
    for f in failures:
        print(f"::error::{f}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(sys.argv[1:])
    
