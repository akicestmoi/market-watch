# Economic Indicators

Catalog of seeded series in [`data_sources/economic_data.json`](../economic_overview/data_sources/economic_data.json) (414 series). Values are stored as **levels**; period-on-period and year-on-year changes can be derived from history.

Organized by **category → subcategory → series label**. Each series opens with the plain-English recap-bubble text (`description`) — what it measures, how the printed level is expressed, who publishes it, and any own-calculation formula — then a table of region seeds (location order: US / EU / FR / JP / DE / ES / IT). Display order on the recap / charts follows catalog `id` within each location block (US `1–84`, EU `85–92`, FR `93–180`, JP `181–268`, DE `269–317`, ES `318–366`, IT `367–415`; gap at `202` after dropping NSFICW official Gini).

Sources and publication calendars: [`DATA_SOURCES.md`](DATA_SOURCES.md).

## Raw level conventions (flows)

A quarterly (or monthly) **flow** has one printed level per period; sources disagree on scale:

| Convention | Meaning of the printed level | Where |
| --- | --- | --- |
| **Period level** | Activity / balance **in that period** | France / Eurostat national accounts |
| **Annualized (SAAR)** | Period activity as an **annual rate** (≈ 4× the quarter for quarterly SAAR) | United States (BEA via FRED), Japan (Cabinet Office SA GDP / kakei) |

The recap bubble Type line spells this out (`Flow (quarterly, seasonally adjusted)` vs `…, annualized)` vs `…, not seasonally adjusted)`). Annualized tickers live in `ANNUALIZED_ABS_LEVEL_TICKERS`; NSA infra-annual seeds in `NON_SEASONALLY_ADJUSTED_TICKERS` (`economic_overview/services/config.py`).

## `vsGDP` scale rules

`vsGDP` is outstanding ÷ matching GDP × 100, after unit magnitude alignment (`K`/`M`/`B`). Annualization depends on `measure_type` and whether the printed level is already annual-scale:

| Outstanding | Denominator | Scaling |
| --- | --- | --- |
| **Stock** | SAAR / annualized GDP | No ×4 — stock / annual GDP |
| **Stock** | Period-level quarterly GDP | ×4 the GDP denominator |
| **Flow**, period level | SAAR GDP | ×4 the flow |
| **Flow**, SAAR or annual frequency | SAAR / annualized GDP | No ×4 |
| **Flow**, SAAR or annual frequency | Period-level quarterly GDP | ×4 the GDP denominator |

Stocks are never annualized with ×4. Annual-frequency flows against SAAR GDP are left unscaled. Annual-frequency flows use a calendar-year GDP denominator: **sum** of quarters against period-level GDP (FR / Eurostat); **mean** of quarterly SAAR against US / JP SAAR GDP.

---

# Macroeconomics

## Growth

Expenditure-side real GDP and demand components, plus estimated / realized annual growth, output gap, and hidden Nominal GDP denominators for `vsGDP`. US / JP printed flows are **SAAR** (annualized); FR / Eurostat are **period level**.

### Real GDP

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** Inflation-adjusted value of all final goods and services produced in the economy — the usual gauge of real activity.

**By region** (where the bubble differs):

