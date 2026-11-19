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
- **URL**: https://webstat.banque-france.fr/export/csv/fr/catalog/{dataset}/{series_key}
- **Data Type**: French interest rates (market overview) and national business-survey series (economic overview)

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

Seeded series live in `economic_overview/data_sources/economic_data.json` (source enum + ticker). Values are scraped via `SOURCE_SCRAP_MAP`; release dates via `PUBLICATION_SOURCE_MAP` in `economic_overview/services/publication_update.py`.

**Publication schedules**

Seed field `publication_schedule_mode` chooses how release slots are maintained (`economic_overview/services/publication_update.py`):

| Mode on the seed | Meaning |
| --- | --- |
| *(empty)* — calendar | Scrape upcoming dated slots via `PUBLICATION_SOURCE_MAP` for that source. Matched on `technical_name` (and location for Trading Economics). **Publication URL** lines below apply only to this mode. |
| `MONTHLY_UPDATE` | **No calendar scrape**. Celery still polls on business days; `publication_update.run_monthly_publication_update` only refreshes values on calendar day 1. |

**`MONTHLY_UPDATE` product families today** (64 seeds): Census ACS Gini / Palma (revenue); Eurostat / StatJP inequality (Gini / Palma revenue); ECB DWA wealth Gini / top-10 share (FR/DE/ES/IT); WID wealth Gini / top-10 share (US/JP); IMF Fiscal Monitor primary balance; all Banque de France economic seeds (capacity, orders, SC1 cash); MLIT RPPI; Japan Cabinet Office SDDS Plus GGO / GGD / financing / COFOG / unwired corporate stubs.

**Derived schedules** (empty mode, not a separate seed flag): ratios and difference tickers listed in `DERIVED_SCHEDULE_*` take the **latest** among their input series’ current/next slots once every input has a schedule. Some fall back to a shared calendar `technical_name` (`DERIVED_SCHEDULE_CALENDAR_TECHNICAL_NAME_BY_TICKER`).

Empty calendar scrape results are normal when a product has no dated slot in the lookahead window (e.g. sparse annual FIES while still on calendar mode, some OECD EO windows).

### - INSEE (Institut National de la Statistique et des Études Économiques)

- **Base Source**: https://www.insee.fr/
- **URL**: https://bdm.insee.fr/series/{ticker}/csv?lang=fr&ordre=antechronologique&anneeDebut=2010&anneeFin={year}&revision=sansrevisions
- **Publication URL**: https://www.insee.fr/fr/agenda-diffusion (POST JSON; match English `famille.facetteConjoncture.libelleEn` to seed `technical_name`)
- **Data Type**: French economic indicators (confidence, national CPI, retail sales, IPI, labour, housing, GDP & components, Maastricht debt, external balance, etc.)
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md) — what each seeded series measures, plus methodology links
- **Per-series page**: https://www.insee.fr/en/statistiques/serie/{ticker}

### - Eurostat

