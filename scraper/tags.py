"""Tags de cada figura: serie y estilo, detectados en los títulos de todas sus tiendas.

Cada serie tiene:
  - nombres: cómo la escriben las tiendas (incluye nombres alternativos y en japonés romanizado).
  - personajes: nombres que la identifican aunque la tienda no escriba la serie. Solo nombres que no se
    confunden con palabras comunes ni con personajes de otras series ("Power", "Gon", "Rem" quedan fuera
    salvo con apellido).
Los patrones se buscan sobre el texto normalizado (minúsculas, sin tildes ni signos).
"""
import re

from .classify import norm

# (slug, nombre visible, nombres de la serie, personajes)
SERIES = [
    ("one-piece", "One Piece", r"one piece", r"monkey d luffy|luffy|roronoa|zoro|vinsmoke|sanji|nico robin|portgas|"
     r"trafalgar|boa hancock|shanks|yamato|kaido|kaidou|whitebeard|edward newgate|tony tony chopper|usopp|jinbe|"
     r"sabo|kizaru|akainu|aokiji|kuzan|borsalino|sakazuki|mihawk|buggy|crocodile|doflamingo|katakuri|big mom|"
     r"charlotte linlin|uta|kozuki oden|garp|rob lucci|enel|eustass kid|perona|vivi|nefertari|carrot|"
     r"yamato|blackbeard|marshall d teach|brook|franky|nami"),
    ("dragon-ball", "Dragon Ball", r"dragon ?ball|dbz|dbs|dbgt", r"goku|vegeta|gohan|trunks|frieza|freezer|piccolo|"
     r"broly|majin buu|bulma|krillin|gogeta|vegito|vegetto|goten|gotenks|beerus|bills|jiren|android 1[78]|"
     r"androide 1[78]|zamasu|cooler|raditz|nappa|bardock|yamcha|tenshinhan|chi chi|videl|caulifla|"
     r"cell max|perfect cell|shenron|whis|granolah|gamma 1|gamma 2"),
    ("gundam", "Gundam", r"gundam|gunpla|zaku|mobile suit|zeon|hguc|entry grade|mgex|mgsd", r"char aznable|amuro"),
    ("pokemon", "Pokémon", r"pokemon|pokémon", r"pikachu|charizard|eevee|mewtwo|gengar|snorlax|bulbasaur|squirtle|"
     r"charmander|lucario|greninja|rayquaza|umbreon|sylveon|jigglypuff|psyduck|mimikyu|gardevoir|dragonite|lugia|"
     r"ho oh|arceus|blastoise|venusaur|meowth|togepi|vaporeon|jolteon|flareon|espeon|leafeon|glaceon"),
    ("demon-slayer", "Demon Slayer", r"kimetsu|demon slayer", r"tanjiro|nezuko|zenitsu|inosuke|rengoku|giyu|tomioka|"
     r"shinobu|kocho|tengen|uzui|muichiro|tokito|mitsuri|kanroji|akaza|kanao|tsuyuri|muzan|kokushibo|douma|"
     r"gyomei|obanai|sanemi|genya|daki|gyutaro|enmu|yoriichi"),
    ("naruto", "Naruto", r"naruto|boruto|shippuden", r"uzumaki|sasuke|uchiha|kakashi|itachi|jiraiya|madara|obito|"
     r"hinata hyuga|hyuga|gaara|sakura haruno|minato|orochimaru|tsunade|kurama|might guy|rock lee|shikamaru|"
     r"neji|kawaki|sarada|mitsuki|akatsuki|deidara|sasori|kisame|hidan|konan|nagato|tobi|sakumo"),
    ("my-hero-academia", "My Hero Academia", r"my hero|boku no hero|hero academia|mha", r"midoriya|izuku|bakugo|"
     r"bakugou|katsuki|todoroki|shoto|all might|ochaco|uraraka|himiko toga|toga himiko|dabi|shigaraki|tomura|"
     r"eijiro|kirishima|tsuyu|asui|momo yaoyorozu|yaoyorozu|denki|kaminari|endeavor|hawks|mirio|tamaki|nejire|"
     r"overhaul|aizawa|eraser head|tenya|iida|hitoshi|shinso|mirko|star and stripe|stain|kurogiri"),
    ("jujutsu-kaisen", "Jujutsu Kaisen", r"jujutsu|jjk", r"gojo|satoru|itadori|yuji|sukuna|megumi|fushiguro|nobara|"
     r"kugisaki|geto|suguru|toji|yuta okkotsu|okkotsu|maki zenin|zenin|nanami|kento|mahito|choso|aoi todo|"
     r"inumaki|toge|rika orimoto|jogo|hanami|kenjaku|uraume|yuki tsukumo|hakari|higuruma|mei mei"),
    ("hatsune-miku", "Hatsune Miku / Vocaloid", r"hatsune|vocaloid|piapro", r"miku|kagamine|megurine|luka|"
     r"meiko|rin len"),
    ("frieren", "Frieren", r"frieren|sousou no|sosou no", r"fern|himmel|heiter|eisen|ubel|aura the guillotine"),
    ("evangelion", "Evangelion", r"evangelion|neon genesis|\beva\b", r"rei ayanami|ayanami|asuka|langley|shinji|"
     r"ikari|mari makinami|misato|kaworu"),
    ("hunter-x-hunter", "Hunter x Hunter", r"hunter x hunter|hunterxhunter|hxh", r"killua|zoldyck|hisoka|"
     r"kurapika|meruem|chrollo|leorio|netero|illumi|gon freecss|feitan|nobunaga"),
    ("chainsaw-man", "Chainsaw Man", r"chainsaw ?man", r"makima|denji|pochita|reze|aki hayakawa|kobeni|himeno|"
     r"kishibe|quanxi"),
    ("re-zero", "Re:Zero", r"re ?zero|rezero", r"emilia|subaru natsuki|echidna|beatrice|puck"),
    ("bleach", "Bleach", r"bleach", r"kurosaki|ichigo|rukia|kuchiki|aizen|byakuya|kenpachi|zaraki|toshiro|hitsugaya|"
     r"orihime|inoue|uryu|ishida|grimmjow|ulquiorra|urahara|yoruichi|soi fon|rangiku|yhwach"),
    ("saint-seiya", "Saint Seiya", r"saint seiya|caballeros del zodiaco|myth cloth", r"pegasus seiya|shiryu|hyoga|"
     r"shun|ikki|athena|camus|shaka|aiolos|aioria|milo|mu de aries"),
    ("spy-x-family", "Spy x Family", r"spy ?x ?family", r"anya|forger|yor|loid|twilight|bond forger"),
    ("dandadan", "Dandadan", r"dandadan|dan da dan", r"momo ayase|ayase momo|okarun|ken takakura|turbo granny|aira shiratori"),
    ("attack-on-titan", "Attack on Titan", r"shingeki|attack on titan|aot", r"eren|jaeger|yeager|levi|ackerman|"
     r"mikasa|armin|erwin|hange|zeke|reiner|annie leonhart|sasha blouse"),
    ("kaiju-no-8", "Kaiju No. 8", r"kaiju no ?8|kaiju n 8|kaijuu", r"kafka hibino|mina ashiro|kikoru|soshiro hoshina|"
     r"reno ichikawa"),
    ("sailor-moon", "Sailor Moon", r"sailor moon|pretty guardian", r"usagi|tsukino|sailor (mars|mercury|jupiter|venus|"
     r"pluto|saturn|uranus|neptune|chibi moon)|chibiusa|tuxedo mask"),
    ("oshi-no-ko", "Oshi no Ko", r"oshi no ko", r"hoshino ai|ai hoshino|ruby hoshino|hoshino ruby|kana arima|akane kurokawa|aqua hoshino"),
    ("solo-leveling", "Solo Leveling", r"solo leveling", r"sung jin ?woo|jinwoo|cha hae ?in|igris"),
    ("blue-lock", "Blue Lock", r"blue lock", r"isagi|bachira|rin itoshi|itoshi|seishiro nagi|reo mikage|chigiri|kunigami|barou"),
    ("jojo", "JoJo's Bizarre Adventure", r"jojo", r"jotaro|kujo|dio brando|josuke|giorno|giovanna|joseph joestar|"
     r"jonathan joestar|jolyne|kishibe rohan|bucciarati|kira yoshikage|star platinum"),
    ("sword-art-online", "Sword Art Online", r"sword art online|\bsao\b", r"kirito|asuna|yuuki|sinon|alice synthesis|leafa"),
    ("konosuba", "KonoSuba", r"konosuba|kono subarashii", r"megumin|kazuma"),
    ("overlord", "Overlord", r"overlord", r"albedo|ainz|shalltear|narberal"),
    ("tokyo-ghoul", "Tokyo Ghoul", r"tokyo ghoul", r"kaneki|touka|rize"),
    ("tokyo-revengers", "Tokyo Revengers", r"tokyo revengers", r"mikey|manjiro sano|draken|takemichi|baji"),
    ("haikyu", "Haikyu!!", r"haikyu", r"hinata shoyo|shoyo hinata|tobio kageyama|kageyama tobio|oikawa|bokuto|kenma|kuroo|nishinoya"),
    ("fate", "Fate", r"\bfate\b|fgo", r"saber|artoria|altria|jeanne d arc|ishtar|ereshkigal|gilgamesh|tohsaka|rin tohsaka|mash kyrielight"),
    ("hololive", "Hololive / VTubers", r"hololive|vtuber|nijisanji", r"gawr gura|houshou marine|usada pekora|"
     r"shirakami fubuki|minato aqua|hoshimachi suisei|mori calliope|kobo kanaeru"),
    ("genshin", "Genshin Impact", r"genshin", r"raiden shogun|hu tao|ganyu|klee|zhongli|venti|nahida|furina|"
     r"kamisato ayaka|yae miko|keqing|paimon|xiao|eula|nilou|navia|arlecchino"),
    ("honkai", "Honkai", r"honkai|star rail", r"silver wolf|firefly|march 7th|acheron|bronya|kiana|elysia|seele"),
    ("blue-archive", "Blue Archive", r"blue archive", r"shiroko|hina sorasaki|asuna ichinose|mika misono"),
    ("azur-lane", "Azur Lane", r"azur lane", r"taihou|atago|belfast|st louis|formidable|cheshire|new jersey"),
    ("nikke", "Nikke", r"nikke", r"modernia|alice nikke"),
    ("love-live", "Love Live!", r"love ?live", r"honoka kosaka|chika takami|you watanabe|ayumu|kanon shibuya"),
    ("idolmaster", "The Idolmaster", r"idolmaster|idol master|im@s", r"shimamura uzuki|shibuya rin|hoshii miki"),
    ("bocchi", "Bocchi the Rock!", r"bocchi", r"hitori gotoh|gotoh hitori|kita ikuyo|nijika|ryo yamada"),
    ("my-dress-up-darling", "My Dress-Up Darling", r"dress ?up darling|sono bisque|bisque doll", r"marin kitagawa|kitagawa marin"),
    ("rascal", "Rascal Does Not Dream", r"rascal does not dream|seishun buta|bunny girl senpai", r"mai sakurajima|sakurajima mai|tomoe koga"),
    ("quintessential", "The Quintessential Quintuplets", r"quintessential quintuplets|gotoubun|5 toubun",
     r"nakano (ichika|nino|miku|yotsuba|itsuki)|(ichika|nino|yotsuba|itsuki) nakano"),
    ("kaguya-sama", "Kaguya-sama", r"kaguya ?sama", r"kaguya shinomiya|chika fujiwara|ai hayasaka"),
    ("gridman", "SSSS.Gridman / Dynazenon", r"ssss|gridman|dynazenon", r"takarada|rikka|akane shinjo|shinjo akane|yume minami|minami yume"),
    ("mushoku-tensei", "Mushoku Tensei", r"mushoku tensei", r"roxy migurdia|roxy|eris greyrat|sylphiette|rudeus"),
    ("shield-hero", "The Rising of the Shield Hero", r"shield hero|tate no yuusha", r"raphtalia|filo|naofumi"),
    ("slime", "That Time I Got Reincarnated as a Slime", r"tensura|reincarnated as a slime|tensei shitara slime",
     r"rimuru|milim|shion|shuna"),
    ("lycoris", "Lycoris Recoil", r"lycoris recoil", r"chisato nishikigi|takina inoue"),
    ("cyberpunk-edgerunners", "Cyberpunk: Edgerunners", r"edgerunners", r"david martinez"),
    ("berserk", "Berserk", r"berserk", r"guts|griffith|casca|femto"),
    ("mob-psycho", "Mob Psycho 100", r"mob psycho", r"shigeo kageyama|reigen"),
    ("one-punch-man", "One Punch Man", r"one ?punch ?man|onepunch", r"saitama|genos|tatsumaki|garou"),
    ("black-clover", "Black Clover", r"black clover", r"asta|yuno|noelle silva|yami sukehiro"),
    ("fire-force", "Fire Force", r"fire force|enen no shouboutai", r"shinra kusakabe|tamaki kotatsu|maki oze|benimaru shinmon"),
    ("hells-paradise", "Hell's Paradise", r"hell s paradise|jigokuraku", r"gabimaru|sagiri|yamada asaemon"),
    ("undead-unluck", "Undead Unluck", r"undead unluck", r"fuuko izumo"),
    ("yu-gi-oh", "Yu-Gi-Oh!", r"yu ?gi ?oh", r"dark magician|blue eyes|kaiba|yugi muto|exodia"),
    ("digimon", "Digimon", r"digimon", r"agumon|gabumon|omegamon|omnimon|wargreymon|patamon|gatomon"),
    ("sonic", "Sonic", r"sonic the hedgehog", r"shadow the hedgehog|knuckles|tails"),
    ("zelda-nintendo", "Nintendo", r"zelda|super mario|nintendo|splatoon|kirby|metroid|animal crossing|xenoblade|"
     r"fire emblem|smash bros", r"link|princess zelda|mario|luigi|bowser|samus"),
    ("persona", "Persona", r"persona [345]|persona5|p5r", r"makoto niijima|futaba sakura|ann takamaki"),
    ("final-fantasy", "Final Fantasy", r"final fantasy", r"cloud strife|sephiroth|tifa|aerith|zack fair"),
    ("nier", "NieR", r"nier|automata", r"2b|9s"),
    ("street-fighter", "Street Fighter", r"street fighter", r"chun li|cammy|ken masters|juri han"),
    ("monster-hunter", "Monster Hunter", r"monster hunter", r"rathalos|nergigante|zinogre"),
    ("uma-musume", "Uma Musume", r"uma ?musume|pretty derby", r"special week|silence suzuka|tokai teio|gold ship|kitasan black|rice shower|mejiro mcqueen"),
    ("sanrio", "Sanrio / Hello Kitty", r"sanrio|hello kitty", r"kuromi|my melody|cinnamoroll|pompompurin|pochacco|hangyodon"),
    ("ranma", "Ranma 1/2", r"ranma", r"akane tendo|tendo akane|shampoo|ryoga hibiki|ukyo kuonji"),
    ("date-a-live", "Date A Live", r"date a live", r"tokisaki|kurumi tokisaki|tohka yatogami|origami tobiichi|kotori itsuka"),
    ("to-love-ru", "To LOVE-Ru", r"to ?love ?ru|loveru", r"deviluke|lala satalin|yami golden darkness|momo belia|nana asta|mikan yuuki|run elsie"),
    ("inuyasha", "Inuyasha", r"inuyasha|inu yasha", r"kagome higurashi|sesshomaru|kikyo|miroku"),
    ("madoka", "Madoka Magica", r"madoka|magica", r"homura akemi|akemi homura|mami tomoe|tomoe mami|kyoko sakura|sayaka miki|kyubey"),
    ("apothecary-diaries", "The Apothecary Diaries", r"apothecary diaries|kusuriya", r"maomao|jinshi"),
    ("arknights", "Arknights", r"arknights", r"amiya|texas|lappland|skadi|exusiai|chen arknights"),
    ("super-sonico", "Super Sonico", r"super sonico|sonico", r""),
    ("mashle", "Mashle", r"mashle", r"mash burnedead"),
    ("keroro", "Keroro", r"keroro", r""),
    ("zoids", "Zoids", r"zoids", r"liger zero|blade liger|shield liger"),
    ("thirty-minutes", "30 Minutes Missions / Sisters", r"30mm|30ms|30 minutes (missions|sisters|fantasy)", r""),
    ("code-geass", "Code Geass", r"code geass", r"lelouch|kallen kozuki|suzaku kururugi"),
    ("mega-man", "Mega Man", r"mega ?man|rockman", r""),
    ("atelier", "Atelier", r"atelier (ryza|sophie|firis|lydie|sophie)", r"reisalin stout|ryza"),
    ("black-rock-shooter", "Black Rock Shooter", r"black rock shooter|black ?rock", r""),
    ("frame-arms-girl", "Frame Arms Girl / Megami Device", r"frame arms girl|megami device|frame arms", r""),
    ("monogatari", "Monogatari", r"monogatari|bakemonogatari", r"shinobu oshino|oshino shinobu|hitagi senjougahara|senjougahara|hanekawa"),
    ("gintama", "Gintama", r"gintama", r"gintoki|kagura|okita sougo"),
    ("conan", "Detective Conan", r"detective conan|meitantei conan|case closed", r"edogawa conan|kaito kid|kaitou kid|ran mouri|amuro tooru|akai shuichi"),
    ("toradora", "Toradora!", r"toradora", r"taiga aisaka"),
    ("steins-gate", "Steins;Gate", r"steins ?gate", r"kurisu makise|makise kurisu|okabe"),
    ("macross", "Macross", r"macross", r"sheryl nome|ranka lee|valkyrie"),
    ("ultraman", "Ultraman / Tokusatsu", r"ultraman|kamen rider|super sentai|power rangers|godzilla", r""),
    ("touhou", "Touhou", r"touhou", r"reimu hakurei|marisa kirisame|remilia|flandre"),
    ("vtuber-misc", "Otros VTubers", r"virtual youtuber", r""),
    ("baki", "Baki", r"baki", r"yujiro hanma|hanma"),
    ("kenshin", "Rurouni Kenshin", r"rurouni kenshin|samurai x", r"himura kenshin|kenshin himura"),
    ("cowboy-bebop", "Cowboy Bebop", r"cowboy bebop", r"spike spiegel|faye valentine"),
    ("ghibli", "Studio Ghibli", r"ghibli|totoro|spirited away|chihiro|howl|kiki|mononoke|ponyo", r""),
    ("kagurabachi", "Kagurabachi", r"kagurabachi", r"chihiro rokuhira"),
    ("sakamoto-days", "Sakamoto Days", r"sakamoto days", r"taro sakamoto|shin asakura"),
]

