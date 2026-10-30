"""Tests for the Swissinfo scraper."""

from datetime import date

from market_analysis.services.scrapers.swissinfo import _parse_swissinfo_market_wrap_card


def test_parse_swissinfo_market_wrap_for_date():
    """
    GIVEN Swissinfo listing HTML with Markets Wrap cards on multiple dates
    WHEN _parse_swissinfo_market_wrap_card is called for a target date
    THEN the Markets Wrap card for that date is returned
    """
    html = """
    <html><body>
      <article class="teaser-wide-card">
        <h3 class="teaser-wide-card__title">Other story</h3>
        <time class="teaser-wide-card__published" datetime="2026-10-23T10:00:00+02:00">
          Oct 23, 2026
        </time>
        <a class="teaser-wide-card__link" href="https://www.swissinfo.ch/eng/other/1"></a>
      </article>
      <article class="teaser-wide-card">
        <h3 class="teaser-wide-card__title">
          Stocks Fall as Oil Rally Keeps a Lid on Treasuries: Markets Wrap
        </h3>
        <time class="teaser-wide-card__published" datetime="2026-10-23T22:05:55+02:00">
          Oct 23, 2026
        </time>
        <a class="teaser-wide-card__link"
           href="https://www.swissinfo.ch/eng/stocks-fall-as-oil-rally-keeps-a-lid-on-treasuries%3a-markets-wrap/92260391">
        </a>
      </article>
      <article class="teaser-wide-card">
        <h3 class="teaser-wide-card__title">Older Markets Wrap</h3>
        <time class="teaser-wide-card__published" datetime="2026-10-22T22:00:00+02:00">
          Oct 22, 2026
        </time>
        <a class="teaser-wide-card__link"
           href="https://www.swissinfo.ch/eng/older-markets-wrap/1"></a>
      </article>
    </body></html>
    """
    article_link = _parse_swissinfo_market_wrap_card(html, date(2026, 10, 23))
    assert article_link is not None
    assert "92260391" in article_link["url"]
    assert "Markets Wrap" in article_link["title"]
