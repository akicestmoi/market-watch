"""Static URLs, dataset templates, and ticker maps for economic ingestion / schedules."""

from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple, NotRequired, Required, TypedDict

from economic_overview.models.common import (
    EconomicDataLocationChoices,
    IndicatorBaseCurrencyChoices,
    IndicatorBaseUnitChoices,
)
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.models.industry_profitability import (
    IndustryClassificationChoices,
)
from economic_overview.models.trade_ranking import TradeTypeChoices

# Series labels that offer vsGDP (outstanding / matching-price-basis GDP).
# Former separate '(% of GDP)' twin rows — default_mode is vsGDP in the catalog.
VS_GDP_SERIES_LABELS: frozenset[str] = frozenset(
    {
        "Current Account",
        "Trade Balance",
        "Primary Income Balance",
        "Secondary Income Balance",
        "Government Budget Balance",
        "Government Debt",
        "Government Expenditure",
        "Government Interest Expenditure",
        "Government Revenue",
        "Annual Government Expenditures",
        "Government Financing Account",
        "Net Liabilities",
        "Net Assets",
        "Acquisition of Financial Assets",
        "Net Debt Securities",
        "Gross New Borrowing",
        "Principal Repayments",
        "Net Loan Borrowing",
        "Other Liability Transactions",
    }
)

# Printed levels at current prices (vsGDP / bubble use Nominal GDP).
NOMINAL_PRICE_BASIS_SERIES_LABELS: frozenset[str] = frozenset(
    {
        "Nominal GDP",
        "Current Account",
        "Trade Balance",
        "Primary Income Balance",
        "Secondary Income Balance",
        "Government Budget Balance",
        "Government Debt",
        "Government Expenditure",
        "Government Interest Expenditure",
        "Government Revenue",
        "Annual Government Expenditures",
        "Government Financing Account",
        "Net Liabilities",
        "Net Assets",
        "Acquisition of Financial Assets",
        "Net Debt Securities",
        "Gross New Borrowing",
        "Principal Repayments",
        "Net Loan Borrowing",
        "Other Liability Transactions",
        "Foreign Exchange Reserves",
        "Nominal Disposable Household Income",
        "Nominal Household Consumption",
        "Nominal Household Saving",
        "Nominal Household Debt",
        "Corporate Debt",
        "Net Operating Surplus",
        "Government Budget Balance",
        "Retail Sales",
    }
)

# Printed levels in volume / chain-linked / constant prices (vsGDP / Rel use Real GDP).
REAL_PRICE_BASIS_SERIES_LABELS: frozenset[str] = frozenset(
    {
        "Real GDP",
        "Household Consumption",
        "Government Consumption",
        "Business Investment",
        "Net Exports",
        "Exports",
        "Imports",
        "Real Disposable Household Income",
        "Estimated Annual GDP Growth",
        "Real Retail Sales",
    }
)

# Recap-only derived annual GDP growth (Current = trailing-4Q estimate,
# Previous = sourced national annual growth). Estimate is not scraped.
ANNUAL_GDP_GROWTH_SERIES_LABEL = "Estimated Annual GDP Growth"
ANNUAL_GDP_GROWTH_TICKER = "derived_annual_gdp_growth"
# Hidden annual series feeding Estimated Annual GDP Growth 'Previous'.
REALIZED_ANNUAL_GDP_GROWTH_SERIES_LABEL = "Realized Annual GDP Growth"
# US BEA annual real GDP % change (via FRED); same release as Real GDP.
US_REALIZED_ANNUAL_GDP_GROWTH_TICKER = "A191RL1A225NBEA"
# FR INSEE annual national accounts GDP volume growth.
FR_REALIZED_ANNUAL_GDP_GROWTH_TICKER = "011779995"
# Eurostat annual real GDP % change vs previous year (DE / ES / IT).
EUROSTAT_REALIZED_ANNUAL_GDP_GROWTH_TICKER = "nama_10_gdp_pch"
# Japan: no separate annual scrape — recap derives Previous from Real GDP.
JP_REALIZED_ANNUAL_GDP_GROWTH_TICKER = "derived_jp_calendar_year_gdp_growth"

# Seeded tickers with no upstream scrape (derived in recap / charts only).
# Empty-ticker stubs are skipped separately in data ingestion.
INDICATOR_TICKERS_TO_SKIP_DURING_INGEST: frozenset[str] = frozenset(
    {
        ANNUAL_GDP_GROWTH_TICKER,
        JP_REALIZED_ANNUAL_GDP_GROWTH_TICKER,
    }
)

# Tickers whose stored printed level is an annualized rate (US BEA SAAR, JP CAO
# annualized SA), not the raw period sum. FR / Eurostat GDP stacks are period
# levels and are intentionally absent.
ANNUALIZED_ABS_LEVEL_TICKERS: frozenset[str] = frozenset(
    {
        # United States — FRED / BEA SAAR amounts
        "GDPC1",
        "GDP",
        "PCECC96",
        "GCEC1",
        "GPDIC1",
        "EXPGSC1",
        "IMPGSC1",
        "NETEXP",
        "BOGZ1FA105019005Q",
        # IEABC / IEABCGS / IEABCPI / IEABCSI are BoP period flows (M$, SA),
        # not SAAR — intentionally absent.
        "AD01RC1Q027SBEA",
        "GRECPT",
        "W054RC1Q027SBEA",
        "W782RC1Q027SBEA",
        "gg_other_revenue",
        "GEXPND",
        "A180RC1Q027SBEA",
        # Z.1 S.13 financial-account transactions (SAAR) and their derivations.
        "BOGZ1FA374190005Q",
        "BOGZ1FA374122005Q",
        "BOGZ1FA374123005Q",
        "BOGZ1FA374090005Q",
        "z1_gg_other_liability_transactions",
        "z1_gg_financing_account",
        "W326RC1Q027SBEA",
        "DPI",
        "DPIC96",
        "PCE",
        "PMSAVE",
        # Japan — Cabinet Office annualized SA amounts
        "gaku-jk",
        "gaku-jk-hh",
        "gaku-jk-gov",
        "gaku-jk-gfcf",
        "gaku-jk-ex",
        "gaku-jk-im",
        "gaku-jk-nx",
        "gaku-mk",
        "kakei_nominal_di",
        "kakei_nominal_saving",
        "kakei_nominal_consumption",
        "kakei_real_di",
    }
)

# ---------------------------------------------------------------------------
# INSEE
# ---------------------------------------------------------------------------
"""INSEE BDM series CSV download: frequency → ZIP member basename and URL template."""

INSEE_SERIES_CSV_URL_TEMPLATE = "https://bdm.insee.fr/series/{ticker}/csv"
# INSEE publication schedule (agenda-diffusion) search endpoint.
INSEE_PUBLICATION_SCHEDULE_URL = "https://www.insee.fr/fr/agenda-diffusion"
# ZIP member basename (no '.csv') for the values file inside each BDM series ZIP.
INSEE_CSV_NAME_BY_FREQUENCY: dict[EconomicPublicationFrequencyChoices, str] = {
    EconomicPublicationFrequencyChoices.MONTHLY: "valeurs_mensuelles",
    EconomicPublicationFrequencyChoices.QUARTERLY: "valeurs_trimestrielles",
    EconomicPublicationFrequencyChoices.ANNUAL: "valeurs_annuelles",
}


# ---------------------------------------------------------------------------
# Eurostat
# ---------------------------------------------------------------------------
"""Eurostat Statistics API values, series templates, and publication calendar.

Configured series IDs match 'economic_data.json' tickers (e.g. 'namq_10_gdp').
Geo comes from the indicator 'location' (same codes as Eurostat), except our 'EU'
location uses Eurostat geo 'EA21' ('EUROSTAT_GEO_FOR_EU_LOCATION', overridable
per template via 'eu_geo' / 'eu_params'). 'dataset' is the Statistics API path
segment (may differ from 'series_id' for unit variants).
"""

# Corporate Gross Fixed Capital Formation (BUSINESS): S.11 + S.12 GFCF from nasq_10_nf_tr.
EUROSTAT_CORPORATE_GFCF_TICKER = "nasq_10_nf_tr_gfcf_corp"
EUROSTAT_CORPORATE_GFCF_SECTOR_TICKERS = (
    "nasq_10_nf_tr_gfcf_s11",
    "nasq_10_nf_tr_gfcf_s12",
)
# Net operating surplus (S.11 / B2N): Eurostat does not publish quarterly B2N for
# S.11, so we store B2A3G − P51C (NSA). For S.11, B3G is zero so B2A3G ≈ B2G and
# B2A3G − P51C ≈ B2N.
EUROSTAT_NET_OPERATING_SURPLUS_TICKER = "nasq_10_nf_tr_nos"
EUROSTAT_NET_OPERATING_SURPLUS_GROSS_TICKER = "nasq_10_nf_tr_b2a3g_nsa"
EUROSTAT_NET_OPERATING_SURPLUS_CFC_TICKER = "nasq_10_nf_tr_p51c_nsa"
# Real GDP Net Exports: chain-linked exports (P6) minus imports (P7). BoP
# 'bop_c6_q_gs' stays on Trade Balance under Current Account (nominal).
EUROSTAT_NET_EXPORTS_TICKER = "namq_10_gdp_nx"
EUROSTAT_NET_EXPORTS_EXPORT_TICKER = "namq_10_gdp_ex"
EUROSTAT_NET_EXPORTS_IMPORT_TICKER = "namq_10_gdp_im"
# General-government revenue SCA building blocks (gov_10q_ggnfa).
EUROSTAT_GG_TAX_REVENUE_TICKER = "gov_10q_ggnfa_taxes_sca"
EUROSTAT_GG_TAX_REVENUE_COMPONENT_TICKERS = [
    "gov_10q_ggnfa_d2rec_sca",
    "gov_10q_ggnfa_d5rec_sca",
    "gov_10q_ggnfa_d91rec_sca",
]
EUROSTAT_GG_SOCIAL_CONTRIBUTIONS_TICKER = "gov_10q_ggnfa_d61rec_sca"
EUROSTAT_GG_REVENUE_SCA_TICKER = "gov_10q_ggnfa_revenue_sca"
EUROSTAT_GG_OTHER_REVENUE_TICKER = "gov_10q_ggnfa_other_revenue_sca"
# Financial-account liability residual: F − F.3 − F.4 (LIAB TRN, consolidated).
EUROSTAT_GG_OTHER_LIABILITY_TRANSACTIONS_TICKER = "gov_10q_ggfa_other_liab_trn"
EUROSTAT_GG_TOTAL_LIABILITY_TRANSACTIONS_TICKER = "gov_10q_ggfa_f_liab_trn"
EUROSTAT_GG_DEBT_SECURITY_TRANSACTIONS_TICKER = "gov_10q_ggfa_f3_liab_trn"
EUROSTAT_GG_LOAN_TRANSACTIONS_TICKER = "gov_10q_ggfa_f4_liab_trn"
EUROSTAT_GG_ASSET_TRANSACTIONS_TICKER = "gov_10q_ggfa_f_ass_trn"
# Financing account: Net Liabilities − Net Assets = F LIAB TRN − F ASS TRN.
EUROSTAT_GG_FINANCING_ACCOUNT_TICKER = "gg_financing_account"
# Real household GDHI: current-price B6G deflated by HH+NPISH FCE PD20.
EUROSTAT_NOMINAL_HH_GDHI_TICKER = "nasq_10_nf_tr_b6g"
EUROSTAT_HH_FCE_DEFLATOR_TICKER = "namq_10_gdp_p31_hh_npish_pd"
EUROSTAT_REAL_HH_GDHI_TICKER = "nasq_10_nf_tr_b6g_real"
# Household gross saving (B8G) and saving / adjusted GDHI ratio.
EUROSTAT_NOMINAL_HH_SAVING_TICKER = "nasq_10_nf_tr_b8g"
# D8net — change in pension entitlements (added to B6G for official ratios).
EUROSTAT_HH_PENSION_ADJ_TICKER = "nasq_10_nf_tr_d8"
EUROSTAT_HH_SAVING_RATIO_TICKER = "nasq_10_nf_tr_hh_saving_ratio"
# Household final consumption expenditure (P.31 ≈ ESA P.3 for S14_S15).
EUROSTAT_NOMINAL_HH_CONSUMPTION_TICKER = "nasq_10_nf_tr_p31"
EUROSTAT_HH_CONSUMPTION_RATIO_TICKER = "nasq_10_nf_tr_hh_consumption_ratio"
# Household loan liabilities (F4). EU debt *ratio* uses published ECB QSA.
EUROSTAT_NOMINAL_HH_DEBT_TICKER = "nasq_10_f_bs_f4_liab"
# Inequality (revenue) — Gini (ilc_di12) and Palma from ilc_di01 decile SHARE.
EUROSTAT_GINI_TICKER = "ilc_di12"
EUROSTAT_PALMA_TICKER = "ilc_di01_palma"
EUROSTAT_PALMA_TOP_DECILE_TICKER = "ilc_di01_d10"
EUROSTAT_PALMA_BOTTOM_DECILE_TICKERS = [
    "ilc_di01_d1",
    "ilc_di01_d2",
    "ilc_di01_d3",
    "ilc_di01_d4",
]

# France real RDB: INSEE nominal B6 deflated by household P3 CP/CLV.
INSEE_RDB_NOMINAL_TICKER = "011794746"
INSEE_HH_FCE_CURRENT_PRICE_TICKER = "011794863"
INSEE_HH_FCE_CHAINED_VOLUME_TICKER = "011794864"
INSEE_REAL_RDB_TICKER = "011794746_real"

# US household ratios derived from FRED levels.
FRED_HH_SAVING_AMOUNT_TICKER = "PMSAVE"
FRED_HH_SAVING_INCOME_TICKER = "DSPI"
FRED_HH_SAVING_RATIO_TICKER = "hh_saving_ratio"
# PCECTR is discontinued on FRED; derive PCE / DSPI instead.
FRED_HH_CONSUMPTION_AMOUNT_TICKER = "PCE"
FRED_HH_CONSUMPTION_INCOME_TICKER = "DSPI"
FRED_HH_CONSUMPTION_RATIO_TICKER = "hh_consumption_ratio"
# Loans-only household & NPISH liabilities (aligns with Eurostat F4 / BOJ L200).
FRED_HH_DEBT_AMOUNT_TICKER = "HNOLL"
FRED_HH_DEBT_INCOME_TICKER = "DPI"
FRED_HH_DEBT_RATIO_TICKER = "hh_debt_ratio"
# US general-government revenue drill-down (BEA NIPA via FRED, SAAR billions).
FRED_GOVERNMENT_REVENUE_TICKER = "GRECPT"
FRED_GOVERNMENT_TAX_REVENUE_TICKER = "W054RC1Q027SBEA"
FRED_GOVERNMENT_SOCIAL_CONTRIBUTIONS_TICKER = "W782RC1Q027SBEA"
# Other revenue: GRECPT − current tax receipts − social insurance contributions.
FRED_GOVERNMENT_OTHER_REVENUE_TICKER = "gg_other_revenue"
# Z.1 S.13 consolidated general-government financial-account transactions
# (FRED BOGZ1FA37*, millions SAAR → stored billions SAAR like GRECPT / GDP).
FRED_GOVERNMENT_TOTAL_LIABILITY_TRANSACTIONS_TICKER = "BOGZ1FA374190005Q"
FRED_GOVERNMENT_DEBT_SECURITY_TRANSACTIONS_TICKER = "BOGZ1FA374122005Q"
FRED_GOVERNMENT_LOAN_TRANSACTIONS_TICKER = "BOGZ1FA374123005Q"
FRED_GOVERNMENT_ASSET_TRANSACTIONS_TICKER = "BOGZ1FA374090005Q"
# Derived US financing tickers differ from the Eurostat ones because
# 'ANNUALIZED_ABS_LEVEL_TICKERS' is keyed by ticker and these are SAAR.
FRED_GOVERNMENT_OTHER_LIABILITY_TRANSACTIONS_TICKER = (
    "z1_gg_other_liability_transactions"
)
FRED_GOVERNMENT_FINANCING_ACCOUNT_TICKER = "z1_gg_financing_account"


