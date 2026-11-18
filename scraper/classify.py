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
    ("gunpla", "Gunpla / Model kit", r"\bgunpla\b|\bmaster grade\b|\bhigh grade\b|\b(mg|hg|rg|pg) 1/\d+|\bfigure ?rise\b|\bmodel kit\b"),
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
    r"\bgift card|\btarjeta de regalo|\benvio\b|\bdespacho\b|\babono\b")
ANIME_HINT = re.compile(
    r"\bbandai\b|\bbanpresto\b|\bgood smile\b|\bmax factory\b|\btamashii\b|\bmegahouse\b|\baniplex\b|\balter\b|"
    r"\bkotobukiya\b|\bsega\b|\btaito\b|\bfuryu\b|\bfreeing\b|\bamakuni\b|\banime\b|\bmanga\b|\bnendoroid\b|\bfigma\b|"
    r"\bdragon ball\b|\bone piece\b|\bnaruto\b|\bdemon slayer\b|\bkimetsu\b|\bjujutsu\b|\bchainsaw\b|\bpokemon\b|"
    r"\bevangelion\b|\bmy hero\b|\bspy x family\b|\bhunter x hunter\b|\bre zero\b|\bhololive\b|\bhatsune miku\b|"
    r"\bfrieren\b|\bbleach\b|\bjojo|\bsailor moon\b|\bhaikyuu\b|\bgundam\b|\bdandadan\b|\bsolo leveling\b")


def is_figure(title, kind="", strict=False):
    t = norm(f"{title} {kind}")
    tt = norm(title)
    if EXCLUDE.search(tt) and not re.search(r"\bfigur|\bnendoroid\b|\bfigma\b", tt):
        return False
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
        m = re.search(r"\bpop\b[^0-9]{0,40}?(\d{1,4})\b", t) or re.search(r"\b(\d{2,4})\b", t)
        return m.group(1) if m else None
    return None


def kuji_prize(title):
    m = re.search(r"\b(?:premio|prize)\s*([a-z]|last ?one)\b", norm(title)) or \
        re.search(r"\b([a-z]|last ?one)\s*(?:premio|prize)\b", norm(title))
    return m.group(1).replace(" ", "") if m else None
