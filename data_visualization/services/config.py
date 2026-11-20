"""Config for visualization services."""

from enum import Enum

from economic_overview.models.common import EconomicDataLocationChoices
from economic_overview.models.economic_indicators import (
    EconomicDataCategoryChoices,
    EconomicDataSubcategoryChoices,
    IndicatorDisplayModeChoices,
)
from market_overview.models.common import LocationChoices

# ---------------------------------------------------------------------------
# Economic events
# ---------------------------------------------------------------------------

# Calendar countries (no DE / ES / IT). Sort order: US → FR → JP → EU.
ECONOMIC_EVENTS_LOCATIONS: list[EconomicDataLocationChoices] = [
    EconomicDataLocationChoices.US,
    EconomicDataLocationChoices.FR,
    EconomicDataLocationChoices.JP,
    EconomicDataLocationChoices.EU,
]

# ---------------------------------------------------------------------------
# Economic recap
# ---------------------------------------------------------------------------

# Country columns on the Economic Recap table.
ECONOMIC_RECAP_LOCATIONS: list[EconomicDataLocationChoices] = [
    EconomicDataLocationChoices.US,
    EconomicDataLocationChoices.FR,
    EconomicDataLocationChoices.JP,
]
# Year dropdown on the as-of toolbar (fixed range through the current year).
ECONOMIC_RECAP_AS_OF_YEAR_START = 2010
# Closing calendar month for each as-of quarter button (Q1→Mar … Q4→Dec).
ECONOMIC_RECAP_QUARTER_END_MONTH_BY_QUARTER: dict[int, int] = {
    1: 3,
    2: 6,
    3: 9,
    4: 12,
}
# Month labels for the as-of Month dropdown (1-indexed; unused index 0).
ECONOMIC_RECAP_AS_OF_MONTH_LABELS: list[str] = [
    "",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]
# Printed levels kept per indicator for client Raw / QoQ / YoY / YTDYoY.
# Monthly YTDYoY Previous needs ~3 calendar years through the latest month
# (Jan..n for current, prior, and prior-prior); quarterly YTD YoY needs the
# current year plus two prior years; annual vsGDP Previous needs enough
# quarterly GDP for two closed calendar years.
TIME_SERIES_HISTORY_WINDOW = 48

# ---------------------------------------------------------------------------
# Economic charts — layout
# ---------------------------------------------------------------------------

# Single-country regions on the Economic Charts page.
ECONOMIC_CHARTS_LOCATIONS: list[EconomicDataLocationChoices] = [
    EconomicDataLocationChoices.US,
    EconomicDataLocationChoices.FR,
    EconomicDataLocationChoices.JP,
]


class ChartPeriodWindow(str, Enum):
    """Shared chart history window presets."""

    ONE_YEAR = "1Y"
    THREE_YEARS = "3Y"
    FIVE_YEARS = "5Y"
    TEN_YEARS = "10Y"
    MAX = "Max"


# Years of history for each chart period window. None keeps every available point.
CHART_PERIOD_WINDOW_YEARS: dict[ChartPeriodWindow, int | None] = {
    ChartPeriodWindow.ONE_YEAR: 1,
    ChartPeriodWindow.THREE_YEARS: 3,
    ChartPeriodWindow.FIVE_YEARS: 5,
    ChartPeriodWindow.TEN_YEARS: 10,
    ChartPeriodWindow.MAX: None,
}

YTD_CHART_MODES: frozenset[IndicatorDisplayModeChoices] = frozenset(
    {
        IndicatorDisplayModeChoices.YTD_RAW,
        IndicatorDisplayModeChoices.YTD_YOY,
        IndicatorDisplayModeChoices.YTD_VS_GDP,
    }
)

