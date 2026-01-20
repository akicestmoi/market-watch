// Helper function to format snake_case to "Capped First Letter + space"
function formatParameterName(name) {
    return name
        .split('_')
        .map(word => {
            // Convert csv to CSV (case-insensitive)
            if (word.toLowerCase() === 'csv') {
                return 'CSV';
            }
            return word.charAt(0).toUpperCase() + word.slice(1);
        })
        .join(' ');
}

// Helper function to get method priority for sorting
function getMethodPriority(method) {
    const order = { "GET": 1, "PUT": 2, "PATCH": 3, "POST": 4, "DELETE": 5 };
    return order[method] || 99;
}

// Helper function to sort endpoints by method
function sortEndpointsByMethod(endpoints) {
    return [...endpoints].sort((a, b) => {
        return getMethodPriority(a.method) - getMethodPriority(b.method);
    });
}

// Management API Endpoint Configuration
const ENDPOINTS = {
    marketData: {
        Asset: [
            {
                name: "Generate Base Assets Data",
                description: "Generate base assets data from JSON file.",
                method: "POST",
                path: "/markets/asset/generate-base-assets-data",
                body: null,
                query: null,
            },
            {
                name: "Get Asset Names",
                description: "Get all asset names in the database.",
                method: "GET",
                path: "/markets/asset/get-asset-names",
                body: null,
                query: [
                    { name: "asset_class", type: "select", options: ["EQUITY", "FIXED_INCOME", "CURRENCY", "COMMODITY"], required: false },
                    { name: "asset_type", type: "select", options: ["STOCK", "BOND", "CURRENCY_PAIR", "METAL", "ENERGY"], required: false },
                    { name: "location", type: "select", options: ["US", "EU", "JP", "UK", "CH", "CN"], required: false },
                    { name: "source", type: "select", options: ["GLOBAL_RATES", "YAHOO_FINANCE", "FRED"], required: false },
                ],
            },
            {
                name: "Get Asset Details",
                description: "Get an asset.",
                method: "GET",
                path: "/markets/asset",
                body: null,
                query: [
                    { name: "short_name", type: "text", required: true },
                ],
            },
        ],
        Prices: [
            {
                name: "Ingest Market Prices",
                description: "Ingest market prices gathered from various sources for a specific date. This endpoint scrapes data from multiple sources and stores it in the database.",
                method: "POST",
                path: "/markets/prices/ingest",
                body: [
                    { name: "date", type: "date", required: true },
                ],
                query: null,
            },
            {
                name: "Batch Ingest Market Prices",
                description: "Ingest market prices for specific assets over target periods. This endpoint scrapes historical data for multiple assets.",
                method: "POST",
                path: "/markets/prices/batch-ingest",
                body: [
                    { name: "data", type: "json", required: true, example: '[{"short_name": "EURUSD", "start_date": "2024-01-01", "end_date": "2024-01-31"}]' },
                ],
                query: null,
            },
            {
                name: "Get Market Price",
                description: "Get market price for a specific asset and date.",
                method: "GET",
                path: "/markets/prices",
                body: null,
                query: [
                    { name: "date", type: "date", required: true },
                    { name: "short_name", type: "text", required: true },
                ],
            },
            {
                name: "List All Market Prices",
                description: "List all market prices for a specific date.",
                method: "GET",
                path: "/markets/prices/list-all",
                body: null,
                query: [
                    { name: "date", type: "date", required: true },
                ],
            },
            {
                name: "Get Assets Without Prices",
                description: "Get assets without prices.",
                method: "GET",
                path: "/markets/prices/get-assets-without-prices",
                body: null,
                query: [
                    { name: "start_date", type: "date", required: false },
                    { name: "end_date", type: "date", required: false },
                    { name: "include_holidays", type: "checkbox", required: false },
                ],
            },
            {
                name: "Bulk Update Assets Prices",
                description: "Bulk update assets prices.",
                method: "PATCH",
                path: "/markets/prices/bulk-update",
                body: [
                    { name: "data", type: "json", required: true, example: '[{"short_name": "EURUSD", "date": "2024-01-01", "price": 1.10, "logs": "Manual update"}]' },
                ],
                query: null,
            },
            {
                name: "Bulk Update Assets Prices from CSV",
                description: "Bulk update assets prices from a CSV file.",
                method: "PATCH",
                path: "/markets/prices/bulk-update-from-csv",
                body: [
                    { name: "csv_file", type: "file", required: true },
                ],
                query: null,
            },
            {
                name: "Get Price Update Logs",
                description: "Get price update logs.",
                method: "GET",
                path: "/markets/prices/get-price-update-logs",
                body: null,
                query: [
                    { name: "price_date", type: "date", required: false },
                    { name: "short_name", type: "text", required: false },
                ],
            },
            {
                name: "Delete Market Prices",
                description: "Delete market prices based on optional filters.",
                method: "DELETE",
                path: "/markets/prices",
                body: null,
                query: [
                    { name: "start_date", type: "date", required: false },
                    { name: "end_date", type: "date", required: false },
                    { name: "short_names", type: "text", required: false, placeholder: "Comma-separated list" },
                ],
            },
        ],
        Holiday: [
            {
                name: "Ingest Holidays",
                description: "Ingest holidays.",
                method: "POST",
                path: "/markets/holidays/ingest",
                body: [
                    { name: "date", type: "date", required: false },
                    { name: "location", type: "select", options: ["US", "EU", "JP", "UK", "CH", "CN"], required: false },
                ],
                query: null,
            },
            {
                name: "Get Holidays",
                description: "Get holidays.",
                method: "GET",
                path: "/markets/holidays",
                body: null,
                query: [
                    { name: "location", type: "select", options: ["US", "EU", "JP", "UK", "CH", "CN"], required: false },
                    { name: "year", type: "number", required: false },
                    { name: "months", type: "text", required: false, placeholder: "Comma-separated months (1-12)" },
                ],
            },
        ],
    },
    economicData: {
        Data: [
            {
                name: "Generate Base Economic Indicator Information",
                description: "Generate base economic indicator information from JSON file.",
                method: "POST",
                path: "/economics/indicator/generate-base-information",
                body: null,
                query: null,
            },
            {
                name: "Ingest Economic Data",
                description: "Ingest economic data from various sources.",
                method: "POST",
                path: "/economics/indicator/ingest",
                body: [
                    { name: "start_date", type: "date", required: true },
                    { name: "end_date", type: "date", required: true },
                    { name: "update_schedule", type: "checkbox", required: false },
                ],
                query: null,
            },
            {
                name: "Ingest Specific Economic Data",
                description: "Ingest specific economic data for a specific indicator and period.",
                method: "POST",
                path: "/economics/indicator/ingest-specific",
                body: [
                    { name: "data", type: "json", required: true, example: '[{"indicator_name": "France Consumer Confidence", "periods": ["2024-01", "2024-02"]}]' },
                ],
                query: null,
            },
            {
                name: "Get Economic Data",
                description: "Get economic data detailed for a specific indicator and period.",
                method: "GET",
                path: "/economics/indicator",
                body: null,
                query: [
                    { name: "indicator_names", type: "text", required: false, placeholder: "Comma-separated list" },
                    { name: "period", type: "text", required: false },
                ],
            },
        ],
        Schedule: [
            {
                name: "Update Publication Schedule",
                description: "Update publication schedule.",
                method: "POST",
                path: "/economics/schedule/update",
                body: [
                    { name: "indicator_names", type: "text", required: false, placeholder: "Comma-separated list or JSON array" },
                ],
                query: null,
            },
        ],
    },
    centralBankData: {
        Data: [
            {
                name: "List Central Bank Data",
                description: "List central bank data.",
                method: "GET",
                path: "/central-banks/data",
                body: null,
                query: [
                    { name: "central_banks", type: "text", required: false, placeholder: "Comma-separated: FRB,ECB,BOJ" },
                    { name: "date", type: "date", required: false },
                    { name: "last_value", type: "checkbox", required: false },
                ],
            },
            {
                name: "Ingest Central Bank Data",
                description: "Ingest central bank data.",
                method: "POST",
                path: "/central-banks/data/ingest",
                body: [
                    { name: "data", type: "json", required: true, example: '[{"central_bank": "FRB", "date": "2024-01-01"}]' },
                ],
                query: null,
            },
        ],
        "STIR Futures Prices": [
            {
                name: "List STIR Futures Prices",
                description: "List Stir Futures Prices for a given date.",
                method: "GET",
                path: "/central-banks/stir-futures",
                body: null,
                query: [
                    { name: "central_banks", type: "text", required: false, placeholder: "Comma-separated: FRB,ECB,BOJ" },
                    { name: "date", type: "date", required: false },
                ],
            },
            {
                name: "Ingest STIR Futures Prices",
                description: "Ingest STIR futures prices.",
                method: "POST",
                path: "/central-banks/stir-futures/ingest",
                body: [
                    { name: "date", type: "date", required: true },
                ],
                query: null,
            },
            {
                name: "Ingest ESTR Price via PDF",
                description: "Ingest ESTR price via PDF.",
                method: "POST",
                path: "/central-banks/stir-futures/ingest-estr-pdf",
                body: [
                    { name: "pdf_file", type: "file", required: true },
                    { name: "date", type: "date", required: true },
                ],
                query: null,
            },
            {
                name: "Bulk Update STIR Futures Prices",
                description: "Bulk update stir futures prices.",
                method: "PATCH",
                path: "/central-banks/stir-futures/bulk-update",
                body: [
                    { name: "data", type: "json", required: true, example: '[{"date": "2024-01-01", "short_name": "ESTR", "maturity": "2024-03", "price": 95.5, "logs": "Manual update"}]' },
                ],
                query: null,
            },
            {
                name: "Bulk Update STIR Futures Prices from CSV",
                description: "Bulk update stir futures prices from a CSV file.",
                method: "PATCH",
                path: "/central-banks/stir-futures/bulk-update-from-csv",
                body: [
                    { name: "csv_file", type: "file", required: true },
                ],
                query: null,
            },
            {
                name: "Get Central Bank Probability Matrix",
                description: "Get central bank probability matrix.",
                method: "GET",
                path: "/central-banks/probability-matrix",
                body: null,
                query: [
                    { name: "central_banks", type: "text", required: false, placeholder: "Comma-separated: FRB,ECB,BOJ" },
                    { name: "date", type: "date", required: true },
                ],
            },
            {
                name: "Delete STIR Futures Prices",
                description: "Delete STIR futures prices based on optional filters.",
                method: "DELETE",
                path: "/central-banks/stir-futures",
                body: null,
                query: [
                    { name: "start_date", type: "date", required: false },
                    { name: "end_date", type: "date", required: false },
                    { name: "central_banks", type: "text", required: false, placeholder: "Comma-separated: FRB,ECB,BOJ" },
                ],
            },
        ],
        "Meeting Dates": [
            {
                name: "Get Central Bank Meeting Dates",
                description: "Get central bank meeting dates.",
                method: "GET",
                path: "/central-banks/meeting-dates",
                body: null,
                query: [
                    { name: "central_banks", type: "text", required: false, placeholder: "Comma-separated: FRB,ECB,BOJ" },
                ],
            },
            {
                name: "Ingest Central Bank Meeting Dates",
                description: "Ingest central bank meeting dates.",
                method: "POST",
                path: "/central-banks/meeting-dates/ingest",
                body: null,
                query: null,
            },
        ],
    },
};

