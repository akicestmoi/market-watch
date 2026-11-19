// ==========================================
// Load Django context data
// ==========================================
const dropdownValues = window.dropdownValuesJSON;
const economicData = window.economicDataJSON;
const compositionPanels = Array.isArray(window.compositionPanelsJSON)
  ? window.compositionPanelsJSON
  : [];
const industryProfitabilityPanels = Array.isArray(
  window.industryProfitabilityPanelsJSON
)
  ? window.industryProfitabilityPanelsJSON
  : [];
const tradeRankingPanels = Array.isArray(window.tradeRankingPanelsJSON)
  ? window.tradeRankingPanelsJSON
  : [];
const categories = window.categoriesJSON;
const selectedValuesRaw = window.selectedValuesJSON || {};
const currentRegion = window.currentRegion;

// Store chart instances
const chartInstances = {};

const CHART_SERIES_MODES = new Set([
  "Raw",
  "MoM",
  "QoQ",
  "QoQy",
  "YoY",
  "vsGDP",
  "YTDvsGDP",
  "YTDRaw",
  "YTDYoY",
  "Rel QoQ",
  "Rel YoY",
  "Contr QoQ",
  "Contr YoY",
  "YTDRelQoQ",
  "YTDRelYoY",
  "YTDContrQoQ",
  "YTDContrYoY",
]);
const FLOW_YTD_CHART_MODES = ["YTDvsGDP", "YTDRaw", "YTDYoY"];
const FLOW_COMPONENT_YTD_REL_CONTR_CHART_MODES = [
  "YTDRelQoQ",
  "YTDRelYoY",
  "YTDContrQoQ",
  "YTDContrYoY",
];
const FLOW_COMPONENT_REL_CONTR_CHART_MODES = [
  "Rel QoQ",
  "Rel YoY",
  "Contr QoQ",
  "Contr YoY",
];
// DERIVED financing account still offers FLOW-style YTD modes on charts.
const EXTRA_YTD_CHART_INDICATOR_NAMES = new Set([
  "Government Financing Account",
]);
const FIXED_YTD_VS_GDP_CHART_INDICATOR_NAMES = new Set([
  "Annual Government Expenditures",
]);
const FIXED_YTD_REL_YOY_CHART_INDICATOR_NAMES = new Set([
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

function getFixedChartModeForSeriesLabel(seriesLabel) {
  const name = String(seriesLabel || "").split("|").pop();
  if (
    name === "Output Gap" ||
    name === "Unemployment Rate" ||
    name === "INSEE Quarterly Unemployment Rate"
  ) {
    return "Raw";
  }
  if (FIXED_YTD_VS_GDP_CHART_INDICATOR_NAMES.has(name)) {
    return "YTDvsGDP";
  }
  if (FIXED_YTD_REL_YOY_CHART_INDICATOR_NAMES.has(name)) {
    return "YTDRelYoY";
  }
  return null;
}

const CHART_SERIES_MODE_LABELS = {
  Raw: "Raw",
  MoM: "MoM",
  QoQ: "QoQ",
  QoQy: "QoQy",
  YoY: "YoY",
  vsGDP: "vsGDP",
  YTDvsGDP: "YTDvsGDP",
  YTDRaw: "YTDRaw",
  YTDYoY: "YTDYoY",
  "Rel QoQ": "Rel QoQ",
  "Rel YoY": "Rel YoY",
  "Contr QoQ": "Contr QoQ",
  "Contr YoY": "Contr YoY",
  YTDRelQoQ: "YTDRelQoQ",
  YTDRelYoY: "YTDRelYoY",
  YTDContrQoQ: "YTDContrQoQ",
  YTDContrYoY: "YTDContrYoY",
};

const measureTypeBySeriesKey = {};
const expansionRelationBySeriesKey = {};
if (dropdownValues && dropdownValues.indicators_by_category_subcategory) {
  dropdownValues.indicators_by_category_subcategory.forEach((item) => {
    (item.indicators || []).forEach((ind) => {
      if (ind.series_label) {
        measureTypeBySeriesKey[ind.series_label] = ind.measure_type || "";
        expansionRelationBySeriesKey[ind.series_label] =
          ind.expansion_relation || "";
      }
    });
  });
}

function doesSeriesSupportFlowYtdModes(seriesKey) {
  const measureType = measureTypeBySeriesKey[seriesKey];
  return (
    measureType === "FLOW" ||
    measureType === "DERIVED" ||
    EXTRA_YTD_CHART_INDICATOR_NAMES.has(seriesKey)
  );
}

function doesSeriesSupportFlowComponentRelContrModes(seriesKey) {
  const measureType = measureTypeBySeriesKey[seriesKey];
  return (
    expansionRelationBySeriesKey[seriesKey] === "COMPONENT" &&
    (measureType === "FLOW" || measureType === "DERIVED")
  );
}

function listModeOptionsForSeries(seriesKey) {
  const modeOptions = ["Raw", "MoM", "QoQ", "QoQy", "YoY"];
  if (supportsVsGdpBySeriesKey[seriesKey]) {
    modeOptions.unshift("vsGDP");
  }
  if (doesSeriesSupportFlowYtdModes(seriesKey)) {
    modeOptions.push(...FLOW_YTD_CHART_MODES);
  }
  if (doesSeriesSupportFlowComponentRelContrModes(seriesKey)) {
    modeOptions.push(...FLOW_COMPONENT_REL_CONTR_CHART_MODES);
    modeOptions.push(...FLOW_COMPONENT_YTD_REL_CONTR_CHART_MODES);
  }
  return modeOptions;
}

function normalizeMode(mode) {
  const trimmed = (mode || "Raw").trim();
  return CHART_SERIES_MODES.has(trimmed) ? trimmed : "Raw";
}

// Series key (``GDP`` / ``DE|GDP``) → DB default_mode from dropdown payload.
const defaultModeBySeriesKey = {};
if (dropdownValues && dropdownValues.indicators_by_category_subcategory) {
  dropdownValues.indicators_by_category_subcategory.forEach((item) => {
    (item.indicators || []).forEach((indicator) => {
      if (indicator.series_label) {
        defaultModeBySeriesKey[indicator.series_label] = normalizeMode(
          indicator.default_mode
        );
      }
    });
  });
}

function getDefaultModeForSeriesKey(seriesKey) {
  return defaultModeBySeriesKey[seriesKey] || "Raw";
}

function parseIndicatorEntry(raw) {
  // Wire format: [Location|]seriesLabel[|MODE]. Location stays on ``seriesLabel``
  // for Cross-Region checkbox keys (``DE|GDP``); mode is peeled off separately.
  // Missing MODE uses the indicator's DB default_mode from the dropdown.
  const text = (raw || "").trim();
  if (!text) {
    return null;
  }
  const tokens = text.split("|").map((part) => part.trim()).filter(Boolean);
  let mode = null;
  if (tokens.length && CHART_SERIES_MODES.has(tokens[tokens.length - 1])) {
    mode = normalizeMode(tokens.pop());
  }
  if (!tokens.length) {
    return null;
  }
  const seriesKey = tokens.join("|");
  // Fixed Raw series — ignore any wired growth mode.
  if (
    seriesKey === "Output Gap" ||
    seriesKey.endsWith("|Output Gap") ||
    seriesKey === "Unemployment Rate" ||
    seriesKey.endsWith("|Unemployment Rate") ||
    seriesKey === "INSEE Quarterly Unemployment Rate" ||
    seriesKey.endsWith("|INSEE Quarterly Unemployment Rate")
  ) {
    mode = "Raw";
  } else if (!mode) {
    mode = getDefaultModeForSeriesKey(seriesKey);
  }
  return { seriesLabel: seriesKey, mode, encoded: `${seriesKey}|${mode}` };
}

function encodeIndicatorEntry(seriesLabel, mode) {
  // ``seriesLabel`` may already be a Cross-Region series key (``DE|Real GDP``).
  return `${seriesLabel}|${normalizeMode(mode)}`;
}

function getSeriesDomId(seriesKey) {
  return String(seriesKey || "").replace(/\|/g, "__");
}

// Parse selectedValues - query params come as strings, need to parse lists
const selectedValues = {};
for (const [key, value] of Object.entries(selectedValuesRaw)) {
  if (key === "region" || key === "period_window") {
    selectedValues[key] = value;
  } else if (key.endsWith("_indicator")) {
    // Parse list from string (could be JSON array string or comma-separated)
    let entries = [];
    if (typeof value === "string") {
      try {
        const parsed = JSON.parse(value);
        entries = Array.isArray(parsed) ? parsed : [parsed];
      } catch (e) {
        entries = value.includes(",")
          ? value.split(",").map((v) => v.trim())
          : value
            ? [value]
            : [];
      }
    } else if (Array.isArray(value)) {
      entries = value;
    } else if (value) {
      entries = [value];
    }
    selectedValues[key] = entries
      .map(parseIndicatorEntry)
      .filter(Boolean)
      .map((entry) => entry.encoded);
  } else {
    selectedValues[key] = value;
  }
}

// Helper to get region value (lowercase) from region label
function getRegionValue(regionLabel) {
  const regionMapping = {
    "United States": "us",
    France: "fr",
    Japan: "jp",
    "Cross-Region": "cross",
  };
  return regionMapping[regionLabel] || regionLabel.toLowerCase();
}

function getLabelString(label) {
  if (typeof label === "string") {
    return label;
  }
  if (label && label.label) {
    return String(label.label);
  }
  return String(label);
}

function getSafeName(label) {
  return getLabelString(label).toLowerCase().replace(/\s+/g, "_");
}

function getChartSlotKey(category, subcategory) {
  return `${getSafeName(category)}__${getSafeName(subcategory)}`;
}

// Convert economicData list to objects keyed by category__subcategory
const economicDataByChartSlot = {};
const valueAxisLabelByChartSlot = {};
if (Array.isArray(economicData)) {
  economicData.forEach((item) => {
    const slotKey = getChartSlotKey(item.category, item.subcategory);
    economicDataByChartSlot[slotKey] = item.category_data || [];
    valueAxisLabelByChartSlot[slotKey] = item.value_axis_label || "Data Value";
  });
}

// Convert indicators_by_category_subcategory for dropdowns / section layout
const indicatorsByChartSlotMap = {};
const displayNameBySeriesLabel = {};
const descriptionBySeriesKey = {};
const comparabilityWarningBySeriesKey = {};
const supportsVsGdpBySeriesKey = {};
const chartSlotsByCategory = {};
if (dropdownValues && dropdownValues.indicators_by_category_subcategory) {
  dropdownValues.indicators_by_category_subcategory.forEach((item) => {
    const categoryStr = getLabelString(item.category);
    const subcategoryStr = getLabelString(item.subcategory);
    const slotKey = getChartSlotKey(categoryStr, subcategoryStr);
    const indicators = item.indicators || [];
    indicatorsByChartSlotMap[slotKey] = indicators.map((ind) => ind.series_label);
    indicators.forEach((ind) => {
      if (ind.series_label && ind.name) {
        displayNameBySeriesLabel[ind.series_label] = ind.name;
      }
      if (ind.series_label) {
        descriptionBySeriesKey[ind.series_label] = ind.description || "";
        comparabilityWarningBySeriesKey[ind.series_label] =
          ind.comparability_warning || "";
        supportsVsGdpBySeriesKey[ind.series_label] = Boolean(ind.supports_vs_gdp);
        measureTypeBySeriesKey[ind.series_label] = ind.measure_type || "";
      }
    });
    if (!chartSlotsByCategory[categoryStr]) {
      chartSlotsByCategory[categoryStr] = [];
    }
    chartSlotsByCategory[categoryStr].push({
      category: categoryStr,
      subcategory: subcategoryStr,
      slotKey,
      hasIndicators: indicators.length > 0,
    });
  });
}

const availableCrossRegionCountries = Array.isArray(
  window.crossRegionCountriesJSON
)
  ? window.crossRegionCountriesJSON
  : [];
const selectedCountriesRaw = Array.isArray(window.selectedCountriesJSON)
  ? window.selectedCountriesJSON
  : [];
let pendingCountries = [...selectedCountriesRaw];

const ECONOMIC_CHARTS_SCROLL_KEY = "economicChartsScrollY";

function navigatePreservingScroll(params) {
  /** Keep the current scroll offset across chart filter reloads. */
  sessionStorage.setItem(ECONOMIC_CHARTS_SCROLL_KEY, String(window.scrollY));
  window.location.search = params.toString();
}

function restorePreservedScroll() {
  const rawScrollY = sessionStorage.getItem(ECONOMIC_CHARTS_SCROLL_KEY);
  if (rawScrollY == null) {
    return;
  }
  sessionStorage.removeItem(ECONOMIC_CHARTS_SCROLL_KEY);
  const scrollY = Number(rawScrollY);
  if (!Number.isFinite(scrollY)) {
    return;
  }
  window.scrollTo(0, scrollY);
}

// ==========================================
// Region Button Handling
// ==========================================

const REGION_CODE_TO_LABEL = {
  US: "United States",
  FR: "France",
  JP: "Japan",
  CROSS: "Cross-Region",
};

/**
 * Fixed series palette (50). Adjacent entries jump across the wheel so ranked
 * side-by-side series never sit on near shades of the same hue.
 */
const CHART_SERIES_COLORS = [
  "rgb(153, 102, 255)", // purple
  "rgb(255, 159, 64)", // orange
  "rgb(34, 197, 94)", // green
  "rgb(54, 162, 235)", // blue
  "rgb(255, 99, 132)", // pink
  "rgb(75, 192, 192)", // teal
  "rgb(120, 53, 15)", // brown
  "rgb(255, 206, 86)", // yellow
  "rgb(220, 38, 38)", // red
  "rgb(14, 165, 233)", // sky
  "rgb(132, 204, 22)", // lime
  "rgb(168, 85, 247)", // violet
  "rgb(245, 158, 11)", // amber
  "rgb(6, 182, 212)", // cyan
  "rgb(244, 63, 94)", // rose
  "rgb(22, 163, 74)", // forest
  "rgb(37, 99, 235)", // royal blue
  "rgb(234, 179, 8)", // gold
  "rgb(219, 39, 119)", // magenta
  "rgb(13, 148, 136)", // deep teal
  "rgb(249, 115, 22)", // vivid orange
  "rgb(99, 102, 241)", // indigo
  "rgb(101, 163, 13)", // olive lime
  "rgb(190, 24, 93)", // deep rose
  "rgb(8, 145, 178)", // ocean
  "rgb(202, 138, 4)", // mustard
  "rgb(124, 58, 237)", // deep violet
  "rgb(21, 128, 61)", // deep green
  "rgb(239, 68, 68)", // bright red
  "rgb(2, 132, 199)", // steel blue
  "rgb(163, 230, 53)", // chartreuse
  "rgb(192, 38, 211)", // fuchsia
  "rgb(180, 83, 9)", // rust
  "rgb(45, 212, 191)", // mint
  "rgb(225, 29, 72)", // crimson
  "rgb(59, 130, 246)", // bright blue
  "rgb(74, 222, 128)", // light green
  "rgb(147, 51, 234)", // bright purple
  "rgb(251, 146, 60)", // light orange
  "rgb(20, 184, 166)", // aqua
  "rgb(244, 114, 182)", // light pink
  "rgb(161, 98, 7)", // dark gold
  "rgb(67, 56, 202)", // deep indigo
  "rgb(190, 242, 100)", // pale lime
  "rgb(157, 23, 77)", // wine
  "rgb(7, 89, 133)", // navy teal
  "rgb(253, 224, 71)", // pale yellow
  "rgb(126, 34, 206)", // grape
  "rgb(4, 120, 87)", // emerald
  "rgb(248, 113, 113)", // salmon
];

function getChartSeriesColor(index) {
  const colorCount = CHART_SERIES_COLORS.length;
  const safeIndex = ((index % colorCount) + colorCount) % colorCount;
  return CHART_SERIES_COLORS[safeIndex];
}

/** Stable Cross-Region country colours (independent of subcategory). */
const CROSS_REGION_COUNTRY_COLORS = {
  "United States": "rgb(124, 58, 237)", // purple
  France: "rgb(37, 99, 235)", // medium-dark blue
  Japan: "rgb(220, 38, 38)", // red
  Germany: "rgb(15, 23, 42)", // black
  Spain: "rgb(234, 179, 8)", // yellow
  Italy: "rgb(21, 128, 61)", // medium-dark green
  Europe: "rgb(120, 53, 15)", // brown (unspecified)
};

/** Fixed main color per subcategory (shared across regions). */
function getSubcategoryOrderIndex(category, subcategory) {
  const slots = chartSlotsByCategory[getLabelString(category)] || [];
  const subcategoryLabel = getLabelString(subcategory);
  return slots.findIndex((slot) => slot.subcategory === subcategoryLabel);
}

function getSubcategoryMainColor(category, subcategory) {
  const orderIndex = getSubcategoryOrderIndex(category, subcategory);
  const colorIndex = orderIndex >= 0 ? orderIndex : 0;
  return getChartSeriesColor(colorIndex);
}

function getSeriesColor(category, subcategory, seriesIndex, seriesLabel) {
  if (currentRegion === "Cross-Region") {
    const countryColor = CROSS_REGION_COUNTRY_COLORS[seriesLabel];
    if (countryColor) {
      return countryColor;
    }
    return getChartSeriesColor(seriesIndex);
  }
  const mainColor = getSubcategoryMainColor(category, subcategory);
  if (seriesIndex === 0) {
    return mainColor;
  }
  const extras = CHART_SERIES_COLORS.filter((color) => color !== mainColor);
  return extras[(seriesIndex - 1) % extras.length];
}

function buildColorByRankedLabel(rankedLabels) {
  const colorByLabel = {};
  rankedLabels.forEach((label, index) => {
    colorByLabel[label] = getChartSeriesColor(index);
  });
  return colorByLabel;
}

function initializeRegionButtons() {
  const regionButtons = document.querySelectorAll(".region-btn");

  regionButtons.forEach((btn) => {
    const regionCode = btn.dataset.region;
    const regionLabel = REGION_CODE_TO_LABEL[regionCode];
    if (!regionLabel) {
      return;
    }

    if (regionLabel === currentRegion) {
      btn.classList.add("active");
    }

    btn.addEventListener("click", () => {
      const params = new URLSearchParams(window.location.search);
      const regionParam =
        regionCode === "CROSS" ? "Cross-Region" : regionCode;
      params.set("region", regionParam);
      navigatePreservingScroll(params);
    });
  });
}

// ==========================================
// Helper Functions
// ==========================================

function getSelectedIndicatorsForChart(category, subcategory) {
  const regionValue = getRegionValue(currentRegion);
  const key = `${regionValue}_${getSafeName(category)}_${getSafeName(subcategory)}_indicator`;
  const indicators = selectedValues[key] || [];
  return indicators.filter((ind) => ind && ind !== "");
}

function getModeForSeriesLabel(category, subcategory, seriesLabel) {
  const entry = getSelectedIndicatorsForChart(category, subcategory)
    .map(parseIndicatorEntry)
    .find((item) => item && item.seriesLabel === seriesLabel);
  return entry ? entry.mode : getDefaultModeForSeriesKey(seriesLabel);
}

function getDefaultIndicatorForChart(category, subcategory) {
  const indicators = getSelectedIndicatorsForChart(category, subcategory);
  return indicators.length > 0 ? indicators[0] : "";
}

function initializePeriodWindowSelect() {
  const select = document.getElementById("period-window");
  if (!select) return;
  select.addEventListener("change", () => {
    const params = new URLSearchParams(window.location.search);
    params.set("period_window", select.value);
    navigatePreservingScroll(params);
  });
}

function syncCountriesDropdownButton() {
  const dropdownButton = document.getElementById("countries-dropdown-button");
  if (!dropdownButton) {
    return;
  }
  const selectedCount = pendingCountries.length;
  dropdownButton.textContent =
    selectedCount > 0
      ? `${selectedCount} countr${selectedCount > 1 ? "ies" : "y"} selected`
      : "-- Select Countries --";
}

function initializeCountriesMultiselect() {
  const countriesSection = document.getElementById("countries-section");
  const dropdownWrapper = document.getElementById("countries-multiselect");
  const dropdownButton = document.getElementById("countries-dropdown-button");
  const dropdownContent = document.getElementById("countries-dropdown-content");
  const checkboxList = document.getElementById("countries-checkbox-list");
  const selectAllBtn = document.getElementById("countries-select-all");
  const unselectAllBtn = document.getElementById("countries-unselect-all");
  const applyBtn = document.getElementById("countries-apply");
  const cancelBtn = document.getElementById("countries-cancel");
  if (
    !countriesSection ||
    !dropdownWrapper ||
    !dropdownButton ||
    !dropdownContent ||
    !checkboxList ||
    !selectAllBtn ||
    !unselectAllBtn ||
    !applyBtn ||
    !cancelBtn
  ) {
    return;
  }

  const isCrossRegion = currentRegion === "Cross-Region";
  countriesSection.hidden = !isCrossRegion;
  renderCrossRegionCountryLegend();
  if (!isCrossRegion) {
    return;
  }

  checkboxList.innerHTML = "";
  availableCrossRegionCountries.forEach((country) => {
    const checkboxItem = document.createElement("div");
    checkboxItem.className = "multiselect-checkbox-item";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = `country-${country.code}`;
    checkbox.value = country.code;
    checkbox.checked = pendingCountries.includes(country.code);
    checkbox.addEventListener("change", () => {
      pendingCountries = Array.from(
        checkboxList.querySelectorAll("input[type='checkbox']:checked")
      ).map((input) => input.value);
      syncCountriesDropdownButton();
      renderCrossRegionCountryLegend();
    });
    const label = document.createElement("label");
    label.htmlFor = checkbox.id;
    label.textContent = country.label;
    checkboxItem.appendChild(checkbox);
    checkboxItem.appendChild(label);
    checkboxList.appendChild(checkboxItem);
  });
  syncCountriesDropdownButton();

  dropdownButton.addEventListener("click", (event) => {
    event.stopPropagation();
    const isOpen = dropdownContent.style.display === "block";
    dropdownContent.style.display = isOpen ? "none" : "block";
    dropdownButton.classList.toggle("active", !isOpen);
  });
  selectAllBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    checkboxList
      .querySelectorAll("input[type='checkbox']")
      .forEach((checkbox) => {
        checkbox.checked = true;
      });
    pendingCountries = availableCrossRegionCountries.map(
      (country) => country.code
    );
    syncCountriesDropdownButton();
    renderCrossRegionCountryLegend();
  });
  unselectAllBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    checkboxList
      .querySelectorAll("input[type='checkbox']")
      .forEach((checkbox) => {
        checkbox.checked = false;
      });
    pendingCountries = [];
    syncCountriesDropdownButton();
    renderCrossRegionCountryLegend();
  });
  applyBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    if (pendingCountries.length === 0) {
      pendingCountries = availableCrossRegionCountries.map(
        (country) => country.code
      );
    }
    const params = new URLSearchParams(window.location.search);
    params.set("countries", pendingCountries.join(","));
    navigatePreservingScroll(params);
  });
  cancelBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    pendingCountries = [...selectedCountriesRaw];
    checkboxList
      .querySelectorAll("input[type='checkbox']")
      .forEach((checkbox) => {
        checkbox.checked = pendingCountries.includes(checkbox.value);
      });
    syncCountriesDropdownButton();
    renderCrossRegionCountryLegend();
    dropdownContent.style.display = "none";
    dropdownButton.classList.remove("active");
  });
  document.addEventListener("click", (event) => {
    if (!dropdownWrapper.contains(event.target)) {
      dropdownContent.style.display = "none";
      dropdownButton.classList.remove("active");
    }
  });
}

