const economicRecapSectionsSource = window.economicRecapDataJSON || [];
const economicRecapLocations = window.economicRecapLocationsJSON || [];
const economicRecapNominalGdpSource = window.economicRecapNominalGdpJSON || [];
const economicRecapAsOfInitial = window.economicRecapAsOfJSON || {};
const ECONOMIC_RECAP_QUARTER_END_MONTH_BY_QUARTER =
  economicRecapAsOfInitial.quarter_end_month_by_quarter || {
    1: 3,
    2: 6,
    3: 9,
    4: 12,
  };

/**
 * Full series stay active; As-of / Comparison window math filters per row.
 * '*Source' aliases are kept so refresh paths can reset without re-fetching.
 */
let economicRecapSections = economicRecapSectionsSource;
let economicRecapNominalGdp = economicRecapNominalGdpSource;

const COMPARISON_LATEST = "Latest";
const COMPARISON_YEAR = "Year";
const COMPARISON_QUARTER = "Quarter";

/**
 * As-of toolbar state. 'month' is only set for an explicit month As-of
 * (year-only / quarter leave month empty so the Month dropdown stays at —).
 */
let economicRecapAsOfState = {
  year: economicRecapAsOfInitial.year ?? null,
  quarter: economicRecapAsOfInitial.quarter ?? null,
  month: economicRecapAsOfInitial.month ?? null,
  monthDisplay: economicRecapAsOfInitial.month_display ?? null,
  endDate: economicRecapAsOfInitial.end_date ?? null,
};

let economicRecapComparisonState =
  economicRecapAsOfInitial.comparison || COMPARISON_LATEST;

function getMonthEndIsoDate(year, month) {
  /** Last calendar day of 'year'-'month' as YYYY-MM-DD (UTC date parts). */
  const endDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const monthText = String(month).padStart(2, "0");
  const dayText = String(endDay).padStart(2, "0");
  return `${year}-${monthText}-${dayText}`;
}

function getMonthStartIsoDate(year, month) {
  /** First calendar day of 'year'-'month' as YYYY-MM-DD. */
  const monthText = String(month).padStart(2, "0");
  return `${year}-${monthText}-01`;
}

function getAsOfEndDate(year, quarter, month) {
  if (year == null) {
    return null;
  }
  if (month != null) {
    return getMonthEndIsoDate(year, month);
  }
  if (quarter != null) {
    return getMonthEndIsoDate(
      year,
      ECONOMIC_RECAP_QUARTER_END_MONTH_BY_QUARTER[quarter]
    );
  }
  return getMonthEndIsoDate(year, 12);
}

function formatAsOfMonthDisplay(_year, _quarter, month) {
  /** Month dropdown only mirrors an explicit month As-of. */
  return month != null ? month : null;
}

function getDefaultComparisonForAsOf(year, quarter, month) {
  if (year == null) {
    return COMPARISON_LATEST;
  }
  if (month != null) {
    return COMPARISON_LATEST;
  }
  if (quarter != null) {
    return COMPARISON_QUARTER;
  }
  return COMPARISON_YEAR;
}

function normalizeComparisonForAsOf(comparison, year, quarter, month) {
  const allowed = new Set([
    COMPARISON_LATEST,
    COMPARISON_YEAR,
    COMPARISON_QUARTER,
  ]);
  let nextComparison = allowed.has(comparison)
    ? comparison
    : getDefaultComparisonForAsOf(year, quarter, month);
  // Year-only As-of cannot use Comparison=Quarter (non-calendar year shift).
  if (
    nextComparison === COMPARISON_QUARTER &&
    year != null &&
    quarter == null &&
    month == null
  ) {
    return COMPARISON_YEAR;
  }
  return nextComparison;
}

function doesModeOwnLookback() {
  return (
    economicRecapAsOfState.year == null &&
    economicRecapComparisonState === COMPARISON_LATEST
  );
}

function applyEconomicRecapAsOfFilter() {
  /** Keep full series; window helpers filter per indicator. */
  economicRecapSections = economicRecapSectionsSource;
  economicRecapNominalGdp = economicRecapNominalGdpSource;
}

function getAsOfWindowBounds(year, quarter, month, frequency) {
  /**
   * Inclusive [start, end] ISO dates for the Current window. Annual frequency
   * ignores quarter/month (full calendar year of the selected year).
   */
  if (year == null) {
    return null;
  }
  const frequencyUpper = String(frequency || "").toUpperCase();
  if (frequencyUpper === "ANNUAL") {
    return {
      startDate: getMonthStartIsoDate(year, 1),
      endDate: getMonthEndIsoDate(year, 12),
      kind: "year",
      year,
      quarter: null,
      month: null,
    };
  }
  if (month != null) {
    return {
      startDate: getMonthStartIsoDate(year, month),
      endDate: getMonthEndIsoDate(year, month),
      kind: "month",
      year,
      quarter: null,
      month,
    };
  }
  if (quarter != null) {
    const endMonth = ECONOMIC_RECAP_QUARTER_END_MONTH_BY_QUARTER[quarter];
    const startMonth = endMonth - 2;
    return {
      startDate: getMonthStartIsoDate(year, startMonth),
      endDate: getMonthEndIsoDate(year, endMonth),
      kind: "quarter",
      year,
      quarter,
      month: null,
    };
  }
  return {
    startDate: getMonthStartIsoDate(year, 1),
    endDate: getMonthEndIsoDate(year, 12),
    kind: "year",
    year,
    quarter: null,
    month: null,
  };
}

function doesWindowUseCanonicalBounds(windowBounds) {
  /**
   * True when start/end still match the full year / quarter / month template.
   * Clipped FLOW stacks (e.g. year through Q3 only) fail this check so shifts
   * keep the same partial span.
   */
  if (!windowBounds || windowBounds.year == null) {
    return false;
  }
  if (windowBounds.kind === "year") {
    return (
      windowBounds.startDate === getMonthStartIsoDate(windowBounds.year, 1) &&
      windowBounds.endDate === getMonthEndIsoDate(windowBounds.year, 12)
    );
  }
  if (windowBounds.kind === "quarter" && windowBounds.quarter != null) {
    const endMonth =
      ECONOMIC_RECAP_QUARTER_END_MONTH_BY_QUARTER[windowBounds.quarter];
    const startMonth = endMonth - 2;
    return (
      windowBounds.startDate ===
        getMonthStartIsoDate(windowBounds.year, startMonth) &&
      windowBounds.endDate === getMonthEndIsoDate(windowBounds.year, endMonth)
    );
  }
  if (windowBounds.kind === "month" && windowBounds.month != null) {
    return (
      windowBounds.startDate ===
        getMonthStartIsoDate(windowBounds.year, windowBounds.month) &&
      windowBounds.endDate ===
        getMonthEndIsoDate(windowBounds.year, windowBounds.month)
    );
  }
  return false;
}

function shiftClippedWindowBounds(windowBounds, months) {
  /** Shift a clipped window by moving its concrete start/end dates. */
  const shiftedStart = shiftPeriodDateMonths(windowBounds.startDate, months);
  const shiftedEnd = shiftPeriodDateMonths(windowBounds.endDate, months);
  if (!shiftedStart || !shiftedEnd) {
    return null;
  }
  const shiftedYear = Number(String(shiftedStart).slice(0, 4));
  const shiftedMonth = Number(String(shiftedStart).slice(5, 7));
  if (windowBounds.kind === "year") {
    return {
      ...windowBounds,
      startDate: shiftedStart,
      endDate: shiftedEnd,
      year: shiftedYear,
      quarter: null,
      month: null,
    };
  }
  if (windowBounds.kind === "quarter") {
    return {
      ...windowBounds,
      startDate: shiftedStart,
      endDate: shiftedEnd,
      year: shiftedYear,
      quarter: Math.floor((shiftedMonth - 1) / 3) + 1,
      month: null,
    };
  }
  return {
    ...windowBounds,
    startDate: shiftedStart,
    endDate: shiftedEnd,
    year: shiftedYear,
    quarter: null,
    month: shiftedMonth,
  };
}

function shiftAsOfWindowBounds(windowBounds, months) {
  /**
   * Shift a window by whole months. Canonical year/quarter/month windows use
   * field math so month-end dates do not spill; clipped FLOW stacks keep the
   * same partial start/end span (e.g. Q1–Q3 → prior Q1–Q3).
   */
  if (!windowBounds || months == null) {
    return null;
  }
  if (!doesWindowUseCanonicalBounds(windowBounds)) {
    return shiftClippedWindowBounds(windowBounds, months);
  }
  if (windowBounds.kind === "year" && windowBounds.year != null) {
    const shiftedYear = windowBounds.year - Math.trunc(months / 12);
    if (months % 12 !== 0) {
      return shiftClippedWindowBounds(windowBounds, months);
    }
    return getAsOfWindowBounds(shiftedYear, null, null, "ANNUAL");
  }
  if (windowBounds.kind === "quarter" && windowBounds.quarter != null) {
    const absoluteQuarter =
      windowBounds.year * 4 + (windowBounds.quarter - 1) - Math.trunc(months / 3);
    const shiftedYear = Math.floor(absoluteQuarter / 4);
    const shiftedQuarter = (absoluteQuarter % 4) + 1;
    return getAsOfWindowBounds(shiftedYear, shiftedQuarter, null, "QUARTERLY");
  }
  if (windowBounds.kind === "month" && windowBounds.month != null) {
    const absoluteMonth =
      windowBounds.year * 12 + (windowBounds.month - 1) - months;
    const shiftedYear = Math.floor(absoluteMonth / 12);
    const shiftedMonth = (absoluteMonth % 12) + 1;
    return getAsOfWindowBounds(shiftedYear, null, shiftedMonth, "MONTHLY");
  }
  return null;
}

function clipStackedWindowBoundsToAvailableData(record, windowBounds) {
  /**
   * End (and start) a FLOW stack at the prints actually present so Comparison /
   * Mode lookback cover the same span (2026 Q1–Q3 → 2025 Q1–Q3). Annual-
   * frequency prints already own the full period — leave them alone.
   */
  if (!record || !windowBounds || !doesMeasureStackInWindow(record.measure_type)) {
    return windowBounds;
  }
  if (String(record.frequency || "").toUpperCase() === "ANNUAL") {
    return windowBounds;
  }
  const points = filterTimeSeriesToWindow(record.time_series, windowBounds);
  if (points.length === 0) {
    return windowBounds;
  }
  // Chronological series: first / last points bound the owned stack span.
  const firstPoint = points[0];
  const latestPoint = points[points.length - 1];
  let startDate = windowBounds.startDate;
  let endDate = windowBounds.endDate;
  if (firstPoint.period_date && firstPoint.period_date > startDate) {
    startDate = firstPoint.period_date;
  }
  if (latestPoint.period_date && latestPoint.period_date < endDate) {
    endDate = latestPoint.period_date;
  }
  if (startDate === windowBounds.startDate && endDate === windowBounds.endDate) {
    return windowBounds;
  }
  return {
    ...windowBounds,
    startDate,
    endDate,
  };
}

function comparisonLookbackMonths(comparison, frequency) {
  const frequencyUpper = String(frequency || "").toUpperCase();
  if (comparison === COMPARISON_YEAR) {
    return 12;
  }
  if (comparison === COMPARISON_QUARTER) {
    if (frequencyUpper === "ANNUAL") {
      return null;
    }
    return 3;
  }
  return null;
}

function doesMeasureStackInWindow(measureType) {
  /** Only FLOW stacks inside an As-of window (calendar YTD). INDEX never sums. */
  return String(measureType || "").toUpperCase() === "FLOW";
}

function getFlowYtdAsOfWindowBounds(year, quarter, month, frequency) {
  /**
   * FLOW As-of window: always from 1 Jan of the selected year through the
   * as-of end (year / quarter / month). Annual frequency stays full year.
   */
  if (year == null) {
    return null;
  }
  const frequencyUpper = String(frequency || "").toUpperCase();
  if (frequencyUpper === "ANNUAL") {
    return getAsOfWindowBounds(year, null, null, frequency);
  }
  let endDate;
  if (month != null) {
    endDate = getMonthEndIsoDate(year, month);
  } else if (quarter != null) {
    const endMonth = ECONOMIC_RECAP_QUARTER_END_MONTH_BY_QUARTER[quarter];
    endDate = getMonthEndIsoDate(year, endMonth);
  } else {
    endDate = getMonthEndIsoDate(year, 12);
  }
  // kind 'year' so partial labels reuse '2025 (Q1 - Q3)' / '2025 (Jan - Sep)'.
  return {
    startDate: getMonthStartIsoDate(year, 1),
    endDate,
    kind: "year",
    year,
    quarter: null,
    month: null,
  };
}

function filterTimeSeriesToWindow(timeSeries, windowBounds) {
  if (!windowBounds) {
    return timeSeries || [];
  }
  return (timeSeries || []).filter(
    (point) =>
      point.period_date &&
      point.period_date >= windowBounds.startDate &&
      point.period_date <= windowBounds.endDate
  );
}

const MONTH_SHORT_LABEL_BY_NUMBER = {
  1: "Jan",
  2: "Feb",
  3: "Mar",
  4: "Apr",
  5: "May",
  6: "Jun",
  7: "Jul",
  8: "Aug",
  9: "Sep",
  10: "Oct",
  11: "Nov",
  12: "Dec",
};

