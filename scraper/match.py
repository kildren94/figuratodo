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
        self.all = {i: [i] for i in range(n)}       # integrantes de cada grupo

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
        self.all[a].extend(self.all.pop(b))
        if mb:
            self.members[a] = ma | mb
            self.members.pop(b, None)

    def group_of(self, a):
        return self.all[self.find(a)]


def _nums(toks):
    return {t for t in toks if re.search(r"\d", t)}


_DF = {}          # frecuencia de cada palabra en la corrida actual (la llena _group)
_CO = {}          # en cuántos productos aparecen juntas dos palabras poco comunes (la llena _group)
_DF_LIMIT = [40]  # palabras más frecuentes que esto son de serie/línea ("dragon", "ball", "saiyan")


def _distinct(ta, tb):
    """True si los nombres tienen palabras propias en conflicto: uno tiene una palabra poco común
    ('kakuzu', 'vegitto') y el otro una propia que no sea de serie ('sasuke', 'goku'). Indica personajes
    o versiones distintas aunque compartan serie y línea."""
    n = _DF_LIMIT[0]
    ok = lambda t: len(t) > 2 and not t.isdigit()
    rare_a = {t for t in ta - tb if ok(t) and _DF.get(t, 0) <= n}
    rare_b = {t for t in tb - ta if ok(t) and _DF.get(t, 0) <= n}
    med_a = {t for t in ta - tb if ok(t) and _DF.get(t, 0) <= 4 * n}
    med_b = {t for t in tb - ta if ok(t) and _DF.get(t, 0) <= 4 * n}

    def conflict(own, other):
        # tolera errores de tipeo o variantes ("kakuzu"/"kakusu", "shoto"/"shouto")
        return any(not any(fuzz.ratio(x, y) >= 86 for y in other) for x in own)
    return bool((rare_a and med_b and conflict(rare_a, med_b)) or (rare_b and med_a and conflict(rare_b, med_a)))


def _generic_vs_specific(ta, tb):
    """True si un nombre solo tiene palabras de serie/línea ("chainsaw man vibration stars") y el otro además
    nombra al personaje o versión ("... power"). El genérico no dice cuál figura es, así que no se une."""
    n = _DF_LIMIT[0]
    own = lambda t: len(t) > 2 and not t.isdigit() and _DF.get(t, 0) <= n
    ga, gb = not any(own(t) for t in ta), not any(own(t) for t in tb)
    return (ga and any(own(t) for t in tb - ta)) or (gb and any(own(t) for t in ta - tb))


_IDENT_DF = 10   # una palabra que aparece en tan pocos productos identifica a la figura ("minami", "meruem")
DB_SERIES = {"z", "gt", "super", "daima", "kai"}


def _subset_specific(ta, tb):
    """Un nombre contenido en otro ("ranma 1/2 ranma glitter glamours" ⊂ "... shampoo", "cooler" ⊂ "metal cooler")
    solo es la misma figura si lo que le sobra al largo son palabras comunes (serie, marca), o si el corto ya
    tiene una palabra que identifica a la figura por sí sola."""
    small, big = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if not small < big:
        return False
    n = _DF_LIMIT[0]
    ok = lambda t: len(t) > 2 and not t.isdigit()
    rarest = min((_DF.get(t, 0) for t in small if ok(t)), default=10 ** 9)
    if rarest <= _IDENT_DF:
        return False

    def attached(t):
        # palabras que casi siempre van con otra del nombre corto: "nico" con "robin", "law" con "trafalgar"
        # o al revés: la palabra del nombre corto casi siempre viene con la extra ("guts" con "berserk")
        return any(_CO.get((min(t, u), max(t, u)), 0) >= 0.6 * _DF.get(t, 1) or
                   _CO.get((min(t, u), max(t, u)), 0) >= 0.7 * _DF.get(u, 1) for u in small if ok(u))
    return any(ok(t) and _DF.get(t, 0) <= n and not attached(t) for t in big - small)


def _repeated_name(la, lb):
    """"Ranma 1/2 - Ranma" o "Chainsaw Man - Chainsaw Man": el personaje se llama como la serie. Si el otro nombre
    menciona la serie una sola vez y agrega otro personaje ("Ranma 1/2 - Shampoo"), son figuras distintas."""
    for x, y in ((la, lb), (lb, la)):
        dup = {t for t in set(x) if len(t) > 2 and x.count(t) >= 2}
        for t in dup:
            if y.count(t) == 1 and any(len(u) > 2 and not u.isdigit() and u not in x for u in y):
                return True
    return False


def _series_variant(ta, tb):
    """Dragon Ball Z / GT / Super / Daima: si ambos nombres dicen la serie y no coinciden, son figuras distintas."""
    sa, sb = ta & DB_SERIES, tb & DB_SERIES
    return bool(sa and sb and sa != sb and {"dragon", "ball"} <= ta and {"dragon", "ball"} <= tb)