# Subcategory order under each top-level charts / recap category.
ECONOMIC_SUBCATEGORIES_BY_CATEGORY: dict[
    EconomicDataCategoryChoices, list[EconomicDataSubcategoryChoices]
] = {
    EconomicDataCategoryChoices.MACROECONOMICS: [
        EconomicDataSubcategoryChoices.GROWTH,
        EconomicDataSubcategoryChoices.TRADE,
        EconomicDataSubcategoryChoices.CONFIDENCE,
    ],
    EconomicDataCategoryChoices.HOUSEHOLD: [
        EconomicDataSubcategoryChoices.LABOUR,
        EconomicDataSubcategoryChoices.INEQUALITY,
        EconomicDataSubcategoryChoices.INCOME,
        EconomicDataSubcategoryChoices.SAVING,
        EconomicDataSubcategoryChoices.DEBT,
        EconomicDataSubcategoryChoices.SALES,
        EconomicDataSubcategoryChoices.PRICES,
        EconomicDataSubcategoryChoices.HOUSING,
        EconomicDataSubcategoryChoices.CONFIDENCE,
    ],
    EconomicDataCategoryChoices.BUSINESS: [
        EconomicDataSubcategoryChoices.INCOME,
        EconomicDataSubcategoryChoices.INVESTMENT,
        EconomicDataSubcategoryChoices.COST,
        EconomicDataSubcategoryChoices.DEBT,
        EconomicDataSubcategoryChoices.PRICES,
        EconomicDataSubcategoryChoices.PRODUCTION,
        EconomicDataSubcategoryChoices.CONFIDENCE,
    ],
    EconomicDataCategoryChoices.GOVERNMENT: [
        EconomicDataSubcategoryChoices.BUDGET,
        EconomicDataSubcategoryChoices.FINANCING,
        EconomicDataSubcategoryChoices.DEBT,
    ],
}


class ChartDefaultLocationScope(str, Enum):
    """Location scope for chart default series selections."""

    ALL = "all"