// ==========================================
// Chart Creation
// ==========================================

function createEconomicChart(category, subcategory, data, colorByLabel) {
  const allPeriods = new Set();
  data.forEach((item) => {
    allPeriods.add(item.period);
  });
  const sortedPeriods = Array.from(allPeriods).sort((a, b) =>
    a.localeCompare(b)
  );

  const uniqueIndicatorNames = [...new Set(data.map((item) => item.indicator_name))];
  const datasets = [];

  uniqueIndicatorNames.forEach((indicatorName, index) => {
    const indicatorData = data.filter((item) => item.indicator_name === indicatorName);
    const dataMap = {};
    let unitLabel = "";
    indicatorData.forEach((d) => {
      dataMap[d.period] = d.data_value;
      if (!unitLabel && d.unit_label) {
        unitLabel = d.unit_label;
      }
    });
    const values = sortedPeriods.map((period) => {
      return dataMap[period] !== undefined ? dataMap[period] : null;
    });

    const seriesColor =
      colorByLabel &&
      Object.prototype.hasOwnProperty.call(colorByLabel, indicatorName)
        ? colorByLabel[indicatorName]
        : getSeriesColor(category, subcategory, index, indicatorName);
    datasets.push({
      label: indicatorName,
      data: values,
      unitLabel,
      borderColor: seriesColor,
      backgroundColor: seriesColor.replace("rgb(", "rgba(").replace(")", ", 0.1)"),
      tension: 0.3,
      fill: false,
      pointRadius: 3,
      spanGaps: false,
    });
  });

  return {
    labels: sortedPeriods,
    datasets: datasets,
  };
}

function renderCrossRegionCountryLegend() {
  const legendHost = document.getElementById("cross-region-country-legend");
  if (!legendHost) {
    return;
  }
  const isCrossRegion = currentRegion === "Cross-Region";
  legendHost.hidden = !isCrossRegion;
  legendHost.innerHTML = "";
  if (!isCrossRegion) {
    return;
  }
  const selectedCountryCodes = new Set(
    pendingCountries.length > 0 ? pendingCountries : selectedCountriesRaw
  );
  const countriesToShow = availableCrossRegionCountries.filter((country) =>
    selectedCountryCodes.has(country.code)
  );
  countriesToShow.forEach((country) => {
    const legendItem = document.createElement("div");
    legendItem.className = "cross-region-country-legend-item";
    const swatch = document.createElement("span");
    swatch.className = "cross-region-country-legend-swatch";
    swatch.style.backgroundColor =
      CROSS_REGION_COUNTRY_COLORS[country.label] ||
      CHART_SERIES_COLORS[0];
    const label = document.createElement("span");
    label.className = "cross-region-country-legend-label";
    label.textContent = country.label;
    legendItem.appendChild(swatch);
    legendItem.appendChild(label);
    legendHost.appendChild(legendItem);
  });
}

function getLineChartTooltipCallbacks() {
  return {
    label(context) {
      const value = context.parsed.y;
      if (value === null || value === undefined) {
        return context.dataset.label || "";
      }
      const unitLabel = context.dataset.unitLabel || "";
      const formattedValue =
        typeof value === "number" ? value.toLocaleString(undefined, {
          maximumFractionDigits: 2,
        }) : value;
      if (!unitLabel) {
        return `${context.dataset.label}: ${formattedValue}`;
      }
      return `${context.dataset.label}: ${formattedValue} ${unitLabel}`;
    },
  };
}

function buildSelectedSeriesDescriptions(selectedEntries) {
  const descriptions = [];
  const seenSeriesLabels = new Set();
  selectedEntries.forEach((rawEntry) => {
    const parsed = parseIndicatorEntry(rawEntry);
    if (!parsed || !parsed.seriesLabel || seenSeriesLabels.has(parsed.seriesLabel)) {
      return;
    }
    seenSeriesLabels.add(parsed.seriesLabel);
    const displayName = displayNameBySeriesLabel[parsed.seriesLabel] || parsed.seriesLabel;
    const description = descriptionBySeriesKey[parsed.seriesLabel] || "";
    descriptions.push({
      name: displayName,
      description: description.trim(),
    });
  });
  return descriptions;
}

function buildCrossRegionChartTitle(subcategory, selectedEntries) {
  // Title carries the series label and mode so the legend can stay country-only.
  const indicatorParts = [];
  const seenKeys = new Set();
  selectedEntries.forEach((rawEntry) => {
    const parsed = parseIndicatorEntry(rawEntry);
    if (!parsed || !parsed.seriesLabel) {
      return;
    }
    const dedupeKey = `${parsed.seriesLabel}|${parsed.mode}`;
    if (seenKeys.has(dedupeKey)) {
      return;
    }
    seenKeys.add(dedupeKey);
    const seriesDisplayLabel =
      displayNameBySeriesLabel[parsed.seriesLabel] ||
      String(parsed.seriesLabel).split("|").pop();
    if (parsed.mode === "Raw") {
      indicatorParts.push(seriesDisplayLabel);
      return;
    }
    const modeLabel = CHART_SERIES_MODE_LABELS[parsed.mode] || parsed.mode;
    indicatorParts.push(`${seriesDisplayLabel} (${modeLabel})`);
  });
  if (indicatorParts.length === 0) {
    return subcategory;
  }
  return `${subcategory}: ${indicatorParts.join(", ")}`;
}

function positionChartInfoPanel(infoPanel, infoButton) {
  const viewportPadding = 8;
  const maxWidth = Math.min(352, window.innerWidth - viewportPadding * 2);
  infoPanel.style.position = "fixed";
  infoPanel.style.width = `${maxWidth}px`;
  infoPanel.style.maxWidth = `${maxWidth}px`;
  infoPanel.style.left = "0px";
  infoPanel.style.top = "0px";
  infoPanel.style.right = "auto";
  infoPanel.style.bottom = "auto";

  const buttonRect = infoButton.getBoundingClientRect();
  const panelRect = infoPanel.getBoundingClientRect();
  let left = buttonRect.right - panelRect.width;
  let top = buttonRect.bottom + 6;
  if (left < viewportPadding) {
    left = viewportPadding;
  }
  if (left + panelRect.width > window.innerWidth - viewportPadding) {
    left = Math.max(
      viewportPadding,
      window.innerWidth - viewportPadding - panelRect.width
    );
  }
  if (top + panelRect.height > window.innerHeight - viewportPadding) {
    top = Math.max(
      viewportPadding,
      buttonRect.top - panelRect.height - 6
    );
  }
  infoPanel.style.left = `${left}px`;
  infoPanel.style.top = `${top}px`;
}

