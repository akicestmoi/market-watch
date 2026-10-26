"""Tests for article_extraction."""

from datetime import date

from market_analysis.services.article_extraction import (
    _extract_main_text,
    _parse_boursier_cloture_link,
    _parse_swissinfo_market_wrap_card,
)


def test_extract_main_text_prefers_article():
    """
    GIVEN HTML with nav, article body, and footer
    WHEN _extract_main_text is called
    THEN only the article body text is returned
    """
    html = """
    <html><body>
      <nav>Ignore nav</nav>
      <article><p>Markets fell on Friday.</p><p>Oil rose.</p></article>
      <footer>Ignore footer</footer>
    </body></html>
    """
    text = _extract_main_text(html)
    assert "Markets fell on Friday." in text
    assert "Oil rose." in text
    assert "Ignore nav" not in text
    assert "Ignore footer" not in text


def test_parse_boursier_cloture_link():
    """
    GIVEN a Boursier listing page HTML with a Clôture Paris link
    WHEN _parse_boursier_cloture_link is called
    THEN the Clôture Paris article URL and title are returned
    """
    html = """
    <html><body>
      <a href="/actualites/news/autre-996000.html">Autre titre</a>
      <a href="/actualites/news/cloture-paris-le-cac-40-en-baisse-kering-et-safran-chutent-996757.html">
        Clôture Paris: le CAC 40 en baisse, Kering et Safran chutent
      </a>
    </body></html>
    """
    article_link = _parse_boursier_cloture_link(
        html, base_url="https://www.boursier.com/actualites/news-du-jour/20261023"
    )
    assert article_link is not None
    assert article_link["url"].endswith("996757.html")
    assert article_link["title"].startswith("Clôture Paris")


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
