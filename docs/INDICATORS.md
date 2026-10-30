# Economic Indicators (France / INSEE)

Catalog of seeded series in [`data_sources/economic_data.json`](../data_sources/economic_data.json). All values are stored as **levels**; period-on-period and year-on-year changes can be derived from history.

Publication schedules are matched on `technical_name` against the English label from the [INSEE agenda](https://www.insee.fr/fr/agenda-diffusion) (`famille.facetteConjoncture.libelleEn`). Data is scraped from BDM CSV ZIPs via `https://bdm.insee.fr/series/{ticker}/csv` (monthly: `valeurs_mensuelles`; quarterly: `valeurs_trimestrielles`, periods as `YYYY-Tn`).

---

## Growth

Quarterly national accounts, chain-linking reference **2020**, CVS-CJO. Volume series are chained previous-year prices stored as **levels in M€** (Base Unit: M); external-balance value series are current prices also in **M€**. Agenda: `Quarterly national accounts - first estimate`.

Methodology: [Quarterly national accounts (EN)](https://www.insee.fr/en/statistiques/fichier/8540868/Comptes_m-EN.pdf).

### GDP and expenditure components (volume)

| Id | Type | Ticker | Base Unit | Series |
| --- | --- | --- | --- | --- |
| 14 | GDP | `011794860` | `M` | [PIB total — volume chaîné](https://www.insee.fr/fr/statistiques/serie/011794860) |
| 15 | Household Consumption | `011794864` | `M` | [Consommation des ménages — volume](https://www.insee.fr/fr/statistiques/serie/011794864) |
| 16 | Government Spending | `011794862` | `M` | [Consommation des APU — volume](https://www.insee.fr/fr/statistiques/serie/011794862) |
| 17 | GFCF | `011794884` | `M` | [FBCF ensemble des secteurs — volume](https://www.insee.fr/fr/statistiques/serie/011794884) |
| 18 | Exports (volume) | `011794877` | `M` | [Exportations — volume](https://www.insee.fr/fr/statistiques/serie/011794877) |
| 19 | Imports (volume) | `011794879` | `M` | [Importations — volume](https://www.insee.fr/fr/statistiques/serie/011794879) |

**What they are.** Expenditure-side GDP stack in volume (goods and services), **absolute chained levels in millions of euros** — not an index. Inventories are not seeded. QoQ / QoQy (annualized QoQ) / YoY can be derived from history.

**Why these series.** Headline GDP plus the main demand components used in growth narratives; volume levels match the catalog preference for levels over growth prints.

---

## Inflation

### HICP (Harmonised Index of Consumer Prices)

| Field | Value |
| --- | --- |
| Id / ticker | `8` / `011812231` |
| Category / frequency | INFLATION / MONTHLY |
| Base Unit / Base Year | `INDEX` / `2025` |
| Series | [HICP – base 2025 – All households – France – COICOP 00 Total](https://www.insee.fr/en/statistiques/serie/011812231) |
| Agenda `technical_name` | `Consumer price index - final results` |

**What it is.** EU-harmonised consumer price index for France (all items), base average 2025 = 100. Designed for cross-country comparison under common methodology and ECOICOP classification.

**Why this series (vs national CPI).** HICP is the internationally comparable inflation measure. The main conceptual difference vs the national CPI is treatment of health costs (HICP uses prices net of social-security reimbursements; national CPI uses gross prices). National CPI all-items (`011814630`) can be added later if needed.

**Methodology:**

- [HICP description](https://www.insee.fr/en/metadonnees/source/indicateur/p1654/description)
- [HICP statistical presentation](https://www.insee.fr/en/metadonnees/source/indicateur/p1654/presentation)
- Related national CPI: [p1653](https://www.insee.fr/en/metadonnees/source/indicateur/p1653)

**Central Banks recap.** The ECB card shows France Inflation Rate as the latest monthly **YoY %** of this index, formatted like `0.9 % (Sep 26)`.

### Euro Area HICP (Harmonised Index of Consumer Prices)

| Field | Value |
| --- | --- |
| Id / ticker | `24` / `prc_hicp_minr` |
| Category / frequency | INFLATION / MONTHLY |
| Location / source | EU / EUROSTAT |
| Base Unit / Base Year | `INDEX` / `2025` |
| Series | Eurostat `prc_hicp_minr` (ECOICOP v2) — geo=`EA`, coicop18=`TOTAL`, unit=`I25`, freq=`M` |
| Agenda `technical_name` | `Inflation (HICP)` |

Publication schedules are matched on `technical_name` against the FullCalendar event `title` from the [Eurostat release calendar](https://ec.europa.eu/eurostat/news/release-calendar/) (`eventsJson`). Prefer the final **Inflation (HICP)** release over **Flash estimate inflation euro area**.

**What it is.** EU-harmonised consumer price index for the euro area (all items), base 2025 = 100. Eurostat retired `prc_hicp_midx` / `I15` (2015=100) after 2025-12; live monthly indices live under `prc_hicp_minr`.

**Central Banks recap.** The ECB card shows Eurozone Inflation Rate as the latest monthly **YoY %** of this index, same `0.9 % (Sep 26)` format as France.

### Industrial raw materials prices

| Field | Value |
| --- | --- |
| Id / ticker | `23` / `010002014` |
| Category / frequency | INFLATION / MONTHLY |
| Base Unit / Base Year | `INDEX` / `2010` |
| Series | [Imported industrial raw materials — euros — base 100 = 2010](https://www.insee.fr/fr/statistiques/serie/010002014) |
| Agenda `technical_name` | `Prices of energy and imported raw materials` |

**What it is.** International price index of **imported industrial raw materials** (produits industriels), expressed in euros, base average 2010 = 100. Published in the monthly IR on energy and imported raw materials.

**Why this series.** Matches the IR “industrial raw materials” euro print. Broader “all imported raw materials ex energy” (`010002010`) and foreign-currency industrial (`010002013`) were not seeded.

Example IR: [June 2026](https://www.insee.fr/en/statistiques/9032806).

---

## Government

### Maastricht debt

| Id | Type | Ticker | Base Unit | Series |
| --- | --- | --- | --- | --- |
| 20 | Government Debt (% of GDP) | `010777608` | `PERCENT` | [Dette Maastricht — % PIB](https://www.insee.fr/fr/statistiques/serie/010777608) |
| 21 | Government Debt (outstanding) | `010777616` | `M` | [Dette Maastricht — encours](https://www.insee.fr/fr/statistiques/serie/010777616) |

| Field | Value |
| --- | --- |
| Category / frequency | GOVERNMENT / QUARTERLY |
| Agenda `technical_name` | `Debt of the general government according to the Maastricht definition` |

**What they are.** Consolidated general-government gross debt (Maastricht / EDP definition), end-quarter: ratio to GDP (**percent**) and outstanding stock (**M€**). Accounts reference year 2020 is not an index base.

**Why these series.** Headline fiscal sustainability ratio plus the euro stock. Methodology: [General government quarterly Maastricht debt](https://www.insee.fr/en/statistiques/documentation/Dette_m_EN.pdf).

### Maastricht deficit / surplus (Eurostat)

| Id | Type | Ticker | Base Unit | Series |
| --- | --- | --- | --- | --- |
| 88 | Government Deficit/Surplus (% of GDP) | `tec00127_pct__FR` | `PERCENT` | [tec00127](https://ec.europa.eu/eurostat/databrowser/view/tec00127/default/table) `PC_GDP` |
| 89 | Government Deficit/Surplus (outstanding) | `tec00127_mio__FR` | `M` | Same table, `MIO_EUR` |

| Field | Value |
| --- | --- |
| Category / frequency | GOVERNMENT / ANNUAL |
| Source | EUROSTAT |
| Agenda `technical_name` | `General government deficit/surplus` |

**What they are.** ESA 2010 / Maastricht net lending (+) / net borrowing (−) of general government (B9): annual **% of GDP** and **million euro**. Negative values are deficits. Same series for DE / ES / IT (ids 90–95). US / JP use national definitions (ids 96–99).

### External trade (national accounts, current prices)

| Id | Type | Ticker | Base Unit | Series |
| --- | --- | --- | --- | --- |
| 22 | Trade Balance | `011794880` | `M` | [Solde extérieur total — valeur](https://www.insee.fr/fr/statistiques/serie/011794880) |

| Field | Value |
| --- | --- |
| Category / frequency | GOVERNMENT / QUARTERLY |
| Agenda `technical_name` | `Quarterly national accounts - first estimate` |

**What it is.** Goods **and** services net external balance at current prices (**M€**), same quarterly accounts family as GDP.

**Why this series.** Complements volume X/M (ids 18–19) with the euro balance markets quote as “trade” in the national-accounts sense. Customs monthly goods CAF/FAB (Douanes) was not seeded.

---

## Production

### Industrial Production

| Field | Value |
| --- | --- |
| Id / ticker | `10` / `010768261` |
| Category / frequency | PRODUCTION / MONTHLY |
| Base Unit / Base Year | `INDEX` / `2021` |
| Series | [SA-WDA IPI – Manufacturing, mining and quarrying and other (A10 BE), base 2021](https://www.insee.fr/en/statistiques/serie/010768261) |
| Agenda `technical_name` | `Industrial production index` |

**What it is.** Seasonally and working-day adjusted industrial production index in volume for NAF A10 item **BE** (industry including mining and energy-related activities beyond pure manufacturing), base average 2021 = 100. Produced under the European Business Statistics (EBS) regulation; used as an early cycle signal and as an input to quarterly accounts.

**Why this series.** Headline industry aggregate (BE), not manufacturing-only (CZ). SA-WDA is the market-relevant read.

**Methodology:**

- [IPI description](https://www.insee.fr/en/metadonnees/source/indicateur/p1646/description)
- [IPI statistical presentation](https://www.insee.fr/en/metadonnees/source/indicateur/p1646/presentation)

---

## Sales

### Retail Sales Volume

| Field | Value |
| --- | --- |
| Id / ticker | `9` / `010769903` |
| Category / frequency | SALES / MONTHLY |
| Base Unit / Base Year | `INDEX` / `2021` |
| Series | [Volume of sales index – Retail trade excl. motor vehicles (NAF 47), SA-WDA, base 2021](https://www.insee.fr/en/statistiques/serie/010769903) |
| Agenda `technical_name` | `Sales volume in wholesale and retail trade` |

**What it is.** Seasonally and working-day adjusted (SA-WDA) **volume** index of retail trade (NACE/NAF division 47), base average 2021 = 100. Volume = turnover deflated by product price indices, from VAT returns.

**Why this series.** Classic “retail sales” scope (excl. motor vehicles). SA-WDA matches the headline Informations Rapides commentary. Broader trade (section G, `010769896`) was not chosen because it mixes wholesale.

**Methodology:**

- [Turnover and sales volume in trade (base 2021) – description](https://www.insee.fr/en/metadonnees/source/indicateur/p1726/description)
- [Methodology](https://www.insee.fr/en/metadonnees/source/indicateur/p1726/documentation-methodologique)

---


---

## Labour

### ILO Unemployment Rate

| Field | Value |
| --- | --- |
| Id / ticker | `11` / `001688527` |
| Category / frequency | LABOUR / QUARTERLY |
| Base Unit | `PERCENT` |
| Series | [ILO unemployment rate – Total – France excluding Mayotte – SA](https://www.insee.fr/en/statistiques/serie/001688527) |
| Agenda `technical_name` | `ILO Unemployment and Labour Market-related indicators (Labour Force Survey results)` |

**What it is.** Seasonally adjusted unemployment **rate** (%) under the International Labour Office (ILO / BIT) definition, from the Labour Force Survey: without work, available within two weeks, and actively seeking work. Geography: France excluding Mayotte (INSEE headline scope).

**Why this series.** Official headline unemployment rate (not France Travail registered jobseekers). Stored as a rate level, not a change.

**Methodology:**

- [Labour market indicators (ILO) – presentation](https://www.insee.fr/en/metadonnees/source/indicateur/p1668/presentation)

### Labour Cost Index

| Field | Value |
| --- | --- |
| Id / ticker | `12` / `010761999` |
| Category / frequency | LABOUR / QUARTERLY |
| Base Unit / Base Year | `INDEX` / `2020` |
| Series | [LCI – hourly costs – NAF sections B to N – base 2020](https://www.insee.fr/fr/statistiques/serie/010761999) |
| Agenda `technical_name` | `Labour cost index (LCI) - Detailed results` |

**What it is.** Seasonally/working-day-aware Laspeyres chain index of **hourly labour cost** (wages + employer social contributions/taxes net of subsidies), covering market non-agricultural sectors B–N, base 2020 = 100. Harmonised for Eurostat comparison. Agenda uses the detailed (not flash) release.

**Why this series.** Full labour cost, not wages-only (`010762015`). Detailed results are preferred over the flash estimate for a stable series.

**Methodology:**

- [LCI presentation](https://www.insee.fr/en/metadonnees/source/indicateur/p1630/presentation)
- [LCI methodology](https://www.insee.fr/fr/metadonnees/source/indicateur/p1630/documentation-methodologique)

---

## Housing

### Second-hand Home Prices

| Field | Value |
| --- | --- |
| Id / ticker | `13` / `010567119` |
| Category / frequency | HOUSING / QUARTERLY |
| Base Unit / Base Year | `INDEX` / `2015` |
| Series | [Notaires-INSEE second-hand dwelling prices – France excl. Mayotte – All dwellings – SA – base 2015](https://www.insee.fr/fr/statistiques/serie/010567119) |
| Agenda `technical_name` | `Indexes of prices of second-hand dwellings` |

**What it is.** Constant-quality hedonic price index for second-hand dwellings (Notaires-INSEE), seasonally adjusted, base average 2015 = 100, France excluding Mayotte. Built from notarial transaction databases.

**Why this series.** Headline home-price print for France (excl. Mayotte), SA, all dwelling types. Prefer over metropolitan-only or raw (non-SA) variants.

**Methodology:**

- [Second-hand dwelling price index – methodology](https://www.insee.fr/fr/metadonnees/source/indicateur/p1643/documentation-methodologique)
- [English note (Notaires-INSEE)](https://www.insee.fr/fr/statistiques/documentation/Fiche_Notaires_Insee_en.pdf)

## Confidence

INSEE business and household tendency surveys are qualitative. Respondents answer in balances of opinion (share “up” minus share “down”). Sector climates and the France-wide composites are standardized to **mean 100, standard deviation 10**: values above 100 mean a more favorable outlook than the long-run average. Seeded confidence series use empty Base Unit (dimensionless climate level, not an index base-year series and not a percent rate).

Methodology overview:

- [Business Tendency Surveys – All Sectors (abbreviated)](https://www.insee.fr/en/statistiques/documentation/climatfrance_m_EN2017.pdf)
- [Composite business climate indicator (definition)](https://www.insee.fr/en/metadonnees/definition/c1514)
- [Méthodologie enquêtes de conjoncture (FR, updated)](https://www.insee.fr/fr/statistiques/documentation/Note_m%C3%A9thodo_IR_France-202607.pdf)

### Aggregate Business Confidence

| Field | Value |
| --- | --- |
| Id / ticker | `1` / `001565530` |
| Category / frequency | CONFIDENCE / MONTHLY |
| Series | [Business climate summary indicator – All sectors – Metropolitan France](https://www.insee.fr/en/statistiques/serie/001565530) |
| Agenda `technical_name` | `Business indicator` |

**What it is.** Single France-wide business-climate summary built with dynamic factor analysis from selected balances across industry, services, retail, wholesale, and construction.

**Why this series.** Headline “business climate” print used as the default aggregate confidence read for France.

### Service / Retail / Manufacturing / Housing Business Confidence

| Id | Type | Ticker | Agenda `technical_name` | Series |
| --- | --- | --- | --- | --- |
| 2 | Service Business Confidence | `001587025` | `Monthly survey of services` | [serie](https://www.insee.fr/en/statistiques/serie/001587025) |
| 3 | Retail Business Confidence | `001580428` | `Monthly survey of retailing` | [serie](https://www.insee.fr/en/statistiques/serie/001580428) |
| 4 | Manufacturing Business Confidence | `001585934` | `Monthly business survey (goods-producing industries)` | [serie](https://www.insee.fr/en/statistiques/serie/001585934) |
| 5 | Housing Business Confidence | `001586890` | `Monthly survey of building` | [serie](https://www.insee.fr/en/statistiques/serie/001586890) |

**What they are.** Sector synthetic climates from the corresponding monthly business tendency surveys (same 100 ± 10 standardization).

**Why these series.** Sector splits explain moves in the aggregate climate and map cleanly to production / sales / construction narratives.

### Consumer Confidence

| Field | Value |
| --- | --- |
| Id / ticker | `6` / `001587668` |
| Category / frequency | CONFIDENCE / MONTHLY |
| Series | [Monthly consumer confidence survey](https://www.insee.fr/en/statistiques/serie/001587668) |
| Agenda `technical_name` | `Monthly consumer confidence survey` |

**What it is.** Household survey synthetic indicator (not the business climate). Same 100 ± 10 scale; summarizes households’ views on the economic situation, personal finances, and spending intentions.

**Why this series.** Complements business confidence with the household side of short-term sentiment.

### Employment Confidence

| Field | Value |
| --- | --- |
| Id / ticker | `7` / `001796629` |
| Category / frequency | CONFIDENCE / MONTHLY |
| Series | [Employment climate summary indicator – All sectors](https://www.insee.fr/en/statistiques/serie/001796629) |
| Agenda `technical_name` | `Business indicator` |

**What it is.** Employment-climate composite from the same family of business surveys (balances on past/expected workforce), standardized like the business climate.

**Why this series.** Soft labour-market signal ahead of hard ILO unemployment prints. Shares the agenda label `Business indicator` with the aggregate business climate (same publication family).

---

# Economic Indicators (United States / FRED)

US series are ingested via the [FRED API](https://fred.stlouisfed.org/docs/api/fred/) (`FRED_API_KEY`). Levels are stored; YoY / MoM can be derived from history. Publication schedules use FRED `release/dates` keyed by `technical_name` → release id via `FRED_RELEASE_ID_BY_TECHNICAL_NAME`.

### Growth (BEA NIPA via FRED)

| Id | Type | Ticker | Freq | Base Unit | Series |
| --- | --- | --- | --- | --- | --- |
| 25 | GDP | `GDPC1` | QUARTERLY | `B` | [Real GDP](https://fred.stlouisfed.org/series/GDPC1) (chained 2017 $, SAAR) |
| 45 | Household Consumption | `PCECC96` | QUARTERLY | `B` | [Real PCE](https://fred.stlouisfed.org/series/PCECC96) |
| 46 | Government Spending | `GCEC1` | QUARTERLY | `B` | [Real gov. consumption & gross investment](https://fred.stlouisfed.org/series/GCEC1) (BEA bundles gov. GFCF here) |
| 47 | Investment | `GPDIC1` | QUARTERLY | `B` | [Real gross private domestic investment](https://fred.stlouisfed.org/series/GPDIC1) |
| 48 | Exports (volume) | `EXPGSC1` | QUARTERLY | `B` | [Real exports of G&S](https://fred.stlouisfed.org/series/EXPGSC1) |
| 49 | Imports (volume) | `IMPGSC1` | QUARTERLY | `B` | [Real imports of G&S](https://fred.stlouisfed.org/series/IMPGSC1) |

Agenda `technical_name` for ids 25 / 45–49: `Gross Domestic Product`.

### Government (debt + deficit + trade)

| Id | Type | Ticker | Freq | Base Unit | Series |
| --- | --- | --- | --- | --- | --- |
| 50 | Trade Balance | `NETEXP` | QUARTERLY | `B` | [Net exports of G&S](https://fred.stlouisfed.org/series/NETEXP) (current $, SAAR) — agenda `Gross Domestic Product` |
| 51 | Government Debt (% of GDP) | `GFDEGDQ188S` | QUARTERLY | `PERCENT` | [Federal debt / GDP](https://fred.stlouisfed.org/series/GFDEGDQ188S) |
| 52 | Government Debt (outstanding) | `GFDEBTN` | QUARTERLY | `M` | [Federal debt total public debt](https://fred.stlouisfed.org/series/GFDEBTN) (millions of $) |
| 96 | Government Deficit/Surplus (% of GDP) | `FYFSDFYGDP` | ANNUAL | `PERCENT` | [Federal surplus or deficit / GDP](https://fred.stlouisfed.org/series/FYFSDFYGDP) (fiscal year; negative = deficit) |
| 97 | Government Deficit/Surplus (outstanding) | `FYFSD` | ANNUAL | `M` | [Federal surplus or deficit](https://fred.stlouisfed.org/series/FYFSD) (millions of $; fiscal year) |

Debt agenda `technical_name`: id 51 → `Debt to Gross Domestic Product Ratios` (FRED release 263); id 52 → `Federal Debt` / Treasury Bulletin (release 80 — FRED often publishes no *future* dates for this release). Deficit agenda: id 96 → `Debt to Gross Domestic Product Ratios` (263); id 97 → `Fiscal Year Budget Data` (81). Federal budget (not general-government Maastricht) definition; observation dates are fiscal-year ends (e.g. `YYYY-09-30`).

### Other US series

| Id | Type | Ticker | Freq | Base Unit | Series |
| --- | --- | --- | --- | --- | --- |
| 26 | Consumer Price Index | `CPIAUCSL` | MONTHLY | `INDEX` / 1982 | [CPI all items SA](https://fred.stlouisfed.org/series/CPIAUCSL) |
| 27 | Retail Sales | `RSAFS` | MONTHLY | `M` | [Retail trade + food services](https://fred.stlouisfed.org/series/RSAFS) |
| 28 | Industrial Production | `INDPRO` | MONTHLY | `INDEX` / 2017 | [IP index SA](https://fred.stlouisfed.org/series/INDPRO) |
| 29 | Unemployment Rate | `UNRATE` | MONTHLY | `PERCENT` | [Unemployment rate SA](https://fred.stlouisfed.org/series/UNRATE) |
| 30 | Nonfarm Payrolls | `PAYEMS` | MONTHLY | `K` | [All employees, total nonfarm](https://fred.stlouisfed.org/series/PAYEMS) |
| 31 | Home Prices | `USSTHPI` | QUARTERLY | `INDEX` / 1980 | [FHFA all-transactions HPI](https://fred.stlouisfed.org/series/USSTHPI) |
| 32 | Consumer Confidence | `UMCSENT` | MONTHLY | _(empty)_ | [U. Michigan Consumer Sentiment](https://fred.stlouisfed.org/series/UMCSENT) |

Upstream agencies (BEA / BLS / Census / FHFA / Treasury / University of Michigan) are reached through FRED rather than scraped directly.

---

# Economic Indicators (Japan / native)

Japan uses native agency feeds (or Statistics of Japan / e-Stat Dashboard that redistributes them). Publication calendars for JP sources are not wired yet.

### Growth — Japan Cabinet Office

Real seasonally adjusted expenditure levels from the latest `gaku-jk*.csv` ([Quarterly Estimates of GDP](https://www.esri.cao.go.jp/en/sna/sokuhou/sokuhou_top.html)), billions of chained 2020 yen (annualized). Tickers select columns in the same CSV.

| Id | Type | Ticker | Column | Series |
| --- | --- | --- | --- | --- |
| 33 | GDP | `gaku-jk` | GDP (expenditure) | Headline real SA GDP |
| 53 | Household Consumption | `gaku-jk-hh` | Consumption of Households | |
| 54 | Government Spending | `gaku-jk-gov` | Government Spending | |
| 55 | Investment | `gaku-jk-gfcf` | Gross Fixed Capital Formation | Total GFCF |
| 56 | Exports (volume) | `gaku-jk-ex` | Exports | Goods & services |
| 57 | Imports (volume) | `gaku-jk-im` | Imports | Goods & services |

All are `QUARTERLY` / `B` with agenda `technical_name` `Quarterly Estimates of GDP`.

### Government — Japan Cabinet Office

| Id | Type | Ticker | Freq | Base Unit | Series |
| --- | --- | --- | --- | --- | --- |
| 58 | Trade Balance | `gaku-jk-nx` | QUARTERLY | `B` | Net Exports column in real SA `gaku-jk` CSV (Exports − Imports) |
| 59 | Government Debt (% of GDP) | `ggd_pct_gdp` | QUARTERLY | `PERCENT` | Total gross debt ÷ annualized nominal SA GDP (`gaku-mk`) × 100 |
| 60 | Government Debt (outstanding) | `ggd_total` | QUARTERLY | `B` | [General Government Gross Debt](https://www.esri.cao.go.jp/en/sna/sddsplus/sddsplus_top.html) Excel `ggd.xlsx`, Total gross debt (billion yen) |
| 98 | Government Deficit/Surplus (% of GDP) | `net_lending_gg_cy_pct_gdp` | ANNUAL | `PERCENT` | SNA table 18 calendar-year sheet `C.Y(2)% of GDP`, General government |
| 99 | Government Deficit/Surplus (outstanding) | `net_lending_gg_cy` | ANNUAL | `B` | SNA table 18 calendar-year sheet `C.Y(1)Amount`, General government (billion yen) |

Trade balance agenda: `Quarterly Estimates of GDP`. Debt outstanding is end-quarter stock; `% of GDP` joins the same quarter to nominal SA GDP (年率). Debt agenda `technical_name`: `General Government Gross Debt`. Deficit/surplus is annual SNA net lending (+) / net borrowing (−) of general government from the [Annual Report on National Accounts](https://www.esri.cao.go.jp/en/sna/kakuhou/kakuhou_top.html) (`*s18_en.xlsx`); negative = deficit. Agenda `technical_name`: `Annual Report on National Accounts`.

### Inflation / Labour / Production / Sales — Statistics of Japan (e-Stat) Dashboard

Underlying agencies: Statistics Bureau (CPI, unemployment), METI (IIP, retail).

| Id | Type | Ticker (IndicatorCode) | Freq | Base Unit | Notes |
| --- | --- | --- | --- | --- | --- |
| 34 | Consumer Price Index | `0703010601010090000` | MONTHLY | `INDEX` / 2025 | CPI all items, original series |
| 35 | Unemployment Rate | `0301010000020020010` | MONTHLY | `PERCENT` | Both sexes, seasonally adjusted |
| 36 | Industrial Production | `0502070301000090010` | MONTHLY | `INDEX` / 2020 | IIP, seasonally adjusted |
| 37 | Retail Sales | `0601010201010010000` | MONTHLY | `B` | Retail sales value (nominal), billion yen |

API: [Statistics Dashboard](https://dashboard.e-stat.go.jp/en/static/api). Add rows to `STAT_OF_JP_DATASET_PARAMS` to wire more IndicatorCodes.

### Housing — MLIT

| Id | Type | Ticker | Freq | Base Unit | Series |
| --- | --- | --- | --- | --- | --- |
| 38 | Home Prices | `residential_property_sa` | MONTHLY | `INDEX` / 2010 | Nationwide SA Residential Property Price Index from [MLIT RPPI page](https://www.mlit.go.jp/totikensangyo/totikensangyo_tk5_000085.html) |

### Confidence — BoJ Tankan

Business Conditions DI (“favorable” − “unfavorable”, % points), current-survey actual, from the latest [Tankan summary ZIP](https://www.boj.or.jp/en/statistics/tk/index.htm).

| Id | Type | Ticker | Size × sector |
| --- | --- | --- | --- |
| 39 | Manufacturing Business Confidence | `business_conditions_large_mfg` | Large × Manufacturing |
| 40 | Manufacturing Business Confidence | `business_conditions_medium_mfg` | Medium × Manufacturing |
| 41 | Manufacturing Business Confidence | `business_conditions_small_mfg` | Small × Manufacturing |
| 42 | Nonmanufacturing Business Confidence | `business_conditions_large_nonmfg` | Large × Nonmanufacturing |
| 43 | Nonmanufacturing Business Confidence | `business_conditions_medium_nonmfg` | Medium × Nonmanufacturing |
| 44 | Nonmanufacturing Business Confidence | `business_conditions_small_nonmfg` | Small × Nonmanufacturing |

All are `QUARTERLY` with empty Base Unit (diffusion index). Point-in-time release: historical ingestion only upserts the latest survey observation (full history would need BOJ Time-Series Data Search).

---

# Economic Indicators (Germany / Spain / Italy — Eurostat)

Charts-only country locations (`DE` / `ES` / `IT`) plotted together under the Economic Charts **Europe** region: each selected type (same defaults as other regions, no confidence) draws Germany, Spain, and Italy as separate series on one chart. Form keys use the `eu_` prefix. Tickers are `{dataset}__{geo}` (e.g. `namq_10_gdp__DE`); filters live in `EUROSTAT_SERIES_TEMPLATES`. Euro-area aggregate HICP (`prc_hicp_minr`, geo=`EA`, seed id 24) remains for Central Banks recap, not these country charts.

Publication schedules match Eurostat calendar `title` on `technical_name` (same as euro-area HICP).

| Type | Dataset template | Freq | Unit / notes |
| --- | --- | --- | --- |
| GDP | `namq_10_gdp` | QUARTERLY | Real GDP `CLV20_MEUR`, SCA (`M`) |
| Consumer Price Index | `prc_hicp_minr` | MONTHLY | HICP `I25` / base 2025 |
| Government Debt (% of GDP) | `gov_10q_ggdebt_pct` → `gov_10q_ggdebt` | QUARTERLY | `PC_GDP` |
| Government Debt (outstanding) | `gov_10q_ggdebt_mio` → `gov_10q_ggdebt` | QUARTERLY | `MIO_EUR` (`M`) |
| Government Deficit/Surplus (% of GDP) | `tec00127_pct` → [`tec00127`](https://ec.europa.eu/eurostat/databrowser/view/tec00127/default/table) | ANNUAL | Maastricht B9, `PC_GDP` (negative = deficit) |
| Government Deficit/Surplus (outstanding) | `tec00127_mio` → `tec00127` | ANNUAL | Maastricht B9, `MIO_EUR` (`M`) |
| Trade Balance | `bop_c6_m` | MONTHLY | Goods BoP balance vs rest of world (`M`) |
| Industrial Production | `sts_inpr_m` | MONTHLY | Volume index `I21` / 2021, SCA |
| Retail Sales | `sts_trtu_m` | MONTHLY | Volume of sales `I21` / 2021, SCA |
| Unemployment Rate | `une_rt_m` | MONTHLY | `%` of active population, SA |
| Home Prices | `prc_hpi_q` | QUARTERLY | House price index `I15_Q` / 2015 |

Seed ids: DE `61–69` + deficit `90–91`, ES `70–78` + `92–93`, IT `79–87` + `94–95`. France also seeds deficit from the same table (`88–89`); debt remains INSEE. US deficit: FRED `96–97`; JP deficit: Cabinet Office SNA table 18 `98–99`.

---