function collectComparabilityWarnings(selectedEntries) {
  /** Unique non-empty Cross-Region comparability notes for the selection. */
  const warnings = [];
  const seenWarnings = new Set();
  (selectedEntries || []).forEach((rawEntry) => {
    const parsed = parseIndicatorEntry(rawEntry);
    if (!parsed || !parsed.seriesLabel) {
      return;
    }
    const seriesLabel = parsed.seriesLabel;
    const warning = (comparabilityWarningBySeriesKey[seriesLabel] || "").trim();
    if (!warning || seenWarnings.has(warning)) {
      return;
    }
    seenWarnings.add(warning);
    warnings.push({ name: seriesLabel, warning });
  });
  return warnings;
}

function attachChartInfoButton(chartCard, descriptions, selectedEntries) {
  const warnings = collectComparabilityWarnings(selectedEntries);
  if ((!descriptions || descriptions.length === 0) && warnings.length === 0) {
    return;
  }

  const infoWrapper = document.createElement("div");
  infoWrapper.className = "chart-info-wrapper";

  if (warnings.length > 0) {
    const warningButton = document.createElement("button");
    warningButton.type = "button";
    warningButton.className = "chart-comparability-warning";
    warningButton.setAttribute(
      "aria-label",
      "Cross-region comparability warning"
    );
    warningButton.textContent = "!";
    const tooltip = document.createElement("div");
    tooltip.className = "chart-comparability-warning-tooltip";
    tooltip.textContent = warnings
      .map((entry) => `${entry.name}: ${entry.warning}`)
      .join("\n\n");
    warningButton.appendChild(tooltip);
    infoWrapper.appendChild(warningButton);
  }

  if (descriptions && descriptions.length > 0) {
    const infoButton = document.createElement("button");
    infoButton.type = "button";
    infoButton.className = "chart-info-button";
    infoButton.setAttribute("aria-label", "Show selected series descriptions");
    infoButton.textContent = "i";

    const infoPanel = document.createElement("div");
    infoPanel.className = "chart-info-panel";
    infoPanel.hidden = true;

    descriptions.forEach((entry) => {
      const block = document.createElement("div");
      block.className = "chart-info-entry";
      const title = document.createElement("div");
      title.className = "chart-info-entry-title";
      title.textContent = entry.name;
      block.appendChild(title);
      const body = document.createElement("div");
      body.className = "chart-info-entry-body";
      body.textContent = entry.description || "No description available.";
      block.appendChild(body);
      infoPanel.appendChild(block);
    });

    infoButton.addEventListener("click", (event) => {
      event.stopPropagation();
      const willOpen = infoPanel.hidden;
      document.querySelectorAll(".chart-info-panel").forEach((panel) => {
        panel.hidden = true;
      });
      if (willOpen) {
        infoPanel.hidden = false;
        positionChartInfoPanel(infoPanel, infoButton);
      }
    });

    document.addEventListener("click", (event) => {
      if (!infoWrapper.contains(event.target)) {
        infoPanel.hidden = true;
      }
    });

    infoWrapper.appendChild(infoButton);
    infoWrapper.appendChild(infoPanel);
  }

  const chartHeader = chartCard.querySelector(".chart-header");
  if (chartHeader) {
    chartHeader.appendChild(infoWrapper);
  } else {
    chartCard.appendChild(infoWrapper);
  }
}

// ==========================================
// Multi-Select Dropdown Management
// ==========================================

const pendingSelections = {};

function applyCrossRegionSingleIndicatorSelection(
  category,
  subcategory,
  seriesLabel,
  mode
) {
  const regionValue = getRegionValue(currentRegion);
  const key = `${regionValue}_${getSafeName(category)}_${getSafeName(subcategory)}_indicator`;
  const params = new URLSearchParams(window.location.search);
  const fixedMode = getFixedChartModeForSeriesLabel(seriesLabel);
  const selectedMode = fixedMode || normalizeMode(mode);
  params.set(key, encodeIndicatorEntry(seriesLabel, selectedMode));
  navigatePreservingScroll(params);
}

function updateCrossRegionIndicatorSelection(
  category,
  subcategory,
  selectionContainer
) {
  const slotKey = getChartSlotKey(category, subcategory);
  const indicatorSelectionContainer =
    selectionContainer ||
    document.getElementById(`${slotKey}-indicator-selection`);
  if (!indicatorSelectionContainer) return;

  const availableIndicators = indicatorsByChartSlotMap[slotKey] || [];
  const selectedIndicators = getSelectedIndicatorsForChart(category, subcategory);
  const defaultIndicator = getDefaultIndicatorForChart(category, subcategory);
  const activeRaw =
    selectedIndicators[0] || defaultIndicator || availableIndicators[0] || "";
  const activeParsed = parseIndicatorEntry(activeRaw);
  const activeSeriesLabel = activeParsed ? activeParsed.seriesLabel : "";
  const activeMode = activeParsed
    ? activeParsed.mode
    : getDefaultModeForSeriesKey(activeSeriesLabel);

  indicatorSelectionContainer.innerHTML = "";
  indicatorSelectionContainer.className =
    "indicator-selection-container cross-region-indicator-selection";

  const typeLabel = document.createElement("label");
  typeLabel.className = "cross-region-select-label";
  typeLabel.textContent = "Indicator";
  typeLabel.htmlFor = `${slotKey}-cross-region-type`;

  const typeSelect = document.createElement("select");
  typeSelect.id = `${slotKey}-cross-region-type`;
  typeSelect.className = "chart-select cross-region-type-select";
  availableIndicators.forEach((seriesLabel) => {
    const option = document.createElement("option");
    option.value = seriesLabel;
    option.textContent =
      displayNameBySeriesLabel[seriesLabel] || seriesLabel;
    typeSelect.appendChild(option);
  });
  if (activeSeriesLabel) {
    typeSelect.value = activeSeriesLabel;
  }

  const modeSelect = document.createElement("select");
  modeSelect.id = `${slotKey}-cross-region-mode`;
  modeSelect.className = "chart-select cross-region-mode-select";
  modeSelect.setAttribute("aria-label", "Display mode");

  function refreshModeOptions() {
    const selectedSeriesLabel = typeSelect.value;
    const fixedMode = getFixedChartModeForSeriesLabel(selectedSeriesLabel);
    modeSelect.innerHTML = "";
    if (fixedMode !== null) {
      const option = document.createElement("option");
      option.value = fixedMode;
      option.textContent = CHART_SERIES_MODE_LABELS[fixedMode] || fixedMode;
      modeSelect.appendChild(option);
      modeSelect.value = fixedMode;
      modeSelect.disabled = true;
      return;
    }
    modeSelect.disabled = false;
    listModeOptionsForSeries(selectedSeriesLabel).forEach((mode) => {
      const option = document.createElement("option");
      option.value = mode;
      option.textContent = CHART_SERIES_MODE_LABELS[mode] || mode;
      modeSelect.appendChild(option);
    });
    const preferredMode =
      selectedSeriesLabel === activeSeriesLabel
        ? activeMode
        : getDefaultModeForSeriesKey(selectedSeriesLabel);
    modeSelect.value = preferredMode;
  }

  refreshModeOptions();
  typeSelect.onchange = () => {
    refreshModeOptions();
    applyCrossRegionSingleIndicatorSelection(
      category,
      subcategory,
      typeSelect.value,
      modeSelect.value
    );
  };
  modeSelect.onchange = () => {
    applyCrossRegionSingleIndicatorSelection(
      category,
      subcategory,
      typeSelect.value,
      modeSelect.value
    );
  };

  const controlsRow = document.createElement("div");
  controlsRow.className = "cross-region-indicator-controls";
  controlsRow.appendChild(typeLabel);
  controlsRow.appendChild(typeSelect);
  controlsRow.appendChild(modeSelect);
  indicatorSelectionContainer.appendChild(controlsRow);
}

function updateIndicatorSelection(category, subcategory, selectionContainer) {
  if (currentRegion === "Cross-Region") {
    updateCrossRegionIndicatorSelection(category, subcategory, selectionContainer);
    return;
  }

  const slotKey = getChartSlotKey(category, subcategory);
  const indicatorSelectionContainer =
    selectionContainer ||
    document.getElementById(`${slotKey}-indicator-selection`);
  if (!indicatorSelectionContainer) return;

  const availableIndicators = indicatorsByChartSlotMap[slotKey] || [];
  const availableIndicatorsFormatted = availableIndicators.map((seriesLabel) => ({
    series_label: seriesLabel,
    name: displayNameBySeriesLabel[seriesLabel] || seriesLabel,
  }));

  const selectedIndicators = getSelectedIndicatorsForChart(category, subcategory);
  const defaultIndicator = getDefaultIndicatorForChart(category, subcategory);

  const indicatorsToCheck =
    selectedIndicators.length > 0
      ? selectedIndicators
      : defaultIndicator
        ? [defaultIndicator]
        : [];
  const seriesLabelsToCheck = indicatorsToCheck
    .map(parseIndicatorEntry)
    .filter(Boolean)
    .map((entry) => entry.seriesLabel);

  pendingSelections[slotKey] = [...indicatorsToCheck];
  indicatorSelectionContainer.innerHTML = "";
  indicatorSelectionContainer.className = "indicator-selection-container";

  const dropdownWrapper = document.createElement("div");
  dropdownWrapper.className = "multiselect-dropdown-wrapper";

  const dropdownButton = document.createElement("button");
  dropdownButton.className = "multiselect-dropdown-button";
  dropdownButton.type = "button";
  const selectedCount = indicatorsToCheck.length;
  dropdownButton.textContent =
    selectedCount > 0
      ? `${selectedCount} indicator${selectedCount > 1 ? "s" : ""} selected`
      : "-- Select Indicators --";
  dropdownButton.onclick = () => toggleDropdown(category, subcategory);

  const dropdownContent = document.createElement("div");
  dropdownContent.id = `${slotKey}-dropdown-content`;
  dropdownContent.className = "multiselect-dropdown-content";
  dropdownContent.style.display = "none";

  const actionButtons = document.createElement("div");
  actionButtons.className = "multiselect-action-buttons";

  const selectAllBtn = document.createElement("button");
  selectAllBtn.className = "multiselect-action-btn";
  selectAllBtn.textContent = "Select All";
  selectAllBtn.onclick = (e) => {
    e.stopPropagation();
    selectAllInDropdown(category, subcategory);
  };

  const unselectAllBtn = document.createElement("button");
  unselectAllBtn.className = "multiselect-action-btn";
  unselectAllBtn.textContent = "Unselect All";
  unselectAllBtn.onclick = (e) => {
    e.stopPropagation();
    unselectAllInDropdown(category, subcategory);
  };

  actionButtons.appendChild(selectAllBtn);
  actionButtons.appendChild(unselectAllBtn);
  dropdownContent.appendChild(actionButtons);

  const checkboxList = document.createElement("div");
  checkboxList.className = "multiselect-checkbox-list";

  availableIndicatorsFormatted.forEach((indicator) => {
    const seriesDomId = getSeriesDomId(indicator.series_label);
    const checkboxItem = document.createElement("div");
    checkboxItem.className = "multiselect-checkbox-item";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = `${slotKey}-indicator-${seriesDomId}`;
    checkbox.value = indicator.series_label;
    checkbox.checked = seriesLabelsToCheck.includes(indicator.series_label);
    checkbox.onchange = () => updatePendingSelection(category, subcategory);

    const label = document.createElement("label");
    label.htmlFor = checkbox.id;
    label.textContent = indicator.name;
    label.onclick = (e) => e.stopPropagation();

    checkboxItem.appendChild(checkbox);
    checkboxItem.appendChild(label);
    // Fixed-mode series — no mode control.
    if (getFixedChartModeForSeriesLabel(indicator.series_label) === null) {
      const modeSelect = document.createElement("select");
      modeSelect.className = "multiselect-mode-select";
      modeSelect.id = `${slotKey}-mode-${seriesDomId}`;
      modeSelect.setAttribute("aria-label", `Mode for ${indicator.name}`);
      listModeOptionsForSeries(indicator.series_label).forEach((mode) => {
        const option = document.createElement("option");
        option.value = mode;
        option.textContent = CHART_SERIES_MODE_LABELS[mode] || mode;
        modeSelect.appendChild(option);
      });
      modeSelect.value = getModeForSeriesLabel(
        category,
        subcategory,
        indicator.series_label
      );
      modeSelect.onclick = (e) => e.stopPropagation();
      modeSelect.onchange = (e) => {
        e.stopPropagation();
        updatePendingSelection(category, subcategory);
      };
      checkboxItem.appendChild(modeSelect);
    }
    checkboxList.appendChild(checkboxItem);
  });

  dropdownContent.appendChild(checkboxList);

  const validationButtons = document.createElement("div");
  validationButtons.className = "multiselect-validation-buttons";

  const applyBtn = document.createElement("button");
  applyBtn.className = "multiselect-apply-btn";
  applyBtn.textContent = "Apply";
  applyBtn.onclick = (e) => {
    e.stopPropagation();
    applyIndicatorSelection(category, subcategory);
  };

  const cancelBtn = document.createElement("button");
  cancelBtn.className = "multiselect-cancel-btn";
  cancelBtn.textContent = "Cancel";
  cancelBtn.onclick = (e) => {
    e.stopPropagation();
    cancelIndicatorSelection(category, subcategory);
  };

  validationButtons.appendChild(applyBtn);
  validationButtons.appendChild(cancelBtn);
  dropdownContent.appendChild(validationButtons);

  dropdownWrapper.appendChild(dropdownButton);
  dropdownWrapper.appendChild(dropdownContent);
  indicatorSelectionContainer.appendChild(dropdownWrapper);

  document.addEventListener("click", (e) => {
    if (!dropdownWrapper.contains(e.target)) {
      dropdownContent.style.display = "none";
      dropdownButton.classList.remove("active");
    }
  });
}

function toggleDropdown(category, subcategory) {
  const slotKey = getChartSlotKey(category, subcategory);
  const dropdownContent = document.getElementById(`${slotKey}-dropdown-content`);
  const dropdownButton = document.querySelector(
    `#${slotKey}-indicator-selection .multiselect-dropdown-button`
  );

  if (dropdownContent && dropdownButton) {
    const isOpen = dropdownContent.style.display === "block";
    dropdownContent.style.display = isOpen ? "none" : "block";
    dropdownButton.classList.toggle("active", !isOpen);
  }
}

function selectAllInDropdown(category, subcategory) {
  const slotKey = getChartSlotKey(category, subcategory);
  const availableIndicators = indicatorsByChartSlotMap[slotKey] || [];

  availableIndicators.forEach((seriesLabel) => {
    const checkbox = document.getElementById(
      `${slotKey}-indicator-${getSeriesDomId(seriesLabel)}`
    );
    if (checkbox) {
      checkbox.checked = true;
    }
  });

  updatePendingSelection(category, subcategory);
}

