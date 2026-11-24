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
        off("x", "Nami Grandline Lady Egghead", 10000, barcode="4580590126947"),
        off("y", "Figura One Piece Nami Grandline Lady Egghead Ver.", 11000, barcode="4580590126947"),
        off("z", "Sanji Film Red DXF", 12000, barcode="4580590126947"),      # mismo código, otra figura
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
    assert prods["jan-4580590126947"]["stores"] == 2          # el Sanji con el mismo código no se une
    assert len(prods) == len({p["id"] for p in prods.values()})


def test_jsonld_page():
    html = """<html><head><script type="application/ld+json">
    {"@context":"https://schema.org","@graph":[{"@type":"WebPage"},{"@type":"Product","name":"POP UP PARADE Machi",
     "image":["https://x/machi.jpg"],"gtin13":"4580590123456","brand":{"@type":"Brand","name":"Good Smile"},
     "offers":{"@type":"Offer","price":"64990","priceCurrency":"CLP","availability":"https://schema.org/PreOrder"}}]}
    </script></head><body></body></html>"""
    p = parse_product_page(html, "https://tienda/machi")
    assert p["price"] == 64990 and p["preorder"] and p["in_stock"]
    assert p["barcode"] == "4580590123456" and p["image"] == "https://x/machi.jpg"


def test_microdata_page():
    html = """<html><head><meta property="og:title" content="X"></head><body><div itemscope itemtype="https://schema.org/Product">
    <h1 itemprop="name">Funko Pop Animation Hunter x Hunter Gon Freecss 2088</h1>
    <img itemprop="image" src="https://x/gon.jpg"><span itemprop="price" content="14990">$14.990</span>
    <link itemprop="availability" href="https://schema.org/InStock"></div></body></html>"""
    p = parse_product_page(html, "https://holygeek/gon")
    assert p["price"] == 14990 and p["in_stock"] and p["title"].startswith("Funko Pop")
    assert p["image"] == "https://x/gon.jpg"


def test_adult():
    from scraper.classify import is_adult
    assert is_adult("Obsidia Bunny 1/4", "Figuras Ecchi (+18) Figuras Estáticas Preventa")
    assert is_adult("Mauve 1/6", "", "Rocket Boy / Native")
    assert not is_adult("Nendoroid Frieren 2367", "Nendoroid")
    assert not is_adult("Figura Alternative Ver. Miku", "Figuras")
    assert not is_adult("Figura Tsuyu Asui Frog Form My Hero Academia", "Figuras")


def test_alternatives():
    from scraper.classify import is_alternative
    assert is_alternative("Boa Hancock - Flag Diamond Ship", "Excelente Figura de Boa Hancock Versión alternativa Nuevo") is True
    assert is_alternative("Figura Banpresto Nami", "Figura 100% original") is False
    assert is_alternative("Figura Banpresto Nami", "") is None
    offers = [
        off("kinue", "One Piece - Luffy - King of the Artist 20th Anniversary (Banpresto)", 32990),
        off("anezaki", "Luffy King of the Artist 20th Anniversary Ver - Banpresto", 34990),
        off("figurasonline", "Monkey D Luffy - King of the Artist - 20th Anniversary Ver Banpresto", 14990, alternative=True),
    ]
    prods = group(offers)
    orig = [p for p in prods if not p["alternative"]]
    alts = [p for p in prods if p["alternative"]]
    assert len(orig) == 1 and orig[0]["min_price"] == 32990 and orig[0]["stores"] == 2
    assert len(alts) == 1 and alts[0]["original_id"] == orig[0]["id"]
    assert orig[0]["alternatives"][0]["min_price"] == 14990


def test_shopify_deposit_variants():
    from scraper.platforms import shopify

    class C:
        base = "https://x"
        opts = {}
        def get(self, path, params=None, expect_json=False):
            if params["page"] > 1:
                return {"products": []}
            return {"products": [{"title": "Levi Ichiban Kuji B Prize", "handle": "levi", "tags": [], "images": [],
                     "variants": [{"title": "Reserva 50%", "price": "42495.00", "available": True},
                                  {"title": "Pago total", "price": "84990.00", "available": True}]},
                    {"title": "Luffy DXF", "handle": "luffy", "tags": [], "images": [],
                     "variants": [{"title": "Default Title", "price": "19995.00", "compare_at_price": "39990.00", "available": True},
                                  {"title": "Default Title", "price": "39990.00", "available": True}]}]}
    c = C()
    items = {i["title"]: i["price"] for i in shopify(c)}
    assert items["Levi Ichiban Kuji B Prize"] == 84990
    c.opts = {"max_price": True}
    items = {i["title"]: i["price"] for i in shopify(c)}
    assert items["Luffy DXF"] == 39990


