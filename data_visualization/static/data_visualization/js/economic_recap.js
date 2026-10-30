const economicRecapSections = window.economicRecapDataJSON || [];
const economicRecapLocations = window.economicRecapLocationsJSON || [];

const MODE_RAW = "Raw";
const MODE_QUARTER = "Quarter";
const MODE_ANNUALIZED_QUARTER = "Annualized Quarter";
const MODE_ANNUAL = "Annual";

const ABS_UNIT_INDEX = "INDEX";
const ABS_UNIT_PERCENT = "PERCENT";
const ABS_UNIT_SCALES = ["K", "M", "B", "T"];

function lagForMode(frequency, mode) {
  if (mode === MODE_RAW) {
    return 0;
  }
  const freq = (frequency || "").toUpperCase();
  if (mode === MODE_QUARTER || mode === MODE_ANNUALIZED_QUARTER) {
    if (freq === "MONTHLY") return 3;
    if (freq === "QUARTERLY") return 1;
    return 1; // ANNUAL: treat QoQ / QoQy as YoY lag
  }
  // YOY
  if (freq === "MONTHLY") return 12;
  if (freq === "QUARTERLY") return 4;
  return 1;
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

function formatAmountUnitLabel(magnitude, currency) {
  const label = String(magnitude || "").toLowerCase();
  return currency ? `${label}${currency}` : label;
}

function formatAbsValue(value, record) {
  const unit = (record && record.base_unit) || "";
  const currency = (record && record.base_currency) || "";
  if (ABS_UNIT_SCALES.includes(unit) && unit !== "T") {
    const scaled = scaleAmountForDisplay(value, unit, currency);
    return formatSpaced(scaled.value, 2);
  }
  return formatSpaced(value, 2);
}

/**
 * Abs name paren — join differing base years / amount units across locations.
 */
function buildDisplayName(baseName, mode, locationRecords) {
  if (mode === MODE_QUARTER || mode === MODE_ANNUALIZED_QUARTER || mode === MODE_ANNUAL) {
    return `${baseName} (in %)`;
  }
  const records = (locationRecords || []).filter(Boolean);
  if (records.length === 0) {
    return baseName;
  }

  const units = [...new Set(records.map((record) => record.base_unit || ""))];
  if (units.length === 1 && units[0] === ABS_UNIT_PERCENT) {
    return `${baseName} (in %)`;
  }
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

  const amountLabels = [];
  records.forEach((record) => {
    const unit = record.base_unit || "";
    if (!["K", "M", "B"].includes(unit)) {
      return;
    }
    // Name paren uses documented base unit (not value-scaled) so the column
    // stays stable; per-cell scaling still applies to printed figures.
    amountLabels.push(formatAmountUnitLabel(unit, record.base_currency || ""));
  });
  const uniqueLabels = [...new Set(amountLabels)];
  if (uniqueLabels.length === 0) {
    return baseName;
  }
  return `${baseName} (in ${uniqueLabels.join(" / ")})`;
}

function valuesForMode(timeSeries, frequency, mode) {
  if (!timeSeries || timeSeries.length === 0) {
    return { current: null, previous: null, change: null, period: null };
  }
  if (mode === MODE_RAW) {
    const curr = timeSeries[timeSeries.length - 1];
    const prev = timeSeries.length >= 2 ? timeSeries[timeSeries.length - 2] : null;
    const currVal = curr ? curr.value : null;
    const prevVal = prev ? prev.value : null;
    return {
      current: currVal,
      previous: prevVal,
      change:
        currVal != null && prevVal != null ? currVal - prevVal : null,
      period: curr ? curr.period : null,
    };
  }

  const lag = lagForMode(frequency, mode);
  const transformed = [];
  for (let i = lag; i < timeSeries.length; i++) {
    const curr = timeSeries[i];
    const prev = timeSeries[i - lag];
    const chg =
      mode === MODE_ANNUALIZED_QUARTER
        ? annualizedQoqPercent(curr.value, prev.value)
        : pctChange(curr.value, prev.value);
    if (chg == null) {
      continue;
    }
    transformed.push({
      period: curr.period,
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
  const curr = transformed[transformed.length - 1];
  const prev =
    transformed.length >= 2 ? transformed[transformed.length - 2] : null;
  return {
    current: curr.value,
    previous: prev ? prev.value : null,
    change:
      curr.value != null && prev && prev.value != null
        ? curr.value - prev.value
        : null,
    period: curr.period,
  };
}

function findRecord(indicatorName, category, location) {
  const section = economicRecapSections.find(
    (categoryGroup) => categoryGroup.category === category
  );
  const group = section ? section.rows : [];
  return group.find(
    (item) => item.name === indicatorName && item.location === location
  );
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

function formatCellValue(value, mode, record) {
  if (value == null) {
    return "—";
  }
  if (mode === MODE_RAW) {
    return formatAbsValue(value, record);
  }
  return formatSpaced(value, 2);
}

function updateRow(row, mode) {
  const indicatorName = row.dataset.indicatorName;
  const category = row.dataset.category;
  const nameCell = row.querySelector(".name-cell");
  const baseName = (nameCell && nameCell.dataset.baseName) || indicatorName;

  const locationRecords = economicRecapLocations
    .map((loc) => findRecord(indicatorName, category, loc))
    .filter(Boolean);

  if (nameCell) {
    nameCell.textContent = buildDisplayName(baseName, mode, locationRecords);
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

    const values = valuesForMode(record.time_series, record.frequency, mode);
    const currEmpty = values.current == null;
    const prevEmpty = values.previous == null;
    const chgEmpty = values.change == null;

    setCellText(
      currCell,
      currEmpty ? "—" : formatCellValue(values.current, mode, record),
      currEmpty
    );
    setCellText(
      prevCell,
      prevEmpty ? "—" : formatCellValue(values.previous, mode, record),
      prevEmpty
    );
    setChangeCell(
      chgCell,
      chgEmpty ? "—" : formatCellValue(values.change, mode, record),
      values.change,
      chgEmpty
    );
    if (periodCell) {
      const empty = !values.period;
      setCellText(periodCell, values.period || "—", empty);
    }
  });
}

document.querySelectorAll(".indicator-row").forEach((row) => {
  const select = row.querySelector(".recap-mode-select");
  if (!select) return;
  const defaultMode = row.dataset.defaultMode || MODE_RAW;
  select.value = defaultMode;
  updateRow(row, defaultMode);
  select.addEventListener("change", () => {
    updateRow(row, select.value);
  });
});

function syncTheadStickyOffset() {
  const table = document.querySelector(".economic-table-scroll table");
  const primary = table && table.querySelector("thead tr.thead-primary");
  if (!table || !primary) return;
  table.style.setProperty(
    "--econ-thead-primary-height",
    `${primary.getBoundingClientRect().height}px`
  );
}

syncTheadStickyOffset();
window.addEventListener("resize", syncTheadStickyOffset);
