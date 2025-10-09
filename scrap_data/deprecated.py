from datetime import date
from typing import Optional

import requests
from bs4 import BeautifulSoup
from cachetools.func import ttl_cache

from scrap_data.services import _parse_str_decimals_to_float


@ttl_cache(maxsize=128, ttl=10 * 60)
def _scrap_mutan_rate_from_boj(target_date: date) -> Optional[float]:
    """Scrap BoJ website to get Mutan Rate.

    Source: https://www3.boj.or.jp/market/jp/menu_m.htm
    """
    DATA_TYPE = {"prevision": "mp", "certified": "md"}
    response = requests.get(
        f"https://www3.boj.or.jp/market/jp/stat/{DATA_TYPE['certified']}{target_date.strftime('%y%m%d')}.htm"
    )
    if response.status_code != 200:
        if response.status_code != 404:
            response.raise_for_status()
        else:
            response = requests.get(
                f"https://www3.boj.or.jp/market/jp/stat/{DATA_TYPE['prevision']}{target_date.strftime('%y%m%d')}.htm"
            )
            response.raise_for_status()

    soup = BeautifulSoup(response.content, "html.parser")
    raw_text = None
    for strong in soup.find_all("strong"):
        if strong.get_text(strip=True) == "平均":
            parent = strong.parent
            if parent:
                span = parent.find("span")
                if span and span.get_text(strip=True):
                    raw_text = span.get_text(strip=True)
                    break
                full = parent.get_text(" ", strip=True)
                candidate = full.replace("平均", "").strip()
                if candidate:
                    raw_text = candidate
                    break
    if not raw_text:
        return

    raw_text = raw_text.replace("％", "").replace("%", "").strip()
    return _parse_str_decimals_to_float(raw_text)
