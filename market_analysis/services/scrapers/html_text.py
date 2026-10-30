"""Shared HTML stripping and main-text extraction for news article scrapers."""

from bs4 import BeautifulSoup, Tag

_STRIP_TAGS = ("script", "style", "noscript", "svg", "iframe")
_STRIP_SELECTORS = (
    "nav",
    "header",
    "footer",
    "aside",
    "[role='navigation']",
    "[role='banner']",
    "[role='contentinfo']",
)


def _does_class_name_contain_article(class_name: str) -> bool:
    """Return True when a CSS class token contains ``article``."""
    return "article" in class_name.lower()


def extract_main_text(html: str) -> str:
    """Extract readable article text with BeautifulSoup."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(_STRIP_TAGS):
        if isinstance(tag, Tag):
            tag.decompose()
    for selector in _STRIP_SELECTORS:
        for tag in soup.select(selector):
            if isinstance(tag, Tag):
                tag.decompose()

    root_candidate = (
        soup.select_one(".article-main")
        or soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.find("article")
        or soup.find(class_=_does_class_name_contain_article)
        or soup.body
        or soup
    )
    root = root_candidate if isinstance(root_candidate, Tag) else soup
    text = root.get_text("\n", strip=True)
    lines = [ln for ln in (line.strip() for line in text.splitlines()) if ln]
    return "\n".join(lines).strip()
