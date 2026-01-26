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
    quickActions: {
        "Common Operations": [
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
                name: "Mark As Holiday",
                description: "Mark market prices as holiday for the given assets and dates. Sets the comment to 'Bank holiday' and price to null.",
                method: "POST",
                path: "/markets/prices/mark-as-holiday",
                bodyAsList: true,
                body: [
                    { name: "data", type: "json", required: true, example: '[{"short_name": "", "date": ""}]' },
                ],
                query: null,
            },
        ],
    },
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

// Add Escape key listener to close modals
document.addEventListener("keydown", function(event) {
    if (event.key === "Escape" || event.keyCode === 27) {
        const formModal = document.getElementById("form-modal-overlay");
        const resultModal = document.getElementById("result-modal-overlay");
        const deleteConfirmationModal = document.getElementById("delete-confirmation-modal-overlay");
        const loadingModal = document.getElementById("loading-modal-overlay");

        // Close modals in order of priority (most specific first)
        if (deleteConfirmationModal && deleteConfirmationModal.classList.contains("active")) {
            closeDeleteConfirmationModal();
        } else if (formModal && formModal.classList.contains("active")) {
            closeFormModal();
        } else if (resultModal && resultModal.classList.contains("active")) {
            closeResultModal();
        }
        // Note: Loading modal is intentionally not closable with Escape
    }
});