# Default series label(s) per category/subcategory and location scope.
# Prefer a location-specific key when present; otherwise use ALL.
# Series labels missing for a location are skipped when the default selection is built.
ECONOMIC_CHARTS_DEFAULT_SERIES_LABELS: dict[
    tuple[
        EconomicDataCategoryChoices,
        EconomicDataSubcategoryChoices,
        ChartDefaultLocationScope | EconomicDataLocationChoices,
    ],
    list[str],
] = {
    (
        EconomicDataCategoryChoices.MACROECONOMICS,
        EconomicDataSubcategoryChoices.GROWTH,
        ChartDefaultLocationScope.ALL,
    ): ["Real GDP"],
    (
        EconomicDataCategoryChoices.MACROECONOMICS,
        EconomicDataSubcategoryChoices.CONFIDENCE,
        ChartDefaultLocationScope.ALL,
    ): ["S&P Composite PMI"],
    (
        EconomicDataCategoryChoices.MACROECONOMICS,
        EconomicDataSubcategoryChoices.TRADE,
        ChartDefaultLocationScope.ALL,
    ): [
        "Current Account",
        "Trade Balance",
    ],
    (
        EconomicDataCategoryChoices.HOUSEHOLD,
        EconomicDataSubcategoryChoices.LABOUR,
        ChartDefaultLocationScope.ALL,
    ): ["Unemployment Rate"],
    (
        EconomicDataCategoryChoices.HOUSEHOLD,
        EconomicDataSubcategoryChoices.INEQUALITY,
        ChartDefaultLocationScope.ALL,
    ): ["Gini Index (Revenue)"],
    (
        EconomicDataCategoryChoices.HOUSEHOLD,
        EconomicDataSubcategoryChoices.SAVING,
        ChartDefaultLocationScope.ALL,
    ): ["Household Saving Ratio"],
    (
        EconomicDataCategoryChoices.HOUSEHOLD,
        EconomicDataSubcategoryChoices.DEBT,
        ChartDefaultLocationScope.ALL,
    ): ["Household Debt Ratio"],
    (
        EconomicDataCategoryChoices.HOUSEHOLD,
        EconomicDataSubcategoryChoices.SALES,
        ChartDefaultLocationScope.ALL,
    ): ["Retail Sales"],
    (
        EconomicDataCategoryChoices.HOUSEHOLD,
        EconomicDataSubcategoryChoices.SALES,
        EconomicDataLocationChoices.US,
    ): [
        "Retail Sales",
        "Real Retail Sales",
    ],
    (
        EconomicDataCategoryChoices.HOUSEHOLD,
        EconomicDataSubcategoryChoices.PRICES,
        ChartDefaultLocationScope.ALL,
    ): ["Consumer Price Index"],
    (
        EconomicDataCategoryChoices.HOUSEHOLD,
        EconomicDataSubcategoryChoices.INCOME,
        ChartDefaultLocationScope.ALL,
    ): [
        "Nominal Disposable Household Income",
        "Real Disposable Household Income",
    ],
    (
        EconomicDataCategoryChoices.HOUSEHOLD,
        EconomicDataSubcategoryChoices.HOUSING,
        ChartDefaultLocationScope.ALL,
    ): [
        "Home Prices",
        "Home Prices (Detached houses)",
    ],
    (
        EconomicDataCategoryChoices.HOUSEHOLD,
        EconomicDataSubcategoryChoices.CONFIDENCE,
        ChartDefaultLocationScope.ALL,
    ): [
        "Michigan Consumer Sentiment",
        "Consumer Confidence",
        "Employment Confidence",
    ],
    (
        EconomicDataCategoryChoices.BUSINESS,
        EconomicDataSubcategoryChoices.INCOME,
        ChartDefaultLocationScope.ALL,
    ): ["Net Operating Surplus"],
    (
        EconomicDataCategoryChoices.BUSINESS,
        EconomicDataSubcategoryChoices.INVESTMENT,
        ChartDefaultLocationScope.ALL,
    ): ["Corporate Gross Fixed Capital Formation"],
    (
        EconomicDataCategoryChoices.BUSINESS,
        EconomicDataSubcategoryChoices.COST,
        ChartDefaultLocationScope.ALL,
    ): ["Labour Cost Index"],
    (
        EconomicDataCategoryChoices.BUSINESS,
        EconomicDataSubcategoryChoices.DEBT,
        ChartDefaultLocationScope.ALL,
    ): ["Corporate Debt"],
    (
        EconomicDataCategoryChoices.BUSINESS,
        EconomicDataSubcategoryChoices.PRICES,
        ChartDefaultLocationScope.ALL,
    ): ["Manufacturing Producer Price Index"],
    (
        EconomicDataCategoryChoices.BUSINESS,
        EconomicDataSubcategoryChoices.PRODUCTION,
        ChartDefaultLocationScope.ALL,
    ): ["Industrial Production"],
    (
        EconomicDataCategoryChoices.BUSINESS,
        EconomicDataSubcategoryChoices.CONFIDENCE,
        EconomicDataLocationChoices.US,
    ): ["CEO Confidence"],
    (
        EconomicDataCategoryChoices.BUSINESS,
        EconomicDataSubcategoryChoices.CONFIDENCE,
        EconomicDataLocationChoices.FR,
    ): ["Aggregate Business Confidence"],
    (
        EconomicDataCategoryChoices.BUSINESS,
        EconomicDataSubcategoryChoices.CONFIDENCE,
        EconomicDataLocationChoices.JP,
    ): ["Tankan Large Manufacturing DI"],
    (
        EconomicDataCategoryChoices.GOVERNMENT,
        EconomicDataSubcategoryChoices.BUDGET,
        ChartDefaultLocationScope.ALL,
    ): ["Government Budget Balance"],
    (
        EconomicDataCategoryChoices.GOVERNMENT,
        EconomicDataSubcategoryChoices.DEBT,
        ChartDefaultLocationScope.ALL,
    ): ["Government Debt"],
    (
        EconomicDataCategoryChoices.GOVERNMENT,
        EconomicDataSubcategoryChoices.FINANCING,
        ChartDefaultLocationScope.ALL,
    ): [
        "Government Financing Account",
        "Net Debt Securities",
    ],
}

# ---------------------------------------------------------------------------
# Economic charts — Cross-Region
# ---------------------------------------------------------------------------

# Display label for the multi-country charts region (not a database location).
ECONOMIC_CHARTS_CROSS_REGION_LABEL = "Cross-Region"


class CrossRegionInfoGroup(str, Enum):
    """Sections of a Cross-Region info note."""

    CORE = "core"
    EU = "eu"


