"""Tests for Boursorama close-wrap candidate collection."""

from market_analysis.models import ArticleRegionChoices, NewsSourceChoices
from market_analysis.services.config import MARKET_CLOSE_TITLE_CUES_BY_SOURCE_REGION
from market_analysis.services.scrapers.boursorama import _collect_boursorama_candidates


def test_collect_boursorama_candidates_prefers_close_over_open():
    """
    GIVEN Boursorama list HTML with Paris close and Wall Street open headlines
    WHEN _collect_boursorama_candidates is called with France close cues
    THEN only the Paris close wrap is kept
    """
    html = """
    <html><body>
      <ul>
        <li class="c-list-news__line">
          <span class="c-list-news__date">ven.</span>
          <div class="c-list-news__content">
            <p class="c-list-news__title">
              <a href="/bourse/actualites/la-bourse-de-paris-termine-en-hausse-1">
                La Bourse de Paris termine en hausse, portée par les résultats
              </a>
            </p>
            <strong class="c-source__name">AFP</strong>
          </div>
        </li>
        <li class="c-list-news__line">
          <p class="c-list-news__title">
            <a href="/bourse/actualites/wall-street-ouvre-en-baisse-2">
              Wall Street ouvre en baisse, plombée par Alphabet
            </a>
          </p>
          <strong class="c-source__name">Reuters</strong>
        </li>
        <li class="c-list-news__line">
          <p class="c-list-news__title">
            <a href="/bourse/actualites/l-europe-finit-en-baisse-3">
              L'Europe finit en baisse, l'IA fait plonger le Nasdaq de 3%
            </a>
          </p>
          <strong class="c-source__name">Reuters</strong>
        </li>
      </ul>
    </body></html>
    """
    candidates = _collect_boursorama_candidates(
        html,
        MARKET_CLOSE_TITLE_CUES_BY_SOURCE_REGION[
            (NewsSourceChoices.BOURSORAMA, ArticleRegionChoices.FR)
        ],
    )
    assert [
        (candidate.title, candidate.url, candidate.provider) for candidate in candidates
    ] == [
        (
            "La Bourse de Paris termine en hausse, portée par les résultats",
            "https://www.boursorama.com/bourse/actualites/la-bourse-de-paris-termine-en-hausse-1",
            "afp",
        )
    ]