function formatWindowPeriodLabel(windowBounds) {
  if (!windowBounds) {
    return null;
  }
  if (windowBounds.kind === "year") {
    return String(windowBounds.year);
  }
  if (windowBounds.kind === "quarter") {
    return `${windowBounds.year}Q${windowBounds.quarter}`;
  }
  if (windowBounds.kind === "month" && windowBounds.month != null) {
    const monthText = String(windowBounds.month).padStart(2, "0");
    return `${windowBounds.year}-${monthText}`;
  }
  return null;
}

function formatPartialStackedPeriodLabel(windowBounds, points, frequency) {
  /**
   * Incomplete FLOW stacks name the owned range (e.g. '2025 (Q1 - Q3)',
   * '2025 (Jan - Sep)'). Full coverage or annual prints keep the plain window
   * label so a complete year is not shown as Q1–Q4.
   */
  if (!windowBounds || !points || points.length === 0) {
    return formatWindowPeriodLabel(windowBounds);
  }
  // Chronological series: last point is the newest print in the window.
  const latestPoint = points[points.length - 1];
  const latestMonth = Number(String(latestPoint.period_date || "").slice(5, 7));
  if (!latestMonth) {
    return formatWindowPeriodLabel(windowBounds) || latestPoint.period;
  }
  const frequencyUpper = String(frequency || "").toUpperCase();
  if (windowBounds.kind === "year") {
    if (frequencyUpper === "ANNUAL") {
      return String(windowBounds.year);
    }
    if (frequencyUpper === "QUARTERLY") {
      const endQuarter = Math.floor((latestMonth - 1) / 3) + 1;
      if (endQuarter >= 4 && points.length >= 4) {
        return String(windowBounds.year);
      }
      return `${windowBounds.year} (Q1 - Q${endQuarter})`;
    }
    if (frequencyUpper === "MONTHLY") {
      if (latestMonth >= 12 && points.length >= 12) {
        return String(windowBounds.year);
      }
      const endMonthLabel = MONTH_SHORT_LABEL_BY_NUMBER[latestMonth];
      return `${windowBounds.year} (Jan - ${endMonthLabel})`;
    }
  }
  if (windowBounds.kind === "quarter" && frequencyUpper === "MONTHLY") {
    const startMonth = windowBounds.quarter * 3 - 2;
    const endMonth = windowBounds.quarter * 3;
    if (latestMonth >= endMonth && points.length >= 3) {
      return formatWindowPeriodLabel(windowBounds);
    }
    const startLabel = MONTH_SHORT_LABEL_BY_NUMBER[startMonth];
    const endLabel = MONTH_SHORT_LABEL_BY_NUMBER[latestMonth];
    return `${windowBounds.year}Q${windowBounds.quarter} (${startLabel} - ${endLabel})`;
  }
  return formatWindowPeriodLabel(windowBounds) || latestPoint.period;
}

function getLevelInWindow(record, windowBounds) {
  /**
   * FLOW → sum prints in the window (SAAR ÷4 first). Other measures → last
   * print in the window. Returns { value, period, period_date }.
   */
  if (!record || !windowBounds) {
    return { value: null, period: null, period_date: null };
  }
  const points = filterTimeSeriesToWindow(record.time_series, windowBounds);
  if (points.length === 0) {
    return { value: null, period: null, period_date: null };
  }
  // Chronological series: last point is the newest print in the window.
  const latestPoint = points[points.length - 1];
  if (doesMeasureStackInWindow(record.measure_type)) {
    const isAnnualized = Boolean(record.is_annualized);
    let total = 0;
    for (const point of points) {
      total += isAnnualized ? point.value / 4 : point.value;
    }
    return {
      value: total,
      period:
        formatPartialStackedPeriodLabel(
          windowBounds,
          points,
          record.frequency
        ) || latestPoint.period,
      period_date: latestPoint.period_date,
    };
  }
  return {
    value: latestPoint.value,
    period: formatWindowPeriodLabel(windowBounds) || latestPoint.period,
    period_date: latestPoint.period_date,
  };
}

function getVsGdpLevelInWindow(record, location, windowBounds) {
  /**
   * vsGDP for one As-of window: numerator and GDP use the same bounds.
   * PERCENT series pass through as a plain window level.
   */
  // 'PERCENT' matches ABS_UNIT_PERCENT (declared later with other unit constants).
  if ((record.base_unit || "") === "PERCENT") {
    return getLevelInWindow(record, windowBounds);
  }
  const gdpRecord = getGdpDenominatorRecord(record, location);
  if (!gdpRecord) {
    return { value: null, period: null, period_date: null };
  }
  const numerator = getLevelInWindow(record, windowBounds);
  const gdpLevel = getLevelInWindow(gdpRecord, windowBounds);
  if (numerator.value == null || gdpLevel.value == null || gdpLevel.value === 0) {
    return { value: null, period: numerator.period, period_date: numerator.period_date };
  }
  const outstandingUnit = record.base_unit || "";
  const gdpUnit = gdpRecord.base_unit || "";
  const outstandingIsStock = (record.measure_type || "") === "STOCK";
  const outstandingIsAnnualFrequency = (record.frequency || "") === "ANNUAL";
  const outstandingAnnualScale =
    Boolean(record.is_annualized) || outstandingIsAnnualFrequency;
  const gdpAnnualized = Boolean(gdpRecord.is_annualized);
  let outstandingValue = scaleValueToMagnitude(
    numerator.value,
    outstandingUnit,
    gdpUnit
  );
  let gdpValue = gdpLevel.value;
  // Window sums already converted SAAR→period; treat stacked FLOW as period-scale.
  const numeratorAlreadyPeriodScale =
    doesMeasureStackInWindow(record.measure_type) &&
    windowBounds.kind !== "month";
  if (outstandingIsStock) {
    if (!gdpAnnualized && windowBounds.kind === "quarter") {
      gdpValue *= 4;
    }
  } else if (
    !outstandingAnnualScale &&
    !numeratorAlreadyPeriodScale &&
    gdpAnnualized
  ) {
    outstandingValue *= 4;
  } else if (
    outstandingAnnualScale &&
    !gdpAnnualized &&
    windowBounds.kind === "quarter"
  ) {
    gdpValue *= 4;
  }
  return {
    value: (outstandingValue / gdpValue) * 100,
    period: numerator.period,
    period_date: numerator.period_date,
  };
}

function valuesFromOwnedWindows(currentLevel, previousLevel) {
  /**
   * Current and Previous are already Mode-transformed window values. Change is
   * always Current − Previous (level diff or pp).
   */
  const currVal = currentLevel.value;
  const prevVal = previousLevel.value;
  return {
    current: currVal,
    previous: prevVal,
    change: currVal != null && prevVal != null ? currVal - prevVal : null,
    period: currentLevel.period,
  };
}

function listPeriodDatesFromRecapSections(sections) {
  const periodDates = [];
  for (const categoryGroup of sections || []) {
    for (const subcategoryGroup of categoryGroup.subcategories || []) {
      for (const entry of subcategoryGroup.entries || []) {
        for (const point of entry.time_series || []) {
          if (point.period_date) {
            periodDates.push(point.period_date);
          }
        }
      }
    }
  }
  return periodDates;
}

function getAsOfAvailability(year) {
  const periodDates = listPeriodDatesFromRecapSections(
    economicRecapSectionsSource
  );
  const availableYears = new Set(
    periodDates
      .map((periodDate) => Number(String(periodDate).slice(0, 4)))
      .filter((periodYear) => Number.isFinite(periodYear))
  );
  if (year == null) {
    return {
      years: availableYears,
      quarters: new Set(),
      months: new Set(),
    };
  }
  const yearPeriodDates = periodDates.filter((periodDate) =>
    String(periodDate).startsWith(`${year}-`)
  );
  const availableMonths = new Set(
    yearPeriodDates
      .map((periodDate) => Number(String(periodDate).slice(5, 7)))
      .filter((periodMonth) => periodMonth >= 1 && periodMonth <= 12)
  );
  const availableQuarters = new Set(
    Array.from(availableMonths).map((periodMonth) =>
      Math.floor((periodMonth - 1) / 3) + 1
    )
  );
  return {
    years: availableYears,
    quarters: availableQuarters,
    months: availableMonths,
  };
}

applyEconomicRecapAsOfFilter();

const MODE_RAW = "Raw";
const MODE_MONTH = "MoM";
const MODE_QUARTER = "QoQ";
const MODE_ANNUALIZED_QUARTER = "QoQy";
const MODE_ANNUAL = "YoY";
const MODE_VS_GDP = "vsGDP";
const MODE_YTD_VS_GDP = "YTDvsGDP";
const MODE_YTD_RAW = "YTDRaw";
const MODE_YTD_YOY = "YTDYoY";
const MODE_REL_QOQ = "Rel QoQ";
const MODE_REL_YOY = "Rel YoY";
const MODE_CONTR_QOQ = "Contr QoQ";
const MODE_CONTR_YOY = "Contr YoY";
const MODE_YTD_REL_QOQ = "YTDRelQoQ";
const MODE_YTD_REL_YOY = "YTDRelYoY";
const MODE_YTD_CONTR_QOQ = "YTDContrQoQ";
const MODE_YTD_CONTR_YOY = "YTDContrYoY";

function mapFlowYtdModeToSamePeriodMode(mode) {
  /** Map explicit FLOW YTD modes onto the shared YTD same-period calculator. */
  if (mode === MODE_YTD_VS_GDP) {
    return MODE_VS_GDP;
  }
  if (mode === MODE_YTD_RAW) {
    return MODE_RAW;
  }
  if (mode === MODE_YTD_YOY) {
    return MODE_ANNUAL;
  }
  return mode;
}

function isFlowYtdMode(mode) {
  return (
    mode === MODE_YTD_VS_GDP ||
    mode === MODE_YTD_RAW ||
    mode === MODE_YTD_YOY
  );
}

function isYtdRelMode(mode) {
  return mode === MODE_YTD_REL_QOQ || mode === MODE_YTD_REL_YOY;
}

function isYtdContrMode(mode) {
  return mode === MODE_YTD_CONTR_QOQ || mode === MODE_YTD_CONTR_YOY;
}

const ABS_UNIT_INDEX = "INDEX";
const ABS_UNIT_PERCENT = "PERCENT";
const ABS_UNIT_PP = "PP";
const ABS_UNIT_SCALES = ["K", "M", "B", "T"];

/** Calendar months to subtract for MoM / QoQ / QoQy / YoY lookback. */
function lookbackMonthsForMode(frequency, mode) {
  if (
    mode === MODE_RAW ||
    mode === MODE_VS_GDP ||
    mode === MODE_YTD_RAW ||
    mode === MODE_YTD_VS_GDP
  ) {
    return 0;
  }
  if (mode === MODE_YTD_YOY) {
    return 12;
  }
  if (mode === MODE_MONTH) {
    return 1;
  }
  const freq = (frequency || "").toUpperCase();
  if (mode === MODE_QUARTER || mode === MODE_ANNUALIZED_QUARTER) {
    if (freq === "MONTHLY" || freq === "QUARTERLY") return 3;
    return 12; // ANNUAL: treat QoQ / QoQy like YoY
  }
  // YoY: same calendar month / quarter / year one year earlier.
  return 12;
}

/** Shift an ISO period date back by whole calendar months (UTC date parts). */
function shiftPeriodDateMonths(periodDateIso, months) {
  const [yearText, monthText, dayText] = String(periodDateIso).split("-");
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  if (!year || !month || !day) {
    return null;
  }
  const shifted = new Date(Date.UTC(year, month - 1 - months, day));
  const shiftedYear = shifted.getUTCFullYear();
  const shiftedMonth = String(shifted.getUTCMonth() + 1).padStart(2, "0");
  const shiftedDay = String(shifted.getUTCDate()).padStart(2, "0");
  return `${shiftedYear}-${shiftedMonth}-${shiftedDay}`;
}

function isRelMode(mode) {
  return (
    mode === MODE_REL_QOQ ||
    mode === MODE_REL_YOY ||
    isYtdRelMode(mode)
  );
}

function isContrMode(mode) {
  return (
    mode === MODE_CONTR_QOQ ||
    mode === MODE_CONTR_YOY ||
    isYtdContrMode(mode)
  );
}

function isComponentShareOrContributionMode(mode) {
  return isRelMode(mode) || isContrMode(mode);
}

/** Calendar months for Rel / Contr Previous (QoQ vs YoY). */
function componentComparisonLookbackMonths(frequency, mode) {
  if (
    mode === MODE_REL_YOY ||
    mode === MODE_CONTR_YOY ||
    mode === MODE_YTD_REL_YOY ||
    mode === MODE_YTD_CONTR_YOY
  ) {
    return lookbackMonthsForMode(frequency, MODE_ANNUAL);
  }
  return lookbackMonthsForMode(frequency, MODE_QUARTER);
}

function pctChange(curr, prev) {
  if (curr == null || prev == null || prev === 0) {
    return null;
  }
  return ((curr - prev) / prev) * 100;
}

/** Annualized QoQ: ((curr / prev) ** 4 - 1) * 100. */
function annualizedQoqPercent(curr, prev) {
  if (curr == null || prev == null || prev === 0) {
    return null;
  }
  const ratio = curr / prev;
  if (ratio <= 0) {
    return null;
  }
  return (ratio ** 4 - 1) * 100;
}

/** Space as thousands separator, e.g. 1234.56 → "1 234.56". */
function formatSpaced(value, digits) {
  const n = Number(value);
  if (Number.isNaN(n)) {
    return "—";
  }
  const sign = n < 0 ? "-" : "";
  const [intPart, decPart] = Math.abs(n).toFixed(digits).split(".");
  const spacedInt = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return decPart != null ? `${sign}${spacedInt}.${decPart}` : `${sign}${spacedInt}`;
}