function unselectAllInDropdown(category, subcategory) {
  const slotKey = getChartSlotKey(category, subcategory);
  const availableIndicators = indicatorsByChartSlotMap[slotKey] || [];

  availableIndicators.forEach((seriesLabel) => {
    const checkbox = document.getElementById(
      `${slotKey}-indicator-${getSeriesDomId(seriesLabel)}`
    );
    if (checkbox) {
      checkbox.checked = false;
    }
  });

  updatePendingSelection(category, subcategory);
}

function updatePendingSelection(category, subcategory) {
  const slotKey = getChartSlotKey(category, subcategory);
  const availableIndicators = indicatorsByChartSlotMap[slotKey] || [];

  const selected = [];
  availableIndicators.forEach((seriesLabel) => {
    const seriesDomId = getSeriesDomId(seriesLabel);
    const checkbox = document.getElementById(`${slotKey}-indicator-${seriesDomId}`);
    const modeSelect = document.getElementById(`${slotKey}-mode-${seriesDomId}`);
    if (checkbox && checkbox.checked) {
      const fixedMode = getFixedChartModeForSeriesLabel(seriesLabel);
      const mode = fixedMode
        ? fixedMode
        : modeSelect
          ? modeSelect.value
          : getDefaultModeForSeriesKey(seriesLabel);
      selected.push(encodeIndicatorEntry(seriesLabel, mode));
    }
  });

  pendingSelections[slotKey] = selected;
}

function applyIndicatorSelection(category, subcategory) {
  const regionValue = getRegionValue(currentRegion);
  const key = `${regionValue}_${getSafeName(category)}_${getSafeName(subcategory)}_indicator`;
  const slotKey = getChartSlotKey(category, subcategory);

  const params = new URLSearchParams(window.location.search);
  const selectedIndicators = pendingSelections[slotKey] || [];

  if (selectedIndicators.length === 0) {
    params.set(key, "");
  } else {
    params.set(key, selectedIndicators.join(","));
  }

  navigatePreservingScroll(params);
}

function cancelIndicatorSelection(category, subcategory) {
  const slotKey = getChartSlotKey(category, subcategory);
  const selectedIndicators = getSelectedIndicatorsForChart(category, subcategory);
  const defaultIndicator = getDefaultIndicatorForChart(category, subcategory);

  const indicatorsToCheck =
    selectedIndicators.length > 0
      ? selectedIndicators
      : defaultIndicator
        ? [defaultIndicator]
        : [];

  pendingSelections[slotKey] = [...indicatorsToCheck];
  const parsed = indicatorsToCheck.map(parseIndicatorEntry).filter(Boolean);
  const seriesLabelsToCheck = parsed.map((entry) => entry.seriesLabel);
  const modeBySeriesLabel = {};
  parsed.forEach((entry) => {
    modeBySeriesLabel[entry.seriesLabel] = entry.mode;
  });

  const availableIndicators = indicatorsByChartSlotMap[slotKey] || [];
  availableIndicators.forEach((seriesLabel) => {
    const seriesDomId = getSeriesDomId(seriesLabel);
    const checkbox = document.getElementById(`${slotKey}-indicator-${seriesDomId}`);
    const modeSelect = document.getElementById(`${slotKey}-mode-${seriesDomId}`);
    if (checkbox) {
      checkbox.checked = seriesLabelsToCheck.includes(seriesLabel);
    }
    if (modeSelect) {
      modeSelect.value =
        modeBySeriesLabel[seriesLabel] || getDefaultModeForSeriesKey(seriesLabel);
    }
  });

  toggleDropdown(category, subcategory);
}

// ==========================================
// Render Charts
// ==========================================

function renderChartCard(category, subcategory, slotKey) {
  const categoryData = economicDataByChartSlot[slotKey] || [];
  const valueAxisLabel = valueAxisLabelByChartSlot[slotKey] || "Data Value";
  const isCrossRegion = currentRegion === "Cross-Region";
  const selectedIndicators = getSelectedIndicatorsForChart(category, subcategory);
  const defaultIndicator = getDefaultIndicatorForChart(category, subcategory);

  let finalSelectedIndicators = selectedIndicators;
  if (finalSelectedIndicators.length === 0 && defaultIndicator) {
    finalSelectedIndicators = [defaultIndicator];
  } else if (finalSelectedIndicators.length === 0) {
    const availableIndicators = indicatorsByChartSlotMap[slotKey] || [];
    if (availableIndicators.length > 0) {
      finalSelectedIndicators = [availableIndicators[0]];
    }
  }
  if (isCrossRegion && finalSelectedIndicators.length > 1) {
    // Cross-Region shows one series label across countries.
    finalSelectedIndicators = finalSelectedIndicators.slice(0, 1);
  }

  const chartCard = document.createElement("div");
  chartCard.className = "chart-card";

  const chartHeader = document.createElement("div");
  chartHeader.className = "chart-header";
  const chartTitle = document.createElement("h3");
  chartTitle.textContent = isCrossRegion
    ? buildCrossRegionChartTitle(subcategory, finalSelectedIndicators)
    : subcategory;
  chartHeader.appendChild(chartTitle);

  const chartWrapper = document.createElement("div");
  chartWrapper.className = "chart-wrapper";
  const canvas = document.createElement("canvas");
  canvas.id = `chart-${slotKey}`;
  chartWrapper.appendChild(canvas);

  const indicatorSelectionContainer = document.createElement("div");
  indicatorSelectionContainer.id = `${slotKey}-indicator-selection`;
  indicatorSelectionContainer.className = "indicator-selection-container";

  chartCard.appendChild(chartHeader);
  attachChartInfoButton(
    chartCard,
    buildSelectedSeriesDescriptions(finalSelectedIndicators),
    finalSelectedIndicators
  );
  chartCard.appendChild(chartWrapper);
  chartCard.appendChild(indicatorSelectionContainer);

  if (finalSelectedIndicators.length > 0) {
    chartWrapper.style.display = "flex";
    indicatorSelectionContainer.style.display = "block";
    // Pass the container directly — card may not be in the document yet.
    updateIndicatorSelection(category, subcategory, indicatorSelectionContainer);

    if (categoryData.length > 0) {
      const chartData = createEconomicChart(category, subcategory, categoryData);
      const ctx = canvas.getContext("2d");

      if (chartInstances[slotKey]) {
        chartInstances[slotKey].destroy();
      }

      chartInstances[slotKey] = new Chart(ctx, {
        type: "line",
        data: chartData,
        options: {
          plugins: {
            legend: {
              // Cross-Region uses the shared country legend under the top toolbar.
              display: !isCrossRegion,
              position: "top",
            },
            tooltip: {
              callbacks: getLineChartTooltipCallbacks(),
            },
          },
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: {
              title: {
                display: true,
                text: "Period",
              },
            },
            y: {
              title: {
                display: true,
                text: valueAxisLabel,
              },
            },
          },
        },
      });
    } else if (chartInstances[slotKey]) {
      chartInstances[slotKey].destroy();
      delete chartInstances[slotKey];
    }
  } else {
    chartWrapper.style.display = "none";
    indicatorSelectionContainer.style.display = "none";
    const noDataMessage = document.createElement("p");
    noDataMessage.className = "no-data-message";
    noDataMessage.textContent = "No data available for this subcategory";
    chartCard.appendChild(noDataMessage);
  }

  return chartCard;
}

const compositionStateByPanel = {};

function getCompositionLocationData(panel, locationCode) {
  const byLocation = panel.by_location || {};
  return byLocation[locationCode] || null;
}

function getCompositionState(panel) {
  const panelId = panel.panel_id;
  const existingState = compositionStateByPanel[panelId];
  if (existingState) {
    return existingState;
  }
  const availableLocations = Array.isArray(panel.available_locations)
    ? panel.available_locations
    : [];
  const defaultLocation =
    typeof panel.default_location === "string" &&
    panel.by_location &&
    panel.by_location[panel.default_location]
      ? panel.default_location
      : availableLocations.length > 0
        ? availableLocations[0].code
        : "";
  const locationData = getCompositionLocationData(panel, defaultLocation);
  const defaultMode =
    locationData && typeof locationData.default_breakdown_mode === "string"
      ? locationData.default_breakdown_mode
      : "Share";
  const defaultSeriesLabels =
    locationData && Array.isArray(locationData.default_selected_series_labels)
      ? [...locationData.default_selected_series_labels]
      : [];
  const defaultPieGranularity =
    locationData && typeof locationData.default_pie_granularity === "string"
      ? locationData.default_pie_granularity
      : "quarter";
  compositionStateByPanel[panelId] = {
    locationCode: defaultLocation,
    breakdownMode: defaultMode,
    selectedSeriesLabels: defaultSeriesLabels,
    pieGranularity: defaultPieGranularity,
    piePeriod: "",
  };
  return compositionStateByPanel[panelId];
}

function filterCompositionLineData(lineData, selectedSeriesLabels) {
  const selectedSeriesLabelSet = new Set(selectedSeriesLabels);
  return (lineData || []).filter((point) =>
    selectedSeriesLabelSet.has(point.indicator_name)
  );
}

function renderCompositionLineChart(
  panel,
  canvas,
  locationData,
  selectedSeriesLabels,
  breakdownMode
) {
  const lineDataByMode = locationData.line_data_by_mode || {};
  const lineData = lineDataByMode[breakdownMode] || [];
  const axisLabelByMode = locationData.value_axis_label_by_mode || {};
  const chartData = createEconomicChart(
    panel.category,
    panel.title,
    filterCompositionLineData(lineData, selectedSeriesLabels)
  );
  const slotKey = `composition-line-${panel.panel_id}`;
  if (chartInstances[slotKey]) {
    chartInstances[slotKey].destroy();
  }
  chartInstances[slotKey] = new Chart(canvas.getContext("2d"), {
    type: "line",
    data: chartData,
    options: {
      plugins: {
        legend: {
          display: true,
          position: "top",
        },
        tooltip: {
          callbacks: getLineChartTooltipCallbacks(),
        },
      },
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          title: {
            display: true,
            text: "Period",
          },
        },
        y: {
          title: {
            display: true,
            text: axisLabelByMode[breakdownMode] || "Share (%)",
          },
        },
      },
    },
  });
}