// Store endpoint references
const endpointMap = new Map();
let currentEndpointIndex = null;
let pendingDeleteRequest = null; // Store delete request data for confirmation

// Initialize the management interface
document.addEventListener("DOMContentLoaded", function () {
    let globalIndex = 0;

    // Render market data endpoints
    const marketContainer = document.getElementById("market-data-endpoints");
    Object.entries(ENDPOINTS.marketData).forEach(([subcategory, endpoints]) => {
        const sortedEndpoints = sortEndpointsByMethod(endpoints);
        const subcategorySection = createSubcategorySection(subcategory, sortedEndpoints, globalIndex, "marketData");
        marketContainer.appendChild(subcategorySection.container);
        sortedEndpoints.forEach((endpoint) => {
            const card = createEndpointCard(endpoint, globalIndex, "marketData");
            subcategorySection.grid.appendChild(card);
            endpointMap.set(globalIndex, { category: "marketData", subcategory, endpoint });
            globalIndex++;
        });
    });

    // Render economic data endpoints
    const economicContainer = document.getElementById("economic-data-endpoints");
    Object.entries(ENDPOINTS.economicData).forEach(([subcategory, endpoints]) => {
        const sortedEndpoints = sortEndpointsByMethod(endpoints);
        const subcategorySection = createSubcategorySection(subcategory, sortedEndpoints, globalIndex, "economicData");
        economicContainer.appendChild(subcategorySection.container);
        sortedEndpoints.forEach((endpoint) => {
            const card = createEndpointCard(endpoint, globalIndex, "economicData");
            subcategorySection.grid.appendChild(card);
            endpointMap.set(globalIndex, { category: "economicData", subcategory, endpoint });
            globalIndex++;
        });
    });

    // Render central bank data endpoints
    const centralBankContainer = document.getElementById("central-bank-data-endpoints");
    Object.entries(ENDPOINTS.centralBankData).forEach(([subcategory, endpoints]) => {
        const sortedEndpoints = sortEndpointsByMethod(endpoints);
        const subcategorySection = createSubcategorySection(subcategory, sortedEndpoints, globalIndex, "centralBankData");
        centralBankContainer.appendChild(subcategorySection.container);
        sortedEndpoints.forEach((endpoint) => {
            const card = createEndpointCard(endpoint, globalIndex, "centralBankData");
            subcategorySection.grid.appendChild(card);
            endpointMap.set(globalIndex, { category: "centralBankData", subcategory, endpoint });
            globalIndex++;
        });
    });
});

