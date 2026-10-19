# Limitaciones, honestamente

## Lo que NO se probó
- **Ningún enlace real.** El entorno donde escribí el código no tenía acceso a internet. Todo lo que viene precargado es dato de prueba (`ejemplo.invalid`).
- Las consultas a la API de iptv-org, Internet Archive y Commons **nunca corrieron**: el código está escrito según la documentación, y su lógica probada con respuestas simuladas (49 pruebas automáticas). La primera ejecución en GitHub puede revelar ajustes (campos, consultas sin resultados).
- La reproducción en Android real: el intent de VLC, hls.js y la instalación como PWA **no se probaron en un teléfono**. Sí probé la interfaz en un Chromium de escritorio con pantalla de celular.
- Que `hls.js` 1.5.20 (versión listada en cdnjs.com) reproduzca una lista real, y que el add-on de Stremio se instale (incluidas las cabeceras CORS de GitHub Pages).

## Calidad y disponibilidad
- Los canales gratuitos **se caen y cambian de dirección** sin aviso. El verificador semanal detecta caídas, pero entre ejecuciones puede haber enlaces rotos.
- “Funciona” significa: *respondió bien desde el servidor de GitHub*. **No garantiza** que funcione en tu celular. Un geobloqueo puede dar resultados distintos según el país.
- 401/403/451 se muestran como “Acceso restringido”, no como “geobloqueado”: desde el verificador no se puede distinguir un bloqueo geográfico de otras causas.
- No se mide calidad real (bitrate, cortes). La etiqueta de calidad (720p, etc.) viene de iptv-org y puede ser inexacta.
- Reproducir en el navegador exige HTTPS y que el servidor permita CORS; muchos streams IPTV no lo hacen. En ese caso, usá VLC.
- Formatos: HLS (.m3u8), MP4, WebM, OGV. DASH, RTMP, RTSP o UDP no están soportados y se marcarían como formato no compatible.
- Películas libres: catálogo **chico y antiguo** (dominio público/Creative Commons). No hay estrenos ni cine comercial. En español latino puede haber muy pocos títulos.
- Series: **no hay fuente automática** gratuita y autorizada que haya podido confirmar. Solo carga manual y enlaces a sitios oficiales (Cine.ar Play, que incluye series argentinas y se abre fuera de la app). La app lo dice en la pestaña Series.
- Las 4 películas de Blender están en inglés y casi sin diálogos; no hay títulos en español latino confirmados.

## Derechos
- iptv-org enlaza, no autoriza: no hay garantía por canal. Usá `live_allowlist.txt` si querés ser estricto.
- Internet Archive no garantiza el copyright de sus ítems: se filtra por `licenseurl`, pero esa licencia la declara quien subió el archivo.
- Las leyes de derechos varían por país. Esto no es asesoramiento legal.
- La app publicada es pública; no aloja video, pero muestra enlaces.

## Mantenimiento (estimado)
- Revisar una vez por mes que el workflow siga activo. En repos públicos, GitHub **desactiva los workflows programados tras 60 días sin actividad**; el commit semanal de `data/state.json` probablemente cuente como actividad, pero no lo verifiqué. Si se pausa, *Run workflow* lo reactiva.
- Si cambia la API de iptv-org o la de Archive, habrá que ajustar `tools/`.
- Si TMDB cambia sus condiciones, hay que revisarlas (el caché de 30 días y la atribución).
- Smart TV: la ruta más simple es la M3U en una app de TV, o Stremio/Jellyfin si tu modelo los tiene. No verifiqué qué marcas los soportan.