def _conflict(ta, tb):
    return _distinct(ta, tb) or _generic_vs_specific(ta, tb) or _subset_specific(ta, tb) or _series_variant(ta, tb)


def _fits(dsu, offers, i, j):
    """Para unir dos grupos por parecido de nombre, ninguna pareja entre ellos puede tener
    palabras propias en conflicto (evita cadenas: A≈B, B≈C pero A≠C)."""
    gi, gj = dsu.group_of(i), dsu.group_of(j)
    if len(gi) * len(gj) > 400:      # grupos grandes: se revisa una muestra
        gi, gj = gi[:20], gj[:20]
    for x in gi:
        tx = set(offers[x]["toks"])
        for y in gj:
            if _conflict(tx, set(offers[y]["toks"])) or _repeated_name(offers[x]["toks"], offers[y]["toks"]):
                return False
    return True


def _compatible(a, b, numbered=False):
    """Para uniones por código de barras o número de catálogo: los nombres deben parecerse algo."""
    if a.get("prize") != b.get("prize"):
        return False
    sa, sb = " ".join(a["toks"]), " ".join(b["toks"])
    if not sa or not sb:
        return True
    if numbered:      # Nendoroid 2205 / figma 567: el número manda, basta un parecido bajo
        return fuzz.token_set_ratio(sa, sb) >= 50
    if _distinct(set(a["toks"]), set(b["toks"])):
        return False
    # código de barras: las tiendas a veces copian el de otra figura, así que el nombre debe parecerse de verdad
    return fuzz.token_set_ratio(sa, sb) >= 80 and fuzz.token_sort_ratio(sa, sb) >= 55


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
    if _conflict(set(a["toks"]), set(b["toks"])) or _repeated_name(a["toks"], b["toks"]):
        return False
    if a["store"] == b["store"]:
        return False      # dos publicaciones distintas de una misma tienda son productos distintos
    sort = fuzz.token_sort_ratio(sa, sb)
    if sort >= 90:
        return True
    ta, tb = set(a["toks"]), set(b["toks"])
    shared = len(ta & tb)
    # un nombre contenido en otro ("luffy gear 5" ⊂ "luffy gear 5 extra battle") no basta si al otro le sobra mucho
    small = min(len(ta), len(tb))
    if small < 4 or small / max(len(ta), len(tb)) < 0.5:
        return False      # títulos genéricos ("figura wcf one piece") no sirven de puente
    return shared >= 4 and fuzz.token_set_ratio(sa, sb) >= 96


def _group(offers, rules=None):
    rules = rules or {}
    for o in offers:
        o["toks"] = tokens(o["title"])
        o["num"] = line_number(o["title"], o["line"])
        o["prize"] = kuji_prize(o["title"]) if o["line"] in ("ichiban-kuji", "masterlise") else None

    per_store = defaultdict(int)
    for o in offers:
        if o.get("barcode"):
            per_store[(o["store"], o["barcode"])] += 1
    for o in offers:
        b = o.get("barcode")
        if b and (per_store[(o["store"], b)] > 1 or len(set(b)) <= 2):
            o["barcode"] = None   # la tienda usa el mismo código en varios productos: no es confiable

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
    # índice invertido para comparar sólo candidatos razonables
    df = defaultdict(int)
    for o in offers:
        for t in set(o["toks"]):
            df[t] += 1
    _DF.clear()
    _DF.update(df)
    _DF_LIMIT[0] = max(40, int(0.01 * len(offers)))
    co = defaultdict(int)
    lim = 4 * _DF_LIMIT[0]
    for o in offers:
        rare = sorted({t for t in o["toks"] if df[t] <= lim})
        for x in range(len(rare)):
            for y in range(x + 1, len(rare)):
                co[(rare[x], rare[y])] += 1
    _CO.clear()
    _CO.update(co)
    strong = defaultdict(list)
    for i, o in enumerate(offers):
        keys = []
        if o.get("barcode"):
            keys.append("b:" + o["barcode"])
        if o["num"]:
            keys.append(f"{o['line']}:{o['num']}")
        for k in keys:
            numbered = k[0] != "b"
            for j in strong[k]:
                if o["store"] == offers[j]["store"] and not numbered:
                    continue
                if _compatible(o, offers[j], numbered=numbered) and (numbered or _fits(dsu, offers, i, j)):
                    dsu.union(j, i)
                    break
            strong[k].append(i)

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
            if dsu.find(i) != dsu.find(j) and _same(o, offers[j]) and _fits(dsu, offers, i, j):
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
            "regular_price": o["regular_price"], "url": o["url"], "barcode": o.get("barcode"),
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
    seen = set()
    for p in orig + alts:      # dos grupos distintos pueden calcular el mismo id
        base, k = p["id"], 2
        while p["id"] in seen:
            p["id"] = f"{base}-{k}"
            k += 1
        seen.add(p["id"])
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
