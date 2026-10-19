"""Utilidades compartidas. Solo biblioteca estándar de Python 3.10+ (sin dependencias)."""
from __future__ import annotations

import json
import re
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USER_AGENT = "iptv-personal/0.1 (+uso personal; verificador de enlaces)"

# Estados posibles de una fuente de reproducción (source.status).
# El front-end muestra una etiqueta distinta para cada uno.
STATUS_OK = "ok"                    # respondió con contenido reproducible desde el verificador
STATUS_RESTRICTED = "restricted"    # 401/403/451: puede ser geobloqueo o requerir cabeceras
STATUS_DEAD = "dead"                # 404/410/5xx/timeout/DNS
STATUS_BAD_FORMAT = "bad_format"    # responde, pero no es HLS/MP4/WebM
STATUS_NEEDS_HEADERS = "needs_headers"  # la fuente exige Referer/User-Agent propios (el navegador no puede enviarlos)
STATUS_INSECURE = "insecure"        # http:// (el navegador lo bloquea desde una página https)
STATUS_UNCHECKED = "unchecked"
STATUS_FIXTURE = "fixture"          # dato de prueba: NO es un enlace real
STATUS_EXTERNAL = "external"        # enlace a un sitio oficial: se abre fuera de la app, no se verifica video

LATAM_COUNTRIES = [
    "AR", "UY", "CL", "PY", "BO", "PE", "EC", "CO", "VE", "MX",
    "CR", "PA", "GT", "HN", "SV", "NI", "DO", "CU", "PR",
]

COUNTRY_NAMES = {
    "AR": "Argentina", "UY": "Uruguay", "CL": "Chile", "PY": "Paraguay", "BO": "Bolivia",
    "PE": "Perú", "EC": "Ecuador", "CO": "Colombia", "VE": "Venezuela", "MX": "México",
    "CR": "Costa Rica", "PA": "Panamá", "GT": "Guatemala", "HN": "Honduras",
    "SV": "El Salvador", "NI": "Nicaragua", "DO": "Rep. Dominicana", "CU": "Cuba",
    "PR": "Puerto Rico", "ES": "España", "US": "Estados Unidos",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def http_get(url: str, headers: dict | None = None, timeout: float = 15.0,
             max_bytes: int = 262_144, byte_range: str | None = None):
    """GET con límite de bytes. Devuelve (status, headers, body, error).

    Nunca lanza excepciones: los errores de red vuelven como texto en `error`.
    """
    req_headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        req_headers.update({k: v for k, v in headers.items() if v})
    if byte_range:
        req_headers["Range"] = f"bytes={byte_range}"
    req = urllib.request.Request(url, headers=req_headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(max_bytes)
            return resp.status, dict(resp.headers.items()), body, None
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(2048)
        except Exception:  # noqa: BLE001
            body = b""
        return exc.code, dict(exc.headers.items()) if exc.headers else {}, body, None
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        return None, {}, b"", f"{type(exc).__name__}: {reason}"


def get_json(url: str, retries: int = 2, timeout: float = 60.0):
    """Descarga y decodifica JSON; reintenta ante errores transitorios."""
    last_error = "desconocido"
    for attempt in range(retries + 1):
        status, _, body, error = http_get(url, timeout=timeout, max_bytes=80_000_000)
        if status == 200:
            try:
                return json.loads(body.decode("utf-8"))
            except ValueError as exc:
                last_error = f"JSON inválido: {exc}"
        else:
            last_error = error or f"HTTP {status}"
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"No se pudo obtener {url}: {last_error}")


def load_json(path: Path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data, indent: int | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=indent, separators=(",", ":") if indent is None else None),
                    encoding="utf-8")


_ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')


def parse_m3u(text: str) -> list[dict]:
    """Parser mínimo de M3U/M3U8 de canales.

    Devuelve una lista de dicts: name, url, attrs (tvg-id, tvg-logo, group-title...),
    referrer y user_agent (si la lista usa #EXTVLCOPT).
    """
    entries: list[dict] = []
    current: dict | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            head, _, name = line.partition(",")
            current = {"name": name.strip(), "attrs": dict(_ATTR_RE.findall(head)),
                       "referrer": None, "user_agent": None}
        elif line.startswith("#EXTVLCOPT:") and current is not None:
            key, _, value = line[len("#EXTVLCOPT:"):].partition("=")
            if key == "http-referrer":
                current["referrer"] = value
            elif key == "http-user-agent":
                current["user_agent"] = value
        elif line.startswith("#"):
            continue
        elif current is not None:
            current["url"] = line
            entries.append(current)
            current = None
    return entries


def slugify(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return text or "x"
