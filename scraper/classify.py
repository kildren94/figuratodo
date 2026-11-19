"""Decide si un producto es una figura, detecta su línea y normaliza el nombre."""
import re
import unicodedata


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm(s):
    s = strip_accents((s or "").lower())
    s = s.replace("&", " and ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9/ ]+", " ", s)).strip()


# (id de línea, nombre visible, regex sobre texto normalizado)
LINES = [
    ("nendoroid-doll", "Nendoroid Doll", r"\bnendoroid doll\b"),
    ("nendoroid", "Nendoroid", r"\bnendoroid\b"),
    ("figma", "figma", r"\bfigma\b"),
    ("pop-up-parade", "Pop Up Parade", r"\bpop ?up ?parade\b"),
    ("figuarts", "S.H.Figuarts", r"\bs ?h ?figuarts\b|\bfiguarts zero\b|\bfiguarts\b"),
    ("ichiban-kuji", "Ichiban Kuji", r"\bichiban ?kuji\b|\bichibansho\b"),
    ("grandista", "Grandista", r"\bgrandista\b"),
    ("masterlise", "Masterlise", r"\bmasterlise\b"),
    ("glitter-glamours", "Glitter & Glamours", r"\bglitter and glamou?rs?\b"),
    ("qposket", "Q Posket", r"\bq ?posket\b"),
    ("vibration-stars", "Vibration Stars", r"\bvibration stars\b"),
    ("banpresto", "Banpresto", r"\bbanpresto\b|\bdxf\b|\bsolid edge works\b|\bmaximatic\b|\bespresto\b|\bhistory box\b|\bblood of saiyans\b|\bthe amazing heroes\b|\bbanpresto chronicle\b"),
    ("sega", "SEGA", r"\bluminasta\b|\bsega\b|\bdesktop x decorate\b|\bpremium perching\b|\bspm\b|\bfigurizm\b"),
    ("taito", "Taito", r"\btaito\b|\bcoreful\b|\baqua float girls\b"),
    ("furyu", "FuRyu", r"\bfuryu\b|\btrio try it\b|\bbicute bunnies\b|\bnoodle stopper\b|\btenitol\b"),
    ("kotobukiya", "Kotobukiya", r"\bkotobukiya\b|\bartfx\b|\bbishoujo\b"),
    ("revoltech", "Revoltech", r"\brevoltech\b"),
    ("funko", "Funko Pop", r"\bfunko\b"),
    ("scale", "Escala", r"\b1/(4|5|6|7|8|10)\b|\bscale figure\b|\bescala\b"),
    ("gunpla", "Gunpla / Model kit", r"\bgunpla\b|\bmaster grade\b|\bhigh grade\b|\breal grade\b|\bperfect grade\b|\bentry grade\b|"
               r"\b(mg|hg|rg|pg) 1/\d+|\b(hg|hguc|rg|mg|mgex|pg|sd|sdcs|eg)\b.*\bgundam\b|\bfigure ?rise\b|\bmodel kit\b|\b30mm\b|\b30ms\b"),
]
LINES_RE = [(i, n, re.compile(r)) for i, n, r in LINES]
LINE_NAMES = {i: n for i, n, _ in LINES}
LINE_NAMES["otra"] = "Otra"

FIGURE_WORDS = re.compile(
    r"\bfigur[ae]s?\b|\bfigure\b|\bestatu[ai]|\bstatue\b|\bfigurine\b|\bcoleccionable\b|\baction figure\b|\bchibi\b|"
    + "|".join(r for _, _, r in LINES))
EXCLUDE = re.compile(
    r"\bpeluche|\bplush|\bmanga\b|\btomo\b|\bvol(umen)? \d+ manga|\bposter|\bllavero|\bkeychain|\bpolera|\bpoleron|"
    r"\bcamiseta|\bcalcet|\bpin(es)?\b|\bchapita|\bcarta(s)?\b|\btcg\b|\bbooster|\bsobre\b|\bmazo\b|\bdeck\b|"
    r"\btaza\b|\bmug\b|\bstickers?\b|\bpegatina|\bmochila|\bbilletera|\bgorro|\bcojin|\bfunda\b|\bartbook|"
    r"\blamina|\bacrylic stand\b|\bstand acrilico|\brubber strap|\bstrap\b|\bbadge|\bcan badge|\bvitrina|\bdisplay case|"
    r"\bgift card|\btarjeta de regalo|\benvio\b|\bdespacho\b|\babono\b|\bbase soporte|\bsoporte para|"
    r"\bbase para (figura|munec)|\bdisplay stand\b|\bstand para\b|\bpintura\b|\bpincel|\baerografo|\bherramienta")