# estilo o vestuario de la figura
STYLES = [
    ("traje-de-bano", "Traje de baño", r"traje de bano|swimsuit|swim suit|bikini|mizugi|beach queens|summer (ver|style|vacation)"),
    ("bunny", "Bunny", r"bunny|conejita|bunnies"),
    ("kimono", "Kimono / Yukata", r"kimono|yukata|furisode|hakama"),
    ("maid", "Maid", r"\bmaid\b|mucama|sirvienta"),
    ("uniforme", "Uniforme escolar", r"school uniform|uniforme escolar|seifuku|sailor uniform|gym uniform"),
    ("vestido", "Vestido / Gala", r"\bdress\b|vestido|wedding|novia|gala|evening"),
    ("idol", "Idol", r"\bidol\b|stage outfit|concert"),
    ("china", "China dress", r"china dress|cheongsam|qipao|kung ?fu"),
    ("navidad", "Navidad", r"christmas|navidad|santa"),
    ("pijama", "Pijama / Casual", r"pijama|pajama|pyjama|loungewear|roomwear|casual (wear|ver|style|outfit)"),
    ("gothic", "Gótico / Lolita", r"gothic|gotica|lolita"),
    ("bunny-lingerie", "Lencería", r"lingerie|lenceria|negligee"),
    ("armadura", "Armadura / Batalla", r"armor|armour|armadura|battle (ver|style)"),
]

_COMPILED = None


def _compile():
    global _COMPILED
    if _COMPILED is None:
        def rx(p):
            return re.compile(r"(?:^| )(?:" + p + r")(?= |$)") if p else None
        _COMPILED = ([(slug, name, rx(names), rx(chars)) for slug, name, names, chars in SERIES],
                     [(slug, name, rx(pat)) for slug, name, pat in STYLES])
    return _COMPILED


def tag_text(texts):
    return " " + " ".join(norm(t) for t in texts if t) + " "


def series_of(texts):
    """Series de la figura: primero por nombre de serie; si no hay, por personaje."""
    series, _ = _compile()
    t = tag_text(texts)
    found = [slug for slug, _, names, _ in series if names and names.search(t)]
    if not found:
        found = [slug for slug, _, _, chars in series if chars and chars.search(t)]
        if len(found) > 2:     # demasiados personajes de series distintas: probablemente una palabra común
            found = []
    return found[:3]


def styles_of(texts):
    _, styles = _compile()
    t = tag_text(texts)
    return [slug for slug, _, pat in styles if pat.search(t)]


SERIES_NAMES = {slug: name for slug, name, _, _ in SERIES}
STYLE_NAMES = {slug: name for slug, name, _ in STYLES}
