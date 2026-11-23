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


def shard_of(pid):
    return int(fnv(pid), 16) % SHARDS


def _norm(s):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9/ ]+", " ", s)).strip()


LIST_KEYS = ("id", "name", "line", "min_price", "image", "stores", "in_stock")
OPTIONAL = ("imgs", "adult", "alternative", "alt_unknown", "drop", "back", "first_seen", "num", "barcode",
            "original_id", "alternatives")


def write_site_files(data_dir, updated, products):
    data_dir.mkdir(parents=True, exist_ok=True)
    lst, shards = [], [dict() for _ in range(SHARDS)]
    for p in products:
        d = {k: p[k] for k in LIST_KEYS}
        d.update({k: p[k] for k in OPTIONAL if p.get(k)})
        name = set(_norm(p["name"]).split())
        extra = []
        for o in p["offers"]:     # palabras de los títulos de cada tienda, para que la búsqueda las encuentre
            for w in _norm(o["title"]).split():
                if w not in name and w not in extra:
                    extra.append(w)
        d["q"] = " ".join(extra)
        d["st"] = sorted({o["store"] for o in p["offers"]})
        d["u"] = [fnv(url_key(o["url"])) for o in p["offers"]]   # para reconocer la lista de deseos
        regs = [o.get("regular_price") or o["price"] for o in p["offers"] if o["in_stock"]]
        if regs:
            d["reg"] = max(regs)
        if all(o.get("preorder") for o in p["offers"]):
            d["pre"] = 1
        lst.append(d)
        shards[shard_of(p["id"])][p["id"]] = p["offers"]
    dump = lambda obj: json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    (data_dir / "list.json").write_text(dump({"updated": updated, "lines": LINE_NAMES, "products": lst}), encoding="utf-8")
    odir = data_dir / "o"
    odir.mkdir(exist_ok=True)
    for i, sh in enumerate(shards):
        (odir / f"{i:02d}.json").write_text(dump(sh), encoding="utf-8")