ANIME_HINT = re.compile(
    r"\bbandai\b|\bbanpresto\b|\bgood smile\b|\bmax factory\b|\btamashii\b|\bmegahouse\b|\baniplex\b|\balter\b|"
    r"\bkotobukiya\b|\bsega\b|\btaito\b|\bfuryu\b|\bfreeing\b|\bamakuni\b|\banime\b|\bmanga\b|\bnendoroid\b|\bfigma\b|"
    r"\bdragon ball\b|\bone piece\b|\bnaruto\b|\bdemon slayer\b|\bkimetsu\b|\bjujutsu\b|\bchainsaw\b|\bpokemon\b|"
    r"\bevangelion\b|\bmy hero\b|\bspy x family\b|\bhunter x hunter\b|\bre zero\b|\bhololive\b|\bhatsune miku\b|"
    r"\bfrieren\b|\bbleach\b|\bjojo|\bsailor moon\b|\bhaikyuu\b|\bgundam\b|\bdandadan\b|\bsolo leveling\b")


# Franquicias que no son anime: se descartan en todas las tiendas, salvo que el título nombre una serie anime
NON_ANIME = re.compile(
    r"\bstar wars\b|\bmarvel\b|\bdc (comics|champion|multiverse|direct)\b|\bdc\b(?= )|\bbatman\b|\bsuperman\b|"
    r"\bspider ?man\b|\bspider ?gwen\b|\bavengers\b|\bharry potter\b|\bdisney\b|\bpixar\b|\btransformers?\b|"
    r"\btortugas ninja\b|\bninja turtles\b|\btmnt\b|\bjurassic\b|\bmandalorian\b|\bgrogu\b|\bkenner\b|\bhasbro\b|"
    r"\bmcfarlane\b|\bwwe\b|\bstranger things\b|\blord of the rings\b|\bsenor de los anillos\b|\bhalo\b|\bg ?i joe\b|"
    r"\bmasters of the universe\b|\bhe ?man\b|\bterminator\b|\bpredator\b|\bmortal kombat\b|\bjoker\b|\bdeadpool\b|"
    r"\bwolverine\b|\bx ?men\b|\biron man\b|\bhulk\b|\bthor\b|\bghostbusters\b|\btoy story\b|\bsimpsons?\b|"
    r"\blooney tunes\b|\bbarbie\b|\bminecraft\b|\bfortnite\b|\bfive nights\b|\bfnaf\b|\bsquid game\b|\blego\b|"
    r"\bvenom\b|\bharley quinn\b|\bwonder woman\b|\bthe flash\b|\baquaman\b|\bcaptain america\b|\bcapitan america\b|"
    r"\bdarth vader\b|\bbaby yoda\b|\bmarvel legends\b|\bblack series\b|\bvintage collection\b|\bsonic prime\b|"
    r"\bblack adam\b|\bshazam\b|\bwalking dead\b|\bfriday the 13th\b|\bhalloween\b|\bscream\b|\bchucky\b|\bbeetlejuice\b|\bwednesday\b")
ANIME_SERIES = re.compile(
    r"\banime\b|\bjapanese tv series\b|\bdragon ball\b|\bone piece\b|\bnaruto\b|\bboruto\b|\bdemon slayer\b|\bkimetsu\b|"
    r"\bjujutsu\b|\bchainsaw\b|\bpokemon\b|\bevangelion\b|\bmy hero\b|\bboku no hero\b|\bspy x family\b|"
    r"\bhunter x hunter\b|\bre ?zero\b|\bhololive\b|\bhatsune miku\b|\bvocaloid\b|\bfrieren\b|\bbleach\b|\bjojo|"
    r"\bsailor moon\b|\bhaikyuu\b|\bgundam\b|\bdandadan\b|\bsolo leveling\b|\bsaint seiya\b|\bcaballeros del zodiaco\b|"
    r"\battack on titan\b|\bshingeki\b|\bblue lock\b|\btokyo revengers\b|\bbeastars\b|\boshi no ko\b|\bkaiju\b|"
    r"\bmacross\b|\bultraman\b|\bkamen rider\b|\bsilent witch\b|\bsakamoto\b|\bgachiakuta\b")


def is_non_anime(title, kind=""):
    t = norm(f"{title} {kind}")
    return bool(NON_ANIME.search(t)) and not ANIME_SERIES.search(norm(title))


def is_figure(title, kind="", strict=False, all_figures=False):
    t = norm(f"{title} {kind}")
    tt = norm(title)
    if is_non_anime(title):
        return False
    if EXCLUDE.search(tt) and not re.search(r"\bfigur|\bnendoroid\b|\bfigma\b", tt):
        return False
    if all_figures:          # tiendas que solo venden figuras y no lo dicen en el título
        return True
    if not FIGURE_WORDS.search(t):
        return False
    if strict and not ANIME_HINT.search(t):
        return False
    return True


def detect_line(title, kind=""):
    t = norm(f"{title}")
    for i, _, rx in LINES_RE:
        if rx.search(t):
            return i
    t2 = norm(kind)
    for i, _, rx in LINES_RE:
        if rx.search(t2):
            return i
    return "otra"


