"""Junta el texto de las páginas de despacho de cada tienda (para revisarlo a mano y llenar "envio" en stores.json).

Uso: python -m tools.envios_texto [ids...]   → escribe envios/<id>.txt
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scraper.http import Client

OUT = Path("envios")
KEY = re.compile(r"env[ií]o|despacho|shipping|entrega|retiro|starken|chilexpress|blue ?express|courier", re.I)
TRY = ["/policies/shipping-policy", "/pages/envios", "/pages/despachos", "/pages/envios-y-despachos",
       "/pages/preguntas-frecuentes", "/envios", "/despachos", "/politicas-de-envio", "/politica-de-envios",
       "/preguntas-frecuentes", "/faq", "/terminos-y-condiciones"]


def text_of(html):
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "noscript", "svg", "header", "nav"]):
        t.decompose()
    lines = [re.sub(r"\s+", " ", x).strip() for x in soup.get_text("\n").split("\n")]
    return [x for x in lines if x]


def relevant(lines):
    keep = set()
    for i, x in enumerate(lines):
        if KEY.search(x) or ("$" in x and re.search(r"gratis|despacho|env", " ".join(lines[max(0, i-2):i+3]), re.I)):
            keep.update(range(max(0, i - 1), min(len(lines), i + 3)))
    return [lines[i] for i in sorted(keep)]


def store(st):
    c = Client(st["url"], delay=0.8)
    out, seen = [], set()
    home = c.get("/")
    links = []
    if home is not None:
        soup = BeautifulSoup(home.text, "lxml")
        for a in soup.find_all("a", href=True):
            h, t = a["href"], a.get_text(" ", strip=True)
            if KEY.search(h) or KEY.search(t):
                u = urljoin(st["url"] + "/", h)
                if urlparse(u).netloc == urlparse(st["url"]).netloc and "/product" not in u and "/collections/" not in u:
                    links.append(u.split("#")[0])
        hl = relevant(text_of(home.text))
        if hl:
            out.append("== INICIO ==\n" + "\n".join(hl[:60]))
    for u in list(dict.fromkeys(links))[:6] + TRY:
        full = urljoin(st["url"] + "/", u)
        if full in seen or len(out) > 8:
            continue
        seen.add(full)
        r = c.get(full, retries=0)
        if r is None or not r.text:
            continue
        rel = relevant(text_of(r.text))
        if rel:
            out.append(f"== {full} ==\n" + "\n".join(rel[:120]))
    (OUT / f"{st['id']}.txt").write_text("\n\n".join(out) or "(sin texto de despacho encontrado)", encoding="utf-8")
    print(st["id"], len(out), "páginas", c.errors or "", flush=True)


def main():
    OUT.mkdir(exist_ok=True)
    stores = json.load(open("stores.json"))
    meta = json.load(open(sys.argv[sys.argv.index("--meta") + 1])) if "--meta" in sys.argv else None
    ok = {s["id"] for s in meta["stores"] if s["status"] == "ok"} if meta else None
    ids = [a for a in sys.argv[1:] if not a.startswith("--") and not a.endswith(".json")]
    for st in stores:
        if (ids and st["id"] not in ids) or (ok is not None and st["id"] not in ok):
            continue
        try:
            store(st)
        except Exception as e:      # una tienda que falla no corta el resto
            print(st["id"], "ERROR", e)


if __name__ == "__main__":
    main()
