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
