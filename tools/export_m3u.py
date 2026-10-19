"""Genera listas M3U (para VLC, Jellyfin, apps de TV) con los canales cuyo estado es "ok".

Salida:
    public/lists/live-ar.m3u       solo Argentina
    public/lists/live-latam.m3u    Argentina primero, luego el resto de Latinoamérica

Los datos de prueba (status = fixture) y las fuentes sin verificar NUNCA se exportan.
Si una fuente exige Referer/User-Agent propios, se agregan líneas #EXTVLCOPT, que VLC entiende.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import STATUS_OK, load_json  # noqa: E402


def render(items: list[dict]) -> tuple[str, int]:
    lines = ["#EXTM3U"]
    count = 0
    for ch in items:
        good = [s for s in ch.get("sources", []) if s.get("status") == STATUS_OK]
        if not good:
            continue
        src = good[0]
        name = ch["name"].replace(",", " ")
        group = f"{ch.get('country_name', '')} / {(ch.get('categories') or ['general'])[0]}"
        attrs = f'tvg-id="{ch["id"]}" group-title="{group}"'
        if ch.get("logo"):
            attrs += f' tvg-logo="{ch["logo"]}"'
        lines.append(f"#EXTINF:-1 {attrs},{name}")
        if src.get("referrer"):
            lines.append(f"#EXTVLCOPT:http-referrer={src['referrer']}")
        if src.get("user_agent"):
            lines.append(f"#EXTVLCOPT:http-user-agent={src['user_agent']}")
        lines.append(src["url"])
        count += 1
    return "\n".join(lines) + "\n", count


def main() -> int:
    catalog = load_json(Path("public/data/live.json"), {}) or {}
    items = catalog.get("items", [])
    out_dir = Path("public/lists")
    out_dir.mkdir(parents=True, exist_ok=True)
    ar_text, ar_n = render([c for c in items if c.get("country") == "AR"])
    all_text, all_n = render(items)
    (out_dir / "live-ar.m3u").write_text(ar_text, encoding="utf-8")
    (out_dir / "live-latam.m3u").write_text(all_text, encoding="utf-8")
    print(f"[m3u] AR: {ar_n} canales verificados · LATAM: {all_n} canales verificados -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
