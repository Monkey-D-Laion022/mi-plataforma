# Investigación técnica (18 de octubre de 2026)

Cada afirmación lleva un nivel de confianza:

- **[Oficial]** leída en la documentación o el sitio del propio proyecto.
- **[Secundaria]** sale de artículos, espejos o agregadores; falta confirmarla en la fuente oficial.
- **[No verificado]** lo sé por conocimiento general o lo deduzco; hay que probarlo.

Importante: no pude abrir el sitio oficial de TMDB con herramientas automáticas (su robots.txt lo impide), así que de sus términos solo tengo los fragmentos que devolvió el buscador.

## 1. LIVE — iptv-org

| Dato | Confianza |
|---|---|
| El repo `iptv-org/iptv` es una colección de enlaces a streams públicos; **no almacena video**. Licencia Unlicense. | [Oficial] (README en GitHub) |
| Su aviso legal dice que los enlaces provienen de envíos de usuarios y que, "a su leal saber", los titulares los hicieron públicos a propósito, pero que **no controlan el destino del enlace**. | [Oficial] |
| API pública: `channels.json`, `streams.json`, `feeds.json`, `logos.json`, `guides.json`, `categories.json`, `languages.json`, `countries.json`, `regions.json`, `cities.json`, `timezones.json`, `blocklist.json`, bajo `https://iptv-org.github.io/api/`. | [Oficial] (README de `iptv-org/api`, copia en jsDelivr) |
| Un canal tiene `id`, `name`, `country`, `categories`, `languages`, `is_nsfw`, `closed`, `logo`, `website`. Un stream tiene `url`, `referrer`, `user_agent` (y otros). | [Oficial] |
| `blocklist.json` lista canales con motivo (por ejemplo `dmca`) y referencia a un issue. | [Oficial] |
| Existen listas M3U en `https://iptv-org.github.io/iptv/index.m3u`; el patrón por país es `…/iptv/countries/ar.m3u`. | El `index.m3u` es [Secundaria]; el patrón por país es [No verificado] (lo uso solo como alternativa; el prototipo usa la API JSON) |
| El repositorio sufrió un **takedown por DMCA en 2023** (hilo de Hacker News); luego volvió. | [Secundaria] |
| Un workflow de GitHub Actions del propio repo regenera playlists y la API. | [Oficial] (archivo `update.yml`) |

**Lo que implica:**
1. Es la mejor fuente para LIVE, con país/categoría/idioma. Argentina y LatAm se filtran por `country`.
2. **iptv-org no garantiza que cada canal sea autorizado.** Para tu requisito de “solo fuentes autorizadas”, el prototipo excluye NSFW, cerrados y blocklist, y ofrece `live_allowlist.txt` (solo los canales que vos marques). Recomiendo empezar con allowlist de emisoras abiertas u oficiales.
3. Hay streams que exigen `referrer`/`user_agent`: un navegador no puede enviar esos encabezados, por eso se ofrece VLC.
4. Como el repo ya fue bajado una vez, no conviene depender de espejos: el prototipo lee la API oficial y guarda tu catálogo en tu propio repositorio.

## 2. MOVIES y SERIES — fuentes de licencia abierta

**Internet Archive**
- API de búsqueda sin clave: `advancedsearch.php` (límite de 10.000 resultados ordenados) y API de *scraping* con cursor; metadatos por ítem en `/metadata/<id>`. [Oficial] (`archive.org/help/aboutsearch.htm`; el endpoint `/metadata/` lo confirman clientes de terceros → [Secundaria])
- El campo `licenseurl` existe y permite filtrar por Creative Commons. [Secundaria]
- **Archive no garantiza el estado de copyright** de sus ítems y exige usarlos "bajo tu propio riesgo". [Oficial] (`help.archive.org/help/rights/`). Por eso el prototipo **solo incluye ítems con `licenseurl`**, y lo muestra en pantalla como "licencia declarada por quien subió el ítem".
- Español latino: no pude confirmar ningún título concreto disponible. La consulta del prototipo filtra por idioma español + licencia, pero **no está probada**; puede devolver pocos resultados.

**Wikimedia Commons**
- MediaWiki Action API sin clave (`list=categorymembers`, `prop=imageinfo`, `extmetadata` con la licencia; `prop=videoinfo` en TimedMediaHandler). [Secundaria] (documentación autogenerada de wikis MediaWiki y guías de terceros)
- Formatos de video: WebM y OGV. [Secundaria] No todos los Smart TV los reproducen. [No verificado]
- Predomina material corto; los largometrajes son pocos.

