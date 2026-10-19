# Solución de errores

Primero, mirá **dónde** falló: *Actions → la corrida → el paso en rojo → tocá el paso para ver el registro*. Las líneas que empiezan con `::error::` dicen qué pasó en castellano.

## Instalación

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| El paso “Instalar el proyecto desde el ZIP” dice *El ZIP no contiene la carpeta tools/* | Se subió otro ZIP o uno re-comprimido | Borrá el ZIP del repositorio y subí de nuevo `mi-plataforma.zip` original |
| En la corrida no aparece el paso de instalación o dice *No hay ZIP en la raíz* | Es normal después de la primera vez (el ZIP se borra solo) | Nada: ya está instalado |
| El workflow no aparece en *Actions* | El archivo no quedó en `.github/workflows/update.yml` | Revisá el nombre exacto (con el punto inicial y sin espacios) |
| *Get Pages site failed* / *Not Found* en “configure-pages” | GitHub Pages no está activado | *Settings → Pages → Source: GitHub Actions* y volvé a ejecutar |
| *Resource not accessible by integration* | El repositorio limita los permisos del robot | *Settings → Actions → General → Workflow permissions → Read and write permissions → Save* y volvé a ejecutar |
| *refusing to allow … to create or update workflow* | Se intentó modificar un archivo de `.github` con el robot | Está evitado en este proyecto; no edites `.github` desde el ZIP |
| La URL da *404* | Todavía no terminó el primer despliegue, o falló | Esperá a que el trabajo **deploy** tenga tilde verde |

## Actualización de catálogos

| Mensaje | Qué significa | Qué hacer |
|---|---|---|
| `live.json no tiene canales` o `…de Argentina` | La API de iptv-org no respondió o cambió | Reintentá más tarde. Si se repite, avisame: hay que adaptar `tools/build_live.py` |
| `N de M fuentes sin respuesta de red` | Falló la conexión del servidor de GitHub, no los canales | Reintentá más tarde. No se publica nada roto |
| `ninguna de las fuentes verificadas dio ‘ok’` | Casi seguro un problema del verificador o de red | Reintentá; si se repite, revisá el registro del paso “Verificar enlaces” |
| `contiene datos de prueba en una corrida real` | Se mezcló data de ejemplo | Revisá que el paso “Limpiar datos de prueba” no esté borrado del workflow |
| `live-ar.m3u tiene 0 canales pero el catálogo dice N` | Error en la exportación | Reintentá; si se repite, avisame con el registro |
| Advertencia: *Ningún canal de Argentina figura como funciona* | Los canales argentinos fallaron en esta corrida (puede ser real o por bloqueo geográfico del servidor) | La app se publica igual. Probá los canales en tu celular, que puede dar otro resultado; esperá a la próxima corrida |
| Advertencia: *movies.json está vacío* | Las consultas a Internet Archive no devolvieron nada o fallaron | Los títulos de `data/manual/movies.json` igual aparecen. Ajustá `config.json` (ver más abajo) |
| El paso “Películas y series” sale naranja/rojo pero sigue | Está configurado para **no frenar** el resto | Revisá el registro: dice qué consulta falló |

**Ajustar las consultas de películas** (`config.json`): cada consulta usa la sintaxis de búsqueda de Internet Archive. Si dan 0 resultados, simplificá: por ejemplo, quitá `AND language:(...)`. Se edita desde Chrome: abrí el archivo en GitHub → ✏️ → *Commit changes*, y volvé a ejecutar el workflow.

## En la app

| Síntoma | Qué hacer |
|---|---|
| Todo figura “Sin verificar” o hay un cartel amarillo de datos de prueba | Todavía no terminó una corrida real. Ejecutá el workflow |
| Veo una versión vieja de la app | Cerrá y abrí la app dos veces; si sigue, Chrome → ⋮ → Configuración → Configuración de sitios → Almacenamiento → borrar datos del sitio |
| Un canal dice “Funciona” pero no se ve | “Funciona” = respondió bien desde el servidor de GitHub. Puede estar bloqueado en tu país, o necesitar CORS. Tocá **Abrir en VLC** |
| “Abrir en VLC” no hace nada | Instalá VLC; o tocá **Copiar enlace** y pegalo en VLC → Más → Nueva transmisión |
| “Acceso restringido” | El enlace respondió 401/403/451: puede ser geobloqueo o requerir cabeceras. Probalo en VLC; si no anda, ese canal no sirve desde tu zona |
| “HTTP sin cifrar” o “Exige cabeceras propias” | El navegador no puede reproducirlo: usá VLC |
| Las películas no tienen carátula | Normal. Opcional: poné tu clave gratuita de TMDB en *Ajustes* |
| Series casi vacío | Es un límite conocido: no hay fuente gratuita y autorizada que pueda automatizarse (ver `LIMITACIONES.md`) |

## Add-on de Stremio
- Abrí `https://TU-USUARIO.github.io/mi-plataforma/stremio/manifest.json` en Chrome: tiene que mostrar un texto JSON. Si da 404, todavía no se publicó.
- Si Stremio no lo instala, puede ser por las cabeceras CORS del hosting (GitHub Pages no lo tengo verificado). Usá la app web o las listas M3U.
- Si no hay películas/canales en el add-on: solo se publican los que figuran “Funciona”, con HTTPS y sin cabeceras especiales.

## El robot dejó de actualizar
GitHub desactiva los workflows programados tras 60 días sin actividad en repositorios públicos. Entrá a *Actions*, abrí el workflow y tocá **Enable workflow** y/o **Run workflow**.