def test_manual_rules():
    a = off("kinue", "Figura Vegeto Grandista Resolution of Soldiers", 39990, url="https://kinuestore.cl/products/vegeto")
    b = off("irion", "VEGETTO GRANDISTA RESOLUTION OF SOLDIERS", 41990, url="https://irion.cl/products/vegetto-grandista")
    c = off("anezaki", "Figura Vegeto Grandista Resolution of Soldiers", 38990, url="https://anezakistore.cl/products/vegeto?v=1")
    d = off("burubox", "Figura Vegeto Grandista Resolution of Soldiers", 37990, url="https://burubox.cl/p/vegeto-otra")
    rules = {"unir": [["https://www.kinuestore.cl/products/vegeto/", "irion.cl/products/vegetto-grandista"]],
             "separar": [["https://burubox.cl/p/vegeto-otra", "https://kinuestore.cl/products/vegeto"]],
             "nombres": {"https://irion.cl/products/vegetto-grandista": "Vegetto Grandista (Resolution of Soldiers)"}}
    prods = group([a, b, c, d], rules)
    main = [p for p in prods if p["name"] == "Vegetto Grandista (Resolution of Soldiers)"]
    assert len(main) == 1 and main[0]["stores"] == 3            # kinue + irion (manual) + anezaki (automático)
    assert any(p["stores"] == 1 and p["offers"][0]["store"] == "burubox" for p in prods)   # separada


def test_non_anime():
    from scraper.classify import is_figure
    assert not is_figure("Figura Blokees Transformers Optimus Prime model kit")
    assert not is_figure("Spider-Man 2099 (Comic Ver.) MAFEX")
    assert is_figure("Funko Pop Marvel x Naruto anime crossover figura")  # nombra una serie anime
    assert is_figure("BEASTARS - Legoshi - POP UP PARADE")


def test_reused_barcode_in_store():
    a = off("friitoys", "Figura Sanji Film Red WCF", 9990, barcode="4983164290813")
    b = off("friitoys", "Figura Woop Slap WCF One Piece", 9990, barcode="4983164290813")
    c = off("animestore", "One Piece The Shukko Monkey D Luffy", 29990, barcode="4983164290813")
    prods = group([a, b, c])
    assert len(prods) == 3                                     # código repetido en la tienda: se ignora
    assert len({p["id"] for p in prods}) == 3


def test_funko_numbers():
    assert line_number("Funko Pop! Animation: Naruto - Kakashi #1199", "funko") == "1199"
    assert line_number("Funko Pop Dragon Ball Z Goku 10 inch", "funko") is None
    assert line_number("Funko Pop Holiday 2023 Pikachu", "funko") is None


def test_alternative_false_positives():
    from scraper.classify import is_alternative
    assert is_alternative("S.H.Figuarts Super Saiyan Trunks", "Incluye manos alternativas y rostros alternativos.") is not True
    assert is_alternative("Figma Samus Aran", "Réplica exacta del personaje con piezas intercambiables.") is not True
    assert is_alternative("Boa Hancock - Flag Diamond Ship", "Excelente Figura de Boa Hancock Versión alternativa Nuevo") is True
    assert is_alternative("Figura Goku (Réplica)", "") is True
    assert is_figure("Base Soporte Para Hot Toys, Muñecas barbie, Figuras 1/6") is False
    assert is_figure("HG Gundam Aerial Rebuild", "Gunpla", strict=True)


def test_character_swaps_not_merged():
    # en datos reales "naruto", "shippuden", "vibration", "stars" son palabras comunes; los personajes no
    filler = [off(f"s{i}", f"Naruto Shippuden Vibration Stars Personaje{i}", 30000 + i) for i in range(60)]
    a = off("mranime", "Figura Naruto Shippuden Vibration Stars Kakuzu", 34990)
    b = off("kinue", "Naruto Shippuden Kakuzu Vibration Stars Banpresto", 32990)
    c = off("anezaki", "Naruto Shippuden - Sasuke Uchiha (Vibration Stars)", 33990)
    prods = group(filler + [a, b, c])
    kak = [p for p in prods if "kakuzu" in p["name"].lower()]
    assert len(kak) == 1 and kak[0]["stores"] == 2
    assert all(o["store"] != "anezaki" for o in kak[0]["offers"])


def test_same_store_listings_not_merged():
    a = off("figuartschile", "Figura WCF One Piece", 9990, url="https://x.cl/p/1")
    b = off("figuartschile", "Figura WCF One Piece", 9990, url="https://x.cl/p/2")
    assert len(group([a, b])) == 2