# Location → display label within each Cross-Region info section.
# Core lines use US / FR / JP; the EU line summarizes Germany, Spain, and Italy.
CROSS_REGION_INFO_LABEL_BY_LOCATION_BY_GROUP: dict[
    CrossRegionInfoGroup, dict[EconomicDataLocationChoices, str]
] = {
    CrossRegionInfoGroup.CORE: {
        EconomicDataLocationChoices.US: "United States",
        EconomicDataLocationChoices.FR: "France",
        EconomicDataLocationChoices.JP: "Japan",
    },
    CrossRegionInfoGroup.EU: {
        EconomicDataLocationChoices.DE: "Germany",
        EconomicDataLocationChoices.ES: "Spain",
        EconomicDataLocationChoices.IT: "Italy",
    },
}

# Countries plotted on Cross-Region charts (core countries, then EU members).
ECONOMIC_CHARTS_CROSS_REGION_LOCATIONS: list[EconomicDataLocationChoices] = [
    *CROSS_REGION_INFO_LABEL_BY_LOCATION_BY_GROUP[CrossRegionInfoGroup.CORE],
    *CROSS_REGION_INFO_LABEL_BY_LOCATION_BY_GROUP[CrossRegionInfoGroup.EU],
]


class CrossRegionTimeSeriesAlignment(str, Enum):
    """How Cross-Region line charts align time series with mismatched cadences."""

    MEAN = "mean"
    LINEAR_INTERPOLATION = "linear_interpolation"


# How to align mismatched publication cadences for Cross-Region line charts.
# Mean: average monthly prints into quarter means (US household saving /
# consumption levels and ratios vs European / Japanese quarterly). For SAAR
# monthly flows (PMSAVE / PCE), the quarter mean stays a SAAR; for ratios, it
# is the mean of the monthly rates in that quarter. Linear interpolation:
# stretch lower-frequency prints onto a monthly timeline (e.g. employment).
CROSS_REGION_TIME_SERIES_ALIGNMENT_FOR_LINE_CHART_COMPARISON: dict[
    str, CrossRegionTimeSeriesAlignment
] = {
    "Household Saving Ratio": CrossRegionTimeSeriesAlignment.MEAN,
    "Household Consumption Ratio": CrossRegionTimeSeriesAlignment.MEAN,
    "Nominal Household Saving": CrossRegionTimeSeriesAlignment.MEAN,
    "Nominal Household Consumption": CrossRegionTimeSeriesAlignment.MEAN,
    "Home Prices": CrossRegionTimeSeriesAlignment.MEAN,
    "Employment Level": CrossRegionTimeSeriesAlignment.LINEAR_INTERPOLATION,
}

# When a location has several indicators for one series label, Cross-Region line
# charts use this full name so countries compare like-to-like (France's hidden
# monthly Eurostat unemployment with the other countries' monthly).
CROSS_REGION_PREFERRED_INDICATORS_FOR_LINE_CHART_COMPARISON: dict[
    tuple[
        EconomicDataLocationChoices,
        EconomicDataCategoryChoices,
        EconomicDataSubcategoryChoices,
    ],
    str,
] = {
    (
        EconomicDataLocationChoices.FR,
        EconomicDataCategoryChoices.HOUSEHOLD,
        EconomicDataSubcategoryChoices.LABOUR,
    ): "Eurostat Monthly Unemployment Rate",
}