/**
 * Scale amount so abs(value) <= 999, bumping K→M→B→T.
 */
function scaleAmountForDisplay(value, baseUnit, baseCurrency) {
  let magnitude = baseUnit;
  let scaled = Number(value);
  if (!ABS_UNIT_SCALES.includes(magnitude) || magnitude === "T") {
    return { value: scaled, magnitude, currency: baseCurrency || "" };
  }
  while (Math.abs(scaled) > 999) {
    const nextIndex = ABS_UNIT_SCALES.indexOf(magnitude) + 1;
    if (nextIndex <= 0 || nextIndex >= ABS_UNIT_SCALES.length) {
      break;
    }
    scaled /= 1000;
    magnitude = ABS_UNIT_SCALES[nextIndex];
  }
  return { value: scaled, magnitude, currency: baseCurrency || "" };
}

/** Convert an amount from 'fromUnit' into 'toMagnitude' (same scale ladder). */
function scaleValueToMagnitude(value, fromUnit, toMagnitude) {
  const fromIndex = ABS_UNIT_SCALES.indexOf(fromUnit);
  const toIndex = ABS_UNIT_SCALES.indexOf(toMagnitude);
  if (fromIndex < 0 || toIndex < 0) {
    return Number(value);
  }
  return Number(value) / 1000 ** (toIndex - fromIndex);
}

/**
 * One magnitude for Current / Previous / Change, driven by Current when present.
 */
function getSharedAmountMagnitude(values, baseUnit) {
  if (!ABS_UNIT_SCALES.includes(baseUnit) || baseUnit === "T") {
    return baseUnit;
  }
  const referenceValue =
    values.current != null
      ? values.current
      : values.previous != null
        ? values.previous
        : values.change;
  if (referenceValue == null) {
    return baseUnit;
  }
  return scaleAmountForDisplay(referenceValue, baseUnit, "").magnitude;
}

const CURRENCY_SYMBOL_BY_CODE = {
  USD: "$",
  EUR: "€",
  JPY: "¥",
};

function formatAmountUnitLabel(magnitude, currency) {
  const label = String(magnitude || "").toLowerCase();
  if (!currency) {
    return label;
  }
  const currencySymbol = CURRENCY_SYMBOL_BY_CODE[currency] || currency;
  return `${label}${currencySymbol}`;
}

function formatRawValue(value, record, sharedMagnitude) {
  /** Format a Raw (level) cell: amounts, %, or pp. */
  const unit = (record && record.base_unit) || "";
  const currency = (record && record.base_currency) || "";
  if (unit === ABS_UNIT_PP) {
    return `${formatSpaced(value, 2)} pp`;
  }
  if (unit === ABS_UNIT_PERCENT) {
    return `${formatSpaced(value, 2)} %`;
  }
  if (ABS_UNIT_SCALES.includes(unit) && unit !== "T") {
    const magnitude =
      sharedMagnitude || scaleAmountForDisplay(value, unit, currency).magnitude;
    const scaled = scaleValueToMagnitude(value, unit, magnitude);
    const unitLabel = formatAmountUnitLabel(magnitude, currency);
    return `${formatSpaced(scaled, 2)} ${unitLabel}`;
  }
  return formatSpaced(value, 2);
}

/**
 * Line title: Rel / Contr tags and index base year only. Percent and amount
 * units go on value cells, not in the name.
 */
function buildDisplayName(baseName, mode, locationRecords, comparisonParentName) {
  if (isRelMode(mode)) {
    const parentLabel = comparisonParentName || "parent";
    return `${baseName} (% of ${parentLabel})`;
  }
  if (
    isContrMode(mode) ||
    mode === MODE_MONTH ||
    mode === MODE_QUARTER ||
    mode === MODE_ANNUALIZED_QUARTER ||
    mode === MODE_ANNUAL ||
    mode === MODE_VS_GDP
  ) {
    return baseName;
  }
  const records = (locationRecords || []).filter(Boolean);
  if (records.length === 0) {
    return baseName;
  }

  const units = [...new Set(records.map((record) => record.base_unit || ""))];
  if (units.includes(ABS_UNIT_INDEX)) {
    const yearParts = records
      .filter((record) => record.base_year != null)
      .map((record) => ({ year: record.base_year, location: record.location }));
    if (yearParts.length === 0) {
      return baseName;
    }
    const uniqueYears = [...new Set(yearParts.map((part) => part.year))];
    if (uniqueYears.length === 1) {
      return `${baseName} (base year: ${uniqueYears[0]})`;
    }
    const joined = yearParts
      .map((part) => `${part.year} ${part.location}`)
      .join(" / ");
    return `${baseName} (base year: ${joined})`;
  }

  return baseName;
}

function valuesForLevelSeries(timeSeries, previousLag) {
  /**
   * Current / Previous from a chronological level series. 'previousLag' is how
   * many steps behind Current the Previous observation sits (1 = adjacent).
   */
  if (!timeSeries || timeSeries.length === 0) {
    return { current: null, previous: null, change: null, period: null };
  }
  const curr = timeSeries[timeSeries.length - 1];
  const previousIndex = timeSeries.length - 1 - previousLag;
  const prev = previousIndex >= 0 ? timeSeries[previousIndex] : null;
  const currVal = curr ? curr.value : null;
  const prevVal = prev ? prev.value : null;
  return {
    current: currVal,
    previous: prevVal,
    change: currVal != null && prevVal != null ? currVal - prevVal : null,
    period: curr ? curr.period : null,
  };
}

function valuesForLevelSeriesCalendar(timeSeries, lookbackMonths) {
  /**
   * Current / Previous from a chronological level series using calendar
   * lookback from Current's 'period_date' (not observation count).
   */
  if (!timeSeries || timeSeries.length === 0) {
    return { current: null, previous: null, change: null, period: null };
  }
  const curr = timeSeries[timeSeries.length - 1];
  const lookbackPeriodDate = shiftPeriodDateMonths(
    curr.period_date,
    lookbackMonths
  );
  const valueByPeriodDate = new Map(
    timeSeries.map((point) => [point.period_date, point])
  );
  const prev = lookbackPeriodDate
    ? valueByPeriodDate.get(lookbackPeriodDate)
    : null;
  const currVal = curr ? curr.value : null;
  const prevVal = prev ? prev.value : null;
  return {
    current: currVal,
    previous: prevVal,
    change: currVal != null && prevVal != null ? currVal - prevVal : null,
    period: curr ? curr.period : null,
  };
}

function valuesForMode(timeSeries, frequency, mode) {
  if (!timeSeries || timeSeries.length === 0) {
    return { current: null, previous: null, change: null, period: null };
  }
  if (mode === MODE_RAW || mode === MODE_VS_GDP) {
    return valuesForLevelSeries(timeSeries, 1);
  }

  const lookbackMonths = lookbackMonthsForMode(frequency, mode);
  const valueByPeriodDate = new Map(
    timeSeries.map((point) => [point.period_date, point])
  );
  const transformed = [];
  for (const curr of timeSeries) {
    const lookbackPeriodDate = shiftPeriodDateMonths(
      curr.period_date,
      lookbackMonths
    );
    if (!lookbackPeriodDate) {
      continue;
    }
    const prev = valueByPeriodDate.get(lookbackPeriodDate);
    if (!prev) {
      continue;
    }
    const chg =
      mode === MODE_ANNUALIZED_QUARTER
        ? annualizedQoqPercent(curr.value, prev.value)
        : pctChange(curr.value, prev.value);
    if (chg == null) {
      continue;
    }
    transformed.push({
      period: curr.period,
      period_date: curr.period_date,
      value: chg,
    });
  }
  if (transformed.length === 0) {
    return {
      current: null,
      previous: null,
      change: null,
      period: null,
    };
  }
  // Growth series is chronological; Current is the latest print, Previous the
  // prior growth observation (adjacent in the transformed series).
  return valuesForLevelSeries(transformed, 1);
}

function findRecord(indicatorName, category, location) {
  const section = economicRecapSections.find(
    (categoryGroup) => categoryGroup.category === category
  );
  if (!section) {
    return undefined;
  }
  for (const subcategoryGroup of section.subcategories || []) {
    const match = (subcategoryGroup.entries || []).find(
      (item) => item.name === indicatorName && item.location === location
    );
    if (match) {
      return match;
    }
  }
  return undefined;
}

function setCellText(cell, text, empty) {
  if (!cell) return;
  const span = cell.querySelector("span") || cell;
  span.classList.toggle("empty-data", empty);
  span.textContent = empty ? "—" : text;
}

function setChangeCell(cell, text, value, empty) {
  if (!cell) return;
  cell.classList.remove("table-change-positive", "table-change-negative");
  if (!empty && value != null && !Number.isNaN(value)) {
    if (value > 0) cell.classList.add("table-change-positive");
    if (value < 0) cell.classList.add("table-change-negative");
  }
  setCellText(cell, text, empty);
}

function formatCellValue(value, mode, record, sharedMagnitude) {
  if (value == null) {
    return "—";
  }
  if (mode === MODE_RAW) {
    return formatRawValue(value, record, sharedMagnitude);
  }
  // Growth modes and vsGDP both render as percent (pp change uses the same suffix).
  return `${formatSpaced(value, 2)} %`;
}

function getComparisonParentName(childRow) {
  /**
   * Parent used for Rel / Contr. Net Exports is special: nested Exports /
   * Imports always compare against Real GDP (the top parent).
   */
  const parentSeriesLabel = childRow.dataset.parentSeriesLabel || "";
  if (parentSeriesLabel === "Net Exports") {
    return "Real GDP";
  }
  return parentSeriesLabel;
}

const FIXED_YTD_VS_GDP_INDICATOR_NAMES = new Set([
  "Annual Government Expenditures",
]);

const FIXED_YTD_REL_YOY_INDICATOR_NAMES = new Set([
  "General Public Services",
  "Defence",
  "Public Order and Safety",
  "Economic Affairs",
  "Environmental Protection",
  "Housing and Community Amenities",
  "Health",
  "Recreation, Culture and Religion",
  "Education",
  "Social Protection",
  // US BEA NIPA Table 3.16 function names (no Environmental Protection).
  "General Public Service",
  "National Defense",
  "Housing and Community Services",
  "Recreation and Culture",
  "Income Security",
]);

function getFixedDisplayModeForIndicatorName(indicatorName) {
  /**
   * Return a locked mode when the line has no mode dropdown, else null.
   */
  const name = String(indicatorName || "");
  if (
    name === "Output Gap" ||
    name === "Estimated Annual GDP Growth" ||
    name === "Unemployment Rate" ||
    name === "INSEE Quarterly Unemployment Rate"
  ) {
    return MODE_RAW;
  }
  if (FIXED_YTD_VS_GDP_INDICATOR_NAMES.has(name)) {
    return MODE_YTD_VS_GDP;
  }
  if (FIXED_YTD_REL_YOY_INDICATOR_NAMES.has(name)) {
    return MODE_YTD_REL_YOY;
  }
  return null;
}

function findRealGdpRecord(location) {
  /** Real GDP sits under Growth — search every category for that location. */
  for (const section of economicRecapSections) {
    const match = findRecord("Real GDP", section.category, location);
    if (match) {
      return match;
    }
  }
  return undefined;
}

function getGdpDenominatorRecord(record, location) {
  /**
   * Pick Nominal or Real GDP so vsGDP / % of GDP stays price-basis matched.
   */
  if ((record.price_basis || "") === "REAL") {
    return findRealGdpRecord(location);
  }
  return findNominalGdpRecord(location);
}

function getVsGdpTimeSeries(record, location) {
  /**
   * vsGDP: outstanding / matching-price-basis GDP × 100. Series already stored
   * as PERCENT (e.g. IMF primary balance) pass through unchanged.
   */
  if ((record.base_unit || "") === ABS_UNIT_PERCENT) {
    return record.time_series || [];
  }
  const gdpRecord = getGdpDenominatorRecord(record, location);
  if (!gdpRecord || !record.time_series || !gdpRecord.time_series) {
    return [];
  }
  return buildPctOfGdpTimeSeries(record, gdpRecord);
}

/**
 * Sum quarterly / monthly GDP into one January-1 total per calendar year
 * ('average: true' returns the yearly mean instead, for SAAR levels).
 *
 * Returns chronological (oldest → newest) points so 'valuesForLevelSeries'
 * can take the last entry as Current — same convention as outstanding series.
 * Only complete years are kept (4 quarters or 12 months) so a partial trailing
 * year cannot become the denominator for an annual flow.
 */
function buildCalendarYearSumTimeSeries(timeSeries, { average = false } = {}) {
  // Usage of Map: calendar year → { period, period_date, value, observationCount }.
  const totalByYear = new Map();
  for (const point of timeSeries || []) {
    const year = Number(String(point.period_date || "").slice(0, 4));
    if (!Number.isFinite(year)) {
      continue;
    }
    const existing = totalByYear.get(year);
    if (existing) {
      existing.value += point.value;
      existing.observationCount += 1;
      continue;
    }
    totalByYear.set(year, {
      period: `${year}`,
      period_date: `${year}-01-01`,
      value: point.value,
      observationCount: 1,
    });
  }
  const observationCounts = Array.from(totalByYear.values()).map(
    (entry) => entry.observationCount
  );
  // Quarterly GDP → 4; monthly → 12. Mixed / empty → keep every year.
  const requiredObservations = observationCounts.includes(4)
    ? 4
    : observationCounts.includes(12)
      ? 12
      : null;
  return Array.from(totalByYear.values())
    .filter((entry) =>
      requiredObservations == null
        ? true
        : entry.observationCount >= requiredObservations
    )
    .map(({ period, period_date, value, observationCount }) => ({
      period,
      period_date,
      // Mean of a year's SAAR levels is that year's annual amount.
      value: average ? value / observationCount : value,
    }))
    .sort((left, right) =>
      left.period_date < right.period_date
        ? -1
        : left.period_date > right.period_date
          ? 1
          : 0
    );
}

