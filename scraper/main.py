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
from .classify import is_figure, detect_line
from .match import group

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("FIGURATODO_DATA", ROOT / "docs" / "data"))
STORES = Path(os.environ.get("FIGURATODO_STORES", ROOT / "stores.json"))
CHILE = timezone(timedelta(hours=-3))
STALE_DAYS = 3   # si una tienda falla, se muestran sus últimos precios por este tiempo


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def scrape_store(store):
    t0 = time.time()
    client = Client(store["url"])
    platform, items = detect_and_scrape(client, store.get("platform", "auto"))
    figs = []
    for it in items:
        if not is_figure(it["title"], it.get("kind", ""), strict=store.get("strict", False)):
            continue
        it["store"] = store["id"]
        it["line"] = detect_line(it["title"], it.get("kind", ""))
        figs.append(it)
    return {
        "id": store["id"], "platform": platform, "total": len(items), "figures": figs,
        "requests": client.requests, "seconds": round(time.time() - t0),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stores", help="ids separados por coma (por defecto todas)")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    stores = load(STORES, [])
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
                                                            "barcode": p.get("barcode"), "line": p["line"]})

    now = datetime.now(CHILE)
    today = now.strftime("%Y-%m-%d")
    results = {}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(scrape_store, s): s for s in stores}
        for f in as_completed(futs):
            s = futs[f]
            try:
                r = f.result()
            except Exception as e:
                r = {"id": s["id"], "platform": None, "total": 0, "figures": [], "error": repr(e)}
            results[s["id"]] = r
            print(f"{s['id']:<14} plataforma={r['platform']} productos={r['total']} figuras={len(r['figures'])} "
                  f"pedidos={r.get('requests')} {r.get('seconds')}s {r.get('error', '')}")

    offers, meta_stores = [], []
    for s in load(STORES, []):
        r = results.get(s["id"])
        pm = prev_meta.get(s["id"], {})
        entry = {"id": s["id"], "name": s["name"], "url": s["url"], "location": s.get("location", "")}
        if r and r["figures"]:
            offers += r["figures"]
            entry.update(status="ok", platform=r["platform"], count=len(r["figures"]), last_ok=today)
        else:
            last_ok = pm.get("last_ok")
            keep = last_ok and (now.date() - datetime.strptime(last_ok, "%Y-%m-%d").date()).days <= STALE_DAYS
            old = prev_offers.get(s["id"], []) if keep else []
            offers += old
            entry.update(status="stale" if old else ("error" if r else pm.get("status", "pending")),
                         platform=(r or {}).get("platform") or pm.get("platform"),
                         count=len(old), last_ok=last_ok)
        meta_stores.append(entry)

    products = group(offers)
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
