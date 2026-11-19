"""Lectores de catálogo por plataforma.

Cada lector devuelve una lista de ofertas con este formato:
    {title, price, regular_price, url, image, in_stock, preorder, barcode, sku, brand, kind}
`price` y `regular_price` son enteros en CLP.
"""
import html
import json
import re
import zlib
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

MAX_SHOPIFY_PAGES = 60      # 250 productos por página
MAX_WOO_PAGES = 100         # 100 productos por página
MAX_GENERIC_PAGES = 2500    # páginas de producto por tienda


def _int_price(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return int(round(v))
    s = str(v).strip()
    # "34.990", "34,990", "34990.00", "$34.990"
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        return None
    if re.fullmatch(r"\d+[.,]\d{1,2}", s):           # decimales: 34990.00
        return int(round(float(s.replace(",", "."))))
    s = s.replace(".", "").replace(",", "")
    return int(s) if s else None


def _clean(t):
    return re.sub(r"\s+", " ", html.unescape(BeautifulSoup(t or "", "lxml").get_text(" "))).strip()


def _barcode(v):
    if not v:
        return None
    d = re.sub(r"\D", "", str(v))
    return d if 8 <= len(d) <= 14 else None


# ---------------------------------------------------------------- Shopify
def shopify(client):
    out = []
    for page in range(1, MAX_SHOPIFY_PAGES + 1):
        data = client.get("/products.json", params={"limit": 250, "page": page}, expect_json=True)
        if not data or not data.get("products"):
            break
        for p in data["products"]:
            variants = p.get("variants") or []
            if not variants:
                continue
            # variantes de reserva / abono: no son el precio de la figura
            full = [v for v in variants if not DEPOSIT_RE.search(str(v.get("title") or ""))] or variants
            avail = [v for v in full if v.get("available", True)]
            pick = max if getattr(client, "opts", {}).get("max_price") else min
            v = pick(avail or full, key=lambda x: _int_price(x.get("price")) or (0 if pick is max else 10**12))
            price = _int_price(v.get("price"))
            if not price:
                continue
            tags = p.get("tags") or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",")]
            imgs = p.get("images") or []
            title = _clean(p.get("title"))
            out.append({
                "title": title,
                "price": price,
                "regular_price": _int_price(v.get("compare_at_price")) or price,
                "url": f"{client.base}/products/{p.get('handle')}",
                "image": imgs[0].get("src") if imgs else None,
                "in_stock": bool(avail),
                "preorder": _looks_preorder(title, tags),
                "barcode": _barcode(v.get("barcode")),
                "sku": v.get("sku") or None,
                "brand": p.get("vendor") or None,
                "kind": " ".join([p.get("product_type") or ""] + tags),
                "desc": _clean(p.get("body_html"))[:800],
            })
        if len(data["products"]) < 250:
            break
    return out


# ---------------------------------------------------------------- WooCommerce
def woocommerce(client):
    out = []
    for base in ("/wp-json/wc/store/v1/products", "/wp-json/wc/store/products"):
        first = client.get(base, params={"per_page": 100, "page": 1}, expect_json=True)
        if isinstance(first, list):
            break
    else:
        return None
    page, data = 1, first
    try:
        total_pages = int(client.last_headers.get("X-WP-TotalPages") or 0)
    except ValueError:
        total_pages = 0
    while isinstance(data, list) and data:
        for p in data:
            pr = p.get("prices") or {}
            minor = int(pr.get("currency_minor_unit") or 0)
            div = 10 ** minor

            def money(k):
                v = _int_price(pr.get(k)) if pr.get(k) not in (None, "") else None
                return int(round(v / div)) if v is not None else None

            price = money("price")
            rng = pr.get("price_range") or {}
            if getattr(client, "opts", {}).get("max_price") and rng.get("max_amount"):
                price = int(round(_int_price(rng["max_amount"]) / div))   # variantes de abono: precio completo
            if not price:
                continue
            avail = (p.get("stock_availability") or {}).get("class", "")
            cats = " ".join(c.get("name", "") for c in p.get("categories") or [])
            tags = " ".join(t.get("name", "") for t in p.get("tags") or [])
            title = _clean(p.get("name"))
            imgs = p.get("images") or []
            out.append({
                "title": title,
                "price": price,
                "regular_price": money("regular_price") or price,
                "url": p.get("permalink"),
                "image": imgs[0].get("src") if imgs else None,
                "in_stock": bool(p.get("is_in_stock")) or avail == "on-backorder",
                "preorder": avail == "on-backorder" or _looks_preorder(title, [cats, tags]),
                "barcode": _barcode(p.get("sku")) if p.get("sku") and len(re.sub(r"\D", "", p["sku"])) >= 12 else None,
                "sku": p.get("sku") or None,
                "brand": None,
                "kind": f"{cats} {tags}",
                "desc": _clean(p.get("short_description") or p.get("description"))[:800],
            })
        if page >= MAX_WOO_PAGES or (total_pages and page >= total_pages) or (not total_pages and len(data) < 10):
            break
        page += 1
        data = client.get(base, params={"per_page": 100, "page": page}, expect_json=True)
    return out