function renderDatabaseInformation() {
    const container = document.getElementById("database-info-container");
    if (!container) return;

    const databaseInfo = window.databaseInfoJSON || [];

    if (databaseInfo.length === 0) {
        container.innerHTML = "<p>No database information available.</p>";
        return;
    }

    // Calculate totals
    const totalCount = databaseInfo.reduce((sum, table) => sum + (table.count || 0), 0);
    const totalSizeBytes = databaseInfo.reduce((sum, table) => sum + (table.size_bytes || 0), 0);

    // Format total size (we'll get it from the backend or calculate)
    // For now, we'll sum the size_bytes and format it
    let totalSizeStr = "0 bytes";
    if (totalSizeBytes > 0) {
        // Simple formatting (could be improved)
        if (totalSizeBytes < 1024) {
            totalSizeStr = `${totalSizeBytes} bytes`;
        } else if (totalSizeBytes < 1024 * 1024) {
            totalSizeStr = `${(totalSizeBytes / 1024).toFixed(2)} kB`;
        } else if (totalSizeBytes < 1024 * 1024 * 1024) {
            totalSizeStr = `${(totalSizeBytes / (1024 * 1024)).toFixed(2)} MB`;
        } else {
            totalSizeStr = `${(totalSizeBytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
        }
    }

    // Determine how many rows to show (top 5 + total)
    const showAll = container.dataset.expanded === "true";
    const rowsToShow = showAll ? databaseInfo.length : Math.min(5, databaseInfo.length);

    // Create table
    let html = `
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; background-color: white; border-radius: 0.5rem; overflow: hidden;">
                <thead>
                    <tr style="background-color: #3b82f6; color: white;">
                        <th style="padding: 0.75rem 1rem; text-align: left; font-weight: 600;">Table Name</th>
                        <th style="padding: 0.75rem 1rem; text-align: right; font-weight: 600;">Number of Elements</th>
                        <th style="padding: 0.75rem 1rem; text-align: right; font-weight: 600;">Size</th>
                    </tr>
                </thead>
                <tbody>
    `;

    // Show top rows
    for (let i = 0; i < rowsToShow; i++) {
        const table = databaseInfo[i];
        const rowClass = i % 2 === 0 ? "background-color: #f8fafc;" : "background-color: white;";
        html += `
            <tr style="${rowClass}">
                <td style="padding: 0.75rem 1rem; border-top: 1px solid #e2e8f0; font-size: 0.9rem;">${table.display_name || table.name}</td>
                <td style="padding: 0.75rem 1rem; border-top: 1px solid #e2e8f0; text-align: right;">${(table.count || 0).toLocaleString()}</td>
                <td style="padding: 0.75rem 1rem; border-top: 1px solid #e2e8f0; text-align: right;">${table.size || "Unknown"}</td>
            </tr>
        `;
    }

    // Add total row
    html += `
            <tr style="background-color: #e0f2fe; font-weight: 600; border-top: 2px solid #3b82f6;">
                <td style="padding: 0.75rem 1rem; font-size: 0.9rem;">Total</td>
                <td style="padding: 0.75rem 1rem; text-align: right;">${totalCount.toLocaleString()}</td>
                <td style="padding: 0.75rem 1rem; text-align: right;">${totalSizeStr}</td>
            </tr>
        </tbody>
    </table>
    `;

    // Add expand/collapse button if there are more than 5 tables
    if (databaseInfo.length > 5) {
        html += `
            <button type="button" class="btn-submit" onclick="toggleDatabaseTable()" style="margin-top: 1rem;">
                ${showAll ? "Collapse" : "Expand"}
            </button>
        `;
    }

    html += `</div>`;

    container.innerHTML = html;
}

function toggleDatabaseTable() {
    const container = document.getElementById("database-info-container");
    if (!container) return;

    // Toggle expanded state
    const isExpanded = container.dataset.expanded === "true";
    container.dataset.expanded = (!isExpanded).toString();

    // Re-render
    renderDatabaseInformation();
}

// Make it available globally
window.toggleDatabaseTable = toggleDatabaseTable;

// Initialize the management interface
document.addEventListener("DOMContentLoaded", function () {
    // Render database information
    renderDatabaseInformation();

    let globalIndex = 0;

    // Render quick actions endpoints
    const quickActionsContainer = document.getElementById("quick-actions-endpoints");
    Object.entries(ENDPOINTS.quickActions).forEach(([subcategory, endpoints]) => {
        const sortedEndpoints = sortEndpointsByMethod(endpoints);
        const subcategorySection = createSubcategorySection(subcategory, sortedEndpoints, globalIndex, "quickActions");
        quickActionsContainer.appendChild(subcategorySection.container);
        sortedEndpoints.forEach((endpoint) => {
            const card = createEndpointCard(endpoint, globalIndex, "quickActions");
            subcategorySection.grid.appendChild(card);
            endpointMap.set(globalIndex, { category: "quickActions", subcategory, endpoint });
            globalIndex++;
        });
    });

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

    // Attach event listeners to "Add" buttons after modal is populated
    modalBody.querySelectorAll('.btn-add-element').forEach(btn => {
        btn.addEventListener('click', function() {
            const fieldId = this.getAttribute('data-field-id');
            const fieldName = this.getAttribute('data-field-name');
            const elementStructureJson = this.getAttribute('data-element-structure');
            const prefix = this.getAttribute('data-prefix');
            const elementTitle = this.getAttribute('data-element-title') || 'Item';
            addArrayElement(fieldId, fieldName, elementStructureJson, prefix, elementTitle);
        });
    });

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
            html += createFormField(param, `query-${index}`, false, endpoint);
        });
    }

    // Body parameters - add tabs for POST/PATCH/PUT with JSON body
    if (endpoint.body && endpoint.body.length > 0) {
        const hasJsonBody = endpoint.body.some(p => p.type === "json");
        const isPostLike = ["POST", "PATCH", "PUT"].includes(endpoint.method);

        if (hasJsonBody && isPostLike) {
            // Create tabbed interface for Form vs JSON
            const jsonExample = endpoint.body.find(p => p.type === "json")?.example || "[]";

            html += `
                <div class="body-mode-tabs" style="margin-bottom: 1rem;">
                    <button type="button" class="body-mode-tab active" data-mode="form" data-index="${index}" onclick="switchBodyMode(${index}, 'form')">Form</button>
                    <button type="button" class="body-mode-tab" data-mode="json" data-index="${index}" onclick="switchBodyMode(${index}, 'json')">JSON</button>
                </div>
                <div id="body-mode-form-${index}" class="body-mode-content active">
            `;

            endpoint.body.forEach((param) => {
                html += createFormField(param, `body-${index}`, true, endpoint);
            });

            html += `
                </div>
                <div id="body-mode-json-${index}" class="body-mode-content" style="display: none;">
                    <div class="form-group">
                        <label for="body-raw-json-${index}">JSON Body (required)</label>
                        <textarea id="body-raw-json-${index}" name="raw_json" rows="10" placeholder='${jsonExample.replace(/'/g, "&#39;")}' style="width: 100%; box-sizing: border-box; font-family: monospace; font-size: 0.9rem;"></textarea>
                        <small style="display: block; margin-top: 0.25rem; color: #64748b; font-size: 0.85rem;">Enter valid JSON directly</small>
                    </div>
                </div>
            `;
        } else {
            // Regular body fields without tabs
            endpoint.body.forEach((param) => {
                html += createFormField(param, `body-${index}`, true, endpoint);
            });
        }
    }

    return html || "<p>No parameters required for this endpoint.</p>";
}

function switchBodyMode(index, mode) {
    // Update tab buttons
    document.querySelectorAll(`.body-mode-tab[data-index="${index}"]`).forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-mode') === mode);
    });

    // Update content visibility
    const formContent = document.getElementById(`body-mode-form-${index}`);
    const jsonContent = document.getElementById(`body-mode-json-${index}`);

    if (formContent) formContent.style.display = mode === 'form' ? 'block' : 'none';
    if (jsonContent) jsonContent.style.display = mode === 'json' ? 'block' : 'none';
}

function createFormField(param, prefix, isBody, endpoint = null) {
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
        // Parse example to determine structure (array or object)
        let jsonStructure = null;
        if (param.example) {
            try {
                jsonStructure = JSON.parse(param.example);
            } catch (e) {
                // If example is not valid JSON, treat as simple text input
                inputHtml = `
                    <input type="text" id="${fieldId}" name="${param.name}" ${required} placeholder="${param.placeholder || param.example || 'Enter value'}" style="width: 100%; box-sizing: border-box;">
                    ${param.example ? `<small style="display: block; margin-top: 0.25rem; color: #64748b; font-size: 0.85rem;">Example: ${param.example}</small>` : ''}
                `;
                return `
                    <div class="form-group">
                        <label for="${fieldId}">${formattedName} ${requiredText}</label>
                        ${inputHtml}
                    </div>
                `;
            }
        }

        // Generate dynamic JSON form based on structure
        const elementTitle = getElementTitle(endpoint, param.name);
        const jsonFormHtml = generateJsonFormField(fieldId, param.name, jsonStructure, prefix, required, requiredText, formattedName, elementTitle);
        return jsonFormHtml;
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

function getElementTitle(endpoint, paramName) {
    if (!endpoint) return "Item";

    const endpointName = endpoint.name.toLowerCase();
    const endpointDesc = (endpoint.description || "").toLowerCase();

    // Determine title based on endpoint name/description
    if (endpointName.includes("price") || endpointDesc.includes("price")) {
        return "Price";
    } else if (endpointName.includes("economic") || endpointDesc.includes("economic") || endpointName.includes("indicator")) {
        return "Economic Data";
    } else if (endpointName.includes("stir") || endpointDesc.includes("stir")) {
        return "STIR Futures";
    } else if (endpointName.includes("asset") || endpointDesc.includes("asset")) {
        return "Asset";
    } else if (endpointName.includes("central bank") || endpointDesc.includes("central bank")) {
        return "Central Bank Data";
    } else if (endpointName.includes("meeting") || endpointDesc.includes("meeting")) {
        return "Meeting";
    } else if (endpointName.includes("holiday") || endpointDesc.includes("holiday")) {
        return "Holiday";
    } else if (endpointName.includes("schedule") || endpointDesc.includes("schedule")) {
        return "Schedule";
    }

    // Default: use generic "Item"
    return "Item";
}

function generateJsonFormField(fieldId, fieldName, jsonStructure, prefix, required, requiredText, formattedName, elementTitle = "Item") {
    if (Array.isArray(jsonStructure)) {
        // Handle array: show each element with sub-fields and "Add new element" button
        const containerId = `${fieldId}-container`;
        const arrayIndex = 0; // Start with first element

        let html = `
            <div class="json-form-container" id="${containerId}" data-field-name="${fieldName}" data-structure-type="array">
                <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">${formattedName} ${requiredText}</label>
                <div class="json-array-items" id="${fieldId}-items">
        `;

        // Add first element if array has items
        if (jsonStructure.length > 0) {
            html += generateArrayElement(fieldId, fieldName, jsonStructure[0], 0, prefix, elementTitle);
        } else {
            // Empty array - add one empty element
            html += generateArrayElement(fieldId, fieldName, {}, 0, prefix, elementTitle);
        }

        // Store element structure in data attribute to avoid JSON escaping issues
        const elementStructureJson = JSON.stringify(jsonStructure[0] || {});
        html += `
                </div>
                <button type="button" class="btn-submit btn-add-element"
                        data-field-id="${fieldId}"
                        data-field-name="${fieldName}"
                        data-element-structure='${elementStructureJson.replace(/'/g, "&apos;")}'
                        data-prefix="${prefix}"
                        data-element-title="${elementTitle}"
                        style="margin-top: 0.5rem;">
                    Add
                </button>
            </div>
        `;

        return html;
    } else if (jsonStructure && typeof jsonStructure === 'object') {
        // Handle object: show all keys as form fields
        return generateObjectFields(fieldId, fieldName, jsonStructure, prefix, required, requiredText, formattedName);
    } else {
        // Fallback: simple text input
        return `
            <div class="form-group">
                <label for="${fieldId}">${formattedName} ${requiredText}</label>
                <input type="text" id="${fieldId}" name="${fieldName}" ${required} placeholder="Enter JSON value" style="width: 100%; box-sizing: border-box;">
            </div>
        `;
    }
}

function generateArrayElement(fieldId, fieldName, elementStructure, index, prefix, elementTitle = "Item") {
    const elementId = `${fieldId}-item-${index}`;
    let html = `
        <div class="json-array-item" id="${elementId}" data-index="${index}" data-field-name="${fieldName}" style="border: 1px solid #cbd5e1; border-radius: 0.375rem; padding: 1rem; margin-bottom: 0.5rem; background-color: #f8fafc;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                <strong style="color: #475569;">${elementTitle} ${index + 1}</strong>
                <button type="button" class="btn-cancel" onclick="removeArrayElement('${elementId}')" style="padding: 0.25rem 0.75rem; font-size: 0.85rem;">
                    Remove
                </button>
            </div>
            <div class="json-object-fields">
    `;

    // Generate fields for each key in the element object
    if (elementStructure && typeof elementStructure === 'object') {
        Object.keys(elementStructure).forEach(key => {
            const value = elementStructure[key];
            html += generateFieldForValue(`${elementId}-${key}`, key, value, prefix, fieldName);
        });
    }

    html += `
            </div>
        </div>
    `;

    return html;
}

function generateObjectFields(fieldId, fieldName, objStructure, prefix, required, requiredText, formattedName) {
    let html = `
        <div class="json-form-container" id="${fieldId}-container" data-field-name="${fieldName}" data-structure-type="object">
            <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">${formattedName} ${requiredText}</label>
            <div class="json-object-fields" style="border: 1px solid #cbd5e1; border-radius: 0.375rem; padding: 1rem; background-color: #f8fafc;">
    `;

        Object.keys(objStructure).forEach(key => {
            const value = objStructure[key];
            html += generateFieldForValue(`${fieldId}-${key}`, key, value, prefix, fieldName);
        });

    html += `
            </div>
        </div>
    `;

    return html;
}

function generateFieldForValue(fieldId, fieldName, value, prefix, baseFieldName = '') {
    const formattedName = formatParameterName(fieldName);
    let inputHtml = '';

    if (Array.isArray(value)) {
        // Nested array - create a simple text input for now (could be enhanced)
        inputHtml = `
            <input type="text" id="${fieldId}" name="${fieldName}" data-field-path="${fieldName}" placeholder='${JSON.stringify(value)}' style="width: 100%; box-sizing: border-box;">
            <small style="display: block; margin-top: 0.25rem; color: #64748b; font-size: 0.85rem;">Array: Enter comma-separated values or JSON array</small>
        `;
    } else if (value && typeof value === 'object') {
        // Nested object - recursively generate fields
        let nestedHtml = `
            <div class="nested-object" data-nested-key="${fieldName}" style="border: 1px solid #e2e8f0; border-radius: 0.25rem; padding: 0.75rem; margin-top: 0.5rem; background-color: white;">
                <strong style="color: #475569; display: block; margin-bottom: 0.5rem;">${formattedName}</strong>
        `;

        Object.keys(value).forEach(nestedKey => {
            nestedHtml += generateFieldForValue(`${fieldId}-${nestedKey}`, nestedKey, value[nestedKey], prefix, baseFieldName);
        });

        nestedHtml += `</div>`;
        return `
            <div class="form-group" style="margin-bottom: 1rem;">
                <label for="${fieldId}" style="display: block; margin-bottom: 0.25rem; font-weight: 500;">${formattedName}</label>
                ${nestedHtml}
            </div>
        `;
    } else {
        // Simple value - determine input type
        // Check if field name contains 'date' to use date picker
        const isDateField = fieldName.toLowerCase().includes('date');
        const inputType = typeof value === 'number' ? 'number' :
                         isDateField ? 'date' :
                         (value && String(value).match(/^\d{4}-\d{2}-\d{2}/)) ? 'date' : 'text';

        // Use value only as placeholder hint, not as default value
        const placeholderHint = value || '';
        inputHtml = `
            <input type="${inputType}" id="${fieldId}" name="${fieldName}" data-field-path="${fieldName}" value="" placeholder="${placeholderHint}" style="width: 100%; box-sizing: border-box;">
        `;
    }

    return `
        <div class="form-group" style="margin-bottom: 1rem;">
            <label for="${fieldId}" style="display: block; margin-bottom: 0.25rem; font-weight: 500;">${formattedName}</label>
            ${inputHtml}
        </div>
    `;
}

// Global function to add array element
function addArrayElement(fieldId, fieldName, elementStructureJson, prefix, elementTitle = "Item") {
    const itemsContainer = document.getElementById(`${fieldId}-items`);
    if (!itemsContainer) {
        console.error('Items container not found:', `${fieldId}-items`);
        return;
    }

    // Parse the element structure from JSON string
    let elementStructure;
    try {
        // Unescape HTML entities if needed
        const unescaped = elementStructureJson.replace(/&apos;/g, "'").replace(/&#39;/g, "'");
        elementStructure = JSON.parse(unescaped);
    } catch (e) {
        console.error('Error parsing element structure:', e, elementStructureJson);
        elementStructure = {};
    }

    const existingItems = itemsContainer.querySelectorAll('.json-array-item');
    const newIndex = existingItems.length;

    const newElement = document.createElement('div');
    newElement.innerHTML = generateArrayElement(fieldId, fieldName, elementStructure, newIndex, prefix, elementTitle);
    const elementNode = newElement.firstElementChild;
    if (elementNode) {
        itemsContainer.appendChild(elementNode);
    } else {
        console.error('Failed to create array element');
    }
}

// Make it available globally for onclick handlers (fallback)
window.addArrayElement = addArrayElement;

// Global function to remove array element
window.removeArrayElement = function(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.remove();
        // Re-index remaining elements
        const container = element.closest('.json-array-items');
        if (container) {
            const items = container.querySelectorAll('.json-array-item');
            items.forEach((item, index) => {
                item.setAttribute('data-index', index);
            });
        }
    }
};

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
            // Check if JSON mode is active
            const jsonModeTab = document.querySelector(`.body-mode-tab[data-index="${index}"][data-mode="json"].active`);
            const rawJsonInput = document.getElementById(`body-raw-json-${index}`);

            if (jsonModeTab && rawJsonInput && rawJsonInput.value.trim()) {
                // JSON mode is active - use raw JSON directly
                try {
                    const parsedJson = JSON.parse(rawJsonInput.value.trim());
                    options.headers["Content-Type"] = "application/json";
                    options.body = JSON.stringify(parsedJson);
                } catch (e) {
                    alert("Invalid JSON: " + e.message);
                    return;
                }
            } else {
                // Form mode - collect from form fields
                const formData = new FormData();
                let hasBodyData = false;
                const bodyObj = {};

                // For bodyAsList endpoints, directly collect array items from the form
                if (endpoint.bodyAsList) {
                    const formContainer = document.getElementById(`body-mode-form-${index}`);
                    if (formContainer) {
                        const arrayItems = formContainer.querySelectorAll('.json-array-item');
                        const arrayData = [];

                        arrayItems.forEach((item) => {
                            const itemObj = {};
                            const inputs = item.querySelectorAll('input, select, textarea');

                            inputs.forEach(input => {
                                const fieldPath = input.getAttribute('data-field-path');
                                if (fieldPath && input.value) {
                                    itemObj[fieldPath] = input.value;
                                }
                            });

                            // Only add if item has values
                            if (Object.keys(itemObj).length > 0) {
                                arrayData.push(itemObj);
                            }
                        });

                        if (arrayData.length > 0) {
                            options.headers["Content-Type"] = "application/json";
                            options.body = JSON.stringify(arrayData);
                            hasBodyData = true;
                        }
                    }
                } else {
                    // Standard form collection for non-list endpoints
                    endpoint.body.forEach((param) => {
                        const input = document.getElementById(`body-${index}-${param.name}`);
                        if (input) {
                            if (param.type === "file") {
                                if (input.files && input.files[0]) {
                                    formData.append(param.name, input.files[0]);
                                    hasBodyData = true;
                                }
                            } else if (param.type === "json") {
                                // Reconstruct JSON from form fields
                                const containerId = `body-${index}-${param.name}-container`;
                                const jsonContainer = document.getElementById(containerId);
                                if (jsonContainer) {
                                    const structureType = jsonContainer.getAttribute('data-structure-type');
                                    if (structureType === 'array') {
                                        bodyObj[param.name] = collectArrayValues(jsonContainer, param.name);
                                        hasBodyData = true;
                                    } else if (structureType === 'object') {
                                        bodyObj[param.name] = collectObjectValues(jsonContainer, param.name);
                                        hasBodyData = true;
                                    }
                                } else {
                                    // Fallback: try to parse as JSON from input value
                                    const jsonInput = document.getElementById(`body-${index}-${param.name}`);
                                    if (jsonInput && jsonInput.value) {
                                        try {
                                            const parsed = JSON.parse(jsonInput.value);
                                            bodyObj[param.name] = parsed;
                                            hasBodyData = true;
                                        } catch (e) {
                                            bodyObj[param.name] = jsonInput.value;
                                            hasBodyData = true;
                                        }
                                    }
                                }
                            } else if (param.type === "checkbox") {
                                if (input.checked) {
                                    bodyObj[param.name] = true;
                                    hasBodyData = true;
                                } else {
                                    bodyObj[param.name] = false;
                                }
                            } else if (param.type === "number") {
                                if (input.value) {
                                    const numValue = parseFloat(input.value);
                                    if (!isNaN(numValue)) {
                                        bodyObj[param.name] = numValue;
                                        hasBodyData = true;
                                    } else {
                                        bodyObj[param.name] = input.value;
                                        hasBodyData = true;
                                    }
                                }
                            } else if (param.type === "date") {
                                if (input.value) {
                                    bodyObj[param.name] = input.value;
                                    hasBodyData = true;
                                }
                            } else if (input.value) {
                                bodyObj[param.name] = input.value;
                                hasBodyData = true;
                            }
                        }
                    });

                    if (hasBodyData) {
                        // Check if we have file uploads
                        const hasFiles = Array.from(formData.entries()).some(([key, value]) => value instanceof File);
                        if (hasFiles) {
                            // If we have files, merge bodyObj into formData
                            Object.keys(bodyObj).forEach(key => {
                                if (typeof bodyObj[key] === 'object') {
                                    formData.append(key, JSON.stringify(bodyObj[key]));
                                } else {
                                    formData.append(key, bodyObj[key]);
                                }
                            });
                            options.body = formData;
                        } else {
                            // No files, send as JSON
                            options.headers["Content-Type"] = "application/json";
                            options.body = JSON.stringify(bodyObj);
                        }
                    }
                }
            }
        }
    }

    // Helper functions to collect JSON values from form
    function collectArrayValues(container, fieldName) {
        const items = container.querySelectorAll('.json-array-item');
        const array = [];

        items.forEach((item) => {
            const itemData = collectObjectValues(item);
            // Only add if item has at least one non-empty value
            if (Object.keys(itemData).length > 0 && Object.values(itemData).some(v => v !== '' && v !== null && v !== undefined)) {
                array.push(itemData);
            }
        });

        return array;
    }

    function collectObjectValues(container) {
        const obj = {};
        const inputs = container.querySelectorAll('input:not([type="file"]), select, textarea');

        inputs.forEach((input) => {
            if (input.type === 'file') {
                return; // Skip file inputs
            }

            // Use data-field-path attribute if available, otherwise parse from ID
            let fieldPath = [];
            if (input.hasAttribute('data-field-path')) {
                fieldPath = [input.getAttribute('data-field-path')];
            } else {
                // Parse from ID: find the field name (last part after all prefixes)
                const fullId = input.id;
                const parts = fullId.split('-');
                // Find the actual field name - it's typically the last part, but we need to handle nested objects
                // Look for nested-object containers to determine hierarchy
                let nestedKey = null;
                const nestedObj = input.closest('.nested-object');
                if (nestedObj) {
                    nestedKey = nestedObj.getAttribute('data-nested-key');
                }

                // Get the direct field name (last part of ID)
                const directFieldName = parts[parts.length - 1];

                if (nestedKey) {
                    fieldPath = [nestedKey, directFieldName];
                } else {
                    fieldPath = [directFieldName];
                }
            }

            if (fieldPath.length === 0) return;

            // Get value
            let value = null;
            if (input.type === 'checkbox') {
                value = input.checked;
            } else if (input.type === 'number') {
                value = input.value ? parseFloat(input.value) : null;
            } else if (input.type === 'date') {
                value = input.value || null;
            } else if (input.tagName === 'SELECT') {
                value = input.value || null;
            } else {
                // For text inputs, try to parse as JSON if it looks like JSON
                const textValue = input.value.trim();
                if (textValue.startsWith('[') || textValue.startsWith('{')) {
                    try {
                        value = JSON.parse(textValue);
                    } catch (e) {
                        value = textValue;
                    }
                } else if (textValue.includes(',') && !textValue.includes('{') && !textValue.includes('[')) {
                    // Comma-separated values - treat as array
                    value = textValue.split(',').map(v => v.trim()).filter(v => v);
                } else {
                    value = textValue || null;
                }
            }

            // Only add non-empty values
            if (value !== null && value !== '' && value !== undefined) {
                // Set nested value using field path
                setNestedValue(obj, fieldPath, value);
            }
        });

        return obj;
    }

    function setNestedValue(obj, path, value) {
        if (path.length === 1) {
            obj[path[0]] = value;
        } else {
            const key = path[0];
            if (!obj[key] || typeof obj[key] !== 'object' || Array.isArray(obj[key])) {
                obj[key] = {};
            }
            setNestedValue(obj[key], path.slice(1), value);
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
