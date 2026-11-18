from scraper.classify import is_figure, detect_line, line_number, kuji_prize
from scraper.match import group
from scraper.platforms import parse_product_page, _int_price


def off(store, title, price, **kw):
    o = {"store": store, "title": title, "price": price, "regular_price": price, "url": f"https://{store}/{abs(hash(title))}",
         "image": None, "in_stock": True, "preorder": False, "barcode": None, "sku": None, "brand": None, "kind": ""}
    o.update(kw)
    o["line"] = detect_line(o["title"])
    return o


def test_prices():
    assert _int_price("34.990") == 34990
    assert _int_price("$34.990") == 34990
    assert _int_price("34990.00") == 34990
    assert _int_price("34,990") == 34990
    assert _int_price(34990) == 34990


def test_is_figure():
    assert is_figure("Figura Nendoroid Gojo Satoru 2205")
    assert is_figure("POP UP PARADE Machi")
    assert is_figure("Dragon Ball Z - Vegeto - Grandista (Banpresto)")
    assert not is_figure("Peluche Chopper One Piece 22 cm")
    assert not is_figure("Manga Chainsaw Man Tomo 5")
    assert not is_figure("Llavero Gojo acrílico")
    assert not is_figure("Padmé Amidala The Vintage Collection 3,75\"", strict=True)


def test_lines_and_numbers():
    assert detect_line("S.H.Figuarts Son Goku") == "figuarts"
    assert detect_line("Re:ZERO GLITTER&GLAMOURS Rem") == "glitter-glamours"
    assert line_number("Satoru Gojo Nendoroid 2205 Jujutsu Kaisen", "nendoroid") == "2205"
    assert line_number("FIGURA NENDOROID POWER (RE-RUN) 1580", "nendoroid") == "1580"
    assert line_number("Nendoroid Frieren #2367", "nendoroid") == "2367"
    assert kuji_prize("One Piece - Shanks (Ichiban Kuji, Premio A, Masterlise)") == "a"


def test_grouping():
    offers = [
        off("irion", "FIGURA NENDOROID GOJO SATORU 2205", 49990),
        off("richirocko", "Figura Nendoroid Satoru Gojo Jujutsu Kaisen 2205", 52990),
        off("luffytoys", "[Preventa] Nendoroid 2205 Gojo", 47990, preorder=True),
        off("irion", "FIGURA NENDOROID POWER (RE-RUN) 1580", 45990),
        off("kinue", "Re:ZERO GLITTER&GLAMOURS REM maid ver.", 35000),
        off("zonaanime", "Re:ZERO -Starting Life in Another World- GLITTER&GLAMOURS-REM-maid ver.", 34890),
        off("anezaki", "One Piece - Shanks (Ichiban Kuji, Premio A, Masterlise Expiece) - Nuevo OB", 79990),
        off("kinue", "One Piece - Shanks - Ichiban Kuji (B Prize) Masterlise", 69990),
        off("bydanime", "Dragon ball Z - Vegeto - Grandista (Banpresto)", 39990),
        off("animestore", "Figura Vegeto Grandista Dragon Ball Z", 41990),
        off("burubox", "Figura Banpresto Demon Slayer Yushiro Vol. 21 B", 25990),
        off("otakuverso", "Figura Banpresto Demon Slayer Makomo Vol. 21 A", 25990),
        off("x", "Jan item uno", 10000, barcode="4580590126947"),
        off("y", "Otro nombre totalmente distinto", 11000, barcode="4580590126947"),
    ]
    prods = {p["id"]: p for p in group(offers)}
    import re
    by_name = lambda s: [p for p in prods.values() if re.search(rf"\b{s}\b", p["name"], re.I)]
    assert prods["nendoroid-2205"]["stores"] == 3
    assert prods["nendoroid-2205"]["min_price"] == 47990
    assert prods["nendoroid-1580"]["stores"] == 1
    assert len(by_name("rem")) == 1 and by_name("rem")[0]["stores"] == 2
    assert len(by_name("shanks")) == 2           # premio A y premio B son figuras distintas
    assert len(by_name("vegeto")) == 1 and by_name("vegeto")[0]["stores"] == 2
    assert len([p for p in prods.values() if "21" in p["name"]]) == 2   # Vol. 21 A ≠ Vol. 21 B
    assert prods["jan-4580590126947"]["stores"] == 2


def test_jsonld_page():
    html = """<html><head><script type="application/ld+json">
    {"@context":"https://schema.org","@graph":[{"@type":"WebPage"},{"@type":"Product","name":"POP UP PARADE Machi",
     "image":["https://x/machi.jpg"],"gtin13":"4580590123456","brand":{"@type":"Brand","name":"Good Smile"},
     "offers":{"@type":"Offer","price":"64990","priceCurrency":"CLP","availability":"https://schema.org/PreOrder"}}]}
    </script></head><body></body></html>"""
    p = parse_product_page(html, "https://tienda/machi")
    assert p["price"] == 64990 and p["preorder"] and p["in_stock"]
    assert p["barcode"] == "4580590123456" and p["image"] == "https://x/machi.jpg"