function createSubcategorySection(subcategory, endpoints, startIndex, category) {
    const container = document.createElement("div");
    container.className = "subcategory-section";

    const title = document.createElement("h3");
    title.className = "subcategory-title";
    title.textContent = subcategory;
    container.appendChild(title);

    const grid = document.createElement("div");
    grid.className = "endpoints-grid";
    container.appendChild(grid);

    return { container, grid };
}

function createEndpointCard(endpoint, index, category) {
    const card = document.createElement("div");
    const methodClass = `endpoint-card-method-${endpoint.method.toLowerCase()}`;
    card.className = `endpoint-card ${methodClass}`;
    card.id = `endpoint-${index}`;
    card.dataset.category = category;
    card.onclick = () => openFormModal(index);

    card.innerHTML = `
        <div class="endpoint-name">${endpoint.name}</div>
        <div class="endpoint-description">${endpoint.description}</div>
    `;

    return card;
}

function openFormModal(index) {
    currentEndpointIndex = index;
    const entry = endpointMap.get(index);
    if (!entry) return;

    const endpoint = entry.endpoint;
    const modal = document.getElementById("form-modal-overlay");
    const modalTitle = document.getElementById("form-modal-title");
    const modalBody = document.getElementById("form-modal-body");

    modalTitle.textContent = endpoint.name;
    modalBody.innerHTML = createFormFields(endpoint, index);

    modal.classList.add("active");
}