- **US:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Bureau of Economic Analysis (BEA).
- **FR:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Cabinet Office Economic and Social Research Institute (ESRI).
- **DE:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **ES:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **IT:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 1 | FRED | `GDPC1` | B / USD | YoY | `Gross Domestic Product` | [FRED](https://fred.stlouisfed.org/series/GDPC1) | — |
| FR | 95 | INSEE | `011794860` | M / EUR | YoY | `Quarterly national accounts - first estimate` | [INSEE](https://www.insee.fr/en/statistiques/serie/011794860) | — |
| JP | 185 | JP_CABINET_OFFICE | `gaku-jk` | B / JPY | YoY | `Quarterly Estimates of GDP` | [ESRI](https://www.esri.cao.go.jp/en/sna/sokuhou/sokuhou_top.html) | — |
| DE | 274 | EUROSTAT | `namq_10_gdp` | M / EUR | YoY | `GDP and main aggregates` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | — |
| ES | 325 | EUROSTAT | `namq_10_gdp` | M / EUR | YoY | `GDP and main aggregates` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | — |
| IT | 376 | EUROSTAT | `namq_10_gdp` | M / EUR | YoY | `GDP and main aggregates` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | — |

### Business Investment

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** Private gross fixed capital formation (machinery, equipment, structures, and related assets).

**By region** (where the bubble differs):

- **US:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Bureau of Economic Analysis (BEA).
- **FR:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Cabinet Office Economic and Social Research Institute (ESRI).
- **DE:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **ES:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **IT:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 2 | FRED | `GPDIC1` | B / USD | Rel YoY | `Gross Domestic Product` | [FRED](https://fred.stlouisfed.org/series/GPDIC1) | COMPONENT; parent: Real GDP |
| FR | 96 | INSEE | `011794884` | M / EUR | Rel YoY | `Quarterly national accounts - first estimate` | [INSEE](https://www.insee.fr/en/statistiques/serie/011794884) | COMPONENT; parent: Real GDP |
| JP | 186 | JP_CABINET_OFFICE | `gaku-jk-gfcf` | B / JPY | Rel YoY | `Quarterly Estimates of GDP` | [ESRI](https://www.esri.cao.go.jp/en/sna/sokuhou/sokuhou_top.html) | COMPONENT; parent: Real GDP |
| DE | 275 | EUROSTAT | `namq_10_gdp_gfcf` | M / EUR | Rel YoY | `Quarterly national accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | COMPONENT; parent: Real GDP |
| ES | 326 | EUROSTAT | `namq_10_gdp_gfcf` | M / EUR | Rel YoY | `Quarterly national accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | COMPONENT; parent: Real GDP |
| IT | 377 | EUROSTAT | `namq_10_gdp_gfcf` | M / EUR | Rel YoY | `Quarterly national accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | COMPONENT; parent: Real GDP |

### Government Consumption

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** General-government final consumption expenditure on goods and services.

**By region** (where the bubble differs):

- **US:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Bureau of Economic Analysis (BEA).
- **FR:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Cabinet Office Economic and Social Research Institute (ESRI).
- **DE:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **ES:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **IT:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 3 | FRED | `GCEC1` | B / USD | Rel YoY | `Gross Domestic Product` | [FRED](https://fred.stlouisfed.org/series/GCEC1) | COMPONENT; parent: Real GDP |
| FR | 97 | INSEE | `011794862` | M / EUR | Rel YoY | `Quarterly national accounts - first estimate` | [INSEE](https://www.insee.fr/en/statistiques/serie/011794862) | COMPONENT; parent: Real GDP |
| JP | 187 | JP_CABINET_OFFICE | `gaku-jk-gov` | B / JPY | Rel YoY | `Quarterly Estimates of GDP` | [ESRI](https://www.esri.cao.go.jp/en/sna/sokuhou/sokuhou_top.html) | COMPONENT; parent: Real GDP |
| DE | 276 | EUROSTAT | `namq_10_gdp_gov` | M / EUR | Rel YoY | `Quarterly national accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | COMPONENT; parent: Real GDP |
| ES | 327 | EUROSTAT | `namq_10_gdp_gov` | M / EUR | Rel YoY | `Quarterly national accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | COMPONENT; parent: Real GDP |
| IT | 378 | EUROSTAT | `namq_10_gdp_gov` | M / EUR | Rel YoY | `Quarterly national accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | COMPONENT; parent: Real GDP |

### Household Consumption

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** Household spending on goods and services — usually the largest expenditure component of GDP.

**By region** (where the bubble differs):

- **US:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Bureau of Economic Analysis (BEA).
- **FR:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Cabinet Office Economic and Social Research Institute (ESRI).
- **DE:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **ES:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **IT:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 4 | FRED | `PCECC96` | B / USD | Rel YoY | `Gross Domestic Product` | [FRED](https://fred.stlouisfed.org/series/PCECC96) | COMPONENT; parent: Real GDP |
| FR | 98 | INSEE | `011794864` | M / EUR | Rel YoY | `Quarterly national accounts - first estimate` | [INSEE](https://www.insee.fr/en/statistiques/serie/011794864) | COMPONENT; parent: Real GDP |
| JP | 188 | JP_CABINET_OFFICE | `gaku-jk-hh` | B / JPY | Rel YoY | `Quarterly Estimates of GDP` | [ESRI](https://www.esri.cao.go.jp/en/sna/sokuhou/sokuhou_top.html) | COMPONENT; parent: Real GDP |
| DE | 277 | EUROSTAT | `namq_10_gdp_hh` | M / EUR | Rel YoY | `Quarterly national accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | COMPONENT; parent: Real GDP |
| ES | 328 | EUROSTAT | `namq_10_gdp_hh` | M / EUR | Rel YoY | `Quarterly national accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | COMPONENT; parent: Real GDP |
| IT | 379 | EUROSTAT | `namq_10_gdp_hh` | M / EUR | Rel YoY | `Quarterly national accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | COMPONENT; parent: Real GDP |

### Net Exports

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** Exports minus imports — the goods-and-services trade balance level in the national accounts (not the contribution of net exports to GDP growth).

**By region** (where the bubble differs):

- **US:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Bureau of Economic Analysis (BEA).
- **FR:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Cabinet Office Economic and Social Research Institute (ESRI).
- **DE:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **ES:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **IT:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 5 | FRED | `NETEXP` | B / USD | Rel YoY | `Gross Domestic Product` | [FRED](https://fred.stlouisfed.org/series/NETEXP) | COMPONENT; parent: Real GDP |
| FR | 99 | INSEE | `011794880` | M / EUR | Rel YoY | `Quarterly national accounts - first estimate` | [INSEE](https://www.insee.fr/en/statistiques/serie/011794880) | COMPONENT; parent: Real GDP |
| JP | 189 | JP_CABINET_OFFICE | `gaku-jk-nx` | B / JPY | Rel YoY | `Quarterly Estimates of GDP` | [ESRI](https://www.esri.cao.go.jp/en/sna/sokuhou/sokuhou_top.html) | COMPONENT; parent: Real GDP |
| DE | 278 | EUROSTAT | `namq_10_gdp_nx` | M / EUR | Rel YoY | `Balance of payments` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | COMPONENT; parent: Real GDP |
| ES | 329 | EUROSTAT | `namq_10_gdp_nx` | M / EUR | Rel YoY | `Balance of payments` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | COMPONENT; parent: Real GDP |
| IT | 380 | EUROSTAT | `namq_10_gdp_nx` | M / EUR | Rel YoY | `Balance of payments` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | COMPONENT; parent: Real GDP |

### Estimated Annual GDP Growth

Frequency: `QUARTERLY` · Measure: `DERIVED` · Agenda `technical_name`: `Derived trailing-4Q + national realized annual`

**What it is.** Trailing four-quarter real GDP growth for Current, compared with the official calendar-year real GDP growth print for Previous (percent rates). Current is a run-rate estimate of annual growth: the latest four quarters are treated as a full-year block, holding other things equal (as if the rest of the year continued at a similar pace). Previous is the official completed calendar-year print before Period (Period is that latest Real GDP quarter’s calendar year).

**By region** (where the bubble differs):

- **US:** Built from the Bureau of Economic Analysis (BEA) series.
- **FR:** Built from the National Institute of Statistics and Economic Studies (INSEE) series.
- **JP:** Built from the Cabinet Office Economic and Social Research Institute (ESRI) series.
- **DE:** Built from Eurostat (Statistical Office of the European Union) series.
- **ES:** Built from Eurostat (Statistical Office of the European Union) series.
- **IT:** Built from Eurostat (Statistical Office of the European Union) series.

**Own calculation** (by region):

- **US:** Current = last-4Q Real GDP (GDPC1) / prior-4Q Real GDP (GDPC1) − 1 (averaging the quarterly annualized levels in each block); Previous = official realized annual Real GDP growth for the latest completed year before Period.
- **FR:** Current = last-4Q Real GDP (011794860) / prior-4Q Real GDP (011794860) − 1 (summing the quarterly period-level prints in each block); Previous = official realized annual Real GDP growth for the latest completed year before Period.
- **JP:** Current = last-4Q Real GDP (gaku-jk) / prior-4Q Real GDP (gaku-jk) − 1 (averaging the quarterly annualized levels in each block); Previous = official realized annual Real GDP growth for the latest completed year before Period.
- **DE:** Current = last-4Q Real GDP (namq_10_gdp) / prior-4Q Real GDP (namq_10_gdp) − 1 (summing the quarterly period-level prints in each block); Previous = official realized annual Real GDP growth for the latest completed year before Period.
- **ES:** Current = last-4Q Real GDP (namq_10_gdp) / prior-4Q Real GDP (namq_10_gdp) − 1 (summing the quarterly period-level prints in each block); Previous = official realized annual Real GDP growth for the latest completed year before Period.
- **IT:** Current = last-4Q Real GDP (namq_10_gdp) / prior-4Q Real GDP (namq_10_gdp) − 1 (summing the quarterly period-level prints in each block); Previous = official realized annual Real GDP growth for the latest completed year before Period.

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 6 | FRED | `derived_annual_gdp_growth` | PERCENT | Raw | [link](FRED || United States Real GDP; United States Realized Annual GDP Growth) | — |
| FR | 100 | INSEE | `derived_annual_gdp_growth` | PERCENT | Raw | [link](INSEE || France Real GDP; France Realized Annual GDP Growth) | — |
| JP | 190 | JP_CABINET_OFFICE | `derived_annual_gdp_growth` | PERCENT | Raw | [link](Japan Cabinet Office || Japan Real GDP; Japan Realized Annual GDP Growth) | — |
| DE | 279 | EUROSTAT | `derived_annual_gdp_growth` | PERCENT | Raw | [link](Eurostat || Germany Real GDP; Germany Realized Annual GDP Growth) | — |
| ES | 330 | EUROSTAT | `derived_annual_gdp_growth` | PERCENT | Raw | [link](Eurostat || Spain Real GDP; Spain Realized Annual GDP Growth) | — |
| IT | 381 | EUROSTAT | `derived_annual_gdp_growth` | PERCENT | Raw | [link](Eurostat || Italy Real GDP; Italy Realized Annual GDP Growth) | — |

### Output Gap

Frequency: `ANNUAL` · Measure: `RATE` · Agenda `technical_name`: `Economic Outlook Output Gap`

**What it is.** Difference between actual and potential real GDP, showing how far activity sits above or below capacity. A positive gap means activity above potential; a negative gap means spare capacity. Published by the Organisation for Economic Co-operation and Development (OECD).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 7 | OECD | `eo_gap` | PERCENT | Raw | [OECD](https://data-explorer.oecd.org/) | — |
| FR | 101 | OECD | `eo_gap` | PERCENT | Raw | [OECD](https://data-explorer.oecd.org/) | — |
| JP | 191 | OECD | `eo_gap` | PERCENT | Raw | [OECD](https://data-explorer.oecd.org/) | — |
| DE | 280 | OECD | `eo_gap` | PERCENT | Raw | [OECD](https://data-explorer.oecd.org/) | — |
| ES | 331 | OECD | `eo_gap` | PERCENT | Raw | [OECD](https://data-explorer.oecd.org/) | — |
| IT | 382 | OECD | `eo_gap` | PERCENT | Raw | [OECD](https://data-explorer.oecd.org/) | — |

### Realized Annual GDP Growth

Frequency: `ANNUAL` · Measure: `RATE`

**What it is** (by region):

- **US:** BEA annual real GDP percent change from the preceding year (via FRED). Published by Bureau of Economic Analysis (BEA). Published by the Bureau of Economic Analysis (BEA). Published by the Bureau of Economic Analysis (BEA). Published by the Bureau of Economic Analysis (BEA). Published by the Bureau of Economic Analysis (BEA).
- **FR:** INSEE annual national accounts GDP volume growth (percent change on previous year). Published by National Institute of Statistics and Economic Studies (INSEE). Published by the National Institute of Statistics and Economic Studies (INSEE). Published by the National Institute of Statistics and Economic Studies (INSEE). Published by the National Institute of Statistics and Economic Studies (INSEE). Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** Placeholder for Japan full-year real GDP growth from Cabinet Office quarterly estimates. Published by Cabinet Office Economic and Social Research Institute (ESRI). Published by the Cabinet Office Economic and Social Research Institute (ESRI). Published by the Cabinet Office Economic and Social Research Institute (ESRI). Published by the Cabinet Office Economic and Social Research Institute (ESRI). Published by the Cabinet Office Economic and Social Research Institute (ESRI).
- **DE:** Eurostat annual real GDP percent change on previous year (nama_10_gdp, CLV_PCH_PRE). Published by Eurostat (Statistical Office of the European Union). Published by Eurostat (Statistical Office of the European Union). Published by Eurostat (Statistical Office of the European Union). Published by Eurostat (Statistical Office of the European Union). Published by Eurostat (Statistical Office of the European Union).
- **ES:** Eurostat annual real GDP percent change on previous year (nama_10_gdp, CLV_PCH_PRE). Published by Eurostat (Statistical Office of the European Union). Published by Eurostat (Statistical Office of the European Union). Published by Eurostat (Statistical Office of the European Union). Published by Eurostat (Statistical Office of the European Union). Published by Eurostat (Statistical Office of the European Union).
- **IT:** Eurostat annual real GDP percent change on previous year (nama_10_gdp, CLV_PCH_PRE). Published by Eurostat (Statistical Office of the European Union). Published by Eurostat (Statistical Office of the European Union). Published by Eurostat (Statistical Office of the European Union). Published by Eurostat (Statistical Office of the European Union). Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 8 | FRED | `A191RL1A225NBEA` | PERCENT | Raw | `Gross Domestic Product` | [FRED](https://fred.stlouisfed.org/series/A191RL1A225NBEA) | hidden |
| FR | 102 | INSEE | `011779995` | PERCENT | Raw | `Annual national accounts` | [INSEE](https://www.insee.fr/en/statistiques/serie/011779995) | hidden |
| JP | 192 | JP_CABINET_OFFICE | `derived_jp_calendar_year_gdp_growth` | PERCENT | Raw | `Quarterly Estimates of GDP` | [ESRI](https://www.esri.cao.go.jp/en/sna/sokuhou/sokuhou_top.html) | hidden |
| DE | 281 | EUROSTAT | `nama_10_gdp_pch` | PERCENT | Raw | `GDP and main aggregates` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nama_10_gdp/default/table) | hidden |
| ES | 332 | EUROSTAT | `nama_10_gdp_pch` | PERCENT | Raw | `GDP and main aggregates` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nama_10_gdp/default/table) | hidden |
| IT | 383 | EUROSTAT | `nama_10_gdp_pch` | PERCENT | Raw | `GDP and main aggregates` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nama_10_gdp/default/table) | hidden |

### Nominal GDP

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** Market-value total of final goods and services produced in an economy, measured at current prices without inflation adjustment.

**By region** (where the bubble differs):

- **US:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by Bureau of Economic Analysis (BEA). The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Bureau of Economic Analysis (BEA). The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Bureau of Economic Analysis (BEA). The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Bureau of Economic Analysis (BEA). The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Bureau of Economic Analysis (BEA).
- **FR:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union). The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union). The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union). The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union). The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **JP:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by Cabinet Office Economic and Social Research Institute (ESRI). The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Cabinet Office Economic and Social Research Institute (ESRI). The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Cabinet Office Economic and Social Research Institute (ESRI). The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Cabinet Office Economic and Social Research Institute (ESRI). The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Cabinet Office Economic and Social Research Institute (ESRI).
- **DE:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union). The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union). The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union). The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union). The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **ES:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union). The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union). The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union). The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union). The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **IT:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union). The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union). The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union). The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union). The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 9 | FRED | `GDP` | B / USD | YoY | `Gross Domestic Product` | [FRED](https://fred.stlouisfed.org/series/GDP) | hidden |
| FR | 103 | EUROSTAT | `namq_10_gdp_cp` | M / EUR | YoY | `Gross Domestic Product` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | hidden |
| JP | 193 | JP_CABINET_OFFICE | `gaku-mk` | B / JPY | YoY | `Quarterly Estimates of GDP` | [ESRI](https://www.esri.cao.go.jp/en/sna/sokuhou/sokuhou_top.html) | hidden |
| DE | 282 | EUROSTAT | `namq_10_gdp_cp` | M / EUR | YoY | `Gross Domestic Product` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | hidden |
| ES | 333 | EUROSTAT | `namq_10_gdp_cp` | M / EUR | YoY | `Gross Domestic Product` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | hidden |
| IT | 384 | EUROSTAT | `namq_10_gdp_cp` | M / EUR | YoY | `Gross Domestic Product` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | hidden |

### Exports

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** Goods and services sold to the rest of the world.

**By region** (where the bubble differs):

- **US:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Bureau of Economic Analysis (BEA).
- **FR:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Cabinet Office Economic and Social Research Institute (ESRI).
- **DE:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **ES:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **IT:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 10 | FRED | `EXPGSC1` | B / USD | YoY | `Gross Domestic Product` | [FRED](https://fred.stlouisfed.org/series/EXPGSC1) | COMPONENT; parent: Net Exports |
| FR | 104 | INSEE | `011794877` | M / EUR | YoY | `Quarterly national accounts - first estimate` | [INSEE](https://www.insee.fr/en/statistiques/serie/011794877) | COMPONENT; parent: Net Exports |
| JP | 194 | JP_CABINET_OFFICE | `gaku-jk-ex` | B / JPY | YoY | `Quarterly Estimates of GDP` | [ESRI](https://www.esri.cao.go.jp/en/sna/sokuhou/sokuhou_top.html) | COMPONENT; parent: Net Exports |
| DE | 283 | EUROSTAT | `namq_10_gdp_ex` | M / EUR | YoY | `Quarterly national accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | COMPONENT; parent: Net Exports |
| ES | 334 | EUROSTAT | `namq_10_gdp_ex` | M / EUR | YoY | `Quarterly national accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | COMPONENT; parent: Net Exports |
| IT | 385 | EUROSTAT | `namq_10_gdp_ex` | M / EUR | YoY | `Quarterly national accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | COMPONENT; parent: Net Exports |

### Imports

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** Goods and services purchased from the rest of the world.

**By region** (where the bubble differs):

- **US:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Bureau of Economic Analysis (BEA).
- **FR:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Cabinet Office Economic and Social Research Institute (ESRI).
- **DE:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **ES:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **IT:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 11 | FRED | `IMPGSC1` | B / USD | YoY | `Gross Domestic Product` | [FRED](https://fred.stlouisfed.org/series/IMPGSC1) | COMPONENT; parent: Net Exports |
| FR | 105 | INSEE | `011794879` | M / EUR | YoY | `Quarterly national accounts - first estimate` | [INSEE](https://www.insee.fr/en/statistiques/serie/011794879) | COMPONENT; parent: Net Exports |
| JP | 195 | JP_CABINET_OFFICE | `gaku-jk-im` | B / JPY | YoY | `Quarterly Estimates of GDP` | [ESRI](https://www.esri.cao.go.jp/en/sna/sokuhou/sokuhou_top.html) | COMPONENT; parent: Net Exports |
| DE | 284 | EUROSTAT | `namq_10_gdp_im` | M / EUR | YoY | `Quarterly national accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | COMPONENT; parent: Net Exports |
| ES | 335 | EUROSTAT | `namq_10_gdp_im` | M / EUR | YoY | `Quarterly national accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | COMPONENT; parent: Net Exports |
| IT | 386 | EUROSTAT | `namq_10_gdp_im` | M / EUR | YoY | `Quarterly national accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table) | COMPONENT; parent: Net Exports |

## Trade

Current-account stack, trade balance, BIS real effective exchange rates (via FRED), and IMF foreign-exchange reserves (excl. gold).

### Current Account

**What it is.** Broad external balance covering trade, primary income, and secondary income with the rest of the world.

**By region** (where the bubble differs):

- **US:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by the Bureau of Economic Analysis (BEA).
- **EU:** Published by Eurostat (Statistical Office of the European Union).
- **FR:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **JP:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by the Ministry of Finance (Japan).
- **DE:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **ES:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **IT:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 12 | FRED | `IEABC` | M / USD | YTDvsGDP | `U.S. International Transactions` | [FRED](https://fred.stlouisfed.org/series/IEABC) | — |
| EU | 87 | EUROSTAT | `tipsbp20_ca_pct` | PERCENT | YTDvsGDP | `Balance of payments` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/tipsbp20/default/table) | — |
| FR | 106 | EUROSTAT | `bop_c6_q_ca` | M / EUR | YTDvsGDP | `Balance of payments` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/bop_c6_q/default/table) | — |
| JP | 196 | MOF | `mof_bop_ca` | B / JPY | YTDvsGDP | `Balance of Payments` | [MOF](https://www.mof.go.jp/english/policy/international_policy/reference/balance_of_payments/ebpnet.htm) | — |
| DE | 285 | EUROSTAT | `bop_c6_q_ca` | M / EUR | YTDvsGDP | `Balance of payments` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/bop_c6_q/default/table) | — |
| ES | 336 | EUROSTAT | `bop_c6_q_ca` | M / EUR | YTDvsGDP | `Balance of payments` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/bop_c6_q/default/table) | — |
| IT | 387 | EUROSTAT | `bop_c6_q_ca` | M / EUR | YTDvsGDP | `Balance of payments` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/bop_c6_q/default/table) | — |

### Primary Income Balance

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** Net cross-border income from labour, investment, and related primary distributions. The printed level is the seasonally adjusted flow for that period (not annualized).

**By region** (where the bubble differs):

- **US:** Published by the Bureau of Economic Analysis (BEA).
- **FR:** Published by Eurostat (Statistical Office of the European Union).
- **JP:** Published by the Ministry of Finance (Japan).
- **DE:** Published by Eurostat (Statistical Office of the European Union).
- **ES:** Published by Eurostat (Statistical Office of the European Union).
- **IT:** Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 13 | FRED | `IEABCPI` | M / USD | YTDvsGDP | `U.S. International Transactions` | [FRED](https://fred.stlouisfed.org/series/IEABCPI) | COMPONENT; parent: Current Account |
| FR | 107 | EUROSTAT | `bop_c6_q_in1` | M / EUR | YTDvsGDP | `Balance of payments` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/bop_c6_q/default/table) | COMPONENT; parent: Current Account |
| JP | 197 | MOF | `mof_bop_in1` | B / JPY | YTDvsGDP | `Balance of Payments` | [MOF](https://www.mof.go.jp/english/policy/international_policy/reference/balance_of_payments/ebpnet.htm) | COMPONENT; parent: Current Account |
| DE | 286 | EUROSTAT | `bop_c6_q_in1` | M / EUR | YTDvsGDP | `Balance of payments` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/bop_c6_q/default/table) | COMPONENT; parent: Current Account |
| ES | 337 | EUROSTAT | `bop_c6_q_in1` | M / EUR | YTDvsGDP | `Balance of payments` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/bop_c6_q/default/table) | COMPONENT; parent: Current Account |
| IT | 388 | EUROSTAT | `bop_c6_q_in1` | M / EUR | YTDvsGDP | `Balance of payments` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/bop_c6_q/default/table) | COMPONENT; parent: Current Account |

### Secondary Income Balance

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** Net current transfers with the rest of the world (remittances, aid, and similar transfers). The printed level is the seasonally adjusted flow for that period (not annualized).

**By region** (where the bubble differs):

- **US:** Published by the Bureau of Economic Analysis (BEA).
- **FR:** Published by Eurostat (Statistical Office of the European Union).
- **JP:** Published by the Ministry of Finance (Japan).
- **DE:** Published by Eurostat (Statistical Office of the European Union).
- **ES:** Published by Eurostat (Statistical Office of the European Union).
- **IT:** Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 14 | FRED | `IEABCSI` | M / USD | YTDvsGDP | `U.S. International Transactions` | [FRED](https://fred.stlouisfed.org/series/IEABCSI) | COMPONENT; parent: Current Account |
| FR | 108 | EUROSTAT | `bop_c6_q_in2` | M / EUR | YTDvsGDP | `Balance of payments` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/bop_c6_q/default/table) | COMPONENT; parent: Current Account |
| JP | 198 | MOF | `mof_bop_in2` | B / JPY | YTDvsGDP | `Balance of Payments` | [MOF](https://www.mof.go.jp/english/policy/international_policy/reference/balance_of_payments/ebpnet.htm) | COMPONENT; parent: Current Account |
| DE | 287 | EUROSTAT | `bop_c6_q_in2` | M / EUR | YTDvsGDP | `Balance of payments` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/bop_c6_q/default/table) | COMPONENT; parent: Current Account |
| ES | 338 | EUROSTAT | `bop_c6_q_in2` | M / EUR | YTDvsGDP | `Balance of payments` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/bop_c6_q/default/table) | COMPONENT; parent: Current Account |
| IT | 389 | EUROSTAT | `bop_c6_q_in2` | M / EUR | YTDvsGDP | `Balance of payments` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/bop_c6_q/default/table) | COMPONENT; parent: Current Account |

### Trade Balance

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** Goods-and-services balance with the rest of the world (exports minus imports). The printed level is the seasonally adjusted flow for that period (not annualized).

**By region** (where the bubble differs):

- **US:** Published by the Bureau of Economic Analysis (BEA).
- **FR:** Published by Eurostat (Statistical Office of the European Union).
- **JP:** Published by the Ministry of Finance (Japan).
- **DE:** Published by Eurostat (Statistical Office of the European Union).
- **ES:** Published by Eurostat (Statistical Office of the European Union).
- **IT:** Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 15 | FRED | `IEABCGS` | M / USD | YTDvsGDP | `U.S. International Transactions` | [FRED](https://fred.stlouisfed.org/series/IEABCGS) | COMPONENT; parent: Current Account |
| FR | 109 | EUROSTAT | `bop_c6_q_gs` | M / EUR | YTDvsGDP | `Balance of payments` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/bop_c6_q/default/table) | COMPONENT; parent: Current Account |
| JP | 199 | MOF | `mof_bop_gs` | B / JPY | YTDvsGDP | `Balance of Payments` | [MOF](https://www.mof.go.jp/english/policy/international_policy/reference/balance_of_payments/ebpnet.htm) | COMPONENT; parent: Current Account |
| DE | 288 | EUROSTAT | `bop_c6_q_gs` | M / EUR | YTDvsGDP | `Balance of payments` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/bop_c6_q/default/table) | COMPONENT; parent: Current Account |
| ES | 339 | EUROSTAT | `bop_c6_q_gs` | M / EUR | YTDvsGDP | `Balance of payments` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/bop_c6_q/default/table) | COMPONENT; parent: Current Account |
| IT | 390 | EUROSTAT | `bop_c6_q_gs` | M / EUR | YTDvsGDP | `Balance of payments` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/bop_c6_q/default/table) | COMPONENT; parent: Current Account |

### Real Effective Exchange Rate

Frequency: `MONTHLY` · Measure: `INDEX` · Agenda `technical_name`: `BIS Effective Exchange Rate Indices`

**What it is.** Trade-weighted exchange rate adjusted for relative prices — competitiveness versus trading partners. Index with base year 2020 = 100. Published by the Bank for International Settlements (BIS).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 16 | FRED | `RBUSBIS` | INDEX / base 2020 | Raw | [FRED](https://fred.stlouisfed.org/series/RBUSBIS) | — |
| EU | 88 | FRED | `RBXMBIS` | INDEX / base 2020 | Raw | [FRED](https://fred.stlouisfed.org/series/RBXMBIS) | — |
| FR | 110 | FRED | `RBFRBIS` | INDEX / base 2020 | Raw | [FRED](https://fred.stlouisfed.org/series/RBFRBIS) | — |
| JP | 200 | FRED | `RBJPBIS` | INDEX / base 2020 | Raw | [FRED](https://fred.stlouisfed.org/series/RBJPBIS) | — |
| DE | 289 | FRED | `RBDEBIS` | INDEX / base 2020 | Raw | [FRED](https://fred.stlouisfed.org/series/RBDEBIS) | — |
| ES | 340 | FRED | `RBESBIS` | INDEX / base 2020 | Raw | [FRED](https://fred.stlouisfed.org/series/RBESBIS) | — |
| IT | 391 | FRED | `RBITBIS` | INDEX / base 2020 | Raw | [FRED](https://fred.stlouisfed.org/series/RBITBIS) | — |

### Foreign Exchange Reserves

Frequency: `MONTHLY` · Measure: `STOCK` · Agenda `technical_name`: `International Liquidity`

**What it is.** Official reserve assets held by the monetary authorities. The printed level is an outstanding stock. Published by the International Monetary Fund (IMF).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 17 | IMF | `RXF11_REVS` | M / USD | YoY | [IMF](https://data.imf.org/en/datasets/IMF.STA:IL) | — |
| FR | 111 | IMF | `RXF11_REVS` | M / USD | YoY | [IMF](https://data.imf.org/en/datasets/IMF.STA:IL) | — |
| JP | 201 | IMF | `RXF11_REVS` | M / USD | YoY | [IMF](https://data.imf.org/en/datasets/IMF.STA:IL) | — |
| DE | 290 | IMF | `RXF11_REVS` | M / USD | YoY | [IMF](https://data.imf.org/en/datasets/IMF.STA:IL) | — |
| ES | 341 | IMF | `RXF11_REVS` | M / USD | YoY | [IMF](https://data.imf.org/en/datasets/IMF.STA:IL) | — |
| IT | 392 | IMF | `RXF11_REVS` | M / USD | YoY | [IMF](https://data.imf.org/en/datasets/IMF.STA:IL) | — |

## Confidence

Macro confidence line: S&P Global Composite PMI (via Trading Economics).

### S&P Composite PMI

Frequency: `MONTHLY` · Measure: `INDEX` · Agenda `technical_name`: `S&P Global Composite PMI`

**What it is.** Diffusion index of private-sector manufacturing and services activity. S&P Global purchasing-managers survey of companies across manufacturing and services (panel size varies by country; typically hundreds of firms). Neutral: 50 (above = private-sector expansion, below = contraction). Published by S&P Global.

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 18 | TRADING_ECONOMICS | `us_sp_composite_pmi` | — | Raw | [TE](https://tradingeconomics.com/united-states/composite-pmi) | — |
| FR | 112 | TRADING_ECONOMICS | `fr_sp_composite_pmi` | — | Raw | [TE](https://tradingeconomics.com/france/composite-pmi) | — |
| JP | 202 | TRADING_ECONOMICS | `jp_sp_composite_pmi` | — | Raw | [TE](https://tradingeconomics.com/japan/composite-pmi) | — |

---

# Household

## Labour

Unemployment, employment levels, and US nonfarm payrolls.

### Unemployment Rate

Measure: `RATE`

**What it is.** Share of the labour force that is without work and actively seeking employment.

**By region** (where the bubble differs):

- **US:** Published by the Bureau of Labor Statistics (BLS).
- **FR:** Published by the National Institute of Statistics and Economic Studies (INSEE).
- **FR:** Published by Eurostat (Statistical Office of the European Union). Hidden from France charts and the economic recap; kept for Cross-Region monthly overlays.
- **JP:** Published by the Statistics Bureau of Japan (SBJ).
- **DE:** Published by Eurostat (Statistical Office of the European Union).
- **ES:** Published by Eurostat (Statistical Office of the European Union).
- **IT:** Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 19 | FRED | `UNRATE` | PERCENT | Raw | `Employment Situation` | [FRED](https://fred.stlouisfed.org/series/UNRATE) | — |
| FR | 113 | INSEE | `001688527` | PERCENT | Raw | `ILO Unemployment and Labour Market-related indicators (Labour Force Survey results)` | [INSEE](https://www.insee.fr/en/statistiques/serie/001688527) | — |
| FR | 114 | EUROSTAT | `une_rt_m` | PERCENT | Raw | `Unemployment` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/une_rt_m/default/table) | hidden |
| JP | 203 | STAT_OF_JP | `0301010000020020010` | PERCENT | Raw | `Labour Force Survey` | [e-Stat](https://dashboard.e-stat.go.jp/en/static/api) | — |
| DE | 291 | EUROSTAT | `une_rt_m` | PERCENT | Raw | `Unemployment` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/une_rt_m/default/table) | — |
| ES | 342 | EUROSTAT | `une_rt_m` | PERCENT | Raw | `Unemployment` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/une_rt_m/default/table) | — |
| IT | 393 | EUROSTAT | `une_rt_m` | PERCENT | Raw | `Unemployment` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/une_rt_m/default/table) | — |

### Employment Level

Measure: `STOCK`

**What it is.** Number of people in employment. The printed level is an outstanding stock.

**By region** (where the bubble differs):

- **US:** Published by the Bureau of Labor Statistics (BLS).
- **FR:** Published by Eurostat (Statistical Office of the European Union).
- **FR:** Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** Published by the Statistics Bureau of Japan (SBJ).
- **DE:** Published by Eurostat (Statistical Office of the European Union).
- **ES:** Published by Eurostat (Statistical Office of the European Union).
- **IT:** Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 20 | FRED | `CE16OV` | K | YoY | `Employment Situation (CPS)` | [FRED](https://fred.stlouisfed.org/series/CE16OV) | — |
| FR | 115 | EUROSTAT | `lfsi_emp_q` | K | YoY | `Quarterly employment and labour force` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/lfsi_emp_q/default/table) | — |
| FR | 116 | INSEE | `001796852` | K | YoY | `Quarterly employment estimates – detailed figures` | [INSEE](https://www.insee.fr/en/statistiques/serie/001796852) | — |
| JP | 204 | STAT_OF_JP | `0301010000010010010` | K | YoY | `Labour Force Survey` | [e-Stat](https://www.e-stat.go.jp/en/stat-search/files?page=1&toukei=00200531) | — |
| DE | 292 | EUROSTAT | `namq_10_pe` | K | YoY | `Employment` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_pe/default/table) | — |
| ES | 343 | EUROSTAT | `namq_10_pe` | K | YoY | `Employment` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_pe/default/table) | — |
| IT | 394 | EUROSTAT | `namq_10_pe` | K | YoY | `Employment` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/namq_10_pe/default/table) | — |

### Nonfarm Payrolls

Frequency: `MONTHLY` · Measure: `STOCK` · Agenda `technical_name`: `Current Employment Statistics (CES)`

**What it is.** Employees on nonfarm payrolls — the main US payroll employment gauge. The printed level is an outstanding stock. Published by the Bureau of Labor Statistics (BLS).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 21 | FRED | `PAYEMS` | K | Raw | [link](https://www.bls.gov/ces/) | — |

## Inequality

Income Gini / Palma and wealth Gini / top-10 share. Cross-country levels are only approximately comparable (EU-SILC vs ACS vs FIES for income; ECB DWA household wealth vs WID personal wealth). Seeds use `MONTHLY_UPDATE`.

### Gini Index (Revenue)

Frequency: `ANNUAL`

**What it is** (by region):

- **US:** Income inequality on a 0–100 scale (0 = perfect equality, 100 = perfect inequality). ACS publishes on a 0–1 scale and is stored ×100 to align with Eurostat’s 0–100 convention. Published by the United States Census Bureau.
- **FR:** Income inequality on a 0–100 scale (0 = perfect equality, 100 = perfect inequality). Published by Eurostat (Statistical Office of the European Union).
- **JP:** Approximate grouped-data Gini of household yearly income on a 0–100 scale, built from ten equal-population household deciles ranked by income (within-decile inequality is ignored, so this is not a fully observed microdata Gini). Built from the Statistics Bureau of Japan (SBJ) series.
- **DE:** Income inequality on a 0–100 scale (0 = perfect equality, 100 = perfect inequality). Published by Eurostat (Statistical Office of the European Union).
- **ES:** Income inequality on a 0–100 scale (0 = perfect equality, 100 = perfect inequality). Published by Eurostat (Statistical Office of the European Union).
- **IT:** Income inequality on a 0–100 scale (0 = perfect equality, 100 = perfect inequality). Published by Eurostat (Statistical Office of the European Union).

**Own calculation:** approximate grouped-data Gini from FIES Table 3 equal-population household decile mean incomes ranked by yearly income: G = 2 Σ i·m_i / (10 Σ m_i) − 11/10, stored ×100 (within-decile inequality ignored).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 22 | CENSUS | `acs_b19083` | — | Raw | `ACS Gini Index of Income Inequality` | [Census](https://api.census.gov/data.html) | MONTHLY_UPDATE |
| FR | 117 | EUROSTAT | `ilc_di12` | — | Raw | `Gini coefficient of equivalised disposable income` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/ilc_di12/default/table?lang=en) | MONTHLY_UPDATE |
| JP | 205 | STAT_OF_JP | `fies_gini` | — | Raw | `Derived FIES equal-decile yearly-income Gini` | [e-Stat](Statistics Bureau || FIES Table 3 || https://www.stat.go.jp/english/data/sousetai/) | MONTHLY_UPDATE |
| DE | 293 | EUROSTAT | `ilc_di12` | — | Raw | `Gini coefficient of equivalised disposable income` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/ilc_di12/default/table?lang=en) | MONTHLY_UPDATE |
| ES | 344 | EUROSTAT | `ilc_di12` | — | Raw | `Gini coefficient of equivalised disposable income` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/ilc_di12/default/table?lang=en) | MONTHLY_UPDATE |
| IT | 395 | EUROSTAT | `ilc_di12` | — | Raw | `Gini coefficient of equivalised disposable income` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/ilc_di12/default/table?lang=en) | MONTHLY_UPDATE |

### Palma Ratio (Revenue)

Frequency: `ANNUAL` · Measure: `DERIVED`

**What it is** (by region):

- **US:** Ratio of the top 10% household money-income share to the bottom 40% share (ACS household concept, not equivalised individual income). Built from the United States Census Bureau series.
- **FR:** Ratio of the top 10% share to the bottom 40% share of equivalised disposable income among persons (EU-SILC / Eurostat ilc_di01). Built from Eurostat (Statistical Office of the European Union) series.
- **JP:** Ratio of the top decile mean to the sum of the bottom four decile means for total households’ yearly income, using equal-population household deciles ranked by income (FIES). Built from the Statistics Bureau of Japan (SBJ) series.
- **DE:** Ratio of the top 10% share to the bottom 40% share of equivalised disposable income among persons (EU-SILC / Eurostat ilc_di01). Built from Eurostat (Statistical Office of the European Union) series.
- **ES:** Ratio of the top 10% share to the bottom 40% share of equivalised disposable income among persons (EU-SILC / Eurostat ilc_di01). Built from Eurostat (Statistical Office of the European Union) series.
- **IT:** Ratio of the top 10% share to the bottom 40% share of equivalised disposable income among persons (EU-SILC / Eurostat ilc_di01). Built from Eurostat (Statistical Office of the European Union) series.

**Own calculation** (by region):

- **US:** top 10% household money-income share ÷ bottom 40% share (ACS 1-year housing PUMS households, HINCP × WGTP).
- **FR:** D10 / (D1 + D2 + D3 + D4) SHARE of equivalised disposable income among persons (Eurostat ilc_di01).
- **JP:** m10 / (m1 + m2 + m3 + m4) from FIES Table 3 equal-population household decile means ranked by yearly income.
- **DE:** D10 / (D1 + D2 + D3 + D4) SHARE of equivalised disposable income among persons (Eurostat ilc_di01).
- **ES:** D10 / (D1 + D2 + D3 + D4) SHARE of equivalised disposable income among persons (Eurostat ilc_di01).
- **IT:** D10 / (D1 + D2 + D3 + D4) SHARE of equivalised disposable income among persons (Eurostat ilc_di01).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 23 | CENSUS | `acs_pums_palma` | — | Raw | `Derived ACS PUMS top 10% / bottom 40% income` | [Census](Census Bureau || ACS 1-Year PUMS housing || https://www.census.gov/programs-surveys/acs/microdata.html) | MONTHLY_UPDATE |
| FR | 118 | EUROSTAT | `ilc_di01_palma` | — | Raw | `Derived D10 / (D1+D2+D3+D4) income shares` | [Eurostat](Eurostat || ilc_di01 D1–D4, D10 SHARE || https://ec.europa.eu/eurostat/databrowser/view/ilc_di01/default/table?lang=en) | MONTHLY_UPDATE |
| JP | 206 | STAT_OF_JP | `fies_palma` | — | Raw | `Derived FIES equal-decile yearly-income Palma` | [e-Stat](Statistics Bureau || FIES Table 3 || https://www.stat.go.jp/english/data/sousetai/) | MONTHLY_UPDATE |
| DE | 294 | EUROSTAT | `ilc_di01_palma` | — | Raw | `Derived D10 / (D1+D2+D3+D4) income shares` | [Eurostat](Eurostat || ilc_di01 D1–D4, D10 SHARE || https://ec.europa.eu/eurostat/databrowser/view/ilc_di01/default/table?lang=en) | MONTHLY_UPDATE |
| ES | 345 | EUROSTAT | `ilc_di01_palma` | — | Raw | `Derived D10 / (D1+D2+D3+D4) income shares` | [Eurostat](Eurostat || ilc_di01 D1–D4, D10 SHARE || https://ec.europa.eu/eurostat/databrowser/view/ilc_di01/default/table?lang=en) | MONTHLY_UPDATE |
| IT | 396 | EUROSTAT | `ilc_di01_palma` | — | Raw | `Derived D10 / (D1+D2+D3+D4) income shares` | [Eurostat](Eurostat || ilc_di01 D1–D4, D10 SHARE || https://ec.europa.eu/eurostat/databrowser/view/ilc_di01/default/table?lang=en) | MONTHLY_UPDATE |

### Gini Index (Wealth)

Frequency: `ANNUAL`

**What it is** (by region):

- **US:** Wealth inequality on a 0–100 scale for net personal wealth. WID publishes on a 0–1 scale and is stored ×100 to align with the ECB Distributional Wealth Accounts 0–100 convention. Published by the World Inequality Database (WID).
- **FR:** Wealth inequality on a 0–100 scale for adjusted net household wealth. Annual points keep the ECB Distributional Wealth Accounts Q4 observation for each year. Published by the European Central Bank (ECB).
- **JP:** Wealth inequality on a 0–100 scale for net personal wealth. WID publishes on a 0–1 scale and is stored ×100 to align with the ECB Distributional Wealth Accounts 0–100 convention. Published by the World Inequality Database (WID).
- **DE:** Wealth inequality on a 0–100 scale for adjusted net household wealth. Annual points keep the ECB Distributional Wealth Accounts Q4 observation for each year. Published by the European Central Bank (ECB).
- **ES:** Wealth inequality on a 0–100 scale for adjusted net household wealth. Annual points keep the ECB Distributional Wealth Accounts Q4 observation for each year. Published by the European Central Bank (ECB).
- **IT:** Wealth inequality on a 0–100 scale for adjusted net household wealth. Annual points keep the ECB Distributional Wealth Accounts Q4 observation for each year. Published by the European Central Bank (ECB).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 24 | WID | `wid_wealth_gini` | — | Raw | `WID net personal wealth Gini (ghweal992j)` | [WID](https://wid.world/data/) | MONTHLY_UPDATE |
| FR | 119 | ECB | `ecb_dwa_wealth_gini` | — | Raw | `ECB DWA Gini coefficient of household net wealth` | [ECB](https://data.ecb.europa.eu/data/datasets/DWA/DWA.Q.FR.S14._Z._Z.NWA._Z.GI.S.N) | MONTHLY_UPDATE |
| JP | 207 | WID | `wid_wealth_gini` | — | Raw | `WID net personal wealth Gini (ghweal992j)` | [WID](https://wid.world/data/) | MONTHLY_UPDATE |
| DE | 295 | ECB | `ecb_dwa_wealth_gini` | — | Raw | `ECB DWA Gini coefficient of household net wealth` | [ECB](https://data.ecb.europa.eu/data/datasets/DWA/DWA.Q.DE.S14._Z._Z.NWA._Z.GI.S.N) | MONTHLY_UPDATE |
| ES | 346 | ECB | `ecb_dwa_wealth_gini` | — | Raw | `ECB DWA Gini coefficient of household net wealth` | [ECB](https://data.ecb.europa.eu/data/datasets/DWA/DWA.Q.ES.S14._Z._Z.NWA._Z.GI.S.N) | MONTHLY_UPDATE |
| IT | 397 | ECB | `ecb_dwa_wealth_gini` | — | Raw | `ECB DWA Gini coefficient of household net wealth` | [ECB](https://data.ecb.europa.eu/data/datasets/DWA/DWA.Q.IT.S14._Z._Z.NWA._Z.GI.S.N) | MONTHLY_UPDATE |

### Top-10 Wealth Share

Frequency: `ANNUAL`

**What it is** (by region):

- **US:** Share of net personal wealth held by the richest 10% of the population, on a 0–100 percent scale. WID publishes on a 0–1 scale and is stored ×100 to align with the ECB Distributional Wealth Accounts percent convention. Published by the World Inequality Database (WID).
- **FR:** Share of adjusted net household wealth held by the richest 10% of households, on a 0–100 percent scale. Annual points keep the ECB Distributional Wealth Accounts Q4 observation for each year. Published by the European Central Bank (ECB).
- **JP:** Share of net personal wealth held by the richest 10% of the population, on a 0–100 percent scale. WID publishes on a 0–1 scale and is stored ×100 to align with the ECB Distributional Wealth Accounts percent convention. Published by the World Inequality Database (WID).
- **DE:** Share of adjusted net household wealth held by the richest 10% of households, on a 0–100 percent scale. Annual points keep the ECB Distributional Wealth Accounts Q4 observation for each year. Published by the European Central Bank (ECB).
- **ES:** Share of adjusted net household wealth held by the richest 10% of households, on a 0–100 percent scale. Annual points keep the ECB Distributional Wealth Accounts Q4 observation for each year. Published by the European Central Bank (ECB).
- **IT:** Share of adjusted net household wealth held by the richest 10% of households, on a 0–100 percent scale. Annual points keep the ECB Distributional Wealth Accounts Q4 observation for each year. Published by the European Central Bank (ECB).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 25 | WID | `wid_top10_wealth_share` | — | Raw | `WID top 10% net personal wealth share (shweal992j p90p100)` | [WID](https://wid.world/data/) | MONTHLY_UPDATE |
| FR | 120 | ECB | `ecb_dwa_top10_wealth_share` | — | Raw | `ECB DWA top 10% household net wealth share` | [ECB](https://data.ecb.europa.eu/data/datasets/DWA/DWA.Q.FR.S14._Z._Z.NWA.T10.PT.S.N) | MONTHLY_UPDATE |
| JP | 208 | WID | `wid_top10_wealth_share` | — | Raw | `WID top 10% net personal wealth share (shweal992j p90p100)` | [WID](https://wid.world/data/) | MONTHLY_UPDATE |
| DE | 296 | ECB | `ecb_dwa_top10_wealth_share` | — | Raw | `ECB DWA top 10% household net wealth share` | [ECB](https://data.ecb.europa.eu/data/datasets/DWA/DWA.Q.DE.S14._Z._Z.NWA.T10.PT.S.N) | MONTHLY_UPDATE |
| ES | 347 | ECB | `ecb_dwa_top10_wealth_share` | — | Raw | `ECB DWA top 10% household net wealth share` | [ECB](https://data.ecb.europa.eu/data/datasets/DWA/DWA.Q.ES.S14._Z._Z.NWA.T10.PT.S.N) | MONTHLY_UPDATE |
| IT | 398 | ECB | `ecb_dwa_top10_wealth_share` | — | Raw | `ECB DWA top 10% household net wealth share` | [ECB](https://data.ecb.europa.eu/data/datasets/DWA/DWA.Q.IT.S14._Z._Z.NWA.T10.PT.S.N) | MONTHLY_UPDATE |


## Income

Disposable household income (nominal and real).

### Nominal Disposable Household Income

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** Household income after taxes and social contributions, before inflation adjustment.

**By region** (where the bubble differs):

- **US:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Bureau of Economic Analysis (BEA).
- **FR:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Cabinet Office Economic and Social Research Institute (ESRI).
- **DE:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **ES:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **IT:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 26 | FRED | `DPI` | B / USD | YoY | `Personal Income and Outlays` | [FRED](https://fred.stlouisfed.org/series/DPI) | — |
| FR | 121 | INSEE | `011794746` | M / EUR | YoY | `Quarterly national accounts - detailed figures` | [INSEE](https://www.insee.fr/en/statistiques/serie/011794746) | — |
| JP | 209 | JP_CABINET_OFFICE | `kakei_nominal_di` | B / JPY | YoY | `Household Disposable Income and Saving Ratio` | [ESRI](https://www.esri.cao.go.jp/jp/sna/sonota/kakei/household_top.html) | — |
| DE | 297 | EUROSTAT | `nasq_10_nf_tr_b6g` | M / EUR | YoY | `Quarterly sector accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_nf_tr/default/table) | — |
| ES | 348 | EUROSTAT | `nasq_10_nf_tr_b6g` | M / EUR | YoY | `Quarterly sector accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_nf_tr/default/table) | — |
| IT | 399 | EUROSTAT | `nasq_10_nf_tr_b6g` | M / EUR | YoY | `Quarterly sector accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_nf_tr/default/table) | — |

### Real Disposable Household Income

Frequency: `QUARTERLY`

**What it is.** Disposable household income adjusted for consumer prices — a purchasing-power measure.

**By region** (where the bubble differs):

- **US:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Bureau of Economic Analysis (BEA).
- **FR:** Built from the National Institute of Statistics and Economic Studies (INSEE) series.
- **JP:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Cabinet Office Economic and Social Research Institute (ESRI).
- **DE:** Built from Eurostat (Statistical Office of the European Union) series.
- **ES:** Built from Eurostat (Statistical Office of the European Union) series.
- **IT:** Built from Eurostat (Statistical Office of the European Union) series.

**Own calculation** (by region):

- **FR:** Nominal Disposable Household Income (011794746) / (household P3 FCE deflator (CP / CLV) price deflator).
- **DE:** Nominal Disposable Household Income (nasq_10_nf_tr_b6g) / (HH+NPISH FCE deflator (PD20) price deflator).
- **ES:** Nominal Disposable Household Income (nasq_10_nf_tr_b6g) / (HH+NPISH FCE deflator (PD20) price deflator).
- **IT:** Nominal Disposable Household Income (nasq_10_nf_tr_b6g) / (HH+NPISH FCE deflator (PD20) price deflator).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 27 | FRED | `DPIC96` | B / USD | YoY | `Personal Income and Outlays` | [FRED](https://fred.stlouisfed.org/series/DPIC96) | — |
| FR | 122 | INSEE | `011794746_real` | M / EUR | YoY | `Derived RDB / P3 deflator (purchasing power of GDI)` | [INSEE](INSEE || France Nominal Disposable Household Income; France household P3 FCE deflator (CP / CLV) || https://www.insee.fr/en/statistiques/series/117906088) | — |
| JP | 210 | JP_CABINET_OFFICE | `kakei_real_di` | B / JPY | YoY | `Household Disposable Income and Saving Ratio` | [ESRI](https://www.esri.cao.go.jp/jp/sna/sonota/kakei/household_top.html) | — |
| DE | 298 | EUROSTAT | `nasq_10_nf_tr_b6g_real` | M / EUR | YoY | `Derived B6G / P31 PD20` | [link](Eurostat || Germany Nominal Disposable Household Income; Germany HH+NPISH FCE deflator (PD20)) | — |
| ES | 349 | EUROSTAT | `nasq_10_nf_tr_b6g_real` | M / EUR | YoY | `Derived B6G / P31 PD20` | [link](Eurostat || Spain Nominal Disposable Household Income; Spain HH+NPISH FCE deflator (PD20)) | — |
| IT | 400 | EUROSTAT | `nasq_10_nf_tr_b6g_real` | M / EUR | YoY | `Derived B6G / P31 PD20` | [link](Eurostat || Italy Nominal Disposable Household Income; Italy HH+NPISH FCE deflator (PD20)) | — |

## Saving

Household saving levels and saving ratios (ESA vs NIPA personal vs ESRI kakei concepts differ by region).

### Nominal Household Saving

Measure: `FLOW`

**What it is** (by region):

- **US:** Household saving in current prices — income not spent on consumption. The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Bureau of Economic Analysis (BEA).
- **FR:** Household + NPISH gross saving (B8G) in current prices — saving before the consumption of fixed capital adjustment. The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **JP:** Household saving in current prices — income not spent on consumption. The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Cabinet Office Economic and Social Research Institute (ESRI).
- **DE:** Household + NPISH gross saving (B8G) in current prices — saving before the consumption of fixed capital adjustment. The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **ES:** Household + NPISH gross saving (B8G) in current prices — saving before the consumption of fixed capital adjustment. The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **IT:** Household + NPISH gross saving (B8G) in current prices — saving before the consumption of fixed capital adjustment. The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 28 | FRED | `PMSAVE` | B / USD | YoY | `Personal Saving` | [FRED](https://fred.stlouisfed.org/series/PMSAVE) | — |
| FR | 123 | EUROSTAT | `nasq_10_nf_tr_b8g` | M / EUR | YoY | `Quarterly sector accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_nf_tr/default/table) | — |
| JP | 211 | JP_CABINET_OFFICE | `kakei_nominal_saving` | B / JPY | YoY | `Household Disposable Income and Saving Ratio` | [ESRI](https://www.esri.cao.go.jp/jp/sna/sonota/kakei/household_top.html) | — |
| DE | 299 | EUROSTAT | `nasq_10_nf_tr_b8g` | M / EUR | YoY | `Quarterly sector accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_nf_tr/default/table) | — |
| ES | 350 | EUROSTAT | `nasq_10_nf_tr_b8g` | M / EUR | YoY | `Quarterly sector accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_nf_tr/default/table) | — |
| IT | 401 | EUROSTAT | `nasq_10_nf_tr_b8g` | M / EUR | YoY | `Quarterly sector accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_nf_tr/default/table) | — |

### Household Saving Ratio

Measure: `DERIVED`

**What it is** (by region):

- **US:** Personal saving as a percent of disposable personal income (BEA personal-saving concept). Built from the Bureau of Economic Analysis (BEA) series.
- **EU:** Household + NPISH gross saving as a percent of gross disposable income adjusted for the change in pension entitlements (denominator is B6G + D8). Built from Eurostat (Statistical Office of the European Union) series.
- **FR:** Household + NPISH gross saving as a percent of gross disposable income adjusted for the change in pension entitlements (denominator is B6G + D8). Built from Eurostat (Statistical Office of the European Union) series.
- **JP:** Household saving as a percent of disposable household income. Built from the Cabinet Office Economic and Social Research Institute (ESRI) series.
- **DE:** Household + NPISH gross saving as a percent of gross disposable income adjusted for the change in pension entitlements (denominator is B6G + D8). Built from Eurostat (Statistical Office of the European Union) series.
- **ES:** Household + NPISH gross saving as a percent of gross disposable income adjusted for the change in pension entitlements (denominator is B6G + D8). Built from Eurostat (Statistical Office of the European Union) series.
- **IT:** Household + NPISH gross saving as a percent of gross disposable income adjusted for the change in pension entitlements (denominator is B6G + D8). Built from Eurostat (Statistical Office of the European Union) series.

**Own calculation** (by region):

- **US:** Nominal Household Saving (PMSAVE) / Nominal Disposable Household Income (DPI) × 100.
- **EU:** Nominal Household Saving / (Nominal Disposable Household Income + change in pension entitlements D8) × 100.
- **FR:** Nominal Household Saving (nasq_10_nf_tr_b8g) / (Nominal Disposable Household Income (011794746) + change in pension entitlements D8) × 100.
- **JP:** Nominal Household Saving (kakei_nominal_saving) / Nominal Disposable Household Income (kakei_nominal_di) × 100.
- **DE:** Nominal Household Saving (nasq_10_nf_tr_b8g) / (Nominal Disposable Household Income (nasq_10_nf_tr_b6g) + change in pension entitlements D8) × 100.
- **ES:** Nominal Household Saving (nasq_10_nf_tr_b8g) / (Nominal Disposable Household Income (nasq_10_nf_tr_b6g) + change in pension entitlements D8) × 100.
- **IT:** Nominal Household Saving (nasq_10_nf_tr_b8g) / (Nominal Disposable Household Income (nasq_10_nf_tr_b6g) + change in pension entitlements D8) × 100.

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 29 | FRED | `hh_saving_ratio` | PERCENT | Raw | `Derived PMSAVE / DSPI` | [link](FRED || United States Nominal Household Saving; United States Nominal Disposable Household Income) | — |
| EU | 89 | EUROSTAT | `nasq_10_nf_tr_hh_saving_ratio` | PERCENT | Raw | `Derived B8G / (B6G + D8)` | [link](Eurostat || Euro Area Nominal Household Saving; Euro Area Nominal Disposable Household Income) | — |
| FR | 124 | EUROSTAT | `nasq_10_nf_tr_hh_saving_ratio` | PERCENT | Raw | `Derived B8G / (B6G + D8)` | [link](Eurostat || France Nominal Household Saving; France Nominal Disposable Household Income) | — |
| JP | 212 | JP_CABINET_OFFICE | `kakei_saving_ratio` | PERCENT | Raw | `saving / disposable income × 100` | [ESRI](Japan Cabinet Office || Japan Nominal Household Saving; Japan Nominal Disposable Household Income || https://www.esri.cao.go.jp/jp/sna/sonota/kakei/household_top.html) | — |
| DE | 300 | EUROSTAT | `nasq_10_nf_tr_hh_saving_ratio` | PERCENT | Raw | `Derived B8G / (B6G + D8)` | [link](Eurostat || Germany Nominal Household Saving; Germany Nominal Disposable Household Income) | — |
| ES | 351 | EUROSTAT | `nasq_10_nf_tr_hh_saving_ratio` | PERCENT | Raw | `Derived B8G / (B6G + D8)` | [link](Eurostat || Spain Nominal Household Saving; Spain Nominal Disposable Household Income) | — |
| IT | 402 | EUROSTAT | `nasq_10_nf_tr_hh_saving_ratio` | PERCENT | Raw | `Derived B8G / (B6G + D8)` | [link](Eurostat || Italy Nominal Household Saving; Italy Nominal Disposable Household Income) | — |

## Debt

Household loan stocks and debt ratios (stock ÷ annualised disposable income).

### Nominal Household Debt

Frequency: `QUARTERLY` · Measure: `STOCK`

**What it is.** Outstanding household loan liabilities. The printed level is an outstanding stock.

**By region** (where the bubble differs):

- **US:** Published by the Federal Reserve Board (FRB).
- **FR:** Published by Eurostat (Statistical Office of the European Union).
- **JP:** Published by the Bank of Japan (BoJ).
- **DE:** Published by Eurostat (Statistical Office of the European Union).
- **ES:** Published by Eurostat (Statistical Office of the European Union).
- **IT:** Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 30 | FRED | `HNOLL` | B / USD | YoY | `Household & NPISH loans` | [FRED](https://fred.stlouisfed.org/series/HNOLL) | — |
| FR | 125 | EUROSTAT | `nasq_10_f_bs_f4_liab` | M / EUR | YoY | `Quarterly sector accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_f_bs/default/table) | — |
| JP | 213 | BOJ | `fof_hh_loans` | B / JPY | YoY | `Flow of Funds household loans` | [BoJ](https://www.stat-search.boj.or.jp/info/dload_en.html) | — |
| DE | 301 | EUROSTAT | `nasq_10_f_bs_f4_liab` | M / EUR | YoY | `Quarterly sector accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_f_bs/default/table) | — |
| ES | 352 | EUROSTAT | `nasq_10_f_bs_f4_liab` | M / EUR | YoY | `Quarterly sector accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_f_bs/default/table) | — |
| IT | 403 | EUROSTAT | `nasq_10_f_bs_f4_liab` | M / EUR | YoY | `Quarterly sector accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_f_bs/default/table) | — |

### Household Debt Ratio

Frequency: `QUARTERLY`

**What it is.** Household debt as a percent of disposable household income.

**By region** (where the bubble differs):

- **US:** Built from the Federal Reserve Board (FRB) series.
- **EU:** Published by the European Central Bank (ECB).
- **FR:** Published by the European Central Bank (ECB).
- **JP:** Built from the Bank of Japan (BoJ), Cabinet Office Economic and Social Research Institute (ESRI) series.
- **DE:** Published by the European Central Bank (ECB).
- **ES:** Published by the European Central Bank (ECB).
- **IT:** Published by the European Central Bank (ECB).

**Own calculation** (by region):

- **US:** Nominal Household Debt (HNOLL) / Nominal Disposable Household Income (DPI) × 100.
- **JP:** Nominal Household Debt (fof_hh_loans) / Nominal Disposable Household Income (kakei_nominal_di) × 100.

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 31 | FRED | `hh_debt_ratio` | PERCENT | Raw | `Derived HNOLL / DPI` | [link](FRED || United States Nominal Household Debt; United States Nominal Disposable Household Income) | — |
| EU | 90 | ECB | `qsa_hh_loans_to_gdi` | PERCENT | Raw | `Household loans to GDI` | [ECB](https://data.ecb.europa.eu/data/datasets/QSA) | — |
| FR | 126 | ECB | `qsa_hh_loans_to_gdi` | PERCENT | Raw | `Household loans to GDI` | [ECB](https://data.ecb.europa.eu/data/datasets/QSA) | — |
| JP | 214 | BOJ | `hh_debt_ratio` | PERCENT | Raw | `Derived FOF loans / ESRI DI` | [link](Bank of Japan, Japan Cabinet Office || Japan Nominal Household Debt; Japan Nominal Disposable Household Income) | — |
| DE | 302 | ECB | `qsa_hh_loans_to_gdi` | PERCENT | Raw | `Household loans to GDI` | [ECB](https://data.ecb.europa.eu/data/datasets/QSA) | — |
| ES | 353 | ECB | `qsa_hh_loans_to_gdi` | PERCENT | Raw | `Household loans to GDI` | [ECB](https://data.ecb.europa.eu/data/datasets/QSA) | — |
| IT | 404 | ECB | `qsa_hh_loans_to_gdi` | PERCENT | Raw | `Household loans to GDI` | [ECB](https://data.ecb.europa.eu/data/datasets/QSA) | — |

## Sales

Household consumption (national accounts) plus retail sales (nominal and real).

### Nominal Household Consumption

Measure: `FLOW`

**What it is.** Household spending on goods and services in current prices.

**By region** (where the bubble differs):

- **US:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Bureau of Economic Analysis (BEA).
- **FR:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Cabinet Office Economic and Social Research Institute (ESRI).
- **DE:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **ES:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **IT:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 32 | FRED | `PCE` | B / USD | YoY | `Personal Income and Outlays` | [FRED](https://fred.stlouisfed.org/series/PCE) | — |
| FR | 127 | INSEE | `011794863` | M / EUR | YoY | `Comptes nationaux trimestriels` | [INSEE](https://www.insee.fr/fr/statistiques/serie/011794863) | — |
| JP | 215 | JP_CABINET_OFFICE | `kakei_nominal_consumption` | B / JPY | YoY | `Household Disposable Income and Saving Ratio` | [ESRI](https://www.esri.cao.go.jp/jp/sna/sonota/kakei/household_top.html) | — |
| DE | 303 | EUROSTAT | `nasq_10_nf_tr_p31` | M / EUR | YoY | `Quarterly sector accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_nf_tr/default/table) | — |
| ES | 354 | EUROSTAT | `nasq_10_nf_tr_p31` | M / EUR | YoY | `Quarterly sector accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_nf_tr/default/table) | — |
| IT | 405 | EUROSTAT | `nasq_10_nf_tr_p31` | M / EUR | YoY | `Quarterly sector accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_nf_tr/default/table) | — |

### Household Consumption Ratio

Measure: `DERIVED`

**What it is** (by region):

- **US:** Household consumption as a percent of disposable household income. Built from the Bureau of Economic Analysis (BEA) series.
- **FR:** Household + NPISH final consumption as a percent of gross disposable income adjusted for the change in pension entitlements (B6G + D8) — the consumption-rate counterpart to the Eurostat saving-rate identity. Built from Eurostat (Statistical Office of the European Union) series.
- **JP:** Household consumption as a percent of disposable household income. Built from the Cabinet Office Economic and Social Research Institute (ESRI) series.
- **DE:** Household + NPISH final consumption as a percent of gross disposable income adjusted for the change in pension entitlements (B6G + D8) — the consumption-rate counterpart to the Eurostat saving-rate identity. Built from Eurostat (Statistical Office of the European Union) series.
- **ES:** Household + NPISH final consumption as a percent of gross disposable income adjusted for the change in pension entitlements (B6G + D8) — the consumption-rate counterpart to the Eurostat saving-rate identity. Built from Eurostat (Statistical Office of the European Union) series.
- **IT:** Household + NPISH final consumption as a percent of gross disposable income adjusted for the change in pension entitlements (B6G + D8) — the consumption-rate counterpart to the Eurostat saving-rate identity. Built from Eurostat (Statistical Office of the European Union) series.

**Own calculation** (by region):

- **US:** Nominal Household Consumption (PCE) / Nominal Disposable Household Income (DPI) × 100.
- **FR:** Nominal Household Consumption (011794863) / (Nominal Disposable Household Income (011794746) + change in pension entitlements D8) × 100.
- **JP:** Nominal Household Consumption (kakei_nominal_consumption) / Nominal Disposable Household Income (kakei_nominal_di) × 100.
- **DE:** Nominal Household Consumption (nasq_10_nf_tr_p31) / (Nominal Disposable Household Income (nasq_10_nf_tr_b6g) + change in pension entitlements D8) × 100.
- **ES:** Nominal Household Consumption (nasq_10_nf_tr_p31) / (Nominal Disposable Household Income (nasq_10_nf_tr_b6g) + change in pension entitlements D8) × 100.
- **IT:** Nominal Household Consumption (nasq_10_nf_tr_p31) / (Nominal Disposable Household Income (nasq_10_nf_tr_b6g) + change in pension entitlements D8) × 100.

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 33 | FRED | `hh_consumption_ratio` | PERCENT | Raw | `Derived PCE / DSPI` | [link](FRED || United States Nominal Household Consumption; United States Nominal Disposable Household Income) | — |
| FR | 128 | EUROSTAT | `nasq_10_nf_tr_hh_consumption_ratio` | PERCENT | Raw | `Derived P.31 / (B6G + D8)` | [link](Eurostat || France Nominal Household Consumption; France Nominal Disposable Household Income) | — |
| JP | 216 | JP_CABINET_OFFICE | `kakei_consumption_ratio` | PERCENT | Raw | `Derived Consumption / DI` | [ESRI](Japan Cabinet Office || Japan Nominal Household Consumption; Japan Nominal Disposable Household Income || https://www.esri.cao.go.jp/jp/sna/sonota/kakei/household_top.html) | — |
| DE | 304 | EUROSTAT | `nasq_10_nf_tr_hh_consumption_ratio` | PERCENT | Raw | `Derived P.31 / (B6G + D8)` | [link](Eurostat || Germany Nominal Household Consumption; Germany Nominal Disposable Household Income) | — |
| ES | 355 | EUROSTAT | `nasq_10_nf_tr_hh_consumption_ratio` | PERCENT | Raw | `Derived P.31 / (B6G + D8)` | [link](Eurostat || Spain Nominal Household Consumption; Spain Nominal Disposable Household Income) | — |
| IT | 406 | EUROSTAT | `nasq_10_nf_tr_hh_consumption_ratio` | PERCENT | Raw | `Derived P.31 / (B6G + D8)` | [link](Eurostat || Italy Nominal Household Consumption; Italy Nominal Disposable Household Income) | — |

### Retail Sales

Frequency: `MONTHLY`

**What it is.** Household goods spending through retail outlets.

**By region** (where the bubble differs):

- **US:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by the United States Census Bureau.
- **FR:** Index with base year 2021 = 100. Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by the Ministry of Economy, Trade and Industry (METI).
- **DE:** Index with base year 2021 = 100. Published by Eurostat (Statistical Office of the European Union).
- **ES:** Index with base year 2021 = 100. Published by Eurostat (Statistical Office of the European Union).
- **IT:** Index with base year 2021 = 100. Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 34 | FRED | `RSAFS` | M / USD | YTDYoY | `Advance Monthly Sales for Retail and Food Services` | [FRED](https://fred.stlouisfed.org/series/RSAFS) | — |
| FR | 129 | INSEE | `010770798` | INDEX / base 2021 | MoM | `Turnover in retail trade` | [INSEE](https://www.insee.fr/en/statistiques/serie/010770798) | — |
| JP | 217 | METI | `retail_sales_index_sa` | INDEX / base 2020 | MoM | `Current Survey of Commerce` | [e-Stat](https://www.e-stat.go.jp/stat-search/files?stat_infid=000031387999 || https://www.meti.go.jp/statistics/tyo/syoudou/result-2/index.html) | — |
| DE | 305 | EUROSTAT | `sts_trtu_m_nettur` | INDEX / base 2021 | MoM | `Retail trade turnover` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/sts_trtu_m/default/table) | — |
| ES | 356 | EUROSTAT | `sts_trtu_m_nettur` | INDEX / base 2021 | MoM | `Retail trade turnover` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/sts_trtu_m/default/table) | — |
| IT | 407 | EUROSTAT | `sts_trtu_m_nettur` | INDEX / base 2021 | MoM | `Retail trade turnover` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/sts_trtu_m/default/table) | — |

### Real Retail Sales

Frequency: `MONTHLY`

**What it is.** Retail sales in volume / constant-price terms — a timely proxy for real household goods spending.

**By region** (where the bubble differs):

- **US:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by the United States Census Bureau.
- **FR:** Index with base year 2021 = 100. Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** Index with base year 2015 = 100. Published by the Organisation for Economic Co-operation and Development (OECD).
- **DE:** Index with base year 2021 = 100. Published by Eurostat (Statistical Office of the European Union).
- **ES:** Index with base year 2021 = 100. Published by Eurostat (Statistical Office of the European Union).
- **IT:** Index with base year 2021 = 100. Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 35 | FRED | `RRSFS` | M / USD | YTDYoY | `Advance Monthly Sales for Retail and Food Services` | [FRED](https://fred.stlouisfed.org/series/RRSFS) | — |
| FR | 130 | INSEE | `010769903` | INDEX / base 2021 | MoM | `Sales volume in wholesale and retail trade` | [INSEE](https://www.insee.fr/en/statistiques/serie/010769903) | — |
| JP | 218 | OECD | `JPN.M.TOVM.IX.G47.Y._Z._Z.N` | INDEX / base 2015 | MoM | `Main Economic Indicators` | [OECD](https://data-explorer.oecd.org/) | — |
| DE | 306 | EUROSTAT | `sts_trtu_m` | INDEX / base 2021 | MoM | `Retail trade volume` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/sts_trtu_m/default/table) | — |
| ES | 357 | EUROSTAT | `sts_trtu_m` | INDEX / base 2021 | MoM | `Retail trade volume` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/sts_trtu_m/default/table) | — |
| IT | 408 | EUROSTAT | `sts_trtu_m` | INDEX / base 2021 | MoM | `Retail trade volume` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/sts_trtu_m/default/table) | — |

## Prices

Consumer prices: national CPI / HICP, US PCE, and core CPI variants. Euro area / DE / ES / IT CPI lines are HICP; France uses national CPI.

### Consumer Price Index

Frequency: `MONTHLY` · Measure: `INDEX`

**What it is.** Average change in prices of a representative basket of consumer goods and services.

**By region** (where the bubble differs):

- **US:** Index with base year 1982 = 100. Published by the Bureau of Labor Statistics (BLS).
- **EU:** Index with base year 2025 = 100. Published by Eurostat (Statistical Office of the European Union).
- **FR:** Index with base year 2025 = 100. National CPI uses gross prices for health and is distinct from HICP. Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** Index with base year 2025 = 100. Published by the Statistics Bureau of Japan (SBJ).
- **DE:** Index with base year 2025 = 100. Published by Eurostat (Statistical Office of the European Union).
- **ES:** Index with base year 2025 = 100. Published by Eurostat (Statistical Office of the European Union).
- **IT:** Index with base year 2025 = 100. Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 36 | FRED | `CPIAUCSL` | INDEX / base 1982 | YoY | `Consumer Price Index` | [FRED](https://fred.stlouisfed.org/series/CPIAUCSL) | — |
| EU | 91 | EUROSTAT | `prc_hicp_minr` | INDEX / base 2025 | YoY | `Inflation (HICP)` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_minr/default/table) | — |
| FR | 131 | INSEE | `011814630` | INDEX / base 2025 | YoY | `Consumer price index - all households` | [INSEE](https://www.insee.fr/en/statistiques/serie/011814630) | — |
| JP | 219 | STAT_OF_JP | `0703010601010090000` | INDEX / base 2025 | YoY | `Consumer Price Index` | [e-Stat](https://dashboard.e-stat.go.jp/en/static/api) | — |
| DE | 307 | EUROSTAT | `prc_hicp_minr` | INDEX / base 2025 | YoY | `Inflation (HICP)` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_minr/default/table) | — |
| ES | 358 | EUROSTAT | `prc_hicp_minr` | INDEX / base 2025 | YoY | `Inflation (HICP)` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_minr/default/table) | — |
| IT | 409 | EUROSTAT | `prc_hicp_minr` | INDEX / base 2025 | YoY | `Inflation (HICP)` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_minr/default/table) | — |

### PCE Price Index

Frequency: `MONTHLY` · Measure: `INDEX` · Agenda `technical_name`: `PCE Price Index`

**What it is.** Prices for personal consumption expenditures — the Fed’s preferred consumer-inflation gauge. Published by the Bureau of Economic Analysis (BEA).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 37 | FRED | `PCEPI` | INDEX | YoY | [FRED](https://fred.stlouisfed.org/series/PCEPI) | — |

### Core CPI (excl. Energy)

Frequency: `MONTHLY` · Measure: `INDEX`

**What it is.** Consumer prices with energy items removed, to strip out volatile energy swings.

**By region** (where the bubble differs):

- **US:** Index with base year 1982 = 100. Published by the Bureau of Labor Statistics (BLS).
- **FR:** Index with base year 2025 = 100. Not seasonally adjusted. Published by the National Institute of Statistics and Economic Studies (INSEE).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 38 | FRED | `CPILEGSL` | INDEX / base 1982 | YoY | `Consumer Price Index` | [FRED](https://fred.stlouisfed.org/series/CPILEGSL) | — |
| FR | 132 | INSEE | `011814035` | INDEX / base 2025 | YoY | `Consumer price index - final results` | [INSEE](https://www.insee.fr/en/statistiques/serie/011814035) | — |

### Core CPI (excl. Food & Energy)

Frequency: `MONTHLY` · Measure: `INDEX`

**What it is.** Consumer prices with food and energy removed — a common underlying-inflation gauge.

**By region** (where the bubble differs):

- **US:** Index with base year 1982 = 100. Published by the Bureau of Labor Statistics (BLS).
- **FR:** Index with base year 2025 = 100. Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** Index with base year 2025 = 100. Not seasonally adjusted. Published by the Statistics Bureau of Japan (SBJ).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 39 | FRED | `CPILFESL` | INDEX / base 1982 | YoY | `Consumer Price Index` | [FRED](https://fred.stlouisfed.org/series/CPILFESL) | — |
| FR | 133 | INSEE | `011814143` | INDEX / base 2025 | YoY | `Consumer price index - final results` | [INSEE](https://www.insee.fr/en/statistiques/serie/011814143) | — |
| JP | 220 | STAT_OF_JP | `0703010601010090040` | INDEX / base 2025 | YoY | `Consumer Price Index` | [e-Stat](https://dashboard.e-stat.go.jp/en/static/api || https://www.e-stat.go.jp/en/stat-search?page=1&query=consumer%20price%20index%20food%20Japan) | — |

## Housing

Residential property price indexes.

### Home Prices

Measure: `INDEX`

**What it is** (by region):

- **US:** Residential property prices for dwellings. Index with base year 1980 = 100. Published by the Federal Housing Finance Agency (FHFA).
- **FR:** Notaires-INSEE constant-quality hedonic price index for second-hand dwellings (France excluding Mayotte), seasonally adjusted. Index with base year 2015 = 100. Used as France's Cross-Region Home Prices series. Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** Transaction prices for condominiums in Japan (MLIT Residential Property Price Index, seasonally adjusted). Index with base year 2010 = 100. Used as Japan's Cross-Region Home Prices series. Published by the Ministry of Land, Infrastructure, Transport and Tourism (MLIT).
- **DE:** Residential property prices for dwellings. Index with base year 2015 = 100. Published by Eurostat (Statistical Office of the European Union).
- **ES:** Residential property prices for dwellings. Index with base year 2015 = 100. Published by Eurostat (Statistical Office of the European Union).
- **IT:** Residential property prices for dwellings. Index with base year 2015 = 100. Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 40 | FRED | `USSTHPI` | INDEX / base 1980 | YoY | `House Price Index` | [FRED](https://fred.stlouisfed.org/series/USSTHPI) | — |
| FR | 134 | INSEE | `010567119` | INDEX / base 2015 | YoY | `Indexes of prices of second-hand dwellings` | [INSEE](https://www.insee.fr/en/statistiques/serie/010567119) | — |
| JP | 221 | MLIT | `condominiums_sa` | INDEX / base 2010 | YoY | `Residential Property Price Index — Condominiums` | [link](https://www.mlit.go.jp/totikensangyo/totikensangyo_tk5_000085.html) | MONTHLY_UPDATE |
| DE | 308 | EUROSTAT | `prc_hpi_q` | INDEX / base 2015 | YoY | `House price index` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/prc_hpi_q/default/table) | — |
| ES | 359 | EUROSTAT | `prc_hpi_q` | INDEX / base 2015 | YoY | `House price index` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/prc_hpi_q/default/table) | — |
| IT | 410 | EUROSTAT | `prc_hpi_q` | INDEX / base 2015 | YoY | `House price index` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/prc_hpi_q/default/table) | — |

### Home Prices (Detached houses)

Frequency: `MONTHLY` · Measure: `INDEX` · Agenda `technical_name`: `Residential Property Price Index — Detached House`

**What it is.** Transaction prices for detached houses in Japan. Index with base year 2010 = 100. Published by the Ministry of Land, Infrastructure, Transport and Tourism (MLIT).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| JP | 222 | MLIT | `detached_house_sa` | INDEX / base 2010 | YoY | [link](https://www.mlit.go.jp/totikensangyo/totikensangyo_tk5_000085.html) | MONTHLY_UPDATE |

## Confidence

Household sentiment and employment-outlook surveys (Michigan, INSEE Camme, Cabinet Office).

### Michigan Consumer Sentiment

Frequency: `MONTHLY` · Measure: `INDEX` · Agenda `technical_name`: `Surveys of Consumers`

**What it is.** Index of Consumer Sentiment from five household questions (February 1966 = 100). Monthly rotating sample of roughly 500 US households in the University of Michigan Surveys of Consumers. Higher readings mean more optimistic consumer sentiment. Published by the University of Michigan Surveys of Consumers.

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 41 | FRED | `UMCSENT` | — | Raw | [FRED](https://fred.stlouisfed.org/series/UMCSENT) | — |

### Employment Confidence

Frequency: `MONTHLY` · Measure: `INDEX`

**What it is.** Summary of household views on labour-market conditions and job security.

**By region** (where the bubble differs):

- **US:** Monthly rotating sample of roughly 500 US households (Michigan SCA labour-market judgements). Higher readings mean households see a stronger expected labour market. Published by the University of Michigan Surveys of Consumers.
- **FR:** INSEE business surveys on past and expected workforce across sectors (firm respondents, not households). Neutral: 100 (long-run average); above 100 means a more favorable employment climate than average. Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** Cabinet Office household survey judgements on employment conditions. Neutral: 50; above 50 means a more favorable employment outlook. Published by the Cabinet Office Economic and Social Research Institute (ESRI).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 42 | UNIV_MICHIGAN | `sca_table_30` | — | Raw | `Surveys of Consumers` | [link](https://data.sca.isr.umich.edu/data-archive/mine.php) | — |
| FR | 136 | INSEE | `000857190` | — | Raw | `Monthly consumer confidence survey` | [INSEE](https://www.insee.fr/fr/statistiques/serie/000857190) | — |
| JP | 224 | JP_CABINET_OFFICE | `shouhi_employment_sa` | — | Raw | `Consumer Confidence Survey` | [ESRI](https://www.esri.cao.go.jp/en/stat/shouhi/shouhi-e.html) | — |

### Consumer Confidence

Frequency: `MONTHLY` · Measure: `INDEX`

**What it is.** Summary of household views on living standards, finances, and major purchases.

**By region** (where the bubble differs):

- **FR:** INSEE Camme monthly household survey of roughly 2,000 households in metropolitan France. Neutral: 100 (long-run average); above 100 means more optimistic than the long-run average. Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** Cabinet Office Consumer Confidence Survey of households (nationwide sample of consumer judgements). Neutral: 50; above 50 means more optimistic than pessimistic. Published by the Cabinet Office Economic and Social Research Institute (ESRI).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| FR | 135 | INSEE | `001587668` | — | Raw | `Monthly consumer confidence survey` | [INSEE](https://www.insee.fr/en/statistiques/serie/001587668) | — |
| JP | 223 | JP_CABINET_OFFICE | `shouhi_cci_sa` | — | Raw | `Consumer Confidence Survey` | [ESRI](https://www.esri.cao.go.jp/en/stat/shouhi/shouhi-e.html) | — |

---

# Business

## Income

NFC profitability: gross capital share and net operating surplus. Japan lines are visible unwired stubs (empty ticker).

### Gross Capital Share

Frequency: `QUARTERLY` · Measure: `RATIO`

**What it is** (by region):

- **US:** Non-financial corporate capital share from Z.1 S.11: (net operating surplus + consumption of fixed capital) / NFC gross value added × 100. Starting from net surplus and adding depreciation once recovers a gross capital share; this is a national-accounts ratio, not accounting net profit (mixed income is not in this NFC numerator). Published by the Federal Reserve Board (FRB).
- **EU:** Non-financial corporate capital share: B2G_B3G / NFC gross value added. B2G_B3G is already a gross operating surplus (+ mixed income) aggregate, so consumption of fixed capital is not added again; national-accounts ratio, not accounting net profit. Published by Eurostat (Statistical Office of the European Union).
- **FR:** Non-financial corporate capital share: B2G_B3G / NFC gross value added. B2G_B3G is already a gross operating surplus (+ mixed income) aggregate, so consumption of fixed capital is not added again; national-accounts ratio, not accounting net profit. Published by Eurostat (Statistical Office of the European Union).
- **JP:** No comparable quarterly non-financial corporate capital share is seeded for Japan (visible unwired stub). Published by the Cabinet Office Economic and Social Research Institute (ESRI).
- **DE:** Non-financial corporate capital share: B2G_B3G / NFC gross value added. B2G_B3G is already a gross operating surplus (+ mixed income) aggregate, so consumption of fixed capital is not added again; national-accounts ratio, not accounting net profit. Published by Eurostat (Statistical Office of the European Union).
- **ES:** Non-financial corporate capital share: B2G_B3G / NFC gross value added. B2G_B3G is already a gross operating surplus (+ mixed income) aggregate, so consumption of fixed capital is not added again; national-accounts ratio, not accounting net profit. Published by Eurostat (Statistical Office of the European Union).
- **IT:** Non-financial corporate capital share: B2G_B3G / NFC gross value added. B2G_B3G is already a gross operating surplus (+ mixed income) aggregate, so consumption of fixed capital is not added again; national-accounts ratio, not accounting net profit. Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 43 | FRED | `gross_capital_share` | PERCENT | Raw | `Financial Accounts of the United States` | [link](https://www.federalreserve.gov/releases/z1/default.htm) | — |
| EU | 92 | EUROSTAT | `nasq_10_ki_gross_capital_share` | PERCENT | Raw | `Quarterly sector accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_ki/default/table) | — |
| FR | 137 | EUROSTAT | `nasq_10_ki_gross_capital_share` | PERCENT | Raw | `Quarterly sector accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_ki/default/table) | — |
| JP | 225 | JP_CABINET_OFFICE | — | PERCENT | Raw | `Annual Report on National Accounts` | — | unwired stub; MONTHLY_UPDATE |
| DE | 309 | EUROSTAT | `nasq_10_ki_gross_capital_share` | PERCENT | Raw | `Quarterly sector accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_ki/default/table) | — |
| ES | 360 | EUROSTAT | `nasq_10_ki_gross_capital_share` | PERCENT | Raw | `Quarterly sector accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_ki/default/table) | — |
| IT | 411 | EUROSTAT | `nasq_10_ki_gross_capital_share` | PERCENT | Raw | `Quarterly sector accounts` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_ki/default/table) | — |

### Net Operating Surplus

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is** (by region):

- **US:** Net operating surplus of nonfinancial corporate business after consumption of fixed capital (BEA NFC sector; excludes household mixed income). National-accounts operating surplus, not accounting net profit. The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Bureau of Economic Analysis (BEA).
- **FR:** Net operating surplus of non-financial corporations (S.11), derived as gross operating surplus (B2A3G) minus consumption of fixed capital (P51C); excludes household mixed income. National-accounts operating surplus, not accounting net profit. The printed level is the flow for that period (not annualized) and is not seasonally adjusted. Published by Eurostat (Statistical Office of the European Union).
- **JP:** No comparable quarterly non-financial corporate net operating surplus is seeded for Japan (visible unwired stub). Published by the Cabinet Office Economic and Social Research Institute (ESRI).
- **DE:** Net operating surplus of non-financial corporations (S.11), derived as gross operating surplus (B2A3G) minus consumption of fixed capital (P51C); excludes household mixed income. National-accounts operating surplus, not accounting net profit. The printed level is the flow for that period (not annualized) and is not seasonally adjusted. Published by Eurostat (Statistical Office of the European Union).
- **ES:** Net operating surplus of non-financial corporations (S.11), derived as gross operating surplus (B2A3G) minus consumption of fixed capital (P51C); excludes household mixed income. National-accounts operating surplus, not accounting net profit. The printed level is the flow for that period (not annualized) and is not seasonally adjusted. Published by Eurostat (Statistical Office of the European Union).
- **IT:** Net operating surplus of non-financial corporations (S.11), derived as gross operating surplus (B2A3G) minus consumption of fixed capital (P51C); excludes household mixed income. National-accounts operating surplus, not accounting net profit. The printed level is the flow for that period (not annualized) and is not seasonally adjusted. Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 44 | FRED | `W326RC1Q027SBEA` | B / USD | YTDYoY | `Gross Domestic Product` | [FRED](https://fred.stlouisfed.org/series/W326RC1Q027SBEA) | — |
| FR | 138 | EUROSTAT | `nasq_10_nf_tr_nos` | M / EUR | YTDYoY | `Non-financial corporations` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_nf_tr/default/table) | — |
| JP | 226 | JP_CABINET_OFFICE | — | B / JPY | YTDYoY | `Annual Report on National Accounts` | — | unwired stub; MONTHLY_UPDATE |
| DE | 310 | EUROSTAT | `nasq_10_nf_tr_nos` | M / EUR | YTDYoY | `Non-financial corporations` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_nf_tr/default/table) | — |
| ES | 361 | EUROSTAT | `nasq_10_nf_tr_nos` | M / EUR | YTDYoY | `Non-financial corporations` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_nf_tr/default/table) | — |
| IT | 412 | EUROSTAT | `nasq_10_nf_tr_nos` | M / EUR | YTDYoY | `Non-financial corporations` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_nf_tr/default/table) | — |

## Debt

BIS total credit to non-financial corporations (level and % of GDP) via FRED.

### Corporate Debt

Frequency: `QUARTERLY` · Measure: `STOCK` · Agenda `technical_name`: `Credit to Non-Financial Sector`

**What it is.** Credit to non-financial corporations (outstanding liabilities). The printed level is an outstanding stock and is not seasonally adjusted. Published by the Bank for International Settlements (BIS).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 47 | FRED | `CRDQUSANABIS` | B / USD | YoY | [FRED](https://fred.stlouisfed.org/series/CRDQUSANABIS) | — |
| FR | 141 | FRED | `CRDQFRANABIS` | B / EUR | YoY | [FRED](https://fred.stlouisfed.org/series/CRDQFRANABIS) | — |
| JP | 229 | FRED | `CRDQJPANABIS` | B / JPY | YoY | [FRED](https://fred.stlouisfed.org/series/CRDQJPANABIS) | — |
| DE | 313 | FRED | `CRDQDEANABIS` | B / EUR | YoY | [FRED](https://fred.stlouisfed.org/series/CRDQDEANABIS) | — |
| ES | 364 | FRED | `CRDQESANABIS` | B / EUR | YoY | [FRED](https://fred.stlouisfed.org/series/CRDQESANABIS) | — |
| IT | 415 | FRED | `CRDQITANABIS` | B / EUR | YoY | [FRED](https://fred.stlouisfed.org/series/CRDQITANABIS) | — |

### Corporate Debt (% GDP)

Frequency: `QUARTERLY` · Measure: `RATIO` · Agenda `technical_name`: `Credit to Non-Financial Sector`

**What it is.** Credit to non-financial corporations as a percent of GDP. Already expressed as a percent of GDP. Published by the Bank for International Settlements (BIS).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 48 | FRED | `QUSNAM770A` | PERCENT | Raw | [FRED](https://fred.stlouisfed.org/series/QUSNAM770A) | — |
| FR | 142 | FRED | `QFRNAM770A` | PERCENT | Raw | [FRED](https://fred.stlouisfed.org/series/QFRNAM770A) | — |
| JP | 230 | FRED | `QJPNAM770A` | PERCENT | Raw | [FRED](https://fred.stlouisfed.org/series/QJPNAM770A) | — |
| DE | 314 | FRED | `QDENAM770A` | PERCENT | Raw | [FRED](https://fred.stlouisfed.org/series/QDENAM770A) | — |
| ES | 365 | FRED | `QESNAM770A` | PERCENT | Raw | [FRED](https://fred.stlouisfed.org/series/QESNAM770A) | — |
| IT | 416 | FRED | `QITNAM770A` | PERCENT | Raw | [FRED](https://fred.stlouisfed.org/series/QITNAM770A) | — |

## Prices

Producer / manufacturing / services price indexes and core PPI variants.

### Producer Price Index

Frequency: `MONTHLY` · Measure: `INDEX` · Agenda `technical_name`: `Producer Price Index`

**What it is.** Selling prices received by domestic producers for their output. Published by the Bureau of Labor Statistics (BLS).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 49 | FRED | `PPIFIS` | INDEX | YoY | [FRED](https://fred.stlouisfed.org/series/PPIFIS) | — |

### Manufacturing Producer Price Index

Frequency: `MONTHLY` · Measure: `INDEX`

**What it is.** Producer prices in manufacturing. Not seasonally adjusted.

**By region** (where the bubble differs):

- **US:** Published by the Bureau of Labor Statistics (BLS).
- **FR:** Published by Eurostat (Statistical Office of the European Union).
- **JP:** Published by the Bank of Japan (BoJ).
- **DE:** Published by Eurostat (Statistical Office of the European Union).
- **ES:** Published by Eurostat (Statistical Office of the European Union).
- **IT:** Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 50 | FRED | `PCUOMFGOMFG` | INDEX | YoY | `Producer Price Index` | [FRED](https://fred.stlouisfed.org/series/PCUOMFGOMFG) | — |
| FR | 143 | EUROSTAT | `sts_inppd_m` | INDEX | YoY | `Domestic producer prices` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/sts_inppd_m/default/table) | — |
| JP | 231 | BOJ | `PRCG20_2200000000` | INDEX | YoY | `Corporate Goods Price Index` | [BoJ](https://www.stat-search.boj.or.jp/ssi/mtshtml/prcg20_2200000000pr_en.html) | — |
| DE | 315 | EUROSTAT | `sts_inppd_m` | INDEX | YoY | `Domestic producer prices` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/sts_inppd_m/default/table) | — |
| ES | 366 | EUROSTAT | `sts_inppd_m` | INDEX | YoY | `Domestic producer prices` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/sts_inppd_m/default/table) | — |
| IT | 417 | EUROSTAT | `sts_inppd_m` | INDEX | YoY | `Domestic producer prices` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/sts_inppd_m/default/table) | — |

### Core PPI (excl. Energy)

Frequency: `MONTHLY` · Measure: `INDEX` · Agenda `technical_name`: `Producer Price Index`

**What it is.** Producer prices with energy removed. Not seasonally adjusted. Published by the Bureau of Labor Statistics (BLS).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 51 | FRED | `WPUFD49107` | INDEX | YoY | [FRED](https://fred.stlouisfed.org/series/WPUFD49107) | — |

### Core Manufacturing PPI (excl. Energy)

Frequency: `MONTHLY` · Measure: `INDEX`

**What it is.** Manufacturing producer prices with energy removed. Not seasonally adjusted.

**By region** (where the bubble differs):

- **FR:** Published by the National Institute of Statistics and Economic Studies (INSEE).
- **DE:** Published by Eurostat (Statistical Office of the European Union).
- **ES:** Published by Eurostat (Statistical Office of the European Union).
- **IT:** Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| FR | 144 | INSEE | `010764315` | INDEX | YoY | `Industrial producer price indices` | [INSEE](https://www.insee.fr/en/statistiques/serie/010764315) | — |
| DE | 316 | EUROSTAT | `sts_inppd_m_x_mig_nrg` | INDEX | YoY | `Domestic producer prices` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/sts_inppd_m/default/table) | — |
| ES | 367 | EUROSTAT | `sts_inppd_m_x_mig_nrg` | INDEX | YoY | `Domestic producer prices` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/sts_inppd_m/default/table) | — |
| IT | 418 | EUROSTAT | `sts_inppd_m_x_mig_nrg` | INDEX | YoY | `Domestic producer prices` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/sts_inppd_m/default/table) | — |

### Services Producer Price Index

Frequency: `MONTHLY` · Measure: `INDEX` · Agenda `technical_name`: `Services Producer Price Index`

**What it is.** Producer prices for services. Not seasonally adjusted. Published by the Bank of Japan (BoJ).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| JP | 232 | BOJ | `PRCS20_5200000000` | INDEX | YoY | [BoJ](https://www.stat-search.boj.or.jp/ssi/mtshtml/prcs20_5200000000pr_en.html) | — |

## Confidence

Business surveys and PMIs (S&P, ISM, INSEE sector climates, Tankan, CEO Confidence, NAHB).

### S&P Manufacturing PMI

Frequency: `MONTHLY` · Measure: `INDEX` · Agenda `technical_name`: `S&P Global Manufacturing PMI`

**What it is.** Diffusion index of manufacturing activity. S&P Global purchasing-managers survey of manufacturing firms (panel size varies by country; typically hundreds of firms). Neutral: 50 (above = manufacturing expansion, below = contraction). Published by S&P Global.

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 55 | TRADING_ECONOMICS | `us_sp_manufacturing_pmi` | — | Raw | [TE](https://tradingeconomics.com/united-states/manufacturing-pmi) | — |
| FR | 148 | TRADING_ECONOMICS | `fr_sp_manufacturing_pmi` | — | Raw | [TE](https://tradingeconomics.com/france/manufacturing-pmi) | — |
| JP | 236 | TRADING_ECONOMICS | `jp_sp_manufacturing_pmi` | — | Raw | [TE](https://tradingeconomics.com/japan/manufacturing-pmi) | — |

### S&P Services PMI

Frequency: `MONTHLY` · Measure: `INDEX` · Agenda `technical_name`: `S&P Global Services PMI`

**What it is.** Diffusion index of services activity. S&P Global purchasing-managers survey of services firms (panel size varies by country; typically hundreds of firms). Neutral: 50 (above = services expansion, below = contraction). Published by S&P Global.

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 56 | TRADING_ECONOMICS | `us_sp_services_pmi` | — | Raw | [TE](https://tradingeconomics.com/united-states/services-pmi) | — |
| FR | 149 | TRADING_ECONOMICS | `fr_sp_services_pmi` | — | Raw | [TE](https://tradingeconomics.com/france/services-pmi) | — |
| JP | 237 | TRADING_ECONOMICS | `jp_sp_services_pmi` | — | Raw | [TE](https://tradingeconomics.com/japan/services-pmi) | — |

### ISM Manufacturing PMI

Frequency: `MONTHLY` · Measure: `INDEX` · Agenda `technical_name`: `ISM Manufacturing PMI`

**What it is.** Diffusion index of US manufacturing activity from purchasing managers. ISM survey of purchasing managers at US manufacturing firms (panel of several hundred companies). Neutral: 50 (above = manufacturing expansion, below = contraction). Published by the Institute for Supply Management (ISM).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 57 | ISM | `ism_manufacturing_pmi` | — | Raw | [link](https://www.ismworld.org/supply-management-news-and-reports/reports/ism-report-on-business/pmi/) | — |

### ISM Services PMI

Frequency: `MONTHLY` · Measure: `INDEX` · Agenda `technical_name`: `ISM Services PMI`

**What it is.** Diffusion index of US non-manufacturing / services activity from purchasing managers. ISM survey of purchasing managers at US non-manufacturing / services firms (panel of several hundred companies). Neutral: 50 (above = services expansion, below = contraction). Published by the Institute for Supply Management (ISM).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 58 | ISM | `ism_services_pmi` | — | Raw | [link](https://www.ismworld.org/supply-management-news-and-reports/reports/ism-report-on-business/services/) | — |

### CEO Confidence

Frequency: `QUARTERLY` · Measure: `INDEX` · Agenda `technical_name`: `Measure of CEO Confidence`

**What it is.** Chief-executive sentiment on near-term business conditions. The Conference Board survey of US chief executives. Neutral: 50; above 50 means CEOs are more optimistic than pessimistic on near-term conditions. Published by The Conference Board.

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 59 | CONFERENCE_BOARD | `ceo_confidence` | — | Raw | [link](https://www.conference-board.org/topics/CEO-Confidence) | — |

### NAHB Housing Market Index

Frequency: `MONTHLY` · Measure: `INDEX` · Agenda `technical_name`: `NAHB/Wells Fargo Housing Market Index`

**What it is.** Home-builder views on single-family housing market conditions. Monthly survey of single-family home builders (NAHB / Wells Fargo). Neutral: 50; above 50 means more builders view conditions as good than poor. Published by the National Association of Home Builders (NAHB).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 60 | NAHB | `nahb_hmi` | — | Raw | [link](https://www.nahb.org/news-and-economics/housing-economics/indices/housing-market-index) | — |

### Aggregate Business Confidence

Frequency: `MONTHLY` · Measure: `INDEX` · Agenda `technical_name`: `Business indicator`

**What it is.** All-sector business-climate summary from firm opinion balances. INSEE monthly opinion surveys of firms in industry, services, retail, and construction. Neutral: 100 (long-run average, standard deviation 10); above 100 means a more favorable business climate than average. Published by the National Institute of Statistics and Economic Studies (INSEE).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| FR | 150 | INSEE | `001565530` | — | Raw | [INSEE](https://www.insee.fr/en/statistiques/serie/001565530) | — |

### Service Business Confidence

Frequency: `MONTHLY` · Measure: `INDEX` · Agenda `technical_name`: `Monthly survey of services`

**What it is.** Services business-climate summary from firm opinion balances. INSEE monthly opinion survey of services firms. Neutral: 100 (long-run average, standard deviation 10); above 100 means a more favorable services climate than average. Published by the National Institute of Statistics and Economic Studies (INSEE).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| FR | 151 | INSEE | `001587025` | — | Raw | [INSEE](https://www.insee.fr/en/statistiques/serie/001587025) | — |

### Retail Business Confidence

Frequency: `MONTHLY` · Measure: `INDEX` · Agenda `technical_name`: `Monthly survey of retailing`

**What it is.** Retail business-climate summary from firm opinion balances. INSEE monthly opinion survey of retail firms. Neutral: 100 (long-run average, standard deviation 10); above 100 means a more favorable retail climate than average. Published by the National Institute of Statistics and Economic Studies (INSEE).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| FR | 152 | INSEE | `001580428` | — | Raw | [INSEE](https://www.insee.fr/en/statistiques/serie/001580428) | — |

### Manufacturing Business Confidence

Frequency: `MONTHLY` · Measure: `INDEX` · Agenda `technical_name`: `Monthly business survey (goods-producing industries)`

**What it is.** Manufacturing business-climate summary from firm opinion balances. INSEE monthly opinion survey of manufacturing firms. Neutral: 100 (long-run average, standard deviation 10); above 100 means a more favorable industry climate than average. Published by the National Institute of Statistics and Economic Studies (INSEE).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| FR | 153 | INSEE | `001585934` | — | Raw | [INSEE](https://www.insee.fr/en/statistiques/serie/001585934) | — |

### Housing Business Confidence

Frequency: `MONTHLY` · Measure: `INDEX` · Agenda `technical_name`: `Monthly survey of building`

**What it is.** Building / construction business-climate summary from firm opinion balances. INSEE monthly opinion survey of building / construction firms. Neutral: 100 (long-run average, standard deviation 10); above 100 means a more favorable construction climate than average. Published by the National Institute of Statistics and Economic Studies (INSEE).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| FR | 154 | INSEE | `001586890` | — | Raw | [INSEE](https://www.insee.fr/en/statistiques/serie/001586890) | — |

### Labour Market Expectations

Frequency: `MONTHLY` · Measure: `INDEX` · Agenda `technical_name`: `Business indicator`

**What it is.** Household opinion balance on future unemployment. INSEE Camme monthly household survey of roughly 2,000 households in metropolitan France. Stored as an opinion balance / diffusion level, not a currency amount. Neutral: 0; above 0 means more households expect unemployment to rise. Published by the National Institute of Statistics and Economic Studies (INSEE).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| FR | 155 | INSEE | `001796629` | — | Raw | [INSEE](https://www.insee.fr/en/statistiques/serie/001796629) | — |

### Tankan Large Employment Conditions DI

Frequency: `QUARTERLY` · Measure: `INDEX` · Agenda `technical_name`: `Tankan`

**What it is.** Bank of Japan Tankan judgement diffusion index for business conditions or employment (share answering favorable minus unfavorable; employment DI uses excessive minus insufficient). Bank of Japan Tankan survey of enterprises (thousands of firms across capital-size classes; exact panel changes with each survey round). Stored as an opinion balance / diffusion level, not a currency amount. Neutral: 0; above 0 means more firms report favorable conditions (or excess employment) than the opposite. Published by the Bank of Japan (BoJ).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| JP | 238 | BOJ | `TK99F0000608GCQ01000` | — | Raw | [BoJ](https://www.stat-search.boj.or.jp/ssi/mtshtml/co_q_6_en.html) | — |

### Tankan Large Manufacturing DI

Frequency: `QUARTERLY` · Measure: `INDEX` · Agenda `technical_name`: `Tankan`

**What it is.** Bank of Japan Tankan judgement diffusion index for business conditions or employment (share answering favorable minus unfavorable; employment DI uses excessive minus insufficient). Bank of Japan Tankan survey of enterprises (thousands of firms across capital-size classes; exact panel changes with each survey round). Stored as an opinion balance / diffusion level, not a currency amount. Neutral: 0; above 0 means more firms report favorable conditions (or excess employment) than the opposite. Published by the Bank of Japan (BoJ).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| JP | 239 | BOJ | `TK99F1000601GCQ01000` | — | Raw | [BoJ](https://www.stat-search.boj.or.jp/ssi/mtshtml/co_q_6_en.html) | — |

### Tankan Large Nonmanufacturing DI

Frequency: `QUARTERLY` · Measure: `INDEX` · Agenda `technical_name`: `Tankan`

**What it is.** Bank of Japan Tankan judgement diffusion index for business conditions or employment (share answering favorable minus unfavorable; employment DI uses excessive minus insufficient). Bank of Japan Tankan survey of enterprises (thousands of firms across capital-size classes; exact panel changes with each survey round). Stored as an opinion balance / diffusion level, not a currency amount. Neutral: 0; above 0 means more firms report favorable conditions (or excess employment) than the opposite. Published by the Bank of Japan (BoJ).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| JP | 240 | BOJ | `TK99F2000601GCQ01000` | — | Raw | [BoJ](https://www.stat-search.boj.or.jp/ssi/mtshtml/co_q_6_en.html) | — |

### Tankan Medium Employment Conditions DI

Frequency: `QUARTERLY` · Measure: `INDEX` · Agenda `technical_name`: `Tankan`

**What it is.** Bank of Japan Tankan judgement diffusion index for business conditions or employment (share answering favorable minus unfavorable; employment DI uses excessive minus insufficient). Bank of Japan Tankan survey of enterprises (thousands of firms across capital-size classes; exact panel changes with each survey round). Stored as an opinion balance / diffusion level, not a currency amount. Neutral: 0; above 0 means more firms report favorable conditions (or excess employment) than the opposite. Published by the Bank of Japan (BoJ).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| JP | 241 | BOJ | `TK99F0000608GCQ02000` | — | Raw | [BoJ](https://www.stat-search.boj.or.jp/ssi/mtshtml/co_q_6_en.html) | — |

### Tankan Medium Manufacturing DI

Frequency: `QUARTERLY` · Measure: `INDEX` · Agenda `technical_name`: `Tankan`

**What it is.** Bank of Japan Tankan judgement diffusion index for business conditions or employment (share answering favorable minus unfavorable; employment DI uses excessive minus insufficient). Bank of Japan Tankan survey of enterprises (thousands of firms across capital-size classes; exact panel changes with each survey round). Stored as an opinion balance / diffusion level, not a currency amount. Neutral: 0; above 0 means more firms report favorable conditions (or excess employment) than the opposite. Published by the Bank of Japan (BoJ).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| JP | 242 | BOJ | `TK99F1000601GCQ02000` | — | Raw | [BoJ](https://www.stat-search.boj.or.jp/ssi/mtshtml/co_q_6_en.html) | — |

### Tankan Medium Nonmanufacturing DI

Frequency: `QUARTERLY` · Measure: `INDEX` · Agenda `technical_name`: `Tankan`

**What it is.** Bank of Japan Tankan judgement diffusion index for business conditions or employment (share answering favorable minus unfavorable; employment DI uses excessive minus insufficient). Bank of Japan Tankan survey of enterprises (thousands of firms across capital-size classes; exact panel changes with each survey round). Stored as an opinion balance / diffusion level, not a currency amount. Neutral: 0; above 0 means more firms report favorable conditions (or excess employment) than the opposite. Published by the Bank of Japan (BoJ).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| JP | 243 | BOJ | `TK99F2000601GCQ02000` | — | Raw | [BoJ](https://www.stat-search.boj.or.jp/ssi/mtshtml/co_q_6_en.html) | — |

### Tankan Small Employment Conditions DI

Frequency: `QUARTERLY` · Measure: `INDEX` · Agenda `technical_name`: `Tankan`

**What it is.** Bank of Japan Tankan judgement diffusion index for business conditions or employment (share answering favorable minus unfavorable; employment DI uses excessive minus insufficient). Bank of Japan Tankan survey of enterprises (thousands of firms across capital-size classes; exact panel changes with each survey round). Stored as an opinion balance / diffusion level, not a currency amount. Neutral: 0; above 0 means more firms report favorable conditions (or excess employment) than the opposite. Published by the Bank of Japan (BoJ).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| JP | 244 | BOJ | `TK99F0000608GCQ03000` | — | Raw | [BoJ](https://www.stat-search.boj.or.jp/ssi/mtshtml/co_q_6_en.html) | — |

### Tankan Small Manufacturing DI

Frequency: `QUARTERLY` · Measure: `INDEX` · Agenda `technical_name`: `Tankan`

**What it is.** Bank of Japan Tankan judgement diffusion index for business conditions or employment (share answering favorable minus unfavorable; employment DI uses excessive minus insufficient). Bank of Japan Tankan survey of enterprises (thousands of firms across capital-size classes; exact panel changes with each survey round). Stored as an opinion balance / diffusion level, not a currency amount. Neutral: 0; above 0 means more firms report favorable conditions (or excess employment) than the opposite. Published by the Bank of Japan (BoJ).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| JP | 245 | BOJ | `TK99F1000601GCQ03000` | — | Raw | [BoJ](https://www.stat-search.boj.or.jp/ssi/mtshtml/co_q_6_en.html) | — |

### Tankan Small Nonmanufacturing DI

Frequency: `QUARTERLY` · Measure: `INDEX` · Agenda `technical_name`: `Tankan`

**What it is.** Bank of Japan Tankan judgement diffusion index for business conditions or employment (share answering favorable minus unfavorable; employment DI uses excessive minus insufficient). Bank of Japan Tankan survey of enterprises (thousands of firms across capital-size classes; exact panel changes with each survey round). Stored as an opinion balance / diffusion level, not a currency amount. Neutral: 0; above 0 means more firms report favorable conditions (or excess employment) than the opposite. Published by the Bank of Japan (BoJ).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| JP | 246 | BOJ | `TK99F2000601GCQ03000` | — | Raw | [BoJ](https://www.stat-search.boj.or.jp/ssi/mtshtml/co_q_6_en.html) | — |

## Investment

Corporate GFCF (NFC / financial corporations where seeded).

### Corporate Gross Fixed Capital Formation

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** Non-financial corporation investment in fixed assets.

**By region** (where the bubble differs):

- **US:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Federal Reserve Board (FRB).
- **FR:** The printed level is the flow for that period (not annualized) and is not seasonally adjusted. Published by Eurostat (Statistical Office of the European Union).
- **JP:** Published by the Cabinet Office Economic and Social Research Institute (ESRI).
- **DE:** The printed level is the flow for that period (not annualized) and is not seasonally adjusted. Published by Eurostat (Statistical Office of the European Union).
- **ES:** The printed level is the flow for that period (not annualized) and is not seasonally adjusted. Published by Eurostat (Statistical Office of the European Union).
- **IT:** The printed level is the flow for that period (not annualized) and is not seasonally adjusted. Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 45 | FRED | `BOGZ1FA105019005Q` | B / USD | YTDYoY | `Z.1 Financial Accounts` | [FRED](https://fred.stlouisfed.org/series/BOGZ1FA105019005Q) | — |
| FR | 139 | EUROSTAT | `nasq_10_nf_tr_gfcf_corp` | M / EUR | YTDYoY | `Non-financial transactions — corporate GFCF` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_nf_tr/default/table) | — |
| JP | 227 | JP_CABINET_OFFICE | — | B / JPY | YTDYoY | `Annual Report on National Accounts` | — | unwired stub; MONTHLY_UPDATE |
| DE | 311 | EUROSTAT | `nasq_10_nf_tr_gfcf_corp` | M / EUR | YTDYoY | `Non-financial transactions — corporate GFCF` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_nf_tr/default/table) | — |
| ES | 362 | EUROSTAT | `nasq_10_nf_tr_gfcf_corp` | M / EUR | YTDYoY | `Non-financial transactions — corporate GFCF` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_nf_tr/default/table) | — |
| IT | 413 | EUROSTAT | `nasq_10_nf_tr_gfcf_corp` | M / EUR | YTDYoY | `Non-financial transactions — corporate GFCF` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nasq_10_nf_tr/default/table) | — |

## Cost

Labour cost indexes.

### Labour Cost Index

Frequency: `QUARTERLY` · Measure: `INDEX`

**What it is** (by region):

- **US:** Employment Cost Index of total compensation (wages + benefits) for private-industry workers — a compensation-cost index, not unit labour costs. Index with base year 2005 = 100. Published by the Bureau of Labor Statistics (BLS).
- **FR:** Laspeyres chain index of hourly labour costs (wages plus employer social contributions/taxes net of subsidies) in market non-agricultural sectors B–N. Index with base year 2020 = 100. Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** No comparable quarterly labour-cost index is seeded for Japan (visible unwired stub). Published by the Cabinet Office Economic and Social Research Institute (ESRI).
- **DE:** Labour cost index of hourly labour costs for employees (wages and salaries plus labour costs other than wages). Index with base year 2020 = 100. Published by Eurostat (Statistical Office of the European Union).
- **ES:** Labour cost index of hourly labour costs for employees (wages and salaries plus labour costs other than wages). Index with base year 2020 = 100. Published by Eurostat (Statistical Office of the European Union).
- **IT:** Labour cost index of hourly labour costs for employees (wages and salaries plus labour costs other than wages). Index with base year 2020 = 100. Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 46 | FRED | `ECICOM` | INDEX / base 2005 | YoY | `Employment Cost Index` | [FRED](https://fred.stlouisfed.org/series/ECICOM) | — |
| FR | 140 | INSEE | `010761999` | INDEX / base 2020 | YoY | `Labour cost index (LCI) - Detailed results` | [INSEE](https://www.insee.fr/en/statistiques/serie/010761999) | — |
| JP | 228 | JP_CABINET_OFFICE | — | INDEX | YoY | `Labour Cost Index` | — | unwired stub; MONTHLY_UPDATE |
| DE | 312 | EUROSTAT | `lc_lci_r2_q` | INDEX / base 2020 | YoY | `Labour cost index` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/lc_lci_r2_q/default/table) | — |
| ES | 363 | EUROSTAT | `lc_lci_r2_q` | INDEX / base 2020 | YoY | `Labour cost index` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/lc_lci_r2_q/default/table) | — |
| IT | 414 | EUROSTAT | `lc_lci_r2_q` | INDEX / base 2020 | YoY | `Labour cost index` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/lc_lci_r2_q/default/table) | — |

## Production

Industrial production, capacity utilisation / operating ratio, new orders, machinery orders.

### Industrial Production

Frequency: `MONTHLY` · Measure: `INDEX`

**What it is.** Volume of output in industry (typically mining, manufacturing, and utilities).

**By region** (where the bubble differs):

- **US:** Index with base year 2017 = 100. Published by the Federal Reserve Board (FRB).
- **FR:** Index with base year 2021 = 100. Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** Index with base year 2020 = 100. Published by the Statistics Bureau of Japan (SBJ).
- **DE:** Index with base year 2021 = 100. Published by Eurostat (Statistical Office of the European Union).
- **ES:** Index with base year 2021 = 100. Published by Eurostat (Statistical Office of the European Union).
- **IT:** Index with base year 2021 = 100. Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 52 | FRED | `INDPRO` | INDEX / base 2017 | YoY | `G.17 Industrial Production and Capacity Utilization` | [FRED](https://fred.stlouisfed.org/series/INDPRO) | — |
| FR | 145 | INSEE | `010768261` | INDEX / base 2021 | YoY | `Industrial production index` | [INSEE](https://www.insee.fr/en/statistiques/serie/010768261) | — |
| JP | 233 | STAT_OF_JP | `0502070301000090010` | INDEX / base 2020 | YoY | `Indices of Industrial Production` | [e-Stat](https://dashboard.e-stat.go.jp/en/static/api) | — |
| DE | 317 | EUROSTAT | `sts_inpr_m` | INDEX / base 2021 | YoY | `Industrial production` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/sts_inpr_m/default/table) | — |
| ES | 368 | EUROSTAT | `sts_inpr_m` | INDEX / base 2021 | YoY | `Industrial production` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/sts_inpr_m/default/table) | — |
| IT | 419 | EUROSTAT | `sts_inpr_m` | INDEX / base 2021 | YoY | `Industrial production` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/sts_inpr_m/default/table) | — |

### Capacity Utilisation

Measure: `RATE`

**What it is.** Share of industrial capacity in use.

**By region** (where the bubble differs):

- **US:** Higher readings mean a larger share of industrial capacity is in use. Published by the Federal Reserve Board (FRB).
- **EU:** Higher readings mean a larger share of industrial capacity is in use. Published by Eurostat (Statistical Office of the European Union).
- **FR:** Banque de France monthly business survey of manufacturing firms. Higher readings mean a larger share of industrial capacity is in use. Published by Banque de France (BdF).
- **DE:** Higher readings mean a larger share of industrial capacity is in use. Published by Eurostat (Statistical Office of the European Union).
- **ES:** Higher readings mean a larger share of industrial capacity is in use. Published by Eurostat (Statistical Office of the European Union).
- **IT:** Higher readings mean a larger share of industrial capacity is in use. Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 53 | FRED | `TCU` | PERCENT | Raw | `G.17 Industrial Production and Capacity Utilization` | [FRED](https://fred.stlouisfed.org/series/TCU) | — |
| EU | 93 | EUROSTAT | `ei_bsin_q_r2_icu` | PERCENT | Raw | `Business and consumer surveys` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/ei_bsin_q_r2/default/table) | — |
| FR | 146 | BANQUE_DE_FRANCE | `CONJ.M.N01.S.IN.000CZ.TUTSM000.10` | PERCENT | Raw | `Monthly Business Survey in Industry` | [BdF](https://webstat.banque-france.fr/fr/catalogue/conj/CONJ.M.N01.S.IN.000CZ.TUTSM000.10) | MONTHLY_UPDATE |
| DE | 318 | EUROSTAT | `ei_bsin_q_r2_icu` | PERCENT | Raw | `Business and consumer surveys` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/ei_bsin_q_r2/default/table) | — |
| ES | 369 | EUROSTAT | `ei_bsin_q_r2_icu` | PERCENT | Raw | `Business and consumer surveys` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/ei_bsin_q_r2/default/table) | — |
| IT | 420 | EUROSTAT | `ei_bsin_q_r2_icu` | PERCENT | Raw | `Business and consumer surveys` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/ei_bsin_q_r2/default/table) | — |

### New Business Orders

Frequency: `MONTHLY` · Measure: `INDEX`

**What it is.** Firms’ reports on recent change in new orders received. For France, Banque de France monthly survey of manufacturing firms on new orders; for the US, purchasing-managers new-orders diffusion.

**By region** (where the bubble differs):

- **US:** Neutral: 50; above 50 means expanding new orders. Published by the Institute for Supply Management (ISM).
- **FR:** Stored as an opinion balance / diffusion level, not a currency amount. Neutral: 0 (stability); above 0 means more firms report rising orders. Published by Banque de France (BdF).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 54 | FRED | `AMTMNO` | M / USD | YoY | `Manufacturers New Orders` | [FRED](https://fred.stlouisfed.org/series/AMTMNO) | — |
| FR | 147 | BANQUE_DE_FRANCE | `CONJ.M.N01.S.IN.000CZ.CRTEM100.10` | — | Raw | `Manufacturing new orders opinion balance` | [BdF](https://webstat.banque-france.fr/en/catalogue/conj/conj-m-n01-s-in-000cz-crtem100-10) | MONTHLY_UPDATE |

### Operating Ratio Index

Frequency: `MONTHLY` · Measure: `INDEX` · Agenda `technical_name`: `Indices of Production Capacity and Operating Ratio`

**What it is.** How intensively production capacity is used in industry. Index with base year 2020 = 100. Published by the Ministry of Economy, Trade and Industry (METI).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| JP | 234 | METI | `operating_ratio_mfg_sa` | INDEX / base 2020 | YoY | [e-Stat](https://www.e-stat.go.jp/en/statistics/00550320) | — |

### Machinery Orders

Frequency: `MONTHLY` · Measure: `FLOW` · Agenda `technical_name`: `Machinery Orders`

**What it is.** Private-sector orders for machinery — a leading signal of business investment demand in Japan. The printed level is the seasonally adjusted flow for that period (not annualized). Published by the Cabinet Office Economic and Social Research Institute (ESRI).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| JP | 235 | JP_CABINET_OFFICE | `machinery_orders_private_ex_volatile_sa` | B / JPY | YoY | [ESRI](https://www.esri.cao.go.jp/en/stat/juchu/juchu-e.html) | — |

---

# Government

## Debt

General-government gross debt stocks (default display often `vsGDP`).

### Government Debt

Frequency: `QUARTERLY` · Measure: `STOCK`

**What it is.** Outstanding general-government consolidated gross debt. The printed level is an outstanding stock.

**By region** (where the bubble differs):

- **US:** Published by the Federal Reserve Board (FRB).
- **FR:** Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** Published by the Cabinet Office Economic and Social Research Institute (ESRI).
- **DE:** Published by Eurostat (Statistical Office of the European Union).
- **ES:** Published by Eurostat (Statistical Office of the European Union).
- **IT:** Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 86 | FRED | `gg_debt_securities_loans` | M / USD | vsGDP | `Z.1 Financial Accounts` | [FRED](https://fred.stlouisfed.org/series/BOGZ1FL374122005Q) | — |
| FR | 184 | INSEE | `010777616` | B / EUR | vsGDP | `Debt of the general government according to the Maastricht definition` | [INSEE](https://www.insee.fr/en/statistiques/serie/010777616) | — |
| JP | 273 | JP_CABINET_OFFICE | `ggd_total` | B / JPY | vsGDP | `General Government Gross Debt` | [ESRI](https://www.esri.cao.go.jp/en/sna/sddsplus/sddsplus_top.html) | MONTHLY_UPDATE |
| DE | 324 | EUROSTAT | `gov_10q_ggdebt_mio` | M / EUR | vsGDP | `Quarterly government debt` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggdebt/default/table) | — |
| ES | 375 | EUROSTAT | `gov_10q_ggdebt_mio` | M / EUR | vsGDP | `Quarterly government debt` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggdebt/default/table) | — |
| IT | 426 | EUROSTAT | `gov_10q_ggdebt_mio` | M / EUR | vsGDP | `Quarterly government debt` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggdebt/default/table) | — |

## Budget

Budget balance, revenue / expenditure drill-down, IMF primary balance, and annual government expenditures by function (COFOG / BEA Table 3.16). IMF primary-balance seeds use `MONTHLY_UPDATE`.

### Annual Government Expenditures

Frequency: `ANNUAL` · Measure: `FLOW`

**What it is.** Annual functional spending totals for general government.

**By region** (where the bubble differs):

- **US:** Published by the Bureau of Economic Analysis (BEA).
- **FR:** Published by Eurostat (Statistical Office of the European Union).
- **JP:** Published by the Cabinet Office Economic and Social Research Institute (ESRI).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 61 | BEA | `bea_t31600_total` | B / USD | YTDvsGDP | `Government current expenditures by function (Table 3.16)` | [BEA](https://www.bea.gov/itable/national-gdp-and-personal-income) | — |
| FR | 156 | EUROSTAT | `gov_10a_exp_total` | M / EUR | YTDvsGDP | `General government expenditure by function (TOTAL)` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10a_exp/default/table) | — |
| JP | 247 | JP_CABINET_OFFICE | `esri_cofog_total` | B / JPY | YTDvsGDP | `General government total outlays by function (COFOG, Total)` | [ESRI](https://www.esri.cao.go.jp/en/sna/kakuhou/kakuhou_top.html) | MONTHLY_UPDATE |

### Government Budget Balance

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** General-government net lending / net borrowing (revenue minus expenditure).

**By region** (where the bubble differs):

- **US:** Source prints are seasonally adjusted annual rates; the recap converts each quarter to a period amount (÷4) and shows their year-to-date sum from Q1 through the latest available quarter (for example '2025 (Q1 - Q3)'), compared with the same Q1…Qn window a year earlier. Published by the Bureau of Economic Analysis (BEA).
- **FR:** Source prints are seasonally adjusted period flows; default chart / recap mode YTDvsGDP sums Q1 through the latest available quarter (for example '2025 (Q1 - Q3)'), compared with the same Q1…Qn window a year earlier. Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** The source stores quarterly flows; the displayed figure is their year-to-date sum from Q1 through the latest available quarter in that calendar year (for example '2025 (Q1 - Q3)'), compared with the same Q1…Qn window a year earlier. Published by the Cabinet Office Economic and Social Research Institute (ESRI).
- **DE:** Source prints are non-seasonally adjusted period flows; default chart / recap mode YTDvsGDP sums Q1 through the latest available quarter (for example '2025 (Q1 - Q3)'), compared with the same Q1…Qn window a year earlier. Published by Eurostat (Statistical Office of the European Union).
- **ES:** Source prints are non-seasonally adjusted period flows; default chart / recap mode YTDvsGDP sums Q1 through the latest available quarter (for example '2025 (Q1 - Q3)'), compared with the same Q1…Qn window a year earlier. Published by Eurostat (Statistical Office of the European Union).
- **IT:** Source prints are non-seasonally adjusted period flows; default chart / recap mode YTDvsGDP sums Q1 through the latest available quarter (for example '2025 (Q1 - Q3)'), compared with the same Q1…Qn window a year earlier. Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 62 | FRED | `AD01RC1Q027SBEA` | B / USD | YTDvsGDP | `Gross Domestic Product` | [FRED](https://fred.stlouisfed.org/series/AD01RC1Q027SBEA) | — |
| FR | 157 | INSEE | `011794759` | M / EUR | YTDvsGDP | `Net lending (+) or net borrowing (-) of general government` | [INSEE](https://www.insee.fr/en/statistiques/serie/011794759) | — |
| JP | 248 | JP_CABINET_OFFICE | `ggo_net_lending` | B / JPY | YTDvsGDP | `General Government Operations` | [ESRI](https://www.esri.cao.go.jp/en/sna/sddsplus/sddsplus_top.html) | MONTHLY_UPDATE |
| DE | 319 | EUROSTAT | `gov_10q_ggnfa_balance` | M / EUR | YTDvsGDP | `Quarterly non-financial accounts for general government` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggnfa/default/table) | — |
| ES | 370 | EUROSTAT | `gov_10q_ggnfa_balance` | M / EUR | YTDvsGDP | `Quarterly non-financial accounts for general government` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggnfa/default/table) | — |
| IT | 421 | EUROSTAT | `gov_10q_ggnfa_balance` | M / EUR | YTDvsGDP | `Quarterly non-financial accounts for general government` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggnfa/default/table) | — |

### Government Primary Balance (IMF)

Frequency: `ANNUAL` · Measure: `RATE` · Agenda `technical_name`: `Fiscal Monitor`

**What it is.** Budget balance excluding interest — the IMF WEO primary-balance concept. Published by the International Monetary Fund (IMF).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 63 | IMF | `GGXONLB_G01_GDP_PT` | PERCENT | Raw | [IMF](https://www.imf.org/external/datamapper/GGXONLB_G01_GDP_PT) | MONTHLY_UPDATE |
| EU | 94 | IMF | `GGXONLB_G01_GDP_PT` | PERCENT | Raw | [IMF](https://www.imf.org/external/datamapper/GGXONLB_G01_GDP_PT) | MONTHLY_UPDATE |
| FR | 158 | IMF | `GGXONLB_G01_GDP_PT` | PERCENT | Raw | [IMF](https://www.imf.org/external/datamapper/GGXONLB_G01_GDP_PT) | MONTHLY_UPDATE |
| JP | 249 | IMF | `GGXONLB_G01_GDP_PT` | PERCENT | Raw | [IMF](https://www.imf.org/external/datamapper/GGXONLB_G01_GDP_PT) | MONTHLY_UPDATE |
| DE | 320 | IMF | `GGXONLB_G01_GDP_PT` | PERCENT | Raw | [IMF](https://www.imf.org/external/datamapper/GGXONLB_G01_GDP_PT) | MONTHLY_UPDATE |
| ES | 371 | IMF | `GGXONLB_G01_GDP_PT` | PERCENT | Raw | [IMF](https://www.imf.org/external/datamapper/GGXONLB_G01_GDP_PT) | MONTHLY_UPDATE |
| IT | 422 | IMF | `GGXONLB_G01_GDP_PT` | PERCENT | Raw | [IMF](https://www.imf.org/external/datamapper/GGXONLB_G01_GDP_PT) | MONTHLY_UPDATE |

### Economic Affairs

Frequency: `ANNUAL` · Measure: `FLOW`

**What it is** (by region):

- **US:** General-government current expenditure in this function from BEA NIPA Table 3.16 (US functional classification; not Eurostat COFOG). Published by the Bureau of Economic Analysis (BEA).
- **FR:** General-government expenditure in this COFOG function (Eurostat gov_10a_exp). Published by Eurostat (Statistical Office of the European Union).
- **JP:** General-government expenditure in this COFOG function (ESRI / Cabinet Office functional accounts). Published by the Cabinet Office Economic and Social Research Institute (ESRI).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 64 | BEA | `bea_t31600_economic_affairs` | B / USD | YTDRelYoY | `Government current expenditures by function (Table 3.16, line 13)` | [BEA](https://www.bea.gov/itable/national-gdp-and-personal-income) | COMPONENT; parent: Annual Government Expenditures |
| FR | 160 | EUROSTAT | `gov_10a_exp_gf04` | M / EUR | YTDRelYoY | `General government expenditure by function (GF04)` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10a_exp/default/table) | COMPONENT; parent: Annual Government Expenditures |
| JP | 251 | JP_CABINET_OFFICE | `esri_cofog_gf04` | B / JPY | YTDRelYoY | `General government total outlays by function (GF04)` | [ESRI](https://www.esri.cao.go.jp/en/sna/kakuhou/kakuhou_top.html) | MONTHLY_UPDATE; COMPONENT; parent: Annual Government Expenditures |

### Education

Frequency: `ANNUAL` · Measure: `FLOW`

**What it is** (by region):

- **US:** General-government current expenditure in this function from BEA NIPA Table 3.16 (US functional classification; not Eurostat COFOG). Published by the Bureau of Economic Analysis (BEA).
- **FR:** General-government expenditure in this COFOG function (Eurostat gov_10a_exp). Published by Eurostat (Statistical Office of the European Union).
- **JP:** General-government expenditure in this COFOG function (ESRI / Cabinet Office functional accounts). Published by the Cabinet Office Economic and Social Research Institute (ESRI).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 65 | BEA | `bea_t31600_education` | B / USD | YTDRelYoY | `Government current expenditures by function (Table 3.16, line 30)` | [BEA](https://www.bea.gov/itable/national-gdp-and-personal-income) | COMPONENT; parent: Annual Government Expenditures |
| FR | 161 | EUROSTAT | `gov_10a_exp_gf09` | M / EUR | YTDRelYoY | `General government expenditure by function (GF09)` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10a_exp/default/table) | COMPONENT; parent: Annual Government Expenditures |
| JP | 252 | JP_CABINET_OFFICE | `esri_cofog_gf09` | B / JPY | YTDRelYoY | `General government total outlays by function (GF09)` | [ESRI](https://www.esri.cao.go.jp/en/sna/kakuhou/kakuhou_top.html) | MONTHLY_UPDATE; COMPONENT; parent: Annual Government Expenditures |

### General Public Service

Frequency: `ANNUAL` · Measure: `FLOW` · Agenda `technical_name`: `Government current expenditures by function (Table 3.16, line 2)`

**What it is.** General-government current expenditure in this function from BEA NIPA Table 3.16 (US functional classification; not Eurostat COFOG). Published by the Bureau of Economic Analysis (BEA).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 66 | BEA | `bea_t31600_general_public_service` | B / USD | YTDRelYoY | [BEA](https://www.bea.gov/itable/national-gdp-and-personal-income) | COMPONENT; parent: Annual Government Expenditures |

### Government Expenditure

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** Total general-government spending.

**By region** (where the bubble differs):

- **US:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Bureau of Economic Analysis (BEA).
- **FR:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** The source stores quarterly flows; the displayed figure is their year-to-date sum from Q1 through the latest available quarter in that calendar year (for example '2025 (Q1 - Q3)'), compared with the same Q1…Qn window a year earlier. Published by the Cabinet Office Economic and Social Research Institute (ESRI).
- **DE:** The printed level is the flow for that period (not annualized) and is not seasonally adjusted. Published by Eurostat (Statistical Office of the European Union).
- **ES:** The printed level is the flow for that period (not annualized) and is not seasonally adjusted. Published by Eurostat (Statistical Office of the European Union).
- **IT:** The printed level is the flow for that period (not annualized) and is not seasonally adjusted. Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 67 | FRED | `GEXPND` | B / USD | YTDvsGDP | `Gross Domestic Product` | [FRED](https://fred.stlouisfed.org/series/GEXPND) | COMPONENT; parent: Government Budget Balance |
| FR | 164 | INSEE | `011794805` | M / EUR | YTDvsGDP | `General government expenditure` | [INSEE](https://www.insee.fr/en/statistiques/serie/011794805) | COMPONENT; parent: Government Budget Balance |
| JP | 255 | JP_CABINET_OFFICE | `ggo_expense` | B / JPY | YTDvsGDP | `General Government Operations` | [ESRI](https://www.esri.cao.go.jp/en/sna/sddsplus/sddsplus_top.html) | MONTHLY_UPDATE; COMPONENT; parent: Government Budget Balance |
| DE | 321 | EUROSTAT | `gov_10q_ggnfa_expenditure` | M / EUR | YTDvsGDP | `Quarterly non-financial accounts for general government` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggnfa/default/table) | COMPONENT; parent: Government Budget Balance |
| ES | 372 | EUROSTAT | `gov_10q_ggnfa_expenditure` | M / EUR | YTDvsGDP | `Quarterly non-financial accounts for general government` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggnfa/default/table) | COMPONENT; parent: Government Budget Balance |
| IT | 423 | EUROSTAT | `gov_10q_ggnfa_expenditure` | M / EUR | YTDvsGDP | `Quarterly non-financial accounts for general government` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggnfa/default/table) | COMPONENT; parent: Government Budget Balance |

### Government Interest Expenditure

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** Interest paid by general government on its liabilities.

**By region** (where the bubble differs):

- **US:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Bureau of Economic Analysis (BEA).
- **FR:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** The source stores quarterly flows; the displayed figure is their year-to-date sum from Q1 through the latest available quarter in that calendar year (for example '2025 (Q1 - Q3)'), compared with the same Q1…Qn window a year earlier. Published by the Cabinet Office Economic and Social Research Institute (ESRI).
- **DE:** The printed level is the flow for that period (not annualized) and is not seasonally adjusted. Published by Eurostat (Statistical Office of the European Union).
- **ES:** The printed level is the flow for that period (not annualized) and is not seasonally adjusted. Published by Eurostat (Statistical Office of the European Union).
- **IT:** The printed level is the flow for that period (not annualized) and is not seasonally adjusted. Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 68 | FRED | `A180RC1Q027SBEA` | B / USD | YTDvsGDP | `Gross Domestic Product` | [FRED](https://fred.stlouisfed.org/series/A180RC1Q027SBEA) | COMPONENT; parent: Government Budget Balance |
| FR | 165 | INSEE | `011794584` | M / EUR | YTDvsGDP | `General government interest paid` | [INSEE](https://www.insee.fr/en/statistiques/serie/011794584) | COMPONENT; parent: Government Expenditure |
| JP | 256 | JP_CABINET_OFFICE | `ggo_interest` | B / JPY | YTDvsGDP | `General Government Operations` | [ESRI](https://www.esri.cao.go.jp/en/sna/sddsplus/sddsplus_top.html) | MONTHLY_UPDATE; COMPONENT; parent: Government Budget Balance |
| DE | 322 | EUROSTAT | `gov_10q_ggnfa_interest_mio` | M / EUR | YTDvsGDP | `Quarterly non-financial accounts for general government` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggnfa/default/table) | COMPONENT; parent: Government Budget Balance |
| ES | 373 | EUROSTAT | `gov_10q_ggnfa_interest_mio` | M / EUR | YTDvsGDP | `Quarterly non-financial accounts for general government` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggnfa/default/table) | COMPONENT; parent: Government Budget Balance |
| IT | 424 | EUROSTAT | `gov_10q_ggnfa_interest_mio` | M / EUR | YTDvsGDP | `Quarterly non-financial accounts for general government` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggnfa/default/table) | COMPONENT; parent: Government Budget Balance |

### Government Other Revenue

Frequency: `QUARTERLY` · Measure: `DERIVED`

**What it is.** Residual general-government revenue after taxes and social contributions.

**By region** (where the bubble differs):

- **US:** Built from the Bureau of Economic Analysis (BEA) series.
- **FR:** Built from Eurostat (Statistical Office of the European Union) series.
- **JP:** The source stores quarterly flows; the displayed figure is their year-to-date sum from Q1 through the latest available quarter in that calendar year (for example '2025 (Q1 - Q3)'), compared with the same Q1…Qn window a year earlier. Built from the Cabinet Office Economic and Social Research Institute (ESRI) series.

**Own calculation** (by region):

- **US:** Government Current Receipts (GRECPT) − Government Tax Revenue (W054RC1Q027SBEA) − Government Social Contributions (W782RC1Q027SBEA).
- **FR:** Government total revenue TR − tax receipts − social contributions D61REC.
- **JP:** Government Revenue (ggo_revenue) − Government Tax Revenue (ggo_taxes) − Government Social Contributions (ggo_social_contributions).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 69 | FRED | `gg_other_revenue` | B / USD | YTDRelYoY | `Gross Domestic Product` | [FRED](FRED || United States Government Current Receipts; United States Government Tax Revenue; United States Government Social Contributions || https://fred.stlouisfed.org/series/GRECPT) | COMPONENT; parent: Government Revenue |
| FR | 166 | EUROSTAT | `gov_10q_ggnfa_other_revenue_sca` | M / EUR | YTDRelYoY | `Derived TR − taxes − D61REC (SCA)` | [Eurostat](Eurostat || Government total revenue TR; tax receipts; social contributions D61REC || https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggnfa/default/table) | COMPONENT; parent: Government Revenue |
| JP | 257 | JP_CABINET_OFFICE | `ggo_other_revenue` | B / JPY | YTDRelYoY | `General Government Operations` | [ESRI](Japan Cabinet Office || Japan Government Revenue; Japan Government Tax Revenue; Japan Government Social Contributions || https://www.esri.cao.go.jp/en/sna/sddsplus/sddsplus_top.html) | MONTHLY_UPDATE; COMPONENT; parent: Government Revenue |

### Government Revenue

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** Total general-government receipts.

**By region** (where the bubble differs):

- **US:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Bureau of Economic Analysis (BEA).
- **FR:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by the National Institute of Statistics and Economic Studies (INSEE).
- **JP:** The source stores quarterly flows; the displayed figure is their year-to-date sum from Q1 through the latest available quarter in that calendar year (for example '2025 (Q1 - Q3)'), compared with the same Q1…Qn window a year earlier. Published by the Cabinet Office Economic and Social Research Institute (ESRI).
- **DE:** The printed level is the flow for that period (not annualized) and is not seasonally adjusted. Published by Eurostat (Statistical Office of the European Union).
- **ES:** The printed level is the flow for that period (not annualized) and is not seasonally adjusted. Published by Eurostat (Statistical Office of the European Union).
- **IT:** The printed level is the flow for that period (not annualized) and is not seasonally adjusted. Published by Eurostat (Statistical Office of the European Union).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 70 | FRED | `GRECPT` | B / USD | YTDvsGDP | `Gross Domestic Product` | [FRED](https://fred.stlouisfed.org/series/GRECPT) | COMPONENT; parent: Government Budget Balance |
| FR | 167 | INSEE | `011794806` | M / EUR | YTDvsGDP | `General government revenue` | [INSEE](https://www.insee.fr/en/statistiques/serie/011794806) | COMPONENT; parent: Government Budget Balance |
| JP | 258 | JP_CABINET_OFFICE | `ggo_revenue` | B / JPY | YTDvsGDP | `General Government Operations` | [ESRI](https://www.esri.cao.go.jp/en/sna/sddsplus/sddsplus_top.html) | MONTHLY_UPDATE; COMPONENT; parent: Government Budget Balance |
| DE | 323 | EUROSTAT | `gov_10q_ggnfa_revenue` | M / EUR | YTDvsGDP | `Quarterly non-financial accounts for general government` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggnfa/default/table) | COMPONENT; parent: Government Budget Balance |
| ES | 374 | EUROSTAT | `gov_10q_ggnfa_revenue` | M / EUR | YTDvsGDP | `Quarterly non-financial accounts for general government` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggnfa/default/table) | COMPONENT; parent: Government Budget Balance |
| IT | 425 | EUROSTAT | `gov_10q_ggnfa_revenue` | M / EUR | YTDvsGDP | `Quarterly non-financial accounts for general government` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggnfa/default/table) | COMPONENT; parent: Government Budget Balance |

### Government Social Contributions

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** Social contributions received by general government.

**By region** (where the bubble differs):

- **US:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Bureau of Economic Analysis (BEA).
- **FR:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **JP:** The source stores quarterly flows; the displayed figure is their year-to-date sum from Q1 through the latest available quarter in that calendar year (for example '2025 (Q1 - Q3)'), compared with the same Q1…Qn window a year earlier. Published by the Cabinet Office Economic and Social Research Institute (ESRI).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 71 | FRED | `W782RC1Q027SBEA` | B / USD | YTDRelYoY | `Gross Domestic Product` | [FRED](https://fred.stlouisfed.org/series/W782RC1Q027SBEA) | COMPONENT; parent: Government Revenue |
| FR | 168 | EUROSTAT | `gov_10q_ggnfa_d61rec_sca` | M / EUR | YTDRelYoY | `General government social contributions received (D.61)` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggnfa/default/table) | COMPONENT; parent: Government Revenue |
| JP | 259 | JP_CABINET_OFFICE | `ggo_social_contributions` | B / JPY | YTDRelYoY | `General Government Operations` | [ESRI](https://www.esri.cao.go.jp/en/sna/sddsplus/sddsplus_top.html) | MONTHLY_UPDATE; COMPONENT; parent: Government Revenue |

### Government Tax Revenue

Frequency: `QUARTERLY`

**What it is.** General-government tax receipts.

**By region** (where the bubble differs):

- **US:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Bureau of Economic Analysis (BEA).
- **FR:** Built from Eurostat (Statistical Office of the European Union) series.
- **JP:** The source stores quarterly flows; the displayed figure is their year-to-date sum from Q1 through the latest available quarter in that calendar year (for example '2025 (Q1 - Q3)'), compared with the same Q1…Qn window a year earlier. Published by the Cabinet Office Economic and Social Research Institute (ESRI).

**Own calculation:** taxes on production and imports (D2REC) + current taxes on income and wealth (D5REC) + capital taxes (D91REC), seasonally adjusted.

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 72 | FRED | `W054RC1Q027SBEA` | B / USD | YTDRelYoY | `Gross Domestic Product` | [FRED](https://fred.stlouisfed.org/series/W054RC1Q027SBEA) | COMPONENT; parent: Government Revenue |
| FR | 169 | EUROSTAT | `gov_10q_ggnfa_taxes_sca` | M / EUR | YTDRelYoY | `Derived D2REC + D5REC + D91REC (SCA)` | [Eurostat](Eurostat || Government tax receipts D2REC+D5REC+D91REC (gov_10q_ggnfa SCA) || https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggnfa/default/table) | COMPONENT; parent: Government Revenue |
| JP | 260 | JP_CABINET_OFFICE | `ggo_taxes` | B / JPY | YTDRelYoY | `General Government Operations` | [ESRI](https://www.esri.cao.go.jp/en/sna/sddsplus/sddsplus_top.html) | MONTHLY_UPDATE; COMPONENT; parent: Government Revenue |

### Health

Frequency: `ANNUAL` · Measure: `FLOW`

**What it is** (by region):

- **US:** General-government current expenditure in this function from BEA NIPA Table 3.16 (US functional classification; not Eurostat COFOG). Published by the Bureau of Economic Analysis (BEA).
- **FR:** General-government expenditure in this COFOG function (Eurostat gov_10a_exp). Published by Eurostat (Statistical Office of the European Union).
- **JP:** General-government expenditure in this COFOG function (ESRI / Cabinet Office functional accounts). Published by the Cabinet Office Economic and Social Research Institute (ESRI).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 73 | BEA | `bea_t31600_health` | B / USD | YTDRelYoY | `Government current expenditures by function (Table 3.16, line 28)` | [BEA](https://www.bea.gov/itable/national-gdp-and-personal-income) | COMPONENT; parent: Annual Government Expenditures |
| FR | 170 | EUROSTAT | `gov_10a_exp_gf07` | M / EUR | YTDRelYoY | `General government expenditure by function (GF07)` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10a_exp/default/table) | COMPONENT; parent: Annual Government Expenditures |
| JP | 261 | JP_CABINET_OFFICE | `esri_cofog_gf07` | B / JPY | YTDRelYoY | `General government total outlays by function (GF07)` | [ESRI](https://www.esri.cao.go.jp/en/sna/kakuhou/kakuhou_top.html) | MONTHLY_UPDATE; COMPONENT; parent: Annual Government Expenditures |

### Housing and Community Services

Frequency: `ANNUAL` · Measure: `FLOW` · Agenda `technical_name`: `Government current expenditures by function (Table 3.16, line 27)`

**What it is.** General-government current expenditure in this function from BEA NIPA Table 3.16 (US functional classification; not Eurostat COFOG). Published by the Bureau of Economic Analysis (BEA).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 74 | BEA | `bea_t31600_housing_community_services` | B / USD | YTDRelYoY | [BEA](https://www.bea.gov/itable/national-gdp-and-personal-income) | COMPONENT; parent: Annual Government Expenditures |

### Income Security

Frequency: `ANNUAL` · Measure: `FLOW` · Agenda `technical_name`: `Government current expenditures by function (Table 3.16, line 36)`

**What it is.** General-government current expenditure in this function from BEA NIPA Table 3.16 (US functional classification; not Eurostat COFOG). Published by the Bureau of Economic Analysis (BEA).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 75 | BEA | `bea_t31600_income_security` | B / USD | YTDRelYoY | [BEA](https://www.bea.gov/itable/national-gdp-and-personal-income) | COMPONENT; parent: Annual Government Expenditures |

### National Defense

Frequency: `ANNUAL` · Measure: `FLOW` · Agenda `technical_name`: `Government current expenditures by function (Table 3.16, line 7)`

**What it is.** General-government current expenditure in this function from BEA NIPA Table 3.16 (US functional classification; not Eurostat COFOG). Published by the Bureau of Economic Analysis (BEA).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 76 | BEA | `bea_t31600_national_defense` | B / USD | YTDRelYoY | [BEA](https://www.bea.gov/itable/national-gdp-and-personal-income) | COMPONENT; parent: Annual Government Expenditures |

### Public Order and Safety

Frequency: `ANNUAL` · Measure: `FLOW`

**What it is** (by region):

- **US:** General-government current expenditure in this function from BEA NIPA Table 3.16 (US functional classification; not Eurostat COFOG). Published by the Bureau of Economic Analysis (BEA).
- **FR:** General-government expenditure in this COFOG function (Eurostat gov_10a_exp). Published by Eurostat (Statistical Office of the European Union).
- **JP:** General-government expenditure in this COFOG function (ESRI / Cabinet Office functional accounts). Published by the Cabinet Office Economic and Social Research Institute (ESRI).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 77 | BEA | `bea_t31600_public_order_safety` | B / USD | YTDRelYoY | `Government current expenditures by function (Table 3.16, line 8)` | [BEA](https://www.bea.gov/itable/national-gdp-and-personal-income) | COMPONENT; parent: Annual Government Expenditures |
| FR | 172 | EUROSTAT | `gov_10a_exp_gf03` | M / EUR | YTDRelYoY | `General government expenditure by function (GF03)` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10a_exp/default/table) | COMPONENT; parent: Annual Government Expenditures |
| JP | 263 | JP_CABINET_OFFICE | `esri_cofog_gf03` | B / JPY | YTDRelYoY | `General government total outlays by function (GF03)` | [ESRI](https://www.esri.cao.go.jp/en/sna/kakuhou/kakuhou_top.html) | MONTHLY_UPDATE; COMPONENT; parent: Annual Government Expenditures |

### Recreation and Culture

Frequency: `ANNUAL` · Measure: `FLOW` · Agenda `technical_name`: `Government current expenditures by function (Table 3.16, line 29)`

**What it is.** General-government current expenditure in this function from BEA NIPA Table 3.16 (US functional classification; not Eurostat COFOG). Published by the Bureau of Economic Analysis (BEA).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| US | 78 | BEA | `bea_t31600_recreation_culture` | B / USD | YTDRelYoY | [BEA](https://www.bea.gov/itable/national-gdp-and-personal-income) | COMPONENT; parent: Annual Government Expenditures |

### Defence

Frequency: `ANNUAL` · Measure: `FLOW`

**What it is** (by region):

- **FR:** General-government expenditure in this COFOG function (Eurostat gov_10a_exp). Published by Eurostat (Statistical Office of the European Union).
- **JP:** General-government expenditure in this COFOG function (ESRI / Cabinet Office functional accounts). Published by the Cabinet Office Economic and Social Research Institute (ESRI).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| FR | 159 | EUROSTAT | `gov_10a_exp_gf02` | M / EUR | YTDRelYoY | `General government expenditure by function (GF02)` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10a_exp/default/table) | COMPONENT; parent: Annual Government Expenditures |
| JP | 250 | JP_CABINET_OFFICE | `esri_cofog_gf02` | B / JPY | YTDRelYoY | `General government total outlays by function (GF02)` | [ESRI](https://www.esri.cao.go.jp/en/sna/kakuhou/kakuhou_top.html) | MONTHLY_UPDATE; COMPONENT; parent: Annual Government Expenditures |

### Environmental Protection

Frequency: `ANNUAL` · Measure: `FLOW`

**What it is** (by region):

- **FR:** General-government expenditure in this COFOG function (Eurostat gov_10a_exp). Published by Eurostat (Statistical Office of the European Union).
- **JP:** General-government expenditure in this COFOG function (ESRI / Cabinet Office functional accounts). Published by the Cabinet Office Economic and Social Research Institute (ESRI).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| FR | 162 | EUROSTAT | `gov_10a_exp_gf05` | M / EUR | YTDRelYoY | `General government expenditure by function (GF05)` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10a_exp/default/table) | COMPONENT; parent: Annual Government Expenditures |
| JP | 253 | JP_CABINET_OFFICE | `esri_cofog_gf05` | B / JPY | YTDRelYoY | `General government total outlays by function (GF05)` | [ESRI](https://www.esri.cao.go.jp/en/sna/kakuhou/kakuhou_top.html) | MONTHLY_UPDATE; COMPONENT; parent: Annual Government Expenditures |

### General Public Services

Frequency: `ANNUAL` · Measure: `FLOW`

**What it is** (by region):

- **FR:** General-government expenditure in this COFOG function (Eurostat gov_10a_exp). Published by Eurostat (Statistical Office of the European Union).
- **JP:** General-government expenditure in this COFOG function (ESRI / Cabinet Office functional accounts). Published by the Cabinet Office Economic and Social Research Institute (ESRI).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| FR | 163 | EUROSTAT | `gov_10a_exp_gf01` | M / EUR | YTDRelYoY | `General government expenditure by function (GF01)` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10a_exp/default/table) | COMPONENT; parent: Annual Government Expenditures |
| JP | 254 | JP_CABINET_OFFICE | `esri_cofog_gf01` | B / JPY | YTDRelYoY | `General government total outlays by function (GF01)` | [ESRI](https://www.esri.cao.go.jp/en/sna/kakuhou/kakuhou_top.html) | MONTHLY_UPDATE; COMPONENT; parent: Annual Government Expenditures |

### Housing and Community Amenities

Frequency: `ANNUAL` · Measure: `FLOW`

**What it is** (by region):

- **FR:** General-government expenditure in this COFOG function (Eurostat gov_10a_exp). Published by Eurostat (Statistical Office of the European Union).
- **JP:** General-government expenditure in this COFOG function (ESRI / Cabinet Office functional accounts). Published by the Cabinet Office Economic and Social Research Institute (ESRI).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| FR | 171 | EUROSTAT | `gov_10a_exp_gf06` | M / EUR | YTDRelYoY | `General government expenditure by function (GF06)` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10a_exp/default/table) | COMPONENT; parent: Annual Government Expenditures |
| JP | 262 | JP_CABINET_OFFICE | `esri_cofog_gf06` | B / JPY | YTDRelYoY | `General government total outlays by function (GF06)` | [ESRI](https://www.esri.cao.go.jp/en/sna/kakuhou/kakuhou_top.html) | MONTHLY_UPDATE; COMPONENT; parent: Annual Government Expenditures |

### Recreation, Culture and Religion

Frequency: `ANNUAL` · Measure: `FLOW`

**What it is** (by region):

- **FR:** General-government expenditure in this COFOG function (Eurostat gov_10a_exp). Published by Eurostat (Statistical Office of the European Union).
- **JP:** General-government expenditure in this COFOG function (ESRI / Cabinet Office functional accounts). Published by the Cabinet Office Economic and Social Research Institute (ESRI).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| FR | 173 | EUROSTAT | `gov_10a_exp_gf08` | M / EUR | YTDRelYoY | `General government expenditure by function (GF08)` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10a_exp/default/table) | COMPONENT; parent: Annual Government Expenditures |
| JP | 264 | JP_CABINET_OFFICE | `esri_cofog_gf08` | B / JPY | YTDRelYoY | `General government total outlays by function (GF08)` | [ESRI](https://www.esri.cao.go.jp/en/sna/kakuhou/kakuhou_top.html) | MONTHLY_UPDATE; COMPONENT; parent: Annual Government Expenditures |

### Social Protection

Frequency: `ANNUAL` · Measure: `FLOW`

**What it is** (by region):

- **FR:** General-government expenditure in this COFOG function (Eurostat gov_10a_exp). Published by Eurostat (Statistical Office of the European Union).
- **JP:** General-government expenditure in this COFOG function (ESRI / Cabinet Office functional accounts). Published by the Cabinet Office Economic and Social Research Institute (ESRI).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| FR | 174 | EUROSTAT | `gov_10a_exp_gf10` | M / EUR | YTDRelYoY | `General government expenditure by function (GF10)` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10a_exp/default/table) | COMPONENT; parent: Annual Government Expenditures |
| JP | 265 | JP_CABINET_OFFICE | `esri_cofog_gf10` | B / JPY | YTDRelYoY | `General government total outlays by function (GF10)` | [ESRI](https://www.esri.cao.go.jp/en/sna/kakuhou/kakuhou_top.html) | MONTHLY_UPDATE; COMPONENT; parent: Annual Government Expenditures |

## Financing

Financial-account identity: Financing Account = Net Liabilities − Net Assets. France adds BdF SC1 gross issuance / redemptions as RELATED detail under F.3; Japan mixes ESRI GGO with BoJ FOF instrument detail.

### Government Financing Account

Frequency: `QUARTERLY` · Measure: `DERIVED`

**What it is.** General-government net liability incurrence minus net acquisition of financial assets on the financial account. This financing identity can differ statistically from the budget / net-lending balance.

**By region** (where the bubble differs):

- **US:** Source legs are seasonally adjusted annual rates; the recap converts each quarter to a period amount (÷4) and shows the year-to-date financing sum from Q1 through the latest available quarter (for example '2025 (Q1 - Q3)'), compared with the same Q1…Qn window a year earlier. Built from the Federal Reserve Board (FRB) series.
- **FR:** Built from Eurostat (Statistical Office of the European Union) series.
- **JP:** The source stores quarterly flows; the displayed figure is their year-to-date sum from Q1 through the latest available quarter in that calendar year (for example '2025 (Q1 - Q3)'), compared with the same Q1…Qn window a year earlier. Built from the Cabinet Office Economic and Social Research Institute (ESRI) series.

**Own calculation** (by region):

- **US:** Net Liabilities (BOGZ1FA374190005Q) − Net Assets (BOGZ1FA374090005Q).
- **FR:** Net Liabilities (gov_10q_ggfa_f_liab_trn) − Net Assets (gov_10q_ggfa_f_ass_trn).
- **JP:** Net Liabilities (ggo_net_incurrence_liabilities) − Net Assets (ggo_net_acquisition_financial_assets).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 79 | FRED | `z1_gg_financing_account` | B / USD | YTDvsGDP | `Z.1 Financial Accounts` | [link](Federal Reserve Z.1 || United States Net Liabilities; United States Net Assets || https://www.federalreserve.gov/releases/z1/) | — |
| FR | 175 | EUROSTAT | `gg_financing_account` | M / EUR | YTDvsGDP | `Derived Net Liabilities − Net Assets` | [Eurostat](Eurostat || France Net Liabilities; France Net Assets || https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggfa/default/table) | — |
| JP | 266 | JP_CABINET_OFFICE | `ggo_financing_account` | B / JPY | YTDvsGDP | `General Government Operations` | [ESRI](Japan Cabinet Office || Japan Net Liabilities; Japan Net Assets || https://www.esri.cao.go.jp/en/sna/sddsplus/sddsplus_top.html) | MONTHLY_UPDATE |

### Acquisition of Financial Assets

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** General-government net acquisition of financial assets (transactions that raise holdings, not a simple purchases total).

**By region** (where the bubble differs):

- **US:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Federal Reserve Board (FRB).
- **FR:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **JP:** The source stores quarterly flows; the displayed figure is their year-to-date sum from Q1 through the latest available quarter in that calendar year (for example '2025 (Q1 - Q3)'), compared with the same Q1…Qn window a year earlier. Published by the Cabinet Office Economic and Social Research Institute (ESRI).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 80 | FRED | `BOGZ1FA374090005Q` | B / USD | YTDvsGDP | `Z.1 Financial Accounts` | [FRED](https://fred.stlouisfed.org/series/BOGZ1FA374090005Q) | COMPONENT; parent: Net Assets |
| FR | 176 | EUROSTAT | `gov_10q_ggfa_f_ass_trn` | M / EUR | YTDvsGDP | `General government total asset transactions (F ASS TRN)` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggfa/default/table) | COMPONENT; parent: Net Assets |
| JP | 267 | JP_CABINET_OFFICE | `ggo_net_acquisition_financial_assets` | B / JPY | YTDvsGDP | `General Government Operations` | [ESRI](https://www.esri.cao.go.jp/en/sna/sddsplus/sddsplus_top.html) | MONTHLY_UPDATE; COMPONENT; parent: Net Assets |

### Net Assets

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** General-government net acquisition of financial assets.

**By region** (where the bubble differs):

- **US:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Federal Reserve Board (FRB).
- **FR:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **JP:** The source stores quarterly flows; the displayed figure is their year-to-date sum from Q1 through the latest available quarter in that calendar year (for example '2025 (Q1 - Q3)'), compared with the same Q1…Qn window a year earlier. Published by the Cabinet Office Economic and Social Research Institute (ESRI).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 81 | FRED | `BOGZ1FA374090005Q` | B / USD | YTDvsGDP | `Z.1 Financial Accounts` | [FRED](https://fred.stlouisfed.org/series/BOGZ1FA374090005Q) | COMPONENT; parent: Government Financing Account |
| FR | 178 | EUROSTAT | `gov_10q_ggfa_f_ass_trn` | M / EUR | YTDvsGDP | `General government total asset transactions (F ASS TRN)` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggfa/default/table) | COMPONENT; parent: Government Financing Account |
| JP | 268 | JP_CABINET_OFFICE | `ggo_net_acquisition_financial_assets` | B / JPY | YTDvsGDP | `General Government Operations` | [ESRI](https://www.esri.cao.go.jp/en/sna/sddsplus/sddsplus_top.html) | MONTHLY_UPDATE; COMPONENT; parent: Government Financing Account |

### Net Debt Securities

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** Net issuance of general-government debt securities.

**By region** (where the bubble differs):

- **US:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Federal Reserve Board (FRB).
- **FR:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **JP:** The source stores quarterly flows; the displayed figure is their year-to-date sum from Q1 through the latest available quarter in that calendar year (for example '2025 (Q1 - Q3)'), compared with the same Q1…Qn window a year earlier. Published by the Bank of Japan (BoJ).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 82 | FRED | `BOGZ1FA374122005Q` | B / USD | YTDvsGDP | `Z.1 Financial Accounts` | [FRED](https://fred.stlouisfed.org/series/BOGZ1FA374122005Q) | COMPONENT; parent: Net Liabilities |
| FR | 179 | EUROSTAT | `gov_10q_ggfa_f3_liab_trn` | M / EUR | YTDvsGDP | `General government debt-security liability transactions (F.3)` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggfa/default/table) | COMPONENT; parent: Net Liabilities |
| JP | 269 | BOJ | `fof_gg_debt_securities` | B / JPY | YTDvsGDP | `Flow of Funds general government` | [BoJ](https://www.stat-search.boj.or.jp/info/dload_en.html) | RELATED; parent: Net Liabilities |

### Net Liabilities

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** General-government net incurrence of financial liabilities.

**By region** (where the bubble differs):

- **US:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Federal Reserve Board (FRB).
- **FR:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **JP:** The source stores quarterly flows; the displayed figure is their year-to-date sum from Q1 through the latest available quarter in that calendar year (for example '2025 (Q1 - Q3)'), compared with the same Q1…Qn window a year earlier. Published by the Cabinet Office Economic and Social Research Institute (ESRI).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 83 | FRED | `BOGZ1FA374190005Q` | B / USD | YTDvsGDP | `Z.1 Financial Accounts` | [FRED](https://fred.stlouisfed.org/series/BOGZ1FA374190005Q) | COMPONENT; parent: Government Financing Account |
| FR | 180 | EUROSTAT | `gov_10q_ggfa_f_liab_trn` | M / EUR | YTDvsGDP | `General government total liability transactions (F LIAB TRN)` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggfa/default/table) | COMPONENT; parent: Government Financing Account |
| JP | 270 | JP_CABINET_OFFICE | `ggo_net_incurrence_liabilities` | B / JPY | YTDvsGDP | `General Government Operations` | [ESRI](https://www.esri.cao.go.jp/en/sna/sddsplus/sddsplus_top.html) | MONTHLY_UPDATE; COMPONENT; parent: Government Financing Account |

### Net Loan Borrowing

Frequency: `QUARTERLY` · Measure: `FLOW`

**What it is.** Net general-government loan liabilities incurred.

**By region** (where the bubble differs):

- **US:** The printed level is a seasonally adjusted annual rate, not the unscaled period total. Published by the Federal Reserve Board (FRB).
- **FR:** The printed level is the seasonally adjusted flow for that period (not annualized). Published by Eurostat (Statistical Office of the European Union).
- **JP:** The source stores quarterly flows; the displayed figure is their year-to-date sum from Q1 through the latest available quarter in that calendar year (for example '2025 (Q1 - Q3)'), compared with the same Q1…Qn window a year earlier. Published by the Bank of Japan (BoJ).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 84 | FRED | `BOGZ1FA374123005Q` | B / USD | YTDvsGDP | `Z.1 Financial Accounts` | [FRED](https://fred.stlouisfed.org/series/BOGZ1FA374123005Q) | COMPONENT; parent: Net Liabilities |
| FR | 181 | EUROSTAT | `gov_10q_ggfa_f4_liab_trn` | M / EUR | YTDvsGDP | `General government loan liability transactions (F.4)` | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggfa/default/table) | COMPONENT; parent: Net Liabilities |
| JP | 271 | BOJ | `fof_gg_loans` | B / JPY | YTDvsGDP | `Flow of Funds general government` | [BoJ](https://www.stat-search.boj.or.jp/info/dload_en.html) | RELATED; parent: Net Liabilities |

### Other Liability Transactions

Frequency: `QUARTERLY` · Measure: `DERIVED`

**What it is.** Residual general-government liability flows outside debt securities and loans.

**By region** (where the bubble differs):

- **US:** Built from the Federal Reserve Board (FRB) series.
- **FR:** Built from Eurostat (Statistical Office of the European Union) series.
- **JP:** The source stores quarterly flows; the displayed figure is their year-to-date sum from Q1 through the latest available quarter in that calendar year (for example '2025 (Q1 - Q3)'), compared with the same Q1…Qn window a year earlier. Built from the Bank of Japan (BoJ) series.

**Own calculation** (by region):

- **US:** Net Liabilities (BOGZ1FA374190005Q) − Net Debt Securities (BOGZ1FA374122005Q) − Net Loan Borrowing (BOGZ1FA374123005Q).
- **FR:** gov_10q_ggfa F LIAB TRN − F3 LIAB TRN − F4 LIAB TRN.
- **JP:** FOF L900−L700 − Net Debt Securities (fof_gg_debt_securities) − Net Loan Borrowing (fof_gg_loans).

| Location | Id | Source | Ticker | Unit | Default mode | Agenda | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| US | 85 | FRED | `z1_gg_other_liability_transactions` | B / USD | YTDvsGDP | `Z.1 Financial Accounts` | [link](Federal Reserve Z.1 || United States Net Liabilities; United States Net Debt Securities; United States Net Loan Borrowing || https://www.federalreserve.gov/releases/z1/) | COMPONENT; parent: Net Liabilities |
| FR | 182 | EUROSTAT | `gov_10q_ggfa_other_liab_trn` | M / EUR | YTDvsGDP | `Derived F − F.3 − F.4 liability transactions` | [Eurostat](Eurostat || gov_10q_ggfa F LIAB TRN; F3 LIAB TRN; F4 LIAB TRN || https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggfa/default/table) | COMPONENT; parent: Net Liabilities |
| JP | 272 | BOJ | `fof_gg_other_liabilities` | B / JPY | YTDvsGDP | `Flow of Funds general government` | [BoJ](Bank of Japan || FOF L900−L700; Japan Net Debt Securities; Japan Net Loan Borrowing || https://www.stat-search.boj.or.jp/info/dload_en.html) | RELATED; parent: Net Liabilities |

### Gross New Borrowing

Frequency: `QUARTERLY` · Measure: `FLOW` · Agenda `technical_name`: `Gross issuance of general-government debt securities`

**What it is.** Gross issuance of general-government debt securities before redemptions. The printed level is the seasonally adjusted flow for that period (not annualized). Published by Banque de France (BdF).

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| FR | 177 | BANQUE_DE_FRANCE | `SC1.Q.FR.1300.F33000.N.8.Z01.E.Z` | M / EUR | YTDvsGDP | [BdF](https://webstat.banque-france.fr/fr/catalogue/sc1/) | MONTHLY_UPDATE; RELATED; parent: Net Debt Securities |

### Principal Repayments

Frequency: `QUARTERLY` · Measure: `DERIVED` · Agenda `technical_name`: `Derived gross − net debt-security issuance`

**What it is.** Redemptions of general-government debt securities (gross issuance minus net issuance). Built from Banque de France (BdF) series.

**Own calculation:** Gross New Borrowing (SC1.Q.FR.1300.F33000.N.8.Z01.E.Z) − BdF SC1 net debt-security issuance.

| Location | Id | Source | Ticker | Unit | Default mode | Series page | Notes |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| FR | 183 | BANQUE_DE_FRANCE | `gg_debt_securities_redemptions` | M / EUR | YTDvsGDP | [BdF](Banque de France || France Gross New Borrowing; BdF SC1 net debt-security issuance || https://webstat.banque-france.fr/fr/catalogue/sc1/) | MONTHLY_UPDATE; RELATED; parent: Net Debt Securities |

---

# Industry profitability (Economic Charts)

Not seeded in `economic_data.json`. Annual ranking panels (`IndustryProfitabilityModel`) for US / FR / JP on the Economic Charts page.

| Location | Classification | Turnover / operating profit | Contribution (GVA) |
| --- | --- | --- | --- |
| FR | NACE Rev. 2 division | Eurostat SBS (`eurostat.py`) | Same SBS GVA |
| US | BEA industry (finest published) | BEA GDPbyIndustry GO + GOS (`bea_industry.py`) | BEA value added |
| JP | MOF corporate industries | MOF e-Stat corporate survey (`mof.py`) | ESRI SNA economic-activity GVA (`jp_cabinet_office.py`) — **different map** |

Units: FR m€, US $bn, JP million yen. Earliest year kept: `INDUSTRY_PROFITABILITY_START_YEAR` (2010). Sources: [`DATA_SOURCES.md`](DATA_SOURCES.md).

---

# Trade rankings (Economic Charts)

Not seeded in `economic_data.json`. Two Macroeconomics panels for US / FR / JP (`TradeTypeChoices`), same storage shape for both:

| Panel | Storage | UI breakdown | Top-N / history |
| --- | --- | --- | --- |
| Merchandise | Top-N `PRODUCT` / `PARTNER` plus `PRODUCT_PARTNER` cells | `PRODUCT` \| `PARTNER` | Top-20 product & partner (5y) |
| Energy | Same row shapes; product universe limited to the energy HS set | `PRODUCT` \| `PARTNER` | Top-10 product & partner (10y) |

Native currencies (EUR / USD / JPY). Value-only rankings (no quantity). Sources: [`DATA_SOURCES.md`](DATA_SOURCES.md).
