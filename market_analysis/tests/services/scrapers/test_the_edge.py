"""Tests for The Edge Global+Markets scraper."""

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

from market_analysis.services.scrapers.the_edge import (
    _extract_the_edge_article_text,
    _parse_the_edge_global_markets_card,
)


def test_parse_the_edge_global_markets_card_for_kuala_lumpur_date():
    """
    GIVEN The Edge __NEXT_DATA__ with Global Markets flashes
    WHEN _parse_the_edge_global_markets_card is called for the KL publish date
    THEN the matching global wrap is returned and thematic non-wraps are skipped
    """
    kuala_lumpur = ZoneInfo("Asia/Kuala_Lumpur")
    created_ms = int(
        datetime(2026, 10, 30, 7, 16, tzinfo=kuala_lumpur).timestamp() * 1000
    )
    thematic_ms = int(
        datetime(2026, 10, 30, 12, 0, tzinfo=kuala_lumpur).timestamp() * 1000
    )
    next_data = {
        "props": {
            "pageProps": {
                "corporateData": [
                    {
                        "nid": 1,
                        "title": "Swiss stocks becoming a haven from AI fears",
                        "created": thematic_ms,
                        "flash": "Global Markets",
                        "alias": "node/1",
                    },
                    {
                        "nid": 823879,
                        "title": (
                            "Tech giants' spending spooks investors and "
                            "drives bond rally"
                        ),
                        "created": created_ms,
                        "flash": "Global Markets",
                        "alias": "node/823879",
                    },
                ]
            }
        }
    }
    html = (
        "<html><body>"
        f'<script id="__NEXT_DATA__" type="application/json">'
        f"{json.dumps(next_data)}"
        "</script>"
        "</body></html>"
    )
    article_link = _parse_the_edge_global_markets_card(html, date(2026, 10, 30))
    assert article_link == {
        "title": "Tech giants' spending spooks investors and drives bond rally",
        "url": "https://theedgemalaysia.com/node/823879",
    }


def test_extract_the_edge_article_text_from_next_data():
    """
    GIVEN an Edge article page __NEXT_DATA__ with HTML content
    WHEN _extract_the_edge_article_text is called
    THEN the article body text is returned without page chrome
    """
    next_data = {
        "props": {
            "pageProps": {
                "data": {
                    "title": "Tech giants spending",
                    "content": (
                        "<div><p>LONDON/SINGAPORE (Oct 30): Tech shares slumped."
                        "</p><p>US bonds surged.</p></div>"
                    ),
                }
            }
        }
    }
    html = (
        "<html><body><nav>Ignore nav</nav>"
        f'<script id="__NEXT_DATA__" type="application/json">'
        f"{json.dumps(next_data)}"
        "</script>"
        "</body></html>"
    )
    assert (
        _extract_the_edge_article_text(html)
        == "LONDON/SINGAPORE (Oct 30): Tech shares slumped.\nUS bonds surged."
    )
