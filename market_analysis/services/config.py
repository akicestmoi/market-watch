"""Static paths and URLs for market-analysis article extraction."""

from market_analysis.models import ArticleRegionChoices, NewsSourceChoices

# ---------------------------------------------------------------------------
# News source registry
# ---------------------------------------------------------------------------
"""JSON catalog of scrapable news outlets."""

NEWS_SOURCES_JSON = "market_analysis/data_sources/news_sources.json"

# ---------------------------------------------------------------------------
# Article list URLs
# ---------------------------------------------------------------------------
"""Day / listing URLs and HTTP timeout for article extraction."""

BOURSIER_DAY_URL_TEMPLATE = (
    "https://www.boursier.com/actualites/news-du-jour/{yyyymmdd}"
)
SWISSINFO_LIST_URL = "https://www.swissinfo.ch/eng/bloomberg/"
TOKYO_CLOSING_BELL_LIST_URL = "https://tokyoclosingbell.com/"
TBS_BASE_URL = "https://newsdig.tbs.co.jp"
TBS_JAPAN_MARKETS_LIST_URL = (
    f"{TBS_BASE_URL}/list/withbloomberg/search"
    "?fulltext=%E6%97%A5%E6%9C%AC%E5%B8%82%E6%B3%81"
)
TBS_US_MARKETS_LIST_URL = (
    f"{TBS_BASE_URL}/list/withbloomberg/search"
    "?fulltext=%E7%B1%B3%E5%9B%BD%E5%B8%82%E6%B3%81"
)
BOURSORAMA_BASE_URL = "https://www.boursorama.com"
BOURSORAMA_MARCHES_LIST_URL = f"{BOURSORAMA_BASE_URL}/bourse/actualites/marches/"
BOURSORAMA_ACTUALITES_LIST_URL = f"{BOURSORAMA_BASE_URL}/bourse/actualites/"
ZONEBOURSE_BASE_URL = "https://www.zonebourse.com"
ZONEBOURSE_ACTUALITES_LIST_URL = f"{ZONEBOURSE_BASE_URL}/actualite-bourse/"
ZONEBOURSE_INDICES_LIST_URL = f"{ZONEBOURSE_BASE_URL}/actualite-bourse/indices/"
# CAC 40 news feed keeps Paris / Europe close wires that fall off the generic
# indices listing when US headlines dominate.
ZONEBOURSE_CAC40_NEWS_LIST_URL = (
    f"{ZONEBOURSE_BASE_URL}/cours/indice/CAC-40-4941/actualite/"
)
NEWSQUAWK_HEADLINES_LIST_URL = "https://www.newsquawk.com/headlines"
THE_EDGE_BASE_URL = "https://theedgemalaysia.com"
THE_EDGE_GLOBAL_MARKETS_LIST_URL = (
    f"{THE_EDGE_BASE_URL}/flash-categories/Global%2BMarkets"
)
CNBC_STOCK_MARKET_DAILY_RECAP_LIST_URL = (
    "https://www.cnbc.com/stock-market-daily-recap/"
)
HTTP_REQUEST_TIMEOUT_SECONDS = 180

# Close-wrap title cues by catalog source + region (substring, case-insensitive).
MARKET_CLOSE_TITLE_CUES_BY_SOURCE_REGION: dict[
    tuple[NewsSourceChoices, ArticleRegionChoices], list[str]
] = {
    (NewsSourceChoices.BOURSORAMA, ArticleRegionChoices.FR): [
        "bourse de paris clôture",
        "bourse de paris cloture",
        "bourse de paris termine",
        "cac 40 termine",
        "cac 40 finit",
    ],
    (NewsSourceChoices.BOURSORAMA, ArticleRegionChoices.EU): [
        "les bourses européennes clôturent",
        "les bourses europeennes cloturent",
        "les bourses européennes terminent",
        "les bourses europeennes terminent",
        "l'europe finit",
        "les marchés européens",
        "les marches europeens",
    ],
    (NewsSourceChoices.ZONEBOURSE, ArticleRegionChoices.US): [
        "wall street clôture",
        "wall street cloture",
        "wall street termine",
        "point marchés-wall street",
        "point marches-wall street",
        "point marchés - wall street",
        "nasdaq plonge",
        "nasdaq creuse",
        "nasdaq décroche",
        "nasdaq decroche",
    ],
    (NewsSourceChoices.ZONEBOURSE, ArticleRegionChoices.EU): [
        "les bourses européennes",
        "les bourses europeennes",
        "l'europe finit",
        "les marchés européens",
        "les marches europeens",
        "point marchés-l'europe",
        "point marches-l'europe",
        "point marchés-europe",
        "point marches-europe",
        "point marchés - l'europe",
    ],
    (NewsSourceChoices.ZONEBOURSE, ArticleRegionChoices.FR): [
        "bourse de paris clôture",
        "bourse de paris cloture",
        "bourse de paris termine",
        "bourse de paris finit",
        "cac 40 termine",
        "cac 40 finit",
        "cac 40 : la bourse de paris clôture",
        "cac 40 : la bourse de paris cloture",
        "paris termine",
        "point marchés-paris",
        "point marches-paris",
        "point marchés - paris",
    ],
}

# Prefer these wires when several Boursorama candidates match.
BOURSORAMA_PROVIDER_RANK: dict[str, int] = {
    "reuters": 0,
    "afp": 1,
    "zonebourse": 2,
    "boursorama": 3,
}

# Titles that look like opens / previews / non-daily wraps.
MARKET_WRAP_TITLE_EXCLUDE_CUES: list[str] = [
    "ouvre",
    "s'apprête",
    "s'apprete",
    "vue en",
    "valeurs à suivre",
    "valeurs a suivre",
    "semaine à venir",
    "semaine a venir",
    "bric-à-brac",
    "bric-a-brac",
    "vidéo point marchés",
    "video point marches",
    "octobre",
    "novembre",
    "décembre",
    "decembre",
    "janvier",
    "février",
    "fevrier",
    "mensuel",
    "hebdomadaire",
]
