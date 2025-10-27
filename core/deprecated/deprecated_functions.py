# @ttl_cache(maxsize=128, ttl=10 * 60)
# def _get_spanish_yield_curves_from_bank_of_spain(target_date: date) -> dict:
#     """Extract Spanish bond yield curves from Bank of Spain database.

#     Source: https://www.bde.es/wbe/en/estadisticas/
#     """
#     response = requests.get(
#         "https://www.bde.es/webbe/es/estadisticas/compartido/datos/csv/ti_1_3.csv"
#     )
#     df = pd.read_csv(BytesIO(response.content), encoding="latin1", skiprows=0)

#     # First column is the date
#     date_col = df.columns[0]
#     df[date_col] = pd.to_datetime(
#         df[date_col], format="%d %b %Y", errors="coerce"
#     ).dt.date

#     df = df.replace("_", pd.NA)
#     for col in df.columns[1:]:
#         df[col] = pd.to_numeric(df[col], errors="coerce")

#     row = df[df[date_col] == target_date].replace({float("nan"): None})
#     if not row.empty:
#         return row.iloc[0, 1:].to_dict()


# def _get_spanish_yield_from_bank_of_spain(
#     target_date: date, ticker: str
# ) -> Optional[float]:
#     """Infer Spanish yield from Bank of Spain yield curve."""
#     spanish_yield_curve = _get_spanish_yield_curves_from_bank_of_spain(target_date)
#     if spanish_yield_curve:
#         return spanish_yield_curve.get(ticker)


# @ttl_cache(maxsize=128, ttl=10 * 60)
# def _scrap_mutan_rate_from_boj(target_date: date) -> Optional[float]:
#     """Scrap BoJ website to get Mutan Rate.

#     Source: https://www3.boj.or.jp/market/jp/menu_m.htm
#     """
#     DATA_TYPE = {"prevision": "mp", "certified": "md"}
#     response = requests.get(
#         f"https://www3.boj.or.jp/market/jp/stat/{DATA_TYPE['certified']}{target_date.strftime('%y%m%d')}.htm"
#     )
#     if response.status_code != 200:
#         if response.status_code != 404:
#             response.raise_for_status()
#         else:
#             response = requests.get(
#                 f"https://www3.boj.or.jp/market/jp/stat/{DATA_TYPE['prevision']}{target_date.strftime('%y%m%d')}.htm"
#             )
#             response.raise_for_status()

#     soup = BeautifulSoup(response.content, "html.parser")
#     raw_text = None
#     for strong in soup.find_all("strong"):
#         if strong.get_text(strip=True) == "平均":
#             parent = strong.parent
#             if parent:
#                 span = parent.find("span")
#                 if span and span.get_text(strip=True):
#                     raw_text = span.get_text(strip=True)
#                     break
#                 full = parent.get_text(" ", strip=True)
#                 candidate = full.replace("平均", "").strip()
#                 if candidate:
#                     raw_text = candidate
#                     break
#     if not raw_text:
#         return

#     raw_text = raw_text.replace("％", "").replace("%", "").strip()
#     return _parse_str_decimals_to_float(raw_text)