function closeFormModal() {
    const modal = document.getElementById("form-modal-overlay");
    modal.classList.remove("active");
    currentEndpointIndex = null;
}

function createFormFields(endpoint, index) {
    let html = "";

    // Query parameters
    if (endpoint.query && endpoint.query.length > 0) {
        endpoint.query.forEach((param) => {
            html += createFormField(param, `query-${index}`, false);
        });
    }

    // Body parameters
    if (endpoint.body && endpoint.body.length > 0) {
        endpoint.body.forEach((param) => {
            html += createFormField(param, `body-${index}`, true);
        });
    }

    return html || "<p>No parameters required for this endpoint.</p>";
}

function createFormField(param, prefix, isBody) {
    const fieldId = `${prefix}-${param.name}`;
    const required = param.required ? "required" : "";
    const formattedName = formatParameterName(param.name);
    const requiredText = param.required ? "(required)" : "";
    let inputHtml = "";

    if (param.type === "select") {
        inputHtml = `
            <select id="${fieldId}" name="${param.name}" ${required} style="width: 100%; box-sizing: border-box;">
                <option value="">-- Select --</option>
                ${param.options.map(opt => `<option value="${opt}">${opt}</option>`).join("")}
            </select>
        `;
    } else if (param.type === "checkbox") {
        inputHtml = `
            <div class="checkbox-label">
                <input type="checkbox" id="${fieldId}" name="${param.name}" ${required}>
                <label for="${fieldId}">${formattedName} ${requiredText}</label>
            </div>
        `;
        // For checkboxes, return early since the label is inside the inputHtml
        return `
            <div class="form-group">
                ${inputHtml}
            </div>
        `;
    } else if (param.type === "json") {
        inputHtml = `
            <textarea id="${fieldId}" name="${param.name}" ${required} placeholder="${param.example || ''}" style="width: 100%; box-sizing: border-box;"></textarea>
        `;
    } else if (param.type === "file") {
        inputHtml = `
            <input type="file" id="${fieldId}" name="${param.name}" ${required} style="width: 100%; box-sizing: border-box;">
        `;
    } else if (param.type === "number") {
        inputHtml = `
            <input type="number" id="${fieldId}" name="${param.name}" ${required} placeholder="${param.placeholder || ''}" style="width: 100%; box-sizing: border-box;">
        `;
    } else {
        inputHtml = `
            <input type="${param.type}" id="${fieldId}" name="${param.name}" ${required} placeholder="${param.placeholder || ''}" style="width: 100%; box-sizing: border-box;">
        `;
    }

    return `
        <div class="form-group">
            <label for="${fieldId}">${formattedName} ${requiredText}</label>
            ${inputHtml}
        </div>
    `;
}

