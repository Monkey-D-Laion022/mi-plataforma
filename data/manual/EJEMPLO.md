# Entradas manuales

Agregá objetos a `movies.json` o `series.json`. Sin el campo `rights` la entrada se omite:
tenés que dejar escrito de dónde sale el derecho a reproducirla.

```json
{
  "title": "Nombre de la película",
  "year": 1920,
  "languages": ["es"],
  "genres": ["drama"],
  "overview": "Sinopsis breve.",
  "rights": "Dominio público en Argentina (autor fallecido hace más de 70 años) — fuente: <enlace>",
  "sources": [{"url": "https://servidor.ejemplo/pelicula.mp4", "type": "mp4"}]
}
```

Para una serie usá `"seasons": [{"number": 1, "episodes": [{"number": 1, "title": "...", "sources": [...]}]}]`.
Los enlaces a plataformas oficiales (que no se pueden reproducir dentro de la app) van como
`"sources": [{"url": "https://...", "type": "external"}]` y se muestran como "Abrir en el sitio oficial".

En `movies.json` ya hay 4 películas abiertas de Blender y 2 enlaces oficiales como ejemplo real de cada tipo.
