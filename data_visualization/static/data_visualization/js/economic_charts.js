// ==========================================
// Load Django context data
// ==========================================
const dropdownValues = window.dropdownValuesJSON;
const economicData = window.economicDataJSON;
const categories = window.categoriesJSON;
const selectedValuesRaw = window.selectedValuesJSON || {};
const currentZone = window.currentZone;

// Store chart instances
const chartInstances = {};

// Parse selectedValues - query params come as strings, need to parse lists
const selectedValues = {};
for (const [key, value] of Object.entries(selectedValuesRaw)) {
  if (key === "zone") {
    selectedValues[key] = value;
  } else if (key.endsWith("_indicator")) {
    // Parse list from string (could be JSON array string or comma-separated)
    if (typeof value === "string") {
      try {
        // Try parsing as JSON first
        const parsed = JSON.parse(value);
        selectedValues[key] = Array.isArray(parsed) ? parsed : [parsed].filter(v => v);
      } catch (e) {
        // If not JSON, try comma-separated or single value
        if (value.includes(",")) {
          selectedValues[key] = value.split(",").map(v => v.trim()).filter(v => v);
        } else {
          selectedValues[key] = value ? [value] : [""];
        }
      }
    } else if (Array.isArray(value)) {
      selectedValues[key] = value.filter(v => v);
    } else {
      selectedValues[key] = value ? [value] : [""];
    }
  } else {
    selectedValues[key] = value;
  }
}

// Helper to get zone value (lowercase) from zone label
function getZoneValue(zoneLabel) {
  const zoneMapping = {
    "United States": "us",
    "France": "fr",
    "Japan": "jp",
  };
  return zoneMapping[zoneLabel] || zoneLabel.toLowerCase();
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
} else if (economicData && economicData.category_data) {
  // Legacy format support
  Object.keys(economicData.category_data).forEach((category) => {
    economicDataByCategory[category] = economicData.category_data[category];
  });
}

// Convert indicators_by_category to object keyed by category string
const indicatorsByCategoryMap = {};
const indicatorsByCategoryTypeMap = {}; // Map type -> name for display
if (dropdownValues && dropdownValues.indicators_by_category) {
  dropdownValues.indicators_by_category.forEach((item) => {
    const categoryStr = getCategoryString(item.category);
    const indicators = item.indicators || [];
    // Extract types for filtering
    indicatorsByCategoryMap[categoryStr] = indicators.map(ind =>
      typeof ind === 'string' ? ind : ind.type
    );
    // Create type -> name mapping
    indicators.forEach(ind => {
      if (typeof ind === 'object' && ind.type && ind.name) {
        indicatorsByCategoryTypeMap[ind.type] = ind.name;
      }
    });
  });
}

// ==========================================
// Zone Button Handling
// ==========================================

function initializeZoneButtons() {
  const zoneButtons = document.querySelectorAll(".zone-btn");
  const zoneMapping = {
    US: "United States",
    FR: "France",
    JP: "Japan",
  };

  zoneButtons.forEach((btn) => {
    const zone = btn.dataset.zone;
    const zoneLabel = zoneMapping[zone];

    // Check if this zone matches current zone
    if (zoneLabel === currentZone || (zone === "US" && currentZone.includes("United States"))) {
      btn.classList.add("active");
    }

    btn.addEventListener("click", () => {
      const params = new URLSearchParams(window.location.search);
      params.set("zone", zoneLabel);
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
  const zoneValue = getZoneValue(currentZone);
  const categoryValue = category.toLowerCase().replace(/\s+/g, "_");
  const key = `${zoneValue}_${categoryValue}_indicator`;

  const indicators = selectedValues[key] || [];
  // Filter out empty strings
  return indicators.filter(ind => ind && ind !== "");
}

function getDefaultIndicatorForCategory(category) {
  const indicators = getSelectedIndicatorsForCategory(category);
  return indicators.length > 0 ? indicators[0] : "";
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
  const colors = [
    "#3b82f6",
    "#10b981",
    "#f59e0b",
    "#ef4444",
    "#8b5cf6",
    "#ec4899",
    "#06b6d4",
    "#84cc16",
    "#f97316",
    "#6366f1",
  ];

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

    datasets.push({
      label: indicatorName,
      data: values,
      borderColor: colors[index % colors.length],
      backgroundColor: colors[index % colors.length] + "20",
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

  // Determine which indicators should be checked
  const indicatorsToCheck = selectedIndicators.length > 0
    ? selectedIndicators
    : (defaultIndicator ? [defaultIndicator] : []);

  // Store initial pending selection
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
    ? `${selectedCount} indicator${selectedCount > 1 ? 's' : ''} selected`
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
    const checkboxItem = document.createElement("div");
    checkboxItem.className = "multiselect-checkbox-item";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = `${categorySafe}-indicator-${indicator.name}`;
    checkbox.value = indicator.name;
    checkbox.checked = indicatorsToCheck.includes(indicator.name);
    checkbox.onchange = () => updatePendingSelection(category);

    const label = document.createElement("label");
    label.htmlFor = checkbox.id;
    label.textContent = indicator.full_name;
    label.onclick = (e) => e.stopPropagation();

    checkboxItem.appendChild(checkbox);
    checkboxItem.appendChild(label);
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
    const checkbox = document.getElementById(`${categorySafe}-indicator-${indicatorType}`);
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
    const checkbox = document.getElementById(`${categorySafe}-indicator-${indicatorType}`);
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
    const checkbox = document.getElementById(`${categorySafe}-indicator-${indicatorType}`);
    if (checkbox && checkbox.checked) {
      selected.push(indicatorType);
    }
  });

  pendingSelections[categorySafe] = selected;
}

function applyIndicatorSelection(category) {
  const zoneValue = getZoneValue(currentZone);
  const categoryValue = category.toLowerCase().replace(/\s+/g, "_");
  const key = `${zoneValue}_${categoryValue}_indicator`;

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

  // Restore to original selection
  const indicatorsToCheck = selectedIndicators.length > 0
    ? selectedIndicators
    : (defaultIndicator ? [defaultIndicator] : []);

  pendingSelections[categorySafe] = [...indicatorsToCheck];

  // Update checkboxes to match original selection
  const categoryStr = getCategoryString(category);
  const availableIndicators = indicatorsByCategoryMap[categoryStr] || [];
  availableIndicators.forEach((indicatorType) => {
    const checkbox = document.getElementById(`${categorySafe}-indicator-${indicatorType}`);
    if (checkbox) {
      checkbox.checked = indicatorsToCheck.includes(indicatorType);
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
  initializeZoneButtons();
  renderCharts();
});
