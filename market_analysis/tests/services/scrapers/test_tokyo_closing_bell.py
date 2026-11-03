"""Tests for the Tokyo Closing Bell scraper."""

from datetime import date

from market_analysis.services.scrapers.tokyo_closing_bell import (
    _parse_tokyo_closing_bell_card,
)


def test_parse_tokyo_closing_bell_card_prefers_url_session_date():
    """
    GIVEN homepage HTML where publish datetime differs from the URL session date
    WHEN _parse_tokyo_closing_bell_card is called for the session date
    THEN the Nikkei wrap whose URL slug matches that date is returned
    """
    html = """
    <html><body>
      <article>
        <h2 class="entry-title">
          <a href="https://tokyoclosingbell.com/nikkei-claws-back-2026-10-23/">
            Nikkei Claws Back a Plunge
          </a>
        </h2>
        <time datetime="2026-10-25T21:13:11+09:00">October 25, 2026</time>
      </article>
      <article>
        <h2 class="entry-title">
          <a href="https://tokyoclosingbell.com/nikkei-drops-2026-10-30/">
            Nikkei Drops 2.1% as AI Capex Doubts Hit Chips
          </a>
        </h2>
        <time datetime="2026-10-30T17:33:58+09:00">October 30, 2026</time>
      </article>
    </body></html>
    """
    article_link = _parse_tokyo_closing_bell_card(html, date(2026, 10, 23))
    assert article_link == {
        "title": "Nikkei Claws Back a Plunge",
        "url": "https://tokyoclosingbell.com/nikkei-claws-back-2026-10-23/",
    }
