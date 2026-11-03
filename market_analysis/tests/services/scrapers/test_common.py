"""Tests for shared article-scraper helpers."""

from datetime import date

from market_analysis.services.scrapers.common import (
    does_title_look_like_market_wrap,
    extract_main_text,
    parse_article_published_date,
)


def test_does_title_look_like_market_wrap_excludes_opens():
    """
    GIVEN close cues and an open-session title
    WHEN does_title_look_like_market_wrap is called
    THEN the open title is rejected and a close title is accepted
    """
    cues = ["wall street clôture", "wall street termine"]
    assert (
        does_title_look_like_market_wrap(
            "Wall Street ouvre en nette baisse, Amazon et Intel décrochent", cues
        )
        is False
    )
    assert (
        does_title_look_like_market_wrap(
            "Wall Street clôture en nette baisse, la tech déraille", cues
        )
        is True
    )


def test_parse_article_published_date_from_meta():
    """
    GIVEN article HTML with article:published_time
    WHEN parse_article_published_date is called
    THEN the calendar date is returned
    """
    html = """
    <html><head>
      <meta property="article:published_time" content="2026-10-30T07:33:46+0100"/>
    </head><body></body></html>
    """
    assert parse_article_published_date(html) == date(2026, 10, 30)


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
    assert text == "Markets fell on Friday.\nOil rose."


def test_extract_main_text_prefers_article_body_over_related_cards():
    """
    GIVEN HTML where related-story 'article' cards precede '.article-body'
    WHEN extract_main_text is called
    THEN the main article-body text is returned
    """
    html = """
    <html><body>
      <article class="m-article">
        <div class="m-article__content">GMO不正アクセス related card</div>
      </article>
      <div class="article-body">
        <p>（ブルームバーグ）： 30日の日本市場は株式が下落。</p>
      </div>
    </body></html>
    """
    assert (
        extract_main_text(html) == "（ブルームバーグ）： 30日の日本市場は株式が下落。"
    )


def test_extract_main_text_tolerates_null_class_attributes():
    """
    GIVEN HTML with an element whose class attribute is missing
    WHEN extract_main_text is called as a class-name fallback
    THEN extraction completes without raising
    """
    html = """
    <html><body>
      <div>Plain body text about markets.</div>
    </body></html>
    """
    assert extract_main_text(html) == "Plain body text about markets."