# ---------------------------------------------------------------- Genérico (sitemap + JSON-LD)
SKIP_URL = re.compile(r"/(blog|blogs|pages?|collections?|categor(y|ia|ias)|categoria-producto|tag|etiqueta|"
                      r"contact|contacto|cart|carro|checkout|account|cuenta|login|search|buscar|marcas?|brands?)(/|$)", re.I)


def _sitemap_urls(client):
    """Devuelve [(url, lastmod)] de productos según el sitemap de la tienda."""
    roots = []
    r = client.get("/robots.txt")
    if r is not None:
        roots += re.findall(r"(?im)^\s*sitemap:\s*(\S+)", r.text)
    roots += [client.base + p for p in ("/sitemap.xml", "/sitemap_index.xml", "/1_index_sitemap.xml",
                                        "/sitemap_products_1.xml", "/product-sitemap.xml")]
    seen, product_urls, other_urls = set(), [], []
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    def parse(url, depth=0, product_hint=False):
        if url in seen or depth > 2 or len(seen) > 40:
            return
        seen.add(url)
        r = client.get(url)
        if r is None:
            return
        try:
            root = ET.fromstring(r.content)
        except ET.ParseError:
            return
        children = [e.text.strip() for e in root.findall("s:sitemap/s:loc", ns) if e.text]
        if children:
            prod = [c for c in children if "product" in c.lower() or "producto" in c.lower()]
            for c in (prod or children):
                parse(c, depth + 1, product_hint=bool(prod))
            return
        locs = []
        for u in root.findall("s:url", ns):
            loc = u.find("s:loc", ns)
            if loc is None or not loc.text:
                continue
            lm = u.find("s:lastmod", ns)
            locs.append((loc.text.strip(), (lm.text or "").strip() if lm is not None else ""))
        (product_urls if product_hint or "product" in url.lower() else other_urls).extend(locs)

    for u in dict.fromkeys(roots):
        parse(u)
        if product_urls or other_urls:
            break
    urls = product_urls or [(u, lm) for u, lm in other_urls if not SKIP_URL.search(u)
                            and u.rstrip("/") != client.base]
    return list(dict.fromkeys(urls))[:MAX_GENERIC_PAGES]


CRAWL_SKIP = re.compile(r"\.(jpe?g|png|gif|webp|svg|pdf|zip|css|js|xml)(\?|$)|/(cart|carrito|checkout|login|"
                        r"account|mi-cuenta|my-account|contact|contacto|wishlist|module/|blog)", re.I)


def _crawl(client, limit=1500):
    """Para tiendas sin sitemap: recorre los links internos desde la portada buscando páginas de producto."""
    from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode
    host = urlparse(client.base).netloc
    queue, seen, out = [client.base + "/"], set(), []
    while queue and len(seen) < limit and not client.out_of_time():
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        r = client.get(url)
        if r is None or "html" not in r.headers.get("content-type", ""):
            continue
        item = parse_product_page(r.text, url)
        if item:
            out.append(item)
            continue   # en una página de producto no hace falta seguir links
        for a in BeautifulSoup(r.text, "lxml").find_all("a", href=True):
            u = urlparse(urljoin(url, a["href"]))
            if u.netloc != host or CRAWL_SKIP.search(u.path):
                continue
            q = [(k, v) for k, v in parse_qsl(u.query) if k in ("page", "p")]   # sólo paginación
            clean = urlunparse((u.scheme, u.netloc, u.path, "", urlencode(q), ""))
            if clean not in seen:
                queue.append(clean)
    return out


