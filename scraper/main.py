"""Corre todos los scrapers y escribe los datos que usa el sitio (docs/data)."""
import argparse
import os
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .http import Client
from .platforms import detect_and_scrape
from .classify import is_figure, detect_line, is_adult, is_alternative
from .match import group, norm_url

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("FIGURATODO_DATA", ROOT / "docs" / "data"))
STORES = Path(os.environ.get("FIGURATODO_STORES", ROOT / "stores.json"))
CHILE = timezone(timedelta(hours=-3))
STALE_DAYS = 3
STORE_BUDGET = int(os.environ.get("FIGURATODO_STORE_MINUTES", "55")) * 60   # tiempo máximo por tienda
RUN_BUDGET = int(os.environ.get("FIGURATODO_RUN_MINUTES", "95")) * 60       # tiempo máximo de la corrida
RUN_START = time.time()   # si una tienda falla, se muestran sus últimos precios por este tiempo


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


CACHE = ROOT / "cache"


def scrape_store(store):
    t0 = time.time()
    deadline = min(time.time() + STORE_BUDGET, RUN_START + RUN_BUDGET)
    client = Client(store["url"], deadline=deadline)
    client.opts = store
    client.known_platform = store.get("_known_platform")
    diag = []
    cache_file = CACHE / f"{store['id']}.json"
    cache = load(cache_file, {})
    platform, items = detect_and_scrape(client, store.get("platform", "auto"), diag, cache)
    if cache:
        CACHE.mkdir(exist_ok=True)
        cache_file.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    figs, dropped = [], []
    for it in items:
        if not is_figure(it["title"], it.get("kind", ""), strict=store.get("strict", False),
                         all_figures=store.get("all_figures", False)):
            if len(dropped) < 15:
                dropped.append(f'{it["title"]} || {it.get("kind", "")}'[:160])
            continue
        it["store"] = store["id"]
        it["line"] = detect_line(it["title"], it.get("kind", ""))
        it["adult"] = is_adult(it["title"], it.get("kind", ""), it.get("brand") or "")
        alt = is_alternative(it["title"], it.get("desc", ""))
        # en tiendas que mezclan originales y alternativas, lo que no dice nada se trata como alternativa
        it["alternative"] = bool(alt) or (alt is None and store.get("alt_default", False))
        it["alt_unknown"] = alt is None and it["alternative"]
        it.pop("desc", None)
        figs.append(it)
    return {
        "id": store["id"], "platform": platform, "total": len(items), "figures": figs,
        "requests": client.requests, "seconds": round(time.time() - t0),
        "partial": client.out_of_time(),
        "diag": {"intentos": diag, "descartados_ejemplo": dropped if len(figs) < 20 else []},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stores", help="ids separados por coma (por defecto todas)")
    ap.add_argument("--workers", type=int, default=0, help="0 = una hebra por tienda")
    ap.add_argument("--rebuild", action="store_true",
                    help="no lee tiendas: rearma el sitio con los últimos precios (para aplicar ajustes.json)")
    args = ap.parse_args()

    stores = [s for s in load(STORES, []) if s.get("enabled", True)]
    if args.rebuild:
        stores = []
    if args.stores:
        wanted = set(args.stores.split(","))
        stores = [s for s in stores if s["id"] in wanted]

    DATA.mkdir(parents=True, exist_ok=True)
    prev_products = load(DATA / "products.json", {"products": []})["products"]
    prev_meta = {s["id"]: s for s in load(DATA / "meta.json", {"stores": []})["stores"]}
    prev_offers = {}
    for p in prev_products:
        for o in p["offers"]:
            prev_offers.setdefault(o["store"], []).append({**o, "image": p.get("image"),
                                                            "barcode": p.get("barcode"), "line": p["line"],
                                                            "adult": o.get("adult", p.get("adult", False)),
                                                            "alternative": o.get("alternative", False),
                                                            "alt_unknown": o.get("alt_unknown", False)})

    # plataforma detectada la vez anterior; las tiendas lentas (página por página) parten primero
    for s in stores:
        s["_known_platform"] = prev_meta.get(s["id"], {}).get("platform")
    stores.sort(key=lambda s: 0 if s["_known_platform"] in ("generic", None) else 1)
    workers = args.workers or min(len(stores), 48) or 1

    now = datetime.now(CHILE)
    today = now.strftime("%Y-%m-%d")
    results = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(scrape_store, s): s for s in stores}
        for f in as_completed(futs):
            s = futs[f]
            try:
                r = f.result()
            except Exception as e:
                r = {"id": s["id"], "platform": None, "total": 0, "figures": [], "error": repr(e)}
            results[s["id"]] = r
            print(f"{s['id']:<14} plataforma={r['platform']} productos={r['total']} figuras={len(r['figures'])} "
                  f"pedidos={r.get('requests')} {r.get('seconds')}s {'PARCIAL ' if r.get('partial') else ''}"
                  f"{r.get('error', '')}", flush=True)

    offers, meta_stores = [], []
    for s in load(STORES, []):
        if not s.get("enabled", True):
            continue
        r = results.get(s["id"])
        pm = prev_meta.get(s["id"], {})
        entry = {"id": s["id"], "name": s["name"], "url": s["url"], "location": s.get("location", "")}
        if r is None and pm:
            offers += prev_offers.get(s["id"], [])
            meta_stores.append(pm)
            continue
        if r and r.get("diag"):
            entry["diag"] = r["diag"]
        if r and r["figures"]:
            offers += r["figures"]
            entry.update(status="ok", platform=r["platform"], count=len(r["figures"]), last_ok=today,
                         partial=r.get("partial", False))
        else:
            last_ok = pm.get("last_ok")
            keep = last_ok and (now.date() - datetime.strptime(last_ok, "%Y-%m-%d").date()).days <= STALE_DAYS
            old = prev_offers.get(s["id"], []) if keep else []
            offers += old
            entry.update(status="stale" if old else ("error" if r else pm.get("status", "pending")),
                         platform=(r or {}).get("platform") or pm.get("platform"),
                         count=len(old), last_ok=last_ok, total=(r or {}).get("total", 0))
        meta_stores.append(entry)

    # correcciones manuales (ajustes.json)
    rules = load(ROOT / "ajustes.json", {})
    excl = {norm_url(u) for u in rules.get("excluir", [])}
    flags = {k: {norm_url(u) for u in rules.get(k, [])} for k in ("alternativa", "original", "adulto", "no_adulto")}
    kept = []
    for o in offers:
        u = norm_url(o["url"])
        if u in excl:
            continue
        if u in flags["alternativa"]:
            o["alternative"], o["alt_unknown"] = True, False
        if u in flags["original"]:
            o["alternative"], o["alt_unknown"] = False, False
        if u in flags["adulto"]:
            o["adult"] = True
        if u in flags["no_adulto"]:
            o["adult"] = False
        kept.append(o)
    offers = kept
    products = group(offers, rules)
    products.sort(key=lambda p: (-p["stores"], p["name"].lower()))

    # historial por oferta (tienda + url): sólo se guarda cuando el precio cambia
    hist = load(DATA / "history.json", {})
    for p in products:
        for o in p["offers"]:
            key = f"{o['store']}|{o['url']}"
            h = hist.setdefault(key, [])
            if not h or h[-1][1] != o["price"]:
                if h and h[-1][0] == today:
                    h[-1] = [today, o["price"]]
                else:
                    h.append([today, o["price"]])

    # novedades: bajas de precio, vuelta a stock y figuras recién llegadas
    tday = now.date()
    recent = lambda d, days: d and (tday - datetime.strptime(d, "%Y-%m-%d").date()).days <= days
    stock = load(CACHE / "stock.json", {})
    seen_path = CACHE / "first_seen.json"
    first_run = not seen_path.exists()
    seen = load(seen_path, {})
    known_stores = {sid for sid, m in prev_meta.items() if m.get("last_ok")}
    for p in products:
        prev_min, back, first = None, None, None
        for o in p["offers"]:
            key = f"{o['store']}|{o['url']}"
            h = hist.get(key, [])
            # precio anterior si cambió en los últimos 7 días
            before = h[-2][1] if len(h) >= 2 and recent(h[-1][0], 7) else o["price"]
            if o["in_stock"] or not p["in_stock"]:
                prev_min = before if prev_min is None else min(prev_min, before)
            st = stock.get(key)
            if st is None:
                stock[key] = {"s": o["in_stock"], "d": today, "back": False}
            elif st["s"] != o["in_stock"]:
                stock[key] = {"s": o["in_stock"], "d": today, "back": o["in_stock"]}
            st = stock[key]
            if st["s"] and st.get("back") and recent(st["d"], 3):
                back = max(back or st["d"], st["d"])
            if key not in seen:
                # en la primera corrida o con una tienda recién agregada, todo su catálogo no es "nuevo"
                seen[key] = "2000-01-01" if first_run or o["store"] not in known_stores else today
            first = seen[key] if first is None else min(first, seen[key])
        if prev_min and p["min_price"] < prev_min:
            p["drop"] = {"from": prev_min, "pct": round(100 * (1 - p["min_price"] / prev_min))}
        if back:
            p["back"] = back
        if first and first != "2000-01-01":
            p["first_seen"] = first
    CACHE.mkdir(exist_ok=True)
    (CACHE / "stock.json").write_text(json.dumps(stock, separators=(",", ":")), encoding="utf-8")
    seen_path.write_text(json.dumps(seen, separators=(",", ":")), encoding="utf-8")

    (DATA / "products.json").write_text(json.dumps({"updated": now.isoformat(timespec="minutes"),
                                                    "products": products}, ensure_ascii=False, separators=(",", ":")),
                                        encoding="utf-8")
    (DATA / "history.json").write_text(json.dumps(hist, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (DATA / "meta.json").write_text(json.dumps({"updated": now.isoformat(timespec="minutes"), "stores": meta_stores},
                                               ensure_ascii=False, indent=1), encoding="utf-8")
    multi = sum(1 for p in products if p["stores"] > 1)
    print(f"\n{len(offers)} ofertas → {len(products)} figuras ({multi} en más de una tienda)")


if __name__ == "__main__":
    main()
