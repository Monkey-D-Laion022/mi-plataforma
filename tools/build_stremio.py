"""Genera un add-on ESTÁTICO de Stremio en public/stremio/ (solo archivos JSON).

El protocolo de add-ons de Stremio es REST + JSON:
    /manifest.json
    /catalog/{type}/{id}.json
    /meta/{type}/{id}.json
    /stream/{type}/{id}.json
Un add-on que no necesita lógica dinámica puede servirse como archivos estáticos
(por ejemplo, desde GitHub Pages). Esto expone SOLO tus propias fuentes verificadas:
nunca consulta add-ons de terceros ni fuentes torrent/debrid.

Solo se publican ítems con al menos una fuente en estado "ok" que pueda reproducirse
por HTTPS sin cabeceras especiales. Los datos de prueba nunca se publican.
CORS: Stremio necesita que el servidor envíe cabeceras CORS; verificá que tu hosting las envíe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import STATUS_OK, load_json  # noqa: E402

OUT = Path("public/stremio")
PREFIX = "iptvp"


def playable(src: dict) -> bool:
    return (src.get("status") == STATUS_OK and src["url"].startswith("https://")
            and not src.get("referrer") and not src.get("user_agent"))


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    movies = (load_json(Path("public/data/movies.json"), {}) or {}).get("items", [])
    live = (load_json(Path("public/data/live.json"), {}) or {}).get("items", [])
    manifest = {
        "id": "org.personal.iptvp",
        "version": "0.1.0",
        "name": "Mi plataforma personal (solo fuentes verificadas)",
        "description": "Canales en vivo y películas de licencia abierta, verificados automáticamente.",
        "resources": ["catalog", "meta", "stream"],
        "types": ["movie", "tv"],
        "idPrefixes": [f"{PREFIX}_"],
        "catalogs": [
            {"type": "movie", "id": f"{PREFIX}_movies", "name": "Películas libres"},
            {"type": "tv", "id": f"{PREFIX}_live", "name": "TV en vivo (Argentina y LatAm)"},
        ],
    }
    write(OUT / "manifest.json", manifest)

    n_movies = n_live = 0
    movie_metas = []
    for m in movies:
        srcs = [s for s in m.get("sources", []) if playable(s)]
        if not srcs:
            continue
        sid = f"{PREFIX}_{m['id']}"
        meta = {"id": sid, "type": "movie", "name": m["title"], "poster": m.get("poster"),
                "description": m.get("overview", ""), "genres": m.get("genres", [])[:5],
                "releaseInfo": str(m["year"]) if m.get("year") else None}
        meta = {k: v for k, v in meta.items() if v}
        movie_metas.append(meta)
        write(OUT / "meta" / "movie" / f"{sid}.json", {"meta": meta})
        write(OUT / "stream" / "movie" / f"{sid}.json",
              {"streams": [{"url": s["url"], "title": f"{m.get('license', '')} · {s.get('type', '')}".strip(" ·")}
                           for s in srcs]})
        n_movies += 1
    write(OUT / "catalog" / "movie" / f"{PREFIX}_movies.json", {"metas": movie_metas})

    live_metas = []
    for ch in live:
        srcs = [s for s in ch.get("sources", []) if playable(s)]
        if not srcs:
            continue
        sid = f"{PREFIX}_{ch['id']}"
        meta = {"id": sid, "type": "tv", "name": ch["name"], "poster": ch.get("logo"),
                "genres": (ch.get("categories") or [])[:3]}
        meta = {k: v for k, v in meta.items() if v}
        live_metas.append(meta)
        write(OUT / "meta" / "tv" / f"{sid}.json", {"meta": meta})
        write(OUT / "stream" / "tv" / f"{sid}.json",
              {"streams": [{"url": s["url"], "title": s.get("quality") or "HLS"} for s in srcs]})
        n_live += 1
    write(OUT / "catalog" / "tv" / f"{PREFIX}_live.json", {"metas": live_metas})
    print(f"[stremio] add-on estático: {n_movies} películas, {n_live} canales -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