def _iter_ld(obj):
    if isinstance(obj, list):
        for x in obj:
            yield from _iter_ld(x)
    elif isinstance(obj, dict):
        if "@graph" in obj:
            yield from _iter_ld(obj["@graph"])
        yield obj


def _page_desc(soup, prod):
    """Descripción del producto: JSON-LD, metadatos o el bloque de descripción de la página."""
    parts = []
    if isinstance(prod, dict) and isinstance(prod.get("description"), str):
        parts.append(prod["description"])
    for sel in ('meta[name="description"]', 'meta[property="og:description"]'):
        m = soup.select_one(sel)
        if m and m.get("content"):
            parts.append(m["content"])
    for el in soup.select('[itemprop="description"], .product-description, #description, .woocommerce-product-details__short-description')[:3]:
        parts.append(el.get_text(" ", strip=True))
    return _clean(" ".join(parts))[:800]


def parse_product_page(html_text, url):
    soup = BeautifulSoup(html_text, "lxml")
    prod = None
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except (ValueError, TypeError):
            continue
        for o in _iter_ld(data):
            t = o.get("@type")
            if t == "Product" or (isinstance(t, list) and "Product" in t):
                prod = o
                break
        if prod:
            break

    def meta(prop):
        m = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
        return m.get("content") if m else None

    if prod:
        offers = prod.get("offers") or {}
        if isinstance(offers, list):
            offers = min(offers, key=lambda o: _int_price(o.get("price") or o.get("lowPrice")) or 10**12, default={})
        price = _int_price(offers.get("price") or offers.get("lowPrice"))
        avail = str(offers.get("availability") or "")
        img = prod.get("image")
        if isinstance(img, list):
            img = img[0] if img else None
        if isinstance(img, dict):
            img = img.get("url")
        brand = prod.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name")
        title = _clean(prod.get("name"))
        barcode = None
        for k in ("gtin13", "gtin", "gtin12", "gtin14", "gtin8", "ean"):
            barcode = barcode or _barcode(prod.get(k) or offers.get(k))
    elif len({(e.get("content") or e.get_text(strip=True)) for e in soup.find_all(attrs={"itemprop": "price"})}) == 1:
        def ip(name, attr="content"):
            el = soup.find(attrs={"itemprop": name})
            if not el:
                return None
            return el.get(attr) or el.get("content") or el.get("href") or el.get("src") or el.get_text(" ", strip=True)
        price = _int_price(ip("price"))
        title = _clean(ip("name") or meta("og:title") or "")
        avail = ip("availability", "href") or meta("product:availability") or ""
        img = ip("image", "src") or meta("og:image")
        brand, barcode = None, _barcode(ip("gtin13") or ip("gtin"))
        prod = {"sku": ip("sku")}
    else:
        price = _int_price(meta("product:price:amount") or meta("og:price:amount"))
        title = _clean(meta("og:title") or (soup.title.string if soup.title else ""))
        avail = meta("product:availability") or ""
        img = meta("og:image")
        brand, barcode = None, None
    if not price or not title:
        return None
    a = avail.lower()
    return {
        "title": title,
        "price": price,
        "regular_price": price,
        "url": url,
        "image": img,
        "in_stock": not ("outofstock" in a or "soldout" in a or "out of stock" in a or "discontinued" in a),
        "preorder": "preorder" in a or "backorder" in a or _looks_preorder(title, []),
        "barcode": barcode,
        "sku": (prod or {}).get("sku"),
        "brand": brand,
        "kind": " ".join(c.get_text(" ") for c in soup.select(".breadcrumb a, nav.breadcrumb a")[:6]),
        "desc": _page_desc(soup, prod),
    }


REFRESH_DAYS = 4   # aunque el sitemap no indique cambios, cada producto se vuelve a leer cada tantos días


