"""Tests for html_text scraper helpers."""

from market_analysis.services.scrapers.html_text import extract_main_text


def test_extract_main_text_prefers_article():
    """
    GIVEN HTML with nav, article body, and footer
    WHEN extract_main_text is called
    THEN only the article body text is returned
    """
    html = """
    <html><body>
      <nav>Ignore nav</nav>
      <article><p>Markets fell on Friday.</p><p>Oil rose.</p></article>
      <footer>Ignore footer</footer>
    </body></html>
    """
    text = extract_main_text(html)
    assert "Markets fell on Friday." in text
    assert "Oil rose." in text
    assert "Ignore nav" not in text
    assert "Ignore footer" not in text
