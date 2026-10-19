"""Verificador de fuentes: clasifica cada URL como ok / restricted / dead / bad_format / ...

LIMITACIÓN IMPORTANTE: la verificación corre en un servidor (p. ej. GitHub Actions) y no
en tu celular. "ok" significa "respondió bien desde ahí". Un canal geobloqueado para
Argentina puede dar "ok" en el verificador (si el runner está en EE. UU.) y fallar en tu
teléfono, y al revés. Por eso 401/403/451 se informan como "restricted" (posible geobloqueo
o cabeceras requeridas) y nunca como "caído" ni como "geobloqueado confirmado".

Uso:
    python tools/verify.py public/data/live.json public/data/movies.json public/data/series.json
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).parent))
from common import (STATUS_BAD_FORMAT, STATUS_DEAD, STATUS_EXTERNAL, STATUS_FIXTURE,  # noqa: E402
                    STATUS_OK, STATUS_RESTRICTED, http_get, load_json, now_iso, save_json)

# Estados que el verificador no toca: no son enlaces de video verificables.
SKIP_STATUSES = (STATUS_FIXTURE, STATUS_EXTERNAL)

VIDEO_EXT = (".mp4", ".webm", ".ogv", ".ogg", ".m4v", ".mkv")
HLS_TYPES = ("mpegurl", "x-mpegurl", "vnd.apple.mpegurl")


def _result(status: str, reason: str, http: int | None = None) -> dict:
    return {"status": status, "reason": reason, "http": http, "checked": now_iso()}


def classify_http_status(code: int | None, error: str | None) -> tuple[str, str]:
    if code is None:
        return STATUS_DEAD, f"Sin respuesta ({error})"
    if code in (401, 403, 451):
        return STATUS_RESTRICTED, (
            f"HTTP {code}: posible geobloqueo o exige cabeceras/credenciales. "
            "Puede funcionar desde tu país; probalo en el celular.")
    if code in (404, 410):
        return STATUS_DEAD, f"HTTP {code}: el enlace ya no existe"
    if code >= 500:
        return STATUS_DEAD, f"HTTP {code}: error del servidor (puede ser temporal)"
    return STATUS_DEAD, f"HTTP {code} inesperado"


def check_source(source: dict, timeout: float = 15.0) -> dict:
    """Devuelve un dict con status/reason/http/checked para una fuente."""
    url = source.get("url", "")
    if source.get("status") in SKIP_STATUSES or source.get("type") == "external":
        return {}  # datos de prueba y sitios externos nunca se "verifican"
    if not url.startswith(("http://", "https://")):
        return _result(STATUS_BAD_FORMAT, "URL no HTTP(S)")

    headers = {}
    if source.get("referrer"):
        headers["Referer"] = source["referrer"]
    if source.get("user_agent"):
        headers["User-Agent"] = source["user_agent"]

    kind = source.get("type", "hls")
    is_video_file = kind in ("mp4", "webm", "ogv") or urlparse(url).path.lower().endswith(VIDEO_EXT)

    if is_video_file:
        code, hdrs, body, error = http_get(url, headers, timeout, max_bytes=2048, byte_range="0-1023")
        if code in (200, 206):
            ctype = next((v for k, v in hdrs.items() if k.lower() == "content-type"), "").lower()
            if ctype.startswith(("video/", "application/ogg", "application/octet-stream", "binary/")):
                result = _result(STATUS_OK, "Archivo de video accesible", code)
            else:
                result = _result(STATUS_BAD_FORMAT, f"Responde, pero content-type={ctype or 'vacío'}", code)
        else:
            st, why = classify_http_status(code, error)
            result = _result(st, why, code)
    else:
        code, hdrs, body, error = http_get(url, headers, timeout, max_bytes=65_536)
        if code == 200:
            text = body.decode("utf-8", "replace")
            if text.lstrip().startswith("#EXTM3U"):
                result = _check_playlist(url, text, headers, timeout)
            else:
                result = _result(STATUS_BAD_FORMAT, "Responde 200 pero no es una lista HLS (#EXTM3U)", code)
        else:
            st, why = classify_http_status(code, error)
            result = _result(st, why, code)

    # Banderas que NO dependen de la respuesta, pero afectan la reproducción en navegador.
    flags = []
    if url.startswith("http://"):
        flags.append("http_sin_cifrar")
    if source.get("referrer") or source.get("user_agent"):
        flags.append("exige_cabeceras")
    result["flags"] = flags
    if result["status"] == STATUS_OK:
        # Sigue siendo "ok" para el reproductor externo; el front-end usa las banderas
        # para ocultar el reproductor del navegador y ofrecer VLC.
        pass
    return result


def safe_check(source: dict, timeout: float = 10.0) -> dict:
    """check_source con red de seguridad: un enlace raro NUNCA puede detener el catálogo entero."""
    try:
        return check_source(source, timeout)
    except Exception as exc:  # noqa: BLE001 - justamente: cualquier error queda aislado en esta fuente
        return {"status": STATUS_DEAD, "reason": f"Error interno al verificar ({type(exc).__name__}: {exc})",
                "http": None, "checked": now_iso(), "flags": []}


def _check_playlist(url: str, text: str, headers: dict, timeout: float) -> dict:
    """Si es lista maestra, prueba la primera variante; si es lista media, revisa que haya segmentos."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if any(ln.startswith("#EXT-X-STREAM-INF") for ln in lines):
        variants = [ln for ln in lines if not ln.startswith("#")]
        if not variants:
            return _result(STATUS_BAD_FORMAT, "Lista maestra sin variantes", 200)
        code, _, body, error = http_get(urljoin(url, variants[0]), headers, timeout, max_bytes=32_768)
        if code != 200:
            st, why = classify_http_status(code, error)
            return _result(st, f"Variante principal: {why}", code)
        if not body.decode("utf-8", "replace").lstrip().startswith("#EXTM3U"):
            return _result(STATUS_BAD_FORMAT, "La variante no es una lista HLS válida", code)
        return _result(STATUS_OK, "Lista HLS maestra y variante accesibles", 200)
    if any(ln.startswith("#EXTINF") or ln.startswith("#EXT-X-TARGETDURATION") for ln in lines):
        return _result(STATUS_OK, "Lista HLS accesible", 200)
    return _result(STATUS_BAD_FORMAT, "Lista M3U sin segmentos de video", 200)


