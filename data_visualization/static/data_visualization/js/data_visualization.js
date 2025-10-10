// ===== Load Django context data =====
const dropdownValues = window.dropdownValuesJSON;
const marketData = window.marketDataJSON;
const selectedValues = window.selectedValuesJSON;
const labels = window.labelsJSON;

// ===== Helper: populate dropdown =====
function populateDropdown(selectId, options, selectedValue) {
    const select = document.getElementById(selectId);
    select.innerHTML = "";

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.text = "-- Select value --";
    placeholder.disabled = true;
    placeholder.selected = !selectedValue;
    select.appendChild(placeholder);

    options.forEach(opt => {
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

// ===== Populate dropdowns =====
populateDropdown("yieldCurveLocationSelect", dropdownValues.locations, selectedValues.yield_curve_location);
populateDropdown("stockSelect", dropdownValues.stocks, selectedValues.stock_name);
populateDropdown("fxSelect", dropdownValues.fx, selectedValues.fx_name);
populateDropdown("commoditySelect", dropdownValues.commodity, selectedValues.commodity_name);
populateDropdown("cryptoSelect", dropdownValues.crypto, selectedValues.crypto_name);
populateDropdown("mainRateSelect", dropdownValues.rates, selectedValues.main_rate);
populateDropdown("spreadRateSelect", dropdownValues.rates, selectedValues.spread_rate);

// ===== Dropdown reload handler =====
function handleDropdownChange(selectId, paramKey) {
    const select = document.getElementById(selectId);
    select.addEventListener("change", e => {
        const selected = e.target.value;
        if (!selected) return;
        const params = new URLSearchParams(window.location.search);
        params.set(paramKey, selected);
        window.location.search = params.toString();
    });
}

handleDropdownChange("yieldCurveLocationSelect", "yield_curve_location");
handleDropdownChange("stockSelect", "stock_name");
handleDropdownChange("fxSelect", "fx_name");
handleDropdownChange("commoditySelect", "commodity_name");
handleDropdownChange("cryptoSelect", "crypto_name");
handleDropdownChange("mainRateSelect", "main_rate");
handleDropdownChange("spreadRateSelect", "spread_rate");

// ===== Chart builders =====
function createLineChart(assetId, data, label, headerId, color = "rgb(75, 192, 192)") {
    const ctx = document.getElementById(assetId).getContext("2d");
    const header = document.getElementById(headerId);
    header.innerText = label;

    return new Chart(ctx, {
        type: "line",
        data: {
            labels: data.map(d => d.price_date),
            datasets: [{
                label: label,
                data: data.map(d => d.price),
                borderColor: color,
                backgroundColor: "rgba(75,192,192,0.1)",
                tension: 0.3,
                fill: true,
                pointRadius: 3
            }]
        },
        options: {
            plugins: { legend: { display: false } },
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { title: { display: true, text: "Date" } },
                y: { title: { display: true, text: "Price" } }
            }
        }
    });
}

function createYieldCurveChart(assetId, data, previous_data = null, locationLabel, headerId = "yieldHeader", color = "#0ea5e9") {
    const ctx = document.getElementById(assetId).getContext("2d");
    const header = document.getElementById(headerId);
    header.innerText = locationLabel;

    const labelsX = data.map((pt) => `${pt.maturity}Y`);
    const datasets = [{
        label: "Current curve",
        data: data.map((pt) => pt.price),
        borderColor: color,
        fill: false,
        tension: 0.3,
        pointRadius: 3
    }];

    if (Array.isArray(previous_data) && previous_data.length > 0) {
        datasets.push({
            label: "Previous curve",
            data: previous_data.map((pt) => pt.price),
            borderColor: color,
            borderDash: [5, 5],
            fill: false,
            tension: 0.3,
            pointRadius: 3
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
                y: { title: { display: true, text: "Yield (%)" } }
            }
        }
    });
}

function createYieldSpreadChart(assetId, data, mainRate, spreadRate, headerId, color = "rgb(153,102,255)") {
    const ctx = document.getElementById(assetId).getContext("2d");
    const header = document.getElementById(headerId);
    const label = `Yield Spread: ${mainRate} - ${spreadRate}`;
    header.innerText = label;

    return new Chart(ctx, {
        type: "line",
        data: {
            labels: data.map((d) => d.price_date),
            datasets: [{
                label: label,
                data: data.map((d) => d.price),
                borderColor: color,
                backgroundColor: "rgba(153,102,255,0.1)",
                tension: 0.3,
                fill: true,
                pointRadius: 3
            }]
        },
        options: {
            plugins: { legend: { display: false } },
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { title: { display: true, text: "Date" } },
                y: { title: { display: true, text: "Spread (bps)" } }
            }
        }
    });
}

// ===== Create charts =====
createLineChart("stockChart", marketData.stock_prices, `Stocks: ${labels.stocks}`, "stockHeader");
createLineChart("fxChart", marketData.fx_prices, `FX: ${labels.fx}`, "fxHeader", "rgb(255,99,132)");
let yieldCurveChartInstance = createYieldCurveChart("yieldCurveChart", marketData.reference_yield_curve, marketData.previous_yield_curve, `Yield Curve: ${labels.yield_curve_location}`);
createLineChart("commodityChart", marketData.commodity_prices, `Commodity: ${labels.commodity}`, "commodityHeader", "rgb(54,162,235)");
createLineChart("cryptoChart", marketData.crypto_prices, `Crypto: ${labels.crypto}`, "cryptoHeader", "rgb(255,206,86)");
createYieldSpreadChart("yieldSpreadChart", marketData.spread_rates, labels.main_rate, labels.spread_rate, "spreadHeader");

// ===== Set initial value and handle yield curve previous date change =====
const previousCurveDateInput = document.getElementById("previousCurveDate");
if (previousCurveDateInput) {
    // Set initial value from backend
    if (selectedValues.previous_curve_date) {
        previousCurveDateInput.value = selectedValues.previous_curve_date;
    }
    
    // Handle date change
    previousCurveDateInput.addEventListener("change", function(e) {
        const previousCurveDate = e.target.value;
        if (!previousCurveDate) return;
        
        // Get current parameters from URL
        const params = new URLSearchParams(window.location.search);
        
        // Update the previous_curve_date parameter
        params.set('previous_curve_date', previousCurveDate);
        
        // Reload the page with new parameters
        window.location.search = params.toString();
    });
}