class _FredGovernmentBreakdownResidual(NamedTuple):
    """Residual after subtracting breakdown components from a total FRED series."""

    total_ticker: str
    component_tickers: list[str]


FRED_GOVERNMENT_BREAKDOWN_RESIDUAL_BY_TICKER: dict[
    str, _FredGovernmentBreakdownResidual
] = {
    FRED_GOVERNMENT_OTHER_REVENUE_TICKER: _FredGovernmentBreakdownResidual(
        total_ticker=FRED_GOVERNMENT_REVENUE_TICKER,
        component_tickers=[
            FRED_GOVERNMENT_TAX_REVENUE_TICKER,
            FRED_GOVERNMENT_SOCIAL_CONTRIBUTIONS_TICKER,
        ],
    ),
    FRED_GOVERNMENT_OTHER_LIABILITY_TRANSACTIONS_TICKER: _FredGovernmentBreakdownResidual(
        total_ticker=FRED_GOVERNMENT_TOTAL_LIABILITY_TRANSACTIONS_TICKER,
        component_tickers=[
            FRED_GOVERNMENT_DEBT_SECURITY_TRANSACTIONS_TICKER,
            FRED_GOVERNMENT_LOAN_TRANSACTIONS_TICKER,
        ],
    ),
    FRED_GOVERNMENT_FINANCING_ACCOUNT_TICKER: _FredGovernmentBreakdownResidual(
        total_ticker=FRED_GOVERNMENT_TOTAL_LIABILITY_TRANSACTIONS_TICKER,
        component_tickers=[FRED_GOVERNMENT_ASSET_TRANSACTIONS_TICKER],
    ),
}
# HNOLL / Z.1 NFC gross fixed investment / Z.1 S.13 transactions are published
# in millions of USD; store in billions like DPI / other US printed amounts.
FRED_NFC_GROSS_FIXED_INVESTMENT_TICKER = "BOGZ1FA105019005Q"
FRED_VALUE_SCALE_BY_TICKER: dict[str, float] = {
    FRED_HH_DEBT_AMOUNT_TICKER: 0.001,
    FRED_NFC_GROSS_FIXED_INVESTMENT_TICKER: 0.001,
    FRED_GOVERNMENT_TOTAL_LIABILITY_TRANSACTIONS_TICKER: 0.001,
    FRED_GOVERNMENT_DEBT_SECURITY_TRANSACTIONS_TICKER: 0.001,
    FRED_GOVERNMENT_LOAN_TRANSACTIONS_TICKER: 0.001,
    FRED_GOVERNMENT_ASSET_TRANSACTIONS_TICKER: 0.001,
}
# Z.1 Table S.11.1.i.q (FRED BOGZ1FU* redistributes FA/FU codes):
# (net operating surplus + CFC) / gross value added × 100.
# NFC capital-share denominator (Z.1 gross value added for S.11).
FRED_NFC_CAPITAL_SHARE_DENOMINATOR_TICKER = "BOGZ1FU106902501Q"  # FA106902501
FRED_NFC_CFC_TICKER = "BOGZ1FU106300003Q"  # FA106300003
FRED_NFC_NOS_TICKER = "BOGZ1FU106402101Q"  # FA106402101
FRED_GROSS_CAPITAL_SHARE_TICKER = "gross_capital_share"
# Z.1 general-government consolidated gross debt ≈ debt securities + loans
# (Maastricht-style instruments; peer of Eurostat gov_10q_ggdebt / INSEE debt).
FRED_GOVERNMENT_DEBT_SECURITIES_TICKER = "BOGZ1FL374122005Q"
FRED_GOVERNMENT_DEBT_LOANS_TICKER = "BOGZ1FL374123005Q"
FRED_GOVERNMENT_DEBT_TICKER = "gg_debt_securities_loans"

# Japan BOJ Flow of Funds — household loans + GG instrument detail.
BOJ_FOF_FLAT_FILE_ZIP_URL = "https://www.stat-search.boj.or.jp/info/fof2_en.zip"
BOJ_FOF_QUARTERLY_CSV_NAME = "ff_dl_fof_quarterly_en.csv"
# Flat-file series id (without FF' prefix) for liabilities / loans / households.
BOJ_HH_LOANS_STOCK_SERIES_ID = "FOF_FFAS430L200"
BOJ_HH_LOANS_STOCK_TICKER = "fof_hh_loans"
# 億円 (100 million yen) → billion yen, to match ESRI kakei DI units.
BOJ_FOF_OKU_YEN_TO_BILLION_YEN = 0.1
BOJ_HH_DEBT_RATIO_TICKER = "hh_debt_ratio"
# ESRI disposable income ticker used as the Japan debt-ratio denominator.
JP_CAO_HH_DEBT_INCOME_TICKER = "kakei_nominal_di"
# General-government (FFAF420) quarterly NSA flows — RELATED instrument detail
# under GGO Net Liabilities (identity itself stays on ESRI GGO).
# 'L900' (liabilities total) includes the 'L700' financial surplus/deficit
# balancing item, so liabilities incurred are L900 − L700.
BOJ_FOF_GG_TOTAL_LIABILITIES_SERIES_ID = "FOF_FFAF420L900"
BOJ_FOF_GG_FINANCIAL_SURPLUS_SERIES_ID = "FOF_FFAF420L700"
# Internal scrape ticker used to derive other liabilities (not seeded).
BOJ_FOF_GG_NET_LIABILITIES_TICKER = "fof_gg_net_liabilities"
BOJ_FOF_GG_DEBT_SECURITIES_TICKER = "fof_gg_debt_securities"
BOJ_FOF_GG_LOANS_TICKER = "fof_gg_loans"
# Other liabilities: (L900 − L700) − L300 − L200.
BOJ_FOF_GG_OTHER_LIABILITIES_TICKER = "fof_gg_other_liabilities"
# Seed ticker → flat-file series id for FOF series read as published.
BOJ_FOF_SERIES_ID_BY_TICKER: dict[str, str] = {
    BOJ_HH_LOANS_STOCK_TICKER: BOJ_HH_LOANS_STOCK_SERIES_ID,
    BOJ_FOF_GG_DEBT_SECURITIES_TICKER: "FOF_FFAF420L300",
    BOJ_FOF_GG_LOANS_TICKER: "FOF_FFAF420L200",
}

# Japan BOJ Time-Series Data Search API (CGPI / SPPI monthly indexes).
BOJ_TIME_SERIES_API_URL = "https://www.stat-search.boj.or.jp/api/v1/getDataCode"
# Monthly CGPI / SPPI history starts well before 2010; request from 2010-01.
BOJ_TIME_SERIES_START_DATE = "201001"
# Tankan judgement DIs go back further; request from 1983-Q1.
BOJ_TANKAN_TIME_SERIES_START_DATE = "198301"


class _BojTimeSeriesSeries(NamedTuple):
    """One BoJ Time-Series getDataCode series (db + code, no CO'/PR0x' prefix)."""

    db: str
    code: str
    frequency: EconomicPublicationFrequencyChoices
    start_date: str


BOJ_TIME_SERIES_BY_TICKER: dict[str, _BojTimeSeriesSeries] = {
    # Corporate Goods Price Index — all commodities (CY2020=100).
    "PRCG20_2200000000": _BojTimeSeriesSeries(
        db="PR01",
        code="PRCG20_2200000000",
        frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        start_date=BOJ_TIME_SERIES_START_DATE,
    ),
    # Services Producer Price Index — all items (CY2020=100).
    "PRCS20_5200000000": _BojTimeSeriesSeries(
        db="PR02",
        code="PRCS20_5200000000",
        frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        start_date=BOJ_TIME_SERIES_START_DATE,
    ),
    # Tankan Business Conditions DI — Manufacturing × size (actual).
    "TK99F1000601GCQ01000": _BojTimeSeriesSeries(
        db="CO",
        code="TK99F1000601GCQ01000",
        frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        start_date=BOJ_TANKAN_TIME_SERIES_START_DATE,
    ),
    "TK99F1000601GCQ02000": _BojTimeSeriesSeries(
        db="CO",
        code="TK99F1000601GCQ02000",
        frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        start_date=BOJ_TANKAN_TIME_SERIES_START_DATE,
    ),
    "TK99F1000601GCQ03000": _BojTimeSeriesSeries(
        db="CO",
        code="TK99F1000601GCQ03000",
        frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        start_date=BOJ_TANKAN_TIME_SERIES_START_DATE,
    ),
    # Tankan Business Conditions DI — Nonmanufacturing × size (actual).
    "TK99F2000601GCQ01000": _BojTimeSeriesSeries(
        db="CO",
        code="TK99F2000601GCQ01000",
        frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        start_date=BOJ_TANKAN_TIME_SERIES_START_DATE,
    ),
    "TK99F2000601GCQ02000": _BojTimeSeriesSeries(
        db="CO",
        code="TK99F2000601GCQ02000",
        frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        start_date=BOJ_TANKAN_TIME_SERIES_START_DATE,
    ),
    "TK99F2000601GCQ03000": _BojTimeSeriesSeries(
        db="CO",
        code="TK99F2000601GCQ03000",
        frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        start_date=BOJ_TANKAN_TIME_SERIES_START_DATE,
    ),
    # Tankan Employment Conditions DI — All industries × size (actual).
    "TK99F0000608GCQ01000": _BojTimeSeriesSeries(
        db="CO",
        code="TK99F0000608GCQ01000",
        frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        start_date=BOJ_TANKAN_TIME_SERIES_START_DATE,
    ),
    "TK99F0000608GCQ02000": _BojTimeSeriesSeries(
        db="CO",
        code="TK99F0000608GCQ02000",
        frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        start_date=BOJ_TANKAN_TIME_SERIES_START_DATE,
    ),
    "TK99F0000608GCQ03000": _BojTimeSeriesSeries(
        db="CO",
        code="TK99F0000608GCQ03000",
        frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        start_date=BOJ_TANKAN_TIME_SERIES_START_DATE,
    ),
}


class EurostatQueryParams(TypedDict, total=False):
    """Eurostat Statistics API query filters for one series (API key names)."""

    freq: Required[str]
    sinceTimePeriod: Required[str]
    unit: str
    geo: str
    coicop18: str
    na_item: str
    s_adj: str
    sector: str
    indic_bt: str
    nace_r2: str
    age: str
    sex: str
    purchase: str
    bop_item: str
    partner: str
    stk_flow: str
    currency: str
    sector10: str
    sectpart: str
    indic: str
    indic_em: str
    direct: str
    finpos: str
    lcstruct: str
    cofog99: str
    sector2: str
    co_nco: str
    quant_inc: str
    statinfo: str


class EurostatQueryParamsOverride(TypedDict, total=False):
    """Partial Eurostat query overrides merged onto a full template 'params'."""

    unit: str
    geo: str
    coicop18: str
    na_item: str
    s_adj: str
    sector: str
    indic_bt: str
    nace_r2: str
    age: str
    sex: str
    purchase: str
    bop_item: str
    partner: str
    stk_flow: str
    currency: str
    sector10: str
    sectpart: str
    indic: str
    indic_em: str
    direct: str
    finpos: str
    lcstruct: str
    cofog99: str
    sector2: str
    co_nco: str
    quant_inc: str
    statinfo: str


class _EurostatApiDefaultParams(TypedDict):
    """Default Eurostat Statistics API query args."""

    format: str
    lang: str


class EurostatTickerParams(TypedDict):
    """Resolved request ready for the Statistics API."""

    dataset: str
    params: EurostatQueryParams


@dataclass(frozen=True)
class _EurostatSeriesTemplate:
    """One Eurostat series keyed by our configured series ID (seed ticker).

    Frozen dataclass: needs '_EurostatSeriesTemplate(...)'.
    Optional 'eu_geo' / 'eu_params' override the shared EU→euro-area mapping when a
    dataset only publishes under a newer EA code or different partner filter.
    """

    series_id: str
    dataset: str
    params: EurostatQueryParams
    eu_geo: str | None = None
    eu_params: EurostatQueryParamsOverride | None = None


EUROSTAT_STATISTICS_API_BASE_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
)
EUROSTAT_API_DEFAULT_PARAMS = _EurostatApiDefaultParams(
    format="JSON",
    lang="en",
)
# Eurostat 'geo' for our 'EU' location (euro area, 21 members from 2026);
# other locations use their code as-is. Per-template 'eu_geo' can override.
EUROSTAT_GEO_FOR_EU_LOCATION = "EA21"

