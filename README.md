# Rama `datos`

Datos que genera la lectura automática de FiguraTodo. **No se edita a mano.**

- `data/`: lo que publica el sitio (products.json, history.json, meta.json).
- `cache/`: memoria del lector entre lecturas (qué páginas ya leyó, stock, fechas).

Cada lectura reemplaza esta rama por un único commit nuevo, así el repositorio no crece con cada actualización.
El código vive en la rama `main`.
