"""Lectores de catálogo por plataforma.

Cada lector devuelve una lista de ofertas con este formato:
    {title, price, regular_price, url, image, in_stock, preorder, barcode, sku, brand, kind}
`price` y `regular_price` son enteros en CLP.
"""
import html
import json
import re
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
            avail = [v for v in variants if v.get("available", True)]
            v = min(avail or variants, key=lambda x: _int_price(x.get("price")) or 10**12)
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
    roots = []
    r = client.get("/robots.txt")
    if r is not None:
        roots += re.findall(r"(?im)^\s*sitemap:\s*(\S+)", r.text)
    roots += [client.base + "/sitemap.xml", client.base + "/sitemap_index.xml"]
    seen, product_urls, other_urls = set(), [], []

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
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        children = [e.text.strip() for e in root.findall("s:sitemap/s:loc", ns) if e.text]
        if children:
            prod = [c for c in children if "product" in c.lower() or "producto" in c.lower()]
            for c in (prod or children):
                parse(c, depth + 1, product_hint=bool(prod))
            return
        locs = [e.text.strip() for e in root.findall("s:url/s:loc", ns) if e.text]
        (product_urls if product_hint or "product" in url.lower() else other_urls).extend(locs)

    for u in dict.fromkeys(roots):
        parse(u)
        if product_urls or other_urls:
            break
    urls = product_urls or [u for u in other_urls if not SKIP_URL.search(u)
                            and u.rstrip("/") != client.base]
    return list(dict.fromkeys(urls))[:MAX_GENERIC_PAGES]


def _iter_ld(obj):
    if isinstance(obj, list):
        for x in obj:
            yield from _iter_ld(x)
    elif isinstance(obj, dict):
        if "@graph" in obj:
            yield from _iter_ld(obj["@graph"])
        yield obj


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
    elif soup.find(attrs={"itemprop": "price"}):
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
    }


def generic(client):
    out = []
    for url in _sitemap_urls(client):
        r = client.get(url)
        if r is None or "html" not in r.headers.get("content-type", "html"):
            continue
        item = parse_product_page(r.text, url)
        if item:
            out.append(item)
    return out


# ---------------------------------------------------------------- utilidades
PREORDER_RE = re.compile(r"pre[\s-]?venta|preorder|pre[\s-]?order|reserva|por encargo|encargo", re.I)


def _looks_preorder(title, extra):
    return bool(PREORDER_RE.search(" ".join([title or ""] + [str(x) for x in extra])))


def detect_and_scrape(client, platform="auto", diag=None):
    """Devuelve (plataforma_usada, ofertas). Si se pasa `diag` (lista), anota cada intento."""
    order = {"shopify": [shopify], "woocommerce": [woocommerce], "generic": [generic]}.get(
        platform, [shopify, woocommerce, generic])
    if platform in ("shopify", "woocommerce"):
        order = order + [generic]          # si la API está cerrada, intenta por sitemap
    for fn in order:
        before = dict(client.errors)
        try:
            items = fn(client)
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
