// Helper function to format snake_case to "Capped First Letter + space"
function formatParameterName(name) {
  const uppercaseWords = new Set(["csv", "pdf", "url", "fx"]);
  return name
    .split("_")
    .map(word => {
      if (uppercaseWords.has(word.toLowerCase())) {
        return word.toUpperCase();
      }
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join(" ");
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

const MANAGEMENT_CATALOG = window.managementCatalogJSON || {
  assetShortNames: [],
  indicatorNames: [],
  centralBanks: ["FRB", "ECB", "BOJ"],
};

const STIR_FUTURES_SHORT_NAMES = ["FF1M", "ESTR3M", "MUTAN3M"];
const ASSET_CLASS_OPTIONS = ["STOCKS", "RATES", "FX", "CRYPTO", "COMMODITIES", "OTHERS"];
const ASSET_TYPE_OPTIONS = [
  "EQUITY_INDEX",
  "INTERBANK_RATE",
  "GOVERNMENT_BOND_RATE",
  "FX_SPOT_RATE",
  "CRYPTO_SPOT_RATE",
  "COMMODITIY_FUTURE_SPOT_PRICE",
  "VOLATILITY_INDEX",
];
const LOCATION_OPTIONS = ["US", "EU", "DE", "FR", "JP"];
const PRICE_SOURCE_OPTIONS = [
  "GOV_TREASURY_DEPT",
  "NYFED",
  "WEBSTAT",
  "BUNDESBANK",
  "BOJ",
  "BB",
  "GLOBAL_RATES",
  "YAHOO",
];
function resolveParamOptions(param) {
  if (Array.isArray(param.options) && param.options.length > 0) {
    return param.options;
  }
  switch (param.optionsFrom) {
  case "assetShortNames":
    return MANAGEMENT_CATALOG.assetShortNames || [];
  case "indicatorNames":
    return MANAGEMENT_CATALOG.indicatorNames || [];
  case "centralBanks":
    return MANAGEMENT_CATALOG.centralBanks || ["FRB", "ECB", "BOJ"];
  case "stirFuturesShortNames":
    return STIR_FUTURES_SHORT_NAMES;
  default:
    return [];
  }
}

function resolveNestedFieldOptions(fieldName) {
  switch (fieldName) {
  case "short_name":
    return MANAGEMENT_CATALOG.assetShortNames || [];
  case "central_bank":
    return MANAGEMENT_CATALOG.centralBanks || ["FRB", "ECB", "BOJ"];
  case "indicator_name":
    return MANAGEMENT_CATALOG.indicatorNames || [];
  default:
    return null;
  }
}

function buildSelectOptionsHtml(options, includeEmpty = true) {
  const emptyOption = includeEmpty ? "<option value=\"\">-- Select --</option>" : "";
  return emptyOption + options.map(opt => `<option value="${opt}">${opt}</option>`).join("");
}

function getSelectedMultiValues(inputEl) {
  if (!inputEl) {
    return [];
  }
  const rawValue = (inputEl.value || "").trim();
  if (!rawValue) {
    return [];
  }
  try {
    const parsed = JSON.parse(rawValue);
    if (Array.isArray(parsed)) {
      return parsed.map(String).filter(value => value !== "");
    }
  } catch (_error) {
    // Fall through to CSV parsing for older values.
  }
  return rawValue
    .split(",")
    .map(value => value.trim())
    .filter(value => value !== "");
}

function buildChipMultiselectHtml(fieldId, paramName, options, serialize, required) {
  const optionsHtml = options.map(option => `
            <label class="chip-multiselect-option">
                <input type="checkbox" value="${option}">
                <span>${option}</span>
            </label>
        `).join("");

  return `
        <div class="chip-multiselect" data-field-id="${fieldId}">
            <input type="hidden" id="${fieldId}" name="${paramName}" value="[]" data-serialize="${serialize}" ${required}>
            <button type="button" class="chip-multiselect-control" aria-haspopup="listbox" aria-expanded="false">
                <div class="chip-multiselect-chips">
                    <span class="chip-multiselect-placeholder">Select values…</span>
                </div>
                <span class="chip-multiselect-caret" aria-hidden="true"></span>
            </button>
            <div class="chip-multiselect-dropdown" hidden>
                <div class="chip-multiselect-options">
                    ${optionsHtml || "<p class=\"chip-multiselect-empty\">No options available.</p>"}
                </div>
                <div class="chip-multiselect-actions">
                    <button type="button" class="btn-cancel chip-multiselect-cancel">Cancel</button>
                    <button type="button" class="btn-submit chip-multiselect-apply">Apply</button>
                </div>
            </div>
        </div>
    `;
}

function renderChipMultiselectChips(root, selectedValues) {
  const chipsContainer = root.querySelector(".chip-multiselect-chips");
  if (!chipsContainer) {
    return;
  }
  if (selectedValues.length === 0) {
    chipsContainer.innerHTML = "<span class=\"chip-multiselect-placeholder\">Select values…</span>";
    return;
  }
  chipsContainer.innerHTML = selectedValues.map(value => `
        <span class="chip-multiselect-chip" data-value="${value}">
            <button type="button" class="chip-multiselect-chip-remove" aria-label="Remove ${value}">×</button>
            <span class="chip-multiselect-chip-label">${value}</span>
        </span>
    `).join("");
}

function syncChipMultiselectCheckboxes(root, selectedValues) {
  const selectedSet = new Set(selectedValues);
  root.querySelectorAll(".chip-multiselect-option input[type=\"checkbox\"]").forEach(checkbox => {
    checkbox.checked = selectedSet.has(checkbox.value);
  });
}

function closeChipMultiselect(root) {
  const dropdown = root.querySelector(".chip-multiselect-dropdown");
  const control = root.querySelector(".chip-multiselect-control");
  if (dropdown) {
    dropdown.hidden = true;
  }
  if (control) {
    control.setAttribute("aria-expanded", "false");
  }
}

function openChipMultiselect(root) {
  const dropdown = root.querySelector(".chip-multiselect-dropdown");
  const control = root.querySelector(".chip-multiselect-control");
  const hiddenInput = root.querySelector("input[type=\"hidden\"]");
  if (!dropdown || !control || !hiddenInput) {
    return;
  }
  syncChipMultiselectCheckboxes(root, getSelectedMultiValues(hiddenInput));
  dropdown.hidden = false;
  control.setAttribute("aria-expanded", "true");
}

function initChipMultiselects(container) {
  container.querySelectorAll(".chip-multiselect").forEach(root => {
    const hiddenInput = root.querySelector("input[type=\"hidden\"]");
    const control = root.querySelector(".chip-multiselect-control");
    const applyButton = root.querySelector(".chip-multiselect-apply");
    const cancelButton = root.querySelector(".chip-multiselect-cancel");
    if (!hiddenInput || !control) {
      return;
    }

    renderChipMultiselectChips(root, getSelectedMultiValues(hiddenInput));

    control.addEventListener("click", (event) => {
      event.preventDefault();
      const isOpen = control.getAttribute("aria-expanded") === "true";
      document.querySelectorAll(".chip-multiselect").forEach(otherRoot => {
        if (otherRoot !== root) {
          closeChipMultiselect(otherRoot);
        }
      });
      if (isOpen) {
        closeChipMultiselect(root);
      } else {
        openChipMultiselect(root);
      }
    });

    root.addEventListener("click", (event) => {
      const removeButton = event.target.closest(".chip-multiselect-chip-remove");
      if (!removeButton) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      const chip = removeButton.closest(".chip-multiselect-chip");
      const valueToRemove = chip ? chip.getAttribute("data-value") : null;
      const nextValues = getSelectedMultiValues(hiddenInput).filter(
        value => value !== valueToRemove
      );
      hiddenInput.value = JSON.stringify(nextValues);
      renderChipMultiselectChips(root, nextValues);
      syncChipMultiselectCheckboxes(root, nextValues);
    });

    if (applyButton) {
      applyButton.addEventListener("click", (event) => {
        event.preventDefault();
        const nextValues = Array.from(
          root.querySelectorAll(".chip-multiselect-option input[type=\"checkbox\"]:checked")
        ).map(checkbox => checkbox.value);
        hiddenInput.value = JSON.stringify(nextValues);
        renderChipMultiselectChips(root, nextValues);
        closeChipMultiselect(root);
      });
    }

    if (cancelButton) {
      cancelButton.addEventListener("click", (event) => {
        event.preventDefault();
        syncChipMultiselectCheckboxes(root, getSelectedMultiValues(hiddenInput));
        closeChipMultiselect(root);
      });
    }
  });
}

document.addEventListener("click", (event) => {
  if (event.target.closest(".chip-multiselect")) {
    return;
  }
  document.querySelectorAll(".chip-multiselect").forEach(closeChipMultiselect);
});

// Management API Endpoint Configuration
const ENDPOINTS = {
  quickActions: {
    "Common Operations": [
      {
        name: "Ingest Market Prices",
        description: "Ingest market prices gathered from various sources for a specific date.",
        method: "POST",
        path: "/markets/prices/ingest",
        body: [
          { name: "date", type: "date", required: true },
        ],
        query: null,
      },
      {
        name: "Get Assets Without Prices",
        description: "List assets that are missing a price in the selected window.",
        help: "Dates can be left empty for the default lookback, or either bound can be set to narrow the window. Include Holidays can be ticked to keep holiday rows.",
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
        description: "Ingest STIR futures prices for a date.",
        method: "POST",
        path: "/central-banks/stir-futures/ingest",
        body: [
          { name: "date", type: "date", required: true },
        ],
        query: null,
      },
      {
        name: "Ingest ESTR Price via PDF",
        description: "Ingest an ESTR futures print from an uploaded PDF.",
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
        description: "Mark market prices as holiday for the given assets and dates. Sets comment to Bank holiday and price to null.",
        method: "POST",
        path: "/markets/prices/mark-as-holiday",
        bodyAsList: true,
        body: [
          { name: "data", type: "json", required: true, example: "[{\"short_name\": \"EURUSD\", \"date\": \"\"}]" },
        ],
        query: null,
      },
    ],
  },
  marketData: {
    Asset: [
      {
        name: "Generate Base Assets Data",
        description: "Generate base assets data from the catalog JSON.",
        method: "POST",
        path: "/markets/asset/generate-base-assets-data",
        body: null,
        query: null,
      },
      {
        name: "Get Asset Names",
        description: "List asset short names stored in the database.",
        help: "Filters can be left empty to list all assets, or any dropdowns can be filled to narrow the list.",
        method: "GET",
        path: "/markets/asset/get-asset-names",
        body: null,
        query: [
          { name: "asset_class", type: "select", options: ASSET_CLASS_OPTIONS, required: false },
          { name: "asset_type", type: "select", options: ASSET_TYPE_OPTIONS, required: false },
          { name: "location", type: "select", options: LOCATION_OPTIONS, required: false },
          { name: "source", type: "select", options: PRICE_SOURCE_OPTIONS, required: false },
        ],
      },
      {
        name: "Get Asset Details",
        description: "Fetch one asset by short name.",
        method: "GET",
        path: "/markets/asset",
        body: null,
        query: [
          { name: "short_name", type: "select", optionsFrom: "assetShortNames", required: true },
        ],
      },
    ],
    Prices: [
      {
        name: "Batch Ingest Market Prices",
        description: "Ingest historical prices for specific assets over target periods.",
        method: "POST",
        path: "/markets/prices/batch-ingest",
        bodyAsList: true,
        body: [
          { name: "data", type: "json", required: true, example: "[{\"short_name\": \"EURUSD\", \"start_date\": \"2024-01-01\", \"end_date\": \"2024-01-31\"}]" },
        ],
        query: null,
      },
      {
        name: "Get Market Price",
        description: "Get the market price for one asset on one date.",
        method: "GET",
        path: "/markets/prices",
        body: null,
        query: [
          { name: "date", type: "date", required: true },
          { name: "short_name", type: "select", optionsFrom: "assetShortNames", required: true },
        ],
      },
      {
        name: "List All Market Prices",
        description: "List every stored market price for a date.",
        method: "GET",
        path: "/markets/prices/list-all",
        body: null,
        query: [
          { name: "date", type: "date", required: true },
        ],
      },
      {
        name: "Bulk Update Assets Prices",
        description: "Manually patch prices for one or more assets. Logs is optional free text on each row.",
        method: "PATCH",
        path: "/markets/prices/bulk-update",
        bodyAsList: true,
        body: [
          { name: "data", type: "json", required: true, example: "[{\"short_name\": \"EURUSD\", \"date\": \"2024-01-01\", \"price\": 1.10, \"logs\": \"Manual update\"}]" },
        ],
        query: null,
      },
      {
        name: "Bulk Update Assets Prices from CSV",
        description: "Bulk update asset prices from an uploaded CSV file.",
        method: "PATCH",
        path: "/markets/prices/bulk-update-from-csv",
        body: [
          { name: "csv_file", type: "file", required: true },
        ],
        query: null,
      },
      {
        name: "Get Price Update Logs",
        description: "Inspect price update logs.",
        help: "Filters can be left empty for all logs, or Price Date and/or Short Name can be set to narrow the search.",
        method: "GET",
        path: "/markets/prices/get-price-update-logs",
        body: null,
        query: [
          { name: "price_date", type: "date", required: false },
          { name: "short_name", type: "select", optionsFrom: "assetShortNames", required: false },
        ],
      },
      {
        name: "Delete Market Prices",
        description: "Delete market prices by IDs.",
        help: "A comma-separated Ids list can be used for the prices to delete.",
        method: "DELETE",
        path: "/markets/prices",
        body: null,
        query: [
          { name: "ids", type: "text", required: false, placeholder: "Comma-separated IDs" },
        ],
      },
    ],
    Holiday: [
      {
        name: "Ingest Holidays",
        description: "Ingest holidays from configured sources.",
        help: "Filters can be left empty for the default ingest, or Date and/or Location can be set to restrict the scrape.",
        method: "POST",
        path: "/markets/holidays/ingest",
        body: [
          { name: "date", type: "date", required: false },
          { name: "location", type: "select", options: ["US", "FR", "JP"], required: false },
        ],
        query: null,
      },
      {
        name: "Get Holidays",
        description: "List stored holidays.",
        help: "Filters can be left empty to list all holidays, or Location, Year, and/or Months (comma-separated 1-12) can be set to narrow the list.",
        method: "GET",
        path: "/markets/holidays",
        body: null,
        query: [
          { name: "location", type: "select", options: ["US", "FR", "JP"], required: false },
          { name: "year", type: "number", required: false },
          {
            name: "months",
            type: "text",
            required: false,
            placeholder: "Comma-separated months (1-12)",
          },
        ],
      },
    ],
  },
  economicData: {
    Data: [
      {
        name: "Generate Base Economic Indicator Information",
        description: "Generate base economic indicator information from the catalog JSON.",
        method: "POST",
        path: "/economics/indicator/generate-base-information",
        body: null,
        query: null,
      },
      {
        name: "Ingest Latest Economic Data",
        description: "Ingest the latest value for every seeded economic indicator.",
        help: "Update Schedule can be left unchecked to skip schedule refresh, or ticked to also roll publication schedules after ingest.",
        method: "POST",
        path: "/economics/indicator/ingest",
        body: [
          { name: "update_schedule", type: "checkbox", required: false },
        ],
        query: null,
      },
      {
        name: "Ingest Historical Economic Data",
        description: "Ingest every available value whose period falls in the date window.",
        help: "Indicators can be left empty to ingest all indicators, or one or more names can be selected to restrict the run.",
        method: "POST",
        path: "/economics/indicator/ingest-historical",
        body: [
          { name: "start_date", type: "date", required: true },
          { name: "end_date", type: "date", required: true },
          {
            name: "indicators",
            type: "multiselect",
            optionsFrom: "indicatorNames",
            serialize: "json",
            required: false,
          },
        ],
        query: null,
      },
      {
        name: "Ingest Specific Economic Data",
        description: "Ingest specific periods for chosen indicators. Each row needs an indicator_name plus a periods list (e.g. 2024-01).",
        method: "POST",
        path: "/economics/indicator/ingest-specific",
        bodyAsList: true,
        body: [
          { name: "data", type: "json", required: true, example: "[{\"indicator_name\": \"France Consumer Confidence\", \"periods\": [\"2024-01\", \"2024-02\"]}]" },
        ],
        query: null,
      },
      {
        name: "Get Economic Data",
        description: "Fetch stored economic data points.",
        help: "Indicator Names can be left empty to get all indicators. A Period (e.g. 2024-01) can optionally be added to filter further.",
        method: "GET",
        path: "/economics/indicator",
        body: null,
        query: [
          {
            name: "indicator_names",
            type: "multiselect",
            optionsFrom: "indicatorNames",
            serialize: "repeat",
            required: false,
          },
          { name: "period", type: "text", required: false },
        ],
      },
      {
        name: "Delete Economic Data",
        description: "Delete economic data by IDs.",
        method: "DELETE",
        path: "/economics/indicator",
        body: null,
        query: [
          { name: "ids", type: "text", required: true, placeholder: "Comma-separated IDs" },
        ],
      },
    ],
    Schedule: [
      {
        name: "Update Publication Schedule",
        description: "Refresh publication schedules from source calendars.",
        help: "Indicator Names can be left empty to update every indicator, or one or more names can be selected to refresh only those schedules.",
        method: "POST",
        path: "/economics/schedule/update",
        body: [
          {
            name: "indicator_names",
            type: "multiselect",
            optionsFrom: "indicatorNames",
            serialize: "json",
            required: false,
          },
        ],
        query: null,
      },
    ],
  },
  centralBankData: {
    Data: [
      {
        name: "List Central Bank Data",
        description: "List key-rate prints for one or more central banks.",
        help: "Central Banks can be left empty to list all central banks. A Date can optionally be set. Last Value can be ticked to keep only the latest print per series.",
        method: "GET",
        path: "/central-banks/data",
        body: null,
        query: [
          {
            name: "central_banks",
            type: "multiselect",
            optionsFrom: "centralBanks",
            serialize: "csv",
            required: false,
          },
          { name: "date", type: "date", required: false },
          { name: "last_value", type: "checkbox", required: false },
        ],
      },
      {
        name: "Ingest Central Bank Data",
        description: "Ingest key rates for chosen central banks and dates.",
        method: "POST",
        path: "/central-banks/data/ingest",
        bodyAsList: true,
        body: [
          { name: "data", type: "json", required: true, example: "[{\"central_bank\": \"FRB\", \"date\": \"2024-01-01\"}]" },
        ],
        query: null,
      },
      {
        name: "Delete Central Bank Data",
        description: "Delete central bank data using optional filters.",
        help: "At least one filter is required: date range, Central Banks, and/or Ids.",
        method: "DELETE",
        path: "/central-banks/data",
        body: null,
        query: [
          { name: "start_date", type: "date", required: false },
          { name: "end_date", type: "date", required: false },
          {
            name: "central_banks",
            type: "multiselect",
            optionsFrom: "centralBanks",
            serialize: "csv",
            required: false,
          },
          { name: "ids", type: "text", required: false, placeholder: "Comma-separated IDs" },
        ],
      },
    ],
    "STIR Futures Prices": [
      {
        name: "List STIR Futures Prices",
        description: "List STIR futures prices.",
        help: "Central Banks can be left empty to list all central banks. A Date can optionally be set.",
        method: "GET",
        path: "/central-banks/stir-futures",
        body: null,
        query: [
          {
            name: "central_banks",
            type: "multiselect",
            optionsFrom: "centralBanks",
            serialize: "csv",
            required: false,
          },
          { name: "date", type: "date", required: false },
        ],
      },
      {
        name: "Bulk Update STIR Futures Prices",
        description: "Manually patch STIR futures prices. Logs is optional on each row.",
        method: "PATCH",
        path: "/central-banks/stir-futures/bulk-update",
        bodyAsList: true,
        body: [
          {
            name: "data",
            type: "json",
            required: true,
            example: "[{\"date\": \"2024-01-01\", \"short_name\": \"ESTR3M\", \"maturity\": \"2024-03\", \"price\": 95.5, \"logs\": \"Manual update\"}]",
            nestedSelectOptions: { short_name: "stirFuturesShortNames" },
          },
        ],
        query: null,
      },
      {
        name: "Bulk Update STIR Futures Prices from CSV",
        description: "Bulk update STIR futures prices from an uploaded CSV.",
        method: "PATCH",
        path: "/central-banks/stir-futures/bulk-update-from-csv",
        body: [
          { name: "csv_file", type: "file", required: true },
        ],
        query: null,
      },
      {
        name: "Get Central Bank Probability Matrix",
        description: "Build the rate-path probability matrix for a date.",
        help: "Central Banks can be left empty to get all central banks, or specific ones can be selected.",
        method: "GET",
        path: "/central-banks/probability-matrix",
        body: null,
        query: [
          {
            name: "central_banks",
            type: "multiselect",
            optionsFrom: "centralBanks",
            serialize: "csv",
            required: false,
          },
          { name: "date", type: "date", required: true },
        ],
      },
      {
        name: "Delete STIR Futures Prices",
        description: "Delete STIR futures prices using optional filters.",
        help: "At least one filter is required: date range, Central Banks, and/or Ids.",
        method: "DELETE",
        path: "/central-banks/stir-futures",
        body: null,
        query: [
          { name: "start_date", type: "date", required: false },
          { name: "end_date", type: "date", required: false },
          {
            name: "central_banks",
            type: "multiselect",
            optionsFrom: "centralBanks",
            serialize: "csv",
            required: false,
          },
          { name: "ids", type: "text", required: false, placeholder: "Comma-separated IDs" },
        ],
      },
    ],
    "Meeting Dates": [
      {
        name: "Get Central Bank Meeting Dates",
        description: "List upcoming / retained meeting dates.",
        help: "Central Banks can be left empty to get all central banks, or specific ones can be selected.",
        method: "GET",
        path: "/central-banks/meeting-dates",
        body: null,
        query: [
          {
            name: "central_banks",
            type: "multiselect",
            optionsFrom: "centralBanks",
            serialize: "csv",
            required: false,
          },
        ],
      },
      {
        name: "Ingest Central Bank Meeting Dates",
        description: "Ingest meeting dates for all central banks.",
        method: "POST",
        path: "/central-banks/meeting-dates/ingest",
        body: null,
        query: null,
      },
    ],
  },
  marketAnalysis: {
    Recap: [
      {
        name: "Get Daily Recap",
        description: "Fetch the AI-generated financial news recap.",
        help: "Reporting Date can be left empty to load the latest saved recap, or a date can be set to fetch that reporting day.",
        method: "GET",
        path: "/analysis/recap",
        body: null,
        query: [
          { name: "reporting_date", type: "date", required: false },
        ],
      },
      {
        name: "Generate Daily Recap",
        description: "Run the pipeline in-process: collect → analyze → persist recap (not queued).",
        help: "Force can be left unchecked to skip when a recap already exists, or ticked to regenerate anyway.",
        method: "POST",
        path: "/analysis/recap/generate",
        body: [
          { name: "reporting_date", type: "date", required: true },
          { name: "force", type: "checkbox", required: false },
        ],
        query: null,
      },
    ],
    "Cache & Chat": [
      {
        name: "Extract Article",
        description: "Scrape catalog news wraps for a reporting date.",
        help: "Source and Region can be left empty to scrape everything. Source can be set to limit to that source (all its regions), Region to limit to that region across sources, or both together.",
        method: "GET",
        path: "/analysis/article",
        body: null,
        query: [
          { name: "reporting_date", type: "date", required: true },
          {
            name: "source",
            type: "select",
            options: [
              "SWISSINFO_MARKET_WRAP",
              "THE_EDGE_GLOBAL_MARKETS",
              "CNBC_STOCK_MARKET_DAILY_RECAP",
              "NEWSQUAWK_US_MARKET_WRAP",
              "TBS_US_MARKETS",
              "BOURSIER_CLOTURE_PARIS",
              "ZONEBOURSE",
              "BOURSORAMA",
              "TOKYO_CLOSING_BELL",
              "TBS_JAPAN_MARKETS",
            ],
            required: false,
          },
          {
            name: "region",
            type: "select",
            options: ["GLOBAL", "US", "EU", "FR", "JP"],
            required: false,
          },
        ],
      },
      {
        name: "Article Analysis Cache",
        description: "Inspect same-day Redis-cached article digests (24h TTL).",
        help: "Filters can be left empty for the default listing. Reporting Date can be set to scope by day, and/or Source URL to inspect one cached article.",
        method: "GET",
        path: "/analysis/article-cache",
        body: null,
        query: [
          { name: "reporting_date", type: "date", required: false },
          { name: "source_url", type: "text", required: false },
        ],
      },
      {
        name: "Market Analysis Chat",
        description: "Q&A with the market-analysis agent. Prior turns are not collected in this form — send a standalone question.",
        method: "POST",
        path: "/analysis/chat",
        body: [
          { name: "question", type: "text", required: true },
        ],
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

    // Close modals in order of priority (most specific first).
    // Loading modal is intentionally not closable with Escape.
    if (deleteConfirmationModal && deleteConfirmationModal.classList.contains("active")) {
      closeDeleteConfirmationModal();
    } else if (formModal && formModal.classList.contains("active")) {
      closeFormModal();
    } else if (resultModal && resultModal.classList.contains("active")) {
      closeResultModal();
    }
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

  html += "</div>";

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
    const subcategorySection = createSubcategorySection(subcategory);
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
    const subcategorySection = createSubcategorySection(subcategory);
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
    const subcategorySection = createSubcategorySection(subcategory);
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
    const subcategorySection = createSubcategorySection(subcategory);
    centralBankContainer.appendChild(subcategorySection.container);
    sortedEndpoints.forEach((endpoint) => {
      const card = createEndpointCard(endpoint, globalIndex, "centralBankData");
      subcategorySection.grid.appendChild(card);
      endpointMap.set(globalIndex, { category: "centralBankData", subcategory, endpoint });
      globalIndex++;
    });
  });

  // Render research agent endpoints
  const researchContainer = document.getElementById("market-analysis-endpoints");
  if (researchContainer && ENDPOINTS.marketAnalysis) {
    Object.entries(ENDPOINTS.marketAnalysis).forEach(([subcategory, endpoints]) => {
      const sortedEndpoints = sortEndpointsByMethod(endpoints);
      const subcategorySection = createSubcategorySection(subcategory);
      researchContainer.appendChild(subcategorySection.container);
      sortedEndpoints.forEach((endpoint) => {
        const card = createEndpointCard(endpoint, globalIndex, "marketAnalysis");
        subcategorySection.grid.appendChild(card);
        endpointMap.set(globalIndex, { category: "marketAnalysis", subcategory, endpoint });
        globalIndex++;
      });
    });
  }

});

function createSubcategorySection(subcategory) {
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
  const subtitleBlock = document.getElementById("form-modal-subtitle-block");
  const modalDescription = document.getElementById("form-modal-description");
  const modalHelp = document.getElementById("form-modal-help");

  modalTitle.textContent = endpoint.name;
  const helpText = endpoint.help || "";
  if (subtitleBlock && modalDescription && modalHelp) {
    const hasDescription = Boolean(endpoint.description);
    const hasHelp = Boolean(helpText);
    modalDescription.textContent = endpoint.description || "";
    modalDescription.hidden = !hasDescription;
    modalHelp.textContent = helpText;
    modalHelp.hidden = !hasHelp;
    subtitleBlock.hidden = !hasDescription && !hasHelp;
  }
  modalBody.innerHTML = createFormFields(endpoint, index);
  initChipMultiselects(modalBody);

  // Attach event listeners to "Add" buttons after modal is populated
  modalBody.querySelectorAll(".btn-add-element").forEach(btn => {
    btn.addEventListener("click", function() {
      const fieldId = this.getAttribute("data-field-id");
      const fieldName = this.getAttribute("data-field-name");
      const elementStructureJson = this.getAttribute("data-element-structure");
      const prefix = this.getAttribute("data-prefix");
      const elementTitle = this.getAttribute("data-element-title") || "Item";
      const nestedSelectOptionsJson = this.getAttribute("data-nested-select-options");
      addArrayElement(
        fieldId,
        fieldName,
        elementStructureJson,
        prefix,
        elementTitle,
        nestedSelectOptionsJson
      );
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
  const hasQuery = Boolean(endpoint.query && endpoint.query.length > 0);
  const hasBody = Boolean(endpoint.body && endpoint.body.length > 0);
  let html = "";

  // Query parameters
  if (hasQuery) {
    endpoint.query.forEach((param) => {
      html += createFormField(param, `query-${index}`, false, endpoint);
    });
  }

  // Body parameters - add tabs for POST/PATCH/PUT with JSON body
  if (hasBody) {
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

  if (!hasQuery && !hasBody) {
    html += "<p class=\"endpoint-no-params\">No parameters required for this endpoint.</p>";
  }

  return html;
}

function switchBodyMode(index, mode) {
  // Update tab buttons
  document.querySelectorAll(`.body-mode-tab[data-index="${index}"]`).forEach(btn => {
    btn.classList.toggle("active", btn.getAttribute("data-mode") === mode);
  });

  // Update content visibility
  const formContent = document.getElementById(`body-mode-form-${index}`);
  const jsonContent = document.getElementById(`body-mode-json-${index}`);

  if (formContent) formContent.style.display = mode === "form" ? "block" : "none";
  if (jsonContent) jsonContent.style.display = mode === "json" ? "block" : "none";
}

window.switchBodyMode = switchBodyMode;

function createFormField(param, prefix, isBody, endpoint = null) {
  const fieldId = `${prefix}-${param.name}`;
  const required = param.required ? "required" : "";
  const formattedName = formatParameterName(param.name);
  const requiredText = param.required ? "(required)" : "(optional)";
  let inputHtml = "";

  if (param.type === "select") {
    const options = resolveParamOptions(param);
    inputHtml = `
            <select id="${fieldId}" name="${param.name}" ${required} style="width: 100%; box-sizing: border-box;">
                ${buildSelectOptionsHtml(options, true)}
            </select>
        `;
  } else if (param.type === "multiselect") {
    const options = resolveParamOptions(param);
    const serialize = param.serialize || (isBody ? "json" : "csv");
    inputHtml = `
            ${buildChipMultiselectHtml(fieldId, param.name, options, serialize, required)}
            <span class="field-hint">${param.help || "Values can be ticked in the list, then confirmed with Apply."}</span>
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
                    <input type="text" id="${fieldId}" name="${param.name}" ${required} placeholder="${param.placeholder || param.example || "Enter value"}" style="width: 100%; box-sizing: border-box;">
                    ${param.example ? `<small style="display: block; margin-top: 0.25rem; color: #64748b; font-size: 0.85rem;">Example: ${param.example}</small>` : ""}
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
    const elementTitle = getElementTitle(endpoint);
    const jsonFormHtml = generateJsonFormField(
      fieldId,
      param.name,
      jsonStructure,
      prefix,
      required,
      requiredText,
      formattedName,
      elementTitle,
      param.nestedSelectOptions || null
    );
    return jsonFormHtml;
  } else if (param.type === "file") {
    inputHtml = `
            <input type="file" id="${fieldId}" name="${param.name}" ${required} style="width: 100%; box-sizing: border-box;">
        `;
  } else if (param.type === "number") {
    inputHtml = `
            <input type="number" id="${fieldId}" name="${param.name}" ${required} placeholder="${param.placeholder || ""}" style="width: 100%; box-sizing: border-box;">
        `;
  } else {
    inputHtml = `
            <input type="${param.type}" id="${fieldId}" name="${param.name}" ${required} placeholder="${param.placeholder || ""}" style="width: 100%; box-sizing: border-box;">
        `;
  }

  return `
        <div class="form-group">
            <label for="${fieldId}">${formattedName} ${requiredText}</label>
            ${inputHtml}
        </div>
    `;
}

function getElementTitle(endpoint) {
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

function generateJsonFormField(
  fieldId,
  fieldName,
  jsonStructure,
  prefix,
  required,
  requiredText,
  formattedName,
  elementTitle = "Item",
  nestedSelectOptions = null
) {
  if (Array.isArray(jsonStructure)) {
    // Handle array: show each element with sub-fields and "Add new element" button
    const containerId = `${fieldId}-container`;
    const nestedSelectOptionsJson = JSON.stringify(nestedSelectOptions || {});

    let html = `
            <div class="json-form-container" id="${containerId}" data-field-name="${fieldName}" data-structure-type="array">
                <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">${formattedName} ${requiredText}</label>
                <div class="json-array-items" id="${fieldId}-items">
        `;

    // Add first element if array has items
    if (jsonStructure.length > 0) {
      html += generateArrayElement(
        fieldId,
        fieldName,
        jsonStructure[0],
        0,
        prefix,
        elementTitle,
        nestedSelectOptions
      );
    } else {
      // Empty array - add one empty element
      html += generateArrayElement(
        fieldId,
        fieldName,
        {},
        0,
        prefix,
        elementTitle,
        nestedSelectOptions
      );
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
                        data-nested-select-options='${nestedSelectOptionsJson.replace(/'/g, "&apos;")}'
                        style="margin-top: 0.5rem;">
                    Add
                </button>
            </div>
        `;

    return html;
  } else if (jsonStructure && typeof jsonStructure === "object") {
    // Handle object: show all keys as form fields
    return generateObjectFields(
      fieldId,
      fieldName,
      jsonStructure,
      prefix,
      required,
      requiredText,
      formattedName,
      nestedSelectOptions
    );
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

function generateArrayElement(
  fieldId,
  fieldName,
  elementStructure,
  index,
  prefix,
  elementTitle = "Item",
  nestedSelectOptions = null
) {
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
  if (elementStructure && typeof elementStructure === "object") {
    Object.keys(elementStructure).forEach(key => {
      const value = elementStructure[key];
      html += generateFieldForValue(
        `${elementId}-${key}`,
        key,
        value,
        prefix,
        fieldName,
        nestedSelectOptions
      );
    });
  }

  html += `
            </div>
        </div>
    `;

  return html;
}

function generateObjectFields(
  fieldId,
  fieldName,
  objStructure,
  prefix,
  required,
  requiredText,
  formattedName,
  nestedSelectOptions = null
) {
  let html = `
        <div class="json-form-container" id="${fieldId}-container" data-field-name="${fieldName}" data-structure-type="object">
            <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">${formattedName} ${requiredText}</label>
            <div class="json-object-fields" style="border: 1px solid #cbd5e1; border-radius: 0.375rem; padding: 1rem; background-color: #f8fafc;">
    `;

  Object.keys(objStructure).forEach(key => {
    const value = objStructure[key];
    html += generateFieldForValue(
      `${fieldId}-${key}`,
      key,
      value,
      prefix,
      fieldName,
      nestedSelectOptions
    );
  });

  html += `
            </div>
        </div>
    `;

  return html;
}

function generateFieldForValue(
  fieldId,
  fieldName,
  value,
  prefix,
  baseFieldName = "",
  nestedSelectOptions = null
) {
  const formattedName = formatParameterName(fieldName);
  let inputHtml = "";

  if (Array.isArray(value)) {
    // Nested array - create a simple text input for now (could be enhanced)
    inputHtml = `
            <input type="text" id="${fieldId}" name="${fieldName}" data-field-path="${fieldName}" placeholder='${JSON.stringify(value)}' style="width: 100%; box-sizing: border-box;">
            <small style="display: block; margin-top: 0.25rem; color: #64748b; font-size: 0.85rem;">Array: Enter comma-separated values or JSON array</small>
        `;
  } else if (value && typeof value === "object") {
    // Nested object - recursively generate fields
    let nestedHtml = `
            <div class="nested-object" data-nested-key="${fieldName}" style="border: 1px solid #e2e8f0; border-radius: 0.25rem; padding: 0.75rem; margin-top: 0.5rem; background-color: white;">
                <strong style="color: #475569; display: block; margin-bottom: 0.5rem;">${formattedName}</strong>
        `;

    Object.keys(value).forEach(nestedKey => {
      nestedHtml += generateFieldForValue(
        `${fieldId}-${nestedKey}`,
        nestedKey,
        value[nestedKey],
        prefix,
        baseFieldName,
        nestedSelectOptions
      );
    });

    nestedHtml += "</div>";
    return `
            <div class="form-group" style="margin-bottom: 1rem;">
                <label for="${fieldId}" style="display: block; margin-bottom: 0.25rem; font-weight: 500;">${formattedName}</label>
                ${nestedHtml}
            </div>
        `;
  } else {
    const overrideOptionsFrom = nestedSelectOptions && nestedSelectOptions[fieldName];
    const closedOptions = overrideOptionsFrom
      ? resolveParamOptions({ optionsFrom: overrideOptionsFrom })
      : resolveNestedFieldOptions(fieldName);

    if (closedOptions && closedOptions.length > 0) {
      inputHtml = `
            <select id="${fieldId}" name="${fieldName}" data-field-path="${fieldName}" style="width: 100%; box-sizing: border-box;">
                ${buildSelectOptionsHtml(closedOptions, true)}
            </select>
        `;
    } else {
      // Simple value - determine input type
      // Check if field name contains 'date' to use date picker
      const isDateField = fieldName.toLowerCase().includes("date");
      const inputType = typeof value === "number" ? "number" :
        isDateField ? "date" :
          (value && String(value).match(/^\d{4}-\d{2}-\d{2}/)) ? "date" : "text";

      // Use value only as placeholder hint, not as default value
      const placeholderHint = value || "";
      inputHtml = `
            <input type="${inputType}" id="${fieldId}" name="${fieldName}" data-field-path="${fieldName}" value="" placeholder="${placeholderHint}" style="width: 100%; box-sizing: border-box;">
        `;
    }
  }

  return `
        <div class="form-group" style="margin-bottom: 1rem;">
            <label for="${fieldId}" style="display: block; margin-bottom: 0.25rem; font-weight: 500;">${formattedName}</label>
            ${inputHtml}
        </div>
    `;
}

// Global function to add array element
function addArrayElement(
  fieldId,
  fieldName,
  elementStructureJson,
  prefix,
  elementTitle = "Item",
  nestedSelectOptionsJson = null
) {
  const itemsContainer = document.getElementById(`${fieldId}-items`);
  if (!itemsContainer) {
    console.error("Items container not found:", `${fieldId}-items`);
    return;
  }

  // Parse the element structure from JSON string
  let elementStructure;
  try {
    // Unescape HTML entities if needed
    const unescaped = elementStructureJson.replace(/&apos;/g, "'").replace(/&#39;/g, "'");
    elementStructure = JSON.parse(unescaped);
  } catch (e) {
    console.error("Error parsing element structure:", e, elementStructureJson);
    elementStructure = {};
  }

  let nestedSelectOptions = null;
  if (nestedSelectOptionsJson) {
    try {
      const unescapedOptions = nestedSelectOptionsJson
        .replace(/&apos;/g, "'")
        .replace(/&#39;/g, "'");
      nestedSelectOptions = JSON.parse(unescapedOptions);
    } catch (e) {
      console.error("Error parsing nested select options:", e, nestedSelectOptionsJson);
      nestedSelectOptions = null;
    }
  }

  const existingItems = itemsContainer.querySelectorAll(".json-array-item");
  const newIndex = existingItems.length;

  const newElement = document.createElement("div");
  newElement.innerHTML = generateArrayElement(
    fieldId,
    fieldName,
    elementStructure,
    newIndex,
    prefix,
    elementTitle,
    nestedSelectOptions
  );
  const elementNode = newElement.firstElementChild;
  if (elementNode) {
    itemsContainer.appendChild(elementNode);
  } else {
    console.error("Failed to create array element");
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
    const container = element.closest(".json-array-items");
    if (container) {
      const items = container.querySelectorAll(".json-array-item");
      items.forEach((item, index) => {
        item.setAttribute("data-index", index);
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
        } else if (param.type === "multiselect") {
          const selectedValues = getSelectedMultiValues(input);
          if (selectedValues.length === 0) {
            return;
          }
          const serialize = param.serialize || input.getAttribute("data-serialize") || "csv";
          if (serialize === "repeat") {
            selectedValues.forEach(value => queryParams.append(param.name, value));
            queryData[param.name] = selectedValues;
          } else {
            const csvValue = selectedValues.join(",");
            queryParams.append(param.name, csvValue);
            queryData[param.name] = csvValue;
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
            const arrayItems = formContainer.querySelectorAll(".json-array-item");
            const arrayData = [];

            arrayItems.forEach((item) => {
              const itemObj = {};
              const inputs = item.querySelectorAll("input, select, textarea");

              inputs.forEach(input => {
                const fieldPath = input.getAttribute("data-field-path");
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
            if (param.type === "multiselect") {
              if (!input) {
                return;
              }
              const selectedValues = getSelectedMultiValues(input);
              // Optional empty multi-select still sends [] when serialize is json.
              if (param.serialize === "json" || !param.required) {
                bodyObj[param.name] = selectedValues;
                hasBodyData = true;
              } else if (selectedValues.length > 0) {
                bodyObj[param.name] = selectedValues;
                hasBodyData = true;
              }
              return;
            }
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
                  const structureType = jsonContainer.getAttribute("data-structure-type");
                  if (structureType === "array") {
                    bodyObj[param.name] = collectArrayValues(jsonContainer);
                    hasBodyData = true;
                  } else if (structureType === "object") {
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
            const hasFiles = Array.from(formData.entries()).some(([, value]) => value instanceof File);
            if (hasFiles) {
              // If we have files, merge bodyObj into formData
              Object.keys(bodyObj).forEach(key => {
                if (typeof bodyObj[key] === "object") {
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
  function collectArrayValues(container) {
    const items = container.querySelectorAll(".json-array-item");
    const array = [];

    items.forEach((item) => {
      const itemData = collectObjectValues(item);
      // Only add if item has at least one non-empty value
      if (Object.keys(itemData).length > 0 && Object.values(itemData).some(v => v !== "" && v !== null && v !== undefined)) {
        array.push(itemData);
      }
    });

    return array;
  }

  function collectObjectValues(container) {
    const obj = {};
    const inputs = container.querySelectorAll("input:not([type=\"file\"]), select, textarea");

    inputs.forEach((input) => {
      if (input.type === "file") {
        return; // Skip file inputs
      }

      // Use data-field-path attribute if available, otherwise parse from ID
      let fieldPath = [];
      if (input.hasAttribute("data-field-path")) {
        fieldPath = [input.getAttribute("data-field-path")];
      } else {
        // Parse from ID: find the field name (last part after all prefixes)
        const fullId = input.id;
        const parts = fullId.split("-");
        // Find the actual field name - it's typically the last part, but we need to handle nested objects
        // Look for nested-object containers to determine hierarchy
        let nestedKey = null;
        const nestedObj = input.closest(".nested-object");
        if (nestedObj) {
          nestedKey = nestedObj.getAttribute("data-nested-key");
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
      if (input.type === "checkbox") {
        value = input.checked;
      } else if (input.type === "number") {
        value = input.value ? parseFloat(input.value) : null;
      } else if (input.type === "date") {
        value = input.value || null;
      } else if (input.tagName === "SELECT") {
        value = input.value || null;
      } else {
        // For text inputs, try to parse as JSON if it looks like JSON
        const textValue = input.value.trim();
        if (textValue.startsWith("[") || textValue.startsWith("{")) {
          try {
            value = JSON.parse(textValue);
          } catch (e) {
            value = textValue;
          }
        } else if (textValue.includes(",") && !textValue.includes("{") && !textValue.includes("[")) {
          // Comma-separated values - treat as array
          value = textValue.split(",").map(v => v.trim()).filter(v => v);
        } else {
          value = textValue || null;
        }
      }

      // Only add non-empty values
      if (value !== null && value !== "" && value !== undefined) {
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
      if (!obj[key] || typeof obj[key] !== "object" || Array.isArray(obj[key])) {
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

window.confirmRequest = confirmRequest;

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

window.executeDeleteRequest = executeDeleteRequest;

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
    conditionsHtml = "<div class=\"delete-condition-item delete-condition-empty\">No specific conditions - all matching records will be deleted</div>";
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
