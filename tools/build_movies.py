from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import STATUS_UNCHECKED, now_iso, save_json, slugify

# Tus 5 listas M3U
LISTAS_M3U = [
    "http://xdplus.site:2082/get.php?username=EstebanQP&password=ZVXNF&type=m3u_plus",
    "http://aurinegro.site:8080/get.php?username=RICARDOTORREZ&password=5MZg5DjYd9&type=m3u_plus",
    "http://bunkertp.xyz:8000/get.php?username=gubazu4&password=210727&type=m3u_plus",
    "http://bunkertp.xyz:8000/get.php?username=afsantiagol&password=lopez&type=m3u_plus",
    "http://myultratv.com:8080/get.php?username=956124877tv&password=s08e13&type=m3u_plus",
]


def descargar_y_parsear_m3u(urls: list[str]) -> list[dict]:
    elementos = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    for url in urls:
        print(f"[m3u] Descargando e ingresando lista: {url[:45]}...")
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=25) as response:
                contenido = response.read().decode("utf-8", errors="ignore")
                lineas = contenido.splitlines()

                i = 0
                while i < len(lineas):
                    linea = lineas[i].strip()
                    if linea.startswith("#EXTINF:"):
                        # Extraer carátula/logo si existe
                        logo_match = re.search(r'tvg-logo="([^"]+)"', linea)
                        logo = logo_match.group(1) if logo_match else None

                        # Extraer categoría si existe
                        group_match = re.search(r'group-title="([^"]+)"', linea)
                        categoria = (
                            group_match.group(1).lower()
                            if group_match
                            else "general"
                        )

                        # Extraer título
                        titulo = (
                            linea.split(",")[-1].strip()
                            if "," in linea
                            else "Sin Título"
                        )

                        # Buscar la URL del stream en la línea siguiente
                        i += 1
                        while i < len(lineas) and not lineas[i].strip():
                            i += 1

                        if i < len(lineas):
                            stream_url = lineas[i].strip()
                            if stream_url.startswith("http"):
                                ftype = (
                                    "hls"
                                    if ".m3u8" in stream_url
                                    else "mp4"
                                )
                                item_id = f"m3u-{slugify(titulo[:40])}-{len(elementos)}"

                                elementos.append({
                                    "id": item_id,
                                    "kind": "movie",
                                    "title": titulo,
                                    "year": None,
                                    "languages": ["es"],
                                    "genres": [categoria],
                                    "overview": f"Categoría: {categoria}",
                                    "poster": logo,
                                    "popularity": 100,
                                    "license": "Lista M3U personal",
                                    "license_url": None,
                                    "rights_note": "Fuente M3U directa provista por el usuario.",
                                    "origin": "Listas M3U",
                                    "origin_url": None,
                                    "sources": [{
                                        "url": stream_url,
                                        "type": ftype,
                                        "quality": "HD",
                                        "status": STATUS_UNCHECKED,
                                        "reason": "Pendiente de verificación",
                                    }],
                                })
                    i += 1
        except Exception as exc:
            print(f"[m3u] Error al procesar la lista {url[:35]}: {exc}")

    return elementos


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--out-dir", default="public/data")
    parser.add_argument("--fixtures", help="no utilizado en modo M3U")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)

    print("[build_movies] Procesando listas M3U...")
    movies = descargar_y_parsear_m3u(LISTAS_M3U)

    # Cargar también manuales de data/manual/movies.json si querés sumar algo local a futuro
    manual_path = Path("data/manual/movies.json")
    if manual_path.exists():
        try:
            with open(manual_path, "r", encoding="utf-8") as f:
                manual_data = json.load(f)
                if isinstance(manual_data, list):
                    for entry in manual_data:
                        if isinstance(entry, dict) and entry.get("title"):
                            movies.append(entry)
        except Exception as exc:
            print(f"[manual] Error al cargar {manual_path}: {exc}")

    stamp = now_iso()
    origin = "Listas M3U externas"

    out_dir.mkdir(parents=True, exist_ok=True)
    save_json(
        out_dir / "movies.json",
        {"generated": stamp, "origin": origin, "items": movies},
    )
    # Dejamos series preparado por compatibilidad
    save_json(
        out_dir / "series.json",
        {"generated": stamp, "origin": origin, "items": []},
    )

    print(
        f"[build_movies] ¡Listo! {len(movies)} elementos guardados en {out_dir / 'movies.json'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
                              