def generic(client, cache=None):
    """Lee productos desde el sitemap. Con `cache` ({url: {lastmod, fetched, item}}) solo abre las páginas
    nuevas, las que cambiaron según el sitemap o las que no se leen hace REFRESH_DAYS días."""
    import datetime as _dt
    today = _dt.date.today()
    cache = cache if cache is not None else {}
    entries = _sitemap_urls(client)
    if not entries:
        return _crawl(client)
    out, fresh = [], {}
    entries.sort(key=lambda e: e[0] in cache)   # primero las nunca leídas
    for url, lastmod in entries:
        c = cache.get(url)
        if c:
            age = (today - _dt.date.fromisoformat(c["fetched"])).days
            # el desfase por url reparte las relecturas entre días distintos
            stale = age >= REFRESH_DAYS + (zlib.crc32(url.encode()) % 3)
            if c.get("lastmod") == lastmod and lastmod and not stale:
                fresh[url] = c
                if c.get("item"):
                    out.append(c["item"])
                continue
            if not lastmod and not stale:
                fresh[url] = c
                if c.get("item"):
                    out.append(c["item"])
                continue
        if client.out_of_time():
            if c:
                fresh[url] = c
                if c.get("item"):
                    out.append(c["item"])
            continue
        cond = {}
        if c and c.get("etag"):
            cond["If-None-Match"] = c["etag"]
        if c and c.get("lastmodh"):
            cond["If-Modified-Since"] = c["lastmodh"]
        r = client.get(url, headers=cond or None)
        if r is not None and r.status_code == 304 and c:
            c = {**c, "fetched": today.isoformat(), "lastmod": lastmod}
            fresh[url] = c
            if c.get("item"):
                out.append(c["item"])
            continue
        if r is None or "html" not in r.headers.get("content-type", "html"):
            if c:
                fresh[url] = c
                if c.get("item"):
                    out.append(c["item"])
            continue
        item = parse_product_page(r.text, url)
        fresh[url] = {"lastmod": lastmod, "fetched": today.isoformat(), "item": item,
                      "etag": r.headers.get("ETag"), "lastmodh": r.headers.get("Last-Modified")}
        if item:
            out.append(item)
    cache.clear()
    cache.update(fresh)
    return out


# ---------------------------------------------------------------- utilidades
DEPOSIT_RE = re.compile(r"reserva|abono|anticipo|se[ñn]a\b|\bpie\b|pago parcial|\b50 ?%|primer pago|dep[oó]sito", re.I)
PREORDER_RE = re.compile(r"pre[\s-]?venta|preorder|pre[\s-]?order|reserva|por encargo|encargo", re.I)


def _looks_preorder(title, extra):
    return bool(PREORDER_RE.search(" ".join([title or ""] + [str(x) for x in extra])))


def detect_and_scrape(client, platform="auto", diag=None, cache=None):
    """Devuelve (plataforma_usada, ofertas). Si se pasa `diag` (lista), anota cada intento."""
    known = getattr(client, "known_platform", None)
    fns = {"shopify": shopify, "woocommerce": woocommerce, "generic": generic}
    order = {"shopify": [shopify], "woocommerce": [woocommerce], "generic": [generic]}.get(
        platform, [shopify, woocommerce, generic])
    if platform == "auto" and known in fns:      # la que funcionó la vez anterior va primero
        order = [fns[known]] + [f for f in order if f is not fns[known]]
    if platform in ("shopify", "woocommerce"):
        order = order + [generic]          # si la API está cerrada, intenta por sitemap
    for fn in order:
        before = dict(client.errors)
        try:
            items = fn(client, cache) if fn is generic else fn(client)
            err = None
        except Exception as e:  # una tienda rota no debe botar la corrida
            print(f"  {client.host}: {fn.__name__} falló: {e!r}")
            items, err = None, repr(e)[:200]
        if diag is not None:
            new = {k: v - before.get(k, 0) for k, v in client.errors.items() if v - before.get(k, 0)}
            diag.append({"intento": fn.__name__, "productos": len(items or []), "errores": new, "excepcion": err})
        if items:
            return fn.__name__, items
    return None, []