# Hover warnings shown left of the chart info button. Keys are series labels;
# values explain why cross-country levels are hard to compare.
CROSS_REGION_COMPARABILITY_WARNING_BY_SERIES_LABEL: dict[str, str] = {
    "Gini Index (Revenue)": (
        "These Gini scores do not measure the same income concept. Europe "
        "uses equivalised disposable income per person; the United States "
        "uses household money income (not equivalised); Japan builds an "
        "approximation from equal-sized household income bands. A higher "
        "reading in one country is only a rough signal versus another."
    ),
    "Palma Ratio (Revenue)": (
        "The Palma ratio is top 10% income over bottom 40%, but the income "
        "base differs: Europe uses equivalised disposable income per "
        "person; the United States uses household money income (not "
        "equivalised); Japan uses mean yearly income of equal household "
        "bands. Do not read level gaps as like-for-like inequality."
    ),
    "Gini Index (Wealth)": (
        "These wealth Gini scores are not on the same wealth concept. "
        "Euro-area countries use ECB Distributional Wealth Accounts "
        "adjusted net household wealth; the United States and Japan use "
        "WID net personal wealth. Do not read level gaps as like-for-like."
    ),
    "Top-10 Wealth Share": (
        "Top-10 wealth shares mix household and personal wealth concepts. "
        "Euro-area countries use ECB Distributional Wealth Accounts "
        "household net wealth; the United States and Japan use WID net "
        "personal wealth. Treat cross-country level gaps with care."
    ),
    "Household Saving Ratio": (
        "Saving rates look similar as percentages, but numerators and "
        "denominators are not aligned. Europe uses household gross saving "
        "over disposable income adjusted for pension entitlements; the "
        "United States uses personal saving over disposable personal "
        "income (monthly rates are averaged into quarters here); Japan "
        "uses household saving over disposable household income. Treat "
        "level gaps with care."
    ),
    "Household Debt Ratio": (
        "Debt-to-income ratios share a name, not a balance-sheet "
        "definition. Europe and the euro area use ECB household + NPISH "
        "loan stock over annualised disposable income; the United States "
        "uses household liabilities over disposable personal income; "
        "Japan uses household loans over disposable household income. "
        "Who counts as a household also differs."
    ),
    "Household Consumption Ratio": (
        "Consumption-to-income ratios are not on a common income concept. "
        "Europe uses household final consumption over disposable income "
        "adjusted for pension entitlements; the United States uses "
        "personal consumption over disposable personal income (monthly "
        "rates averaged into quarters here); Japan uses household "
        "consumption over disposable household income."
    ),
    "Nominal Household Saving": (
        "Dollar / euro / yen levels are not comparable, and the time "
        "basis differs too: United States monthly SAAR prints are "
        "averaged into quarters for this overlay; Europe shows a "
        "seasonally adjusted period flow (not annualised); Japan shows "
        "a quarterly SAAR. Prefer growth rates over absolute levels."
    ),
    "Nominal Household Consumption": (
        "Absolute consumption levels are not comparable across "
        "currencies, and annualisation differs: United States monthly "
        "SAAR PCE is averaged into quarters here; France uses an INSEE "
        "period flow while other European countries use Eurostat P.31 "
        "period flows; Japan shows a quarterly SAAR. Prefer growth "
        "rates over levels."
    ),
    "Employment Level": (
        "Headcount concepts and frequencies differ. United States and "
        "Japan print monthly labour-force employment; France uses "
        "quarterly LFS employment and Germany / Spain / Italy use "
        "quarterly national-accounts employment — both European series "
        "are linearly interpolated to monthly for this overlay, so "
        "in-between months are not official prints."
    ),
    "Annual Government Expenditures": (
        "The United States total is current expenditures only (gross "
        "investment excluded), so it is narrower than France and Japan "
        "total outlays. US spending-function names also differ from "
        "COFOG labels used for France and Japan. Do not compare levels "
        "or function shares as if the perimeter matched."
    ),
    "Labour Cost Index": (
        "These are different labour-cost baskets and base years. Europe "
        "(and France's INSEE twin) track hourly labour costs with base "
        "2020 = 100; the United States tracks private-industry total "
        "compensation with base December 2005 = 100; Japan has no "
        "comparable quarterly series here. Prefer YoY — raw index "
        "levels are not comparable."
    ),
    "Manufacturing Producer Price Index": (
        "Producer-price indexes do not share a base year or exact "
        "basket: the United States is rebased to 1984 = 100; Europe "
        "uses 2021 = 100; Japan uses 2020 = 100. Prefer YoY — raw "
        "levels are not comparable."
    ),
    "Output Gap": (
        "Every line is an OECD Economic Outlook GAP estimate "
        "((Y − Y*) / Y*), but vintage, revisions, and country detail "
        "in the production-function setup can still differ. Treat "
        "level comparisons cautiously."
    ),
    "Home Prices": (
        "Housing coverage is not the same product. France uses the "
        "Notaires-INSEE second-hand dwellings index; Germany, Spain, and "
        "Italy use Eurostat's existing-dwellings house price index; Japan "
        "is condominiums only, with monthly prints averaged into quarters "
        "for this overlay; the United States FHFA index covers "
        "single-family homes with conforming mortgages (Fannie/Freddie), "
        "not the full stock. Base years also differ — prefer YoY."
    ),
}

