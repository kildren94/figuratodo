"""Agrupa ofertas de distintas tiendas que corresponden a la misma figura."""
import hashlib
import re
from collections import defaultdict

from rapidfuzz import fuzz

from .classify import tokens, line_number, kuji_prize, LINE_NAMES


def norm_url(u):
    """URL comparable: sin protocolo, www, parámetros ni barra final."""
    from urllib.parse import urlparse
    p = urlparse((u or "").strip())
    host = p.netloc.lower().removeprefix("www.")
    return f"{host}{p.path.rstrip('/')}".lower()


class DSU:
    def __init__(self, n, forbid=None):
        self.p = list(range(n))
        # forbid: {índice: set(índices con los que nunca debe juntarse)}
        self.forbid = {i: set(v) for i, v in (forbid or {}).items()}
        self.members = {i: {i} for i in self.forbid}

    def find(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a == b:
            return
        ma, mb = self.members.get(a, set()), self.members.get(b, set())
        if any(self.forbid.get(x, set()) & mb for x in ma):
            return   # una regla manual dice que estas ofertas son figuras distintas
        self.p[b] = a
        if mb:
            self.members[a] = ma | mb
            self.members.pop(b, None)


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


def _group(offers, rules=None):
    rules = rules or {}
    for o in offers:
        o["toks"] = tokens(o["title"])
        o["num"] = line_number(o["title"], o["line"])
        o["prize"] = kuji_prize(o["title"]) if o["line"] in ("ichiban-kuji", "masterlise") else None

    n = len(offers)
    pos = defaultdict(list)
    for i, o in enumerate(offers):
        pos[norm_url(o["url"])].append(i)
    forbid = defaultdict(set)
    for grp in rules.get("separar", []):
        idx = [pos[norm_url(u)] for u in grp]
        for a in range(len(idx)):
            for b in range(len(idx)):
                if a != b:
                    for i in idx[a]:
                        forbid[i].update(idx[b])
    dsu = DSU(n, forbid)
    for grp in rules.get("unir", []):     # primero las uniones manuales
        idx = [i for u in grp for i in pos[norm_url(u)]]
        for i in idx[1:]:
            dsu.union(idx[0], i)
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
    names = {norm_url(u): v for u, v in rules.get("nombres", {}).items()}
    prods = []
    for c in clusters.values():
        p = _product(c)
        for o in c:
            if norm_url(o["url"]) in names:
                p["name"] = names[norm_url(o["url"])]
        prods.append(p)
    return prods


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
        "alternative": bool(offs[0].get("alternative")),
        "alt_unknown": all(o.get("alt_unknown") for o in offs),
        "stores": len({o["store"] for o in offs}),
        "offers": [{
            "store": o["store"], "title": o["title"], "price": o["price"],
            "regular_price": o["regular_price"], "url": o["url"],
            "in_stock": o["in_stock"], "preorder": o["preorder"], "adult": bool(o.get("adult")),
            "alternative": bool(o.get("alternative")), "alt_unknown": bool(o.get("alt_unknown")),
        } for o in offs],
    }


def group(offers, rules=None):
    """Agrupa originales y alternativas por separado (una réplica nunca es el 'mejor precio' de una original)
    y enlaza cada alternativa con su figura original cuando se puede identificar."""
    orig = _group([o for o in offers if not o.get("alternative")], rules)
    alts = _group([o for o in offers if o.get("alternative")], rules)
    for p in alts:
        p["id"] = "alt-" + p["id"]
    by_key = {}
    for p in orig:
        if p["num"]:
            by_key[f"{p['line']}:{p['num']}"] = p
        if p["barcode"]:
            by_key["b:" + p["barcode"]] = p
    by_line = defaultdict(list)
    for p in orig:
        for o in p["offers"]:
            by_line[p["line"]].append((p, " ".join(tokens(o["title"]))))

    def score(at, t):
        if _nums(at.split()) != _nums(t.split()):
            return 0
        sort = fuzz.token_sort_ratio(at, t)
        if sort >= 90:
            return sort
        shared = len(set(at.split()) & set(t.split()))
        return 95 if shared >= 3 and fuzz.token_set_ratio(at, t) >= 96 else 0

    for a in alts:
        target = by_key.get(f"{a['line']}:{a['num']}") if a["num"] else None
        target = target or (by_key.get("b:" + a["barcode"]) if a["barcode"] else None)
        if not target:
            at = " ".join(tokens(a["name"]))
            best = max(((score(at, t), p) for p, t in by_line[a["line"]] if t),
                       key=lambda x: x[0], default=(0, None))
            if best[0] >= 90:
                target = best[1]
        if target:
            a["original_id"] = target["id"]
            alt_list = target.setdefault("alternatives", [])
            alt_list.append({"id": a["id"], "min_price": a["min_price"]})
    return orig + alts
