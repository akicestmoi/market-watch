// ==========================================
// Load Django context data
// ==========================================
const dropdownValues = window.dropdownValuesJSON;
const marketData = window.marketDataJSON;
const selectedValues = window.selectedValuesJSON;
const labels = window.labelsJSON;

// ==========================================
// Dropdown Population Utilities
// ==========================================

/**
 * Populate a standard dropdown with options
 */
function populateDropdown(selectId, options, selectedValue) {
  const select = document.getElementById(selectId);
  select.innerHTML = "";

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.text = "-- Select value --";
  placeholder.disabled = true;
  placeholder.selected = !selectedValue;
  select.appendChild(placeholder);

  options.forEach((opt) => {
    const option = document.createElement("option");

    if (selectId === "yieldCurveLocationSelect") {
      option.value = opt;
      option.text = opt;
      if (opt === selectedValue) {
        option.selected = true;
        placeholder.selected = false;
      }
    } else {
      option.value = opt.short_name;
      option.text = opt.full_name;
      if (String(opt.short_name) === String(selectedValue)) {
        option.selected = true;
        placeholder.selected = false;
      }
    }
    select.appendChild(option);
  });
}

/**
 * Populate comparison dropdown (excludes main selected asset)
 */
function populateComparisonDropdown(
  selectId,
  options,
  selectedValue,
  removeFromOptions = null
) {
  const select = document.getElementById(selectId);
  select.innerHTML = '<option value="">-- Compare Prices --</option>';

  options.forEach((opt) => {
    // Skip the currently selected main asset
    if (removeFromOptions && opt.short_name === removeFromOptions) return;

    const option = document.createElement("option");
    option.value = opt.short_name;
    option.text = opt.full_name;
    if (String(opt.short_name) === String(selectedValue)) {
      option.selected = true;
    }
    select.appendChild(option);
  });
}

// ==========================================
// Event Handlers
// ==========================================

/**
 * Handle dropdown change by updating URL params
 */
function handleDropdownChange(selectId, paramKey) {
  const select = document.getElementById(selectId);
  select.addEventListener("change", (e) => {
    const selected = e.target.value;
    if (!selected) return;
    const params = new URLSearchParams(window.location.search);
    params.set(paramKey, selected);
    window.location.search = params.toString();
  });
}

/**
 * Handle remove button click for comparison
 */
function handleRemoveComparison(btnId, paramKey) {
  const btn = document.getElementById(btnId);
  btn.addEventListener("click", () => {
    const params = new URLSearchParams(window.location.search);
    params.delete(paramKey);
    window.location.search = params.toString();
  });
}

/**
 * Show/hide remove button based on comparison state
 */
function toggleRemoveButton(btnId, hasComparison) {
  const btn = document.getElementById(btnId);
  if (hasComparison) {
    btn.classList.remove("hidden");
  } else {
    btn.classList.add("hidden");
  }
}

// ==========================================
// Chart Creation Functions
// ==========================================

/**
 * Create a line chart with optional comparison line
 */
function createLineChart(
  assetId,
  data,
  titleLabel,
  assetName,
  headerId,
  color = "rgb(75, 192, 192)",
  compareData = null,
  compareAssetName = null,
  compareColor = "rgb(255, 159, 64)"
) {
  const ctx = document.getElementById(assetId).getContext("2d");
  const header = document.getElementById(headerId);
  header.innerText = titleLabel;

  const hasComparison = compareData && compareData.length > 0 && compareAssetName;

  const datasets = [
    {
      label: assetName,
      data: data.map((d) => d.price),
      borderColor: color,
      backgroundColor: "rgba(75,192,192,0.1)",
      tension: 0.3,
      fill: true,
      pointRadius: 3,
      yAxisID: "y",
    },
  ];

  // Add comparison dataset if provided
  if (hasComparison) {
    datasets.push({
      label: compareAssetName,
      data: compareData.map((d) => d.price),
      borderColor: compareColor,
      backgroundColor: "rgba(255,159,64,0.1)",
      tension: 0.3,
      fill: false,
      pointRadius: 3,
      borderDash: [5, 5],
      yAxisID: "y1",
    });
  }

  const scales = {
    x: { title: { display: true, text: "Date" } },
    y: {
      type: "linear",
      display: true,
      position: "left",
      title: {
        display: true,
        text: `${assetName} (prices)`,
      },
    },
  };

  // Add right y-axis for comparison
  if (hasComparison) {
    scales.y1 = {
      type: "linear",
      display: true,
      position: "right",
      title: {
        display: true,
        text: `${compareAssetName} (prices)`,
      },
      grid: {
        drawOnChartArea: false,
      },
    };
  }

  return new Chart(ctx, {
    type: "line",
    data: {
      labels: data.map((d) => d.price_date),
      datasets: datasets,
    },
    options: {
      plugins: {
        legend: {
          display: true,
          position: "top",
        },
      },
      responsive: true,
      maintainAspectRatio: false,
      scales: scales,
    },
  });
}

