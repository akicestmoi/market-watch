// ==========================================
// Load Django context data
// ==========================================
const dropdownValues = window.dropdownValuesJSON;
const economicData = window.economicDataJSON;
const categories = window.categoriesJSON;
const selectedValuesRaw = window.selectedValuesJSON || {};
const currentRegion = window.currentRegion;

// Store chart instances
const chartInstances = {};

const CHART_SERIES_MODES = new Set([
  "Raw",
  "Quarter",
  "Annualized Quarter",
  "Annual",
]);
const CHART_SERIES_MODE_LABELS = {
  Raw: "Abs",
  Quarter: "QoQ",
  "Annualized Quarter": "QoQy",
  Annual: "YoY",
};

function normalizeMode(mode) {
  const trimmed = (mode || "Raw").trim();
  return CHART_SERIES_MODES.has(trimmed) ? trimmed : "Raw";
}

// Series key (``GDP`` / ``DE|GDP``) → DB default_mode from dropdown payload.
const defaultModeBySeriesKey = {};
if (dropdownValues && dropdownValues.indicators_by_category) {
  dropdownValues.indicators_by_category.forEach((item) => {
    (item.indicators || []).forEach((indicator) => {
      if (indicator.type) {
        defaultModeBySeriesKey[indicator.type] = normalizeMode(
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
  // Wire format: [Location|]Type[|MODE]. Location stays on ``type`` for Europe
  // checkbox keys (``DE|GDP``); mode is peeled off separately.
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
  if (!mode) {
    mode = getDefaultModeForSeriesKey(seriesKey);
  }
  return { type: seriesKey, mode, encoded: `${seriesKey}|${mode}` };
}

function encodeIndicatorEntry(type, mode) {
  // ``type`` may already be a Europe series key (``DE|GDP``).
  return `${type}|${normalizeMode(mode)}`;
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
    Europe: "eu",
    France: "fr",
    Japan: "jp",
  };
  return regionMapping[regionLabel] || regionLabel.toLowerCase();
}

// Helper to get category string from enum object
function getCategoryString(category) {
  if (typeof category === "string") {
    return category;
  }
  // If it's an enum object, try to get the label
  if (category && category.label) {
    return String(category.label);
  }
  // Fallback to string conversion
  return String(category);
}

// Convert economicData list to object keyed by category
const economicDataByCategory = {};
if (Array.isArray(economicData)) {
  economicData.forEach((item) => {
    const categoryStr = getCategoryString(item.category);
    economicDataByCategory[categoryStr] = item.category_data || [];
  });
}

// Convert indicators_by_category to object keyed by category string
const indicatorsByCategoryMap = {};
const indicatorsByCategoryTypeMap = {}; // Map type -> name for display
if (dropdownValues && dropdownValues.indicators_by_category) {
  dropdownValues.indicators_by_category.forEach((item) => {
    const categoryStr = getCategoryString(item.category);
    const indicators = item.indicators || [];
    indicatorsByCategoryMap[categoryStr] = indicators.map((ind) => ind.type);
    indicators.forEach((ind) => {
      if (ind.type && ind.name) {
        indicatorsByCategoryTypeMap[ind.type] = ind.name;
      }
    });
  });
}

// ==========================================
// Region Button Handling
// ==========================================

const REGION_CODE_TO_LABEL = {
  US: "United States",
  EU: "Europe",
  FR: "France",
  JP: "Japan",
};

/**
 * Same Chart.js hues as market charts, but assigned in a different order so
 * economic categories do not mirror stocks → FX → commodity → …
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
];

/** Fixed main color per category (shared across all regions). */
const CATEGORY_MAIN_COLORS = {
  Growth: CHART_SERIES_COLORS[0], // purple
  Inflation: CHART_SERIES_COLORS[1], // orange
  Government: CHART_SERIES_COLORS[2], // green
  Production: CHART_SERIES_COLORS[3], // blue
  Sales: CHART_SERIES_COLORS[4], // pink
  Labour: CHART_SERIES_COLORS[5], // teal
  Housing: CHART_SERIES_COLORS[6], // brown
  Confidence: CHART_SERIES_COLORS[7], // yellow
};

function getCategoryMainColor(category) {
  return CATEGORY_MAIN_COLORS[getCategoryString(category)] || CHART_SERIES_COLORS[0];
}

function getSeriesColor(category, seriesIndex) {
  const mainColor = getCategoryMainColor(category);
  if (seriesIndex === 0) {
    return mainColor;
  }
  // Walk the market-chart palette, skipping the category’s own color.
  const extras = CHART_SERIES_COLORS.filter((color) => color !== mainColor);
  return extras[(seriesIndex - 1) % extras.length];
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
      params.set("region", regionLabel);
      window.location.search = params.toString();
    });
  });
}


// ==========================================
// Helper Functions
// ==========================================

function getCategorySafeName(category) {
  return category.toLowerCase().replace(/\s+/g, "_");
}

function getSelectedIndicatorsForCategory(category) {
  const regionValue = getRegionValue(currentRegion);
  const categoryValue = category.toLowerCase().replace(/\s+/g, "_");
  const key = `${regionValue}_${categoryValue}_indicator`;

  const indicators = selectedValues[key] || [];
  // Filter out empty strings; values are Type|MODE encoded
  return indicators.filter((ind) => ind && ind !== "");
}

function getModeForType(category, indicatorType) {
  const entry = getSelectedIndicatorsForCategory(category)
    .map(parseIndicatorEntry)
    .find((item) => item && item.type === indicatorType);
  return entry ? entry.mode : getDefaultModeForSeriesKey(indicatorType);
}

function getDefaultIndicatorForCategory(category) {
  const indicators = getSelectedIndicatorsForCategory(category);
  return indicators.length > 0 ? indicators[0] : "";
}

function initializePeriodWindowSelect() {
  const select = document.getElementById("period-window");
  if (!select) return;
  select.addEventListener("change", () => {
    const params = new URLSearchParams(window.location.search);
    params.set("period_window", select.value);
    window.location.search = params.toString();
  });
}

// ==========================================
// Dropdown Population
// ==========================================

function populateDropdown(selectId, options, selectedValue, excludeValues = []) {
  const select = document.getElementById(selectId);
  if (!select) return;

  select.innerHTML = "";

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.text = "-- Select Indicator to Add --";
  placeholder.disabled = true;
  placeholder.selected = !selectedValue;
  select.appendChild(placeholder);

  options.forEach((opt) => {
    // Skip if in exclude list
    if (excludeValues.includes(opt.name)) return;

    const option = document.createElement("option");
    option.value = opt.name;
    option.text = opt.full_name;
    if (opt.name === selectedValue) {
      option.selected = true;
      placeholder.selected = false;
    }
    select.appendChild(option);
  });
}

// ==========================================
// Chart Creation
// ==========================================

function createEconomicChart(category, data, selectedIndicators) {
  // Get all unique periods from all indicators (sorted)
  const allPeriods = new Set();
  data.forEach((item) => {
    allPeriods.add(item.period);
  });
  const sortedPeriods = Array.from(allPeriods).sort((a, b) =>
    a.localeCompare(b)
  );

  // Get unique indicator names from the data (backend returns indicator_name which is the type)
  const uniqueIndicatorNames = [...new Set(data.map(item => item.indicator_name))];

  // Create datasets for each indicator in the data
  // Note: selectedIndicators contains type values, and data has indicator_name (type field)
  // Backend should have filtered, so we show all data returned
  const datasets = [];

  uniqueIndicatorNames.forEach((indicatorName, index) => {
    // Filter data for this indicator
    const indicatorData = data.filter((item) => item.indicator_name === indicatorName);

    // Create a map for quick lookup
    const dataMap = {};
    indicatorData.forEach((d) => {
      dataMap[d.period] = d.data_value;
    });

    // Create data array aligned with sortedPeriods
    const values = sortedPeriods.map((period) => {
      return dataMap[period] !== undefined ? dataMap[period] : null;
    });

    const seriesColor = getSeriesColor(category, index);
    datasets.push({
      label: indicatorName,
      data: values,
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

// ==========================================
// Multi-Select Dropdown Management
// ==========================================

// Store pending selections (before apply/cancel)
const pendingSelections = {};

function updateIndicatorSelection(category) {
  const categorySafe = getCategorySafeName(category);
  const indicatorSelectionContainer = document.getElementById(`${categorySafe}-indicator-selection`);
  if (!indicatorSelectionContainer) return;

  const categoryStr = getCategoryString(category);
  const availableIndicators = indicatorsByCategoryMap[categoryStr] || [];
  // Convert to object format with name and full_name (using actual name from backend)
  const availableIndicatorsFormatted = availableIndicators.map(type => ({
    name: type,
    full_name: indicatorsByCategoryTypeMap[type] || type, // Use full name if available
  }));

  const selectedIndicators = getSelectedIndicatorsForCategory(category);
  const defaultIndicator = getDefaultIndicatorForCategory(category);

  // Determine which encoded Type|MODE entries should be selected
  const indicatorsToCheck = selectedIndicators.length > 0
    ? selectedIndicators
    : (defaultIndicator ? [defaultIndicator] : []);
  const typesToCheck = indicatorsToCheck
    .map(parseIndicatorEntry)
    .filter(Boolean)
    .map((entry) => entry.type);

  // Store initial pending selection (encoded Type|MODE)
  pendingSelections[categorySafe] = [...indicatorsToCheck];

  // Clear existing content
  indicatorSelectionContainer.innerHTML = "";

  // Create multi-select dropdown wrapper
  const dropdownWrapper = document.createElement("div");
  dropdownWrapper.className = "multiselect-dropdown-wrapper";

  // Create dropdown button (shows selected count or placeholder)
  const dropdownButton = document.createElement("button");
  dropdownButton.className = "multiselect-dropdown-button";
  dropdownButton.type = "button";
  const selectedCount = indicatorsToCheck.length;
  dropdownButton.textContent = selectedCount > 0
    ? `${selectedCount} indicator${selectedCount > 1 ? "s" : ""} selected`
    : "-- Select Indicators --";
  dropdownButton.onclick = () => toggleDropdown(category);

  // Create dropdown content (hidden by default)
  const dropdownContent = document.createElement("div");
  dropdownContent.id = `${categorySafe}-dropdown-content`;
  dropdownContent.className = "multiselect-dropdown-content";
  dropdownContent.style.display = "none";

  // Create select all / unselect all buttons
  const actionButtons = document.createElement("div");
  actionButtons.className = "multiselect-action-buttons";

  const selectAllBtn = document.createElement("button");
  selectAllBtn.className = "multiselect-action-btn";
  selectAllBtn.textContent = "Select All";
  selectAllBtn.onclick = (e) => {
    e.stopPropagation();
    selectAllInDropdown(category);
  };

  const unselectAllBtn = document.createElement("button");
  unselectAllBtn.className = "multiselect-action-btn";
  unselectAllBtn.textContent = "Unselect All";
  unselectAllBtn.onclick = (e) => {
    e.stopPropagation();
    unselectAllInDropdown(category);
  };

  actionButtons.appendChild(selectAllBtn);
  actionButtons.appendChild(unselectAllBtn);
  dropdownContent.appendChild(actionButtons);

  // Create checkbox list
  const checkboxList = document.createElement("div");
  checkboxList.className = "multiselect-checkbox-list";

  availableIndicatorsFormatted.forEach((indicator) => {
    const seriesDomId = getSeriesDomId(indicator.name);
    const checkboxItem = document.createElement("div");
    checkboxItem.className = "multiselect-checkbox-item";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = `${categorySafe}-indicator-${seriesDomId}`;
    checkbox.value = indicator.name;
    checkbox.checked = typesToCheck.includes(indicator.name);
    checkbox.onchange = () => updatePendingSelection(category);

    const label = document.createElement("label");
    label.htmlFor = checkbox.id;
    label.textContent = indicator.full_name;
    label.onclick = (e) => e.stopPropagation();

    const modeSelect = document.createElement("select");
    modeSelect.className = "multiselect-mode-select";
    modeSelect.id = `${categorySafe}-mode-${seriesDomId}`;
    modeSelect.setAttribute("aria-label", `Mode for ${indicator.full_name}`);
    ["Raw", "Quarter", "Annualized Quarter", "Annual"].forEach((mode) => {
      const option = document.createElement("option");
      option.value = mode;
      option.textContent = CHART_SERIES_MODE_LABELS[mode];
      modeSelect.appendChild(option);
    });
    modeSelect.value = getModeForType(category, indicator.name);
    modeSelect.onclick = (e) => e.stopPropagation();
    modeSelect.onchange = (e) => {
      e.stopPropagation();
      updatePendingSelection(category);
    };

    checkboxItem.appendChild(checkbox);
    checkboxItem.appendChild(label);
    checkboxItem.appendChild(modeSelect);
    checkboxList.appendChild(checkboxItem);
  });

  dropdownContent.appendChild(checkboxList);

  // Create apply/cancel buttons
  const validationButtons = document.createElement("div");
  validationButtons.className = "multiselect-validation-buttons";

  const applyBtn = document.createElement("button");
  applyBtn.className = "multiselect-apply-btn";
  applyBtn.textContent = "Apply";
  applyBtn.onclick = (e) => {
    e.stopPropagation();
    applyIndicatorSelection(category);
  };

  const cancelBtn = document.createElement("button");
  cancelBtn.className = "multiselect-cancel-btn";
  cancelBtn.textContent = "Cancel";
  cancelBtn.onclick = (e) => {
    e.stopPropagation();
    cancelIndicatorSelection(category);
  };

  validationButtons.appendChild(applyBtn);
  validationButtons.appendChild(cancelBtn);
  dropdownContent.appendChild(validationButtons);

  dropdownWrapper.appendChild(dropdownButton);
  dropdownWrapper.appendChild(dropdownContent);
  indicatorSelectionContainer.appendChild(dropdownWrapper);

  // Close dropdown when clicking outside
  document.addEventListener("click", (e) => {
    if (!dropdownWrapper.contains(e.target)) {
      dropdownContent.style.display = "none";
      dropdownButton.classList.remove("active");
    }
  });
}

function toggleDropdown(category) {
  const categorySafe = getCategorySafeName(category);
  const dropdownContent = document.getElementById(`${categorySafe}-dropdown-content`);
  const dropdownButton = document.querySelector(`#${categorySafe}-indicator-selection .multiselect-dropdown-button`);

  if (dropdownContent && dropdownButton) {
    const isOpen = dropdownContent.style.display === "block";
    dropdownContent.style.display = isOpen ? "none" : "block";
    dropdownButton.classList.toggle("active", !isOpen);
  }
}

function selectAllInDropdown(category) {
  const categorySafe = getCategorySafeName(category);
  const categoryStr = getCategoryString(category);
  const availableIndicators = indicatorsByCategoryMap[categoryStr] || [];

  availableIndicators.forEach((indicatorType) => {
    const checkbox = document.getElementById(
      `${categorySafe}-indicator-${getSeriesDomId(indicatorType)}`
    );
    if (checkbox) {
      checkbox.checked = true;
    }
  });

  updatePendingSelection(category);
}

function unselectAllInDropdown(category) {
  const categorySafe = getCategorySafeName(category);
  const categoryStr = getCategoryString(category);
  const availableIndicators = indicatorsByCategoryMap[categoryStr] || [];

  availableIndicators.forEach((indicatorType) => {
    const checkbox = document.getElementById(
      `${categorySafe}-indicator-${getSeriesDomId(indicatorType)}`
    );
    if (checkbox) {
      checkbox.checked = false;
    }
  });

  updatePendingSelection(category);
}

function updatePendingSelection(category) {
  const categorySafe = getCategorySafeName(category);
  const categoryStr = getCategoryString(category);
  const availableIndicators = indicatorsByCategoryMap[categoryStr] || [];

  const selected = [];
  availableIndicators.forEach((indicatorType) => {
    const seriesDomId = getSeriesDomId(indicatorType);
    const checkbox = document.getElementById(
      `${categorySafe}-indicator-${seriesDomId}`
    );
    const modeSelect = document.getElementById(
      `${categorySafe}-mode-${seriesDomId}`
    );
    if (checkbox && checkbox.checked) {
      const mode = modeSelect
        ? modeSelect.value
        : getDefaultModeForSeriesKey(indicatorType);
      selected.push(encodeIndicatorEntry(indicatorType, mode));
    }
  });

  pendingSelections[categorySafe] = selected;
}

function applyIndicatorSelection(category) {
  const regionValue = getRegionValue(currentRegion);
  const categoryValue = category.toLowerCase().replace(/\s+/g, "_");
  const key = `${regionValue}_${categoryValue}_indicator`;

  const params = new URLSearchParams(window.location.search);
  const selectedIndicators = pendingSelections[getCategorySafeName(category)] || [];

  if (selectedIndicators.length === 0) {
    // If nothing selected, set empty string
    params.set(key, "");
  } else {
    // Set as comma-separated string (backend expects this format)
    params.set(key, selectedIndicators.join(","));
  }

  window.location.search = params.toString();
}

function cancelIndicatorSelection(category) {
  const categorySafe = getCategorySafeName(category);
  const selectedIndicators = getSelectedIndicatorsForCategory(category);
  const defaultIndicator = getDefaultIndicatorForCategory(category);

  // Restore to original selection (encoded Type|MODE)
  const indicatorsToCheck = selectedIndicators.length > 0
    ? selectedIndicators
    : (defaultIndicator ? [defaultIndicator] : []);

  pendingSelections[categorySafe] = [...indicatorsToCheck];
  const parsed = indicatorsToCheck.map(parseIndicatorEntry).filter(Boolean);
  const typesToCheck = parsed.map((entry) => entry.type);
  const modeByType = {};
  parsed.forEach((entry) => {
    modeByType[entry.type] = entry.mode;
  });

  // Update checkboxes / modes to match original selection
  const categoryStr = getCategoryString(category);
  const availableIndicators = indicatorsByCategoryMap[categoryStr] || [];
  availableIndicators.forEach((indicatorType) => {
    const seriesDomId = getSeriesDomId(indicatorType);
    const checkbox = document.getElementById(
      `${categorySafe}-indicator-${seriesDomId}`
    );
    const modeSelect = document.getElementById(
      `${categorySafe}-mode-${seriesDomId}`
    );
    if (checkbox) {
      checkbox.checked = typesToCheck.includes(indicatorType);
    }
    if (modeSelect) {
      modeSelect.value =
        modeByType[indicatorType] || getDefaultModeForSeriesKey(indicatorType);
    }
  });

  // Close dropdown
  toggleDropdown(category);
}

// Note: removeIndicatorFromCategory removed - using multi-select dropdown with apply/cancel instead


// ==========================================
// Render Charts
// ==========================================

function renderCharts() {
  const chartGrid = document.getElementById("chart-grid");
  chartGrid.innerHTML = "";

  categories.forEach((category) => {
    const categoryStr = getCategoryString(category);
    const categoryData = economicDataByCategory[categoryStr] || [];
    const categorySafe = getCategorySafeName(category);
    const selectedIndicators = getSelectedIndicatorsForCategory(category);
    const defaultIndicator = getDefaultIndicatorForCategory(category);

    // If no default indicator is set, use first available
    let finalSelectedIndicators = selectedIndicators;
    if (finalSelectedIndicators.length === 0 && defaultIndicator) {
      finalSelectedIndicators = [defaultIndicator];
    } else if (finalSelectedIndicators.length === 0) {
      const availableIndicators = indicatorsByCategoryMap[categoryStr] || [];
      if (availableIndicators.length > 0) {
        finalSelectedIndicators = [availableIndicators[0]];
      }
    }

    // Create chart card
    const chartCard = document.createElement("div");
    chartCard.className = "chart-card";

    const chartHeader = document.createElement("div");
    chartHeader.className = "chart-header";
    const chartTitle = document.createElement("h2");
    chartTitle.textContent = categoryStr;
    chartHeader.appendChild(chartTitle);

    const chartWrapper = document.createElement("div");
    chartWrapper.className = "chart-wrapper";
    const canvas = document.createElement("canvas");
    canvas.id = `chart-${categorySafe}`;
    chartWrapper.appendChild(canvas);

    // Indicator selection container (placed below chart)
    const indicatorSelectionContainer = document.createElement("div");
    indicatorSelectionContainer.id = `${categorySafe}-indicator-selection`;
    indicatorSelectionContainer.className = "indicator-selection-container";

    chartCard.appendChild(chartHeader);
    chartCard.appendChild(chartWrapper);
    chartCard.appendChild(indicatorSelectionContainer);
    chartGrid.appendChild(chartCard);

    // Create chart or hide chart area if no data
    // Show chart if we have selected indicators (even if some don't have data yet)
    if (finalSelectedIndicators.length > 0) {
      // Show chart wrapper and indicator selection
      chartWrapper.style.display = "flex";
      indicatorSelectionContainer.style.display = "block";

      // Setup indicator selection
      updateIndicatorSelection(category);

      // Only create chart if we have data
      if (categoryData.length > 0) {
        const chartData = createEconomicChart(category, categoryData, finalSelectedIndicators);
        const ctx = canvas.getContext("2d");

        // Destroy existing chart if any
        if (chartInstances[categorySafe]) {
          chartInstances[categorySafe].destroy();
        }

        chartInstances[categorySafe] = new Chart(ctx, {
          type: "line",
          data: chartData,
          options: {
            plugins: {
              legend: {
                display: true,
                position: "top",
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
                  text: "Data Value",
                },
              },
            },
          },
        });
      } else {
        // Clear any existing chart
        if (chartInstances[categorySafe]) {
          chartInstances[categorySafe].destroy();
          delete chartInstances[categorySafe];
        }
      }
    } else {
      // Hide chart wrapper and indicator selection when no indicators selected
      chartWrapper.style.display = "none";
      indicatorSelectionContainer.style.display = "none";

      // Show message below header
      const noDataMessage = document.createElement("p");
      noDataMessage.className = "no-data-message";
      noDataMessage.textContent = "No data available for this category";
      chartCard.appendChild(noDataMessage);
    }
  });
}

// ==========================================
// Initialize
// ==========================================

document.addEventListener("DOMContentLoaded", () => {
  initializeRegionButtons();
  initializePeriodWindowSelect();
  renderCharts();
});