/**
 * Build outstanding / GDP × 100, matching magnitude and annualization.
 *
 * Stocks (Government Debt, FX reserves, …) are end-of-period levels: never ×4
 * the stock. When GDP is a quarterly period sum, annualize the denominator
 * (×4) so the ratio is stock / annual GDP. Period-level flows still ×4 against
 * SAAR GDP (e.g. US BoP M$ vs GDP B$ SAAR). Eurostat BoP and namq Nominal GDP
 * are both M€ period levels for flows, so no extra step. JP Cabinet Office
 * flows and Nominal GDP are both annualized B¥. Annual-frequency flows match
 * calendar-year GDP (sum of that year's period levels, or mean of its SAAR
 * levels), not Q1×4 / Q1 SAAR.
 */
function buildPctOfGdpTimeSeries(outstandingRecord, gdpRecord) {
  const outstandingUnit = outstandingRecord.base_unit || "";
  const gdpUnit = gdpRecord.base_unit || "";
  const outstandingIsStock = (outstandingRecord.measure_type || "") === "STOCK";
  const outstandingIsAnnualFrequency =
    (outstandingRecord.frequency || "") === "ANNUAL";
  // Annual-frequency flows are already full-year totals (same scale as SAAR).
  const outstandingAnnualScale =
    Boolean(outstandingRecord.is_annualized) || outstandingIsAnnualFrequency;
  const gdpAnnualized = Boolean(gdpRecord.is_annualized);
  const useCalendarYearGdp =
    outstandingIsAnnualFrequency && !outstandingIsStock && !gdpAnnualized;
  // Annual flow vs SAAR GDP (US / JP): average that year's SAAR levels.
  const useCalendarYearAverageGdp =
    outstandingIsAnnualFrequency && !outstandingIsStock && gdpAnnualized;
  const gdpTimeSeries = useCalendarYearGdp
    ? buildCalendarYearSumTimeSeries(gdpRecord.time_series)
    : useCalendarYearAverageGdp
      ? buildCalendarYearSumTimeSeries(gdpRecord.time_series, { average: true })
      : gdpRecord.time_series;
  return alignTimeSeriesByPeriod(gdpTimeSeries, outstandingRecord.time_series)
    .map((point) => {
      if (point.parentValue === 0) {
        return null;
      }
      let outstandingValue = scaleValueToMagnitude(
        point.childValue,
        outstandingUnit,
        gdpUnit
      );
      let gdpValue = point.parentValue;
      if (outstandingIsStock) {
        // Stock / annual GDP. SAAR GDP is already annual; period GDP ×4.
        if (!gdpAnnualized) {
          gdpValue *= 4;
        }
      } else if (!outstandingAnnualScale && gdpAnnualized) {
        // Period-level flow vs SAAR GDP (e.g. US BoP M$ vs GDP B$ SAAR).
        outstandingValue *= 4;
      } else if (
        outstandingAnnualScale &&
        !gdpAnnualized &&
        !useCalendarYearGdp
      ) {
        gdpValue *= 4;
      }
      return {
        period: point.period,
        period_date: point.period_date,
        value: (outstandingValue / gdpValue) * 100,
      };
    })
    .filter(Boolean);
}

/** Calendar months between successive YTD steps for a publication frequency. */
function ytdStepMonthsForFrequency(frequency) {
  const freq = String(frequency || "").toUpperCase();
  if (freq === "MONTHLY") {
    return 1;
  }
  if (freq === "ANNUAL") {
    return 12;
  }
  return 3;
}

const YTD_MONTH_ABBREVS = [
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
];

/**
 * Running year-to-date sums of a chronological series.
 *
 * Quarterly: each point is Q1..Qn of its calendar year (e.g. 2025Q2 →
 * 25Q1 + 25Q2). Monthly: Jan..n of that year. A year only yields points while
 * periods are contiguous from period 1, so a gap cannot shrink the window and
 * skew the same-period comparison.
 */
function buildYearToDateCumulativeTimeSeries(timeSeries, frequency) {
  const stepMonths = ytdStepMonthsForFrequency(frequency);
  // Usage of Map: calendar year → { nextMonth, total } running state.
  const runningTotalByYear = new Map();
  const cumulativeSeries = [];
  const ordered = [...(timeSeries || [])].sort((left, right) =>
    String(left.period_date || "").localeCompare(String(right.period_date || ""))
  );
  for (const point of ordered) {
    const [yearText, monthText] = String(point.period_date || "").split("-");
    const year = Number(yearText);
    const month = Number(monthText);
    if (!year || !month) {
      continue;
    }
    const runningTotal = runningTotalByYear.get(year) || {
      nextMonth: 1,
      total: 0,
    };
    if (runningTotal.nextMonth == null || month !== runningTotal.nextMonth) {
      // Gap or missing period 1: stop this year so later periods are not summed.
      runningTotal.nextMonth = null;
      runningTotalByYear.set(year, runningTotal);
      continue;
    }
    runningTotal.total += point.value;
    const nextExpected = month + stepMonths;
    runningTotal.nextMonth = nextExpected <= 12 ? nextExpected : null;
    runningTotalByYear.set(year, runningTotal);
    cumulativeSeries.push({
      period: point.period,
      period_date: point.period_date,
      value: runningTotal.total,
    });
  }
  return cumulativeSeries;
}

function formatYtdPeriodLabel(periodDate, frequency) {
  /**
   * Label a YTD window from its ending period date. Complete year → '2025';
   * partial quarterly → '2025 (Q1 - Q3)'; partial monthly → '2025 (Jan - Sep)'.
   */
  const year = Number(String(periodDate || "").slice(0, 4));
  const month = Number(String(periodDate || "").slice(5, 7));
  if (!Number.isFinite(year) || year <= 0 || !month || month < 1 || month > 12) {
    return null;
  }
  const freq = String(frequency || "").toUpperCase();
  if (freq === "ANNUAL" || month === 12) {
    return String(year);
  }
  if (freq === "MONTHLY") {
    return `${year} (Jan - ${YTD_MONTH_ABBREVS[month - 1]})`;
  }
  const endQuarter = Math.floor((month - 1) / 3) + 1;
  if (endQuarter < 1 || endQuarter > 4) {
    return null;
  }
  if (endQuarter === 4) {
    return String(year);
  }
  return `${year} (Q1 - Q${endQuarter})`;
}

function valuesForYtdSamePeriodLevels(ytdSeries, frequency) {
  /**
   * Current = latest year-to-date level; Previous = the same window of the
   * prior year (same period one year earlier in the cumulative series).
   * Period names the YTD window, e.g. '2025 (Q1 - Q3)', not 25Q3 alone.
   */
  const values = valuesForLevelSeriesCalendar(ytdSeries, 12);
  if (!ytdSeries || ytdSeries.length === 0) {
    return values;
  }
  const latestYtdPoint = ytdSeries[ytdSeries.length - 1];
  return {
    ...values,
    period:
      formatYtdPeriodLabel(latestYtdPoint.period_date, frequency) ||
      values.period,
  };
}

function valuesForYtdSamePeriodYoy(timeSeries, frequency) {
  /**
   * Current = YoY of the latest year-to-date sum vs the same window one year
   * earlier; Previous = that prior-year window's YoY vs the year before;
   * Change = Current − Previous (pp).
   */
  const ytdSeries = buildYearToDateCumulativeTimeSeries(timeSeries, frequency);
  if (ytdSeries.length === 0) {
    return { current: null, previous: null, change: null, period: null };
  }
  const ytdByPeriodDate = new Map(
    ytdSeries.map((point) => [point.period_date, point])
  );
  const yoyForPeriodDate = (periodDate) => {
    const ytdPoint = ytdByPeriodDate.get(periodDate);
    const priorYearPeriodDate = shiftPeriodDateMonths(periodDate, 12);
    const priorYearPoint = priorYearPeriodDate
      ? ytdByPeriodDate.get(priorYearPeriodDate)
      : null;
    if (!ytdPoint || !priorYearPoint) {
      return null;
    }
    return pctChange(ytdPoint.value, priorYearPoint.value);
  };
  const latestYtdPoint = ytdSeries[ytdSeries.length - 1];
  const currentYoy = yoyForPeriodDate(latestYtdPoint.period_date);
  const priorYearPeriodDate = shiftPeriodDateMonths(
    latestYtdPoint.period_date,
    12
  );
  const previousYoy = priorYearPeriodDate
    ? yoyForPeriodDate(priorYearPeriodDate)
    : null;
  return {
    current: currentYoy,
    previous: previousYoy,
    change:
      currentYoy != null && previousYoy != null ? currentYoy - previousYoy : null,
    period:
      formatYtdPeriodLabel(latestYtdPoint.period_date, frequency) ||
      latestYtdPoint.period,
  };
}

function convertToPeriodLevelTimeSeries(timeSeries, isAnnualized) {
  /** Turn SAAR / annualized quarterly levels into one-quarter amounts (÷4). */
  if (!isAnnualized) {
    return timeSeries || [];
  }
  return (timeSeries || []).map((point) => ({
    period: point.period,
    period_date: point.period_date,
    value: point.value / 4,
  }));
}

function buildYtdPctOfGdpTimeSeries(record, location) {
  /**
   * Year-to-date flow / GDP over the same quarters × 100. Both sides are
   * first restricted to quarters present in each, so the windows match.
   */
  const gdpRecord = getGdpDenominatorRecord(record, location);
  if (!gdpRecord || !record.time_series || !gdpRecord.time_series) {
    return [];
  }
  const recordUnit = record.base_unit || "";
  const gdpUnit = gdpRecord.base_unit || "";
  const aligned = alignTimeSeriesByPeriod(
    convertToPeriodLevelTimeSeries(
      gdpRecord.time_series,
      Boolean(gdpRecord.is_annualized)
    ),
    convertToPeriodLevelTimeSeries(
      record.time_series,
      Boolean(record.is_annualized)
    )
  );
  const frequency = record.frequency;
  const ytdGdpSeries = buildYearToDateCumulativeTimeSeries(
    aligned.map((point) => ({
      period: point.period,
      period_date: point.period_date,
      value: point.parentValue,
    })),
    frequency
  );
  const ytdFlowSeries = buildYearToDateCumulativeTimeSeries(
    aligned.map((point) => ({
      period: point.period,
      period_date: point.period_date,
      value: scaleValueToMagnitude(point.childValue, recordUnit, gdpUnit),
    })),
    frequency
  );
  return buildShareTimeSeries(ytdGdpSeries, ytdFlowSeries);
}

function getRecordDisplayTimeSeries(record) {
  /** Stored period series (YTD transforms apply only for explicit YTD modes). */
  return (record && record.time_series) || [];
}

function buildYtdCumulativeSeriesForRecord(record) {
  /** Calendar YTD levels after SAAR→period conversion when needed. */
  return buildYearToDateCumulativeTimeSeries(
    convertToPeriodLevelTimeSeries(
      (record && record.time_series) || [],
      Boolean(record && record.is_annualized)
    ),
    record && record.frequency
  );
}

function valuesForYtdSamePeriodRecord(record, location, mode) {
  /**
   * Current / Previous / Change for a YTD-flagged record outside Rel / Contr:
   * Annual = YTD YoY; Raw / vsGDP = YTD level vs the prior-year same window;
   * other growth modes run on the YTD cumulative series.
   */
  const frequency = record.frequency;
  const periodLevelSeries = convertToPeriodLevelTimeSeries(
    record.time_series,
    Boolean(record.is_annualized)
  );
  if (mode === MODE_ANNUAL) {
    return valuesForYtdSamePeriodYoy(periodLevelSeries, frequency);
  }
  if (mode === MODE_RAW) {
    return valuesForYtdSamePeriodLevels(
      buildYearToDateCumulativeTimeSeries(periodLevelSeries, frequency),
      frequency
    );
  }
  if (mode === MODE_VS_GDP) {
    return valuesForYtdSamePeriodLevels(
      buildYtdPctOfGdpTimeSeries(record, location),
      frequency
    );
  }
  return valuesForMode(
    buildYearToDateCumulativeTimeSeries(periodLevelSeries, frequency),
    frequency,
    mode
  );
}

function getComponentRawTimeSeries(childRecord) {
  /** Component Raw / growth modes use the child's own outstanding series. */
  return getRecordDisplayTimeSeries(childRecord);
}

