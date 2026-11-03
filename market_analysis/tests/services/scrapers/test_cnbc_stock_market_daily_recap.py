"""Tests for the CNBC Stock Market Daily Recap scraper."""

from datetime import date

from market_analysis.services.scrapers.cnbc_stock_market_daily_recap import (
    _parse_cnbc_stock_market_daily_recap_card,
)


def test_parse_cnbc_stock_market_daily_recap_picks_matching_url_date():
    """
    GIVEN CNBC daily-recap listing HTML with live-update cards
    WHEN _parse_cnbc_stock_market_daily_recap_card is called for that date
    THEN the matching stock-market-today live update is returned
    """
    html = """
    <html><body>
      <a href="https://www.cnbc.com/2026/10/29/stock-market-today-live-updates.html">
        Stock market rocked as investors dump tech shares
      </a>
      <a href="https://www.cnbc.com/2026/10/28/stock-market-today-live-updates.html">
        Dow loses 100 points, S&P 500 snaps 3-day advance
      </a>
      <a href="https://www.cnbc.com/2026/10/29/other-story.html">
        Unrelated CNBC story long enough to pass length check
      </a>
    </body></html>
    """
    article_link = _parse_cnbc_stock_market_daily_recap_card(html, date(2026, 10, 29))
    assert article_link == {
        "title": "Stock market rocked as investors dump tech shares",
        "url": "https://www.cnbc.com/2026/10/29/stock-market-today-live-updates.html",
    }
