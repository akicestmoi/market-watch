"""Tests for the Newsquawk US Market Wrap scraper."""

from datetime import date

from market_analysis.services.scrapers.newsquawk import (
    _parse_newsquawk_us_market_wrap_card,
)


def test_parse_newsquawk_us_market_wrap_for_date():
    """
    GIVEN Newsquawk headlines HTML with a dated US Market Wrap
    WHEN _parse_newsquawk_us_market_wrap_card is called for that date
    THEN the wrap card is returned
    """
    html = """
    <html><body>
      <article class="group">
        <a href="/headlines/other">
          <time datetime="2026-10-30T19:00:00.000Z">19:00</time>
          <h2>US FX Wrap: Dollar mixed</h2>
        </a>
      </article>
      <article class="group">
        <a href="/headlines/ndx-briefly-enters-correction">
          <time datetime="2026-10-30T20:32:10.000Z">20:32</time>
          <h2>US Market Wrap: NDX briefly enters correction as weak tech earnings spark AI rout</h2>
        </a>
      </article>
    </body></html>
    """
    article_link = _parse_newsquawk_us_market_wrap_card(html, date(2026, 10, 30))
    assert article_link == {
        "title": (
            "US Market Wrap: NDX briefly enters correction as weak tech "
            "earnings spark AI rout"
        ),
        "url": ("https://www.newsquawk.com/headlines/ndx-briefly-enters-correction"),
    }