function buildComponentShareOrContributionValues(
  row,
  childRecord,
  location,
  mode
) {
  /**
   * Rel = child / parent share; Contr = contribution of child change to parent.
   * YTD Rel / Contr build calendar YTD on both legs first, then the same math.
   * QoQ / YoY pick the calendar lookback between Current and Previous (and
   * inside the Contr formula).
   */
  const category = row.dataset.category || "";
  let rawSeries = getComponentRawTimeSeries(childRecord);
  const parentName = getComparisonParentName(row);
  const parentRecord = findRecord(parentName, category, location);
  if (!parentRecord) {
    return { values: valuesForLevelSeries([], 1), formatMode: MODE_RAW };
  }
  let parentSeries = getRecordDisplayTimeSeries(parentRecord);
  if (isYtdRelMode(mode) || isYtdContrMode(mode)) {
    rawSeries = buildYearToDateCumulativeTimeSeries(
      convertToPeriodLevelTimeSeries(
        rawSeries,
        Boolean(childRecord.is_annualized)
      ),
      childRecord.frequency
    );
    parentSeries = buildYtdCumulativeSeriesForRecord(parentRecord);
  }
  const lookbackMonths = componentComparisonLookbackMonths(
    childRecord.frequency,
    mode
  );
  if (isRelMode(mode)) {
    const shareSeries = buildShareTimeSeries(parentSeries, rawSeries);
    return {
      values: valuesForLevelSeriesCalendar(shareSeries, lookbackMonths),
      formatMode: MODE_RAW,
      formatRecord: { base_unit: ABS_UNIT_PERCENT, base_currency: "" },
    };
  }
  const contributionSeries = buildContributionTimeSeries(
    parentSeries,
    rawSeries,
    lookbackMonths
  );
  return {
    values: valuesForLevelSeries(contributionSeries, 1),
    formatMode: MODE_RAW,
    formatRecord: { base_unit: ABS_UNIT_PP, base_currency: "" },
  };
}

function getWindowLevelForMode(record, location, mode, windowBounds) {
  /**
   * Mode transforms one As-of/Comparison window in place. Growth modes use
   * Mode lookback from that window (not the Comparison window), so Current
   * stays fixed when Comparison changes.
   */
  if (mode === MODE_VS_GDP || mode === MODE_YTD_VS_GDP) {
    // As-of FLOW windows are already calendar YTD, so YTDvsGDP shares vsGDP math.
    return getVsGdpLevelInWindow(record, location, windowBounds);
  }
  if (mode === MODE_YTD_RAW) {
    return getLevelInWindow(record, windowBounds);
  }
  if (mode === MODE_YTD_YOY) {
    mode = MODE_ANNUAL;
  }
  if (
    mode === MODE_MONTH ||
    mode === MODE_QUARTER ||
    mode === MODE_ANNUALIZED_QUARTER ||
    mode === MODE_ANNUAL
  ) {
    const currentLevel = getLevelInWindow(record, windowBounds);
    const lookbackMonths = lookbackMonthsForMode(record.frequency, mode);
    const lookbackBounds = shiftAsOfWindowBounds(windowBounds, lookbackMonths);
    const lookbackLevel = getLevelInWindow(record, lookbackBounds);
    const transformedValue =
      mode === MODE_ANNUALIZED_QUARTER
        ? annualizedQoqPercent(currentLevel.value, lookbackLevel.value)
        : pctChange(currentLevel.value, lookbackLevel.value);
    return {
      value: transformedValue,
      period: currentLevel.period,
      period_date: currentLevel.period_date,
    };
  }
  return getLevelInWindow(record, windowBounds);
}

function getComponentShareLevelInWindow(
  childRecord,
  parentRecord,
  windowBounds
) {
  const childLevel = getLevelInWindow(childRecord, windowBounds);
  const parentLevel = getLevelInWindow(parentRecord, windowBounds);
  if (
    childLevel.value == null ||
    parentLevel.value == null ||
    parentLevel.value === 0
  ) {
    return { value: null, period: childLevel.period, period_date: childLevel.period_date };
  }
  const childUnit = childRecord.base_unit || "";
  const parentUnit = parentRecord.base_unit || "";
  const scaledChild = scaleValueToMagnitude(
    childLevel.value,
    childUnit,
    parentUnit
  );
  return {
    value: (scaledChild / parentLevel.value) * 100,
    period: childLevel.period,
    period_date: childLevel.period_date,
  };
}

function getComponentContributionLevelInWindow(
  childRecord,
  parentRecord,
  currentBounds,
  previousBounds
) {
  const childCurrent = getLevelInWindow(childRecord, currentBounds);
  const childPrevious = getLevelInWindow(childRecord, previousBounds);
  const parentPrevious = getLevelInWindow(parentRecord, previousBounds);
  if (
    childCurrent.value == null ||
    childPrevious.value == null ||
    parentPrevious.value == null ||
    parentPrevious.value === 0
  ) {
    return {
      value: null,
      period: childCurrent.period,
      period_date: childCurrent.period_date,
    };
  }
  const childUnit = childRecord.base_unit || "";
  const parentUnit = parentRecord.base_unit || "";
  const childDelta =
    scaleValueToMagnitude(childCurrent.value, childUnit, parentUnit) -
    scaleValueToMagnitude(childPrevious.value, childUnit, parentUnit);
  return {
    value: (childDelta / Math.abs(parentPrevious.value)) * 100,
    period: childCurrent.period,
    period_date: childCurrent.period_date,
  };
}

function buildValuesForAsOfComparison(
  row,
  record,
  location,
  mode,
  isComponentChild
) {
  /**
   * As-of × Comparison own Current/Previous levels; Mode only formats them.
   * Latest As-of with Comparison Year/Quarter shifts from the latest print.
   */
  const frequency = record.frequency;
  let comparison = normalizeComparisonForAsOf(
    economicRecapComparisonState,
    economicRecapAsOfState.year,
    economicRecapAsOfState.quarter,
    economicRecapAsOfState.month
  );
  if (
    comparison === COMPARISON_QUARTER &&
    String(frequency || "").toUpperCase() === "ANNUAL"
  ) {
    comparison = COMPARISON_LATEST;
  }

  const isFlowMeasure = doesMeasureStackInWindow(record.measure_type);
  let currentBounds =
    isFlowMeasure && economicRecapAsOfState.year != null
      ? getFlowYtdAsOfWindowBounds(
        economicRecapAsOfState.year,
        economicRecapAsOfState.quarter,
        economicRecapAsOfState.month,
        frequency
      )
      : getAsOfWindowBounds(
        economicRecapAsOfState.year,
        economicRecapAsOfState.quarter,
        economicRecapAsOfState.month,
        frequency
      );

  // Latest As-of: pin Current to the latest print's native period window.
  // FLOW stays point-in-time here (dashboard), not calendar YTD.
  if (!currentBounds) {
    const series = record.time_series || [];
    if (series.length === 0) {
      return { current: null, previous: null, change: null, period: null };
    }
    // Chronological series: last point is the latest print.
    const latestPoint = series[series.length - 1];
    const periodDate = latestPoint.period_date;
    const year = Number(String(periodDate).slice(0, 4));
    const month = Number(String(periodDate).slice(5, 7));
    const frequencyUpper = String(frequency || "").toUpperCase();
    if (frequencyUpper === "ANNUAL") {
      currentBounds = getAsOfWindowBounds(year, null, null, frequency);
    } else if (frequencyUpper === "QUARTERLY") {
      const quarter = Math.floor((month - 1) / 3) + 1;
      currentBounds = getAsOfWindowBounds(year, quarter, null, frequency);
    } else {
      currentBounds = getAsOfWindowBounds(year, null, month, frequency);
    }
  }

  const workingRecord =
    isComponentChild
      ? {
        ...record,
        time_series: getComponentRawTimeSeries(record),
      }
      : record;

  // Clip stacked Current to prints that exist (Q1–Q3, not empty Q4) so
  // Comparison / Mode lookback shift the same span on Previous.
  currentBounds = clipStackedWindowBoundsToAvailableData(
    workingRecord,
    currentBounds
  );

  // FLOW with an explicit As-of year always compares to the same YTD prior year.
  // Other measures keep Comparison Year / Quarter / Latest lookbacks.
  const frequencyUpper = String(frequency || "").toUpperCase();
  const shiftMonths =
    isFlowMeasure && economicRecapAsOfState.year != null
      ? 12
      : comparison === COMPARISON_LATEST
        ? frequencyUpper === "MONTHLY"
          ? 1
          : frequencyUpper === "ANNUAL"
            ? 12
            : 3
        : comparisonLookbackMonths(comparison, frequency);
  const previousBounds = shiftAsOfWindowBounds(currentBounds, shiftMonths);

  if (
    isComponentChild &&
    isComponentShareOrContributionMode(mode)
  ) {
    const parentName = getComparisonParentName(row);
    const parentRecord = findRecord(
      parentName,
      row.dataset.category || "",
      location
    );
    if (!parentRecord) {
      return { current: null, previous: null, change: null, period: null };
    }
    if (isRelMode(mode)) {
      const currentLevel = getComponentShareLevelInWindow(
        record,
        parentRecord,
        currentBounds
      );
      const previousLevel = getComponentShareLevelInWindow(
        record,
        parentRecord,
        previousBounds
      );
      return valuesFromOwnedWindows(currentLevel, previousLevel);
    }
    // Contr Current = contribution over the Comparison horizon; Previous is
    // the contribution one Comparison step earlier.
    const previousPreviousBounds = shiftAsOfWindowBounds(
      previousBounds,
      shiftMonths
    );
    const currentLevel = getComponentContributionLevelInWindow(
      record,
      parentRecord,
      currentBounds,
      previousBounds
    );
    const previousLevel = getComponentContributionLevelInWindow(
      record,
      parentRecord,
      previousBounds,
      previousPreviousBounds
    );
    return valuesFromOwnedWindows(currentLevel, previousLevel);
  }

  const currentLevel = getWindowLevelForMode(
    workingRecord,
    location,
    mode,
    currentBounds
  );
  const previousLevel = getWindowLevelForMode(
    workingRecord,
    location,
    mode,
    previousBounds
  );
  return valuesFromOwnedWindows(currentLevel, previousLevel);
}

function updateRow(row, mode) {
  const indicatorName = row.dataset.indicatorName;
  const category = row.dataset.category;
  const isComponentChild = row.dataset.expansionRelation === "COMPONENT";
  const fixedMode = getFixedDisplayModeForIndicatorName(indicatorName);
  const nameCell = row.querySelector(".name-cell");
  const nameText = nameCell && nameCell.querySelector(".name-text");
  const baseName = (nameCell && nameCell.dataset.baseName) || indicatorName;
  const comparisonParentName =
    isComponentChild && fixedMode !== MODE_RAW
      ? getComparisonParentName(row)
      : "";
  const effectiveMode = fixedMode || mode;

  const locationRecords = economicRecapLocations
    .map((loc) => findRecord(indicatorName, category, loc))
    .filter(Boolean);

  const displayName = buildDisplayName(
    baseName,
    effectiveMode,
    locationRecords,
    comparisonParentName
  );
  if (nameText) {
    nameText.textContent = displayName;
  } else if (nameCell) {
    nameCell.textContent = displayName;
  }

  economicRecapLocations.forEach((location) => {
    const record = findRecord(indicatorName, category, location);
    const currCell = row.querySelector(`.loc-curr[data-location="${location}"]`);
    const prevCell = row.querySelector(`.loc-prev[data-location="${location}"]`);
    const chgCell = row.querySelector(`.loc-chg[data-location="${location}"]`);
    const periodCell = row.querySelector(
      `.loc-period[data-location="${location}"]`
    );

    if (!record) {
      setCellText(currCell, "—", true);
      setCellText(prevCell, "—", true);
      setChangeCell(chgCell, "—", null, true);
      if (periodCell) {
        setCellText(periodCell, "—", true);
      }
      return;
    }

    let values;
    let formatMode = effectiveMode;
    let formatRecord = record;
    const modeOwnsLookback = doesModeOwnLookback();
    const measureType = String(record.measure_type || "").toUpperCase();
    const useExplicitFlowYtd =
      modeOwnsLookback &&
      isFlowYtdMode(effectiveMode) &&
      (measureType === "FLOW" || measureType === "DERIVED") &&
      !(isComponentChild && isComponentShareOrContributionMode(effectiveMode));
    if (
      modeOwnsLookback &&
      useExplicitFlowYtd &&
      !(isComponentChild && isComponentShareOrContributionMode(effectiveMode))
    ) {
      // Explicit FLOW YTD modes (YTDvsGDP / YTDRaw / YTDYoY) on Latest.
      const ytdMode = mapFlowYtdModeToSamePeriodMode(effectiveMode);
      values = valuesForYtdSamePeriodRecord(record, location, ytdMode);
      if (ytdMode === MODE_VS_GDP || effectiveMode === MODE_YTD_VS_GDP) {
        formatMode = MODE_VS_GDP;
        formatRecord = { base_unit: ABS_UNIT_PERCENT, base_currency: "" };
      } else if (effectiveMode === MODE_YTD_YOY) {
        formatMode = MODE_ANNUAL;
      }
    } else if (!modeOwnsLookback) {
      values = buildValuesForAsOfComparison(
        row,
        record,
        location,
        effectiveMode,
        isComponentChild
      );
      if (
        effectiveMode === MODE_VS_GDP ||
        effectiveMode === MODE_YTD_VS_GDP
      ) {
        formatMode = MODE_VS_GDP;
        formatRecord = { base_unit: ABS_UNIT_PERCENT, base_currency: "" };
      } else if (
        isComponentChild &&
        isComponentShareOrContributionMode(effectiveMode)
      ) {
        formatMode = MODE_RAW;
        formatRecord = isRelMode(effectiveMode)
          ? { base_unit: ABS_UNIT_PERCENT, base_currency: "" }
          : { base_unit: ABS_UNIT_PP, base_currency: "" };
      }
    } else if (effectiveMode === MODE_VS_GDP) {
      const vsGdpSeries = getVsGdpTimeSeries(record, location);
      values = valuesForMode(vsGdpSeries, record.frequency, MODE_VS_GDP);
      formatMode = MODE_VS_GDP;
      formatRecord = { base_unit: ABS_UNIT_PERCENT, base_currency: "" };
    } else if (
      isComponentChild &&
      isComponentShareOrContributionMode(effectiveMode)
    ) {
      const resolved = buildComponentShareOrContributionValues(
        row,
        record,
        location,
        effectiveMode
      );
      values = resolved.values;
      formatMode = resolved.formatMode;
      formatRecord = resolved.formatRecord || formatRecord;
    } else if (isComponentChild) {
      // Raw / MoM / QoQ / QoQy / YoY on the component's own outstanding series.
      const rawSeries = getComponentRawTimeSeries(record);
      values = valuesForMode(rawSeries, record.frequency, effectiveMode);
    } else {
      values = valuesForMode(
        record.time_series,
        record.frequency,
        effectiveMode
      );
    }

    const currEmpty = values.current == null;
    const prevEmpty = values.previous == null;
    const chgEmpty = values.change == null;
    const sharedMagnitude =
      formatMode === MODE_RAW
        ? getSharedAmountMagnitude(
          values,
          (formatRecord && formatRecord.base_unit) || ""
        )
        : null;

    setCellText(
      currCell,
      currEmpty
        ? "—"
        : formatCellValue(
          values.current,
          formatMode,
          formatRecord,
          sharedMagnitude
        ),
      currEmpty
    );
    setCellText(
      prevCell,
      prevEmpty
        ? "—"
        : formatCellValue(
          values.previous,
          formatMode,
          formatRecord,
          sharedMagnitude
        ),
      prevEmpty
    );
    setChangeCell(
      chgCell,
      chgEmpty
        ? "—"
        : formatCellValue(
          values.change,
          formatMode,
          formatRecord,
          sharedMagnitude
        ),
      values.change,
      chgEmpty
    );
    if (periodCell) {
      const empty = !values.period;
      setCellText(periodCell, values.period || "—", empty);
    }
  });
}

