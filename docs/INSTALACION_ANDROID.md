# Instalación desde Android (sin PC)

Todo se hace con **Chrome en el celular** y una cuenta gratuita de GitHub. Dura unos 15 minutos más lo que tarde la primera actualización.

> Si en algún paso GitHub te muestra una página muy distinta a la descripta (menús, botones), abrí el menú ⋮ de Chrome y activá **Sitio para computadoras**. Los nombres de los botones pueden cambiar con el tiempo: yo no pude ver la interfaz actual desde mi entorno.

## Cómo funciona (por qué se hace así)

Chrome en Android **no puede subir carpetas** a GitHub, y la carpeta oculta `.github/workflows/` (donde vive el robot de actualización) se perdería. Por eso el método es:

1. Subís **un solo archivo**: `mi-plataforma.zip` (sin descomprimir).
2. Pegás **un solo archivo de texto** (`update.yml`) en la ruta `.github/workflows/update.yml`.
3. El robot de GitHub **descomprime el ZIP solo**, instala todo y publica la app.

Probé el script de instalación del robot en una simulación local (un repositorio git de prueba): descomprime, ubica `tools/`, `public/`, `data/`, etc. en la raíz, borra el ZIP y **no toca** tu workflow. No lo probé en GitHub real.

## Paso a paso

### 1. Guardar los dos archivos en el celular
Desde la conversación, descargá `mi-plataforma.zip` y `PEGAR_EN_GITHUB_update.yml.txt`. Quedan en la carpeta **Descargas** (app *Archivos*).

### 2. Crear la cuenta y el repositorio
1. Entrá a **github.com** y creá tu cuenta gratuita (o iniciá sesión).
2. Abrí **github.com/new**.
3. *Repository name*: `mi-plataforma`.
4. Elegí **Public**. (Es obligatorio para tener GitHub Pages gratis. Ver “Seguridad” abajo.)
5. Marcá **Add a README file** (así el repositorio ya tiene rama `main`).
6. Tocá **Create repository**.

### 3. Subir el ZIP (sin descomprimir)
1. En tu repositorio: **Add file ▾ → Upload files**.
2. Tocá **choose your files** y, en el selector de Android, abrí **Descargas** y elegí `mi-plataforma.zip`. Si no ves Descargas, tocá ≡ (menú del selector) → *Descargas*.
3. Esperá a que termine la barra de carga.
4. Bajá y tocá **Commit changes**.

### 4. Crear el workflow (el archivo oculto)
1. **Add file ▾ → Create new file**.
2. En el campo del nombre, escribí exactamente: `.github/workflows/update.yml`
   (al escribir cada `/`, GitHub crea la carpeta. Desactivá la autocorrección del teclado si te cambia las letras).
3. Abrí `PEGAR_EN_GITHUB_update.yml.txt` con cualquier app de texto o con Chrome, **seleccioná todo**, **copiá**, volvé a GitHub y **pegá** en el cuadro grande.
4. **Commit changes… → Commit directly to the main branch → Commit changes**.
5. Verificá: en la pantalla principal del repositorio tiene que aparecer la carpeta `.github` (y adentro `workflows/update.yml`).

### 5. Activar GitHub Pages (antes de ejecutar nada)
1. **Settings** (pestaña del repositorio) → **Pages** (menú lateral).
2. En *Build and deployment* → *Source*, elegí **GitHub Actions**.

### 6. Ejecutar el workflow
1. Pestaña **Actions**.
2. Tocá **Actualizar catálogo y publicar** (lista de la izquierda o menú).
3. **Run workflow ▾ → Run workflow** (botón verde).
4. Tocá la corrida que aparece para seguirla. Pasos que verás, en orden: instalar desde el ZIP → limpiar datos de prueba → pruebas → canales → películas → verificar enlaces → guardias → listas M3U → publicar.
5. **Tilde verde en todo = listo.** Puede tardar desde unos minutos hasta más de media hora, según cuántos canales haya que verificar.
6. Si algo sale rojo: **docs/SOLUCION_ERRORES.md** (también está en el repositorio, carpeta `docs`).

### 7. Obtener la dirección final (URL)
- Tiene la forma `https://TU-USUARIO.github.io/mi-plataforma/`.
- Aparece en **Settings → Pages** (“Your site is live at…”) y en la corrida, en el trabajo **deploy**.

### 8. Instalar la app en el celular
Abrí la URL en Chrome → menú ⋮ → **Instalar app** (o **Agregar a la pantalla principal**).

### 9. Usarla
- **Live / Movies / Series**, con filtros.
- Cada elemento dice su estado. **“Funciona”** solo si el verificador pudo abrir el enlace en la última actualización.
- Si un canal no se reproduce dentro de la app, tocá **Abrir en VLC** (instalá VLC desde Google Play).
- En **Ajustes** ves cuándo fue la última actualización y cuántos canales funcionaban.

### 10. Listas M3U (VLC o app IPTV)
Una vez publicada la app:
- `https://TU-USUARIO.github.io/mi-plataforma/lists/live-ar.m3u` (Argentina)
- `https://TU-USUARIO.github.io/mi-plataforma/lists/live-latam.m3u` (Latinoamérica)

**Probar en VLC (Android):** abrí VLC → **Más** → **Nueva transmisión** → pegá la dirección → ▶. Si carga la lista, tocá un canal.
**Probar en una app IPTV:** instalá una que acepte listas por URL (por ejemplo TiviMate, Televizo, IPTV Smarters o GSE Smart IPTV, citadas por sitios de terceros; no las probé) → *Agregar lista / playlist por URL* → pegá la dirección.
Si la lista aparece vacía, mirá `SOLUCION_ERRORES.md` (sección “La lista M3U está vacía”).

## Si no podés subir el ZIP (plan B)
No pude probar estos caminos; son los más realistas sin PC:
1. **Otra app para elegir el archivo:** en “Upload files”, probá el selector **Archivos de Google** o **Documentos** en lugar de *Fotos*. El ZIP debe estar en Descargas.
2. **Editor web de GitHub (github.dev):** en tu repositorio, en el navegador, cambiá `github.com` por `github.dev` en la dirección. Es un editor tipo VS Code dentro de Chrome; ahí podés crear la carpeta `.github/workflows` y subir archivos con el menú del explorador. Puede ser incómodo en pantalla chica.
3. **Uno por uno:** *Add file → Create new file* y pegar cada archivo escribiendo su ruta completa. Son unos 40 archivos: es el último recurso. Si lo necesitás, decime y armo una versión mínima con menos archivos.

## Seguridad
- **GitHub Pages es público**: cualquiera con la dirección ve la app y el catálogo (solo contiene enlaces ya públicos y sus estados). No guardes nada privado en el repositorio.
- No hay claves en el proyecto. Si usás TMDB, tu clave se escribe en **Ajustes** de la app y queda **solo en tu celular** (no se sube a GitHub).
- Lo que **se publica**: solo la carpeta `public/`. Lo que **queda en el repositorio sin publicarse**: `tools/`, `data/`, `docs/`, `tests/`, `config.json`, `README.md`.
- GitHub Actions **puede fallar o pausarse**. En repositorios públicos GitHub desactiva los workflows programados si pasan 60 días sin actividad. Si el sitio deja de actualizarse, entrá a *Actions → Run workflow*. Si una corrida falla, **no se publica nada nuevo y queda en línea la versión anterior**.