EUROSTAT_SERIES_TEMPLATES: list[_EurostatSeriesTemplate] = [
    # HICP ECOICOP v2 monthly index 2025=100 (EU seed → geo EA; DE/ES/IT use location).
    _EurostatSeriesTemplate(
        series_id="prc_hicp_minr",
        dataset="prc_hicp_minr",
        params=EurostatQueryParams(
            freq="M",
            sinceTimePeriod="2015-01",
            unit="I25",
            coicop18="TOTAL",
        ),
    ),
    # Real GDP, chain-linked volumes 2020, million euro, SCA.
    _EurostatSeriesTemplate(
        series_id="namq_10_gdp",
        dataset="namq_10_gdp",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="CLV20_MEUR",
            na_item="B1GQ",
            s_adj="SCA",
        ),
    ),
    # Annual real GDP growth rate (chain-linked volumes, % change on previous year).
    _EurostatSeriesTemplate(
        series_id="nama_10_gdp_pch",
        dataset="nama_10_gdp",
        params=EurostatQueryParams(
            freq="A",
            sinceTimePeriod="2010",
            unit="CLV_PCH_PRE",
            na_item="B1GQ",
        ),
    ),
    # Nominal GDP, current prices, million euro, SCA (hidden % of GDP denominator).
    _EurostatSeriesTemplate(
        series_id="namq_10_gdp_cp",
        dataset="namq_10_gdp",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="CP_MEUR",
            na_item="B1GQ",
            s_adj="SCA",
        ),
    ),
    # General government consolidated gross debt, million euro (vsGDP in UI).
    _EurostatSeriesTemplate(
        series_id="gov_10q_ggdebt_mio",
        dataset="gov_10q_ggdebt",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="MIO_EUR",
            na_item="GD",
            sector="S13",
        ),
    ),
    # Industrial production volume index (2021=100), SCA.
    _EurostatSeriesTemplate(
        series_id="sts_inpr_m",
        dataset="sts_inpr_m",
        params=EurostatQueryParams(
            freq="M",
            sinceTimePeriod="2015-01",
            unit="I21",
            indic_bt="PRD",
            nace_r2="B-D",
            s_adj="SCA",
        ),
    ),
    # Retail trade volume of sales index (2021=100), SCA.
    _EurostatSeriesTemplate(
        series_id="sts_trtu_m",
        dataset="sts_trtu_m",
        params=EurostatQueryParams(
            freq="M",
            sinceTimePeriod="2015-01",
            unit="I21",
            indic_bt="VOL_SLS",
            nace_r2="G47",
            s_adj="SCA",
        ),
    ),
    # Retail trade net turnover / value index (2021=100), SCA.
    _EurostatSeriesTemplate(
        series_id="sts_trtu_m_nettur",
        dataset="sts_trtu_m",
        params=EurostatQueryParams(
            freq="M",
            sinceTimePeriod="2015-01",
            unit="I21",
            indic_bt="NETTUR",
            nace_r2="G47",
            s_adj="SCA",
        ),
    ),
    # Unemployment rate, % of active population, SA.
    _EurostatSeriesTemplate(
        series_id="une_rt_m",
        dataset="une_rt_m",
        params=EurostatQueryParams(
            freq="M",
            sinceTimePeriod="2015-01",
            unit="PC_ACT",
            s_adj="SA",
            age="TOTAL",
            sex="T",
        ),
    ),
    # Total employment (resident LFS concept), thousand persons, SA.
    _EurostatSeriesTemplate(
        series_id="lfsi_emp_q",
        dataset="lfsi_emp_q",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="THS_PER",
            s_adj="SA",
            sex="T",
            age="Y15-74",
            indic_em="EMP_LFS",
        ),
    ),
    # Existing-dwellings house price index, 2015=100, quarterly.
    _EurostatSeriesTemplate(
        series_id="prc_hpi_q",
        dataset="prc_hpi_q",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="I15_Q",
            purchase="DW_EXST",
        ),
    ),
    # Gross capital share of non-financial corporations (B2G_B3G / B1G × 100).
    _EurostatSeriesTemplate(
        series_id="nasq_10_ki_gross_capital_share",
        dataset="nasq_10_ki",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="PC",
            s_adj="NSA",
            sector="S11",
            na_item="B2G_B3G_RAT_S11",
        ),
    ),
    # Industrial capacity utilisation (%), European Commission BCS.
    _EurostatSeriesTemplate(
        series_id="ei_bsin_q_r2_icu",
        dataset="ei_bsin_q_r2",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            indic="BS-ICU-PC",
            s_adj="SA",
        ),
    ),
    # Current-account balance, % of GDP (annual MIP tip table).
    _EurostatSeriesTemplate(
        series_id="tipsbp20_ca_pct",
        dataset="tipsbp20",
        params=EurostatQueryParams(
            freq="A",
            sinceTimePeriod="2010",
            unit="PC_GDP",
            bop_item="CA",
            partner="WRL_REST",
            stk_flow="BAL",
            sector10="S1",
            sectpart="S1",
            s_adj="NSA",
        ),
        eu_params=EurostatQueryParamsOverride(partner="EXT_EA21"),
    ),
    # GDP components — household consumption (chain-linked volumes).
    _EurostatSeriesTemplate(
        series_id="namq_10_gdp_hh",
        dataset="namq_10_gdp",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="CLV20_MEUR",
            na_item="P31_S14",
            s_adj="SCA",
        ),
    ),
    # GDP components — government consumption.
    _EurostatSeriesTemplate(
        series_id="namq_10_gdp_gov",
        dataset="namq_10_gdp",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="CLV20_MEUR",
            na_item="P3_S13",
            s_adj="SCA",
        ),
    ),
    # GDP components — GFCF (Macro Business Investment; all-economy).
    _EurostatSeriesTemplate(
        series_id="namq_10_gdp_gfcf",
        dataset="namq_10_gdp",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="CLV20_MEUR",
            na_item="P51G",
            s_adj="SCA",
        ),
    ),
    # Corporate GFCF — non-financial corporations (S.11), current prices.
    # Seed ticker 'nasq_10_nf_tr_gfcf_corp' sums this with S.12 (see eurostat scraper).
    _EurostatSeriesTemplate(
        series_id="nasq_10_nf_tr_gfcf_s11",
        dataset="nasq_10_nf_tr",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="CP_MEUR",
            sector="S11",
            na_item="P51G",
            s_adj="NSA",
            direct="PAID",
        ),
    ),
    # Corporate GFCF — financial corporations (S.12), current prices.
    _EurostatSeriesTemplate(
        series_id="nasq_10_nf_tr_gfcf_s12",
        dataset="nasq_10_nf_tr",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="CP_MEUR",
            sector="S12",
            na_item="P51G",
            s_adj="NSA",
            direct="PAID",
        ),
    ),
    # GDP components — exports of goods and services.
    _EurostatSeriesTemplate(
        series_id="namq_10_gdp_ex",
        dataset="namq_10_gdp",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="CLV20_MEUR",
            na_item="P6",
            s_adj="SCA",
        ),
    ),
    # GDP components — imports of goods and services.
    _EurostatSeriesTemplate(
        series_id="namq_10_gdp_im",
        dataset="namq_10_gdp",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="CLV20_MEUR",
            na_item="P7",
            s_adj="SCA",
        ),
    ),
    # Current account balance, million euro (quarterly BoP).
    _EurostatSeriesTemplate(
        series_id="bop_c6_q_ca",
        dataset="bop_c6_q",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            bop_item="CA",
            partner="WRL_REST",
            stk_flow="BAL",
            currency="MIO_EUR",
            sector10="S1",
            sectpart="S1",
        ),
    ),
    # Goods + services trade balance (BoP), million euro — Current Account component.
    _EurostatSeriesTemplate(
        series_id="bop_c6_q_gs",
        dataset="bop_c6_q",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            bop_item="GS",
            partner="WRL_REST",
            stk_flow="BAL",
            currency="MIO_EUR",
            sector10="S1",
            sectpart="S1",
        ),
    ),
    # Primary income balance (BoP), million euro.
    _EurostatSeriesTemplate(
        series_id="bop_c6_q_in1",
        dataset="bop_c6_q",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            bop_item="IN1",
            partner="WRL_REST",
            stk_flow="BAL",
            currency="MIO_EUR",
            sector10="S1",
            sectpart="S1",
        ),
    ),
    # Secondary income balance (BoP), million euro.
    _EurostatSeriesTemplate(
        series_id="bop_c6_q_in2",
        dataset="bop_c6_q",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            bop_item="IN2",
            partner="WRL_REST",
            stk_flow="BAL",
            currency="MIO_EUR",
            sector10="S1",
            sectpart="S1",
        ),
    ),
    # Quarterly general-government non-financial accounts (gov_10q_ggnfa).
    # Internal tickers are aliases into one dataset: sector=S13, unit=MIO_EUR,
    # s_adj=NSA, na_item = B9 / TR / TE / D41PAY (ESA D.41p interest payable).
    _EurostatSeriesTemplate(
        series_id="gov_10q_ggnfa_balance",
        dataset="gov_10q_ggnfa",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="MIO_EUR",
            na_item="B9",
            sector="S13",
            s_adj="NSA",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="gov_10q_ggnfa_revenue",
        dataset="gov_10q_ggnfa",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="MIO_EUR",
            na_item="TR",
            sector="S13",
            s_adj="NSA",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="gov_10q_ggnfa_expenditure",
        dataset="gov_10q_ggnfa",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="MIO_EUR",
            na_item="TE",
            sector="S13",
            s_adj="NSA",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="gov_10q_ggnfa_interest_mio",
        dataset="gov_10q_ggnfa",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="MIO_EUR",
            na_item="D41PAY",
            sector="S13",
            s_adj="NSA",
        ),
    ),
    # Seasonally adjusted revenue building blocks (SCA) for FR tax / social /
    # other drill-down. Taxes = D2REC + D5REC + D91REC; Other = TR − taxes − D61.
    _EurostatSeriesTemplate(
        series_id="gov_10q_ggnfa_revenue_sca",
        dataset="gov_10q_ggnfa",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="MIO_EUR",
            na_item="TR",
            sector="S13",
            s_adj="SCA",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="gov_10q_ggnfa_d2rec_sca",
        dataset="gov_10q_ggnfa",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="MIO_EUR",
            na_item="D2REC",
            sector="S13",
            s_adj="SCA",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="gov_10q_ggnfa_d5rec_sca",
        dataset="gov_10q_ggnfa",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="MIO_EUR",
            na_item="D5REC",
            sector="S13",
            s_adj="SCA",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="gov_10q_ggnfa_d91rec_sca",
        dataset="gov_10q_ggnfa",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="MIO_EUR",
            na_item="D91REC",
            sector="S13",
            s_adj="SCA",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="gov_10q_ggnfa_d61rec_sca",
        dataset="gov_10q_ggnfa",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="MIO_EUR",
            na_item="D61REC",
            sector="S13",
            s_adj="SCA",
        ),
    ),
    # Annual COFOG expenditure by function (Table 3.301 / gov_10a_exp), S.13.
    _EurostatSeriesTemplate(
        series_id="gov_10a_exp_total",
        dataset="gov_10a_exp",
        params=EurostatQueryParams(
            freq="A",
            sinceTimePeriod="2010",
            unit="MIO_EUR",
            na_item="TE",
            sector="S13",
            cofog99="TOTAL",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="gov_10a_exp_gf01",
        dataset="gov_10a_exp",
        params=EurostatQueryParams(
            freq="A",
            sinceTimePeriod="2010",
            unit="MIO_EUR",
            na_item="TE",
            sector="S13",
            cofog99="GF01",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="gov_10a_exp_gf02",
        dataset="gov_10a_exp",
        params=EurostatQueryParams(
            freq="A",
            sinceTimePeriod="2010",
            unit="MIO_EUR",
            na_item="TE",
            sector="S13",
            cofog99="GF02",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="gov_10a_exp_gf03",
        dataset="gov_10a_exp",
        params=EurostatQueryParams(
            freq="A",
            sinceTimePeriod="2010",
            unit="MIO_EUR",
            na_item="TE",
            sector="S13",
            cofog99="GF03",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="gov_10a_exp_gf04",
        dataset="gov_10a_exp",
        params=EurostatQueryParams(
            freq="A",
            sinceTimePeriod="2010",
            unit="MIO_EUR",
            na_item="TE",
            sector="S13",
            cofog99="GF04",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="gov_10a_exp_gf05",
        dataset="gov_10a_exp",
        params=EurostatQueryParams(
            freq="A",
            sinceTimePeriod="2010",
            unit="MIO_EUR",
            na_item="TE",
            sector="S13",
            cofog99="GF05",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="gov_10a_exp_gf06",
        dataset="gov_10a_exp",
        params=EurostatQueryParams(
            freq="A",
            sinceTimePeriod="2010",
            unit="MIO_EUR",
            na_item="TE",
            sector="S13",
            cofog99="GF06",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="gov_10a_exp_gf07",
        dataset="gov_10a_exp",
        params=EurostatQueryParams(
            freq="A",
            sinceTimePeriod="2010",
            unit="MIO_EUR",
            na_item="TE",
            sector="S13",
            cofog99="GF07",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="gov_10a_exp_gf08",
        dataset="gov_10a_exp",
        params=EurostatQueryParams(
            freq="A",
            sinceTimePeriod="2010",
            unit="MIO_EUR",
            na_item="TE",
            sector="S13",
            cofog99="GF08",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="gov_10a_exp_gf09",
        dataset="gov_10a_exp",
        params=EurostatQueryParams(
            freq="A",
            sinceTimePeriod="2010",
            unit="MIO_EUR",
            na_item="TE",
            sector="S13",
            cofog99="GF09",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="gov_10a_exp_gf10",
        dataset="gov_10a_exp",
        params=EurostatQueryParams(
            freq="A",
            sinceTimePeriod="2010",
            unit="MIO_EUR",
            na_item="TE",
            sector="S13",
            cofog99="GF10",
        ),
    ),
    # Quarterly general-government financial accounts (gov_10q_ggfa), consolidated.
    _EurostatSeriesTemplate(
        series_id="gov_10q_ggfa_f_liab_trn",
        dataset="gov_10q_ggfa",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="MIO_EUR",
            na_item="F",
            sector="S13",
            finpos="LIAB",
            stk_flow="TRN",
            sector2="S1_S2",
            co_nco="CO",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="gov_10q_ggfa_f3_liab_trn",
        dataset="gov_10q_ggfa",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="MIO_EUR",
            na_item="F3",
            sector="S13",
            finpos="LIAB",
            stk_flow="TRN",
            sector2="S1_S2",
            co_nco="CO",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="gov_10q_ggfa_f4_liab_trn",
        dataset="gov_10q_ggfa",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="MIO_EUR",
            na_item="F4",
            sector="S13",
            finpos="LIAB",
            stk_flow="TRN",
            sector2="S1_S2",
            co_nco="CO",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="gov_10q_ggfa_f_ass_trn",
        dataset="gov_10q_ggfa",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="MIO_EUR",
            na_item="F",
            sector="S13",
            finpos="ASS",
            stk_flow="TRN",
            sector2="S1_S2",
            co_nco="CO",
        ),
    ),
    # Persons employed (domestic concept), thousands.
    _EurostatSeriesTemplate(
        series_id="namq_10_pe",
        dataset="namq_10_pe",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="THS_PER",
            na_item="EMP_DC",
            s_adj="SCA",
        ),
    ),
    # NFC operating surplus gross (B2A3G≈B2G for S.11) — NSA component of NOS.
    _EurostatSeriesTemplate(
        series_id="nasq_10_nf_tr_b2a3g_nsa",
        dataset="nasq_10_nf_tr",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="CP_MEUR",
            sector="S11",
            na_item="B2A3G",
            s_adj="NSA",
            direct="PAID",
        ),
    ),
    # NFC consumption of fixed capital — NSA component of NOS.
    _EurostatSeriesTemplate(
        series_id="nasq_10_nf_tr_p51c_nsa",
        dataset="nasq_10_nf_tr",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="CP_MEUR",
            sector="S11",
            na_item="P51C",
            s_adj="NSA",
            direct="PAID",
        ),
    ),
    # Household + NPISH gross disposable income (B6G), million euro, SCA.
    _EurostatSeriesTemplate(
        series_id="nasq_10_nf_tr_b6g",
        dataset="nasq_10_nf_tr",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="CP_MEUR",
            sector="S14_S15",
            na_item="B6G",
            s_adj="SCA",
            direct="RECV",
        ),
    ),
    # Household + NPISH gross saving (B8G), million euro, SCA.
    _EurostatSeriesTemplate(
        series_id="nasq_10_nf_tr_b8g",
        dataset="nasq_10_nf_tr",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="CP_MEUR",
            sector="S14_S15",
            na_item="B8G",
            s_adj="SCA",
            direct="RECV",
        ),
    ),
    # HH+NPISH adjustment for change in pension entitlements (D8), million euro.
    _EurostatSeriesTemplate(
        series_id="nasq_10_nf_tr_d8",
        dataset="nasq_10_nf_tr",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="CP_MEUR",
            sector="S14_S15",
            na_item="D8",
            s_adj="SCA",
            direct="RECV",
        ),
    ),
    # HH+NPISH final consumption expenditure (P.31), million euro, SCA.
    _EurostatSeriesTemplate(
        series_id="nasq_10_nf_tr_p31",
        dataset="nasq_10_nf_tr",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="CP_MEUR",
            sector="S14_S15",
            na_item="P31",
            s_adj="SCA",
            direct="PAID",
        ),
    ),
    # Household + NPISH loan liabilities (F4), million euro.
    _EurostatSeriesTemplate(
        series_id="nasq_10_f_bs_f4_liab",
        dataset="nasq_10_f_bs",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="MIO_EUR",
            sector="S14_S15",
            na_item="F4",
            finpos="LIAB",
        ),
    ),
    # HH+NPISH final consumption expenditure implicit deflator (2020=100).
    _EurostatSeriesTemplate(
        series_id="namq_10_gdp_p31_hh_npish_pd",
        dataset="namq_10_gdp",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="PD20_EUR",
            na_item="P31_S14_S15",
            s_adj="SCA",
        ),
    ),
    # Domestic producer prices, industry excl. construction (NACE B-E36), 2021=100.
    _EurostatSeriesTemplate(
        series_id="sts_inppd_m",
        dataset="sts_inppd_m",
        params=EurostatQueryParams(
            freq="M",
            sinceTimePeriod="2015-01",
            unit="I21",
            indic_bt="PRC_PRR_DOM",
            nace_r2="B-E36",
            s_adj="NSA",
        ),
    ),
    # Domestic industrial PPI excl. energy MIG (mining + manufacturing).
    _EurostatSeriesTemplate(
        series_id="sts_inppd_m_x_mig_nrg",
        dataset="sts_inppd_m",
        params=EurostatQueryParams(
            freq="M",
            sinceTimePeriod="2015-01",
            unit="I21",
            indic_bt="PRC_PRR_DOM",
            nace_r2="B_C_X_MIG_NRG",
            s_adj="NSA",
        ),
    ),
    # Labour cost index, wages and salaries.
    _EurostatSeriesTemplate(
        series_id="lc_lci_r2_q",
        dataset="lc_lci_r2_q",
        params=EurostatQueryParams(
            freq="Q",
            sinceTimePeriod="2010-Q1",
            unit="I20",
            nace_r2="B-S",
            s_adj="SCA",
            lcstruct="D11",
        ),
    ),
    # Gini coefficient of equivalised disposable income (0–100), all ages.
    _EurostatSeriesTemplate(
        series_id="ilc_di12",
        dataset="ilc_di12",
        params=EurostatQueryParams(
            freq="A",
            sinceTimePeriod="2010",
            age="TOTAL",
            statinfo="GINI_HND",
        ),
    ),
    # Income decile shares of equivalised disposable income (Palma inputs).
    _EurostatSeriesTemplate(
        series_id="ilc_di01_d1",
        dataset="ilc_di01",
        params=EurostatQueryParams(
            freq="A",
            sinceTimePeriod="2010",
            quant_inc="D1",
            statinfo="SHARE",
            unit="EUR",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="ilc_di01_d2",
        dataset="ilc_di01",
        params=EurostatQueryParams(
            freq="A",
            sinceTimePeriod="2010",
            quant_inc="D2",
            statinfo="SHARE",
            unit="EUR",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="ilc_di01_d3",
        dataset="ilc_di01",
        params=EurostatQueryParams(
            freq="A",
            sinceTimePeriod="2010",
            quant_inc="D3",
            statinfo="SHARE",
            unit="EUR",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="ilc_di01_d4",
        dataset="ilc_di01",
        params=EurostatQueryParams(
            freq="A",
            sinceTimePeriod="2010",
            quant_inc="D4",
            statinfo="SHARE",
            unit="EUR",
        ),
    ),
    _EurostatSeriesTemplate(
        series_id="ilc_di01_d10",
        dataset="ilc_di01",
        params=EurostatQueryParams(
            freq="A",
            sinceTimePeriod="2010",
            quant_inc="D10",
            statinfo="SHARE",
            unit="EUR",
        ),
    ),
]

# Seed tickers whose stored values are not seasonally adjusted. Built from
# Eurostat templates with 's_adj=NSA', plus the combined corporate-GFCF seed
# ticker (S11 + S12). All other infra-annual recap series are treated as SA.
NON_SEASONALLY_ADJUSTED_TICKERS: frozenset[str] = frozenset(
    {
        *(
            template.series_id
            for template in EUROSTAT_SERIES_TEMPLATES
            if template.params.get("s_adj") == "NSA"
        ),
        "nasq_10_nf_tr_gfcf_corp",
        "nasq_10_nf_tr_nos",
        # Core CPI indexes that are not seasonally adjusted.
        "011814035",  # INSEE CPI excl. energy (NSA)
        "0703010601010090040",  # Japan core-core CPI (NSA)
        # BIS credit to NFC via FRED (end-of-quarter stocks / % of GDP).
        "CRDQUSANABIS",
        "CRDQJPANABIS",
        "CRDQFRANABIS",
        "CRDQDEANABIS",
        "CRDQESANABIS",
        "CRDQITANABIS",
        "QUSNAM770A",
        "QFRNAM770A",
        "QDENAM770A",
        "QESNAM770A",
        "QITNAM770A",
        "QJPNAM770A",
        # US manufacturing PPI (industry index is NSA on FRED).
        "PCUOMFGOMFG",
        # US final-demand PPI less energy (NSA on FRED).
        "WPUFD49107",
        # France INSEE industrial PPI excl. energy (French market).
        "010764315",
        # Japan BOJ Corporate Goods / Services Producer Price Indexes.
        "PRCG20_2200000000",
        "PRCS20_5200000000",
    }
)

# Eurostat publication schedule API URL.
EUROSTAT_PUBLICATION_SCHEDULE_URL = (
    "https://ec.europa.eu/eurostat/o/calendars/eventsJson"
)
# FullCalendar feed is range-bounded; ~13 months covers monthly euro-indicators.
EUROSTAT_PUBLICATION_LOOKAHEAD_DAYS = 400

# ---------------------------------------------------------------------------
# FRED (Federal Reserve of St. Louis)
# ---------------------------------------------------------------------------
"""FRED series endpoint and release-dates calendar for publication schedules."""

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_OBSERVATION_START = "2010-01-01"

# FRED release calendar API URL.
FRED_RELEASE_DATES_URL = "https://api.stlouisfed.org/fred/release/dates"
# Seeded indicator 'technical_name' → FRED release id (from 'fred/series/release').
FRED_RELEASE_ID_BY_TECHNICAL_NAME: dict[str, int] = {
    "Gross Domestic Product": 53,
    "Consumer Price Index": 10,
    "Advance Monthly Sales for Retail and Food Services": 9,
    "G.17 Industrial Production and Capacity Utilization": 13,
    "Employment Situation": 50,
    "Employment Situation (CPS)": 50,
    "Current Employment Statistics (CES)": 50,
    "House Price Index": 171,
    "Surveys of Consumers": 91,
    # Former GFDEBTN (Treasury Bulletin / release 80) had few future dates.
    "Z.1 Financial Accounts": 52,
    "Personal Income and Outlays": 54,
    "Personal Saving": 54,
    "PCE Price Index": 54,
    "Household Debt Service Ratios": 89,
    "U.S. International Transactions": 49,
    "BIS Effective Exchange Rate Indices": 319,
    "Credit to Non-Financial Sector": 325,
    "H.8 Assets and Liabilities of Commercial Banks in the United States": 22,
    "G.19 Consumer Credit": 14,
    "Main Economic Indicators": 300,
    "Employment Cost Index": 11,
    "Balance of Payments": 300,
    "International Reserves": 21,
    "Labour Compensation": 300,
    "Capacity Utilization": 13,
    "New Residential Construction": 97,
    "Producer Price Index": 46,
    "Manufacturers New Orders": 9,
    "Household & NPISH loans": 52,
}
# Official US Eastern wall-clock for principal FRED releases (hour, minute).
# Sources: BLS / BEA / Fed Board release conventions. Unmapped ids stay date-only
# at America/New_York midnight (no invented intraday time).
FRED_RELEASE_EASTERN_TIME_BY_RELEASE_ID: dict[int, tuple[int, int]] = {
    9: (8, 30),  # Census retail / durable goods
    10: (8, 30),  # CPI
    11: (8, 30),  # Employment Cost Index
    13: (9, 15),  # G.17 industrial production / capacity
    14: (15, 0),  # G.19 consumer credit
    22: (16, 15),  # H.8 bank balance sheet
    46: (8, 30),  # PPI
    49: (8, 30),  # International transactions
    50: (8, 30),  # Employment Situation
    52: (12, 0),  # Z.1 Financial Accounts
    53: (8, 30),  # GDP
    54: (8, 30),  # Personal Income and Outlays / PCE
    89: (12, 0),  # Household Debt Service
    91: (10, 0),  # University of Michigan Surveys of Consumers
    97: (8, 30),  # New Residential Construction
}

# Seeded 'technical_name' → Eurostat release-calendar event title when they differ.
EUROSTAT_CALENDAR_TITLE_BY_TECHNICAL_NAME: dict[str, str] = {
    "Domestic producer prices": "Industrial producer prices, domestic market",
    "Retail trade turnover": "Retail trade",
    # Country STS volume releases follow the recurring 'Retail trade' slots;
    # the 'volume index overview' title is a one-off that drops off the window.
    "Retail trade volume": "Retail trade",
    "Gross Domestic Product": "GDP main aggregates and employment",
    "Quarterly national accounts": "GDP main aggregates and employment",
    "GDP and main aggregates": "GDP main aggregates and employment",
    "Employment": "GDP main aggregates and employment",
    "Quarterly employment and labour force": "Labour force survey - data",
    "Quarterly non-financial accounts for general government": (
        "Quarterly government deficit"
    ),
    "Quarterly sector accounts": (
        "First release sector accounts (households and businesses)"
    ),
    "Business and consumer surveys": (
        "Economic Sentiment Indicator & Business and Consumer Survey results"
    ),
    "Non-financial corporations": (
        "First release sector accounts (households and businesses)"
    ),
    "Non-financial transactions — corporate GFCF": (
        "First release sector accounts (households and businesses)"
    ),
    "General government total liability transactions (F LIAB TRN)": (
        "Quarterly government deficit"
    ),
    "General government total asset transactions (F ASS TRN)": (
        "Quarterly government deficit"
    ),
    "General government debt-security liability transactions (F.3)": (
        "Quarterly government deficit"
    ),
    "General government loan liability transactions (F.4)": (
        "Quarterly government deficit"
    ),
    "General government social contributions received (D.61)": (
        "Quarterly government deficit"
    ),
    "General government expenditure by function (TOTAL)": (
        "General government deficit and debt"
    ),
    "General government expenditure by function (GF01)": (
        "General government deficit and debt"
    ),
    "General government expenditure by function (GF02)": (
        "General government deficit and debt"
    ),
    "General government expenditure by function (GF03)": (
        "General government deficit and debt"
    ),
    "General government expenditure by function (GF04)": (
        "General government deficit and debt"
    ),
    "General government expenditure by function (GF05)": (
        "General government deficit and debt"
    ),
    "General government expenditure by function (GF06)": (
        "General government deficit and debt"
    ),
    "General government expenditure by function (GF07)": (
        "General government deficit and debt"
    ),
    "General government expenditure by function (GF08)": (
        "General government deficit and debt"
    ),
    "General government expenditure by function (GF09)": (
        "General government deficit and debt"
    ),
    "General government expenditure by function (GF10)": (
        "General government deficit and debt"
    ),
}

# Seeded 'technical_name' → INSEE agenda English label when they differ.
INSEE_CALENDAR_TITLE_BY_TECHNICAL_NAME: dict[str, str] = {
    "Industrial producer price indices": (
        "Industrial Producer and Import Price Indices"
    ),
    # First-estimate slots often drop off the short agenda window; detailed
    # figures share the same national-accounts release family.
    "Quarterly national accounts - first estimate": (
        "Quarterly national accounts - detailed figures"
    ),
    "Comptes nationaux trimestriels": "Quarterly national accounts - detailed figures",
    "Turnover in retail trade": "Sales volume in wholesale and retail trade",
    "General government expenditure": (
        "Debt of the general government according to the Maastricht definition"
    ),
    "General government revenue": (
        "Debt of the general government according to the Maastricht definition"
    ),
    "General government interest paid": (
        "Debt of the general government according to the Maastricht definition"
    ),
    "Net lending (+) or net borrowing (-) of general government": (
        "Debt of the general government according to the Maastricht definition"
    ),
}


# ---------------------------------------------------------------------------
# Statistics of Japan (e-Stat Dashboard)
# ---------------------------------------------------------------------------
"""e-Stat Statistics Dashboard API (no appId). Ticker = 19-digit IndicatorCode."""


class _StatOfJpDefaultParams(TypedDict):
    """Default e-Stat Dashboard getData query args (API key names)."""

    Lang: str
    RegionCode: str
    TimeFrom: str


class _StatOfJpSeriesParams(TypedDict):
    """e-Stat cycle / seasonal-adjustment filters (API key names)."""

    Cycle: str
    IsSeasonalAdjustment: str


class _StatOfJpSeriesConfig(TypedDict):
    """Configured series mapped to an e-Stat IndicatorCode + filters."""

    ticker: str
    name: str
    indicator_code: str
    params: _StatOfJpSeriesParams
    # Multiply scraped levels when the source unit differs from our base_unit
    # (e.g. 10 thousand persons → thousands).
    value_scale: NotRequired[float]


STAT_OF_JP_DATA_URL = "https://dashboard.e-stat.go.jp/api/1.0/Json/getData"
STAT_OF_JP_DEFAULT_PARAMS = _StatOfJpDefaultParams(
    Lang="EN",
    RegionCode="00000",
    TimeFrom="20100100",
)
# FIES Table 3 yearly-income deciles → derived Gini / Palma (total households).
FIES_GINI_TICKER = "fies_gini"
FIES_PALMA_TICKER = "fies_palma"
FIES_TABLE3_FIRST_YEAR = 2011
FIES_TABLE3_XLS_URL_TEMPLATE = (
    "https://www.stat.go.jp/english/data/sousetai/{year}n/zuhyou/s03.xls"
)
FIES_TABLE3_XLSX_URL_TEMPLATE = (
    "https://www.stat.go.jp/english/data/sousetai/{year}n/zuhyou/vs03.xlsx"
)
# US Census ACS / PUMS inequality.
CENSUS_GINI_TICKER = "acs_b19083"
CENSUS_PALMA_TICKER = "acs_pums_palma"
CENSUS_ACS_API_URL_TEMPLATE = "https://api.census.gov/data/{year}/acs/acs1"
CENSUS_ACS_GINI_FIRST_YEAR = 2010
CENSUS_PUMS_HOUSING_ZIP_URL_TEMPLATE = (
    "https://www2.census.gov/programs-surveys/acs/data/pums/"
    "{year}/1-Year/csv_hus.zip"
)
# PUMS housing zips are large; start with recent vintages and extend as needed.
CENSUS_PUMS_PALMA_YEARS = [2022, 2023, 2024]
STAT_OF_JP_SERIES_BY_TICKER: dict[str, _StatOfJpSeriesConfig] = {
    "0703010601010090000": _StatOfJpSeriesConfig(
        ticker="0703010601010090000",
        name="Japan CPI",
        indicator_code="0703010601010090000",
        params=_StatOfJpSeriesParams(Cycle="1", IsSeasonalAdjustment="1"),
    ),
    "0301010000020020010": _StatOfJpSeriesConfig(
        ticker="0301010000020020010",
        name="Japan Unemployment Rate",
        indicator_code="0301010000020020010",
        params=_StatOfJpSeriesParams(Cycle="1", IsSeasonalAdjustment="2"),
    ),
    # Employed persons SA; e-Stat unit is 10 thousand persons → scale to thousands.
    "0301010000010010010": _StatOfJpSeriesConfig(
        ticker="0301010000010010010",
        name="Japan Employment Level",
        indicator_code="0301010000010010010",
        params=_StatOfJpSeriesParams(Cycle="1", IsSeasonalAdjustment="2"),
        value_scale=10.0,
    ),
    "0502070301000090010": _StatOfJpSeriesConfig(
        ticker="0502070301000090010",
        name="Japan Industrial Production",
        indicator_code="0502070301000090010",
        params=_StatOfJpSeriesParams(Cycle="1", IsSeasonalAdjustment="2"),
    ),
    # All items, less fresh food and energy (Japanese core-core), NSA, 2025=100.
    "0703010601010090040": _StatOfJpSeriesConfig(
        ticker="0703010601010090040",
        name="Japan Core CPI (excl. Food & Energy)",
        indicator_code="0703010601010090040",
        params=_StatOfJpSeriesParams(Cycle="1", IsSeasonalAdjustment="1"),
    ),
}


# ---------------------------------------------------------------------------
# University of Michigan — Surveys of Consumers
# ---------------------------------------------------------------------------
"""Michigan SCA data-archive CSV downloads (table number → Relative index)."""

MICHIGAN_SCA_DATA_ARCHIVE_URL = "https://data.sca.isr.umich.edu/data-archive/mine.php"
# Usage of dict: keys are seed tickers; values are SCA table numbers on mine.php.
MICHIGAN_SCA_TABLE_BY_TICKER: dict[str, int] = {
    "sca_table_30": 30,  # Expected Change in Unemployment During the Next Year
}
# FRED release-calendar technical name (release 91) for SCA publication dates.
MICHIGAN_SCA_FRED_TECHNICAL_NAME = "Surveys of Consumers"

# ---------------------------------------------------------------------------
# Japan Cabinet Office (ESRI / SNA)
# ---------------------------------------------------------------------------
"""Cabinet Office quarterly SNA CSVs and SDDS Plus debt / GGO Excel."""

JP_CAO_YEAR_ARCHIVE_URL = (
    "https://www.esri.cao.go.jp/en/sna/data/sokuhou/files/{year}/toukei_{year}.html"
)
JP_CAO_SITE_ORIGIN = "https://www.esri.cao.go.jp"
JP_CAO_SDDS_PLUS_PAGE_URL = (
    "https://www.esri.cao.go.jp/en/sna/sddsplus/sddsplus_top.html"
)
# Filename prefix of the real SA expenditure CSV on the quarterly-estimates menu
# (e.g. 'gaku-jk' matches 'gaku-jk2622.csv'). Columns are 0-based.
JP_CAO_REAL_SA_CSV_FILENAME_PREFIX = "gaku-jk"
JP_CAO_REAL_SA_COLUMN_BY_TICKER: dict[str, int] = {
    "gaku-jk": 1,  # GDP (expenditure approach)
    "gaku-jk-hh": 3,  # Consumption of Households
    "gaku-jk-gov": 8,  # Government Spending
    "gaku-jk-gfcf": 27,  # Gross Fixed Capital Formation
    "gaku-jk-nx": 11,  # Net Exports (goods & services)
    "gaku-jk-ex": 12,  # Exports
    "gaku-jk-im": 13,  # Imports
}

# ---------------------------------------------------------------------------
# BEA — NIPA government expenditures by function
# ---------------------------------------------------------------------------
"""BEA API NIPA Table 3.16 (government current expenditures by function, annual)."""

BEA_API_DATA_URL = "https://apps.bea.gov/api/data/"

# BEA NIPA Table 3.16 — government current expenditures by function (annual).
BEA_NIPA_DATASET = "NIPA"
BEA_GOVERNMENT_EXPENDITURES_BY_FUNCTION_TABLE_NAME = "T31600"
BEA_NIPA_ANNUAL_FREQUENCY = "A"
BEA_NIPA_ANNUAL_YEAR = ",".join(str(year) for year in range(2000, 2031))
# T31600 is published in millions of dollars (UNIT_MULT=6); store billions.
BEA_NIPA_MILLIONS_TO_BILLIONS = 0.001
# Seed ticker → T31600 LineNumber (total government, federal + state and local).
BEA_GOVERNMENT_EXPENDITURES_LINE_BY_TICKER: dict[str, str] = {
    "bea_t31600_total": "1",
    "bea_t31600_general_public_service": "2",
    "bea_t31600_national_defense": "7",
    "bea_t31600_public_order_safety": "8",
    "bea_t31600_economic_affairs": "13",
    "bea_t31600_housing_community_services": "27",
    "bea_t31600_health": "28",
    "bea_t31600_recreation_culture": "29",
    "bea_t31600_education": "30",
    "bea_t31600_income_security": "36",
}

# Filename prefix of the nominal SA GDP CSV on the quarterly-estimates menu
# (annualized levels; Nominal GDP / vsGDP denominator).
JP_CAO_NOMINAL_SA_CSV_FILENAME_PREFIX = "gaku-mk"
# Seed ticker for hidden Nominal GDP (same CSV column 1).
JP_CAO_NOMINAL_GDP_TICKER = "gaku-mk"
JP_CAO_DEBT_OUTSTANDING_TICKER = "ggd_total"
# SDDS Plus General Government Operations (GGO) — quarterly NSA billion yen.
# Non-financial ops (revenue / expense / interest / net lending) lag financial
# transactions; skip 'NA' cells rather than trusting the workbook header span.
JP_CAO_GGO_XLSX_URL = "https://www.esri.cao.go.jp/en/sna/sddsplus/tables/ggo.xlsx"
JP_CAO_GGO_NET_LENDING_TICKER = "ggo_net_lending"
JP_CAO_GGO_REVENUE_TICKER = "ggo_revenue"
JP_CAO_GGO_EXPENSE_TICKER = "ggo_expense"
JP_CAO_GGO_INTEREST_TICKER = "ggo_interest"
JP_CAO_GGO_TAXES_TICKER = "ggo_taxes"
JP_CAO_GGO_SOCIAL_CONTRIBUTIONS_TICKER = "ggo_social_contributions"
# Other revenue: Revenue − Taxes − Social contributions (grants + other revenue).
JP_CAO_GGO_OTHER_REVENUE_TICKER = "ggo_other_revenue"
# Financial account transactions (quarterly NSA, same workbook).
JP_CAO_GGO_NET_ACQUISITION_FINANCIAL_ASSETS_TICKER = (
    "ggo_net_acquisition_financial_assets"
)
JP_CAO_GGO_NET_INCURRENCE_LIABILITIES_TICKER = "ggo_net_incurrence_liabilities"
# Financing account: net incurrence of liabilities − net acquisition of
# financial assets (positive = net borrowing).
JP_CAO_GGO_FINANCING_ACCOUNT_TICKER = "ggo_financing_account"
JP_CAO_GGO_ROW_LABEL_BY_TICKER: dict[str, str] = {
    JP_CAO_GGO_NET_LENDING_TICKER: "Net lending/borrowing",
    JP_CAO_GGO_REVENUE_TICKER: "Revenue",
    JP_CAO_GGO_TAXES_TICKER: "Taxes",
    JP_CAO_GGO_SOCIAL_CONTRIBUTIONS_TICKER: "Social contributions",
    JP_CAO_GGO_EXPENSE_TICKER: "Expenses",
    JP_CAO_GGO_INTEREST_TICKER: "Interest",
    JP_CAO_GGO_NET_ACQUISITION_FINANCIAL_ASSETS_TICKER: (
        "Net acquisition of financial assets"
    ),
    JP_CAO_GGO_NET_INCURRENCE_LIABILITIES_TICKER: "Net incurrence of liabilities",
}
JP_CAO_GGO_TICKERS: frozenset[str] = frozenset(JP_CAO_GGO_ROW_LABEL_BY_TICKER)
# Supporting Table 7 — general-government total outlays by function (COFOG),
# one sheet per fiscal year, billion yen. The annual-estimates folder is named
# after the release year, so the scraper probes recent years newest-first.
JP_CAO_COFOG_XLSX_URL_TEMPLATE = (
    "https://www.esri.cao.go.jp/en/sna/data/kakuhou/files/{year}/tables/"
    "{year}s7_en.xlsx"
)
JP_CAO_COFOG_URL_LOOKBACK_YEARS = 5
# Workbooks are well above this size; HTML error pages served with 200 are not.
JP_CAO_COFOG_MIN_XLSX_BYTES = 10_000
# Row 4 column B holds the fiscal year of each sheet.
JP_CAO_COFOG_FISCAL_YEAR_ROW = 4
JP_CAO_COFOG_FIRST_DATA_ROW = 9
# 0-based outlay columns summed into total outlays: final consumption (B),
# subsidies (E), social benefits (F), other current transfers (G), GFCF (H),
# changes in inventories (I), capital transfers (J). Columns C / D split final
# consumption into individual / collective and are skipped.
JP_CAO_COFOG_OUTLAY_COLUMNS: list[int] = [1, 4, 5, 6, 7, 8, 9]
# Seed ticker → top-level row key ('Total' or the one-digit COFOG code).
JP_CAO_COFOG_ROW_KEY_BY_TICKER: dict[str, str] = {
    "esri_cofog_total": "Total",
    "esri_cofog_gf01": "1",
    "esri_cofog_gf02": "2",
    "esri_cofog_gf03": "3",
    "esri_cofog_gf04": "4",
    "esri_cofog_gf05": "5",
    "esri_cofog_gf06": "6",
    "esri_cofog_gf07": "7",
    "esri_cofog_gf08": "8",
    "esri_cofog_gf09": "9",
    "esri_cofog_gf10": "10",
}
# End-of-quarter month (3/6/9/12) → quarter-start month for debt outstanding dates.
JP_CAO_GGD_QUARTER_START_MONTH_BY_END_MONTH: dict[int, int] = {
    3: 1,
    6: 4,
    9: 7,
    12: 10,
}

# Consumer Confidence Survey SA sheet (shouhi2.xlsx) — headline CCI + Employment.
JP_CAO_SHOUHI_SA_XLSX_URL = "https://www.esri.cao.go.jp/en/stat/shouhi/shouhi2.xlsx"
JP_CAO_CONSUMER_CONFIDENCE_TICKER = "shouhi_cci_sa"
JP_CAO_EMPLOYMENT_CONFIDENCE_TICKER = "shouhi_employment_sa"
# 1-based Excel columns on the seasonally adjusted sheet.
JP_CAO_SHOUHI_CCI_COLUMN = 5
JP_CAO_SHOUHI_EMPLOYMENT_COLUMN = 11
JP_CAO_SHOUHI_COLUMN_BY_TICKER: dict[str, int] = {
    JP_CAO_CONSUMER_CONFIDENCE_TICKER: JP_CAO_SHOUHI_CCI_COLUMN,
    JP_CAO_EMPLOYMENT_CONFIDENCE_TICKER: JP_CAO_SHOUHI_EMPLOYMENT_COLUMN,
}

# Machinery Orders — private excl. ships/power, monthly SA via e-Stat.
JP_CAO_MACHINERY_ORDERS_TICKER = "machinery_orders_private_ex_volatile_sa"
JP_CAO_MACHINERY_ORDERS_STATS_DATA_ID = "0003355222"
JP_CAO_MACHINERY_ORDERS_DEMAND_CODE = "160"  # 民間需要(船舶・電力を除く)
JP_CAO_MACHINERY_ORDERS_SA_SERIES_CODE = "100"  # 季調系列
# e-Stat unit is 100万円 (million yen); stored values are billion yen.
JP_CAO_MACHINERY_ORDERS_MILLION_YEN_PER_BILLION = 1000.0

# Household disposable income / saving quarterly flash (kakei_*.xlsx).
JP_CAO_KAKEI_FILES_PAGE_URL = (
    "https://www.esri.cao.go.jp/jp/sna/data/data_list/kakei/files/files_kakei.html"
)
JP_CAO_KAKEI_FILES_ORIGIN = (
    "https://www.esri.cao.go.jp/jp/sna/data/data_list/kakei/files/"
)
# English fragment that identifies the seasonally adjusted levels sheet.
JP_CAO_KAKEI_SA_SHEET_MARKER = "Seasonally adjusted series"
# 1-based Excel columns on the SA sheet (English header row).
# Saving ratio (%) is published truncated in col N — derive from L / I instead.
JP_CAO_KAKEI_COLUMN_BY_TICKER: dict[str, int] = {
    "kakei_nominal_di": 9,  # I — Nominal disposable income (billion yen, SAAR)
    "kakei_nominal_consumption": 11,  # K — Consumption of households (billion yen, SAAR)
    "kakei_nominal_saving": 12,  # L — Saving (billion yen, SAAR)
    "kakei_real_di": 16,  # P — Real disposable income (chained, billion yen SAAR)
}
JP_CAO_NOMINAL_HH_SAVING_TICKER = "kakei_nominal_saving"
JP_CAO_NOMINAL_HH_CONSUMPTION_TICKER = "kakei_nominal_consumption"
JP_CAO_HH_CONSUMPTION_RATIO_TICKER = "kakei_consumption_ratio"
JP_CAO_HH_SAVING_RATIO_TICKER = "kakei_saving_ratio"
JP_CAO_NOMINAL_HH_DI_TICKER = "kakei_nominal_di"


# ---------------------------------------------------------------------------
# ECB Data Portal (SDMX 2.1)
# ---------------------------------------------------------------------------
"""ECB QSA household debt-to-income and DWA wealth-distribution series."""


class _EcbSeriesConfig(NamedTuple):
    """One ECB SDMX series: dataflow, key template, and optional Q4→annual keep."""

    dataflow: str
    series_key_template: str
    # When true, keep only Q4 observations and store them as calendar-year points.
    keep_q4_as_annual: bool = False


ECB_SDMX_DATA_URL_TEMPLATE = (
    "https://data-api.ecb.europa.eu/service/data/{dataflow}/{series_key}"
)
ECB_QSA_DATAFLOW = "QSA"
ECB_DWA_DATAFLOW = "DWA"
# Our 'EU' location → euro-area fixed composition code used in QSA keys.
ECB_REF_AREA_FOR_EU_LOCATION = "I9"
ECB_DWA_WEALTH_GINI_TICKER = "ecb_dwa_wealth_gini"
ECB_DWA_TOP10_WEALTH_SHARE_TICKER = "ecb_dwa_top10_wealth_share"
# Ticker → SDMX series; '{ref_area}' is filled from indicator location.
ECB_SERIES_BY_TICKER: dict[str, _EcbSeriesConfig] = {
    # Household loans outstanding ÷ gross disposable income (annualised), %.
    "qsa_hh_loans_to_gdi": _EcbSeriesConfig(
        dataflow=ECB_QSA_DATAFLOW,
        series_key_template=(
            "Q.N.{ref_area}.W0.S1M.S1.N.L.LE.F4.T._Z.XDC_R_B6G_CY._T.S.V.N._T"
        ),
    ),
    ECB_DWA_WEALTH_GINI_TICKER: _EcbSeriesConfig(
        dataflow=ECB_DWA_DATAFLOW,
        series_key_template="Q.{ref_area}.S14._Z._Z.NWA._Z.GI.S.N",
        keep_q4_as_annual=True,
    ),
    ECB_DWA_TOP10_WEALTH_SHARE_TICKER: _EcbSeriesConfig(
        dataflow=ECB_DWA_DATAFLOW,
        series_key_template="Q.{ref_area}.S14._Z._Z.NWA.T10.PT.S.N",
        keep_q4_as_annual=True,
    ),
}
ECB_HTTP_MAX_ATTEMPTS = 3

# ---------------------------------------------------------------------------
# World Inequality Database (WID)
# ---------------------------------------------------------------------------
"""WID bulk country CSV — net personal wealth Gini and top-10 share."""


class _WidSeriesConfig(NamedTuple):
    """One WID bulk-CSV series: variable code, percentile, and value scale."""

    variable: str
    percentile: str
    # Multiply scraped levels when the source unit differs from our stored scale.
    value_scale: float


WID_BULK_CSV_URL_TEMPLATE = (
    "https://wid.world/bulk_download/WID_data_{country_code}.csv"
)
WID_WEALTH_GINI_TICKER = "wid_wealth_gini"
WID_TOP10_WEALTH_SHARE_TICKER = "wid_top10_wealth_share"
# WID publishes 0–1 shares / Gini; store ×100 to match ECB DWA 0–100 scales.
WID_SERIES_BY_TICKER: dict[str, _WidSeriesConfig] = {
    WID_WEALTH_GINI_TICKER: _WidSeriesConfig(
        variable="ghweal992j",
        percentile="p0p100",
        value_scale=100.0,
    ),
    WID_TOP10_WEALTH_SHARE_TICKER: _WidSeriesConfig(
        variable="shweal992j",
        percentile="p90p100",
        value_scale=100.0,
    ),
}


# ---------------------------------------------------------------------------
# IMF (DataMapper + SDMX)
# ---------------------------------------------------------------------------
"""IMF Fiscal Monitor / WEO via DataMapper; international liquidity via SDMX 3.0."""

IMF_DATAMAPPER_INDICATOR_URL_TEMPLATE = (
    "https://www.imf.org/external/datamapper/api/v1/{indicator}"
)
# Seed location code → IMF area / COUNTRY code (ISO alpha-3; DataMapper uses
# 'EURO' for the euro-area aggregate).
IMF_AREA_CODE_BY_LOCATION: dict[str, str] = {
    "US": "USA",
    "FR": "FRA",
    "JP": "JPN",
    "DE": "DEU",
    "ES": "ESP",
    "IT": "ITA",
    "EU": "EURO",
}
# Primary net lending / borrowing (primary balance), % of GDP.
IMF_PRIMARY_BALANCE_TICKER = "GGXONLB_G01_GDP_PT"

# International Liquidity (IL): total reserves excluding gold, USD, monthly.
# Same concept as discontinued FRED 'TRESEG*M052N' redistributions of IMF IFS.
IMF_FX_RESERVES_TICKER = "RXF11_REVS"
IMF_SDMX_IL_DATA_URL_TEMPLATE = (
    "https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/IL/+/"
    "{ref_area}.{indicator}.USD.M"
)
IMF_SDMX_IL_START_PERIOD = "1990-01"


# ---------------------------------------------------------------------------
# OECD (SDMX)
# ---------------------------------------------------------------------------
"""OECD Economic Outlook and Short-Term Economic Statistics SDMX APIs."""

OECD_EO_SDMX_DATA_URL_TEMPLATE = (
    "https://sdmx.oecd.org/public/rest/data/OECD.ECO.MAD,DSD_EO@DF_EO/"
    "{ref_area}.{measure}.A"
)
# Production / sales / orders (MEI-style short-term indicators).
OECD_INDSERV_SDMX_DATA_URL_TEMPLATE = (
    "https://sdmx.oecd.org/public/rest/data/"
    "OECD.SDD.STES,DSD_STES@DF_INDSERV/{series_key}"
)
# Seed location code → OECD REF_AREA dimension.
OECD_REF_AREA_BY_LOCATION: dict[str, str] = {
    "US": "USA",
    "FR": "FRA",
    "JP": "JPN",
    "DE": "DEU",
    "ES": "ESP",
    "IT": "ITA",
}
# Output gap as a percent of potential GDP (Economic Outlook measure GAP).
OECD_OUTPUT_GAP_TICKER = "eo_gap"
OECD_OUTPUT_GAP_MEASURE = "GAP"
OECD_SDMX_START_PERIOD = "1990"
OECD_SDMX_MONTHLY_START_PERIOD = "2010-01"
# Japan retail trade volume excl. motor vehicles (G47), index 2015=100, SCA.
OECD_JP_RETAIL_VOLUME_TICKER = "JPN.M.TOVM.IX.G47.Y._Z._Z.N"


class OecdSeriesConfig(TypedDict):
    """OECD SDMX series: URL template, frequency, and key-building fields."""

    url_template: str
    frequency: EconomicPublicationFrequencyChoices
    start_period: str
    # Economic Outlook keys use '{ref_area}.{measure}.A'.
    measure: NotRequired[str]
    # INDSERV / fixed-key series; may include '{ref_area}' or be a full key.
    series_key_template: NotRequired[str]
    # Optional DBnomics mirror URL when the OECD SDMX dataflow is unavailable.
    fallback_url_template: NotRequired[str]


OECD_SERIES_BY_TICKER: dict[str, OecdSeriesConfig] = {
    OECD_OUTPUT_GAP_TICKER: OecdSeriesConfig(
        measure=OECD_OUTPUT_GAP_MEASURE,
        url_template=OECD_EO_SDMX_DATA_URL_TEMPLATE,
        frequency=EconomicPublicationFrequencyChoices.ANNUAL,
        start_period=OECD_SDMX_START_PERIOD,
    ),
    OECD_JP_RETAIL_VOLUME_TICKER: OecdSeriesConfig(
        url_template=OECD_INDSERV_SDMX_DATA_URL_TEMPLATE,
        series_key_template=OECD_JP_RETAIL_VOLUME_TICKER,
        frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        start_period=OECD_SDMX_MONTHLY_START_PERIOD,
    ),
}


# ---------------------------------------------------------------------------
# MLIT — Residential Property Price Index
# ---------------------------------------------------------------------------
"""MLIT nationwide seasonally adjusted Residential Property Price Index Excel."""

MLIT_RPPI_PAGE_URL = (
    "https://www.mlit.go.jp/totikensangyo/totikensangyo_tk5_000085.html"
)
MLIT_SITE_ORIGIN = "https://www.mlit.go.jp"
MLIT_RPPI_SHEET = "全国Japan季節調整"
# 1-based Excel columns on '全国Japan季節調整' (index level, not MoM / samples).
MLIT_RPPI_INDEX_COLUMN_BY_TICKER: dict[str, int] = {
    "detached_house_sa": 8,
    "condominiums_sa": 11,
}

# ---------------------------------------------------------------------------
# METI — Current Survey of Commerce (retail sales value index)
# ---------------------------------------------------------------------------
"""METI retail trade sales-value index (2020=100, SA), via e-Stat Excel."""

# Long time-series workbook 'h2slt51j.xlsx' (indices of commercial sales value).
METI_RETAIL_SALES_INDEX_XLSX_URL = (
    "https://www.e-stat.go.jp/stat-search/file-download"
    "?statInfId=000031387999&fileKind=0"
)
METI_RETAIL_SALES_INDEX_TICKER = "retail_sales_index_sa"
METI_RETAIL_SALES_INDEX_SHEET = "季調済指数(Seasonaly adjusted)（月次M）"
# 1-based Excel column for nationwide retail trade total ('小売業計' / 'Retail').
METI_RETAIL_SALES_INDEX_COLUMN = 21

# Indices of Production Capacity and Operating Ratio — monthly SA operating ratio.
# Time-series workbook updates with IIP; e-Stat getStatsData for this series lags.
METI_OPERATING_RATIO_XLSX_URL = (
    "https://www.e-stat.go.jp/stat-search/file-download"
    "?statInfId=000040067191&fileKind=0"
)
METI_OPERATING_RATIO_TICKER = "operating_ratio_mfg_sa"
METI_OPERATING_RATIO_SHEET = "稼働率Ｓ"
METI_OPERATING_RATIO_MANUFACTURING_LABEL = "製造工業"

# ---------------------------------------------------------------------------
# e-Stat — government statistics release calendar (Japan)
# ---------------------------------------------------------------------------
"""Shared e-Stat 公表予定カレンダー for Cabinet Office / MIC / METI / etc."""

ESTAT_RELEASE_CALENDAR_URL = "https://www.e-stat.go.jp/release-calendar"
ESTAT_RELEASE_CALENDAR_LOOKAHEAD_MONTHS = 6


class EstatCalendarMatch(NamedTuple):
    """Keyword filters for one seeded 'technical_name' on the e-Stat calendar."""

    # Usage of tuple: fixed ordered Japanese title fragments to match on e-Stat.
    title_keywords: tuple[str, ...]
    # Usage of tuple: fixed ordered prefer fragments when several titles match.
    prefer_keywords: tuple[str, ...] = ()
    # Usage of tuple: fixed ordered fragments that disqualify a calendar title.
    exclude_keywords: tuple[str, ...] = ()


# Seeded 'technical_name' → Japanese title fragments on e-Stat detail links.
ESTAT_SCHEDULE_MATCH_BY_TECHNICAL_NAME: dict[str, EstatCalendarMatch] = {
    "Quarterly Estimates of GDP": EstatCalendarMatch(
        title_keywords=("四半期別ＧＤＰ速報",),
    ),
    "Household Disposable Income and Saving Ratio": EstatCalendarMatch(
        title_keywords=("四半期別ＧＤＰ速報",),
        prefer_keywords=("2次速報",),
    ),
    "Machinery Orders": EstatCalendarMatch(
        title_keywords=("機械受注統計調査",),
    ),
    "Consumer Confidence Survey": EstatCalendarMatch(
        title_keywords=("消費動向調査",),
        exclude_keywords=("消費動向指数",),
    ),
    "Consumer Price Index": EstatCalendarMatch(
        title_keywords=("消費者物価指数",),
        prefer_keywords=("全国",),
        exclude_keywords=("東京都区部",),
    ),
    "Labour Force Survey": EstatCalendarMatch(
        title_keywords=("労働力調査",),
        prefer_keywords=("基本集計",),
    ),
    "Indices of Industrial Production": EstatCalendarMatch(
        title_keywords=("鉱工業生産・出荷・在庫指数",),
        prefer_keywords=("速報",),
        exclude_keywords=("出荷内訳",),
    ),
    # Operating-ratio workbook updates with the preliminary IIP release.
    "Indices of Production Capacity and Operating Ratio": EstatCalendarMatch(
        title_keywords=("鉱工業生産・出荷・在庫指数",),
        prefer_keywords=("速報",),
        exclude_keywords=("出荷内訳",),
    ),
    "Current Survey of Commerce": EstatCalendarMatch(
        title_keywords=("商業動態統計調査",),
        prefer_keywords=("速報",),
    ),
    # OECD MEI Japan retail volume tracks METI commerce releases.
    "Main Economic Indicators": EstatCalendarMatch(
        title_keywords=("商業動態統計調査",),
        prefer_keywords=("速報",),
    ),
}

# ---------------------------------------------------------------------------
# Banque de France (Webstat) — national business surveys
# ---------------------------------------------------------------------------
"""Banque de France Webstat CSV catalog export for economic series."""

BANQUE_DE_FRANCE_WEBSTAT_CSV_URL = (
    "https://webstat.banque-france.fr/export/csv/fr/catalog"
)
# Manufacturing industry average capacity utilisation rate (SA / CVS), percent.
BANQUE_DE_FRANCE_MFG_CAPACITY_UTILISATION_DATASET = "CONJ"
BANQUE_DE_FRANCE_MFG_CAPACITY_UTILISATION_TICKER = "CONJ.M.N01.S.IN.000CZ.TUTSM000.10"
# Manufacturing new orders — EMC solde d'opinion on MoM change in orders (SA / CVS).
# Neutral 0; above 0 = more firms report rising orders than falling (not a euro amount).
BANQUE_DE_FRANCE_MFG_NEW_ORDERS_TICKER = "CONJ.M.N01.S.IN.000CZ.CRTEM100.10"
# General-government debt-security cash financing (Webstat SC1, S.13 / 1300).
# Gross / net are published; redemptions = gross − net (derived).
BANQUE_DE_FRANCE_SC1_DATASET = "SC1"
BANQUE_DE_FRANCE_GG_DEBT_SECURITIES_GROSS_TICKER = "SC1.Q.FR.1300.F33000.N.8.Z01.E.Z"
BANQUE_DE_FRANCE_GG_DEBT_SECURITIES_NET_TICKER = "SC1.Q.FR.1300.F33000.N.4.Z01.E.Z"
BANQUE_DE_FRANCE_GG_DEBT_SECURITIES_REDEMPTIONS_TICKER = (
    "gg_debt_securities_redemptions"
)
# EMC publication list (dates); Webstat has no release calendar API.
BANQUE_DE_FRANCE_EMC_PUBLICATIONS_URL = (
    "https://www.banque-france.fr/fr/publications-et-recherche/"
    "nos-principales-publications/enquete-mensuelle-de-conjoncture"
)
# Market-calendar EMC embargo clock (Europe/Paris); page dates have no hour.
BANQUE_DE_FRANCE_EMC_PARIS_RELEASE_HOUR = 8
BANQUE_DE_FRANCE_EMC_PARIS_RELEASE_MINUTE = 45
# French month labels on BdF publication cards → month number.
BANQUE_DE_FRANCE_FRENCH_MONTH_NUMBER_BY_NAME: dict[str, int] = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}

# ---------------------------------------------------------------------------
# ECB — quarterly sector accounts release calendar
# ---------------------------------------------------------------------------
"""ECB QSA household / NFC press slots (Frankfurt local wall time)."""

ECB_QSA_RELEASE_CALENDAR_URL = (
    "https://www.ecb.europa.eu/press/calendars/statscal/eaa/html/stprfi.en.html"
)
# First household/NFC QSA press release title fragment on the calendar page.
ECB_QSA_HOUSEHOLD_RELEASE_TITLE_FRAGMENT = (
    "Euro area households and non-financial corporations"
)

# ---------------------------------------------------------------------------
# OECD — Economic Outlook known upcoming slots
# ---------------------------------------------------------------------------
"""OECD EO full-volume dates when the live media-advisory page is blocked.

Usage of tuple: (year, month, day, hour, minute) in Europe/Paris.
December 2026 slot from the public EO release calendar (06:00 Paris).
"""

OECD_ECONOMIC_OUTLOOK_PARIS_RELEASE_DATETIMES: list[tuple[int, int, int, int, int]] = [
    (2026, 12, 2, 6, 0),
]

# ---------------------------------------------------------------------------
# Census ACS — annual Gini / PUMS release schedule page
# ---------------------------------------------------------------------------
"""ACS 1-year product schedule (Gini tables); PUMS often lands later / TBD."""

CENSUS_ACS_RELEASE_SCHEDULE_URL = (
    "https://www.census.gov/programs-surveys/acs/news/data-releases/"
    "2025/release-schedule.html"
)
# ACS public release clock is Eastern morning when Census posts a civil date.
CENSUS_ACS_EASTERN_RELEASE_HOUR = 12
CENSUS_ACS_EASTERN_RELEASE_MINUTE = 0

# ---------------------------------------------------------------------------
# Ministry of Finance (Japan) — Balance of Payments
# ---------------------------------------------------------------------------
"""MOF table 6s-a-1: seasonally adjusted quarterly current-account summary CSV."""

MOF_BOP_SA_QUARTERLY_CSV_URL = (
    "https://www.mof.go.jp/policy/international_policy/reference/"
    "balance_of_payments/bp_trend/bpnet/sbp/s-a/6s-a-1.csv"
)
# Source unit is 100 million yen (億円); stored values are billion yen (÷ 10).
MOF_BOP_OKUYEN_PER_BILLION_YEN = 10.0
MOF_BOP_CURRENT_ACCOUNT_TICKER = "mof_bop_ca"
MOF_BOP_GOODS_SERVICES_TICKER = "mof_bop_gs"
MOF_BOP_PRIMARY_INCOME_TICKER = "mof_bop_in1"
MOF_BOP_SECONDARY_INCOME_TICKER = "mof_bop_in2"
# CSV column indexes after csv.reader (Current account / Goods & services /
# Primary income / Secondary income).
MOF_BOP_COLUMN_INDEX_BY_TICKER: dict[str, int] = {
    MOF_BOP_CURRENT_ACCOUNT_TICKER: 5,
    MOF_BOP_GOODS_SERVICES_TICKER: 6,
    MOF_BOP_PRIMARY_INCOME_TICKER: 11,
    MOF_BOP_SECONDARY_INCOME_TICKER: 12,
}
MOF_BOP_QUARTER_START_MONTH_BY_LABEL: dict[str, int] = {
    "1st quarter": 1,
    "2nd quarter": 4,
    "3rd quarter": 7,
    "4th quarter": 10,
}

# ---------------------------------------------------------------------------
# Bank of Japan — Tankan (Time-Series API under BOJ_TIME_SERIES_BY_TICKER)
# ---------------------------------------------------------------------------
"""Tankan judgement DIs use getDataCode db=CO (see BOJ_TIME_SERIES_BY_TICKER)."""

BOJ_RELEASE_SCHEDULE_XLSX_URL = (
    "https://www.boj.or.jp/en/statistics/outline/tkohyos.xlsx"
)
# Seeded technical_name → BoJ schedule workbook series title (column B).
# Values are exact titles or prefixes matched with startswith on column B.
BOJ_SCHEDULE_SERIES_TITLE_BY_TECHNICAL_NAME: dict[str, str] = {
    "Tankan": (
        "Tankan (Short-Term Economic Survey of Enterprises in Japan) / "
        "Summary and Outline"
    ),
    "Corporate Goods Price Index": "Corporate Goods Price Index",
    "Services Producer Price Index": "Services Producer Price Index",
    "Flow of Funds general government": "Flow of Funds Accounts (Preliminary Figures)",
    "Flow of Funds household loans": "Flow of Funds Accounts (Preliminary Figures)",
    "Derived FOF loans / ESRI DI": "Flow of Funds Accounts (Preliminary Figures)",
    # MOF BoP CSV; BoJ publishes the shared BOP release dates on this workbook.
    "Balance of Payments": "Balance of Payments (Preliminary",
}
# Official BoJ statistics clock for series marked on the schedule (* / 8:50 a.m.).
BOJ_RELEASE_TOKYO_HOUR = 8
BOJ_RELEASE_TOKYO_MINUTE = 50

# ---------------------------------------------------------------------------
# NAHB — Housing Market Index
# ---------------------------------------------------------------------------
"""NAHB/Wells Fargo National HMI history workbook resolved from the HMI page."""

NAHB_HMI_PAGE_URL = (
    "https://www.nahb.org/news-and-economics/housing-economics/indices/"
    "housing-market-index"
)
NAHB_SITE_ORIGIN = "https://www.nahb.org"
NAHB_HMI_TICKER = "nahb_hmi"
NAHB_HMI_RELEASE_DATES_URL = (
    "https://www.nahb.org/news-and-economics/housing-economics/indices/"
    "nahb-wells-fargo-housing-market-index-release-dates"
)
# Official HMI embargo clock (NAHB release-dates page).
NAHB_HMI_EASTERN_RELEASE_HOUR = 10
NAHB_HMI_EASTERN_RELEASE_MINUTE = 0

# ---------------------------------------------------------------------------
# ISM — Manufacturing / Services PMI
# ---------------------------------------------------------------------------
"""ISM composite PMI: PR Newswire titles (recent) + forecasts.org NAPM (legacy)."""

ISM_PRNEWSWIRE_LIST_URL = (
    "https://www.prnewswire.com/news/institute-for-supply-management/"
)
ISM_PRNEWSWIRE_PAGE_SIZE = 100
ISM_PRNEWSWIRE_MAX_PAGES = 10
ISM_FORECASTS_NAPM_URL = "https://www.forecasts.org/data/data/NAPM.htm"
ISM_MANUFACTURING_PMI_TICKER = "ism_manufacturing_pmi"
ISM_SERVICES_PMI_TICKER = "ism_services_pmi"
ISM_RELEASE_CALENDAR_URL = (
    "https://www.ismworld.org/supply-management-news-and-reports/reports/"
    "rob-report-calendar/"
)
# Official ISM Report On Business clock (ISM release calendar).
ISM_EASTERN_RELEASE_HOUR = 10
ISM_EASTERN_RELEASE_MINUTE = 0
# Published 2026 day-of-month slots from ISM's release calendar (live HTML is
# often blocked from this host; keep the official table here, no invented days).
# Usage of dict: month number → manufacturing day / services day.
ISM_2026_RELEASE_DAY_BY_MONTH: dict[int, tuple[int, int]] = {
    1: (5, 7),
    2: (2, 4),
    3: (2, 4),
    4: (1, 6),
    5: (1, 5),
    6: (1, 3),
    7: (1, 6),
    8: (3, 5),
    9: (1, 3),
    10: (1, 5),
    11: (2, 4),
    12: (1, 3),
}

# BIS statistics release calendar (FRED mirrors these series without future dates).
BIS_RELEASE_CALENDAR_API_URL = "https://data.bis.org/api/v0/releasecalendar"
BIS_EER_CATEGORY_NAME = "Effective exchange rates"
BIS_CREDIT_CATEGORY_NAME = "Credit to the non-financial sector"
BIS_EER_MONTHLY_RELEASE_TYPE = "Nominal / real monthly data"

# BLS Employment Cost Index schedule (FRED release 11 often has no future rows).
# Official dates/times from https://www.bls.gov/schedule/news_release/eci.htm
# Usage of tuple: (year, month, day) release civil dates at 08:30 ET.
BLS_ECI_EASTERN_RELEASE_DATES: list[tuple[int, int, int]] = [
    (2027, 1, 29),
    (2027, 4, 30),
    (2027, 7, 30),
    (2027, 10, 29),
]
BLS_ECI_EASTERN_RELEASE_HOUR = 8
BLS_ECI_EASTERN_RELEASE_MINUTE = 30

# S&P Global PMI final-release calendar (UTC times on the public page).
SP_GLOBAL_PMI_RELEASE_DATES_URL = (
    "https://www.pmi.spglobal.com/Public/Release/ReleaseDates?language=en"
)


class SpGlobalPmiType(str, Enum):
    """Final S&P Global PMI release type."""

    MANUFACTURING = "manufacturing"
    SERVICES = "services"
    COMPOSITE = "composite"


# Seeded technical_name → release type.
SP_GLOBAL_PMI_TYPE_BY_TECHNICAL_NAME: dict[str, SpGlobalPmiType] = {
    "S&P Global Manufacturing PMI": SpGlobalPmiType.MANUFACTURING,
    "S&P Global Services PMI": SpGlobalPmiType.SERVICES,
    "S&P Global Composite PMI": SpGlobalPmiType.COMPOSITE,
}
# Calendar title fragment on the S&P Global release-dates page. Composite lands
# with Services, so its title still uses the Services label.
SP_GLOBAL_PMI_CALENDAR_LABEL_BY_TYPE: dict[SpGlobalPmiType, str] = {
    SpGlobalPmiType.MANUFACTURING: "Manufacturing",
    SpGlobalPmiType.SERVICES: "Services",
    SpGlobalPmiType.COMPOSITE: "Services",
}
# Manufacturing = 1st weekday; Services / Composite = 3rd weekday.
SP_GLOBAL_PMI_WEEKDAY_INDEX_BY_TYPE: dict[SpGlobalPmiType, int] = {
    SpGlobalPmiType.MANUFACTURING: 1,
    SpGlobalPmiType.SERVICES: 3,
    SpGlobalPmiType.COMPOSITE: 3,
}
# Standard final-release UTC clocks from the S&P Global PMI calendar page.
# Usage of dict: (location, PMI type) → (hour, minute) in UTC.
SP_GLOBAL_PMI_UTC_CLOCK_BY_LOCATION_AND_TYPE: dict[
    tuple[str, SpGlobalPmiType], tuple[int, int]
] = {
    ("US", SpGlobalPmiType.MANUFACTURING): (14, 45),
    ("US", SpGlobalPmiType.SERVICES): (14, 45),
    ("US", SpGlobalPmiType.COMPOSITE): (14, 45),
    ("FR", SpGlobalPmiType.MANUFACTURING): (8, 50),
    ("FR", SpGlobalPmiType.SERVICES): (8, 50),
    ("FR", SpGlobalPmiType.COMPOSITE): (8, 50),
    ("JP", SpGlobalPmiType.MANUFACTURING): (0, 30),
    ("JP", SpGlobalPmiType.SERVICES): (0, 30),
    ("JP", SpGlobalPmiType.COMPOSITE): (0, 30),
}

# ---------------------------------------------------------------------------
# Conference Board — Measure of CEO Confidence
# ---------------------------------------------------------------------------
"""CEO Confidence quarters scraped from Conference Board PR Newswire releases."""

CONFERENCE_BOARD_PRNEWSWIRE_ORIGIN = "https://www.prnewswire.com"
CONFERENCE_BOARD_PRNEWSWIRE_LIST_URL = (
    f"{CONFERENCE_BOARD_PRNEWSWIRE_ORIGIN}/news/the-conference-board/"
)
CONFERENCE_BOARD_PRNEWSWIRE_PAGE_SIZE = 100
CONFERENCE_BOARD_PRNEWSWIRE_MAX_PAGES = 12
CONFERENCE_BOARD_CEO_CONFIDENCE_TICKER = "ceo_confidence"
CONFERENCE_BOARD_CEO_CONFIDENCE_PAGE_URL = (
    "https://www.conference-board.org/topics/CEO-Confidence/"
)
# PR Newswire / Conference Board CEO Confidence embargo clock.
CONFERENCE_BOARD_CEO_CONFIDENCE_EASTERN_RELEASE_HOUR = 6
CONFERENCE_BOARD_CEO_CONFIDENCE_EASTERN_RELEASE_MINUTE = 0

# ---------------------------------------------------------------------------
# Trading Economics — S&P Global PMI (Composite / Manufacturing / Services)
# ---------------------------------------------------------------------------
"""Public TE chart pages for S&P Global PMI; ~3y history without a paid API key."""

TRADING_ECONOMICS_SITE_ORIGIN = "https://tradingeconomics.com"
TRADING_ECONOMICS_CHARTS_API_ORIGIN = "https://charts-api.tradingeconomics.com"
TRADING_ECONOMICS_CHART_OBFUSCATION_KEY = "tradingeconomics-charts-core-api-key"
TRADING_ECONOMICS_CHART_SPAN = "max"
# Usage of dict: keys are seed tickers; values are TE indicator page paths.
TRADING_ECONOMICS_PMI_PATH_BY_TICKER: dict[str, str] = {
    "us_sp_composite_pmi": "/united-states/composite-pmi",
    "us_sp_manufacturing_pmi": "/united-states/manufacturing-pmi",
    "us_sp_services_pmi": "/united-states/services-pmi",
    "fr_sp_composite_pmi": "/france/composite-pmi",
    "fr_sp_manufacturing_pmi": "/france/manufacturing-pmi",
    "fr_sp_services_pmi": "/france/services-pmi",
    "jp_sp_composite_pmi": "/japan/composite-pmi",
    "jp_sp_manufacturing_pmi": "/japan/manufacturing-pmi",
    "jp_sp_services_pmi": "/japan/services-pmi",
}

# ---------------------------------------------------------------------------
# Derived publication schedules (latest input wins)
# ---------------------------------------------------------------------------
"""Derived ticker → same-location input tickers that gate the derived observation."""

DERIVED_SCHEDULE_INPUT_TICKERS_BY_TICKER: dict[str, list[str]] = {
    # Estimated Annual GDP Growth: resolved to Real GDP ticker at runtime.
    ANNUAL_GDP_GROWTH_TICKER: [],
    # DSPI is not seeded; Personal Saving / PCE share the Personal Income clock
    # with DPI, so use those seeded siblings for the derived schedule.
    FRED_HH_SAVING_RATIO_TICKER: [
        FRED_HH_SAVING_AMOUNT_TICKER,
        FRED_HH_DEBT_INCOME_TICKER,
    ],
    FRED_HH_CONSUMPTION_RATIO_TICKER: [
        FRED_HH_CONSUMPTION_AMOUNT_TICKER,
        FRED_HH_DEBT_INCOME_TICKER,
    ],
    FRED_GOVERNMENT_OTHER_REVENUE_TICKER: [
        FRED_GOVERNMENT_REVENUE_TICKER,
        FRED_GOVERNMENT_TAX_REVENUE_TICKER,
        FRED_GOVERNMENT_SOCIAL_CONTRIBUTIONS_TICKER,
    ],
    FRED_GOVERNMENT_OTHER_LIABILITY_TRANSACTIONS_TICKER: [
        FRED_GOVERNMENT_TOTAL_LIABILITY_TRANSACTIONS_TICKER,
        FRED_GOVERNMENT_DEBT_SECURITY_TRANSACTIONS_TICKER,
        FRED_GOVERNMENT_LOAN_TRANSACTIONS_TICKER,
    ],
    FRED_GOVERNMENT_FINANCING_ACCOUNT_TICKER: [
        FRED_GOVERNMENT_TOTAL_LIABILITY_TRANSACTIONS_TICKER,
        FRED_GOVERNMENT_ASSET_TRANSACTIONS_TICKER,
    ],
    FRED_GROSS_CAPITAL_SHARE_TICKER: [
        FRED_NFC_NOS_TICKER,
        FRED_NFC_CFC_TICKER,
        FRED_NFC_CAPITAL_SHARE_DENOMINATOR_TICKER,
    ],
    FRED_GOVERNMENT_DEBT_TICKER: [
        FRED_GOVERNMENT_DEBT_SECURITIES_TICKER,
        FRED_GOVERNMENT_DEBT_LOANS_TICKER,
    ],
    INSEE_REAL_RDB_TICKER: [
        INSEE_RDB_NOMINAL_TICKER,
        INSEE_HH_FCE_CURRENT_PRICE_TICKER,
        INSEE_HH_FCE_CHAINED_VOLUME_TICKER,
    ],
    # Deflator / D8 / Palma components are not seeded as indicators; schedule
    # falls through to DERIVED_SCHEDULE_CALENDAR_TECHNICAL_NAME_BY_TICKER.
    EUROSTAT_GG_FINANCING_ACCOUNT_TICKER: [
        EUROSTAT_GG_TOTAL_LIABILITY_TRANSACTIONS_TICKER,
        EUROSTAT_GG_ASSET_TRANSACTIONS_TICKER,
    ],
    EUROSTAT_GG_OTHER_LIABILITY_TRANSACTIONS_TICKER: [
        EUROSTAT_GG_TOTAL_LIABILITY_TRANSACTIONS_TICKER,
        EUROSTAT_GG_DEBT_SECURITY_TRANSACTIONS_TICKER,
        EUROSTAT_GG_LOAN_TRANSACTIONS_TICKER,
    ],
    EUROSTAT_NET_EXPORTS_TICKER: [
        EUROSTAT_NET_EXPORTS_EXPORT_TICKER,
        EUROSTAT_NET_EXPORTS_IMPORT_TICKER,
    ],
    EUROSTAT_NET_OPERATING_SURPLUS_TICKER: [
        EUROSTAT_NET_OPERATING_SURPLUS_GROSS_TICKER,
        EUROSTAT_NET_OPERATING_SURPLUS_CFC_TICKER,
    ],
    BANQUE_DE_FRANCE_GG_DEBT_SECURITIES_REDEMPTIONS_TICKER: [
        BANQUE_DE_FRANCE_GG_DEBT_SECURITIES_GROSS_TICKER,
    ],
    # Net liabilities is not seeded; debt securities + loans share the FoF clock.
    BOJ_FOF_GG_OTHER_LIABILITIES_TICKER: [
        BOJ_FOF_GG_DEBT_SECURITIES_TICKER,
        BOJ_FOF_GG_LOANS_TICKER,
    ],
    CENSUS_PALMA_TICKER: [CENSUS_GINI_TICKER],
    JP_CAO_HH_SAVING_RATIO_TICKER: [
        JP_CAO_NOMINAL_HH_SAVING_TICKER,
        JP_CAO_NOMINAL_HH_DI_TICKER,
    ],
    JP_CAO_HH_CONSUMPTION_RATIO_TICKER: [
        JP_CAO_NOMINAL_HH_CONSUMPTION_TICKER,
        JP_CAO_NOMINAL_HH_DI_TICKER,
    ],
    JP_CAO_GGO_OTHER_REVENUE_TICKER: [
        JP_CAO_GGO_REVENUE_TICKER,
        JP_CAO_GGO_TAXES_TICKER,
        JP_CAO_GGO_SOCIAL_CONTRIBUTIONS_TICKER,
    ],
    JP_CAO_GGO_FINANCING_ACCOUNT_TICKER: [
        JP_CAO_GGO_NET_INCURRENCE_LIABILITIES_TICKER,
        JP_CAO_GGO_NET_ACQUISITION_FINANCIAL_ASSETS_TICKER,
    ],
}

# Same ticker, different inputs by location (US FRED vs Japan Flow of Funds).
# Usage of dict: location code → ticker → input tickers.
DERIVED_SCHEDULE_INPUT_TICKERS_BY_LOCATION_AND_TICKER: dict[
    str, dict[str, list[str]]
] = {
    "US": {
        FRED_HH_DEBT_RATIO_TICKER: [
            FRED_HH_DEBT_AMOUNT_TICKER,
            FRED_HH_DEBT_INCOME_TICKER,
        ],
    },
    "JP": {
        BOJ_HH_DEBT_RATIO_TICKER: [
            BOJ_HH_LOANS_STOCK_TICKER,
            JP_CAO_HH_DEBT_INCOME_TICKER,
        ],
    },
}

# When derived inputs are not seeded as indicators, scrape this release family.
DERIVED_SCHEDULE_CALENDAR_TECHNICAL_NAME_BY_TICKER: dict[str, str] = {
    EUROSTAT_REAL_HH_GDHI_TICKER: "Quarterly sector accounts",
    EUROSTAT_HH_SAVING_RATIO_TICKER: "Quarterly sector accounts",
    EUROSTAT_HH_CONSUMPTION_RATIO_TICKER: "Quarterly sector accounts",
    EUROSTAT_GG_TAX_REVENUE_TICKER: (
        "Quarterly non-financial accounts for general government"
    ),
    EUROSTAT_GG_OTHER_REVENUE_TICKER: (
        "Quarterly non-financial accounts for general government"
    ),
}

# ---------------------------------------------------------------------------
# Industry profitability (Eurostat SBS / BEA / MOF / ESRI)
# ---------------------------------------------------------------------------

INDUSTRY_CLASSIFICATION_BY_LOCATION: dict[
    EconomicDataLocationChoices, IndustryClassificationChoices
] = {
    EconomicDataLocationChoices.FR: IndustryClassificationChoices.NACE_REV2_DIVISION,
    EconomicDataLocationChoices.US: IndustryClassificationChoices.BEA_INDUSTRY,
    EconomicDataLocationChoices.JP: IndustryClassificationChoices.MOF_CORPORATE_INDUSTRY,
}

# Japan GVA contribution uses ESRI SNA economic-activity lines (not MOF).
INDUSTRY_CONTRIBUTION_CLASSIFICATION_BY_LOCATION: dict[
    EconomicDataLocationChoices, IndustryClassificationChoices
] = {
    EconomicDataLocationChoices.FR: IndustryClassificationChoices.NACE_REV2_DIVISION,
    EconomicDataLocationChoices.US: IndustryClassificationChoices.BEA_INDUSTRY,
    EconomicDataLocationChoices.JP: IndustryClassificationChoices.ESRI_ECONOMIC_ACTIVITY,
}

INDUSTRY_PROFITABILITY_LOCATIONS: list[EconomicDataLocationChoices] = [
    EconomicDataLocationChoices.US,
    EconomicDataLocationChoices.FR,
    EconomicDataLocationChoices.JP,
]

# Shared earliest calendar / fiscal year kept for industry profitability charts.
INDUSTRY_PROFITABILITY_START_YEAR = 2010

# Eurostat SBS — historical annexes (2010–2020) + overview (2021+), amounts in m€.
EUROSTAT_SBS_OVERVIEW_DATASET = "sbs_ovw_act"
EUROSTAT_SBS_OVERVIEW_TURNOVER_INDICATOR = "NETTUR_MEUR"
EUROSTAT_SBS_OVERVIEW_GOS_INDICATOR = "GOS_MEUR"
EUROSTAT_SBS_OVERVIEW_GVA_INDICATOR = "AV_MEUR"
EUROSTAT_SBS_HISTORICAL_TURNOVER_INDICATOR = "V12110"
EUROSTAT_SBS_HISTORICAL_GOS_INDICATOR = "V12170"
EUROSTAT_SBS_HISTORICAL_GVA_INDICATOR = "V12150"
EUROSTAT_SBS_HISTORICAL_DATASETS: list[str] = [
    "sbs_na_ind_r2",
    "sbs_na_con_r2",
    "sbs_na_dt_r2",
    "sbs_na_1a_se_r2",
]
EUROSTAT_SBS_HISTORICAL_START_YEAR = INDUSTRY_PROFITABILITY_START_YEAR
EUROSTAT_SBS_HISTORICAL_END_YEAR = 2020
EUROSTAT_SBS_OVERVIEW_START_YEAR = 2021

# BEA GDP-by-industry — gross output (15), GOS (6), value added (1); billions USD.
BEA_GDP_BY_INDUSTRY_DATASET = "GDPbyIndustry"
BEA_GDP_BY_INDUSTRY_GO_TABLE_ID = "15"
BEA_GDP_BY_INDUSTRY_GOS_TABLE_ID = "6"
BEA_GDP_BY_INDUSTRY_VA_TABLE_ID = "1"
BEA_GDP_BY_INDUSTRY_GOS_COMPONENT = "Gross operating surplus"
# Parents / special aggregates excluded so charts use the finest published lines.
BEA_GDP_BY_INDUSTRY_EXCLUDED_CODES: frozenset[str] = frozenset(
    {
        "GDP",
        "PVT",
        "PGOOD",
        "PSERV",
        "FIRE",
        "ICT",
        "PROF",
        "ORE",
        "HS",
        "II",
        "NABI",
        "G",
        "GF",
        "GFE",
        "GFG",
        "GFGD",
        "GFGN",
        "GSL",
        "GSLE",
        "GSLG",
        "31G",
        "31ND",
        "33DG",
        "44RT",
        "48TW",
        "6",
        "7",
        "11",
        "21",
        "51",
        "52",
        "53",
        "54",
        "56",
        "62",
        "71",
        "72",
    }
)

# MOF Financial Statements Statistics of Corporations via e-Stat (年度次).
# Table 1 — non-finance industries; sales (045) + operating profit (048); 百万円.
ESTAT_API_BASE_URL = "https://api.e-stat.go.jp/rest/3.0/app/json"
MOF_CORPORATE_STATS_DATA_ID = "0003060791"
MOF_CORPORATE_TURNOVER_ITEM_CODE = "045"
MOF_CORPORATE_OPERATING_PROFIT_ITEM_CODE = "048"
MOF_CORPORATE_ALL_SIZES_CODE = "26"
# Totals kept out of ranking charts (leaf industries only).
MOF_CORPORATE_AGGREGATE_INDUSTRY_CODES: frozenset[str] = frozenset(
    {
        "104",  # 全産業（除く金融保険業）
        "108",  # 製造業
        "144",  # 非製造業
    }
)

# ESRI quarterly value added by economic activity (名目原系列, 単位:10億円).
JP_CAO_SEISANQNA_TOP_URL = (
    "https://www.esri.cao.go.jp/jp/sna/sonota/seisanqna/seisanqna_top.html"
)
# Convert ESRI 10億円 amounts into million yen to match MOF 'base_unit' M.
ESRI_GVA_TEN_OKU_YEN_TO_MILLION = 1000.0

INDUSTRY_PROFITABILITY_UNIT_BY_LOCATION: dict[
    EconomicDataLocationChoices, IndicatorBaseUnitChoices
] = {
    EconomicDataLocationChoices.FR: IndicatorBaseUnitChoices.M,
    EconomicDataLocationChoices.US: IndicatorBaseUnitChoices.B,
    EconomicDataLocationChoices.JP: IndicatorBaseUnitChoices.M,
}
INDUSTRY_PROFITABILITY_CURRENCY_BY_LOCATION: dict[
    EconomicDataLocationChoices, IndicatorBaseCurrencyChoices
] = {
    EconomicDataLocationChoices.FR: IndicatorBaseCurrencyChoices.EUR,
    EconomicDataLocationChoices.US: IndicatorBaseCurrencyChoices.USD,
    EconomicDataLocationChoices.JP: IndicatorBaseCurrencyChoices.JPY,
}

# ---------------------------------------------------------------------------
# Merchandise + energy customs trade rankings (charts only)
# ---------------------------------------------------------------------------

TRADE_RANKING_LOCATIONS: list[EconomicDataLocationChoices] = [
    EconomicDataLocationChoices.US,
    EconomicDataLocationChoices.FR,
    EconomicDataLocationChoices.JP,
]

# How many series to show on the left of trade ranking line charts.
TRADE_RANKING_LINE_TOP_N = 5
# On scheduled refresh, re-scrape only the last N completed years (revisions).
TRADE_RANKING_REFRESH_YEARS = 2


@dataclass(frozen=True)
class TradeRankingProfile:
    """Static ingest / chart caps and optional product filter for one trade type."""

    history_years: int
    ingest_top_n: int
    display_top_n: int
    # None = full HS2 / source merchandise universe; otherwise restrict to these codes.
    product_codes: list[str] | None
    # Display labels for 'product_codes' (empty when the universe is unrestricted).
    product_label_by_code: dict[str, str]


# Shared energy HS set (JP product-code aliases live in JP_CUSTOMS_PRODUCT_CODE_ALIASES).
_RESTRICTED_TRADE_PRODUCT_LABEL_BY_CODE: dict[str, str] = {
    "2709": "Crude petroleum oil",
    "2710": "Refined petroleum oils and preparations",
    "271111": "Liquefied natural gas (LNG)",
    "271121": "Natural gas, gaseous/pipeline",
    "270112": "Bituminous coal",
    "271600": "Electricity",
    "271112": "Liquefied propane",
    "270119": "Other non-anthracite, non-bituminous coal",
    "271113": "Liquefied butanes",
    "270799": "Other coal-tar distillation oils/products",
}

TRADE_RANKING_PROFILE_BY_TYPE: dict[TradeTypeChoices, TradeRankingProfile] = {
    TradeTypeChoices.MERCHANDISE: TradeRankingProfile(
        history_years=5,
        ingest_top_n=20,
        display_top_n=20,
        product_codes=None,
        product_label_by_code={},
    ),
    TradeTypeChoices.ENERGY: TradeRankingProfile(
        history_years=10,
        ingest_top_n=10,
        display_top_n=10,
        product_codes=list(_RESTRICTED_TRADE_PRODUCT_LABEL_BY_CODE.keys()),
        product_label_by_code=dict(_RESTRICTED_TRADE_PRODUCT_LABEL_BY_CODE),
    ),
}

TRADE_RANKING_CURRENCY_BY_LOCATION: dict[
    EconomicDataLocationChoices, IndicatorBaseCurrencyChoices
] = {
    EconomicDataLocationChoices.FR: IndicatorBaseCurrencyChoices.EUR,
    EconomicDataLocationChoices.US: IndicatorBaseCurrencyChoices.USD,
    EconomicDataLocationChoices.JP: IndicatorBaseCurrencyChoices.JPY,
}

# Eurostat Comext annual HS × partner (DS-045409).
EUROSTAT_COMEXT_STATISTICS_API_BASE_URL = (
    "https://ec.europa.eu/eurostat/api/comext/dissemination/statistics/1.0/data"
)
EUROSTAT_COMEXT_DATASET = "DS-045409"
EUROSTAT_COMEXT_VALUE_INDICATOR = "VALUE_IN_EUROS"
EUROSTAT_COMEXT_FLOW_IMPORT = "1"
EUROSTAT_COMEXT_FLOW_EXPORT = "2"
EUROSTAT_COMEXT_WORLD_PARTNER = "WORLD"
EUROSTAT_COMEXT_TOTAL_PRODUCT = "TOTAL"
# Partner aggregates excluded from partner rankings (country ISO-2 kept separately).
EUROSTAT_COMEXT_EXCLUDED_PARTNER_CODES: frozenset[str] = frozenset(
    {
        "WORLD",
        "EXT_EU",
        "EXT_EU27_2020",
        "INT_EU",
        "INT_EU27_2020",
        "EU27_2020",
        "EU28",
        "EUR_NEU",
        "EXT_EA",
        "EXT_EA19",
        "EXT_EA20",
        "EXT_EA21",
        "INT_EA",
        "INT_EA19",
        "INT_EA20",
        "INT_EA21",
        "OECD",
        "ASEAN",
        "EFTA",
        "EEA30_2020",
        "QP",  # High seas
        "QQ",  # Stores and provisions
        "QA",
        "QS",
        "QR",
        "QU",  # Countries and territories not specified
        "QV",  # …not specified (intra-Union)
        "QW",  # …not specified (extra-Union)
        "QX",
        "QY",
        "QZ",  # …not specified (extra-Union, commercial/military)
    }
)

# Census International Trade HS time series (December YTD = annual).
CENSUS_INTLTRADE_IMPORTS_HS_URL = (
    "https://api.census.gov/data/timeseries/intltrade/imports/hs"
)
CENSUS_INTLTRADE_EXPORTS_HS_URL = (
    "https://api.census.gov/data/timeseries/intltrade/exports/hs"
)
# World / all-countries total for HS product rankings.
CENSUS_INTLTRADE_WORLD_CTY_CODE = "-"
# Aggregate / non-country partner codes excluded from partner rankings.
# Country partners are 4-digit numeric codes (e.g. 5700 China); groups use
# 00xx / xXXX patterns (OECD, APEC, EU, continental totals, …).
CENSUS_INTLTRADE_EXCLUDED_CTY_CODES: frozenset[str] = frozenset(
    {
        "-",
        "0000",
        "0001",  # OPEC
        "0003",  # European Union
        "0014",  # Pacific Rim
        "0017",  # CAFTA-DR
        "0020",  # USMCA / NAFTA
        "0021",  # Twenty Latin American Republics
        "0022",  # OECD
        "0023",  # NATO
        "0024",  # LAFTA
        "0025",  # Euro area
        "0026",  # APEC
        "1XXX",
        "2XXX",
        "3XXX",
        "4XXX",
        "5XXX",
        "6XXX",
        "7XXX",
        "8XXX",
    }
)

# Japan Customs via e-Stat 「概況品別国別表」(Principal Commodity by Country).
# Values are annual Value-Year (cat02=120), unit 1,000 yen; scraper scales to JPY.
# Table ids change when Customs republishes multi-year bundles — update here.
JP_CUSTOMS_VALUE_YEAR_CAT02 = "120"
JP_CUSTOMS_PRODUCT_CLASS_LEVEL = "2"
JP_CUSTOMS_VALUE_SCALE = 1000.0
JP_CUSTOMS_ESTAT_STATS_DATA_IDS: list[str] = [
    # Kept for older imports / docs; scrapers use the flow-specific table map.
    "0003425295",
    "0003425296",
]
# (statsDataId, TradeFlowChoices value) for years covered by each bundle.
JP_CUSTOMS_PRINCIPAL_COMMODITY_TABLES: list[tuple[str, str]] = [
    ("0003425295", "EXPORT"),  # 2021–2025 export
    ("0003425296", "IMPORT"),  # 2021–2025 import
]

# Japan Customs 概況品 codes → canonical HS product codes (labels come from the profile).
# Finer than merchandise level-2 aggregates; see docs/DATA_SOURCES.md for gaps
# (no JP line for pipeline gas 271121, electricity 271600, or butanes 271113 alone).
JP_CUSTOMS_PRODUCT_CODE_ALIASES: dict[str, str] = {
    "30301000": "2709",  # PETROLEUM (crude)
    "30303000": "2710",  # PETROLEUM PRODUCTS
    "30501030": "271111",  # LIQUEFIED NATURAL GAS
    "30101030": "270112",  # COAL OF COKING ≈ bituminous
    "30101050": "270119",  # COAL N.E.S.
    "30501010": "271112",  # LIQUEFIED PETROLEUM GAS → propane (LPG bundle)
    "50300000": "270799",  # MINERAL TAR,CRUDE CHEMICAL (2706–2707)
}