# Optional Cross-Region 'i' overrides (US / FR / JP / EU). Series labels absent here get
# the same layout built from each country's seeded description at dropdown time.
CROSS_REGION_INFO_DESCRIPTION_BY_SERIES_LABEL: dict[str, str] = {
    "Gini Index (Revenue)": (
        "US: ACS household money income Gini (not equivalised), stored "
        "×100.\n"
        "FR: Eurostat EU-SILC equivalised disposable income per person "
        "(0–100).\n"
        "JP: FIES equal-decile yearly household income (derived), stored "
        "×100.\n"
        "EU: Germany, Spain, and Italy use the same Eurostat EU-SILC "
        "series as France."
    ),
    "Palma Ratio (Revenue)": (
        "US: ACS PUMS top 10% / bottom 40% of household money income "
        "(not equivalised).\n"
        "FR: Eurostat EU-SILC D10 / (D1+D2+D3+D4) on equivalised "
        "disposable income per person.\n"
        "JP: FIES equal-decile means — top band over the bottom four "
        "(m10 / (m1+…+m4)).\n"
        "EU: Germany, Spain, and Italy use the same Eurostat EU-SILC "
        "derivation as France."
    ),
    "Gini Index (Wealth)": (
        "US / JP: WID net personal wealth Gini (ghweal992j), stored "
        "×100.\n"
        "FR / DE / ES / IT: ECB DWA adjusted net household wealth Gini "
        "(annual Q4 observation, 0–100)."
    ),
    "Top-10 Wealth Share": (
        "US / JP: WID top 10% net personal wealth share "
        "(shweal992j p90p100), stored ×100.\n"
        "FR / DE / ES / IT: ECB DWA top 10% household net wealth share "
        "(annual Q4 observation, percent)."
    ),
    "Household Saving Ratio": (
        "US: Personal saving / disposable personal income (monthly "
        "rates averaged into quarters for this overlay).\n"
        "FR: Eurostat B8G / (B6G + D8) × 100 (household gross saving "
        "over disposable income adjusted for pension entitlements).\n"
        "JP: Household saving / disposable household income (Cabinet "
        "Office kakei).\n"
        "EU: Germany, Spain, Italy, and the euro area use the same "
        "Eurostat household concept as France."
    ),
    "Household Debt Ratio": (
        "US: Household liabilities / disposable personal income.\n"
        "FR: ECB QSA household + NPISH loans / annualised disposable "
        "income.\n"
        "JP: Household loans / disposable household income (BoJ / "
        "kakei).\n"
        "EU: Germany, Spain, Italy, and the euro area use the same ECB "
        "QSA loans-to-income concept as France."
    ),
    "Household Consumption Ratio": (
        "US: Personal consumption / disposable personal income (monthly "
        "rates averaged into quarters for this overlay).\n"
        "FR: Eurostat P.31 / (B6G + D8) × 100 (household final "
        "consumption over disposable income adjusted for pension "
        "entitlements).\n"
        "JP: Household consumption / disposable household income "
        "(Cabinet Office kakei).\n"
        "EU: Germany, Spain, and Italy use the same Eurostat household "
        "concept as France."
    ),
    "Nominal Household Saving": (
        "US: Monthly SAAR personal saving; averaged into quarters for "
        "this overlay.\n"
        "FR: Eurostat quarterly SA period flow (gross saving B8G; not "
        "annualised).\n"
        "JP: Quarterly SAAR household saving (Cabinet Office kakei).\n"
        "EU: Germany, Spain, and Italy use the same Eurostat B8G period "
        "flow as France."
    ),
    "Nominal Household Consumption": (
        "US: Monthly SAAR PCE; averaged into quarters for this overlay.\n"
        "FR: INSEE quarterly household final consumption (current "
        "prices; period flow).\n"
        "JP: Quarterly SAAR household consumption (Cabinet Office "
        "kakei).\n"
        "EU: Germany, Spain, and Italy use Eurostat P.31 period flow "
        "(not the INSEE series used for France)."
    ),
    "Employment Level": (
        "US: Monthly CPS employment level.\n"
        "FR: Quarterly Eurostat LFS employment; linearly interpolated "
        "to monthly for this overlay (interpolated months are not "
        "official prints).\n"
        "JP: Monthly employed persons (Labour Force Survey).\n"
        "EU: Germany, Spain, and Italy use quarterly national-accounts "
        "employment (namq_10_pe), also interpolated to monthly — a "
        "different Eurostat concept from France's LFS series."
    ),
    "Annual Government Expenditures": (
        "US: BEA current expenditures only (gross investment excluded); "
        "US function names, not COFOG.\n"
        "FR: Eurostat annual COFOG total outlays (gov_10a_exp).\n"
        "JP: ESRI annual COFOG total outlays (fiscal-year tables).\n"
        "EU: Not on this Cross-Region overlay (no DE/ES/IT series)."
    ),
    "Labour Cost Index": (
        "US: ECI private-industry total compensation (base Dec 2005 = "
        "100).\n"
        "FR: INSEE hourly labour costs B–N (base 2020 = 100).\n"
        "JP: No comparable quarterly labour-cost index (stub / no "
        "data).\n"
        "EU: Germany, Spain, and Italy use Eurostat hourly LCI (base "
        "2020 = 100) — not the INSEE series used for France."
    ),
    "Manufacturing Producer Price Index": (
        "US: PPI total manufacturing (base 1984 = 100).\n"
        "FR: Eurostat domestic PPI industry excl. construction "
        "(base 2021 = 100).\n"
        "JP: BoJ CGPI all commodities (base 2020 = 100).\n"
        "EU: Germany, Spain, and Italy use the same Eurostat domestic "
        "PPI family as France."
    ),
    "Output Gap": (
        "US: OECD Economic Outlook GAP = (Y − Y*) / Y* (% of potential "
        "GDP).\n"
        "FR: Same OECD GAP measure.\n"
        "JP: Same OECD GAP measure.\n"
        "EU: Germany, Spain, and Italy use the same OECD GAP measure."
    ),
    "Home Prices": (
        "US: FHFA all-transactions index for single-family homes with "
        "conforming mortgages (Fannie/Freddie), not the full housing "
        "stock (base 1980 = 100).\n"
        "FR: Notaires-INSEE second-hand dwellings index, seasonally "
        "adjusted (France excluding Mayotte; base 2015 = 100).\n"
        "JP: MLIT condominiums only (RPPI); monthly prints are averaged "
        "into quarters for this overlay (base 2010 = 100).\n"
        "EU: Germany, Spain, and Italy use Eurostat's existing-dwellings "
        "house price index (new dwellings excluded; base 2015 = 100)."
    ),
}

