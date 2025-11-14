# Data Sources Documentation

This document lists all external data sources used in the Market Watch project, organized by category.

## Price Data Sources

### - Yahoo Finance

- **Base Source**: https://pypi.org/project/yfinance/
- **URL**: Uses `yfinance` library (no direct URL)
- **Data Type**: Stock prices, FX rates, commodity prices, crypto prices

### - US Treasury Department

- **Base Source**: https://home.treasury.gov/
- **URL**: https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xmlview?data=daily_treasury_yield_curve&field_tdr_date_value={year}
- **Data Type**: US Treasury yields (1M, 2M, 3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 20Y)

### - New York Federal Reserve (NY Fed)

- **Base Source**: https://www.newyorkfed.org/markets/reference-rates/sofr
- **URL**: https://markets.newyorkfed.org/read?productCode=50&eventCodes=520&limit=25&startPosition=0&sort=postDt:-1&format=xml
- **Data Type**: Secured Overnight Financing Rate (SOFR), Effective Federal funds rate (EFFR)

### - Banque de France (Webstat)

- **Base Source**: https://webstat.banque-france.fr/en/
- **URL**: https://webstat.banque-france.fr/export/csv/fr/catalog/{ticker}
- **Data Type**: French interest rates and economic indicators

### - Deutsche Bundesbank

- **Base Source**: https://www.bundesbank.de/en/statistics/time-series-databases/
- **URL**: https://api.statistiken.bundesbank.de/rest/download/BBSSY/{ticker}?format=sdmx&lang=en
- **Data Type**: German government bond yields

### - Bank of Japan (BoJ)

- **Base Source**: https://www.boj.or.jp/statistics/market/short/mutan/index.htm
- **URL**: https://www.boj.or.jp/statistics/market/short/mutan/d_release/{certified}/{year}/{filename}
- **Data Type**: Japanese overnight call rate

### - Japan Bond Trading Co. Ltd. (BB)

- **Base Source**: https://www.bb.jbts.co.jp/en/index.html
- **URL**: https://www.bb.jbts.co.jp/en/historical/main_rate.html
- **Data Type**: Japanese Government Bond yields (40Y, 30Y, 20Y, 10Y, 5Y, 2Y, TDB(1Y), TDB(6M), TDB(3M))

### - Global Rates

- **Base Source**: https://www.global-rates.com/en/
- **URL**: https://www.global-rates.com/en/interest-rates/euribor/{ticker}
- **Data Type**: Euribor rates

## Economic Data Sources

### - INSEE (Institut National de la Statistique et des Études Économiques)

- **Base Source**: https://www.insee.fr/
- **URL**: https://bdm.insee.fr/series/{ticker}/csv?lang=fr&ordre=antechronologique&transposition=donneescolonne&periodeDebut=1&anneeDebut=1977&periodeFin=10&anneeFin=2025&revision=sansrevisions
- **Publication URL**: https://www.insee.fr/fr/agenda-diffusion
- **Data Type**: French economic indicators (GDP, inflation, unemployment, etc.)
- **Documentation**: https://www.insee.fr/fr/statistiques/serie/{ticker}

### - Japan Cabinet Office

- **Base Source**: Not Implemented
- **URL**: Not Implemented
- **Publication URL**: Not Implemented
- **Data Type**: Japanese GDP
- **Documentation**: Not Implemented
