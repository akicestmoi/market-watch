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
- **URL**: https://bdm.insee.fr/series/{ticker}/csv?lang=fr&ordre=antechronologique&anneeDebut=2010&anneeFin={year}&revision=sansrevisions
- **Publication URL**: https://www.insee.fr/fr/agenda-diffusion
- **Data Type**: French economic indicators (confidence, HICP, industrial raw materials, retail sales, IPI, labour, housing, GDP & components, Maastricht debt, external balance, etc.)
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md) — what each seeded series measures, why it was chosen, and INSEE methodology links
- **Per-series page**: https://www.insee.fr/en/statistiques/serie/{ticker}

### - Eurostat

- **Base Source**: https://ec.europa.eu/eurostat
- **URL**: https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}
- **Publication URL**: https://ec.europa.eu/eurostat/news/release-calendar/ (JSON feed: https://ec.europa.eu/eurostat/o/calendars/eventsJson — event times are UTC; UI labels Europe/Luxembourg)
- **Data Type**: Eurostat Statistics API series in `EUROSTAT_SERIES_TEMPLATES` — seed ticker is the series ID (e.g. `namq_10_gdp`); geo comes from indicator `location` (same codes as Eurostat, except `EU` → `EA` via `EUROSTAT_GEO_FOR_EU_LOCATION`). Covers euro-area and DE/ES/IT HICP/GDP/debt/production/sales/labour/housing/trade, plus FR/DE/ES/IT Maastricht deficit/surplus from [`tec00127`](https://ec.europa.eu/eurostat/databrowser/view/tec00127/default/table) (`PC_GDP` and `MIO_EUR`)
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - FRED (Federal Reserve Bank of St. Louis)

- **Base Source**: https://fred.stlouisfed.org/
- **URL**: https://api.stlouisfed.org/fred/series/observations?series_id={ticker}&api_key={FRED_API_KEY}&file_type=json
- **Publication URL**: https://api.stlouisfed.org/fred/release/dates?release_id={id}&api_key={FRED_API_KEY}&file_type=json&include_release_dates_with_no_data=true
- **Auth**: `FRED_API_KEY` in `.env` / `core.settings`
- **Data Type**: US economic indicators redistributed by FRED (real GDP and expenditure components, net exports, federal debt outstanding / % of GDP, federal surplus/deficit outstanding / % of GDP, CPI, retail sales, industrial production, unemployment, payrolls, FHFA HPI, University of Michigan consumer sentiment)
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - Japan Cabinet Office (ESRI / SNA)

- **Base Source**: https://www.esri.cao.go.jp/en/sna/menu.html
- **URL**: Latest quarterly estimates CSV resolved from https://www.esri.cao.go.jp/en/sna/data/sokuhou/files/{year}/toukei_{year}.html → release menu → `gaku-jk*.csv` (real SA expenditure levels; ticker selects column) or `gaku-mk*.csv` (nominal SA GDP for debt ratio). General government gross debt from https://www.esri.cao.go.jp/en/sna/sddsplus/sddsplus_top.html → `tables/ggd.xlsx`. Annual general-government net lending from https://www.esri.cao.go.jp/en/sna/kakuhou/kakuhou_top.html → latest `*annual_report_e.html` → `tables/*s18_en.xlsx` (calendar-year amount and % of GDP sheets)
- **Publication URL**: Not implemented (schedule scrape still pending)
- **Data Type**: Japanese quarterly real SA GDP and demand components (household / government consumption, GFCF, exports, imports, net exports); general government gross debt outstanding and % of annualized nominal SA GDP; annual general-government net lending (+) / net borrowing (−) outstanding and % of GDP
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - Statistics of Japan (e-Stat Dashboard)

- **Base Source**: https://dashboard.e-stat.go.jp/en/
- **URL**: https://dashboard.e-stat.go.jp/api/1.0/Json/getData?IndicatorCode={ticker}&Lang=EN&RegionCode=00000&…
- **Publication URL**: Not implemented (schedule scrape still pending)
- **Data Type**: Official Japanese series redistributed by the Statistics Dashboard (CPI and unemployment from the Statistics Bureau; industrial production and retail sales from METI / Current Survey of Commerce). Configured series: `STAT_OF_JP_SERIES_BY_TICKER` (ticker → IndicatorCode + filters)
- **Portal**: https://www.e-stat.go.jp/en · https://www.stat.go.jp/english/ · https://www.meti.go.jp/english/
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - MLIT (Ministry of Land, Infrastructure, Transport and Tourism)

- **Base Source**: https://www.mlit.go.jp/en/
- **URL**: Nationwide Residential Property Price Index Excel resolved from https://www.mlit.go.jp/totikensangyo/totikensangyo_tk5_000085.html (sheet `全国Japan季節調整`)
- **Publication URL**: Not implemented (schedule scrape still pending)
- **Data Type**: Japan Residential Property Price Index (nationwide, seasonally adjusted, 2010 = 100)
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - Bank of Japan (Tankan)

- **Base Source**: https://www.boj.or.jp/en/statistics/tk/index.htm
- **URL**: Latest summary ZIP resolved from https://www.boj.or.jp/en/statistics/tk/index.htm (`tkaYYMM.zip` under `gaiyo/YYYY/` → `GA_E1.xlsx`)
- **Publication URL**: Not implemented (schedule scrape still pending)
- **Data Type**: Tankan Business Conditions DI (current-survey actual) for Large / Medium / Small × Manufacturing / Nonmanufacturing (`BOJ_TANKAN_SERIES_BY_TICKER`). Point-in-time release — historical ingestion only stores the latest survey observation
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)
