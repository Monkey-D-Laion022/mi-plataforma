# Resumen de pruebas (19 de octubre de 2026)

**Mi entorno no tenía acceso a Internet para los scripts.** Las herramientas de lectura web que sí tenía rechazaban cualquier URL que no viniera de un resultado de búsqueda, así que **no pude leer la API de iptv-org, ni las listas M3U reales, ni Internet Archive, ni probar un solo canal o película real.** No hay resultados reales de canales en este proyecto, y no inventé ninguno.

## 1. Probado (ejecutado de verdad)

| Qué | Cómo | Resultado |
|---|---|---|
| Lógica del verificador | Servidor HTTP local que simula listas HLS buenas/malas, MP4, 403, 404, 503, cabeceras requeridas, host inexistente | OK |
| Un enlace roto no frena el catálogo | Prueba con una fuente que lanza una excepción entre dos buenas | OK: queda “caído” y las otras se verifican |
| Importador LIVE (filtros) | Datos de prueba con canales adultos, cerrados, bloqueados, fuera de LatAm y sin fuentes; modo lista blanca | OK |
| Importador de películas (reglas de derechos, elección de archivo, licencias, entradas manuales sin `rights`, JSON roto) | Pruebas automáticas | OK |
| Guardias anti-lista-vacía | Escenarios: API vacía, sin Argentina, caída total de red, ningún “ok”, datos de prueba en corrida real, M3U vacía por error | OK: todas fallan como debe; el caso sano pasa |
| Exportación M3U | Solo fuentes “ok”; nunca prueba ni sin verificar | OK |
| Add-on de Stremio (estructura) | Se comprobaron los campos requeridos del manifest según la documentación oficial (`id` con puntos, `name`, `description`, `version`, `types`, `catalogs`, `resources`), ids únicos y que cada entrada tenga sus archivos `meta` y `stream` | OK |
| Higiene | Sin claves en el repositorio; solo `public/` se publica; el workflow tiene las guardias | OK |
| **Instalación desde ZIP** | Ejecuté el script del paso de instalación del workflow en un repositorio git de prueba | OK: instala en la raíz, borra el ZIP, **no toca** `.github/` |
| Workflow | YAML válido con PyYAML | OK (no se ejecutó en GitHub) |
| Interfaz | Chromium de escritorio con pantalla de 390×844: pestañas, filtros, reproductor, detalle, ajustes, sin errores de consola | OK |

Total: **49 pruebas automáticas, todas OK** (`python -m unittest discover -s tests -v`).

## 2. NO probado (no pude)

- **Cualquier acceso real a Internet:** API de iptv-org, Internet Archive, Wikimedia Commons, TMDB.
- **Ningún canal ni película real** pasó por el verificador. Los 4 títulos de Blender y los 2 enlaces oficiales cargados a mano **nunca fueron abiertos por mí**: sus direcciones salen de páginas encontradas en búsquedas.
- **Ejecución en GitHub real:** Pages, Actions, permisos, tiempos, la instalación desde ZIP en el servidor de GitHub.
- **Ningún dispositivo Android real:** instalación como app, reproducción, botón “Abrir en VLC” (intent), `hls.js` con una lista HLS real.
- **M3U en VLC o en una app IPTV; instalación del add-on en Stremio** (ni si GitHub Pages envía las cabeceras CORS que Stremio necesita).
- Smart TV: ningún modelo.
- TMDB con una clave real; el logo oficial de TMDB (falta agregarlo).

## 3. Fuentes reales encontradas (por búsqueda, sin abrirlas desde un script)

| Fuente | Qué es | Confianza |
|---|---|---|
| iptv-org: API (`iptv-org.github.io/api`) y listas M3U por país (`…/iptv/countries/ar.m3u`) | Canales LIVE. Espejos del README muestran **entre 67 y 81 canales para Argentina**, según la fecha del espejo (número actual: no verificado) | Documentación oficial + espejos |
| Sitio de terceros: dice que iptv-org **ya no comprueba si los streams están vivos** | Por eso el verificador propio es indispensable | Secundaria |
| Internet Archive, ítem **Sintel_201709** (“Blender Foundation Films”) | Lista los archivos `Big Buck Bunny.mp4`, `Sintel.mp4`, `Tears of Steel.mp4`, `Elephants Dream.ogv` (también `.ogv` de otros) | Página del ítem, vista en una búsqueda |
| Internet Archive, ítem **BigBuckBunny** | Licencia “Atribución 3.0 Creative Commons”, año 2008, inglés | Página del ítem, vista en una búsqueda |
| Licencias de las películas abiertas de Blender | Tears of Steel: CC BY 3.0 (sitio oficial). Big Buck Bunny: CC BY 3.0 (cita del sitio oficial). Sintel: “Creative Commons Attribution” (cita del sitio oficial; la versión 3.0 viene de listados secundarios). Elephants Dream: CC BY 2.5 según Wikipedia (secundaria) | Mixta: ver `data/manual/movies.json` |
| **Cine.ar Play** (INCAA): `http://www.cine.ar/` | Plataforma oficial gratuita con películas, cortos y **series argentinas**; registro gratuito; según el INCAA citado por la prensa, disponible en todo el mundo. Sigue bajo el INCAA (Decreto 821/2025, según prensa) | Prensa (varias notas); **enlace externo, no se reproduce en la app** |
| **Retina Latina**: `https://www.retinalatina.org` | Cine latinoamericano de acceso abierto, según notas | Prensa; enlace externo |
| Otras plataformas oficiales mencionadas | RTVCPlay (Colombia), OndaMedia / CNTV (Chile), RTVE Play (España), Libreflix | Prensa; **no incluidas** (no tengo sus direcciones verificadas) |
| WikiFlix | Más de 4.000 películas de dominio público o licencia libre, con metadatos de Wikidata | Secundaria; idea para una ampliación futura |
| API oficial de Internet Archive (`advancedsearch.php`, `/metadata/`) y MediaWiki de Commons | Se usan en `tools/build_movies.py`; **las consultas por defecto no fueron ejecutadas** | Documentación |

**No encontré:** (a) series en español latino con licencia abierta o distribución automatizable; (b) películas en español latino con licencia abierta, con enlace directo confirmado. La app lo dice en pantalla (pestaña Series).

## 4. Qué funciona, qué falta, qué no se pudo verificar

**Funciona (código probado):** importar, clasificar y verificar fuentes; separar metadatos de enlaces; marcar caídos/restringidos/formato incompatible/sin cifrar/con cabeceras; no frenar por un error individual; no publicar si el resultado es sospechoso; generar M3U solo con enlaces “ok”; add-on estático de Stremio; interfaz Live/Movies/Series; instalación desde ZIP.

**Falta (depende de tu primera corrida en GitHub):** los catálogos reales, las listas `live-ar.m3u` y `live-latam.m3u` con canales verificados, el add-on de Stremio con contenido, y el informe real de cuántos canales funcionan. **Esos archivos no existen todavía: se generan solos en la primera ejecución.**

**Pendiente de tu parte o futuro:** logo oficial de TMDB (si usás TMDB); ajustar `config.json` si las consultas de películas devuelven 0; ampliar fuentes de películas libres (p. ej., vía WikiFlix/Wikidata).

**No verificado:** todo lo de la sección 2.