def test_clean_deposit_points():
    from scraper.main import clean_deposit_points
    h = [["2026-11-18", 19995], ["2026-11-19", 39990], ["2026-11-25", 41990]]
    clean_deposit_points(h)
    assert h == [["2026-11-19", 39990], ["2026-11-25", 41990]]
    h = [["2026-11-01", 20000], ["2026-11-20", 40000]]  # cambio real, separado en el tiempo
    clean_deposit_points(h)
    assert len(h) == 2


def test_generic_cache_slow_refresh_for_non_figures(monkeypatch):
    import datetime as dt
    from scraper import platforms
    today = dt.date.today()
    old = (today - dt.timedelta(days=8)).isoformat()   # vencido para figuras, vigente para lo demás
    cache = {
        "https://t.cl/manga": {"lastmod": "", "fetched": old, "w": False,
                                "item": {"title": "Manga One Piece 01", "price": 9990}},
        "https://t.cl/fig": {"lastmod": "", "fetched": old, "w": True,
                              "item": {"title": "Figura Nendoroid Frieren", "price": 59990}},
    }
    monkeypatch.setattr(platforms, "_sitemap_urls", lambda c: [(u, "") for u in cache])
    fetched = []

    class C:
        opts = {}
        def out_of_time(self): return False
        def get(self, url, headers=None):
            fetched.append(url); return None
    platforms.generic(C(), cache)
    assert fetched == ["https://t.cl/fig"]


def _grp(titles):
    from scraper.match import group
    offers = [{"title": t, "price": 20000, "regular_price": 20000, "url": f"https://s{i}.cl/p{i}", "store": f"s{i}",
               "image": None, "in_stock": True, "preorder": False, "barcode": None, "line": "banpresto"}
              for i, t in enumerate(titles)]
    # relleno para que las palabras de serie sean comunes y las de personaje no
    for k in range(300):
        offers.append({"title": f"Chainsaw Man Vibration Stars Ranma Dragon Ball Solid Edge Works relleno{k}", "price": 9990,
                       "regular_price": 9990, "url": f"https://x.cl/{k}", "store": "x", "image": None,
                       "in_stock": True, "preorder": False, "barcode": None, "line": "otra"})
    prods = [p for p in group(offers) if p["line"] == "banpresto"]
    return sorted(sorted(o["title"] for o in p["offers"]) for p in prods)


def test_generic_title_not_merged_with_character():
    g = _grp(["Chainsaw Man Vibration Stars", "Chainsaw Man - Power (Vibration Stars)", "CHAINSAW MAN VIBRATION STARS POWER"])
    assert ["Chainsaw Man Vibration Stars"] in g


def test_volume_numbers_roman_and_arabic():
    g = _grp(["Power II Chainsaw Man Vibration Stars", "CHAINSAW MAN VIBRATION STARS POWER 2",
              "Chainsaw Man - Power (Vibration Stars)"])
    assert ["CHAINSAW MAN VIBRATION STARS POWER 2", "Power II Chainsaw Man Vibration Stars"] in g


def test_character_named_like_series():
    g = _grp(["Ranma 1/2 - Ranma (Glitter & Glamours)", "Ranma 1/2 Glitter & Glamours Shampoo"])
    assert len(g) == 2


def test_site_files(tmp_path):
    import json
    from scraper.publish import write_site_files, fnv, url_key, shard_of
    prods = [{"id": "f-1", "name": "Gojo Satoru", "line": "luminasta", "min_price": 20000, "image": None, "stores": 1,
              "in_stock": True, "offers": [{"store": "a", "title": "Jujutsu Kaisen Gojo Satoru Luminasta", "price": 20000,
                                            "regular_price": 25000, "url": "https://www.A.cl/p/gojo/?x=1",
                                            "in_stock": True, "preorder": False}]}]
    write_site_files(tmp_path, "2026-11-23T10:00", prods)
    lst = json.loads((tmp_path / "list.json").read_text())
    p = lst["products"][0]
    assert "offers" not in p and "jujutsu" in p["q"] and p["st"] == ["a"] and p["reg"] == 25000
    assert url_key("https://www.A.cl/p/gojo/?x=1") == "a.cl/p/gojo"
    assert json.loads((tmp_path / "u.json").read_text()) == {fnv("a.cl/p/gojo"): "f-1"}
    assert json.loads((tmp_path / "inicio.json").read_text())["products"][0]["id"] == "f-1"
    shard = json.loads((tmp_path / "o" / f"{shard_of('f-1'):02d}.json").read_text())
    assert shard["f-1"]["o"][0]["price"] == 20000 and shard["f-1"]["h"] == {}