async function confirmRequest() {
    if (currentEndpointIndex === null) return;

    const entry = endpointMap.get(currentEndpointIndex);
    if (!entry) return;

    const endpoint = entry.endpoint;
    const index = currentEndpointIndex;

    // Collect query parameters
    const queryParams = new URLSearchParams();
    const queryData = {};
    if (endpoint.query) {
        endpoint.query.forEach((param) => {
            const input = document.getElementById(`query-${index}-${param.name}`);
            if (input) {
                if (param.type === "checkbox") {
                    if (input.checked) {
                        queryParams.append(param.name, "true");
                        queryData[param.name] = "true";
                    }
                } else if (input.value) {
                    queryParams.append(param.name, input.value);
                    queryData[param.name] = input.value;
                }
            }
        });
    }

    // Build URL
    let url = endpoint.path;
    if (queryParams.toString()) {
        url += "?" + queryParams.toString();
    }

    // Prepare request options
    const options = {
        method: endpoint.method,
        headers: {},
    };

    // Handle body for POST and PATCH (DELETE uses query params only)
    if (["POST", "PATCH"].includes(endpoint.method)) {
        if (endpoint.body) {
            const formData = new FormData();
            let hasBodyData = false;
            let jsonBody = null;

            endpoint.body.forEach((param) => {
                const input = document.getElementById(`body-${index}-${param.name}`);
                if (input) {
                    if (param.type === "file") {
                        if (input.files && input.files[0]) {
                            formData.append(param.name, input.files[0]);
                            hasBodyData = true;
                        }
                    } else if (param.type === "json") {
                        if (input.value) {
                            try {
                                jsonBody = JSON.parse(input.value);
                                hasBodyData = true;
                            } catch (e) {
                                throw new Error(`Invalid JSON: ${e.message}`);
                            }
                        }
                    } else if (param.type === "checkbox") {
                        if (input.checked) {
                            formData.append(param.name, "true");
                            hasBodyData = true;
                        }
                    } else if (input.value) {
                        formData.append(param.name, input.value);
                        hasBodyData = true;
                    }
                }
            });

            if (jsonBody !== null) {
                options.headers["Content-Type"] = "application/json";
                options.body = JSON.stringify(jsonBody);
            } else if (hasBodyData) {
                // Check if we have file uploads
                const hasFiles = Array.from(formData.entries()).some(([key, value]) => value instanceof File);
                if (hasFiles) {
                    options.body = formData;
                } else {
                    // Convert FormData to JSON if no files
                    const bodyObj = {};
                    formData.forEach((value, key) => {
                        bodyObj[key] = value;
                    });
                    options.headers["Content-Type"] = "application/json";
                    options.body = JSON.stringify(bodyObj);
                }
            }
        }
    }

    // If DELETE method, show confirmation modal instead
    if (endpoint.method === "DELETE") {
        // Store request data for later execution
        pendingDeleteRequest = { url, options, endpoint, queryData };

        // Close form modal
        closeFormModal();

        // Show delete confirmation modal
        showDeleteConfirmationModal(endpoint, queryData);
        return;
    }

    // For non-DELETE methods, proceed directly
    // Close form modal first
    closeFormModal();

    try {
        // Show loading modal
        showLoadingModal();

        // Make the request
        const response = await fetch(url, options);
        const responseData = await response.json();

        // Hide loading modal
        hideLoadingModal();

        // Show result modal
        showResultModal(response.ok, response.status, response.statusText, responseData);
    } catch (error) {
        // Hide loading modal
        hideLoadingModal();

        // Show result modal with error
        showResultModal(false, 0, "Error", { error: error.message });
    }
}

