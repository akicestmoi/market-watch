"""Tests for TBS Bloomberg markets scrapers."""

from datetime import date

from market_analysis.services.scrapers.tbs_bloomberg import (
    _parse_tbs_listing_date,
    _parse_tbs_markets_card,
)


def test_parse_tbs_listing_date():
    """
    GIVEN a TBS dotted date string
    WHEN _parse_tbs_listing_date is called
    THEN a date is returned
    """
    assert _parse_tbs_listing_date("2026.10.30") == date(2026, 10, 30)
    assert _parse_tbs_listing_date("not-a-date") is None


def test_parse_tbs_markets_card_takes_newest_same_day():
    """
    GIVEN TBS listing HTML with two 日本市況 cards on the same date
    WHEN _parse_tbs_markets_card is called for that date
    THEN the first (newest) card is returned
    """
    html = """
    <html><body>
      <div class="m-article-wrap">
        <article class="m-article">
          <a class="m-article__link" href="/articles/withbloomberg/3049671?display=1">
            <time class="m-article__date" datetime="2026-10-30T09:25:00+09:00">
              2026.10.30
            </time>
            <div class="m-article__ttl">
              【日本市況】株1300円超安、米ハイテク決算失望－安全志向で金利低下
            </div>
          </a>
        </article>
        <article class="m-article">
          <a class="m-article__link" href="/articles/withbloomberg/3049448?display=1">
            <time class="m-article__date" datetime="2026-10-30T07:10:00+09:00">
              2026.10.30
            </time>
            <div class="m-article__ttl">
              【日本市況】日経平均900円安、米ハイテク決算失望－債券先物が上昇
            </div>
          </a>
        </article>
        <article class="m-article">
          <a class="m-article__link" href="/articles/withbloomberg/3042878?display=1">
            <time class="m-article__date" datetime="2026-10-28T15:00:00+09:00">
              2026.10.28
            </time>
            <div class="m-article__ttl">【日本市況】AI懸念後退し日経平均続伸</div>
          </a>
        </article>
      </div>
    </body></html>
    """
    article_link = _parse_tbs_markets_card(
        html, date(2026, 10, 30), title_marker="【日本市況】"
    )
    assert article_link == {
        "title": "【日本市況】株1300円超安、米ハイテク決算失望－安全志向で金利低下",
        "url": "https://newsdig.tbs.co.jp/articles/withbloomberg/3049671?display=1",
    }


def test_parse_tbs_markets_card_missing_day_returns_none():
    """
    GIVEN TBS listing HTML with no card for the reporting date
    WHEN _parse_tbs_markets_card is called
    THEN None is returned
    """
    html = """
    <html><body>
      <article class="m-article">
        <a class="m-article__link" href="/articles/withbloomberg/1">
          <time class="m-article__date" datetime="2026-10-28T15:00:00+09:00">
            2026.10.28
          </time>
          <div class="m-article__ttl">【日本市況】続伸</div>
        </a>
      </article>
    </body></html>
    """
    assert (
        _parse_tbs_markets_card(html, date(2026, 10, 30), title_marker="【日本市況】")
        is None
    )
