# Costos

## Configuración inicial: USD 0

| Pieza | Costo | Condición |
|---|---|---|
| Cuenta de GitHub | $0 | Plan Free |
| GitHub Pages | $0 | Repositorio **público** |
| GitHub Actions | $0 | Repositorio público, runners estándar |
| iptv-org API, Internet Archive, Wikimedia Commons | $0 | API pública sin clave |
| TMDB | $0 | Solo uso **no comercial**, con atribución. Es opcional |
| Stremio, VLC, Jellyfin | $0 | Software gratuito |

## Gastos recurrentes posibles (no están en la configuración base)

| Gasto | Cuándo aparece | Monto |
|---|---|---|
| Dominio propio | Solo si querés una dirección propia | No investigué precios actuales |
| Repositorio privado con Pages | Si querés ocultar el repo | Requiere plan de pago de GitHub (precio no verificado) y **la página igual sería pública** |
| Servidor remoto (VPS) para Jellyfin | Solo si querés alojar archivos propios sin equipo en casa | No investigué precios; es el único gasto que rompe el costo cero |
| Tailscale | Con más de 3 usuarios (según agregadores) | No verificado |
| Equipo en casa siempre encendido | Para Jellyfin casero | Hardware + electricidad: depende de lo que tengas |
| **Tus datos móviles** | Siempre que veas video fuera de WiFi | Ver abajo |

## Tu consumo de datos (cuenta, no estimación de mercado)

GB por hora ≈ Mbps × 0,45. Ejemplos: 1 Mbps ≈ 0,45 GB/h · 2 Mbps ≈ 0,9 GB/h · 5 Mbps ≈ 2,25 GB/h. Un canal en SD suele andar por 1–2 Mbps y uno en HD por más; el bitrate real de cada fuente lo desconozco.

## Riesgo de costo oculto

Si el workflow o el hosting se pasan de los límites (ver `INVESTIGACION.md`), GitHub puede pedirte reducir el uso antes de cobrar. Esta app transfiere **solo JSON e íconos**, nunca video, así que está muy lejos de esos límites.