/**
 * Create yield curve chart with optional previous curve
 */
function createYieldCurveChart(
  assetId,
  data,
  previous_data = null,
  locationLabel,
  headerId = "yieldHeader",
  color = "#0ea5e9"
) {
  const ctx = document.getElementById(assetId).getContext("2d");
  const header = document.getElementById(headerId);
  header.innerText = locationLabel;

  const labelsX = data.map((pt) => `${pt.maturity}Y`);
  const datasets = [
    {
      label: "Current curve",
      data: data.map((pt) => pt.price),
      borderColor: color,
      fill: false,
      tension: 0.3,
      pointRadius: 3,
    },
  ];

  if (Array.isArray(previous_data) && previous_data.length > 0) {
    datasets.push({
      label: "Previous curve",
      data: previous_data.map((pt) => pt.price),
      borderColor: color,
      borderDash: [5, 5],
      fill: false,
      tension: 0.3,
      pointRadius: 3,
    });
  }

  return new Chart(ctx, {
    type: "line",
    data: { labels: labelsX, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: true } },
      scales: {
        x: { title: { display: true, text: "Maturity (Years)" } },
        y: { title: { display: true, text: "Yield (%)" } },
      },
    },
  });
}

/**
 * Create yield spread chart
 */
function createYieldSpreadChart(
  assetId,
  data,
  mainRate,
  spreadRate,
  headerId,
  color = "rgb(153,102,255)"
) {
  const ctx = document.getElementById(assetId).getContext("2d");
  const header = document.getElementById(headerId);
  const label = `Yield Spread: ${mainRate} - ${spreadRate}`;
  header.innerText = label;

  return new Chart(ctx, {
    type: "line",
    data: {
      labels: data.map((d) => d.price_date),
      datasets: [
        {
          label: label,
          data: data.map((d) => d.price),
          borderColor: color,
          backgroundColor: "rgba(153,102,255,0.1)",
          tension: 0.3,
          fill: true,
          pointRadius: 3,
        },
      ],
    },
    options: {
      plugins: { legend: { display: false } },
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { title: { display: true, text: "Date" } },
        y: { title: { display: true, text: "Spread (bps)" } },
      },
    },
  });
}

// ==========================================
// Initialize Dropdowns
// ==========================================

// Main asset dropdowns
populateDropdown(
  "yieldCurveLocationSelect",
  dropdownValues.locations,
  selectedValues.yield_curve_location
);
populateDropdown("stockSelect", dropdownValues.stocks, selectedValues.stock_name);
populateDropdown("fxSelect", dropdownValues.fx, selectedValues.fx_name);
populateDropdown(
  "commoditySelect",
  dropdownValues.commodity,
  selectedValues.commodity_name
);
populateDropdown("cryptoSelect", dropdownValues.crypto, selectedValues.crypto_name);
populateDropdown("mainRateSelect", dropdownValues.rates, selectedValues.main_rate);
populateDropdown(
  "spreadRateSelect",
  dropdownValues.rates,
  selectedValues.spread_rate
);

// Comparison dropdowns
populateComparisonDropdown(
  "stockCompareSelect",
  dropdownValues.stocks,
  selectedValues.stock_name_compare,
  selectedValues.stock_name
);
populateComparisonDropdown(
  "fxCompareSelect",
  dropdownValues.fx,
  selectedValues.fx_name_compare,
  selectedValues.fx_name
);
populateComparisonDropdown(
  "commodityCompareSelect",
  dropdownValues.commodity,
  selectedValues.commodity_name_compare,
  selectedValues.commodity_name
);
populateComparisonDropdown(
  "cryptoCompareSelect",
  dropdownValues.crypto,
  selectedValues.crypto_name_compare,
  selectedValues.crypto_name
);

// ==========================================
// Attach Event Handlers
// ==========================================

// Main dropdown handlers
handleDropdownChange("yieldCurveLocationSelect", "yield_curve_location");
handleDropdownChange("stockSelect", "stock_name");
handleDropdownChange("fxSelect", "fx_name");
handleDropdownChange("commoditySelect", "commodity_name");
handleDropdownChange("cryptoSelect", "crypto_name");
handleDropdownChange("mainRateSelect", "main_rate");
handleDropdownChange("spreadRateSelect", "spread_rate");

// Comparison dropdown handlers
handleDropdownChange("stockCompareSelect", "stock_name_compare");
handleDropdownChange("fxCompareSelect", "fx_name_compare");
handleDropdownChange("commodityCompareSelect", "commodity_name_compare");
handleDropdownChange("cryptoCompareSelect", "crypto_name_compare");

