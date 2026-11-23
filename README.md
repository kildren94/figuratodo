# FiguraTodo

Comparador de precios de figuras de anime en tiendas chilenas, al estilo SoloTodo.

- **Sitio:** `docs/index.html`, publicado con GitHub Pages.
- **Datos:** `docs/data/` (`products.json`, `meta.json`, `history.json`), generados automáticamente.
- **Actualización:** GitHub Actions corre `.github/workflows/actualizar-precios.yml` tres veces al día (05:17, 13:17 y 21:17, hora de Chile; GitHub puede atrasarlas unas horas) y guarda los precios nuevos en el repositorio.

## Cómo funciona

1. `stores.json` lista las tiendas. Cada una tiene `platform`: `shopify`, `woocommerce` o `auto`.
2. `scraper/platforms.py` lee el catálogo de cada tienda:
   - **Shopify:** `/products.json` (público en casi todas las tiendas Shopify).
   - **WooCommerce:** la Store API pública (`/wp-json/wc/store/v1/products`).
   - **Genérico:** recorre el `sitemap.xml` y lee los datos de producto (JSON-LD / Open Graph) de cada página. Sirve para Jumpseller, Bsale y sitios a medida.
3. `scraper/classify.py` descarta lo que no es figura (peluches, mangas, llaveros…) y detecta la línea (Nendoroid, figma, Pop Up Parade, Banpresto, Ichiban Kuji…).
4. `scraper/match.py` junta la misma figura de distintas tiendas: primero por código de barras (JAN) o número de catálogo (Nendoroid 2205), luego por similitud del nombre dentro de la misma línea.
5. `scraper/main.py` escribe los datos y el historial de precios. Si una tienda falla, se siguen mostrando sus últimos precios por 3 días.

El scraper respeta `robots.txt`, se identifica con su propio User-Agent y espera 1 segundo entre pedidos a una misma tienda. Solo guarda nombre, precio, disponibilidad, link y la URL de la imagen.

## Corregir errores a mano (`ajustes.json`)

Si el agrupador se equivoca, se corrige en `ajustes.json` usando el link de la tienda de cada producto:

```json
{
  "excluir": ["https://irion.cl/products/figura-batman"],
  "unir": [["https://kinuestore.cl/products/vegeto", "https://irion.cl/products/vegetto-grandista"]],
  "separar": [["https://burubox.cl/p/vegeto-otra", "https://kinuestore.cl/products/vegeto"]],
  "nombres": {"https://irion.cl/products/vegetto-grandista": "Vegetto Grandista (Resolution of Soldiers)"},
  "alternativa": [], "original": [], "adulto": [], "no_adulto": []
}
```

Al guardar el archivo en GitHub, el sitio se rearma solo en ~1 minuto con los últimos precios (sin volver a leer las tiendas).
En la ficha de cada figura del sitio hay un link **Reportar error** que abre un issue con los links ya listos para copiar.

## Agregar una tienda

Agrega una línea a `stores.json`:

```json
{"id": "mitienda", "name": "Mi Tienda", "url": "https://mitienda.cl", "platform": "auto", "location": "Providencia"}
```

Usa `"strict": true` en tiendas que venden de todo (Star Wars, Marvel, modelismo) para quedarse solo con figuras de anime.

Para probar solo esa tienda: en GitHub → Actions → *Actualizar precios* → *Run workflow* y escribe su id.

## Correr en tu computador

```bash
pip install -r requirements.txt
python -m scraper.main --stores irion,richirocko   # o sin --stores para todas
python -m http.server -d docs 8000                  # abre http://localhost:8000
python -m pytest -q
```
