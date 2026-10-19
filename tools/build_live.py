"""Construye public/data/live.json a partir de la API pública de iptv-org.

Endpoints (documentados en el README de https://github.com/iptv-org/api):
    channels.json, streams.json, blocklist.json (y categories/countries/languages).

Reglas de filtrado (todas por seguridad/licitud, no por comodidad):
  * Solo países configurados (por defecto Argentina primero, luego Latinoamérica).
  * Se excluyen canales marcados is_nsfw, canales cerrados y los de la blocklist de iptv-org
    (que incluye pedidos DMCA).
  * Si data/manual/live_allowlist.txt tiene IDs de canal, SOLO se incluyen esos (modo conservador:
    vos elegís qué canales considerás oficiales/autorizados).
  * Cada fuente nace como "unchecked": nada se marca disponible hasta que verify.py lo compruebe.

Uso:
    python tools/build_live.py --out public/data/live.json
    python tools/build_live.py --fixtures data/fixtures/api --out public/data/live.json   # offline / pruebas
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (COUNTRY_NAMES, LATAM_COUNTRIES, STATUS_FIXTURE, STATUS_UNCHECKED,  # noqa: E402
                    get_json, load_json, now_iso, save_json)

API_BASE = "https://iptv-org.github.io/api"
ADULT_CATEGORIES = {"xxx"}


def load_api(fixtures_dir: Path | None, api_base: str):
    names = ("channels", "streams", "blocklist")
    data = {}
    for name in names:
        if fixtures_dir:
            data[name] = load_json(fixtures_dir / f"{name}.json", [])
        else:
            data[name] = get_json(f"{api_base}/{name}.json")
    return data["channels"], data["streams"], data["blocklist"]


def read_allowlist(path: Path | None) -> set[str]:
    """Un ID de canal por línea (ej. 'Canal7.ar'); '#' inicia un comentario. Vacío = sin lista."""
    if not path or not path.exists():
        return set()
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            ids.add(line)
    return ids


def build(channels: list, streams: list, blocklist: list, countries: list[str], fixture: bool,
          allowlist: set[str] | None = None) -> dict:
    blocked = {b.get("channel") for b in blocklist if b.get("channel")}
    allowlist = allowlist or set()
    streams_by_channel: dict[str, list] = {}
    for stream in streams:
        if not isinstance(stream, dict):
            continue
        cid = stream.get("channel")
        if cid:
            streams_by_channel.setdefault(cid, []).append(stream)

    order = {code: i for i, code in enumerate(countries)}
    items = []
    skipped = {"nsfw": 0, "cerrado": 0, "blocklist": 0, "sin_fuentes": 0, "fuera_de_allowlist": 0}
    for ch in channels:
        if not isinstance(ch, dict) or not ch.get("id"):
            continue  # registro malformado: se ignora sin frenar el resto
        country = ch.get("country")
        if country not in order:
            continue
        if ch.get("is_nsfw") or ADULT_CATEGORIES & set(ch.get("categories") or []):
            skipped["nsfw"] += 1
            continue
        if ch.get("closed"):
            skipped["cerrado"] += 1
            continue
        if ch["id"] in blocked:
            skipped["blocklist"] += 1
            continue
        if allowlist and ch["id"] not in allowlist:
            skipped["fuera_de_allowlist"] += 1
            continue
        srcs = streams_by_channel.get(ch["id"], [])
        if not srcs:
            skipped["sin_fuentes"] += 1
            continue
        items.append({
            "id": ch["id"],
            "kind": "live",
            "name": ch.get("name", ch["id"]),
            "country": country,
            "country_name": COUNTRY_NAMES.get(country, country),
            "categories": ch.get("categories") or ["general"],
            "languages": ch.get("languages") or [],
            "logo": ch.get("logo"),
            "website": ch.get("website"),
            "sources": [{
                "url": s["url"],
                "type": "hls",
                "quality": s.get("quality"),
                "referrer": s.get("referrer"),
                "user_agent": s.get("user_agent"),
                "status": STATUS_FIXTURE if fixture else STATUS_UNCHECKED,
                "reason": "Dato de prueba: no es un enlace real" if fixture else "Todavía no verificado",
            } for s in srcs if s.get("url")],
        })
    items.sort(key=lambda it: (order[it["country"]], it["name"].lower()))
    return {
        "generated": now_iso(),
        "origin": "iptv-org/api (channels.json + streams.json + blocklist.json)" if not fixture
                  else "DATOS DE PRUEBA locales (data/fixtures/api)",
        "skipped": skipped,
        "items": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="public/data/live.json")
    parser.add_argument("--countries", default=",".join(LATAM_COUNTRIES))
    parser.add_argument("--fixtures", help="carpeta con channels.json/streams.json/blocklist.json de prueba")
    parser.add_argument("--api-base", default=API_BASE)
    parser.add_argument("--allowlist", default="data/manual/live_allowlist.txt",
                        help="si el archivo tiene IDs, SOLO se incluyen esos canales (modo conservador)")
    args = parser.parse_args()

    countries = [c.strip().upper() for c in args.countries.split(",") if c.strip()]
    fixtures_dir = Path(args.fixtures) if args.fixtures else None
    channels, streams, blocklist = load_api(fixtures_dir, args.api_base)
    allow = read_allowlist(Path(args.allowlist))
    if allow:
        print(f"[live] modo allowlist: solo {len(allow)} canales autorizados por vos")
    catalog = build(channels, streams, blocklist, countries, fixture=bool(fixtures_dir), allowlist=allow)
    save_json(Path(args.out), catalog)
    total_src = sum(len(i["sources"]) for i in catalog["items"])
    print(f"[live] {len(catalog['items'])} canales / {total_src} fuentes -> {args.out}  (omitidos: {catalog['skipped']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
