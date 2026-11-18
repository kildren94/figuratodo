"""Agrupa ofertas de distintas tiendas que corresponden a la misma figura."""
import hashlib
import re
from collections import defaultdict

from rapidfuzz import fuzz

from .classify import tokens, line_number, kuji_prize, LINE_NAMES


class DSU:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            self.p[b] = a


def _nums(toks):
    return {t for t in toks if re.search(r"\d", t)}


def _same(a, b):
    """¿Dos ofertas sin código de barras son la misma figura?"""
    if a["line"] != b["line"]:
        return False
    if a["prize"] != b["prize"]:
        return False
    if _nums(a["toks"]) != _nums(b["toks"]):
        return False
    hi, lo = max(a["price"], b["price"]), min(a["price"], b["price"])
    if lo and hi / lo > 2.5:
        return False
    sa, sb = " ".join(a["toks"]), " ".join(b["toks"])
    if not sa or not sb:
        return False
    sort = fuzz.token_sort_ratio(sa, sb)
    if a["store"] == b["store"]:
        return sort == 100
    if sort >= 90:
        return True
    shared = len(set(a["toks"]) & set(b["toks"]))
    return shared >= 3 and fuzz.token_set_ratio(sa, sb) >= 96


def group(offers):
    for o in offers:
        o["toks"] = tokens(o["title"])
        o["num"] = line_number(o["title"], o["line"])
        o["prize"] = kuji_prize(o["title"]) if o["line"] in ("ichiban-kuji", "masterlise") else None

    n = len(offers)
    dsu = DSU(n)
    strong = {}
    for i, o in enumerate(offers):
        keys = []
        if o.get("barcode"):
            keys.append("b:" + o["barcode"])
        if o["num"]:
            keys.append(f"{o['line']}:{o['num']}")
        for k in keys:
            if k in strong:
                dsu.union(strong[k], i)
            else:
                strong[k] = i

    # índice invertido para comparar sólo candidatos razonables
    df = defaultdict(int)
    for o in offers:
        for t in set(o["toks"]):
            df[t] += 1
    index = defaultdict(list)
    for i, o in enumerate(offers):
        o["_rare"] = sorted(set(o["toks"]), key=lambda t: (df[t], t))[:2]
        for t in set(o["toks"]):
            index[(o["line"], t)].append(i)
    for i, o in enumerate(offers):
        if o["num"]:
            continue  # los numerados ya se agruparon por número
        cands = set()
        for t in o["_rare"]:
            cands.update(index[(o["line"], t)])
        for j in cands:
            if j == i or offers[j]["num"]:
                continue
            if dsu.find(i) != dsu.find(j) and _same(o, offers[j]):
                dsu.union(i, j)

    clusters = defaultdict(list)
    for i in range(n):
        clusters[dsu.find(i)].append(offers[i])
    return [_product(c) for c in clusters.values()]


def _product(offs):
    offs.sort(key=lambda o: (not o["in_stock"], o["price"]))
    barcode = next((o["barcode"] for o in offs if o.get("barcode")), None)
    num = next((o["num"] for o in offs if o["num"]), None)
    line = offs[0]["line"]
    if num:
        pid = f"{line}-{num}"
    elif barcode:
        pid = f"jan-{barcode}"
    else:
        base = line + "|" + " ".join(sorted(set(offs[0]["toks"])))
        pid = "f-" + hashlib.sha1(base.encode()).hexdigest()[:10]
    names = sorted((o["title"] for o in offs), key=lambda t: (len(re.sub(r"\[[^\]]*\]", "", t)), t))
    name = re.sub(r"^\s*\[[^\]]*\]\s*|\s*\[[^\]]*\]\s*$", "", names[len(names) // 2] if len(names) > 2 else names[0]).strip()
    stock = [o for o in offs if o["in_stock"]]
    return {
        "id": pid,
        "name": name,
        "line": line,
        "line_name": LINE_NAMES.get(line, line),
        "num": num,
        "barcode": barcode,
        "image": next((o["image"] for o in offs if o.get("image")), None),
        "min_price": min(o["price"] for o in (stock or offs)),
        "in_stock": bool(stock),
        "adult": any(o.get("adult") for o in offs),
        "stores": len({o["store"] for o in offs}),
        "offers": [{
            "store": o["store"], "title": o["title"], "price": o["price"],
            "regular_price": o["regular_price"], "url": o["url"],
            "in_stock": o["in_stock"], "preorder": o["preorder"], "adult": bool(o.get("adult")),
        } for o in offs],
    }