# ---------------------------------------------------------------------------
# Market recap
# ---------------------------------------------------------------------------


class MarketRecapLocationEnum(str, Enum):
    """Geographic buckets for the market-recap price table only."""

    NA = "North America"
    EU = "Europe"
    ASIA = "Asia"
    NO_LOCATION = "No Location"


# Market locations that belong to each geographic group.
MARKET_RECAP_LOCATIONS_BY_GROUP: dict[
    MarketRecapLocationEnum, list[LocationChoices]
] = {
    MarketRecapLocationEnum.NA: [LocationChoices.US],
    MarketRecapLocationEnum.EU: [
        LocationChoices.EU,
        LocationChoices.DE,
        LocationChoices.FR,
    ],
    MarketRecapLocationEnum.ASIA: [LocationChoices.JP],
    MarketRecapLocationEnum.NO_LOCATION: [],
}

# ---------------------------------------------------------------------------
# FX matrix
# ---------------------------------------------------------------------------

# Cross pairs to show and currency column order for the FX strength matrix.
FX_PAIRS_FILTER: list[str] = [
    "EURGBP",
    "EURCHF",
    "EURAUD",
    "EURCNY",
    "GBPJPY",
    "GBPCHF",
    "GBPAUD",
    "GBPCNY",
    "JPYCHF",
    "JPYAUD",
    "JPYCNY",
    "CHFAUD",
    "CHFCNY",
    "AUDCNY",
]
FX_MATRIX_ORDER: list[str] = ["EUR", "USD", "GBP", "JPY", "CHF", "AUD", "CNY"]

# ---------------------------------------------------------------------------
# Sector analysis
# ---------------------------------------------------------------------------

# Cover trailing Month plus full calendar YTD through a late-year as-of date.
SECTOR_ANALYSIS_HISTORY_CALENDAR_DAYS = 400