const SOURCE_LABEL_BY_CODE = {
  INSEE: "INSEE (National Institute of Statistics and Economic Studies)",
  EUROSTAT: "Eurostat (Statistical Office of the European Union)",
  FRED: "FRED (Federal Reserve Economic Data)",
  UNIV_MICHIGAN: "University of Michigan",
  JP_CABINET_OFFICE: "CAO (Japan Cabinet Office)",
  STAT_OF_JP: "e-Stat (Statistics of Japan)",
  MLIT: "MLIT (Ministry of Land, Infrastructure, Transport and Tourism)",
  METI: "METI (Ministry of Economy, Trade and Industry)",
  BOJ: "BOJ (Bank of Japan)",
  MOF: "MOF (Ministry of Finance, Japan)",
  ECB: "ECB (European Central Bank)",
  IMF: "IMF (International Monetary Fund)",
  OECD: "OECD (Organisation for Economic Co-operation and Development)",
  BEA: "BEA (Bureau of Economic Analysis)",
  BANQUE_DE_FRANCE: "BdF (Banque de France)",
  CONFERENCE_BOARD: "Conference Board",
  ISM: "ISM (Institute for Supply Management)",
  NAHB: "NAHB (National Association of Home Builders)",
  CENSUS: "Census (US Census Bureau)",
  TRADING_ECONOMICS: "Trading Economics",
};

function listEconomicRecapRecords() {
  /** Flatten every indicator entry in the active recap sections. */
  const recapRecords = [];
  for (const categoryGroup of economicRecapSections || []) {
    for (const subcategoryGroup of categoryGroup.subcategories || []) {
      for (const entry of subcategoryGroup.entries || []) {
        recapRecords.push(entry);
      }
    }
  }
  return recapRecords;
}

