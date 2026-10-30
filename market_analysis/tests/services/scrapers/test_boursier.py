"""Tests for the Boursier scraper."""

from market_analysis.services.scrapers.boursier import _parse_boursier_cloture_link


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
