"""Archivos que descarga el sitio: una lista liviana para buscar y filtrar, y el detalle de cada figura
(sus ofertas) repartido en archivos chicos que se bajan solo al abrirla."""
import json
import re
import unicodedata

from .classify import LINE_NAMES

SHARDS = 64


def fnv(s):
    """FNV-1a de 32 bits en hex; el sitio usa la misma función (fnv en index.html)."""
    h = 0x811C9DC5
    for b in s.encode("utf-8"):
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return format(h, "08x")


def url_key(u):
    """Igual que urlKey en index.html: sin protocolo, www, parámetros ni una barra final; en minúsculas."""
    u = re.sub(r"^https?://(www\.)?", "", str(u or ""), flags=re.I)
    u = re.sub(r"[?#].*$", "", u)
    if u.endswith("/"):
        u = u[:-1]
    return u.lower()


def slim_image(u):
    """Quita el parámetro anti-caché de Shopify (?v=) y Jumpseller (?123): la foto es la misma y la lista pesa menos."""
    if not u:
        return u
    if u.startswith("https://cdn.shopify.com/") or "/cdn/shop/" in u:
        return re.sub(r"\?v=\d+$", "", u)
    if u.startswith("https://cdnx.jumpseller.com/"):
        return re.sub(r"\?\d+$", "", u)
    return u


def default_view(d):
    """Lo que se ve al abrir el sitio sin buscar: originales, sin +18 y con stock (los filtros por defecto)."""
    return not d.get("alternative") and not d.get("adult") and d.get("in_stock")


def shard_of(pid):
    return int(fnv(pid), 16) % SHARDS


def _norm(s):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9/ ]+", " ", s)).strip()


LIST_KEYS = ("id", "name", "line", "min_price", "image", "stores", "in_stock")
OPTIONAL = ("imgs", "adult", "alternative", "alt_unknown", "drop", "back", "first_seen", "num", "barcode",
            "original_id", "alternatives")


def write_site_files(data_dir, updated, products, hist=None):
    """hist: {"tienda|url": [[fecha, precio, stock], ...]}; va junto a las ofertas de cada figura."""
    hist = hist or {}
    data_dir.mkdir(parents=True, exist_ok=True)
    lst, shards, umap = [], [dict() for _ in range(SHARDS)], {}
    for p in products:
        d = {k: p[k] for k in LIST_KEYS}
        d.update({k: p[k] for k in OPTIONAL if p.get(k)})
        d["image"] = slim_image(d.get("image"))
        if d.get("imgs"):
            d["imgs"] = [slim_image(x) for x in d["imgs"]]
        name = set(_norm(p["name"]).split())
        extra = []
        for o in p["offers"]:     # palabras de los títulos de cada tienda, para que la búsqueda las encuentre
            for w in _norm(o["title"]).split():
                if w not in name and w not in extra:
                    extra.append(w)
        d["q"] = " ".join(extra)
        d["st"] = sorted({o["store"] for o in p["offers"]})
        for o in p["offers"]:   # código de cada link → figura, para reubicar listas de deseos si una figura cambia de id
            umap[fnv(url_key(o["url"]))] = p["id"]
        regs = [o.get("regular_price") or o["price"] for o in p["offers"] if o["in_stock"]]
        if regs:
            d["reg"] = max(regs)
        if all(o.get("preorder") for o in p["offers"]):
            d["pre"] = 1
        lst.append(d)
        h = {f'{o["store"]}|{o["url"]}': hist[f'{o["store"]}|{o["url"]}'] for o in p["offers"]
             if f'{o["store"]}|{o["url"]}' in hist}
        shards[shard_of(p["id"])][p["id"]] = {"o": p["offers"], "h": h}
    dump = lambda obj: json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    (data_dir / "list.json").write_text(dump({"updated": updated, "lines": LINE_NAMES, "products": lst}), encoding="utf-8")
    # primeras figuras de la portada, para mostrarlas mientras baja la lista completa
    first = [d for d in lst if default_view(d)]
    (data_dir / "inicio.json").write_text(dump({"updated": updated, "lines": LINE_NAMES, "total": len(first),
                                                "count": len(lst), "products": first[:60]}), encoding="utf-8")
    (data_dir / "u.json").write_text(dump(umap), encoding="utf-8")
    odir = data_dir / "o"
    odir.mkdir(exist_ok=True)
    for i, sh in enumerate(shards):
        (odir / f"{i:02d}.json").write_text(dump(sh), encoding="utf-8")