**WikiFlix** (Toolforge, proyecto de voluntarios Wikimedia): agrega más de 4.000 películas de dominio público o licencia libre desde Commons, Internet Archive o YouTube/Vimeo, con metadatos de Wikidata. [Secundaria] (varios artículos y el *Signpost*). Es la mejor guía para **descubrir** películas libres; su código y datos (Wikidata) son una ruta futura para automatizar la importación.

**Películas abiertas de Blender** (Elephants Dream, Big Buck Bunny, Sintel, Tears of Steel, Spring): licencias Creative Commons Attribution declaradas por la Blender Foundation. [Oficial para Tears of Steel (mango.blender.org); Secundaria para las demás] No verifiqué las URLs de descarga, así que **no están en el catálogo**.

**Plataformas oficiales gratuitas con cine latinoamericano**: Retina Latina, Cine.ar Play (INCAA), RTVCPlay, entre otras. [Secundaria] (notas periodísticas). Son aplicaciones/sitios propios **sin API pública conocida para integrarlas**: lo legítimo es **abrirlas en su sitio oficial** (`type: "external"` en `data/manual`). Algunas piden registro o son específicas por país. No las incluí por defecto porque no verifiqué sus direcciones oficiales.

**Series:** no encontré una fuente gratuita, autorizada y automatizable de series en español latino. El prototipo soporta series (temporadas/episodios) vía `data/manual/series.json` y enlaces externos. Cualquier promesa de “biblioteca de series” sería falsa.

## 3. Stremio

| Dato | Confianza |
|---|---|
| El SDK oficial (`Stremio/stremio-addon-sdk`) es de Node.js; existen portes de terceros (Go, Deno). | [Oficial] / [Secundaria] |
| El protocolo es REST+JSON: `manifest.json`, `catalog/{type}/{id}.json`, `meta/{type}/{id}.json`, `stream/{type}/{id}.json` (más `subtitles`). Jerarquía: catálogo → meta → videos → streams. | [Oficial] |
| Un add-on puede ser **estático** (solo archivos JSON). | [Oficial] (el protocolo incluye un "ejemplo de add-on estático") |
| Un objeto *stream* puede llevar una `url` HTTP directa. | [Oficial] |
| Los Términos de Stremio lo describen como catálogo de metadatos y plataforma para contenido **oficial**; los add-ons comunitarios los hacen terceros con el SDK abierto. | [Secundaria] (espejo de los términos) |
| Muchos add-ons comunitarios traen streams desde torrents/debrid. | [Secundaria] |
| Se puede mostrar el resultado de un add-on en una interfaz propia: es HTTP+JSON público. | Técnicamente sí [Deducción]; **no lo hago** con add-ons de terceros |

**Consultar un catálogo no es tener acceso al video.** En el protocolo, `catalog`/`meta` solo dan títulos y carátulas; el video llega en la respuesta de `stream`, y su legitimidad depende del add-on. Por eso:
- El prototipo **genera su propio add-on estático** (`tools/build_stremio.py`) con tus fuentes verificadas: Stremio queda como una **interfaz extra** (útil en Android TV), no como fuente.
- No consulta add-ons de terceros ni integra torrents/debrid.
- Que Stremio esté disponible en tu Smart TV concreta [No verificado]: comprobalo para tu modelo.

## 4. TMDB

| Condición | Confianza |
|---|---|
| API gratuita para uso **no comercial**, citando a TMDB como fuente. Comercial = el propósito principal es generar ingresos para el dueño; requiere acuerdo aparte. | [Oficial] (FAQ de desarrolladores) |
| Atribución: usar un logo aprobado de TMDB y mostrar el aviso *"This product uses the TMDB API but is not endorsed or certified by TMDB."*, dentro de una sección "Acerca de"/"Créditos"; el logo debe ser menos prominente que el de tu app. | [Oficial] |
| La licencia de API es no exclusiva, intransferible y **no sublicenciable**; si se termina, hay que borrar todo el contenido TMDB, incluido el caché. | [Oficial] (fragmento de los API Terms) |
| El API es de código cerrado; hay documentación de límites de tasa (alrededor de 40 solicitudes/seg., variable). | FAQ [Oficial]; el valor numérico [Secundaria] |
| **Caché máximo de 6 meses.** | **[Secundaria] — NO confirmado.** Aparece en agregadores, no lo pude leer en los términos oficiales. |
| Un moderador de TMDB (2021) aceptó que alguien transforme datos y los sirva desde un sitio estático, si cita a TMDB. | [Oficial, foro, antiguo] |

**Decisiones de diseño:**
- TMDB **no es obligatorio**. Las películas libres ya traen carátula y sinopsis de Internet Archive/Commons.
- Para no *redistribuir* datos de TMDB en un repositorio público (zona gris por "no sublicenciable"), la app consulta TMDB **desde tu celular con tu propia clave**, la guarda solo en ese teléfono y cachea **30 días** (más corto que el límite no confirmado).
- Antes de publicar con TMDB: agregá el logo oficial y releé los términos en su sitio.

