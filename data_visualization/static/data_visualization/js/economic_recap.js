const economicRecapSections = window.economicRecapDataJSON || [];
const economicRecapLocations = window.economicRecapLocationsJSON || [];

const MODE_ABS = "ABS";
const MODE_QOQ = "QOQ";
const MODE_QOQY = "QOQY";
const MODE_YOY = "YOY";

const ABS_UNIT_INDEX = "INDEX";
const ABS_UNIT_PERCENT = "PERCENT";
const ABS_UNIT_SCALES = new Set(["K", "M", "B"]);

function lagForMode(frequency, mode) {
  if (mode === MODE_ABS) {
    return 0;
  }
  const freq = (frequency || "").toUpperCase();
  if (mode === MODE_QOQ || mode === MODE_QOQY) {
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

/** Space as thousands separator, e.g. 1234.5 → "1 234.5". */
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
 * Abs name paren from documented base_unit (INDICATORS.md) — never infer
 * K/M/B from the magnitude of the printed value.
 */
function buildDisplayName(baseName, mode, record) {
  if (mode === MODE_QOQ || mode === MODE_QOQY || mode === MODE_YOY) {
    return `${baseName} (in %)`;
  }
  const unit = (record && record.base_unit) || "";
  if (unit === ABS_UNIT_INDEX && record.base_year != null) {
    return `${baseName} (base year: ${record.base_year})`;
  }
  if (unit === ABS_UNIT_PERCENT) {
    return `${baseName} (in %)`;
  }
  if (ABS_UNIT_SCALES.has(unit)) {
    return `${baseName} (in ${unit})`;
  }
  return baseName;
}

function valuesForMode(timeSeries, frequency, mode) {
  if (!timeSeries || timeSeries.length === 0) {
    return { current: null, previous: null, change: null, period: null };
  }
  if (mode === MODE_ABS) {
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
      mode === MODE_QOQY
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

function updateRow(row, mode) {
  const indicatorName = row.dataset.indicatorName;
  const category = row.dataset.category;
  const nameCell = row.querySelector(".name-cell");
  const baseName = (nameCell && nameCell.dataset.baseName) || indicatorName;

  const metaRecord =
    economicRecapLocations
      .map((loc) => findRecord(indicatorName, category, loc))
      .find(Boolean) || null;

  if (nameCell) {
    nameCell.textContent = buildDisplayName(baseName, mode, metaRecord);
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
      currEmpty ? "—" : formatSpaced(values.current, 1),
      currEmpty
    );
    setCellText(
      prevCell,
      prevEmpty ? "—" : formatSpaced(values.previous, 1),
      prevEmpty
    );
    setChangeCell(
      chgCell,
      chgEmpty ? "—" : formatSpaced(values.change, 1),
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
  const defaultMode = row.dataset.defaultMode || MODE_ABS;
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
