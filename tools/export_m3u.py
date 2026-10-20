"""Genera listas M3U (para VLC, TiviMate, IPTV Smarters, Jellyfin, apps de TV) desde los catálogos ya verificados.

Salida en public/lists/:
    live-ar.m3u       canales en vivo de Argentina
    live-latam.m3u    canales en vivo, Argentina primero y luego el resto de Latinoamérica
    movies.m3u        películas
    series.m3u        series (un renglón por episodio, agrupadas por serie)
    vod.m3u           películas + series en una sola lista (la "lista completa unificada" de VOD)

Reglas (las mismas que usa la app):
  * Solo entran fuentes con estado "ok" en la última verificación. Los datos de prueba, los "sin verificar"
    y los enlaces externos (sitios oficiales) NUNCA se exportan.
  * Un ítem de VOD solo se exporta si declara de dónde sale el derecho a reproducirlo (`rights` o `license`).
  * Si una fuente exige Referer/User-Agent, se agregan líneas #EXTVLCOPT (VLC las entiende; otras apps pueden ignorarlas).
  * Este script SOLO LEE public/data/*.json: no modifica los catálogos, así que la PWA no cambia.

AVISO: public/lists/ se publica en GitHub Pages, que es PÚBLICO. Cualquiera con la dirección puede abrir
estas listas y ver los enlaces.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import STATUS_EXTERNAL, STATUS_OK, load_json  # noqa: E402


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def clean_attr(value: str, is_url: bool = False) -> str:
    """Los atributos van entre comillas dobles: se neutralizan comillas, saltos de línea y comas
    (algunos reproductores cortan el #EXTINF en la primera coma, aunque esté entre comillas)."""
    text = str(value).replace('"', "'").replace("\n", " ").replace("\r", " ").strip()
    return text.replace(",", "%2C") if is_url else text.replace(",", " ")


def clean_name(value: str) -> str:
    """El nombre va después de la última coma del #EXTINF: no puede contener comas ni saltos de línea."""
    return str(value).replace(",", " ").replace("\n", " ").replace("\r", " ").strip()


def first_ok(sources: list[dict]) -> dict | None:
    for s in sources or []:
        if s.get("status") == STATUS_OK and s.get("type") != "external" and s.get("status") != STATUS_EXTERNAL \
                and str(s.get("url", "")).startswith(("http://", "https://")):
            return s
    return None


def extinf_block(attrs: dict, name: str, src: dict) -> list[str]:
    attr_text = " ".join(f'{k}="{clean_attr(v, is_url=(k == "tvg-logo"))}"' for k, v in attrs.items() if v)
    lines = [f"#EXTINF:-1 {attr_text},{clean_name(name)}"]
    if src.get("referrer"):
        lines.append(f"#EXTVLCOPT:http-referrer={src['referrer']}")
    if src.get("user_agent"):
        lines.append(f"#EXTVLCOPT:http-user-agent={src['user_agent']}")
    lines.append(src["url"])
    return lines


# ---------------------------------------------------------------------------
# LIVE (sin cambios de comportamiento)
# ---------------------------------------------------------------------------
def render(items: list[dict]) -> tuple[str, int]:
    lines = ["#EXTM3U"]
    count = 0
    for ch in items:
        src = first_ok(ch.get("sources", []))
        if not src:
            continue
        group = f"{ch.get('country_name', '')} / {(ch.get('categories') or ['general'])[0]}"
        attrs = {"tvg-id": ch["id"], "group-title": group, "tvg-logo": ch.get("logo")}
        lines += extinf_block(attrs, ch["name"], src)
        count += 1
    return "\n".join(lines) + "\n", count


# ---------------------------------------------------------------------------
# VOD: películas y series
# ---------------------------------------------------------------------------
def publishable(item: dict) -> bool:
    """Solo se exporta contenido que declara su derecho de reproducción (rights o license)."""
    return bool(item.get("rights") or item.get("license"))


def episode_name(show: str, season: int, number: int, title: str | None) -> str:
    base = f"{show} S{int(season):02d}E{int(number):02d}"
    generic = {"", f"episodio {number}".lower(), "episodio"}
    return base if (title or "").strip().lower() in generic else f"{base} - {title.strip()}"


def vod_entries(movies: list[dict], series: list[dict]) -> list[dict]:
    """Lista plana y ordenada de entradas exportables. La usan tanto el exportador como guard.py."""
    out: list[dict] = []
    for m in sorted(movies, key=lambda i: (i.get("title") or "").lower()):
        if not publishable(m):
            continue
        src = first_ok(m.get("sources", []))
        if not src:
            continue
        genre = ((m.get("genres") or ["sin género"])[0]).title()
        out.append({"kind": "movie", "id": m["id"], "name": m["title"], "group": f"Películas / {genre}",
                    "logo": m.get("poster"), "src": src})
    for s in sorted(series, key=lambda i: (i.get("title") or "").lower()):
        if not publishable(s):
            continue
        for season in sorted(s.get("seasons", []), key=lambda x: x.get("number", 0)):
            for ep in sorted(season.get("episodes", []), key=lambda x: x.get("number", 0)):
                src = first_ok(ep.get("sources", []))
                if not src:
                    continue
                out.append({"kind": "series", "id": f"{s['id']}-s{season['number']}e{ep['number']}",
                            "name": episode_name(s["title"], season["number"], ep["number"], ep.get("title")),
                            "group": f"Series / {s['title']}", "logo": s.get("poster"), "src": src})
    return out


def render_vod(entries: list[dict]) -> tuple[str, int]:
    lines = ["#EXTM3U"]
    for e in entries:
        attrs = {"tvg-id": e["id"], "tvg-name": e["name"], "group-title": e["group"], "tvg-logo": e["logo"]}
        lines += extinf_block(attrs, e["name"], e["src"])
    return "\n".join(lines) + "\n", len(entries)


# ---------------------------------------------------------------------------
def main() -> int:
    data = Path("public/data")
    live = (load_json(data / "live.json", {}) or {}).get("items", [])
    movies = (load_json(data / "movies.json", {}) or {}).get("items", [])
    series = (load_json(data / "series.json", {}) or {}).get("items", [])

    out_dir = Path("public/lists")
    out_dir.mkdir(parents=True, exist_ok=True)

    ar_text, ar_n = render([c for c in live if c.get("country") == "AR"])
    latam_text, latam_n = render(live)
    entries = vod_entries(movies, series)
    movie_text, movie_n = render_vod([e for e in entries if e["kind"] == "movie"])
    series_text, series_n = render_vod([e for e in entries if e["kind"] == "series"])
    vod_text, vod_n = render_vod(entries)

    for name, text in (("live-ar.m3u", ar_text), ("live-latam.m3u", latam_text), ("movies.m3u", movie_text),
                       ("series.m3u", series_text), ("vod.m3u", vod_text)):
        (out_dir / name).write_text(text, encoding="utf-8")

    print(f"[m3u] LIVE AR: {ar_n} · LIVE LATAM: {latam_n} · películas: {movie_n} · "
          f"episodios de series: {series_n} · vod.m3u (unificada): {vod_n} -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
    