# Palabras que no ayudan a identificar la figura
NOISE = set("""
figura figuras figure figures original originales oficial official anime manga chile stock en entrega inmediata
preventa pre venta order preorder reserva encargo express nuevo nueva new ob version ver de del la el los las y and
the of a con sin para coleccion coleccionable collection collectible pvc abs cm cms aprox approx tienda
banpresto bandai spirits good smile company gsc sega taito furyu kotobukiya max factory megahouse
premio prize figurine estatua statue action accion articulada edicion limited limitada exclusive exclusiva
usado usada sin caja expuesto expuesta sellado sellada open re run rerun restock japones japonesa jp import importado
tamashii nations vol volumen series serie set jap the of
""".split())


def tokens(title):
    t = norm(re.sub(r"\[[^\]]*\]|\([^)]*(stock|preventa|encargo|pre ?order|original)[^)]*\)", " ", title or "", flags=re.I))
    return [w for w in t.split() if w not in NOISE and not re.fullmatch(r"\d{1,2}(cm|cms)?", w)]


def line_number(title, line):
    """Número de catálogo para líneas numeradas (Nendoroid 1234, figma 567, Funko 932)."""
    t = norm(title)
    if line in ("nendoroid", "figma"):
        m = re.search(rf"\b{line}\s*(?:no\s*)?(\d{{2,4}})\b", t) or \
            re.search(r"(?:#|n[°ºo]\.?\s*)(\d{2,4})\b", title or "", re.I) or \
            re.search(r"(?<!20)\b(\d{3,4})(?: release| re ?run)?$", t)
        return m.group(1) if m else None
    if line == "funko":
        # solo números que claramente son de catálogo: "#932", "(932)" o al final del nombre
        m = re.search(r"#\s*(\d{1,4})\b", title or "") or re.search(r"\((\d{2,4})\)", title or "") or \
            re.search(r"\b(\d{2,4})$", t)
        if m and not re.fullmatch(r"(19|20)\d\d", m.group(1)):
            return m.group(1)
        return None
    return None


def kuji_prize(title):
    m = re.search(r"\b(?:premio|prize)\s*([a-z]|last ?one)\b", norm(title)) or \
        re.search(r"\b([a-z]|last ?one)\s*(?:premio|prize)\b", norm(title))
    return m.group(1).replace(" ", "") if m else None


# Figuras para adultos: por categoría de la tienda o por fabricante especializado
ADULT_WORDS = re.compile(r"\+ ?18|18 ?\+|\becchi\b|\bhentai\b|\bnsfw\b|\badult[oa]s?\b|\bcast ?off\b|\berotic|\b r18\b|\br 18\b")
ADULT_BRANDS = re.compile(
    r"\bnative\b|\bbinding\b|\brocket boy\b|\bnocturne\b|\bpink cat\b|\bhotvenus\b|\bhot venus\b|\bskytube\b|"
    r"\bsky tube\b|\btuberosa\b|\borchidseed\b|\bq six\b|\bqsix\b|\blechery\b|\bmagic mould\b|\bdaiki kougyou\b|"
    r"\binsight\b|\bgentlemen\b|\bpartylook\b|\bascendia\b|\bfrog\b|\bmagicbullets\b|\bpink charm\b|\bvibrastar\b")


def is_adult(title, kind="", brand=""):
    raw = f"{title} {kind} {brand}"
    if ADULT_WORDS.search(raw.lower()) or ADULT_WORDS.search(norm(raw)):
        return True
    # los fabricantes se miran solo en marca/categorías: en un título "Frog" o "Native" puede ser otra cosa
    return bool(ADULT_BRANDS.search(norm(f"{kind} {brand}")))


# Figuras alternativas (réplicas / bootlegs)
# en la descripción solo cuentan frases inequívocas ("versión alternativa"); "manos alternativas",
# "rostros alternativos" o "réplica exacta del personaje" aparecen en figuras originales
ALT_DESC = re.compile(r"versi[oó]n alternativa|figura alternativa|\bes alternativa\b|\bbootleg\b|"
                      r"\bno es (una figura |un producto )?original\b|\bproducto no original\b|\bimitaci[oó]n\b|"
                      r"\bknock ?off\b|versi[oó]n gen[eé]rica|figura gen[eé]rica", re.I)
# en el título se acepta un poco más
ALT_TITLE = re.compile(r"\balternativ[ao]\b(?! (ver|version|color|outfit|costume))|\bbootleg\b|\bno original\b|"
                       r"\bgen[eé]ric[ao]\b|\bimitaci[oó]n\b|\(r[eé]plica\)|\br[eé]plica\b(?! (de|del) (espada|arma|casco|katana|sable))", re.I)
ORIG_RE = re.compile(r"\boriginal(es)?\b|100 ?% original|licenciad[ao]|aut[eé]ntic[ao]", re.I)


def is_alternative(title, desc=""):
    """True = alternativa, False = dice ser original, None = no lo indica."""
    if ALT_TITLE.search(title or "") or ALT_DESC.search(desc or ""):
        return True
    if ORIG_RE.search(f"{title} {desc}"):
        return False
    return None