def iter_sources(catalog: dict):
    """Recorre todas las fuentes de un catálogo (live/movies/series)."""
    for item in catalog.get("items", []):
        for src in item.get("sources", []):
            yield item, src
        for season in item.get("seasons", []):
            for episode in season.get("episodes", []):
                for src in episode.get("sources", []):
                    yield episode, src


def verify_catalog(path: Path, state: dict, workers: int = 32, timeout: float = 10.0) -> dict:
    catalog = load_json(path)
    if not catalog:
        print(f"[verify] {path}: no existe o está vacío, se omite")
        return {}
    pairs = list(iter_sources(catalog))
    todo = [(item, src) for item, src in pairs
            if src.get("status") not in SKIP_STATUSES and src.get("type") != "external"]
    print(f"[verify] {path.name}: {len(pairs)} fuentes, {len(todo)} a verificar "
          f"({len(pairs) - len(todo)} omitidas: datos de prueba o sitios externos)")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda pair: safe_check(pair[1], timeout), todo))

    counts: dict[str, int] = {}
    for (item, src), res in zip(todo, results):
        key = src.get("url") or ""
        hist = state.setdefault(key, {"fails": 0, "last_ok": None})
        src.update(res)
        if res["status"] == STATUS_OK:
            hist["fails"] = 0
            hist["last_ok"] = res["checked"]
        else:
            hist["fails"] += 1
        src["fails"] = hist["fails"]
        src["last_ok"] = hist["last_ok"]
        counts[res["status"]] = counts.get(res["status"], 0) + 1
    # Solo se sella "verified_at" si de verdad se comprobó algo (los datos de prueba no cuentan).
    if todo:
        catalog["verified_at"] = now_iso()
    else:
        catalog.pop("verified_at", None)
    save_json(path, catalog)
    print(f"[verify] {path.name}: {counts}")
    return counts


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    state_path = Path("data/state.json")
    state = load_json(state_path, {}) or {}
    for arg in argv:
        verify_catalog(Path(arg), state)
    save_json(state_path, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
    