- **Base Source**: https://ec.europa.eu/eurostat
- **URL**: https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}
- **Publication URL**: https://ec.europa.eu/eurostat/news/release-calendar/ (JSON feed: https://ec.europa.eu/eurostat/o/calendars/eventsJson — event times are UTC; UI labels Europe/Luxembourg)
- **Data Type**: Eurostat Statistics API series in `EUROSTAT_SERIES_TEMPLATES` — seed ticker is the series ID (e.g. `namq_10_gdp`); geo comes from indicator `location` (same codes as Eurostat, except `EU` → `EA21` via `EUROSTAT_GEO_FOR_EU_LOCATION`, overridable per template). Covers euro-area and DE/ES/IT HICP/GDP/debt/production/sales/labour/housing/trade, household saving / NFC profit & investment rates ([`nasq_10_ki`](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_ki/default/table)), capacity utilisation ([`ei_bsin_q_r2`](https://ec.europa.eu/eurostat/databrowser/view/ei_bsin_q_r2/default/table)), current account % GDP ([`tipsbp20`](https://ec.europa.eu/eurostat/databrowser/view/tipsbp20/default/table)), quarterly general-government accounts ([`gov_10q_ggnfa`](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggnfa/default/table) — internal aliases `gov_10q_ggnfa_balance` / `_revenue` / `_expenditure` / `_interest_mio` → `na_item` B9 / TR / TE / D41PAY; FR revenue SCA drill-down taxes = D2REC+D5REC+D91REC, social = D61REC, other = TR − taxes − D61), annual COFOG expenditure ([`gov_10a_exp`](https://ec.europa.eu/eurostat/databrowser/view/gov_10a_exp/default/table) — `gov_10a_exp_gf01`…`gf10`), quarterly financial accounts ([`gov_10q_ggfa`](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggfa/default/table) — F / F3 / F4 LIAB+ASS TRN consolidated), GVA by NACE A10 industry ([`namq_10_a10`](https://ec.europa.eu/eurostat/databrowser/view/namq_10_a10/default/table) — `namq_10_a10_*` seed tickers, real SCA chain-linked). Derived real household GDHI (`nasq_10_nf_tr_b6g_real`) divides current-price B6G by the HH+NPISH FCE PD20 deflator. Household saving / consumption ratios use `B8G` / `P.31` over `B6G + D8`.
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - BEA (Bureau of Economic Analysis)

- **Base Source**: https://www.bea.gov/
- **URL**: https://apps.bea.gov/api/data/ — NIPA government expenditures by function with `datasetname=NIPA`, `TableName=T31600`, `Frequency=A` (one cached table download serves every `bea_t31600_*` ticker). GDP-by-industry industry-profitability panels use `datasetname=GDPbyIndustry` (tables 15 / 6 / 1 for gross output, GOS, value added) — not seeded in `economic_data.json`; see **Industry profitability** below
- **Publication URL** (calendar seeds): Table 3.16 shares the BEA quarterly GDP family → FRED release calendar id `53` (`Gross Domestic Product`, 08:30 ET). Industry-profitability GDPbyIndustry panels have no publication-schedule seeds
- **Auth**: `BEA_API_KEY` in `.env` / `core.settings`
- **Data Type**: Annual government current expenditures by function (NIPA Table 3.16, millions → stored billions): `bea_t31600_total` (line 1, Annual Government Expenditures, fixed `vsGDP`) and nine US-named function children (`bea_t31600_*`, fixed `Rel YoY`)
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - FRED (Federal Reserve Bank of St. Louis)

- **Base Source**: https://fred.stlouisfed.org/
- **URL**: https://api.stlouisfed.org/fred/series/observations?series_id={ticker}&api_key={FRED_API_KEY}&file_type=json
- **Publication URL**: https://api.stlouisfed.org/fred/release/dates?release_id={id}&api_key={FRED_API_KEY}&file_type=json&include_release_dates_with_no_data=true
- **Auth**: `FRED_API_KEY` in `.env` / `core.settings`
- **Data Type**: US (and selected international) series redistributed by FRED — NIPA / personal income & outlays, household & NPISH loan liabilities (`HNOLL`, millions → stored billions), capacity utilisation, current account, consumer & C&I credit, federal receipts/expenditures/interest, general-government revenue split (`W054RC1Q027SBEA` taxes, `W782RC1Q027SBEA` social contributions, derived `gg_other_revenue` = `GRECPT` − both), Z.1 S.13 financial-account transactions (`BOGZ1FA374190005Q` / `…122005Q` / `…123005Q` / `…090005Q`, millions → stored billions; derived `z1_gg_financing_account` and `z1_gg_other_liability_transactions`), and BIS real broad effective exchange rates for US / FR / JP / euro area. Derived breakdown residuals live in `FRED_GOVERNMENT_BREAKDOWN_RESIDUAL_BY_TICKER` and subtract components one at a time so only periods every input has are kept
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - Japan Cabinet Office (ESRI / SNA)

- **Base Source**: https://www.esri.cao.go.jp/en/sna/menu.html
- **URL**: Latest quarterly estimates CSV resolved from https://www.esri.cao.go.jp/en/sna/data/sokuhou/files/{year}/toukei_{year}.html → release menu → `gaku-jk*.csv` (real SA expenditure levels; ticker selects column) or `gaku-mk*.csv` (nominal SA GDP for debt ratio). General government gross debt from https://www.esri.cao.go.jp/en/sna/sddsplus/sddsplus_top.html → `tables/ggd.xlsx`. Quarterly General Government Operations from the same SDDS Plus page → `tables/ggo.xlsx` (Revenue / Taxes / Social contributions / Expenses / Interest / Net lending/borrowing, plus financial-account Net acquisition of financial assets / Net incurrence of liabilities for Japan government financing; scrapers skip `NA` for lagging non-financial quarters). Annual general-government outlays by function (COFOG) from Annual SNA Supporting Table 7 (https://www.esri.cao.go.jp/en/sna/kakuhou/kakuhou_top.html) → `https://www.esri.cao.go.jp/en/sna/data/kakuhou/files/{year}/tables/{year}s7_en.xlsx` (one sheet per fiscal year; the scraper GETs the current calendar year back through `JP_CAO_COFOG_URL_LOOKBACK_YEARS` years and uses the newest URL that returns a workbook). Household disposable income / saving / consumption from https://www.esri.cao.go.jp/jp/sna/data/data_list/kakei/files/files_kakei.html → latest `kakei_*.xlsx` (SA sheet: DI col I, Consumption of households col K, Saving col L, real DI col P; saving / consumption ratios derived). Consumer Confidence Survey SA from https://www.esri.cao.go.jp/en/stat/shouhi/shouhi2.xlsx (`shouhi_cci_sa` headline col 5; `shouhi_employment_sa` col 11). Machinery Orders historical by-sectors workbook from https://www.esri.cao.go.jp/jp/stat/juchu/juchu.html → latest `YYMMchouki-1.xlsx` (SA monthly private excl. volatile orders, million yen → stored billion yen)
- **Publication URL**: Calendar seeds (GDP flash, kakei DI/saving, machinery orders, consumer confidence) use the shared [e-Stat release calendar](https://www.e-stat.go.jp/release-calendar) via `ESTAT_SCHEDULE_MATCH_BY_TECHNICAL_NAME`. SDDS Plus GGO / GGD / financing, annual COFOG, and unwired corporate stubs are `MONTHLY_UPDATE` (no e-Stat scrape)
- **Data Type**: Japanese quarterly real SA GDP and demand components (household / government consumption, GFCF, exports, imports, net exports; Net Exports default `Rel YoY`); household nominal/real disposable income, nominal consumption, and nominal saving (kakei SA sheet); derived saving ratio (saving ÷ DI, because the workbook % is truncated) and consumption ratio (consumption ÷ DI); general government gross debt outstanding and % of annualized nominal SA GDP; quarterly GGO net lending / revenue (plus taxes, social contributions, and derived `ggo_other_revenue`) / expense / interest (Government Primary Balance (IMF) remains IMF); quarterly NSA GGO financing — `ggo_net_incurrence_liabilities`, `ggo_net_acquisition_financial_assets`, derived `ggo_financing_account` = liabilities − assets (recap shows year-to-date same-period vsGDP; BoJ FOF RELATED instrument detail under Net Liabilities); annual COFOG total outlays (`esri_cofog_total`) and GF01–GF10 children (`esri_cofog_gf01`…`gf10`, fiscal year stored at `date(FY, 1, 1)`); Consumer Confidence Index SA (`shouhi_cci_sa`, 0–100 with 50 = neutral) and Employment perception SA (`shouhi_employment_sa`); Machinery Orders private excl. volatile (`machinery_orders_private_ex_volatile_sa`, monthly SA, billion yen). Japan Net Operating Surplus / Gross Capital Share remain unwired stubs on the recap (no scrape)
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - ECB Data Portal (SDMX)

- **Base Source**: https://data.ecb.europa.eu/
- **URL**: https://data-api.ecb.europa.eu/service/data/{dataflow}/{series_key}?format=csvdata
- **Publication URL**: https://www.ecb.europa.eu/press/calendars/statscal/eaa/html/stprfi.en.html (QSA household / NFC press slots; Europe/Berlin). DWA wealth seeds are `MONTHLY_UPDATE` (no DWA calendar scrape)
- **Data Type**: Quarterly sector accounts (QSA) — published household + NPISH loans as % of annualised gross disposable income (`qsa_hh_loans_to_gdi`; REF_AREA from indicator location, `EU` → `I9`). Used for Household Debt Ratio in FR/DE/ES/IT/EU (Eurostat F4 remains the Nominal Household Debt stock only). Distributional Wealth Accounts (DWA) — household net-wealth Gini (`ecb_dwa_wealth_gini`) and top-10 wealth share (`ecb_dwa_top10_wealth_share`); annual seeds keep the Q4 observation
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - IMF (DataMapper + SDMX)

- **Base Source**: https://www.imf.org/external/datamapper/ · https://data.imf.org/
- **URL (DataMapper)**: https://www.imf.org/external/datamapper/api/v1/{indicator}
- **URL (IL SDMX)**: https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/IL/+/{COUNTRY}.{INDICATOR}.USD.M
- **Publication URL**: International Liquidity (FX reserves) follows FRED release **International Reserves** (calendar mode). Fiscal Monitor primary-balance seeds are `MONTHLY_UPDATE` (no Fiscal Monitor calendar scrape)
- **Auth**: None (public JSON APIs)
- **Data Type**: Fiscal Monitor / WEO via DataMapper — general-government primary balance % of GDP (`GGXONLB_G01_GDP_PT`); International Liquidity via SDMX — total reserves excluding gold (`RXF11_REVS`, monthly, stored values in millions of USD after SCALE÷10⁶). Area / COUNTRY from indicator location (`US`→`USA`, `EU`→`EURO` for DataMapper only)
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - OECD (SDMX)

- **Base Source**: https://data-explorer.oecd.org/
- **URL**: Economic Outlook `…/OECD.ECO.MAD,DSD_EO@DF_EO/{REF_AREA}.{MEASURE}.A`; Short-term indicators `…/OECD.SDD.STES,DSD_STES@DF_INDSERV/{series_key}`; Productivity growth rates `…/OECD.SDD.TPS,DSD_PDB@DF_PDB_GR/{series_key}` (with DBnomics mirror fallback when OECD SDMX returns HTTP 500)
- **Publication URL**: EO full-volume Paris wall-time slots in `OECD_ECONOMIC_OUTLOOK_PARIS_RELEASE_DATETIMES` (live media-advisory HTML is often blocked). Japan MEI retail volume follows e-Stat commerce preliminary releases (`Main Economic Indicators` → 商業動態統計調査)
- **Auth**: None (public SDMX JSON API)
- **Data Type**: Annual EO output gap (`eo_gap` → `GAP`); Japan retail trade volume (`JPN.M.TOVM.IX.G47.Y._Z._Z.N`, monthly index 2015=100, SCA). REF_AREA from indicator location for EO (`US`→`USA`, `JP`→`JPN`, …)
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - Statistics of Japan (e-Stat Dashboard + FIES)

- **Base Source**: https://dashboard.e-stat.go.jp/en/ · https://www.stat.go.jp/english/data/sousetai/
- **URL**: Dashboard `https://dashboard.e-stat.go.jp/api/1.0/Json/getData?IndicatorCode={ticker}&…`; FIES Table 3 `https://www.stat.go.jp/english/data/sousetai/{year}n/zuhyou/s03.xls` (through 2024) / `vs03.xlsx` (from 2025)
- **Publication URL**: Calendar seeds (CPI / LFS / IIP) use https://www.e-stat.go.jp/release-calendar via `ESTAT_SCHEDULE_MATCH_BY_TECHNICAL_NAME`. FIES Gini / Palma (revenue) are `MONTHLY_UPDATE` (irregular annual products; no dated scrape)
- **Data Type**: Dashboard IndicatorCode series (`STAT_OF_JP_SERIES_BY_TICKER`) — CPI, unemployment, employment, industrial production. Inequality: FIES-derived `fies_gini` / `fies_palma` from Table 3 total-household yearly-income deciles (revenue)
- **Portal**: https://www.e-stat.go.jp/en · https://www.stat.go.jp/english/ · https://www.meti.go.jp/english/
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - US Census Bureau

- **Base Source**: https://www.census.gov/
- **URL**: ACS Data API `https://api.census.gov/data/{year}/acs/acs1?get=NAME,B19083_001E&for=us:1&key={CENSUS_API_KEY}`; ACS 1-year housing PUMS zip `https://www2.census.gov/programs-surveys/acs/data/pums/{year}/1-Year/csv_hus.zip`
- **Publication URL**: ACS Gini / Palma (revenue) seeds are `MONTHLY_UPDATE` (no ACS release-schedule scrape). Calendar helper target when used: https://www.census.gov/programs-surveys/acs/news/data-releases/2025/release-schedule.html
- **Auth**: `CENSUS_API_KEY` in `.env` / `core.settings` (required for ACS Gini; PUMS FTP needs no key)
- **Data Type**: US Gini (`acs_b19083`, ACS B19083 ×100) and Palma (`acs_pums_palma`, weighted PUMS top 10% / bottom 40% household money income) — revenue inequality
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - World Inequality Database (WID)

- **Base Source**: https://wid.world/
- **URL**: Bulk country CSV `https://wid.world/bulk_download/WID_data_{country_code}.csv` (`US`, `JP`)
- **Publication URL**: Wealth seeds are `MONTHLY_UPDATE` (no WID release-calendar scrape)
- **Auth**: None (public bulk CSV)
- **Data Type**: Net personal wealth Gini (`wid_wealth_gini` ← `ghweal992j` p0p100 ×100) and top-10 wealth share (`wid_top10_wealth_share` ← `shweal992j` p90p100 ×100)
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - METI (Ministry of Economy, Trade and Industry)

- **Base Source**: https://www.meti.go.jp/statistics/tyo/syoudou/result-2/index.html · https://www.meti.go.jp/english/statistics/tyo/iip/
- **URL**: e-Stat file downloads — Current Survey of Commerce `h2slt51j.xlsx` (`statInfId=000031387999`); Indices of Production Capacity and Operating Ratio monthly SA `b2020_ngsm1j.xlsx` (`statInfId=000040067191`, sheet `稼働率Ｓ`, Manufacturing total)
- **Publication URL**: https://www.e-stat.go.jp/release-calendar — retail commerce → 商業動態統計調査; operating ratio follows the preliminary IIP release that updates the capacity workbook
- **Data Type**: Japan Retail Sales — nominal retail trade sales-value index, SA, 2020 = 100 (`retail_sales_index_sa`); Japan Operating Ratio Index — manufacturing SA operating ratio, 2020 = 100 (`operating_ratio_mfg_sa`, e-Stat stats code `00550320`)
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - Banque de France (economic series)

- **Base Source**: https://webstat.banque-france.fr/en/
- **URL**: https://webstat.banque-france.fr/export/csv/fr/catalog/{dataset}/{series_key}
- **Publication URL**: Seeds are `MONTHLY_UPDATE`. Calendar helper when used: EMC manufacturing survey cards at https://www.banque-france.fr/fr/publications-et-recherche/nos-principales-publications/enquete-mensuelle-de-conjoncture (08:45 Europe/Paris). SC1 debt-security series have no dated public calendar entry.
- **Data Type**: France Capacity Utilisation — manufacturing average capacity utilisation rate, monthly SA / CVS percent (`CONJ.M.N01.S.IN.000CZ.TUTSM000.10`); France New Business Orders — manufacturing *solde d'opinion* on MoM change in overall new orders received, monthly SA / CVS (`CONJ.M.N01.S.IN.000CZ.CRTEM100.10`; **Neutral: 0**; above 0 = more firms report rising orders than falling; not a euro amount); France financing account — Eurostat `gov_10q_ggfa` Net Liabilities − Net Assets (F LIAB − F ASS); BdF SC1 gross issuance / derived redemptions are RELATED cash detail under Net Debt Securities (F.3) only
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - University of Michigan (Surveys of Consumers)

- **Base Source**: https://data.sca.isr.umich.edu/
- **URL**: CSV export from https://data.sca.isr.umich.edu/data-archive/mine.php (`table` + `format=Comma-Separated (CSV)`)
- **Publication URL**: FRED release **Surveys of Consumers** (id `91`); local clock 10:00 ET
- **Data Type**: Employment Confidence — Table 30 Expected Change in Unemployment During the Next Year Relative index (`sca_table_30`; 100 = neutral)
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - Conference Board (CEO Confidence)

- **Base Source**: https://www.conference-board.org/topics/CEO-Confidence
- **URL**: PR Newswire Conference Board news list → CEO Confidence release articles (`ceo_confidence`)
- **Publication URL**: Conference Board CEO Confidence topic page (next release only; 06:00 America/New_York, matching PR Newswire embargo stamps)
- **Data Type**: Measure of CEO Confidence™ quarterly index (**Neutral: 50**)
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - ISM (Report On Business PMI)

- **Base Source**: https://www.ismworld.org/supply-management-news-and-reports/reports/ism-pmi-reports
- **URL (recent)**: https://www.prnewswire.com/news/institute-for-supply-management/ (title embeds `Manufacturing/Services PMI at X%; Month Year`)
- **URL (legacy Manufacturing)**: https://www.forecasts.org/data/data/NAPM.htm (history through 2014-08; merge under `ism_manufacturing_pmi`)
- **Publication URL**: https://www.ismworld.org/supply-management-news-and-reports/reports/rob-report-calendar/ (10:00 ET). Live HTML is often blocked; published 2026 day table lives in `ISM_2026_RELEASE_DAY_BY_MONTH`
- **Data Type**: Manufacturing PMI (`ism_manufacturing_pmi`) and Services PMI (`ism_services_pmi`) composites (**Neutral / threshold: 50**). Manufacturing may have a gap between the forecasts.org cutoff and the earliest PR Newswire title retained on the listing pages.
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - Trading Economics (S&P Global PMI)

- **Base Source**: https://tradingeconomics.com (pages credit S&P Global)
- **URL**: Country PMI pages → embedded chart auth → `https://charts-api.tradingeconomics.com/economics/{symbol}?span=max` (payload is XOR + gzip; public history ≈ last 3 years)
- **Publication URL**: https://www.pmi.spglobal.com/Public/Release/ReleaseDates?language=en (final Manufacturing / Services / Composite UTC clocks; weekday-rule fallback when HTML is blocked)
- **Data Type**: S&P Composite / Manufacturing / Services PMI for US, France, Japan (`us_sp_*` / `fr_sp_*` / `jp_sp_*`; **Neutral / threshold: 50**)
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - NAHB (Housing Market Index)

- **Base Source**: https://www.nahb.org/news-and-economics/housing-economics/indices/housing-market-index
- **URL**: Latest `t2-national-hmi-history-*.xls` resolved from the HMI page (`nahb_hmi`)
- **Publication URL**: https://www.nahb.org/news-and-economics/housing-economics/indices/nahb-wells-fargo-housing-market-index-release-dates (10:00 ET)
- **Data Type**: NAHB/Wells Fargo National Housing Market Index, monthly SA, 0–100 (**Neutral / midpoint: 50**)
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - MLIT (Ministry of Land, Infrastructure, Transport and Tourism)

- **Base Source**: https://www.mlit.go.jp/en/
- **URL**: Nationwide Residential Property Price Index Excel resolved from https://www.mlit.go.jp/totikensangyo/totikensangyo_tk5_000085.html (sheet `全国Japan季節調整`)
- **Publication URL**: RPPI seeds are `MONTHLY_UPDATE` (no calendar scrape — official release remains postponed)
- **Data Type**: Japan Home Prices — nationwide SA Detached House (`detached_house_sa`, col 8) and Condominiums (`condominiums_sa`, col 11), 2010 = 100
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - Bank of Japan (Tankan + Flow of Funds + CGPI / SPPI)

- **Base Source**: https://www.boj.or.jp/en/statistics/tk/index.htm · https://www.stat-search.boj.or.jp/info/dload_en.html · https://www.stat-search.boj.or.jp/
- **URL (Tankan)**: Latest summary ZIP resolved from https://www.boj.or.jp/en/statistics/tk/index.htm (`tkaYYMM.zip` under `gaiyo/YYYY/` → `GA_E1.xlsx`)
- **URL (FOF)**: https://www.stat-search.boj.or.jp/info/fof2_en.zip → `ff_dl_fof_quarterly_en.csv` (period labels `YYYY0Q`)
- **URL (CGPI / PPI)**: https://www.stat-search.boj.or.jp/api/v1/getDataCode?db=PR01&code=PRCG20_2200000000&lang=en&format=json
- **URL (SPPI)**: https://www.stat-search.boj.or.jp/api/v1/getDataCode?db=PR02&code=PRCS20_5200000000&lang=en&format=json
- **Publication URL**: https://www.boj.or.jp/en/statistics/outline/tkohyos.xlsx (match `BOJ_SCHEDULE_SERIES_TITLE_BY_TECHNICAL_NAME`; 08:50 Asia/Tokyo). Also covers shared Balance of Payments slots used by MOF BoP
- **Data Type**: Tankan Business Conditions DI (current-survey actual) for Large / Medium / Small × Manufacturing / Nonmanufacturing (`BOJ_TANKAN_SERIES_BY_TICKER`); Flow of Funds household loan liabilities (`fof_hh_loans` → `FOF_FFAS430L200`, 億円 → billion yen); Flow of Funds general-government RELATED instrument flows under GGO Net Liabilities (`fof_gg_debt_securities` → `FOF_FFAF420L300`, `fof_gg_loans` → `FOF_FFAF420L200`, derived `fof_gg_other_liabilities` = (L900−L700) − L300 − L200); read from one cached flat-file download (Japan financing identity itself stays on ESRI SDDS Plus GGO); derived Household Debt Ratio (`hh_debt_ratio` = FOF loans ÷ ESRI `kakei_nominal_di` SAAR); Manufacturing Producer Price Index (`PRCG20_2200000000` → Corporate Goods Price Index, all commodities, CY2020=100); Services Producer Price Index (`PRCS20_5200000000` → SPPI all items, CY2020=100)
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - Ministry of Finance (Japan) — Balance of Payments

- **Base Source**: https://www.mof.go.jp/english/policy/international_policy/reference/balance_of_payments/ebpnet.htm
- **URL**: https://www.mof.go.jp/policy/international_policy/reference/balance_of_payments/bp_trend/bpnet/sbp/s-a/6s-a-1.csv (table `6s-a-1`, seasonally adjusted quarterly current account)
- **Publication URL**: BoJ statistics release workbook (shared Balance of Payments slots; MOF publishes the CSV)
- **Auth**: None (public CSV; Shift_JIS / cp932)
- **Data Type**: Japan current account and components — current account (`mof_bop_ca`), goods & services (`mof_bop_gs`), primary income (`mof_bop_in1`), secondary income (`mof_bop_in2`). Source unit is 100 million yen (億円); stored values are billion yen (÷ 10), period flow not annualized
- **Series documentation**: [`INDICATORS.md`](INDICATORS.md)

### - Industry profitability (charts only — not in `economic_data.json`)

Annual industry ranking panels on Economic Charts (`IndustryProfitabilityModel`), not seeded as recap/series tickers.

| Location | Source | Scraper | What |
| --- | --- | --- | --- |
| FR | Eurostat SBS | `eurostat.py` | NACE Rev. 2 division turnover / GOS / GVA (`sbs_na_*_r2` through 2020, `sbs_ovw_act` from 2021), m€ |
| US | BEA GDPbyIndustry | `bea_industry.py` | Finest published industry lines — gross output (table 15), GOS (table 6), value added (table 1), $bn |
| JP | MOF e-Stat + ESRI | `mof.py` / `jp_cabinet_office.py` | MOF corporate survey sales & operating profit (百万円); Contribution uses ESRI SNA economic-activity GVA (名目原系列) — **two different industry maps** |

- **Auth**: BEA needs `BEA_API_KEY`; MOF e-Stat needs `ESTAT_APP_ID`
- **e-Stat API**: `https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData` (`stat_of_jp.py`)
- **Publication schedules**: none — charts-only panels are not in `PUBLICATION_SOURCE_MAP` / day events
- **Series / panel documentation**: [`INDICATORS.md`](INDICATORS.md) (Industry profitability)

### - Trade rankings (charts only — not in `economic_data.json`)

Annual customs trade ranking panels on Economic Charts (`TradeRankingModel` with `TradeTypeChoices`), not BoP / GDP trade series. Both trade types store Top-N `PRODUCT` / `PARTNER` plus `PRODUCT_PARTNER` cells; the energy type restricts the product universe via `TRADE_RANKING_PROFILE_BY_TYPE`.

| Location | Source | Scraper | What |
| --- | --- | --- | --- |
| FR | Eurostat Comext `DS-045409` | `eurostat_comext.py` | Annual HS × partner values in EUR; Top-N product (vs WORLD) and ISO-2 country partners |
| US | Census International Trade HS | `census_trade.py` | December YTD as annual; imports `GEN_VAL_YR`, exports `ALL_VAL_YR`; country partners only (OECD / regional groups dropped) |
| JP | Japan Customs via e-Stat | `jp_customs.py` | Principal Commodity by Country tables in `JP_CUSTOMS_PRINCIPAL_COMMODITY_TABLES` (update when Customs republishes) |

- **Windows**: per `TRADE_RANKING_PROFILE_BY_TYPE` (merchandise: 5y / Top-20 product & partner; energy: 10y / Top-10); scheduled refresh re-scrapes last 2 years
- **Auth**: Census needs `CENSUS_API_KEY`; JP e-Stat needs `ESTAT_APP_ID`; Comext is public
- **Energy product set** (profile): crude `2709`, refined `2710`, LNG `271111`, pipeline gas `271121`, bituminous coal `270112`, electricity `271600`, propane `271112`, other coal `270119`, butanes `271113`, other coal-tar oils `270799`
- **Japan 概況品 aliases**: crude `30301000`, refined products `30303000`, LNG `30501030`, coking/bituminous coal `30101030`, other coal `30101050`, LPG→propane `30501010`, mineral tar/chemicals→`270799` via `50300000`. No JP line for pipeline gas `271121`, electricity `271600`, or butanes `271113` alone (LPG is one bucket)
- **Publication schedules**: none — charts-only
- **Panel documentation**: [`INDICATORS.md`](INDICATORS.md) (Trade rankings)

## Market-wrap news scrapers

Daily close/wrap article extraction for market recaps (Swissinfo, The Edge, CNBC, Newsquawk, TBS, Tokyo Closing Bell, Boursier, Boursorama, Zonebourse).

- **Catalog**: `market_analysis/data_sources/news_sources.json`
- **Parsing strategy (per source)**: [`MARKET_WRAP_SCRAPERS.md`](MARKET_WRAP_SCRAPERS.md)
