"""Shared TypedDicts for news article scrapers."""

from typing import TypedDict


class ArticleLink(TypedDict):
    """Article link dictionnary (listing discovery before body fetch)."""

    title: str
    url: str


class ScrapingResult(TypedDict):
    """Scraping result dictionnary."""

    url: str | None
    title: str | None
    content: str | None
    comment: str | None