## 5. Infraestructura

| Opción | ¿Gratis? | Límites | Android / Smart TV | Confianza |
|---|---|---|---|---|
| **GitHub Pages** | Sí, con repositorio **público** (privado requiere plan de pago) | Sitio ≤ 1 GB, ~100 GB/mes de ancho de banda (límite blando), 10 builds/hora (no aplica con Actions), despliegue ≤ 10 min. **Es público aunque el repo sea privado.** | Sirve la app y los JSON; **no es para alojar video** | [Oficial] |
| **GitHub Actions** | Gratis para runners estándar en repos públicos | Los workflows programados se **desactivan tras 60 días sin actividad** en el repo público | Corre el verificador semanal | [Oficial] |
| **Jellyfin en casa** | Software libre; Live TV con tuner M3U + guía XMLTV | Requiere un equipo **siempre encendido** (PC, mini-PC, NAS) y acceso remoto | Hay apps para Android y Android TV; para otras marcas de Smart TV, [No verificado] | Oficial (M3U/XMLTV); clientes [Secundaria] |
| **Acceso remoto a casa (Tailscale)** | Plan personal gratuito (3 usuarios, 100 dispositivos según agregadores) | Los precios cambian; confirmar | Cliente en Android; en Smart TV que no sean Android TV, [No verificado] | [Secundaria] |
| **Servidor remoto (VPS)** | **No es gratis** | Costo mensual recurrente + mantenimiento + transferencia | Sirve para Jellyfin sin equipo propio | [No verificado]: no investigué precios |

**Veredicto:** con tu condición “sin PC”, GitHub Pages + Actions es la única opción realmente gratuita y mantenible desde el celular. Jellyfin solo aporta si **tenés un equipo prendido en casa** y vas a alojar archivos propios (hay que tener los derechos). Un VPS rompe el costo cero.

Privacidad: la app publicada **es pública** (cualquiera con el enlace ve el catálogo). Solo contiene enlaces ya públicos y estados; tu clave de TMDB y tus preferencias quedan en el celular. Si necesitás acceso realmente privado hace falta otro hosting con control de acceso (Cloudflare Access aparece gratis hasta 50 usuarios según Tailscale, [Secundaria]); no lo probé.

## 6. Formato final: ¿M3U, PWA o Stremio?

| Formato | Live | Movies | Series | Mantenible sin PC | Veredicto |
|---|---|---|---|---|---|
| **Lista M3U** | Sí | Pobre (sin carátulas, sinopsis ni temporadas fiables) | No | Sí | Subproducto útil para VLC/TV |
| **PWA** | Sí | Sí | Sí | **Sí** | **Principal** |
| **Add-on Stremio** | Sí (tipo `tv`) | Sí | Sí | Sí si es estático | Interfaz **opcional** |

**Recomendación:** PWA como centro + M3U y add-on estático generados automáticamente desde el mismo catálogo. Una sola fuente de verdad, tres formas de consumirla.

## Anexo (19 de octubre de 2026): hallazgos de la segunda ronda

- **hls.js:** `1.5.17` solo aparece en cdnjs como versión *canary*; la versión estable verificada en cdnjs.com es `1.5.20` (también `1.5.9`). El proyecto usa **1.5.20**. [Oficial: listado de cdnjs]
- **Stremio, manifest oficial:** campos requeridos `id` (con puntos), `name`, `description`, `version`, `types`, `catalogs` y `resources`; `idPrefixes` es opcional. El catálogo se pide en `/catalog/{type}/{id}.json`. La documentación indica que el CORS hay que configurarlo en el hosting remoto. [Oficial (stremio.github.io); lo de CORS: espejo]. El add-on generado cumple esos campos (probado por pruebas automáticas); **no verifiqué que GitHub Pages envíe CORS.**
- **iptv-org:** el patrón `countries/<código>.m3u` figura en el README (espejos). Un sitio de terceros afirma que iptv-org ya no comprueba que los streams estén vivos. [Secundaria]
- **Películas abiertas (Blender):** el ítem `Sintel_201709` de Internet Archive lista `Big Buck Bunny.mp4`, `Sintel.mp4`, `Tears of Steel.mp4` y `Elephants Dream.ogv`. Licencias en `data/manual/movies.json`.
- **Cine.ar Play (INCAA):** plataforma gratuita con películas, cortos y series nacionales, registro gratuito. [Prensa]. Es solo enlace externo.
- **No pude acceder a:** la API de iptv-org, Internet Archive ni los términos oficiales de TMDB (bloqueado por robots.txt).