function extractSourceDocsUrl(rawSourceUrl) {
  /** First http(s) segment in a 'source_url' (derived or plain). */
  return (
    (rawSourceUrl || "")
      .split("||")
      .map((part) => part.trim())
      .find((part) => /^https?:\/\//i.test(part)) || ""
  );
}

function doesInputSeriesMatchRecapRecord(inputSeriesName, record) {
  /**
   * True when a derived-input label names this table row.
   * Labels are usually '{Location} {type}' while 'name' is the type.
   */
  const inputSeriesLabel = (inputSeriesName || "").trim();
  if (!inputSeriesLabel) {
    return false;
  }
  if (
    record.display_name === inputSeriesLabel ||
    record.name === inputSeriesLabel
  ) {
    return true;
  }
  if (record.name && inputSeriesLabel.endsWith(` ${record.name}`)) {
    return true;
  }
  if (
    record.display_name &&
    inputSeriesLabel.endsWith(` ${record.display_name}`)
  ) {
    return true;
  }
  return false;
}

function doesDerivedNeedOwnSourceLink(inputSeriesPart) {
  /**
   * Own derivation stays a plain label when any listed input is already a
   * clickable Source row in this table. Link only when none of those inputs
   * are present with a docs URL (e.g. Palma feeds that are not table lines).
   */
  const inputSeriesNames = (inputSeriesPart || "")
    .split(";")
    .map((part) => part.trim())
    .filter(Boolean);
  if (inputSeriesNames.length === 0) {
    return true;
  }
  const recapRecords = listEconomicRecapRecords();
  const hasLinkedInputInTable = inputSeriesNames.some((inputSeriesName) => {
    const matchedRecord = recapRecords.find((record) =>
      doesInputSeriesMatchRecapRecord(inputSeriesName, record)
    );
    return Boolean(
      matchedRecord && extractSourceDocsUrl(matchedRecord.source_url)
    );
  });
  return !hasLinkedInputInTable;
}

function formatRecapSourceDisplay(record) {
  /**
   * Source column label + docs URL. Derived 'source_url' is
   * 'Agency[, Agency] || Input indicator[; …][ || https://…]'.
   */
  const sourceAgencyLabel =
    SOURCE_LABEL_BY_CODE[record.source] || record.source || "—";
  const rawSourceUrl = (record.source_url || "").trim();
  if (record.measure_type === "DERIVED" && rawSourceUrl.includes("||")) {
    const derivedSourceParts = rawSourceUrl
      .split("||")
      .map((part) => part.trim())
      .filter(Boolean);
    // Agency list is first; optional input list; docs URL is any https part.
    const agenciesLabel = derivedSourceParts[0] || sourceAgencyLabel;
    const inputSeriesPart =
      derivedSourceParts.find(
        (part) => part !== agenciesLabel && !/^https?:\/\//i.test(part)
      ) || "";
    const docsUrl = extractSourceDocsUrl(rawSourceUrl);
    const shouldLinkOwnDerivation =
      Boolean(docsUrl) && doesDerivedNeedOwnSourceLink(inputSeriesPart);
    return {
      label: `Own derivation (${agenciesLabel})`,
      url: shouldLinkOwnDerivation ? docsUrl : "",
    };
  }
  // Non-derived series usually store a single docs URL in source_url.
  return {
    label: sourceAgencyLabel,
    url: extractSourceDocsUrl(rawSourceUrl),
  };
}

function isUnwiredLocationStubRecord(record) {
  /**
   * True when this location has no seeded series on the line (aligned
   * placeholder cell with empty values and no docs URL).
   */
  return Boolean(
    record &&
      !(record.source_url || "").trim() &&
      record.current == null &&
      record.previous == null &&
      record.period == null &&
      !(record.time_series && record.time_series.length)
  );
}

function fillSourceCell(row) {
  /** Fill the Source column with a clickable agency label when a docs URL exists. */
  const sourceCell = row.querySelector(".source-cell");
  if (!sourceCell) {
    return;
  }
  const record = getIndicatorBubbleRecord(row);
  if (!record || isUnwiredLocationStubRecord(record)) {
    sourceCell.textContent = "—";
    return;
  }
  const sourceDisplay = formatRecapSourceDisplay(record);
  if (sourceDisplay.url) {
    const sourceLink = document.createElement("a");
    sourceLink.className = "source-link";
    sourceLink.href = sourceDisplay.url;
    sourceLink.target = "_blank";
    sourceLink.rel = "noopener noreferrer";
    sourceLink.textContent = sourceDisplay.label;
    sourceLink.title = sourceDisplay.url;
    sourceCell.replaceChildren(sourceLink);
    return;
  }
  sourceCell.textContent = sourceDisplay.label;
}

function hideIndicatorInfoBubble() {
  /** Clear the methodology hover bubble. */
  activeIndicatorInfoBubbleRow = null;
  if (!indicatorInfoBubble) {
    return;
  }
  indicatorInfoBubble.hidden = true;
  indicatorInfoBubble.setAttribute("aria-hidden", "true");
  indicatorInfoBubble.innerHTML = "";
}

function isSourceCellTarget(eventTarget) {
  /** True when the event is over the Source column (link goes to docs URL). */
  return Boolean(
    eventTarget &&
      eventTarget.closest &&
      eventTarget.closest(".source-cell")
  );
}

function wireIndicatorRowModeSelect(row) {
  if (row.dataset.modeWired === "true") {
    return;
  }
  row.dataset.modeWired = "true";
  fillSourceCell(row);
  const select = row.querySelector(".recap-mode-select");
  if (!select) {
    // Fixed Raw lines (Output Gap, Estimated Annual GDP Growth) and other rows without a mode control.
    updateRow(row, MODE_RAW);
    return;
  }
  const defaultMode = row.dataset.defaultMode || MODE_RAW;
  const optionValues = Array.from(select.options).map((option) => option.value);
  const initialMode = optionValues.includes(defaultMode)
    ? defaultMode
    : optionValues[0] || MODE_RAW;
  select.value = initialMode;
  updateRow(row, initialMode);
  select.addEventListener("change", () => {
    updateRow(row, select.value);
    if (
      typeof activeIndicatorInfoBubbleRow !== "undefined" &&
      activeIndicatorInfoBubbleRow === row &&
      indicatorInfoBubble
    ) {
      const record = getIndicatorBubbleRecord(row);
      if (record) {
        indicatorInfoBubble.innerHTML = buildIndicatorInfoBubbleHtml(
          record,
          row
        );
      }
    }
  });
}

function refreshAllIndicatorRows() {
  document.querySelectorAll(".indicator-row").forEach((row) => {
    const select = row.querySelector(".recap-mode-select");
    const fixedMode = getFixedDisplayModeForIndicatorName(
      row.dataset.indicatorName
    );
    const mode =
      fixedMode ||
      (select && select.value) ||
      row.dataset.defaultMode ||
      MODE_RAW;
    updateRow(row, mode);
  });
}

document.querySelectorAll(".indicator-row").forEach((row) => {
  wireIndicatorRowModeSelect(row);
});


function findNominalGdpRecord(location) {
  return economicRecapNominalGdp.find((item) => item.location === location);
}

function alignTimeSeriesByPeriod(parentSeries, childSeries) {
  // Usage of Map: keys are ISO period dates.
  const childByPeriod = new Map(
    (childSeries || []).map((point) => [point.period_date, point])
  );
  const aligned = [];
  for (const parentPoint of parentSeries || []) {
    const childPoint = childByPeriod.get(parentPoint.period_date);
    if (!childPoint) {
      continue;
    }
    aligned.push({
      period: parentPoint.period,
      period_date: parentPoint.period_date,
      parentValue: parentPoint.value,
      childValue: childPoint.value,
    });
  }
  return aligned;
}

function buildShareTimeSeries(parentSeries, childSeries) {
  return alignTimeSeriesByPeriod(parentSeries, childSeries)
    .map((point) => {
      if (point.parentValue === 0) {
        return null;
      }
      return {
        period: point.period,
        period_date: point.period_date,
        value: (point.childValue / point.parentValue) * 100,
      };
    })
    .filter(Boolean);
}

function buildContributionTimeSeries(parentSeries, childSeries, lookbackMonths = 1) {
  /**
   * Contribution of the child's change over the calendar lookback to the
   * parent's prior level: (child_t − child_{t−lookback}) / |parent_{t−lookback}| × 100.
   * Aligned series are chronological (oldest first).
   */
  const aligned = alignTimeSeriesByPeriod(parentSeries, childSeries);
  const alignedByPeriodDate = new Map(
    aligned.map((point) => [point.period_date, point])
  );
  const contributionSeries = [];
  for (const current of aligned) {
    const lookbackPeriodDate = shiftPeriodDateMonths(
      current.period_date,
      lookbackMonths
    );
    if (!lookbackPeriodDate) {
      continue;
    }
    const previous = alignedByPeriodDate.get(lookbackPeriodDate);
    if (!previous || previous.parentValue === 0) {
      continue;
    }
    contributionSeries.push({
      period: current.period,
      period_date: current.period_date,
      value:
        ((current.childValue - previous.childValue) /
          Math.abs(previous.parentValue)) *
        100,
    });
  }
  return contributionSeries;
}

function findRowspanCell(fromRow, cellSelector) {
  let row = fromRow;
  while (row) {
    const cell = row.querySelector(cellSelector);
    if (cell) {
      return cell;
    }
    row = row.previousElementSibling;
  }
  return null;
}

function adjustCategorySubcategoryRowspans(parentRow, delta) {
  if (!delta) {
    return;
  }
  const categoryCell = findRowspanCell(parentRow, "td.category-cell");
  const subcategoryCell = findRowspanCell(parentRow, "td.subcategory-cell");
  if (categoryCell) {
    categoryCell.rowSpan = Math.max(1, categoryCell.rowSpan + delta);
  }
  if (subcategoryCell) {
    subcategoryCell.rowSpan = Math.max(1, subcategoryCell.rowSpan + delta);
  }
}

function listDirectExpandableChildRows(parentName) {
  /**
   * COMPONENT and RELATED children both nest under the parent toggle.
   * Only COMPONENT participates in Rel / Contr share math elsewhere.
   */
  return Array.from(document.querySelectorAll(".indicator-row")).filter(
    (row) => {
      if ((row.dataset.parentSeriesLabel || "") !== parentName) {
        return false;
      }
      const expansionRelation = row.dataset.expansionRelation || "";
      return (
        expansionRelation === "COMPONENT" || expansionRelation === "RELATED"
      );
    }
  );
}

function applyExpandDepthToChildRows() {
  /**
   * Indent depth follows the parent chain (Real GDP → Net Exports → Exports).
   */
  // Usage of Map: keys are indicator line names; values are table rows.
  const rowByName = new Map();
  Array.from(document.querySelectorAll(".indicator-row")).forEach((row) => {
    rowByName.set(row.dataset.indicatorName || "", row);
  });

  function depthForRow(row) {
    const parentSeriesLabel = row.dataset.parentSeriesLabel || "";
    if (!parentSeriesLabel) {
      return 0;
    }
    const parentRow = rowByName.get(parentSeriesLabel);
    if (!parentRow) {
      return 1;
    }
    return 1 + depthForRow(parentRow);
  }

  rowByName.forEach((row) => {
    const expandDepth = depthForRow(row);
    if (expandDepth <= 0) {
      return;
    }
    row.dataset.expandDepth = String(expandDepth);
    row.style.setProperty("--expand-depth", String(expandDepth));
  });
}

function countVisibleDescendantComponentRows(parentRow) {
  /**
   * When collapsing a parent, also hide already-expanded nested children and
   * count every row that leaves the visible table.
   */
  const parentName = parentRow.dataset.indicatorName || "";
  const directChildren = listDirectExpandableChildRows(parentName);
  let hiddenCount = 0;
  directChildren.forEach((childRow) => {
    if (!childRow.classList.contains("is-collapsed")) {
      hiddenCount += 1;
    }
    const nestedToggle = childRow.querySelector(".expand-toggle");
    if (
      nestedToggle &&
      nestedToggle.getAttribute("aria-expanded") === "true"
    ) {
      hiddenCount += countVisibleDescendantComponentRows(childRow);
      nestedToggle.setAttribute("aria-expanded", "false");
      nestedToggle.textContent = "+";
      childRow.classList.remove("is-expanded");
    }
    childRow.classList.add("is-collapsed");
  });
  return hiddenCount;
}

function wireExpandableIndicatorRows() {
  applyExpandDepthToChildRows();
  const rows = Array.from(document.querySelectorAll(".indicator-row"));

  rows.forEach((row) => {
    const indicatorName = row.dataset.indicatorName || "";
    const directChildren = listDirectExpandableChildRows(indicatorName);
    const toggle = row.querySelector(".expand-toggle");
    if (!toggle) {
      return;
    }
    if (directChildren.length === 0) {
      toggle.hidden = true;
      return;
    }
    toggle.hidden = false;
    toggle.addEventListener("click", (event) => {
      event.stopPropagation();
      const expanded = toggle.getAttribute("aria-expanded") === "true";
      const nextExpanded = !expanded;
      toggle.setAttribute("aria-expanded", nextExpanded ? "true" : "false");
      toggle.textContent = nextExpanded ? "−" : "+";
      row.classList.toggle("is-expanded", nextExpanded);

      let rowspanDelta = 0;
      if (!nextExpanded) {
        rowspanDelta -= countVisibleDescendantComponentRows(row);
      } else {
        directChildren.forEach((childRow) => {
          childRow.classList.remove("is-collapsed");
          wireIndicatorRowModeSelect(childRow);
          const childSelect = childRow.querySelector(".recap-mode-select");
          updateRow(
            childRow,
            childSelect ? childSelect.value : MODE_RAW
          );
          rowspanDelta += 1;
        });
      }

      adjustCategorySubcategoryRowspans(row, rowspanDelta);
      refreshCategorySeparatorRows();
    });
  });
}

function findRowspanLabelCell(startRow, cellSelector) {
  // Walk upward until the rowspan category/subcategory label cell is found.
  let row = startRow;
  while (row) {
    const labelCell = row.querySelector(cellSelector);
    if (labelCell) {
      return labelCell;
    }
    row = row.previousElementSibling;
  }
  return null;
}

function refreshCategorySeparatorRows() {
  /**
   * Dark-blue category borders sit on the last visible row per category and on
   * the rowspan category/subcategory cells that close that same vertical edge.
   */
  const tbody = document.querySelector(".economic-table-scroll tbody");
  if (!tbody) {
    return;
  }
  const rows = Array.from(tbody.querySelectorAll("tr.indicator-row"));
  rows.forEach((row) => {
    row.classList.remove("category-last-row", "subcategory-last-row");
  });
  tbody
    .querySelectorAll(".category-closing-cell, .subcategory-closing-cell")
    .forEach((cell) => {
      cell.classList.remove(
        "category-closing-cell",
        "subcategory-closing-cell"
      );
    });

  // Usage of Map: keys are category codes; values are visible rows in DOM order.
  const visibleRowsByCategory = new Map();
  // Usage of Map: keys are `${category}::${subcategory}`; values are visible rows.
  const visibleRowsBySubcategory = new Map();
  rows.forEach((row) => {
    if (row.classList.contains("is-collapsed")) {
      return;
    }
    if (row.style.display === "none") {
      return;
    }
    const category = row.dataset.category || "";
    const subcategory = row.dataset.subcategory || "";
    if (!visibleRowsByCategory.has(category)) {
      visibleRowsByCategory.set(category, []);
    }
    visibleRowsByCategory.get(category).push(row);
    const subcategoryKey = `${category}::${subcategory}`;
    if (!visibleRowsBySubcategory.has(subcategoryKey)) {
      visibleRowsBySubcategory.set(subcategoryKey, []);
    }
    visibleRowsBySubcategory.get(subcategoryKey).push(row);
  });

  visibleRowsBySubcategory.forEach((subcategoryRows) => {
    // The series is DOM order, so the last entry is the bottom row of the block.
    const lastSubcategoryRow = subcategoryRows[subcategoryRows.length - 1];
    lastSubcategoryRow.classList.add("subcategory-last-row");
    const subcategoryCell = findRowspanLabelCell(
      lastSubcategoryRow,
      ".subcategory-cell"
    );
    if (subcategoryCell) {
      subcategoryCell.classList.add("subcategory-closing-cell");
    }
  });
  visibleRowsByCategory.forEach((categoryRows) => {
    // The series is DOM order, so the last entry closes the category.
    const lastCategoryRow = categoryRows[categoryRows.length - 1];
    lastCategoryRow.classList.remove("subcategory-last-row");
    lastCategoryRow.classList.add("category-last-row");
    const categoryCell = findRowspanLabelCell(lastCategoryRow, ".category-cell");
    if (categoryCell) {
      categoryCell.classList.add("category-closing-cell");
    }
    const subcategoryCell = findRowspanLabelCell(
      lastCategoryRow,
      ".subcategory-cell"
    );
    if (subcategoryCell) {
      subcategoryCell.classList.remove("subcategory-closing-cell");
      subcategoryCell.classList.add("category-closing-cell");
    }
  });
}

wireExpandableIndicatorRows();
refreshCategorySeparatorRows();

function escapeBubbleText(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatPriceBasisPhrase(priceBasis) {
  if (priceBasis === "REAL") {
    return "real";
  }
  if (priceBasis === "NOMINAL") {
    return "nominal";
  }
  return "";
}

function formatGdpShareUnitLabel(priceBasis) {
  const basisPhrase = formatPriceBasisPhrase(priceBasis);
  if (basisPhrase) {
    return `Percent of ${basisPhrase} GDP`;
  }
  return "Percent of GDP";
}

function formatBubbleUnit(record, mode, comparisonParentName) {
  if (isRelMode(mode)) {
    if (comparisonParentName === "Real GDP") {
      return "Percent of real GDP";
    }
    if (comparisonParentName === "Nominal GDP") {
      return "Percent of nominal GDP";
    }
    return "Percent of parent";
  }
  if (isContrMode(mode)) {
    return "Percentage points (pp)";
  }
  if (mode === MODE_VS_GDP || mode === MODE_YTD_VS_GDP) {
    return formatGdpShareUnitLabel(record && record.price_basis);
  }
  if (
    mode === MODE_MONTH ||
    mode === MODE_QUARTER ||
    mode === MODE_ANNUALIZED_QUARTER ||
    mode === MODE_ANNUAL ||
    mode === MODE_YTD_YOY
  ) {
    return "Percent";
  }
  const unit = (record && record.base_unit) || "";
  const currency = (record && record.base_currency) || "";
  const baseYear = record && record.base_year;
  if (unit === ABS_UNIT_INDEX) {
    return baseYear != null ? `Index (base year ${baseYear})` : "Index";
  }
  if (unit === ABS_UNIT_PERCENT) {
    const typeName = (record && (record.display_name || record.name)) || "";
    if (/of GDP/i.test(typeName) || /% of GDP/i.test(typeName)) {
      return formatGdpShareUnitLabel(record && record.price_basis);
    }
    return "Percent";
  }
  if (["K", "M", "B"].includes(unit)) {
    const magnitudeLabel =
      unit === "K" ? "Thousands" : unit === "M" ? "Millions" : "Billions";
    const amountLabel = currency
      ? `${magnitudeLabel} ${currency}`
      : magnitudeLabel;
    const basisPhrase = formatPriceBasisPhrase(record && record.price_basis);
    return basisPhrase ? `${amountLabel} (${basisPhrase})` : amountLabel;
  }
  return "—";
}

const MEASURE_TYPE_LABEL_BY_CODE = {
  FLOW: "Flow",
  STOCK: "Stock",
  RATE: "Rate",
  INDEX: "Index",
  RATIO: "Ratio",
  DERIVED: "Derived",
};

const FLOW_INTERVAL_LABEL_BY_FREQUENCY = {
  MONTHLY: "monthly",
  QUARTERLY: "quarterly",
  ANNUAL: "annual",
};

function formatMeasureTypeLabel(
  measureType,
  frequency,
  isAnnualized,
  priceBasis,
  isSeasonallyAdjusted
) {
  if (!measureType) {
    return "—";
  }
  const baseLabel = MEASURE_TYPE_LABEL_BY_CODE[measureType] || measureType;
  const basisPhrase = formatPriceBasisPhrase(priceBasis);
  const qualifiers = [];
  // Flows, rates, and derived series carry the publication interval; US / JP
  // raw amounts that are SAAR / annualized get that called out too. Nominal /
  // real comes from price_basis when the indicator type has one. Infra-annual
  // series also say whether the print is seasonally adjusted.
  if (
    measureType === "FLOW" ||
    measureType === "RATE" ||
    measureType === "DERIVED"
  ) {
    const flowInterval = FLOW_INTERVAL_LABEL_BY_FREQUENCY[frequency || ""];
    if (flowInterval) {
      qualifiers.push(flowInterval);
    }
    if (frequency === "MONTHLY" || frequency === "QUARTERLY") {
      qualifiers.push(
        isSeasonallyAdjusted
          ? "seasonally adjusted"
          : "not seasonally adjusted"
      );
    }
  }
  if (isAnnualized) {
    qualifiers.push("annualized");
  }
  if (basisPhrase) {
    qualifiers.push(basisPhrase);
  }
  if (!qualifiers.length) {
    return baseLabel;
  }
  return `${baseLabel} (${qualifiers.join(", ")})`;
}

function buildIndicatorInfoBubbleHtml(record, row) {
  const select = row && row.querySelector(".recap-mode-select");
  const fixedMode = row
    ? getFixedDisplayModeForIndicatorName(row.dataset.indicatorName)
    : null;
  const mode = fixedMode || (select ? select.value : MODE_RAW);
  const isComponentChild =
    row && (row.dataset.expansionRelation || "") === "COMPONENT";
  const comparisonParentName =
    isComponentChild && fixedMode !== MODE_RAW
      ? getComparisonParentName(row)
      : "";
  const baseTitle = record.display_name || record.name || "Indicator";
  const titlePlain = isComponentChild
    ? buildDisplayName(baseTitle, mode, [record], comparisonParentName)
    : baseTitle;
  const title = escapeBubbleText(titlePlain);
  // Unwired location stubs keep the row with — cells and no source URL.
  if (isUnwiredLocationStubRecord(record)) {
    return `
    <p class="bubble-title">${title}</p>
    <p class="bubble-meta">No data</p>
  `;
  }
  const frequency = escapeBubbleText(record.frequency || "—");
  const measureTypeLabel = escapeBubbleText(
    formatMeasureTypeLabel(
      record.measure_type,
      record.frequency,
      Boolean(record.is_annualized),
      record.price_basis || "",
      record.is_seasonally_adjusted !== false
    )
  );
  const unitLabel = escapeBubbleText(
    formatBubbleUnit(record, mode, comparisonParentName)
  );
  const description = escapeBubbleText((record.description || "").trim());
  const descriptionBlock = description
    ? `<p class="bubble-meta bubble-description">${description.replace(
      /\n/g,
      "<br>"
    )}</p>`
    : "";
  // Source / Series / URL live in the table Source column, not the bubble.
  return `
    <p class="bubble-title">${title}</p>
    ${descriptionBlock}
    <dl class="bubble-meta"><dt>Type</dt><dd>${measureTypeLabel}</dd></dl>
    <dl class="bubble-meta"><dt>Unit</dt><dd>${unitLabel}</dd></dl>
    <dl class="bubble-meta"><dt>Frequency</dt><dd>${frequency}</dd></dl>
  `;
}

function positionIndicatorInfoBubble(bubble, event) {
  const offset = 14;
  const bubbleWidth = bubble.offsetWidth;
  const bubbleHeight = bubble.offsetHeight;
  let left = event.clientX + offset;
  let top = event.clientY + offset;
  if (left + bubbleWidth > window.innerWidth - 8) {
    left = event.clientX - bubbleWidth - offset;
  }
  if (top + bubbleHeight > window.innerHeight - 8) {
    top = event.clientY - bubbleHeight - offset;
  }
  bubble.style.left = `${Math.max(8, left)}px`;
  bubble.style.top = `${Math.max(8, top)}px`;
}

function getIndicatorBubbleRecord(row) {
  const indicatorName = row.dataset.indicatorName;
  const category = row.dataset.category;
  // Single-region table: locationsJSON has exactly the selected region.
  const location = economicRecapLocations[0];
  return findRecord(indicatorName, category, location);
}

function buildEconomicRecapAsOfQueryString(asOfState, comparison) {
  const queryParts = [];
  if (asOfState.year != null) {
    queryParts.push(`as_of_year=${asOfState.year}`);
    if (asOfState.quarter != null) {
      queryParts.push(`as_of_quarter=${asOfState.quarter}`);
    } else if (asOfState.month != null) {
      queryParts.push(`as_of_month=${asOfState.month}`);
    }
  }
  const defaultComparison = getDefaultComparisonForAsOf(
    asOfState.year,
    asOfState.quarter,
    asOfState.month
  );
  if (comparison && comparison !== defaultComparison) {
    queryParts.push(`comparison=${encodeURIComponent(comparison)}`);
  }
  return queryParts.join("&");
}

function syncEconomicRecapAsOfUrl() {
  const params = new URLSearchParams();
  const selectedRegionButton = document.querySelector(
    ".region-btn.active[data-region]"
  );
  const selectedRegion =
    (selectedRegionButton && selectedRegionButton.dataset.region) ||
    economicRecapLocations[0];
  if (selectedRegion) {
    params.set("region", selectedRegion);
  }
  if (economicRecapAsOfState.year != null) {
    params.set("as_of_year", String(economicRecapAsOfState.year));
    if (economicRecapAsOfState.quarter != null) {
      params.set("as_of_quarter", String(economicRecapAsOfState.quarter));
    } else if (economicRecapAsOfState.month != null) {
      params.set("as_of_month", String(economicRecapAsOfState.month));
    }
  }
  const defaultComparison = getDefaultComparisonForAsOf(
    economicRecapAsOfState.year,
    economicRecapAsOfState.quarter,
    economicRecapAsOfState.month
  );
  if (economicRecapComparisonState !== defaultComparison) {
    params.set("comparison", economicRecapComparisonState);
  }
  const query = params.toString();
  const nextUrl = query
    ? `${window.location.pathname}?${query}`
    : window.location.pathname;
  window.history.replaceState({}, "", nextUrl);

  document.querySelectorAll(".region-btn[data-region]").forEach((regionLink) => {
    const region = regionLink.dataset.region;
    const asOfQuery = buildEconomicRecapAsOfQueryString(
      economicRecapAsOfState,
      economicRecapComparisonState
    );
    regionLink.href = asOfQuery
      ? `?region=${encodeURIComponent(region)}&${asOfQuery}`
      : `?region=${encodeURIComponent(region)}`;
  });
}

function syncRecapModeOptionsForAsOf() {
  /**
   * Hide MoM under year/quarter As-of; hide QoQ/QoQy under year-only As-of.
   * Rel/Contr keep both QoQ/YoY labels; Comparison owns the horizon when set.
   */
  const yearSelected = economicRecapAsOfState.year != null;
  const quarterSelected = economicRecapAsOfState.quarter != null;
  const monthSelected = economicRecapAsOfState.month != null;
  const hideMom = yearSelected && !monthSelected;
  const hideQoq = yearSelected && !quarterSelected && !monthSelected;

  document.querySelectorAll(".indicator-row").forEach((row) => {
    const select = row.querySelector(".recap-mode-select");
    if (!select) {
      return;
    }
    Array.from(select.options).forEach((option) => {
      if (option.value === MODE_MONTH) {
        option.hidden = hideMom;
        option.disabled = hideMom;
      }
      if (
        option.value === MODE_QUARTER ||
        option.value === MODE_ANNUALIZED_QUARTER
      ) {
        option.hidden = hideQoq;
        option.disabled = hideQoq;
      }
    });
    if (select.selectedOptions[0] && select.selectedOptions[0].disabled) {
      const fallback =
        Array.from(select.options).find((option) => !option.disabled) ||
        select.options[0];
      if (fallback) {
        select.value = fallback.value;
      }
    }
  });
}

function syncEconomicRecapAsOfControls() {
  const yearSelect = document.getElementById("as-of-year");
  const quarterSelect = document.getElementById("as-of-quarter");
  const monthSelect = document.getElementById("as-of-month");
  const latestButton = document.getElementById("as-of-latest");
  const comparisonSelect = document.getElementById("recap-comparison");
  const availability = getAsOfAvailability(economicRecapAsOfState.year);

  if (yearSelect) {
    Array.from(yearSelect.options).forEach((option) => {
      if (!option.value) {
        return;
      }
      const year = Number(option.value);
      option.disabled = !availability.years.has(year);
    });
    yearSelect.value =
      economicRecapAsOfState.year != null
        ? String(economicRecapAsOfState.year)
        : "";
  }

  const yearSelected = economicRecapAsOfState.year != null;

  if (quarterSelect) {
    quarterSelect.disabled = !yearSelected;
    Array.from(quarterSelect.options).forEach((option) => {
      if (!option.value) {
        return;
      }
      const quarter = Number(option.value);
      option.disabled = !yearSelected || !availability.quarters.has(quarter);
    });
    quarterSelect.value =
      economicRecapAsOfState.quarter != null
        ? String(economicRecapAsOfState.quarter)
        : "";
  }

  if (monthSelect) {
    monthSelect.disabled = !yearSelected;
    Array.from(monthSelect.options).forEach((option) => {
      if (!option.value) {
        return;
      }
      const month = Number(option.value);
      option.disabled = !yearSelected || !availability.months.has(month);
    });
    monthSelect.value =
      economicRecapAsOfState.monthDisplay != null
        ? String(economicRecapAsOfState.monthDisplay)
        : "";
  }

  if (latestButton) {
    latestButton.classList.toggle(
      "active",
      economicRecapAsOfState.year == null
    );
  }

  if (comparisonSelect) {
    const yearOnly =
      yearSelected &&
      economicRecapAsOfState.quarter == null &&
      economicRecapAsOfState.month == null;
    Array.from(comparisonSelect.options).forEach((option) => {
      if (option.value === COMPARISON_QUARTER) {
        option.disabled = yearOnly;
      }
    });
    economicRecapComparisonState = normalizeComparisonForAsOf(
      economicRecapComparisonState,
      economicRecapAsOfState.year,
      economicRecapAsOfState.quarter,
      economicRecapAsOfState.month
    );
    comparisonSelect.value = economicRecapComparisonState;
  }

  syncRecapModeOptionsForAsOf();
}

function setEconomicRecapAsOfState({ year, quarter, month, resetComparison }) {
  const nextYear = year == null || year === "" ? null : Number(year);
  let nextQuarter =
    quarter == null || quarter === "" ? null : Number(quarter);
  let nextMonth = month == null || month === "" ? null : Number(month);

  if (nextYear == null) {
    nextQuarter = null;
    nextMonth = null;
  } else if (nextMonth != null) {
    // Month and quarter are mutually exclusive; month wins.
    nextQuarter = null;
  } else if (nextQuarter != null) {
    nextMonth = null;
  }

  economicRecapAsOfState = {
    year: nextYear,
    quarter: nextQuarter,
    month: nextMonth,
    monthDisplay: formatAsOfMonthDisplay(nextYear, nextQuarter, nextMonth),
    endDate: getAsOfEndDate(nextYear, nextQuarter, nextMonth),
  };
  if (resetComparison !== false) {
    economicRecapComparisonState = getDefaultComparisonForAsOf(
      nextYear,
      nextQuarter,
      nextMonth
    );
  } else {
    economicRecapComparisonState = normalizeComparisonForAsOf(
      economicRecapComparisonState,
      nextYear,
      nextQuarter,
      nextMonth
    );
  }
  applyEconomicRecapAsOfFilter();
  syncEconomicRecapAsOfControls();
  syncEconomicRecapAsOfUrl();
  refreshAllIndicatorRows();
}

function setEconomicRecapComparison(comparison) {
  economicRecapComparisonState = normalizeComparisonForAsOf(
    comparison,
    economicRecapAsOfState.year,
    economicRecapAsOfState.quarter,
    economicRecapAsOfState.month
  );
  syncEconomicRecapAsOfControls();
  syncEconomicRecapAsOfUrl();
  refreshAllIndicatorRows();
}

function wireEconomicRecapAsOfToolbar() {
  const yearSelect = document.getElementById("as-of-year");
  const quarterSelect = document.getElementById("as-of-quarter");
  const monthSelect = document.getElementById("as-of-month");
  const latestButton = document.getElementById("as-of-latest");
  const comparisonSelect = document.getElementById("recap-comparison");
  if (!yearSelect || !monthSelect || !latestButton || !quarterSelect) {
    return;
  }

  yearSelect.addEventListener("change", () => {
    const year = yearSelect.value ? Number(yearSelect.value) : null;
    if (year == null) {
      setEconomicRecapAsOfState({ year: null, quarter: null, month: null });
      return;
    }
    // Keep quarter/month only when they still have prints under the new year.
    const availability = getAsOfAvailability(year);
    let quarter = economicRecapAsOfState.quarter;
    let month = economicRecapAsOfState.month;
    if (quarter != null && !availability.quarters.has(quarter)) {
      quarter = null;
    }
    if (month != null && !availability.months.has(month)) {
      month = null;
    }
    setEconomicRecapAsOfState({ year, quarter, month });
  });

  quarterSelect.addEventListener("change", () => {
    if (!economicRecapAsOfState.year) {
      return;
    }
    const quarter = quarterSelect.value ? Number(quarterSelect.value) : null;
    setEconomicRecapAsOfState({
      year: economicRecapAsOfState.year,
      quarter,
      month: null,
    });
  });

  monthSelect.addEventListener("change", () => {
    if (!economicRecapAsOfState.year) {
      return;
    }
    const month = monthSelect.value ? Number(monthSelect.value) : null;
    setEconomicRecapAsOfState({
      year: economicRecapAsOfState.year,
      quarter: null,
      month,
    });
  });

  latestButton.addEventListener("click", () => {
    setEconomicRecapAsOfState({ year: null, quarter: null, month: null });
  });

  if (comparisonSelect) {
    comparisonSelect.addEventListener("change", () => {
      setEconomicRecapComparison(comparisonSelect.value);
    });
  }

  economicRecapComparisonState = normalizeComparisonForAsOf(
    economicRecapComparisonState,
    economicRecapAsOfState.year,
    economicRecapAsOfState.quarter,
    economicRecapAsOfState.month
  );
  syncEconomicRecapAsOfControls();
  syncEconomicRecapAsOfUrl();
}

wireEconomicRecapAsOfToolbar();

const indicatorInfoBubble = document.getElementById("indicator-info-bubble");
const economicRecapTableBody = document.querySelector(
  ".economic-table-scroll tbody"
);
let activeIndicatorInfoBubbleRow = null;
if (indicatorInfoBubble && economicRecapTableBody) {
  economicRecapTableBody.addEventListener("mouseover", (event) => {
    // Source column owns the docs URL link — no methodology bubble there.
    if (isSourceCellTarget(event.target)) {
      hideIndicatorInfoBubble();
      return;
    }
    const row = event.target.closest("tr.indicator-row");
    if (!row || !economicRecapTableBody.contains(row)) {
      return;
    }
    if (row === activeIndicatorInfoBubbleRow) {
      return;
    }
    const record = getIndicatorBubbleRecord(row);
    if (!record) {
      return;
    }
    activeIndicatorInfoBubbleRow = row;
    indicatorInfoBubble.innerHTML = buildIndicatorInfoBubbleHtml(record, row);
    indicatorInfoBubble.hidden = false;
    indicatorInfoBubble.setAttribute("aria-hidden", "false");
    positionIndicatorInfoBubble(indicatorInfoBubble, event);
  });
  economicRecapTableBody.addEventListener("mousemove", (event) => {
    if (isSourceCellTarget(event.target)) {
      hideIndicatorInfoBubble();
      return;
    }
    if (indicatorInfoBubble.hidden) {
      return;
    }
    const row = event.target.closest("tr.indicator-row");
    if (!row) {
      return;
    }
    positionIndicatorInfoBubble(indicatorInfoBubble, event);
  });
  economicRecapTableBody.addEventListener("mouseout", (event) => {
    const row = event.target.closest("tr.indicator-row");
    if (!row) {
      return;
    }
    const nextRow = event.relatedTarget
      ? event.relatedTarget.closest("tr.indicator-row")
      : null;
    if (nextRow === row && !isSourceCellTarget(event.relatedTarget)) {
      return;
    }
    if (activeIndicatorInfoBubbleRow === row) {
      hideIndicatorInfoBubble();
    }
  });
}
