# Economic Indicators (France / INSEE)

Catalog of seeded series in [`data_sources/economic_data.json`](../data_sources/economic_data.json). All values are stored as **levels** (index or rate); period-on-period and year-on-year changes can be derived from history.

Publication schedules are matched on `technical_name` against the English label from the [INSEE agenda](https://www.insee.fr/fr/agenda-diffusion) (`famille.facetteConjoncture.libelleEn`). Data is scraped from BDM CSV ZIPs via `https://bdm.insee.fr/series/{ticker}/csv` (monthly: `valeurs_mensuelles`; quarterly: `valeurs_trimestrielles`, periods as `YYYY-Tn`).

---

## Growth

Quarterly national accounts, **base 2020**, CVS-CJO. Volume series are chained previous-year prices; external-balance value series are current prices (M€). Agenda: `Quarterly national accounts - first estimate`.

Methodology: [Quarterly national accounts (EN)](https://www.insee.fr/en/statistiques/fichier/8540868/Comptes_m-EN.pdf).

### GDP and expenditure components (volume)

| Id | Type | Ticker | Series |
| --- | --- | --- | --- |
| 14 | GDP | `011794860` | [PIB total — volume chaîné](https://www.insee.fr/fr/statistiques/serie/011794860) |
| 15 | Household Consumption | `011794864` | [Consommation des ménages — volume](https://www.insee.fr/fr/statistiques/serie/011794864) |
| 16 | Government Consumption | `011794862` | [Consommation des APU — volume](https://www.insee.fr/fr/statistiques/serie/011794862) |
| 17 | GFCF | `011794884` | [FBCF ensemble des secteurs — volume](https://www.insee.fr/fr/statistiques/serie/011794884) |
| 18 | Exports (volume) | `011794877` | [Exportations — volume](https://www.insee.fr/fr/statistiques/serie/011794877) |
| 19 | Imports (volume) | `011794879` | [Importations — volume](https://www.insee.fr/fr/statistiques/serie/011794879) |

**What they are.** Expenditure-side GDP stack in volume (goods and services). Inventories are not seeded. QoQ/YoY can be derived from history.

**Why these series.** Headline GDP plus the main demand components used in growth narratives; volume levels match the catalog preference for levels over growth prints.

### External trade (national accounts, current prices)

| Id | Type | Ticker | Series |
| --- | --- | --- | --- |
| 22 | Trade Balance | `011794880` | [Solde extérieur total — valeur](https://www.insee.fr/fr/statistiques/serie/011794880) |

**What it is.** Goods **and** services net external balance at current prices (same quarterly accounts family as GDP).

**Why this series.** Complements volume X/M (ids 18–19) with the euro balance markets quote as “trade” in the national-accounts sense. Customs monthly goods CAF/FAB (Douanes) was not seeded.

---

## Inflation

### HICP (Harmonised Index of Consumer Prices)

| Field | Value |
| --- | --- |
| Id / ticker | `8` / `011812231` |
| Category / frequency | INFLATION / MONTHLY |
| Series | [HICP – base 2025 – All households – France – COICOP 00 Total](https://www.insee.fr/en/statistiques/serie/011812231) |
| Agenda `technical_name` | `Consumer price index - final results` |

**What it is.** EU-harmonised consumer price index for France (all items), base average 2025 = 100. Designed for cross-country comparison under common methodology and ECOICOP classification.

**Why this series (vs national CPI).** HICP is the internationally comparable inflation measure. The main conceptual difference vs the national CPI is treatment of health costs (HICP uses prices net of social-security reimbursements; national CPI uses gross prices). National CPI all-items (`011814630`) can be added later if needed.

**Methodology:**

- [HICP description](https://www.insee.fr/en/metadonnees/source/indicateur/p1654/description)
- [HICP statistical presentation](https://www.insee.fr/en/metadonnees/source/indicateur/p1654/presentation)
- Related national CPI: [p1653](https://www.insee.fr/en/metadonnees/source/indicateur/p1653)

### Industrial raw materials prices

| Field | Value |
| --- | --- |
| Id / ticker | `23` / `010002014` |
| Category / frequency | INFLATION / MONTHLY |
| Series | [Imported industrial raw materials — euros — base 100 = 2010](https://www.insee.fr/fr/statistiques/serie/010002014) |
| Agenda `technical_name` | `Prices of energy and imported raw materials` |

**What it is.** International price index of **imported industrial raw materials** (produits industriels), expressed in euros, base average 2010 = 100. Published in the monthly IR on energy and imported raw materials.

**Why this series.** Matches the IR “industrial raw materials” euro print. Broader “all imported raw materials ex energy” (`010002010`) and foreign-currency industrial (`010002013`) were not seeded.

Example IR: [June 2026](https://www.insee.fr/en/statistiques/9032806).

---

## Government

### Maastricht debt

| Id | Type | Ticker | Series |
| --- | --- | --- | --- |
| 20 | Government Debt (% of GDP) | `010777608` | [Dette Maastricht — % PIB](https://www.insee.fr/fr/statistiques/serie/010777608) |
| 21 | Government Debt (outstanding) | `010777616` | [Dette Maastricht — encours](https://www.insee.fr/fr/statistiques/serie/010777616) |

| Field | Value |
| --- | --- |
| Category / frequency | GOVERNMENT / QUARTERLY |
| Agenda `technical_name` | `Debt of the general government according to the Maastricht definition` |

**What they are.** Consolidated general-government gross debt (Maastricht / EDP definition), end-quarter, base 2020: ratio to GDP (%) and outstanding stock.

**Why these series.** Headline fiscal sustainability ratio plus the euro stock. Methodology: [General government quarterly Maastricht debt](https://www.insee.fr/en/statistiques/documentation/Dette_m_EN.pdf).

---

## Production

### Industrial Production

| Field | Value |
| --- | --- |
| Id / ticker | `10` / `010768261` |
| Category / frequency | PRODUCTION / MONTHLY |
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
| Series | [Notaires-INSEE second-hand dwelling prices – France excl. Mayotte – All dwellings – SA – base 2015](https://www.insee.fr/fr/statistiques/serie/010567119) |
| Agenda `technical_name` | `Indexes of prices of second-hand dwellings` |

**What it is.** Constant-quality hedonic price index for second-hand dwellings (Notaires-INSEE), seasonally adjusted, base average 2015 = 100, France excluding Mayotte. Built from notarial transaction databases.

**Why this series.** Headline home-price print for France (excl. Mayotte), SA, all dwelling types. Prefer over metropolitan-only or raw (non-SA) variants.

**Methodology:**

- [Second-hand dwelling price index – methodology](https://www.insee.fr/fr/metadonnees/source/indicateur/p1643/documentation-methodologique)
- [English note (Notaires-INSEE)](https://www.insee.fr/fr/statistiques/documentation/Fiche_Notaires_Insee_en.pdf)

## Confidence

INSEE business and household tendency surveys are qualitative. Respondents answer in balances of opinion (share “up” minus share “down”). Sector climates and the France-wide composites are standardized to **mean 100, standard deviation 10**: values above 100 mean a more favorable outlook than the long-run average.

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