function formatCompositionSharePercent(share) {
  if (typeof share !== "number") {
    return String(share);
  }
  return `${share.toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
}

const compositionPieSliceLabelsPlugin = {
  id: "compositionPieSliceLabels",
  afterDatasetsDraw(chart) {
    const dataset = chart.data.datasets[0];
    if (!dataset || !Array.isArray(dataset.data)) {
      return;
    }
    const total = dataset.data.reduce(
      (sum, value) => sum + (typeof value === "number" ? value : 0),
      0
    );
    if (total <= 0) {
      return;
    }
    const meta = chart.getDatasetMeta(0);
    if (!meta || !Array.isArray(meta.data)) {
      return;
    }
    const { ctx } = chart;
    ctx.save();
    ctx.font = "bold 12px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = "#f1f5f9";
    // Soft dark edge so pale slices still show the white percent.
    ctx.strokeStyle = "rgba(15, 23, 42, 0.45)";
    ctx.lineWidth = 3;
    ctx.lineJoin = "round";
    meta.data.forEach((arc, index) => {
      if (!arc || arc.hidden) {
        return;
      }
      const value = dataset.data[index];
      if (typeof value !== "number" || value <= 0) {
        return;
      }
      const shareOfPie = value / total;
      // Skip labels on tiny slices so text stays readable.
      if (shareOfPie < 0.04) {
        return;
      }
      const angle = (arc.startAngle + arc.endAngle) / 2;
      const innerRadius =
        typeof arc.innerRadius === "number" ? arc.innerRadius : 0;
      const outerRadius =
        typeof arc.outerRadius === "number" ? arc.outerRadius : 0;
      if (!(outerRadius > 0)) {
        return;
      }
      // Pull labels toward the outer rim (further from the pie center).
      const radius = innerRadius + (outerRadius - innerRadius) * 0.62;
      const labelX = arc.x + Math.cos(angle) * radius;
      const labelY = arc.y + Math.sin(angle) * radius;
      const label = formatCompositionSharePercent(value);
      ctx.strokeText(label, labelX, labelY);
      ctx.fillText(label, labelX, labelY);
    });
    ctx.restore();
  },
};

function getCompositionPieSlices(locationData, pieGranularity, periodLabel) {
  const pieByGranularity = locationData.pie_by_period_by_granularity || {};
  const pieByPeriod = pieByGranularity[pieGranularity] || {};
  return pieByPeriod[periodLabel] || [];
}

function renderCompositionPieChart(
  panel,
  canvas,
  locationData,
  pieGranularity,
  periodLabel
) {
  const slices = getCompositionPieSlices(
    locationData,
    pieGranularity,
    periodLabel
  );
  const slotKey = `composition-pie-${panel.panel_id}`;
  if (chartInstances[slotKey]) {
    chartInstances[slotKey].destroy();
  }
  const labels = slices.map((slice) => slice.name);
  const values = slices.map((slice) => slice.share);
  const colors = labels.map((_label, index) => getChartSeriesColor(index));
  chartInstances[slotKey] = new Chart(canvas.getContext("2d"), {
    type: "pie",
    data: {
      labels,
      datasets: [
        {
          data: values,
          backgroundColor: colors,
          borderColor: "#ffffff",
          borderWidth: 1,
        },
      ],
    },
    options: {
      plugins: {
        legend: {
          display: true,
          position: "right",
        },
        tooltip: {
          callbacks: {
            label(context) {
              const value = context.parsed;
              return `${context.label}: ${formatCompositionSharePercent(value)}`;
            },
          },
        },
      },
      responsive: true,
      maintainAspectRatio: false,
    },
    plugins: [compositionPieSliceLabelsPlugin],
  });
}

function buildCompositionSelectionDropdown(panel, state, chartCard, onApply) {
  const selectionContainer = document.createElement("div");
  selectionContainer.className = "indicator-selection-container";
  selectionContainer.id = `composition-${panel.panel_id}-indicator-selection`;

  const dropdownWrapper = document.createElement("div");
  dropdownWrapper.className = "multiselect-dropdown-wrapper";

  const dropdownButton = document.createElement("button");
  dropdownButton.className = "multiselect-dropdown-button";
  dropdownButton.type = "button";

  const dropdownContent = document.createElement("div");
  dropdownContent.className = "multiselect-dropdown-content";
  dropdownContent.style.display = "none";

  const actionButtons = document.createElement("div");
  actionButtons.className = "multiselect-action-buttons";
  const selectAllBtn = document.createElement("button");
  selectAllBtn.className = "multiselect-action-btn";
  selectAllBtn.type = "button";
  selectAllBtn.textContent = "Select All";
  const unselectAllBtn = document.createElement("button");
  unselectAllBtn.className = "multiselect-action-btn";
  unselectAllBtn.type = "button";
  unselectAllBtn.textContent = "Unselect All";
  actionButtons.appendChild(selectAllBtn);
  actionButtons.appendChild(unselectAllBtn);
  dropdownContent.appendChild(actionButtons);

  const checkboxList = document.createElement("div");
  checkboxList.className = "multiselect-checkbox-list";
  dropdownContent.appendChild(checkboxList);

  const validationButtons = document.createElement("div");
  validationButtons.className = "multiselect-validation-buttons";
  const applyBtn = document.createElement("button");
  applyBtn.className = "multiselect-apply-btn";
  applyBtn.type = "button";
  applyBtn.textContent = "Apply";
  const cancelBtn = document.createElement("button");
  cancelBtn.className = "multiselect-cancel-btn";
  cancelBtn.type = "button";
  cancelBtn.textContent = "Cancel";
  validationButtons.appendChild(applyBtn);
  validationButtons.appendChild(cancelBtn);
  dropdownContent.appendChild(validationButtons);

  function syncCheckboxState() {
    const selectedCount = state.selectedSeriesLabels.length;
    dropdownButton.textContent =
      selectedCount > 0
        ? `${selectedCount} indicator${selectedCount > 1 ? "s" : ""} selected`
        : "-- Select Indicators --";
    checkboxList.querySelectorAll("input[type='checkbox']").forEach((checkbox) => {
      checkbox.checked = state.selectedSeriesLabels.includes(checkbox.value);
    });
  }

  function rebuildInfoButton(locationData) {
    const existing = chartCard.querySelector(".chart-info-wrapper");
    if (existing) {
      existing.remove();
    }
    const descriptionBySeriesLabel = {};
    (locationData.multiselect_indicators || []).forEach((indicator) => {
      descriptionBySeriesLabel[indicator.series_label] = indicator.description || "";
    });
    attachChartInfoButton(
      chartCard,
      state.selectedSeriesLabels.map((seriesLabel) => ({
        name: seriesLabel,
        description: descriptionBySeriesLabel[seriesLabel] || "",
      })),
      state.selectedSeriesLabels
    );
  }

  function rebuildCheckboxList(locationData) {
    checkboxList.innerHTML = "";
    (locationData.multiselect_indicators || []).forEach((indicator) => {
      const checkboxItem = document.createElement("div");
      checkboxItem.className = "multiselect-checkbox-item";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = indicator.series_label;
      checkbox.id = `composition-${panel.panel_id}-${getSeriesDomId(indicator.series_label)}`;
      const label = document.createElement("label");
      label.htmlFor = checkbox.id;
      label.textContent = indicator.name;
      label.onclick = (event) => event.stopPropagation();
      checkboxItem.appendChild(checkbox);
      checkboxItem.appendChild(label);
      checkboxList.appendChild(checkboxItem);
    });
    syncCheckboxState();
    rebuildInfoButton(locationData);
  }

  dropdownButton.onclick = () => {
    const isOpen = dropdownContent.style.display === "block";
    dropdownContent.style.display = isOpen ? "none" : "block";
    dropdownButton.classList.toggle("active", !isOpen);
    if (!isOpen) {
      syncCheckboxState();
    }
  };

  selectAllBtn.onclick = (event) => {
    event.stopPropagation();
    checkboxList.querySelectorAll("input[type='checkbox']").forEach((checkbox) => {
      checkbox.checked = true;
    });
  };
  unselectAllBtn.onclick = (event) => {
    event.stopPropagation();
    checkboxList.querySelectorAll("input[type='checkbox']").forEach((checkbox) => {
      checkbox.checked = false;
    });
  };
  applyBtn.onclick = (event) => {
    event.stopPropagation();
    const selectedSeriesLabels = [];
    checkboxList.querySelectorAll("input[type='checkbox']").forEach((checkbox) => {
      if (checkbox.checked) {
        selectedSeriesLabels.push(checkbox.value);
      }
    });
    state.selectedSeriesLabels = selectedSeriesLabels;
    syncCheckboxState();
    onApply();
    dropdownContent.style.display = "none";
    dropdownButton.classList.remove("active");
  };
  cancelBtn.onclick = (event) => {
    event.stopPropagation();
    syncCheckboxState();
    dropdownContent.style.display = "none";
    dropdownButton.classList.remove("active");
  };

  document.addEventListener("click", (event) => {
    if (!dropdownWrapper.contains(event.target)) {
      dropdownContent.style.display = "none";
      dropdownButton.classList.remove("active");
    }
  });

  dropdownWrapper.appendChild(dropdownButton);
  dropdownWrapper.appendChild(dropdownContent);
  selectionContainer.appendChild(dropdownWrapper);
  return {
    selectionContainer,
    rebuildCheckboxList,
    rebuildInfoButton,
  };
}

function renderCompositionCard(panel, sectionGrid) {
  const state = getCompositionState(panel);
  const card = document.createElement("div");
  card.className = "chart-card composition-card";

  const header = document.createElement("div");
  header.className = "chart-header";
  const cardTitle = document.createElement("h3");
  cardTitle.textContent = panel.title;
  header.appendChild(cardTitle);
  card.appendChild(header);

  const sharedControls = document.createElement("div");
  sharedControls.className = "composition-card-controls";
  const availableLocations = Array.isArray(panel.available_locations)
    ? panel.available_locations
    : [];
  let locationSelect = null;
  if (availableLocations.length > 1) {
    const locationLabel = document.createElement("label");
    locationLabel.className = "composition-control-label";
    locationLabel.textContent = "Country:";
    locationLabel.setAttribute("for", `composition-location-${panel.panel_id}`);
    locationSelect = document.createElement("select");
    locationSelect.id = `composition-location-${panel.panel_id}`;
    locationSelect.className = "chart-select";
    availableLocations.forEach((locationOption) => {
      const option = document.createElement("option");
      option.value = locationOption.code;
      option.textContent = locationOption.label;
      locationSelect.appendChild(option);
    });
    locationSelect.value = state.locationCode;
    sharedControls.appendChild(locationLabel);
    sharedControls.appendChild(locationSelect);
    card.appendChild(sharedControls);
  }

  const modeLabel = document.createElement("label");
  modeLabel.className = "composition-control-label";
  modeLabel.textContent = "Mode:";
  modeLabel.setAttribute("for", `composition-mode-${panel.panel_id}`);
  const modeSelect = document.createElement("select");
  modeSelect.id = `composition-mode-${panel.panel_id}`;
  modeSelect.className = "chart-select";

  const chartsRow = document.createElement("div");
  chartsRow.className = "composition-charts-row";

  const linePanel = document.createElement("div");
  linePanel.className = "composition-chart-panel";
  const lineHeader = document.createElement("div");
  lineHeader.className = "composition-chart-header";
  const lineTitle = document.createElement("h4");
  lineTitle.textContent = panel.trend_title || "Trend";
  lineHeader.appendChild(lineTitle);
  const trendModeControls = document.createElement("div");
  trendModeControls.className = "composition-trend-mode-controls";
  trendModeControls.appendChild(modeLabel);
  trendModeControls.appendChild(modeSelect);
  lineHeader.appendChild(trendModeControls);
  linePanel.appendChild(lineHeader);
  const lineWrapper = document.createElement("div");
  lineWrapper.className = "chart-wrapper composition-line-wrapper";
  const lineCanvas = document.createElement("canvas");
  lineCanvas.id = `composition-line-${panel.panel_id}`;
  lineWrapper.appendChild(lineCanvas);
  linePanel.appendChild(lineWrapper);
  chartsRow.appendChild(linePanel);

  const piePanel = document.createElement("div");
  piePanel.className = "composition-chart-panel";
  const pieHeader = document.createElement("div");
  pieHeader.className = "composition-chart-header";
  const pieTitle = document.createElement("h4");
  pieTitle.textContent = panel.pie_title || "Share";
  pieHeader.appendChild(pieTitle);
  const periodControls = document.createElement("div");
  periodControls.className = "composition-period-controls";
  const granularityLabel = document.createElement("label");
  granularityLabel.className = "composition-period-label";
  granularityLabel.textContent = "By:";
  granularityLabel.setAttribute(
    "for",
    `composition-granularity-${panel.panel_id}`
  );
  const granularitySelect = document.createElement("select");
  granularitySelect.id = `composition-granularity-${panel.panel_id}`;
  granularitySelect.className = "chart-select composition-period-select";
  const periodLabel = document.createElement("label");
  periodLabel.className = "composition-period-label";
  periodLabel.setAttribute("for", `composition-period-${panel.panel_id}`);
  const periodSelect = document.createElement("select");
  periodSelect.id = `composition-period-${panel.panel_id}`;
  periodSelect.className = "chart-select composition-period-select";
  periodControls.appendChild(granularityLabel);
  periodControls.appendChild(granularitySelect);
  periodControls.appendChild(periodLabel);
  periodControls.appendChild(periodSelect);
  pieHeader.appendChild(periodControls);
  piePanel.appendChild(pieHeader);
  const pieWrapper = document.createElement("div");
  pieWrapper.className = "chart-wrapper composition-pie-wrapper";
  const pieCanvas = document.createElement("canvas");
  pieCanvas.id = `composition-pie-${panel.panel_id}`;
  pieWrapper.appendChild(pieCanvas);
  piePanel.appendChild(pieWrapper);
  chartsRow.appendChild(piePanel);

  card.appendChild(chartsRow);
  sectionGrid.appendChild(card);

  const selectionDropdown = buildCompositionSelectionDropdown(
    panel,
    state,
    card,
    () => {
      refreshCompositionCard();
    }
  );
  selectionDropdown.selectionContainer.classList.add(
    "composition-trend-indicator-selection"
  );
  linePanel.appendChild(selectionDropdown.selectionContainer);

  function syncModePlacement(locationData) {
    const modeInTrend = Boolean(locationData.mode_in_trend_panel);
    trendModeControls.style.display = modeInTrend ? "flex" : "none";
    if (!modeInTrend) {
      if (!sharedControls.parentElement) {
        card.insertBefore(sharedControls, chartsRow);
      }
      if (!sharedControls.contains(modeLabel)) {
        sharedControls.appendChild(modeLabel);
        sharedControls.appendChild(modeSelect);
      }
      sharedControls.style.display = "flex";
    } else if (availableLocations.length <= 1) {
      sharedControls.style.display = "none";
    }
  }

  function syncModeOptions(locationData) {
    const modes = Array.isArray(locationData.available_breakdown_modes)
      ? locationData.available_breakdown_modes
      : ["Share"];
    modeSelect.innerHTML = "";
    modes.forEach((mode) => {
      const option = document.createElement("option");
      option.value = mode;
      option.textContent = mode;
      modeSelect.appendChild(option);
    });
    if (!modes.includes(state.breakdownMode)) {
      state.breakdownMode = locationData.default_breakdown_mode || modes[0];
    }
    modeSelect.value = state.breakdownMode;
  }

  function syncGranularityOptions(locationData) {
    const granularities = Array.isArray(locationData.available_pie_granularities)
      ? locationData.available_pie_granularities
      : ["quarter"];
    granularitySelect.innerHTML = "";
    granularities.forEach((granularity) => {
      const option = document.createElement("option");
      option.value = granularity;
      option.textContent = granularity === "year" ? "Year" : "Quarter";
      granularitySelect.appendChild(option);
    });
    granularitySelect.style.display = granularities.length > 1 ? "" : "none";
    granularityLabel.style.display = granularities.length > 1 ? "" : "none";
    if (!granularities.includes(state.pieGranularity)) {
      state.pieGranularity =
        locationData.default_pie_granularity || granularities[0];
    }
    granularitySelect.value = state.pieGranularity;
  }

  function syncPeriodOptions(locationData) {
    const periodsByGranularity = locationData.periods_by_granularity || {};
    const periods = Array.isArray(periodsByGranularity[state.pieGranularity])
      ? periodsByGranularity[state.pieGranularity]
      : [];
    periodLabel.textContent =
      state.pieGranularity === "year" ? "Year:" : "Quarter:";
    periodSelect.innerHTML = "";
    periods.forEach((period) => {
      const option = document.createElement("option");
      option.value = period;
      option.textContent = period;
      periodSelect.appendChild(option);
    });
    // Periods are newest-first, so index 0 is the latest share snapshot.
    if (!periods.includes(state.piePeriod)) {
      state.piePeriod = periods.length > 0 ? periods[0] : "";
    }
    if (state.piePeriod) {
      periodSelect.value = state.piePeriod;
    }
  }

  function refreshCompositionCard() {
    const locationData = getCompositionLocationData(panel, state.locationCode);
    if (!locationData) {
      return;
    }
    syncModePlacement(locationData);
    syncModeOptions(locationData);
    syncGranularityOptions(locationData);
    syncPeriodOptions(locationData);
    selectionDropdown.rebuildCheckboxList(locationData);
    if (state.selectedSeriesLabels.length > 0) {
      renderCompositionLineChart(
        panel,
        lineCanvas,
        locationData,
        state.selectedSeriesLabels,
        state.breakdownMode
      );
    }
    if (state.piePeriod) {
      renderCompositionPieChart(
        panel,
        pieCanvas,
        locationData,
        state.pieGranularity,
        state.piePeriod
      );
    }
  }

  if (locationSelect) {
    locationSelect.addEventListener("change", () => {
      state.locationCode = locationSelect.value;
      const locationData = getCompositionLocationData(panel, state.locationCode);
      state.breakdownMode =
        (locationData && locationData.default_breakdown_mode) || "Share";
      state.selectedSeriesLabels =
        locationData && Array.isArray(locationData.default_selected_series_labels)
          ? [...locationData.default_selected_series_labels]
          : [];
      state.pieGranularity =
        (locationData && locationData.default_pie_granularity) || "quarter";
      state.piePeriod = "";
      refreshCompositionCard();
    });
  }
  modeSelect.addEventListener("change", () => {
    state.breakdownMode = modeSelect.value;
    refreshCompositionCard();
  });
  granularitySelect.addEventListener("change", () => {
    state.pieGranularity = granularitySelect.value;
    state.piePeriod = "";
    refreshCompositionCard();
  });
  periodSelect.addEventListener("change", () => {
    state.piePeriod = periodSelect.value;
    const locationData = getCompositionLocationData(panel, state.locationCode);
    if (locationData && state.piePeriod) {
      renderCompositionPieChart(
        panel,
        pieCanvas,
        locationData,
        state.pieGranularity,
        state.piePeriod
      );
    }
  });

  refreshCompositionCard();
}

const industryProfitabilityStateByPanel = {};

function getIndustryProfitabilityState(panel) {
  const panelId = panel.panel_id;
  const existingState = industryProfitabilityStateByPanel[panelId];
  if (
    existingState &&
    Object.prototype.hasOwnProperty.call(existingState, "asOfYear") &&
    Object.prototype.hasOwnProperty.call(existingState, "rankBy")
  ) {
    return existingState;
  }
  const availableYears = Array.isArray(panel.available_years)
    ? panel.available_years
    : [];
  // Available years are newest-first, so index 0 is the latest as-of year.
  const defaultYear =
    typeof panel.as_of_year === "number"
      ? panel.as_of_year
      : availableYears.length > 0
        ? availableYears[0]
        : null;
  const defaultRankBy =
    typeof panel.rank_by === "string" && panel.rank_by
      ? panel.rank_by
      : "turnover";
  industryProfitabilityStateByPanel[panelId] = {
    asOfYear: defaultYear,
    rankBy: defaultRankBy,
    lineTopN:
      typeof panel.line_top_n === "number" && panel.line_top_n > 0
        ? panel.line_top_n
        : 5,
    barTopN:
      typeof panel.bar_top_n === "number" && panel.bar_top_n > 0
        ? panel.bar_top_n
        : 20,
  };
  return industryProfitabilityStateByPanel[panelId];
}

function getIndustryValueAxisLabel(panel, rankBy) {
  if (rankBy === "margin") {
    return "%";
  }
  return panel.value_axis_label || "m";
}

function getIndustryMetricLabel(rankBy) {
  if (rankBy === "gva") {
    return "GVA";
  }
  if (rankBy === "margin") {
    return "Margin";
  }
  if (rankBy === "operating_profit") {
    return "Operating Profit";
  }
  return "Turnover";
}

function getIndustryChartTitles(rankBy) {
  const metricLabel = getIndustryMetricLabel(rankBy);
  return {
    cardTitle: `Industry ${metricLabel}`,
    lineTitle: "Trend",
    barTitle: "Ranking",
  };
}

function getIndustryObservationsForRankBy(panel, rankBy) {
  if (
    rankBy === "gva" &&
    Array.isArray(panel.contribution_observations) &&
    panel.contribution_observations.length > 0
  ) {
    return panel.contribution_observations;
  }
  return Array.isArray(panel.observations) ? panel.observations : [];
}

function getIndustryMetricValue(observation, rankBy) {
  const metricValue = observation[rankBy];
  return typeof metricValue === "number" ? metricValue : null;
}

function listRankedIndustryLabelsForYear(observations, asOfYear, rankBy) {
  const ranked = [];
  observations.forEach((observation) => {
    if (observation.year !== asOfYear) {
      return;
    }
    const metricValue = getIndustryMetricValue(observation, rankBy);
    if (metricValue === null) {
      return;
    }
    ranked.push({
      metricValue,
      industryLabel: observation.industry_label,
    });
  });
  ranked.sort((left, right) => right.metricValue - left.metricValue);
  return ranked.map((entry) => entry.industryLabel);
}

function listTopIndustryLabelsForYear(observations, asOfYear, topN, rankBy) {
  return listRankedIndustryLabelsForYear(observations, asOfYear, rankBy).slice(
    0,
    topN
  );
}

function getIndustryLatestYear(panel) {
  const availableYears = Array.isArray(panel.available_years)
    ? panel.available_years
    : [];
  // Available years are newest-first, so index 0 is the latest year.
  if (availableYears.length > 0) {
    return availableYears[0];
  }
  return typeof panel.as_of_year === "number" ? panel.as_of_year : null;
}

function listIndustryColorRankLabels(panel, state) {
  const observations = getIndustryObservationsForRankBy(panel, state.rankBy);
  const latestYear = getIndustryLatestYear(panel);
  // Ranking as-of year is canonical for colours; append trend-only labels after.
  const barRankedLabels = listRankedIndustryLabelsForYear(
    observations,
    state.asOfYear,
    state.rankBy
  );
  const lineRankedLabels =
    latestYear === null
      ? []
      : listRankedIndustryLabelsForYear(observations, latestYear, state.rankBy);
  const mergedLabels = [...barRankedLabels];
  lineRankedLabels.forEach((industryLabel) => {
    if (!mergedLabels.includes(industryLabel)) {
      mergedLabels.push(industryLabel);
    }
  });
  return mergedLabels;
}

function buildIndustryColorByLabel(panel, state) {
  return buildColorByRankedLabel(listIndustryColorRankLabels(panel, state));
}

function listDisplayedIndustryLabels(panel, state) {
  const observations = getIndustryObservationsForRankBy(panel, state.rankBy);
  const latestYear = getIndustryLatestYear(panel);
  const lineLabels =
    latestYear === null
      ? []
      : listTopIndustryLabelsForYear(
        observations,
        latestYear,
        state.lineTopN,
        state.rankBy
      );
  const barLabels = listTopIndustryLabelsForYear(
    observations,
    state.asOfYear,
    state.barTopN,
    state.rankBy
  );
  const displayedLabelSet = new Set([...lineLabels, ...barLabels]);
  return listIndustryColorRankLabels(panel, state).filter((industryLabel) =>
    displayedLabelSet.has(industryLabel)
  );
}

const INDUSTRY_LINE_HISTORY_YEARS_BY_PERIOD_WINDOW = {
  "1Y": 1,
  "3Y": 3,
  "5Y": 5,
  "10Y": 10,
  Max: null,
};

function getIndustryLineHistoryStartYear(latestYear) {
  const periodWindow = selectedValues.period_window || "10Y";
  const historyYears = Object.prototype.hasOwnProperty.call(
    INDUSTRY_LINE_HISTORY_YEARS_BY_PERIOD_WINDOW,
    periodWindow
  )
    ? INDUSTRY_LINE_HISTORY_YEARS_BY_PERIOD_WINDOW[periodWindow]
    : 10;
  if (historyYears === null) {
    return null;
  }
  // Same cutoff rule as economic chart period windows: keep years >= latest - N.
  return latestYear - historyYears;
}

function buildIndustryProfitabilityLineData(panel, lineTopN, rankBy) {
  const observations = getIndustryObservationsForRankBy(panel, rankBy);
  const latestYear = getIndustryLatestYear(panel);
  if (latestYear === null) {
    return [];
  }
  // Trend always ranks and ends on the latest available year (as-of is ranking-only).
  const topLabels = listTopIndustryLabelsForYear(
    observations,
    latestYear,
    lineTopN,
    rankBy
  );
  if (topLabels.length === 0) {
    return [];
  }
  const topLabelSet = new Set(topLabels);
  const historyStartYear = getIndustryLineHistoryStartYear(latestYear);
  const unitLabel = getIndustryValueAxisLabel(panel, rankBy);
  const lineData = [];
  observations.forEach((observation) => {
    if (!topLabelSet.has(observation.industry_label)) {
      return;
    }
    if (observation.year > latestYear) {
      return;
    }
    if (historyStartYear !== null && observation.year < historyStartYear) {
      return;
    }
    const metricValue = getIndustryMetricValue(observation, rankBy);
    if (metricValue === null) {
      return;
    }
    lineData.push({
      period: String(observation.year),
      data_value: metricValue,
      indicator_name: observation.industry_label,
      unit_label: unitLabel,
    });
  });
  lineData.sort((left, right) => {
    if (left.period === right.period) {
      return right.indicator_name.localeCompare(left.indicator_name);
    }
    return right.period.localeCompare(left.period);
  });
  return lineData;
}

function buildIndustryProfitabilityBarData(panel, asOfYear, barTopN, rankBy) {
  const observations = getIndustryObservationsForRankBy(panel, rankBy);
  const topLabels = listTopIndustryLabelsForYear(
    observations,
    asOfYear,
    barTopN,
    rankBy
  );
  const metricByLabel = {};
  observations.forEach((observation) => {
    if (observation.year !== asOfYear) {
      return;
    }
    if (!topLabels.includes(observation.industry_label)) {
      return;
    }
    const metricValue = getIndustryMetricValue(observation, rankBy);
    if (metricValue === null) {
      return;
    }
    metricByLabel[observation.industry_label] = metricValue;
  });
  const unitLabel = getIndustryValueAxisLabel(panel, rankBy);
  return topLabels
    .filter((industryLabel) => metricByLabel[industryLabel] !== undefined)
    .map((industryLabel) => ({
      period: String(asOfYear),
      data_value: metricByLabel[industryLabel],
      indicator_name: industryLabel,
      unit_label: unitLabel,
    }));
}

function formatIndustryChartValue(value, unitLabel) {
  if (typeof value !== "number") {
    return String(value);
  }
  const formatted = value.toLocaleString(undefined, {
    maximumFractionDigits: 1,
  });
  return unitLabel ? `${formatted} ${unitLabel}` : formatted;
}

function renderIndustryProfitabilityLineChart(
  panel,
  canvas,
  lineData,
  rankBy,
  colorByLabel
) {
  const valueAxisLabel = getIndustryValueAxisLabel(panel, rankBy);
  const titles = getIndustryChartTitles(rankBy);
  const chartData = createEconomicChart(
    panel.category,
    titles.lineTitle,
    lineData,
    colorByLabel
  );
  const slotKey = `industry-line-${panel.panel_id}`;
  if (chartInstances[slotKey]) {
    chartInstances[slotKey].destroy();
  }
  chartInstances[slotKey] = new Chart(canvas.getContext("2d"), {
    type: "line",
    data: chartData,
    options: {
      plugins: {
        legend: {
          display: false,
        },
        tooltip: {
          callbacks: getLineChartTooltipCallbacks(),
        },
      },
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          title: {
            display: true,
            text: "Year",
          },
        },
        y: {
          title: {
            display: true,
            text: valueAxisLabel,
          },
        },
      },
    },
  });
}

function truncateIndustryBarLabel(label, maxChars = 28) {
  const text = String(label || "");
  if (text.length <= maxChars) {
    return text;
  }
  return `${text.slice(0, Math.max(1, maxChars - 1))}…`;
}

function renderIndustryProfitabilityBarChart(
  panel,
  canvas,
  barData,
  rankBy,
  colorByLabel
) {
  const slotKey = `industry-bar-${panel.panel_id}`;
  if (chartInstances[slotKey]) {
    chartInstances[slotKey].destroy();
  }
  const valueAxisLabel = getIndustryValueAxisLabel(panel, rankBy);
  const titles = getIndustryChartTitles(rankBy);
  const fullLabels = barData.map((point) => point.indicator_name);
  const labels = fullLabels.map((label) => truncateIndustryBarLabel(label));
  const values = barData.map((point) => point.data_value);
  const colors = fullLabels.map(
    (industryLabel, index) =>
      (colorByLabel && colorByLabel[industryLabel]) || getChartSeriesColor(index)
  );
  chartInstances[slotKey] = new Chart(canvas.getContext("2d"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: titles.barTitle,
          data: values,
          backgroundColor: colors,
          borderColor: colors,
          borderWidth: 1,
        },
      ],
    },
    options: {
      indexAxis: "y",
      plugins: {
        legend: {
          display: false,
        },
        tooltip: {
          callbacks: {
            title(tooltipItems) {
              if (!tooltipItems.length) {
                return "";
              }
              const dataIndex = tooltipItems[0].dataIndex;
              return fullLabels[dataIndex] || "";
            },
            label(context) {
              return formatIndustryChartValue(context.parsed.x, valueAxisLabel);
            },
          },
        },
      },
      responsive: true,
      maintainAspectRatio: false,
      layout: {
        padding: {
          left: 4,
          right: 8,
          top: 4,
          bottom: 4,
        },
      },
      scales: {
        x: {
          title: {
            display: true,
            text: valueAxisLabel,
          },
        },
        y: {
          ticks: {
            autoSkip: false,
            callback(_value, index) {
              return labels[index] || "";
            },
          },
        },
      },
    },
  });
}

function parsePositiveIntegerInput(rawValue, fallback) {
  const parsed = Number.parseInt(String(rawValue), 10);
  if (!Number.isFinite(parsed) || parsed < 1) {
    return fallback;
  }
  return parsed;
}

function buildIndustrySharedControls(panel, state) {
  const controls = document.createElement("div");
  controls.className = "industry-profitability-card-controls";

  const rankLabel = document.createElement("label");
  rankLabel.className = "industry-profitability-control-label";
  rankLabel.textContent = "By:";
  rankLabel.setAttribute("for", `industry-rank-${panel.panel_id}`);
  const rankSelect = document.createElement("select");
  rankSelect.id = `industry-rank-${panel.panel_id}`;
  rankSelect.className = "chart-select industry-profitability-rank-select";
  const rankByOptions = Array.isArray(panel.rank_by_options)
    ? panel.rank_by_options
    : [
      { value: "turnover", label: "Turnover" },
      { value: "operating_profit", label: "Operating Profit" },
      { value: "margin", label: "Margin" },
      { value: "gva", label: "GVA" },
    ];
  rankByOptions.forEach((rankOption) => {
    const option = document.createElement("option");
    option.value = String(rankOption.value);
    option.textContent = String(rankOption.label);
    rankSelect.appendChild(option);
  });
  rankSelect.value = String(state.rankBy);

  const yearLabel = document.createElement("label");
  yearLabel.className = "industry-profitability-control-label";
  yearLabel.textContent = "Ranking as-of:";
  yearLabel.setAttribute("for", `industry-as-of-${panel.panel_id}`);
  const yearSelect = document.createElement("select");
  yearSelect.id = `industry-as-of-${panel.panel_id}`;
  yearSelect.className = "chart-select industry-profitability-year-select";
  (panel.available_years || []).forEach((year) => {
    const option = document.createElement("option");
    option.value = String(year);
    option.textContent = String(year);
    yearSelect.appendChild(option);
  });
  if (state.asOfYear !== null) {
    yearSelect.value = String(state.asOfYear);
  }

  controls.appendChild(rankLabel);
  controls.appendChild(rankSelect);
  controls.appendChild(yearLabel);
  controls.appendChild(yearSelect);
  return { controls, rankSelect, yearSelect };
}

function buildIndustryTopControl(panelId, chartKey, topN) {
  const controls = document.createElement("div");
  controls.className = "industry-profitability-chart-controls";
  const topInputId = `industry-${chartKey}-topn-${panelId}`;
  const topLabel = document.createElement("label");
  topLabel.className = "industry-profitability-control-label";
  topLabel.textContent = "Top:";
  topLabel.setAttribute("for", topInputId);
  const topInput = document.createElement("input");
  topInput.type = "number";
  topInput.min = "1";
  topInput.step = "1";
  topInput.id = topInputId;
  topInput.className = "industry-profitability-topn-input";
  topInput.value = String(topN);
  controls.appendChild(topLabel);
  controls.appendChild(topInput);
  return { controls, topInput };
}

function renderIndustryLegendSubcard(legendHost, displayedLabels, colorByLabel) {
  legendHost.innerHTML = "";
  const legendTitle = document.createElement("div");
  legendTitle.className = "industry-profitability-legend-title";
  legendTitle.textContent = "Legend";
  legendHost.appendChild(legendTitle);
  const legendItems = document.createElement("div");
  legendItems.className = "industry-profitability-legend-items";
  displayedLabels.forEach((industryLabel) => {
    const item = document.createElement("div");
    item.className = "industry-profitability-legend-item";
    const swatch = document.createElement("span");
    swatch.className = "industry-profitability-legend-swatch";
    swatch.style.backgroundColor =
      colorByLabel[industryLabel] || getChartSeriesColor(0);
    const label = document.createElement("span");
    label.className = "industry-profitability-legend-label";
    label.textContent = industryLabel;
    item.appendChild(swatch);
    item.appendChild(label);
    legendItems.appendChild(item);
  });
  legendHost.appendChild(legendItems);
}

function attachIndustryProfitabilityInfoButton(chartCard, panel, chartTitle) {
  const descriptions = [
    {
      name: chartTitle,
      description: panel.description || "",
    },
  ];
  attachChartInfoButton(chartCard, descriptions, [chartTitle]);
  const warningText = (panel.comparability_warning || "").trim();
  if (!warningText) {
    return;
  }
  let infoWrapper = chartCard.querySelector(".chart-info-wrapper");
  if (!infoWrapper) {
    infoWrapper = document.createElement("div");
    infoWrapper.className = "chart-info-wrapper";
    chartCard.appendChild(infoWrapper);
  }
  const warningButton = document.createElement("button");
  warningButton.type = "button";
  warningButton.className = "chart-comparability-warning";
  warningButton.setAttribute("aria-label", "Industry classification warning");
  warningButton.textContent = "!";
  const tooltip = document.createElement("div");
  tooltip.className = "chart-comparability-warning-tooltip";
  tooltip.textContent = warningText;
  warningButton.appendChild(tooltip);
  // Keep the warning before the info button when both are present.
  infoWrapper.insertBefore(warningButton, infoWrapper.firstChild);
}

function renderIndustryProfitabilityCards(panel, sectionGrid) {
  const state = getIndustryProfitabilityState(panel);
  const initialTitles = getIndustryChartTitles(state.rankBy);

  const card = document.createElement("div");
  card.className = "chart-card industry-profitability-card";

  const header = document.createElement("div");
  header.className = "chart-header";
  const cardTitle = document.createElement("h3");
  cardTitle.textContent = initialTitles.cardTitle;
  header.appendChild(cardTitle);
  card.appendChild(header);

  const sharedControls = buildIndustrySharedControls(panel, state);
  card.appendChild(sharedControls.controls);

  const chartsRow = document.createElement("div");
  chartsRow.className = "industry-profitability-charts-row";

  const linePanel = document.createElement("div");
  linePanel.className = "industry-profitability-chart-panel";
  const lineHeader = document.createElement("div");
  lineHeader.className = "industry-profitability-chart-header";
  const lineTitle = document.createElement("h4");
  lineTitle.textContent = initialTitles.lineTitle;
  lineHeader.appendChild(lineTitle);
  const lineTop = buildIndustryTopControl(
    panel.panel_id,
    "line",
    state.lineTopN
  );
  lineHeader.appendChild(lineTop.controls);
  linePanel.appendChild(lineHeader);
  const lineWrapper = document.createElement("div");
  lineWrapper.className = "chart-wrapper industry-profitability-line-wrapper";
  const lineCanvas = document.createElement("canvas");
  lineCanvas.id = `industry-line-${panel.panel_id}`;
  lineWrapper.appendChild(lineCanvas);
  linePanel.appendChild(lineWrapper);
  chartsRow.appendChild(linePanel);

  const barPanel = document.createElement("div");
  barPanel.className = "industry-profitability-chart-panel";
  const barHeader = document.createElement("div");
  barHeader.className = "industry-profitability-chart-header";
  const barTitle = document.createElement("h4");
  barTitle.textContent = initialTitles.barTitle;
  barHeader.appendChild(barTitle);
  const barTop = buildIndustryTopControl(panel.panel_id, "bar", state.barTopN);
  barHeader.appendChild(barTop.controls);
  barPanel.appendChild(barHeader);
  const barWrapper = document.createElement("div");
  barWrapper.className = "chart-wrapper industry-profitability-bar-wrapper";
  const barCanvas = document.createElement("canvas");
  barCanvas.id = `industry-bar-${panel.panel_id}`;
  barWrapper.appendChild(barCanvas);
  barPanel.appendChild(barWrapper);
  chartsRow.appendChild(barPanel);

  card.appendChild(chartsRow);

  const legendSubcard = document.createElement("div");
  legendSubcard.className = "industry-profitability-legend-subcard";
  card.appendChild(legendSubcard);

  attachIndustryProfitabilityInfoButton(card, panel, initialTitles.cardTitle);
  sectionGrid.appendChild(card);

  function refreshIndustryCharts() {
    const titles = getIndustryChartTitles(state.rankBy);
    cardTitle.textContent = titles.cardTitle;
    lineTitle.textContent = titles.lineTitle;
    barTitle.textContent = titles.barTitle;
    const colorByLabel = buildIndustryColorByLabel(panel, state);
    const lineData = buildIndustryProfitabilityLineData(
      panel,
      state.lineTopN,
      state.rankBy
    );
    if (lineData.length > 0) {
      renderIndustryProfitabilityLineChart(
        panel,
        lineCanvas,
        lineData,
        state.rankBy,
        colorByLabel
      );
    }
    const barData = buildIndustryProfitabilityBarData(
      panel,
      state.asOfYear,
      state.barTopN,
      state.rankBy
    );
    if (barData.length > 0) {
      renderIndustryProfitabilityBarChart(
        panel,
        barCanvas,
        barData,
        state.rankBy,
        colorByLabel
      );
    }
    renderIndustryLegendSubcard(
      legendSubcard,
      listDisplayedIndustryLabels(panel, state),
      colorByLabel
    );
  }

  sharedControls.rankSelect.addEventListener("change", () => {
    state.rankBy = sharedControls.rankSelect.value || "turnover";
    refreshIndustryCharts();
  });
  sharedControls.yearSelect.addEventListener("change", () => {
    const parsedYear = Number.parseInt(sharedControls.yearSelect.value, 10);
    if (Number.isFinite(parsedYear)) {
      state.asOfYear = parsedYear;
      refreshIndustryCharts();
    }
  });
  lineTop.topInput.addEventListener("change", () => {
    state.lineTopN = parsePositiveIntegerInput(
      lineTop.topInput.value,
      state.lineTopN
    );
    lineTop.topInput.value = String(state.lineTopN);
    refreshIndustryCharts();
  });
  barTop.topInput.addEventListener("change", () => {
    state.barTopN = parsePositiveIntegerInput(
      barTop.topInput.value,
      state.barTopN
    );
    barTop.topInput.value = String(state.barTopN);
    refreshIndustryCharts();
  });

  refreshIndustryCharts();
}

function getTradeRankingState(panel) {
  return {
    asOfYear: panel.as_of_year,
    flow: panel.flow,
    breakdown: panel.breakdown,
    productCode: panel.product_code || "",
    partnerCode: panel.partner_code || "",
    lineTopN: panel.line_top_n || 5,
    barTopN: panel.top_n,
  };
}

function isTradeCrossView(state) {
  return (
    (state.breakdown === "PARTNER" && Boolean(state.productCode)) ||
    (state.breakdown === "PRODUCT" && Boolean(state.partnerCode))
  );
}

function applyTradeBarDrilldown(state, bar) {
  const itemCode = bar && bar.item_code;
  if (!itemCode) {
    return false;
  }
  if (isTradeCrossView(state)) {
    // Second click: clear the cross filter and return to the ranking we drilled from.
    if (state.breakdown === "PARTNER" && state.productCode) {
      state.breakdown = "PRODUCT";
      state.productCode = "";
      state.partnerCode = "";
      return true;
    }
    if (state.breakdown === "PRODUCT" && state.partnerCode) {
      state.breakdown = "PARTNER";
      state.productCode = "";
      state.partnerCode = "";
      return true;
    }
  }
  if (state.breakdown === "PARTNER") {
    // Partner ranking → products for the clicked partner.
    state.breakdown = "PRODUCT";
    state.partnerCode = itemCode;
    state.productCode = "";
    return true;
  }
  // Product ranking → partners for the clicked product.
  state.breakdown = "PARTNER";
  state.productCode = itemCode;
  state.partnerCode = "";
  return true;
}

function buildTradeCrossBars(cells, state, topN) {
  if (state.breakdown === "PARTNER" && state.productCode) {
    return cells
      .filter(
        (observation) =>
          observation.year === state.asOfYear &&
          observation.flow === state.flow &&
          observation.product_code === state.productCode &&
          observation.rank <= topN
      )
      .sort((left, right) => left.rank - right.rank)
      .map((observation) => ({
        item_code: observation.partner_code,
        item_label: observation.partner_label,
        rank: observation.rank,
        trade_value: observation.trade_value,
      }));
  }
  if (state.breakdown === "PRODUCT" && state.partnerCode) {
    return cells
      .filter(
        (observation) =>
          observation.year === state.asOfYear &&
          observation.flow === state.flow &&
          observation.partner_code === state.partnerCode
      )
      .sort((left, right) => right.trade_value - left.trade_value)
      .slice(0, topN)
      .map((observation, index) => ({
        item_code: observation.product_code,
        item_label: observation.product_label,
        rank: index + 1,
        trade_value: observation.trade_value,
      }));
  }
  return null;
}

function buildTradeAggregatedCellBars(cells, state) {
  const matching = cells.filter(
    (observation) =>
      observation.year === state.asOfYear && observation.flow === state.flow
  );
  if (state.breakdown === "PRODUCT") {
    const totalsByProduct = {};
    matching.forEach((observation) => {
      const previous = totalsByProduct[observation.product_code] || {
        item_label: observation.product_label,
        trade_value: 0,
      };
      totalsByProduct[observation.product_code] = {
        item_label: previous.item_label,
        trade_value: previous.trade_value + observation.trade_value,
      };
    });
    return Object.entries(totalsByProduct)
      .map(([itemCode, total]) => ({
        item_code: itemCode,
        item_label: total.item_label,
        trade_value: total.trade_value,
      }))
      .sort((left, right) => right.trade_value - left.trade_value)
      .slice(0, state.barTopN)
      .map((item, index) => ({ ...item, rank: index + 1 }));
  }
  const totalsByPartner = {};
  matching.forEach((observation) => {
    const previous = totalsByPartner[observation.partner_code] || {
      item_label: observation.partner_label,
      trade_value: 0,
    };
    totalsByPartner[observation.partner_code] = {
      item_label: previous.item_label,
      trade_value: previous.trade_value + observation.trade_value,
    };
  });
  return Object.entries(totalsByPartner)
    .map(([itemCode, total]) => ({
      item_code: itemCode,
      item_label: total.item_label,
      trade_value: total.trade_value,
    }))
    .sort((left, right) => right.trade_value - left.trade_value)
    .slice(0, state.barTopN)
    .map((item, index) => ({ ...item, rank: index + 1 }));
}

function buildTradeBars(panel, state) {
  const cells = panel.cell_observations || [];
  const rankings = panel.ranking_observations || [];
  const crossBars = buildTradeCrossBars(cells, state, state.barTopN);
  if (crossBars !== null) {
    return crossBars;
  }
  if (rankings.length > 0) {
    return rankings
      .filter(
        (observation) =>
          observation.year === state.asOfYear &&
          observation.flow === state.flow &&
          observation.breakdown === state.breakdown &&
          observation.rank <= state.barTopN
      )
      .sort((left, right) => left.rank - right.rank)
      .map((observation) => ({
        item_code: observation.item_code,
        item_label: observation.item_label,
        rank: observation.rank,
        trade_value: observation.trade_value,
      }));
  }
  return buildTradeAggregatedCellBars(cells, state);
}

function buildTradeLineDataFromCells(panel, state, topCodes, labelByCode) {
  const totalsByYearAndCode = {};
  (panel.cell_observations || []).forEach((observation) => {
    if (observation.flow !== state.flow) {
      return;
    }
    let itemCode;
    if (state.breakdown === "PRODUCT") {
      if (state.partnerCode && observation.partner_code !== state.partnerCode) {
        return;
      }
      itemCode = observation.product_code;
    } else if (state.productCode) {
      if (observation.product_code !== state.productCode) {
        return;
      }
      itemCode = observation.partner_code;
    } else {
      itemCode = observation.partner_code;
    }
    if (!topCodes.has(itemCode)) {
      return;
    }
    const key = `${observation.year}::${itemCode}`;
    totalsByYearAndCode[key] =
      (totalsByYearAndCode[key] || 0) + observation.trade_value;
  });
  return Object.entries(totalsByYearAndCode).map(([key, tradeValue]) => {
    const [yearText, itemCode] = key.split("::");
    return {
      period: yearText,
      data_value: tradeValue,
      indicator_name: labelByCode[itemCode] || itemCode,
      unit_label: panel.value_axis_label,
    };
  });
}

function buildTradeLineData(panel, state) {
  const latestYear = Math.max(...(panel.available_years || [state.asOfYear]));
  const latestState = { ...state, asOfYear: latestYear, barTopN: state.lineTopN };
  const topBars = buildTradeBars(panel, latestState);
  const topCodes = new Set(topBars.map((bar) => bar.item_code));
  const labelByCode = {};
  topBars.forEach((bar) => {
    labelByCode[bar.item_code] = bar.item_label;
  });
  const cells = panel.cell_observations || [];
  const rankings = panel.ranking_observations || [];
  let lineData = [];
  if (state.breakdown === "PARTNER" && state.productCode) {
    cells.forEach((observation) => {
      if (
        observation.flow !== state.flow ||
        observation.product_code !== state.productCode ||
        !topCodes.has(observation.partner_code)
      ) {
        return;
      }
      lineData.push({
        period: String(observation.year),
        data_value: observation.trade_value,
        indicator_name: observation.partner_label,
        unit_label: panel.value_axis_label,
      });
    });
  } else if (state.breakdown === "PRODUCT" && state.partnerCode) {
    cells.forEach((observation) => {
      if (
        observation.flow !== state.flow ||
        observation.partner_code !== state.partnerCode ||
        !topCodes.has(observation.product_code)
      ) {
        return;
      }
      lineData.push({
        period: String(observation.year),
        data_value: observation.trade_value,
        indicator_name: observation.product_label,
        unit_label: panel.value_axis_label,
      });
    });
  } else if (rankings.length > 0) {
    rankings.forEach((observation) => {
      if (
        observation.flow !== state.flow ||
        observation.breakdown !== state.breakdown ||
        !topCodes.has(observation.item_code)
      ) {
        return;
      }
      lineData.push({
        period: String(observation.year),
        data_value: observation.trade_value,
        indicator_name: observation.item_label,
        unit_label: panel.value_axis_label,
      });
    });
  } else {
    lineData = buildTradeLineDataFromCells(
      panel,
      state,
      topCodes,
      labelByCode
    );
  }
  lineData.sort((left, right) => {
    if (left.period === right.period) {
      return right.indicator_name.localeCompare(left.indicator_name);
    }
    return right.period.localeCompare(left.period);
  });
  return lineData;
}

function buildTradeColorByLabel(bars, lineData) {
  const rankedLabels = bars.map((bar) => bar.item_label);
  lineData.forEach((point) => {
    if (!rankedLabels.includes(point.indicator_name)) {
      rankedLabels.push(point.indicator_name);
    }
  });
  return buildColorByRankedLabel(rankedLabels);
}

function renderTradeRankingBarChart(
  panel,
  canvas,
  bars,
  valueAxisLabel,
  colorByLabel,
  onBarClick
) {
  const slotKey = `trade-bar-${panel.panel_id}`;
  if (chartInstances[slotKey]) {
    chartInstances[slotKey].destroy();
  }
  const fullLabels = bars.map((point) => point.item_label);
  const labels = fullLabels.map((label) =>
    String(label || "").length > 28
      ? `${String(label).slice(0, 27)}…`
      : String(label || "")
  );
  const values = bars.map((point) => point.trade_value);
  const colors = fullLabels.map(
    (itemLabel, index) =>
      (colorByLabel && colorByLabel[itemLabel]) || getChartSeriesColor(index)
  );
  chartInstances[slotKey] = new Chart(canvas.getContext("2d"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: panel.title,
          data: values,
          backgroundColor: colors,
          borderColor: colors,
          borderWidth: 1,
        },
      ],
    },
    options: {
      indexAxis: "y",
      onClick(_event, elements) {
        if (!onBarClick || !elements.length) {
          return;
        }
        const bar = bars[elements[0].index];
        if (bar) {
          onBarClick(bar);
        }
      },
      onHover(event, elements) {
        const target = event.native && event.native.target;
        if (target) {
          target.style.cursor = elements.length ? "pointer" : "default";
        }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title(tooltipItems) {
              if (!tooltipItems.length) {
                return "";
              }
              return fullLabels[tooltipItems[0].dataIndex] || "";
            },
            label(context) {
              const value = context.parsed.x;
              const formattedValue = Number(value).toLocaleString(undefined, {
                maximumFractionDigits: 1,
              });
              return `${formattedValue} ${valueAxisLabel}`;
            },
          },
        },
      },
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          title: {
            display: true,
            text: valueAxisLabel,
          },
          ticks: {
            callback(value) {
              return Number(value).toLocaleString(undefined, {
                maximumFractionDigits: 1,
              });
            },
          },
        },
        y: {
          ticks: {
            autoSkip: false,
            callback(_value, index) {
              return labels[index] || "";
            },
          },
        },
      },
    },
  });
}

function renderTradeRankingLineChart(panel, canvas, lineData, colorByLabel) {
  const slotKey = `trade-line-${panel.panel_id}`;
  if (chartInstances[slotKey]) {
    chartInstances[slotKey].destroy();
  }
  if (!lineData.length) {
    return;
  }
  const chartData = createEconomicChart(
    panel.category,
    "Trend",
    lineData,
    colorByLabel
  );
  chartInstances[slotKey] = new Chart(canvas.getContext("2d"), {
    type: "line",
    data: chartData,
    options: {
      plugins: {
        legend: {
          display: false,
        },
        tooltip: {
          callbacks: getLineChartTooltipCallbacks(),
        },
      },
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          title: {
            display: true,
            text: "Year",
          },
        },
        y: {
          title: {
            display: true,
            text: panel.value_axis_label || "",
          },
          ticks: {
            callback(value) {
              return Number(value).toLocaleString(undefined, {
                maximumFractionDigits: 1,
              });
            },
          },
        },
      },
    },
  });
}

function fillTradeSelectOptions(select, options, selectedValue) {
  select.innerHTML = "";
  options.forEach((option) => {
    const optionElement = document.createElement("option");
    optionElement.value = option.value;
    optionElement.textContent = option.label;
    if (option.value === selectedValue) {
      optionElement.selected = true;
    }
    select.appendChild(optionElement);
  });
  select.value = selectedValue;
}

function appendTradeSelectControl(controls, labelText, options, selectedValue, onChange) {
  const selectId = `trade-select-${controls.childElementCount}-${Math.random()
    .toString(36)
    .slice(2, 8)}`;
  const label = document.createElement("label");
  label.className = "industry-profitability-control-label";
  label.textContent = labelText;
  label.setAttribute("for", selectId);
  const select = document.createElement("select");
  select.id = selectId;
  select.className = "chart-select";
  fillTradeSelectOptions(select, options, selectedValue);
  select.addEventListener("change", () => onChange(select.value));
  controls.appendChild(label);
  controls.appendChild(select);
  return select;
}

function buildTradeTopControl(panelId, chartKey, topN) {
  return buildIndustryTopControl(panelId, `trade-${chartKey}`, topN);
}

function listTradeYearOptions(panel) {
  return (panel.available_years || []).map((year) => ({
    value: String(year),
    label: String(year),
  }));
}

function listTradeProductFilterOptions(panel) {
  return [{ value: "", label: "All products" }, ...(panel.product_options || [])];
}

function listTradePartnerFilterOptions(panel) {
  return [{ value: "", label: "All partners" }, ...(panel.partner_options || [])];
}

function groupTradePanelsByLocation(panels) {
  const panelsByLocation = {};
  panels.forEach((panel) => {
    const locationKey = panel.location || panel.panel_id;
    if (!panelsByLocation[locationKey]) {
      panelsByLocation[locationKey] = [];
    }
    panelsByLocation[locationKey].push(panel);
  });
  return Object.values(panelsByLocation);
}

function renderTradeRankingCard(locationPanels, sectionGrid) {
  // Prefer energy when both trade types are present for the location.
  const panels = locationPanels.slice().sort((left, right) => {
    if (left.panel === "energy") {
      return -1;
    }
    if (right.panel === "energy") {
      return 1;
    }
    return (left.panel_label || "").localeCompare(right.panel_label || "");
  });
  let panel = panels[0];
  const state = getTradeRankingState(panel);
  const cardPanelId = `trade-${String(panel.location || "unknown").toLowerCase()}`;
  const card = document.createElement("div");
  card.className = "chart-card industry-profitability-card";
  const header = document.createElement("div");
  header.className = "chart-header";
  const cardTitle = document.createElement("h3");
  cardTitle.textContent = panel.title;
  header.appendChild(cardTitle);
  card.appendChild(header);

  const controls = document.createElement("div");
  controls.className = "industry-profitability-card-controls";
  if (panels.length > 1) {
    appendTradeSelectControl(
      controls,
      "Trade type:",
      panels.map((tradePanel) => ({
        value: tradePanel.panel,
        label: tradePanel.panel_label || tradePanel.panel,
      })),
      panel.panel,
      (value) => {
        const nextPanel = panels.find((tradePanel) => tradePanel.panel === value);
        if (!nextPanel || nextPanel === panel) {
          return;
        }
        panel = nextPanel;
        const nextState = getTradeRankingState(panel);
        state.asOfYear = nextState.asOfYear;
        state.flow = nextState.flow;
        state.breakdown = nextState.breakdown;
        state.productCode = "";
        state.partnerCode = "";
        state.lineTopN = nextState.lineTopN;
        state.barTopN = nextState.barTopN;
        fillTradeSelectOptions(
          yearSelect,
          listTradeYearOptions(panel),
          String(state.asOfYear)
        );
        flowSelect.value = state.flow;
        breakdownSelect.value = state.breakdown;
        fillTradeSelectOptions(
          productSelect,
          listTradeProductFilterOptions(panel),
          state.productCode
        );
        fillTradeSelectOptions(
          partnerSelect,
          listTradePartnerFilterOptions(panel),
          state.partnerCode
        );
        lineTop.topInput.value = String(state.lineTopN);
        barTop.topInput.value = String(state.barTopN);
        refresh();
      }
    );
  }
  const yearSelect = appendTradeSelectControl(
    controls,
    "Year:",
    listTradeYearOptions(panel),
    String(state.asOfYear),
    (value) => {
      state.asOfYear = Number.parseInt(value, 10);
      refresh();
    }
  );
  const flowSelect = appendTradeSelectControl(
    controls,
    "Flow:",
    panel.flow_options || [],
    state.flow,
    (value) => {
      state.flow = value;
      refresh();
    }
  );
  const breakdownSelect = appendTradeSelectControl(
    controls,
    "Breakdown:",
    panel.breakdown_options || [],
    state.breakdown,
    (value) => {
      state.breakdown = value;
      state.productCode = "";
      state.partnerCode = "";
      productSelect.value = "";
      partnerSelect.value = "";
      refresh();
    }
  );
  const productSelect = appendTradeSelectControl(
    controls,
    "Product:",
    listTradeProductFilterOptions(panel),
    state.productCode,
    (value) => {
      state.productCode = value;
      refresh();
    }
  );
  productSelect.classList.add("trade-cross-filter-select");
  const productLabel = productSelect.previousElementSibling;
  const partnerSelect = appendTradeSelectControl(
    controls,
    "Partner:",
    listTradePartnerFilterOptions(panel),
    state.partnerCode,
    (value) => {
      state.partnerCode = value;
      refresh();
    }
  );
  partnerSelect.classList.add("trade-cross-filter-select");
  const partnerLabel = partnerSelect.previousElementSibling;
  card.appendChild(controls);

  const chartsRow = document.createElement("div");
  chartsRow.className = "industry-profitability-charts-row";

  const linePanel = document.createElement("div");
  linePanel.className = "industry-profitability-chart-panel";
  const lineHeader = document.createElement("div");
  lineHeader.className = "industry-profitability-chart-header";
  const lineTitle = document.createElement("h4");
  lineTitle.textContent = "Trend";
  lineHeader.appendChild(lineTitle);
  const lineTop = buildTradeTopControl(cardPanelId, "line", state.lineTopN);
  lineHeader.appendChild(lineTop.controls);
  linePanel.appendChild(lineHeader);
  const lineWrapper = document.createElement("div");
  lineWrapper.className = "chart-wrapper industry-profitability-line-wrapper";
  const lineCanvas = document.createElement("canvas");
  lineCanvas.id = `trade-line-${cardPanelId}`;
  lineWrapper.appendChild(lineCanvas);
  linePanel.appendChild(lineWrapper);
  chartsRow.appendChild(linePanel);

  const barPanel = document.createElement("div");
  barPanel.className = "industry-profitability-chart-panel";
  const barHeader = document.createElement("div");
  barHeader.className = "industry-profitability-chart-header";
  const barTitle = document.createElement("h4");
  barTitle.textContent = "Ranking";
  barHeader.appendChild(barTitle);
  const barTop = buildTradeTopControl(cardPanelId, "bar", state.barTopN);
  barHeader.appendChild(barTop.controls);
  barPanel.appendChild(barHeader);
  const barWrapper = document.createElement("div");
  barWrapper.className = "chart-wrapper industry-profitability-bar-wrapper";
  const barCanvas = document.createElement("canvas");
  barCanvas.id = `trade-bar-${cardPanelId}`;
  barWrapper.appendChild(barCanvas);
  barPanel.appendChild(barWrapper);
  chartsRow.appendChild(barPanel);
  card.appendChild(chartsRow);
  sectionGrid.appendChild(card);

  lineTop.topInput.addEventListener("change", () => {
    state.lineTopN = parsePositiveIntegerInput(
      lineTop.topInput.value,
      state.lineTopN
    );
    lineTop.topInput.value = String(state.lineTopN);
    refresh();
  });
  barTop.topInput.addEventListener("change", () => {
    state.barTopN = parsePositiveIntegerInput(
      barTop.topInput.value,
      state.barTopN
    );
    barTop.topInput.value = String(state.barTopN);
    refresh();
  });

  function refresh() {
    const showProduct = state.breakdown === "PARTNER";
    const showPartner = state.breakdown === "PRODUCT";
    productSelect.style.display = showProduct ? "" : "none";
    if (productLabel) {
      productLabel.style.display = showProduct ? "" : "none";
    }
    partnerSelect.style.display = showPartner ? "" : "none";
    if (partnerLabel) {
      partnerLabel.style.display = showPartner ? "" : "none";
    }
    const breakdownLabel =
      (panel.breakdown_options || []).find(
        (option) => option.value === state.breakdown
      )?.label || state.breakdown;
    const crossCode =
      state.breakdown === "PARTNER"
        ? state.productCode
        : state.partnerCode;
    const titleSuffix = crossCode
      ? `${breakdownLabel} (${crossCode})`
      : breakdownLabel;
    const panelLabel = panel.panel_label || "Trade";
    cardTitle.textContent = `${panel.location} ${panelLabel} — ${titleSuffix}`;
    const bars = buildTradeBars(panel, state);
    const lineData = buildTradeLineData(panel, state);
    const colorByLabel = buildTradeColorByLabel(bars, lineData);
    renderTradeRankingLineChart(panel, lineCanvas, lineData, colorByLabel);
    if (bars.length > 0) {
      renderTradeRankingBarChart(
        panel,
        barCanvas,
        bars,
        panel.value_axis_label,
        colorByLabel,
        (bar) => {
          if (!applyTradeBarDrilldown(state, bar)) {
            return;
          }
          breakdownSelect.value = state.breakdown;
          productSelect.value = state.productCode;
          partnerSelect.value = state.partnerCode;
          refresh();
        }
      );
    }
  }
  refresh();
}

function renderCharts() {
  const chartGrid = document.getElementById("chart-grid");
  chartGrid.innerHTML = "";
  chartGrid.className = "chart-sections";

  const compositionPanelsByCategory = {};
  compositionPanels.forEach((panel) => {
    const categoryStr = getLabelString(panel.category);
    if (!compositionPanelsByCategory[categoryStr]) {
      compositionPanelsByCategory[categoryStr] = [];
    }
    compositionPanelsByCategory[categoryStr].push(panel);
  });

  const industryPanelsByCategory = {};
  industryProfitabilityPanels.forEach((panel) => {
    const categoryStr = getLabelString(panel.category);
    if (!industryPanelsByCategory[categoryStr]) {
      industryPanelsByCategory[categoryStr] = [];
    }
    industryPanelsByCategory[categoryStr].push(panel);
  });

  const tradePanelsByCategory = {};
  tradeRankingPanels.forEach((panel) => {
    const categoryStr = getLabelString(panel.category);
    if (!tradePanelsByCategory[categoryStr]) {
      tradePanelsByCategory[categoryStr] = [];
    }
    tradePanelsByCategory[categoryStr].push(panel);
  });

  categories.forEach((category) => {
    const categoryStr = getLabelString(category);
    const slots = (chartSlotsByCategory[categoryStr] || []).filter(
      (slot) => slot.hasIndicators
    );
    const categoryCompositionPanels = compositionPanelsByCategory[categoryStr] || [];
    const categoryIndustryPanels = industryPanelsByCategory[categoryStr] || [];
    const categoryTradePanels = tradePanelsByCategory[categoryStr] || [];
    if (
      slots.length === 0 &&
      categoryCompositionPanels.length === 0 &&
      categoryIndustryPanels.length === 0 &&
      categoryTradePanels.length === 0
    ) {
      return;
    }

    const section = document.createElement("section");
    section.className = "chart-category-section";

    const sectionTitle = document.createElement("h2");
    sectionTitle.className = "chart-category-title";
    sectionTitle.textContent = categoryStr;
    section.appendChild(sectionTitle);

    const sectionGrid = document.createElement("div");
    sectionGrid.className = "chart-grid";
    section.appendChild(sectionGrid);
    chartGrid.appendChild(section);

    slots.forEach((slot) => {
      sectionGrid.appendChild(
        renderChartCard(slot.category, slot.subcategory, slot.slotKey)
      );
    });
    categoryCompositionPanels.forEach((panel) => {
      renderCompositionCard(panel, sectionGrid);
    });
    categoryIndustryPanels.forEach((panel) => {
      renderIndustryProfitabilityCards(panel, sectionGrid);
    });
    groupTradePanelsByLocation(categoryTradePanels).forEach((locationPanels) => {
      renderTradeRankingCard(locationPanels, sectionGrid);
    });
  });
}

// ==========================================
// Initialize
// ==========================================

document.addEventListener("DOMContentLoaded", () => {
  restorePreservedScroll();
  initializeRegionButtons();
  initializePeriodWindowSelect();
  initializeCountriesMultiselect();
  renderCharts();
});
