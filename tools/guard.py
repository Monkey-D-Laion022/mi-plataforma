"""Guardia de calidad y seguridad: evita publicar un catálogo roto, vacío o con claves expuestas.

Modos (en el workflow):
    python tools/guard.py security --source       # ANTES de construir: busca claves en config.json y data/manual
    python tools/guard.py catalogs --strict       # después de verificar: ¿es seguro publicar este catálogo?
    python tools/guard.py lists                   # después de exportar: ¿las M3U coinciden con lo "ok" del catálogo?
    python tools/guard.py security --public       # ANTES de publicar: busca claves en public/

Tres tipos de resultado en el modo "catalogs":
  * FALLA (código 1, la corrida queda en rojo, no se publica): datos inconsistentes o peligrosos.
      - live.json vacío SIN error de red declarado, o sin canales de Argentina (la API cambió de formato).
      - ninguna fuente "ok" habiendo 20 o más verificadas por respuestas HTTP (no por red).
      - (--strict) datos de prueba mezclados en una corrida real.
  * OMITIR PUBLICACIÓN (código 0, la corrida queda en verde, NO se publica y queda en línea la versión anterior):
      - la API de iptv-org no respondió (api_error en live.json).
      - más del 90 % de las fuentes en vivo sin respuesta de red (corte de red del servidor, no de los canales).
    En estos casos escribe publish=false en $GITHUB_OUTPUT y en report.json.
  * ADVERTENCIA (se publica; queda en report.json y se ve en la app): 0 canales "ok" en Argentina, 0 películas, etc.

Modo "security": falla (código 1) si aparece "username=", "password=", "usuario:clave@" o claves JSON equivalentes.
Nunca imprime el valor encontrado, solo el archivo, la línea y el tipo de hallazgo.

Siempre escribe public/data/report.json con el resumen (salvo en el modo security).
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import STATUS_EXTERNAL, STATUS_FIXTURE, STATUS_OK, load_json, now_iso, save_json  # noqa: E402
from export_m3u import vod_entries  # noqa: E402
from verify import iter_sources  # noqa: E402

DATA = Path("public/data")
REPORT = DATA / "report.json"


# ---------------------------------------------------------------------------
# Mensajes: anotaciones de GitHub solo en una corrida real (no durante las pruebas)
# ---------------------------------------------------------------------------
def annotations_enabled() -> bool:
    """Las líneas '::error::' se convierten en anotaciones rojas en GitHub. Las pruebas automáticas
    simulan fallas a propósito, así que ahí se imprimen como texto común para no confundir."""
    return (os.environ.get("GITHUB_ACTIONS") == "true" and "unittest" not in sys.modules
            and not os.environ.get("GUARD_QUIET"))


def emit(level: str, message: str, file: str | None = None, line: int | None = None) -> None:
    if annotations_enabled():
        where = f" file={file},line={line}" if file else ""
        print(f"::{level}{where}::{message}")
    else:
        where = f"{file}:{line}: " if file else ""
        print(f"[{level.upper()}] {where}{message}")


def write_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{name}={value}\n")


# ---------------------------------------------------------------------------
# Catálogos
# ---------------------------------------------------------------------------
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


def check_catalogs(strict: bool) -> tuple[dict, list[str], list[str], list[str]]:
    failures: list[str] = []   # rojo: no se publica
    soft: list[str] = []       # verde, pero no se publica (corte externo temporal)
    warnings: list[str] = []   # se publica, con aviso
    live = load_json(DATA / "live.json", {}) or {}
    movies = load_json(DATA / "movies.json", {}) or {}
    series = load_json(DATA / "series.json", {}) or {}
    report = {"generated": now_iso(), "catalogs": {
        "live": summarize(live), "movies": summarize(movies), "series": summarize(series)}}

    items = live.get("items", [])
    ar_items = [c for c in items if c.get("country") == "AR"]
    api_error = live.get("api_error")
    if api_error:
        soft.append(f"La API de iptv-org no respondió desde el servidor de GitHub ({api_error}).")
    elif not items:
        failures.append("live.json no tiene canales: la API de iptv-org respondió, pero cambió de formato o vino vacía.")
    elif not ar_items:
        failures.append("live.json no tiene canales de Argentina (¿cambió el formato de la API?).")

    for name, cat in (("live", live), ("movies", movies), ("series", series)):
        s = report["catalogs"][name]
        real = [st for st in s["by_status"] if st not in (STATUS_FIXTURE, STATUS_EXTERNAL)]
        checked = sum(s["by_status"][st] for st in real if st != "unchecked")
        outage = checked >= 10 and s["network_errors"] / max(checked, 1) > 0.9
        if strict and (str(cat.get("origin", "")).startswith("DATOS DE PRUEBA") or s["by_status"].get(STATUS_FIXTURE)):
            failures.append(f"{name}: contiene datos de prueba en una corrida real.")
        if outage:
            msg = (f"{name}: {s['network_errors']} de {checked} fuentes sin respuesta de red. "
                   "Es casi seguro un corte de red del servidor, no de los canales.")
            (soft if name == "live" else warnings).append(msg)
        elif name == "live" and not api_error and checked >= 20 and s["by_status"].get(STATUS_OK, 0) == 0:
            failures.append("live: ninguna de las fuentes verificadas dio 'ok'. Revisá el verificador.")

    ar_ok = sum(1 for c in ar_items for s in c["sources"] if s.get("status") == STATUS_OK)
    all_ok = sum(1 for c in items for s in c["sources"] if s.get("status") == STATUS_OK)
    report["live_ok"] = {"argentina": ar_ok, "latam": all_ok}
    if items and ar_ok == 0 and not soft:
        warnings.append("Ningún canal de Argentina figura como 'funciona' en esta corrida.")
    if not movies.get("items"):
        warnings.append("movies.json está vacío: no hay películas cargadas o las consultas no devolvieron nada.")
    elif not [m for m in movies["items"] if any(s.get("status") == STATUS_OK for s in m.get("sources", []))]:
        warnings.append("Ninguna película figura como 'funciona' en esta corrida.")

    report["warnings"] = warnings + soft
    report["soft_failures"] = soft
    report["failures"] = failures
    report["publish"] = not failures and not soft
    return report, failures, warnings, soft


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
        if got == -1 and exp == 0:
            got = 0
        print(f"[guard] {fname}: {got} canales en el archivo, {exp} esperados")
        if got != exp:
            problems.append(f"{fname} tiene {got} canales pero el catálogo dice {exp} (error del proceso de exportación).")
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


# ---------------------------------------------------------------------------
# Seguridad: claves en archivos que se publican o que están en un repositorio público
# ---------------------------------------------------------------------------
TEXT_SUFFIXES = {".json", ".m3u", ".m3u8", ".js", ".html", ".css", ".txt", ".webmanifest", ".md", ".xml", ".yml", ".yaml"}
SECRET_PATTERNS = [
    (re.compile(r"(?i)(?<![A-Za-z0-9_])(username|password|passwd)=[^&\s\"'<>]+"), "usuario o clave dentro de un enlace"),
    (re.compile(r"(?i)https?://[^/\s:@\"']+:[^/\s@\"']+@"), "usuario:clave@ dentro de un enlace"),
    (re.compile(r"(?i)\"(username|password|passwd)\"\s*:\s*\"[^\"]+\""), "usuario o clave en un campo JSON"),
]
SOURCE_ROOTS = [Path("config.json"), Path("data/manual")]
PUBLIC_ROOTS = [Path("public")]


def iter_text_files(roots):
    for root in roots:
        if root.is_file():
            yield root
        elif root.is_dir():
            for p in sorted(root.rglob("*")):
                if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES:
                    yield p


def scan_for_secrets(roots) -> list[tuple[str, int, str]]:
    """Devuelve (archivo, línea, tipo). NUNCA devuelve el valor encontrado."""
    found = []
    for path in iter_text_files(roots):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for pattern, kind in SECRET_PATTERNS:
                if pattern.search(line):
                    found.append((str(path), number, kind))
                    break
    return found


def check_security(argv: list[str]) -> int:
    roots = []
    if "--source" in argv or "--public" not in argv:
        roots += SOURCE_ROOTS
    if "--public" in argv or "--source" not in argv:
        roots += PUBLIC_ROOTS
    found = scan_for_secrets(roots)
    for file, line, kind in found:
        emit("error", f"Se encontró {kind}. Valor oculto. Sacalo de este archivo y cambiá esa clave.", file, line)
    if found:
        print(f"[guard] SEGURIDAD: {len(found)} hallazgo(s). No se continúa. Recordá: el repositorio y GitHub Pages son "
              "públicos; si una clave ya se subió, cambiala con tu proveedor aunque la borres.")
        return 1
    print("[guard] SEGURIDAD: no se encontraron usuarios ni claves en", ", ".join(str(r) for r in roots))
    return 0


# ---------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    mode = argv[0] if argv else "catalogs"
    if mode == "security":
        return check_security(argv[1:])
    if mode == "lists":
        problems = check_lists()
        for p in problems:
            emit("error", p)
        return 1 if problems else 0

    report, failures, warnings, soft = check_catalogs(strict="--strict" in argv)
    save_json(REPORT, report, indent=2)
    print(f"[guard] live: {report['catalogs']['live']['by_status']}  ok AR={report['live_ok']['argentina']} "
          f"LATAM={report['live_ok']['latam']}")
    print(f"[guard] movies: {report['catalogs']['movies']['by_status']}")
    for w in warnings:
        emit("warning", w)
    for s in soft:
        emit("warning", f"NO SE PUBLICA ESTA VEZ (corte externo temporal; queda la versión anterior): {s}")
    for f in failures:
        emit("error", f)
    if not failures:
        write_output("publish", "true" if not soft else "false")
        if soft:
            print("[guard] Resultado: corrida en verde, pero sin publicar. Reintentá más tarde con Run workflow.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
                 
