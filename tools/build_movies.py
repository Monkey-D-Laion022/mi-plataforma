"""Construye public/data/movies.json y public/data/series.json.

Fuentes (todas con API pública sin clave):
  1. Internet Archive: https://archive.org/advancedsearch.php  +  https://archive.org/metadata/<id>
     (documentadas en https://archive.org/help/aboutsearch.htm)
  2. Wikimedia Commons: https://commons.wikimedia.org/w/api.php (MediaWiki Action API)
  3. Entradas manuales en data/manual/*.json (vos garantizás el derecho a reproducirlas)

REGLA DE DERECHOS: Internet Archive declara que NO garantiza el estado de copyright de sus
ítems. Por eso, por defecto solo se incluye un ítem de Internet Archive si tiene un campo
`licenseurl` (Creative Commons / dominio público). `allow_unlicensed` en config.json existe,
pero viene en false y no se recomienda activarlo.

Las consultas de config.json NO fueron probadas contra la API real en el entorno donde se
escribió este código (sin red). La primera ejecución en GitHub Actions es la prueba real.

Uso:
    python tools/build_movies.py
    python tools/build_movies.py --fixtures data/fixtures      # datos de prueba, sin red
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import quote, urlencode

sys.path.insert(0, str(Path(__file__).parent))
from common import (STATUS_EXTERNAL, STATUS_FIXTURE, STATUS_UNCHECKED, get_json, load_json,  # noqa: E402
                    now_iso, save_json, slugify)

IA_SEARCH = "https://archive.org/advancedsearch.php"
IA_META = "https://archive.org/metadata/"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

DEFAULT_CONFIG = {
    "ia_queries": [
        {
            "name": "Español con licencia abierta",
            "q": 'mediatype:movies AND language:(Spanish OR spa OR es) AND licenseurl:*creativecommons.org*',
            "rows": 100,
            "max_items": 150,
        },
        {
            "name": "Dominio público declarado (CC0 / Public Domain Mark)",
            "q": "mediatype:movies AND licenseurl:*creativecommons.org/publicdomain*",
            "rows": 100,
            "max_items": 150,
        },
    ],
    "commons_categories": [],
    "allow_unlicensed": False,
    "max_file_bytes": 1_500_000_000,
}

LICENSE_LABELS = [
    (re.compile(r"publicdomain/zero"), "CC0 (dominio público)"),
    (re.compile(r"publicdomain/mark"), "Dominio público (marca PDM)"),
    (re.compile(r"licenses/by-nc-nd/([\d.]+)"), "CC BY-NC-ND {0}"),
    (re.compile(r"licenses/by-nc-sa/([\d.]+)"), "CC BY-NC-SA {0}"),
    (re.compile(r"licenses/by-nc/([\d.]+)"), "CC BY-NC {0}"),
    (re.compile(r"licenses/by-nd/([\d.]+)"), "CC BY-ND {0}"),
    (re.compile(r"licenses/by-sa/([\d.]+)"), "CC BY-SA {0}"),
    (re.compile(r"licenses/by/([\d.]+)"), "CC BY {0}"),
]

# Preferencia de archivos en Internet Archive (formato -> prioridad; menor = mejor para celular)
IA_FORMAT_PRIORITY = {"h.264": 0, "MPEG4": 1, "h.264 HD": 2, "512Kb MPEG4": 3, "Ogg Video": 5, "WebM": 6}


def license_label(url: str | None) -> str | None:
    if not url:
        return None
    for pattern, label in LICENSE_LABELS:
        m = pattern.search(url)
        if m:
            return label.format(*m.groups())
    return "Licencia indicada (revisar enlace)"


def as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def norm_language(values) -> list[str]:
    out = []
    for v in as_list(values):
        v = str(v).strip().lower()
        if v in ("spanish", "spa", "es", "español", "castellano"):
            out.append("es")
        elif v in ("english", "eng", "en"):
            out.append("en")
        elif v:
            out.append(v[:12])
    return sorted(set(out))


def pick_ia_file(files: list[dict], max_bytes: int) -> dict | None:
    candidates = []
    for f in files:
        name = f.get("name", "")
        fmt = f.get("format", "")
        lower = name.lower()
        if not lower.endswith((".mp4", ".ogv", ".webm", ".m4v")):
            continue
        try:
            size = int(f.get("size", 0))
        except (TypeError, ValueError):
            size = 0
        if size and size > max_bytes:
            continue
        priority = IA_FORMAT_PRIORITY.get(fmt, 4 if lower.endswith(".mp4") else 7)
        candidates.append((priority, size or 10**12, f))
    if not candidates:
        return None
    candidates.sort(key=lambda c: (c[0], c[1]))
    return candidates[0][2]


def ia_collect(query: dict, cfg: dict) -> list[dict]:
    items, page = [], 1
    while len(items) < query.get("max_items", 100):
        params = [("q", query["q"]), ("output", "json"), ("rows", query.get("rows", 100)), ("page", page),
                  ("sort[]", "downloads desc")]
        for field in ("identifier", "title", "description", "year", "language", "licenseurl",
                      "downloads", "subject", "creator", "runtime"):
            params.append(("fl[]", field))
        data = get_json(f"{IA_SEARCH}?{urlencode(params)}")
        docs = data.get("response", {}).get("docs", [])
        if not docs:
            break
        items.extend(docs)
        page += 1
    return items[: query.get("max_items", 100)]


def ia_to_movie(doc: dict, cfg: dict) -> dict | None:
    ident = doc.get("identifier")
    lic_url = doc.get("licenseurl")
    if not ident:
        return None
    if not lic_url and not cfg.get("allow_unlicensed"):
        return None  # Archive no garantiza derechos: sin licencia declarada, no entra.
    try:
        meta = get_json(f"{IA_META}{quote(ident)}", retries=1, timeout=30)
    except RuntimeError as exc:
        print(f"[movies] {ident}: sin metadatos ({exc})")
        return None
    chosen = pick_ia_file(meta.get("files", []), cfg["max_file_bytes"])
    if not chosen:
        return None
    ftype = "mp4" if chosen["name"].lower().endswith((".mp4", ".m4v")) else (
        "webm" if chosen["name"].lower().endswith(".webm") else "ogv")
    year = str(doc.get("year") or "")[:4]
    subjects = [s.strip().lower() for s in as_list(doc.get("subject")) if isinstance(s, str)][:6]
    desc = doc.get("description")
    desc = " ".join(as_list(desc))[:600] if desc else ""
    desc = re.sub(r"<[^>]+>", " ", desc)
    return {
        "id": f"ia-{slugify(ident)}",
        "kind": "movie",
        "title": " ".join(as_list(doc.get("title")))[:140] or ident,
        "year": int(year) if year.isdigit() else None,
        "languages": norm_language(doc.get("language")),
        "genres": subjects,
        "overview": desc,
        "poster": f"https://archive.org/services/img/{quote(ident)}",
        "popularity": int(doc.get("downloads") or 0),
        "license": license_label(lic_url) or "Sin licencia declarada",
        "license_url": lic_url,
        "rights_note": "Licencia declarada por quien subió el ítem; Internet Archive no la garantiza.",
        "origin": "Internet Archive",
        "origin_url": f"https://archive.org/details/{quote(ident)}",
        "sources": [{
            "url": f"https://archive.org/download/{quote(ident)}/{quote(chosen['name'])}",
            "type": ftype,
            "quality": None,
            "status": STATUS_UNCHECKED,
            "reason": "Todavía no verificado",
        }],
    }


def commons_collect(category: str) -> list[dict]:
    params = {
        "action": "query", "format": "json", "generator": "categorymembers",
        "gcmtitle": category, "gcmtype": "file", "gcmlimit": "50",
        "prop": "imageinfo", "iiprop": "url|mime|size|extmetadata",
    }
    data = get_json(f"{COMMONS_API}?{urlencode(params)}")
    movies = []
    for page in (data.get("query", {}).get("pages", {}) or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        mime = info.get("mime", "")
        if mime not in ("video/webm", "video/ogg", "application/ogg"):
            continue
        ext = info.get("extmetadata", {})
        lic = ext.get("LicenseShortName", {}).get("value")
        if not lic:
            continue
        title = re.sub(r"^File:|\.[A-Za-z0-9]+$", "", page.get("title", ""))
        movies.append({
            "id": f"commons-{slugify(title)}",
            "kind": "movie",
            "title": title.replace("_", " "),
            "year": None,
            "languages": [],
            "genres": [category.replace("Category:", "").replace("_", " ").lower()],
            "overview": re.sub(r"<[^>]+>", "", ext.get("ImageDescription", {}).get("value", ""))[:600],
            "poster": None,
            "popularity": 0,
            "license": lic,
            "license_url": ext.get("LicenseUrl", {}).get("value"),
            "rights_note": "Licencia tomada de los metadatos de Wikimedia Commons.",
            "origin": "Wikimedia Commons",
            "origin_url": info.get("descriptionurl"),
            "sources": [{
                "url": info["url"], "type": "webm" if mime == "video/webm" else "ogv",
                "quality": f"{info.get('height')}p" if info.get("height") else None,
                "status": STATUS_UNCHECKED, "reason": "Todavía no verificado",
            }],
        })
    return movies


def _default_status(src: dict) -> str:
    return STATUS_EXTERNAL if src.get("type") == "external" else STATUS_UNCHECKED


def manual_entries(path: Path, kind: str) -> list[dict]:
    try:
        data = load_json(path, []) or []
    except ValueError as exc:
        print(f"[manual] {path} tiene JSON inválido y se ignora: {exc}")
        return []
    good = []
    for entry in data:
        if not isinstance(entry, dict) or not entry.get("rights"):
            title = entry.get("title") if isinstance(entry, dict) else entry
            print(f"[manual] '{title}' omitido: falta el campo 'rights' (de dónde sale el derecho a reproducirlo)")
            continue
        entry.setdefault("kind", kind)
        entry.setdefault("id", f"manual-{slugify(entry.get('title', 'x'))}")
        entry.setdefault("origin", "Manual")
        entry.setdefault("license", entry["rights"])
        all_sources = list(entry.get("sources", []))
        for season in entry.get("seasons", []):
            for ep in season.get("episodes", []):
                all_sources.extend(ep.get("sources", []))
        for src in all_sources:
            src.setdefault("status", _default_status(src))
            src.setdefault("reason", "Sitio externo: se abre fuera de la app" if src["status"] == STATUS_EXTERNAL
                           else "Todavía no verificado")
        good.append(entry)
    return good


def mark_fixture(items: list[dict]) -> None:
    for it in items:
        for src in it.get("sources", []):
            src["status"] = STATUS_FIXTURE
            src["reason"] = "Dato de prueba: no es un enlace real"
        for season in it.get("seasons", []):
            for ep in season.get("episodes", []):
                for src in ep.get("sources", []):
                    src["status"] = STATUS_FIXTURE
                    src["reason"] = "Dato de prueba: no es un enlace real"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--out-dir", default="public/data")
    parser.add_argument("--fixtures", help="carpeta con movies.json y series.json de prueba (sin red)")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)

    if args.fixtures:
        movies = load_json(Path(args.fixtures) / "movies.json", [])
        series = load_json(Path(args.fixtures) / "series.json", [])
        mark_fixture(movies)
        mark_fixture(series)
        origin = "DATOS DE PRUEBA locales (data/fixtures)"
    else:
        cfg = {**DEFAULT_CONFIG, **(load_json(Path(args.config), {}) or {})}
        movies, seen = [], set()
        for q in cfg["ia_queries"]:
            try:
                docs = ia_collect(q, cfg)
            except RuntimeError as exc:
                print(f"[movies] consulta '{q['name']}' falló: {exc}")
                continue
            print(f"[movies] '{q['name']}': {len(docs)} resultados de búsqueda")
            for doc in docs:
                if doc.get("identifier") in seen:
                    continue
                seen.add(doc.get("identifier"))
                try:
                    movie = ia_to_movie(doc, cfg)
                except Exception as exc:  # noqa: BLE001 - un ítem raro no debe frenar el catálogo
                    print(f"[movies] {doc.get('identifier')}: ítem omitido por error inesperado ({type(exc).__name__}: {exc})")
                    continue
                if movie:
                    movies.append(movie)
        for cat in cfg.get("commons_categories", []):
            try:
                movies.extend(commons_collect(cat))
            except RuntimeError as exc:
                print(f"[movies] Commons '{cat}' falló: {exc}")
        movies.extend(manual_entries(Path("data/manual/movies.json"), "movie"))
        series = manual_entries(Path("data/manual/series.json"), "series")
        origin = "Internet Archive + Wikimedia Commons + entradas manuales"

    stamp = now_iso()
    save_json(out_dir / "movies.json", {"generated": stamp, "origin": origin, "items": movies})
    save_json(out_dir / "series.json", {"generated": stamp, "origin": origin, "items": series})
    print(f"[movies] {len(movies)} películas, {len(series)} series -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
