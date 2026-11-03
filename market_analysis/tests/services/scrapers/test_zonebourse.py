"""Tests for Zonebourse close-wrap candidate collection."""

from market_analysis.models import ArticleRegionChoices, NewsSourceChoices
from market_analysis.services.config import MARKET_CLOSE_TITLE_CUES_BY_SOURCE_REGION
from market_analysis.services.scrapers.zonebourse import _collect_zonebourse_candidates


def test_collect_zonebourse_candidates_keeps_europe_close_wraps():
    """
    GIVEN Zonebourse listing HTML with Europe close and commodity close titles
    WHEN _collect_zonebourse_candidates is called with Europe close cues
    THEN only the European equity-session wrap is kept
    """
    html = """
    <html><body>
      <a href="/actualite-bourse/les-bourses-europeennes-terminent-en-hausse-1">
        Les Bourses européennes terminent en hausse
      </a>
      <a href="/actualite-bourse/point-marches-l-europe-finit-en-baisse-2">
        Point marchés-L'Europe finit en baisse, l'IA fait plonger le Nasdaq
      </a>
      <a href="/actualite-bourse/le-ble-europeen-termine-en-hausse-3">
        Le blé européen termine en hausse, mais accuse une deuxième baisse
      </a>
      <a href="/cours/indice/CAC-40-4941/">CAC 40</a>
    </body></html>
    """
    candidates = _collect_zonebourse_candidates(
        html,
        MARKET_CLOSE_TITLE_CUES_BY_SOURCE_REGION[
            (NewsSourceChoices.ZONEBOURSE, ArticleRegionChoices.EU)
        ],
    )
    assert candidates == [
        {
            "title": "Les Bourses européennes terminent en hausse",
            "url": (
                "https://www.zonebourse.com/actualite-bourse/"
                "les-bourses-europeennes-terminent-en-hausse-1"
            ),
        },
        {
            "title": (
                "Point marchés-L'Europe finit en baisse, " "l'IA fait plonger le Nasdaq"
            ),
            "url": (
                "https://www.zonebourse.com/actualite-bourse/"
                "point-marches-l-europe-finit-en-baisse-2"
            ),
        },
    ]


def test_collect_zonebourse_candidates_keeps_paris_close_wraps():
    """
    GIVEN Zonebourse CAC-40 feed HTML with a Paris close wrap
    WHEN _collect_zonebourse_candidates is called with France close cues
    THEN the Paris close wrap is kept and monthly titles are skipped
    """
    html = """
    <html><body>
      <a href="/actualite-bourse/paris-termine-octobre-quasi-stable-1">
        Paris termine octobre quasi stable
      </a>
      <a href="/actualite-bourse/cac-40-la-bourse-de-paris-cloture-2">
        CAC 40 : La Bourse de Paris clôture sans grand changement
      </a>
    </body></html>
    """
    candidates = _collect_zonebourse_candidates(
        html,
        MARKET_CLOSE_TITLE_CUES_BY_SOURCE_REGION[
            (NewsSourceChoices.ZONEBOURSE, ArticleRegionChoices.FR)
        ],
    )
    assert candidates == [
        {
            "title": "CAC 40 : La Bourse de Paris clôture sans grand changement",
            "url": (
                "https://www.zonebourse.com/actualite-bourse/"
                "cac-40-la-bourse-de-paris-cloture-2"
            ),
        }
    ]


def test_collect_zonebourse_candidates_keeps_us_close_wraps():
    """
    GIVEN Zonebourse indices HTML with Wall Street close and Europe titles
    WHEN _collect_zonebourse_candidates is called with US close cues
    THEN only the US session wrap is kept
    """
    html = """
    <html><body>
      <a href="/actualite-bourse/wall-street-cloture-en-nette-baisse-1">
        Wall Street clôture en nette baisse, la tech déraille
      </a>
      <a href="/actualite-bourse/l-europe-finit-en-baisse-2">
        L'Europe finit en baisse, l'IA fait plonger le Nasdaq de 3%
      </a>
      <a href="/actualite-bourse/journee-noire-nasdaq-3">
        Journée noire pour l'IA, le Nasdaq plonge de plus de 3%
      </a>
    </body></html>
    """
    candidates = _collect_zonebourse_candidates(
        html,
        MARKET_CLOSE_TITLE_CUES_BY_SOURCE_REGION[
            (NewsSourceChoices.ZONEBOURSE, ArticleRegionChoices.US)
        ],
    )
    assert candidates == [
        {
            "title": "Wall Street clôture en nette baisse, la tech déraille",
            "url": (
                "https://www.zonebourse.com/actualite-bourse/"
                "wall-street-cloture-en-nette-baisse-1"
            ),
        },
        {
            "title": "Journée noire pour l'IA, le Nasdaq plonge de plus de 3%",
            "url": (
                "https://www.zonebourse.com/actualite-bourse/" "journee-noire-nasdaq-3"
            ),
        },
    ]