async function executeDeleteRequest() {
    if (!pendingDeleteRequest) return;

    const { url, options } = pendingDeleteRequest;

    // Close delete confirmation modal
    closeDeleteConfirmationModal();

    try {
        // Show loading modal
        showLoadingModal();

        // Make the request
        const response = await fetch(url, options);
        const responseData = await response.json();

        // Hide loading modal
        hideLoadingModal();

        // Show result modal
        showResultModal(response.ok, response.status, response.statusText, responseData);

        // Clear pending request
        pendingDeleteRequest = null;
    } catch (error) {
        // Hide loading modal
        hideLoadingModal();

        // Show result modal with error
        showResultModal(false, 0, "Error", { error: error.message });

        // Clear pending request
        pendingDeleteRequest = null;
    }
}

function showDeleteConfirmationModal(endpoint, queryData) {
    const modal = document.getElementById("delete-confirmation-modal-overlay");
    const conditionsContainer = document.getElementById("delete-conditions");

    // Build conditions HTML
    let conditionsHtml = "";
    let hasConditions = false;

    if (endpoint.query && endpoint.query.length > 0) {
        endpoint.query.forEach((param) => {
            const formattedName = formatParameterName(param.name);
            const value = queryData[param.name];

            if (value !== undefined && value !== null && value !== "") {
                hasConditions = true;
                conditionsHtml += `
                    <div class="delete-condition-item">
                        <span class="delete-condition-label">${formattedName}:</span>
                        <span class="delete-condition-value">${value}</span>
                    </div>
                `;
            }
        });
    }

    if (!hasConditions) {
        conditionsHtml = '<div class="delete-condition-item delete-condition-empty">No specific conditions - all matching records will be deleted</div>';
    }

    conditionsContainer.innerHTML = conditionsHtml;

    // Show modal
    modal.classList.add("active");
}

function closeDeleteConfirmationModal() {
    const modal = document.getElementById("delete-confirmation-modal-overlay");
    modal.classList.remove("active");
    pendingDeleteRequest = null;
}

function showResultModal(isSuccess, status, statusText, data) {
    const modal = document.getElementById("result-modal-overlay");
    const modalHeader = document.getElementById("result-modal-header");
    const modalTitle = document.getElementById("result-modal-title");
    const modalContent = document.getElementById("result-modal-content");

    // Update header styling
    modalHeader.className = `result-modal-header ${isSuccess ? "success" : "error"}`;
    modalTitle.className = `result-modal-title ${isSuccess ? "success" : "error"}`;
    modalTitle.textContent = isSuccess ? "Success" : "Error";

    // Update content
    const statusInfo = status ? `Status: ${status} ${statusText}\n\n` : "";
    modalContent.textContent = statusInfo + JSON.stringify(data, null, 2);

    // Show modal
    modal.classList.add("active");
}

function closeResultModal() {
    const modal = document.getElementById("result-modal-overlay");
    modal.classList.remove("active");
}

function showLoadingModal() {
    const modal = document.getElementById("loading-modal-overlay");
    modal.classList.add("active");
}

function hideLoadingModal() {
    const modal = document.getElementById("loading-modal-overlay");
    modal.classList.remove("active");
}

// Close modals when clicking outside
document.addEventListener("click", function(event) {
    const formModal = document.getElementById("form-modal-overlay");
    const resultModal = document.getElementById("result-modal-overlay");
    const deleteConfirmationModal = document.getElementById("delete-confirmation-modal-overlay");

    if (event.target === formModal) {
        closeFormModal();
    }
    if (event.target === resultModal) {
        closeResultModal();
    }
    if (event.target === deleteConfirmationModal) {
        closeDeleteConfirmationModal();
    }
});