// Remove button handlers
handleRemoveComparison("stockRemoveBtn", "stock_name_compare");
handleRemoveComparison("fxRemoveBtn", "fx_name_compare");
handleRemoveComparison("commodityRemoveBtn", "commodity_name_compare");
handleRemoveComparison("cryptoRemoveBtn", "crypto_name_compare");

// Toggle remove button visibility
toggleRemoveButton("stockRemoveBtn", selectedValues.stock_name_compare);
toggleRemoveButton("fxRemoveBtn", selectedValues.fx_name_compare);
toggleRemoveButton("commodityRemoveBtn", selectedValues.commodity_name_compare);
toggleRemoveButton("cryptoRemoveBtn", selectedValues.crypto_name_compare);

// ==========================================
// Create and Render Charts
// ==========================================

createLineChart(
  "stockChart",
  marketData.stock_prices,
  `Stocks: ${labels.stocks}`,
  labels.stocks,
  "stockHeader",
  "rgb(75, 192, 192)",
  marketData.stock_prices_compare,
  labels.stock_name_compare,
  "rgb(75, 192, 192)"
);

createLineChart(
  "fxChart",
  marketData.fx_prices,
  `FX: ${labels.fx}`,
  labels.fx,
  "fxHeader",
  "rgb(255,99,132)",
  marketData.fx_prices_compare,
  labels.fx_name_compare,
  "rgb(255,99,132)"
);

const yieldCurveChartInstance = createYieldCurveChart(
  "yieldCurveChart",
  marketData.reference_yield_curve,
  marketData.previous_yield_curve,
  `Yield Curve: ${labels.yield_curve_location}`
);

createLineChart(
  "commodityChart",
  marketData.commodity_prices,
  `Commodity: ${labels.commodity}`,
  labels.commodity,
  "commodityHeader",
  "rgb(54,162,235)",
  marketData.commodity_prices_compare,
  labels.commodity_name_compare,
  "rgb(153, 102, 255)"
);

createLineChart(
  "cryptoChart",
  marketData.crypto_prices,
  `Crypto: ${labels.crypto}`,
  labels.crypto,
  "cryptoHeader",
  "rgb(255,206,86)",
  marketData.crypto_prices_compare,
  labels.crypto_name_compare,
  "rgb(255, 99, 132)"
);

createYieldSpreadChart(
  "yieldSpreadChart",
  marketData.spread_rates,
  labels.main_rate,
  labels.spread_rate,
  "spreadHeader"
);

// ==========================================
// Yield Curve Previous Date Handler
// ==========================================

const previousCurveDateInput = document.getElementById("previousCurveDate");
if (previousCurveDateInput) {
  // Set initial value from backend
  if (selectedValues.previous_curve_date) {
    previousCurveDateInput.value = selectedValues.previous_curve_date;
  }

  // Handle date change
  previousCurveDateInput.addEventListener("change", function (e) {
    const previousCurveDate = e.target.value;
    if (!previousCurveDate) return;

    // Get current parameters from URL
    const params = new URLSearchParams(window.location.search);

    // Update the previous_curve_date parameter
    params.set("previous_curve_date", previousCurveDate);

    // Reload the page with new parameters
    window.location.search = params.toString();
  });
}

// ==========================================
// Duration Button Functionality
// ==========================================

/**
 * Initialize duration buttons for all charts (except yield curve)
 */
function initializeDurationButtons() {
  // Get all duration button containers
  const durationContainers = document.querySelectorAll('.duration-buttons');

  durationContainers.forEach(container => {
    const chartType = container.getAttribute('data-chart-type');
    const buttons = container.querySelectorAll('.duration-btn');

    // Set active button based on current chart duration from selectedValues
    const currentDuration = selectedValues[`${chartType}_chart_duration`];
    buttons.forEach(button => {
      if (button.getAttribute('data-duration') === currentDuration) {
        button.classList.add('active');
      } else {
        button.classList.remove('active');
      }
    });

    buttons.forEach(button => {
      button.addEventListener('click', function() {
        const duration = this.getAttribute('data-duration');

        // Remove active class from all buttons in this container
        buttons.forEach(btn => btn.classList.remove('active'));

        // Add active class to clicked button
        this.classList.add('active');

        // Update specific chart duration
        updateChartDuration(chartType, duration);
      });
    });
  });
}

/**
 * Update specific chart duration and reload data
 */
function updateChartDuration(chartType, duration) {
  // Get current parameters from URL
  const params = new URLSearchParams(window.location.search);

  // Update the specific chart duration parameter
  params.set(`${chartType}_chart_duration`, duration);

  // Reload the page with new parameters
  window.location.search = params.toString();
}

// ==========================================
// Initialize Duration Buttons
// ==========================================

// Initialize duration buttons when the page loads
initializeDurationButtons();
