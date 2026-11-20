/**
 * Render one region's sector analysis: pies, top equities, and best/worst sectors.
 */

const SECTOR_ANALYSIS_DATA = JSON.parse(
  document.getElementById("sector-analysis-data").textContent,
);

const LOCATION_LABEL_BY_CODE = {
  US: "United States",
  FR: "France",
  JP: "Japan",
};

const INDEX_LABEL_BY_CODE = {
  SPX: "S&P 500",
  CAC40: "CAC 40",
  NIKKEI225: "Nikkei 225",
};

// Best/worst history lines — high-contrast for the top-3 series.
const PERFORMERS_HISTORY_PALETTE = [
  "rgb(220, 38, 38)",
  "rgb(37, 99, 235)",
  "rgb(22, 163, 74)",
  "rgb(234, 88, 12)",
  "rgb(147, 51, 234)",
  "rgb(8, 145, 178)",
];

// Historical sector performance — cyan family.
const HISTORICAL_LINE_PALETTE = [
  "rgb(6, 182, 212)",
  "rgb(8, 145, 178)",
  "rgb(14, 116, 144)",
  "rgb(34, 211, 238)",
  "rgb(22, 78, 99)",
  "rgb(103, 232, 249)",
  "rgb(21, 94, 117)",
  "rgb(165, 243, 252)",
  "rgb(7, 89, 133)",
  "rgb(56, 189, 248)",
  "rgb(12, 74, 110)",
];

const SECTOR_PERFORMERS_COUNT = 3;
const PERFORMERS_PERIOD_WEEK = "week";
const PERFORMERS_PERIOD_MONTH = "month";
const PERFORMERS_PERIOD_YTD = "ytd";
const PERFORMERS_PERIOD_CUSTOM = "custom";
const PERFORMERS_PERIOD_OPTIONS = [
  { value: PERFORMERS_PERIOD_WEEK, label: "Week" },
  { value: PERFORMERS_PERIOD_MONTH, label: "Month" },
  { value: PERFORMERS_PERIOD_YTD, label: "YTD" },
  { value: PERFORMERS_PERIOD_CUSTOM, label: "Period" },
];

const chartInstances = [];
let performersHistoryChart = null;
let performersBarChart = null;
let lineChart = null;
let sectorPieChart = null;
let subsectorPieChart = null;
let topMoversChart = null;
let subsectorPieTitle = null;
let topMoversTitle = null;
let selectedSectorName = null;
let selectedSubsectorName = null;
let lineHistoryPoints = [];
let pageAsOfDate = null;
let sectorDayByName = {};
let performersBarCanvas = null;
let performersHistoryCanvas = null;
let bestSectorNames = [];
let worstSectorNames = [];
let selectedLineSectorNames = [];
let pendingLineSectorNames = [];
let performersHistoryMode = "best";
let performersBarPeriod = PERFORMERS_PERIOD_YTD;
let performersBarCustomStart = null;
let performersHistoryPeriod = PERFORMERS_PERIOD_YTD;
let performersHistoryCustomStart = null;
let historicalLinePeriod = PERFORMERS_PERIOD_YTD;
let historicalLineCustomStart = null;
let historicalLineCanvas = null;

// Skip label and value when the slice is too small to read.
const PIE_LABEL_MIN_ANGLE = 0.32;
const PIE_LABEL_LINE_LENGTH = 8;
const PIE_LABEL_TEXT_GAP = 4;
const PIE_LABEL_LINE_TO_TEXT_GAP = 6;
const PIE_CALLOUT_MIN_GAP = 16;
const PIE_CALLOUT_EDGE_PAD = 6;
const PIE_CALLOUT_RADIUS_STEP = 10;
const PIE_CALLOUT_MAX_EXTRA_RADIUS = 56;
const PIE_OUTSIDE_LABEL_COLOR = "#0f172a";
const PIE_INNER_VALUE_COLOR = "#f1f5f9";
const BAR_INNER_LABEL_COLOR = "#f1f5f9";

function formatPieReturnLabel(dailyReturn) {
  return `${dailyReturn >= 0 ? "+" : ""}${dailyReturn.toFixed(1)}%`;
}

function listPieCalloutEntries(slices, dataset, arcs) {
  const entries = [];
  arcs.forEach((arc, index) => {
    if (!arc || arc.hidden) {
      return;
    }
    const slice = slices[index];
    const value = dataset.data[index];
    if (!slice || typeof value !== "number" || value <= 0) {
      return;
    }
    const outerRadius = typeof arc.outerRadius === "number" ? arc.outerRadius : 0;
    const innerRadius = typeof arc.innerRadius === "number" ? arc.innerRadius : 0;
    if (!(outerRadius > 0)) {
      return;
    }
    const sliceAngle = Math.abs(arc.endAngle - arc.startAngle);
    if (sliceAngle < PIE_LABEL_MIN_ANGLE) {
      return;
    }
    const midAngle = (arc.startAngle + arc.endAngle) / 2;
    entries.push({
      arc,
      slice,
      midAngle,
      outerRadius,
      innerRadius,
      returnLabel: formatPieReturnLabel(slice.daily_return),
      labelName: slice.name,
    });
  });
  return entries;
}

function placePieCalloutAtRadius(callout, labelRadius, drawBounds) {
  callout.labelRadius = labelRadius;
  const rawX = callout.centerX + Math.cos(callout.midAngle) * labelRadius;
  const rawY = callout.centerY + Math.sin(callout.midAngle) * labelRadius;
  // Clamp to the full canvas (padding zone), not the doughnut chartArea,
  // so full-name labels can sit outside the pie.
  callout.labelX = Math.min(
    Math.max(rawX, drawBounds.left + PIE_CALLOUT_EDGE_PAD),
    drawBounds.right - PIE_CALLOUT_EDGE_PAD,
  );
  callout.labelY = Math.min(
    Math.max(rawY, drawBounds.top + PIE_CALLOUT_EDGE_PAD),
    drawBounds.bottom - PIE_CALLOUT_EDGE_PAD,
  );
}

function doPieCalloutsOverlap(leftCallout, rightCallout) {
  return (
    Math.hypot(
      leftCallout.labelX - rightCallout.labelX,
      leftCallout.labelY - rightCallout.labelY,
    ) < PIE_CALLOUT_MIN_GAP
  );
}

function resolvePieCalloutOverlapsOutward(callouts, drawBounds) {
  const baseExtra = PIE_LABEL_LINE_LENGTH + PIE_LABEL_TEXT_GAP;
  const maxRadiusByOuter = (outerRadius) =>
    outerRadius + baseExtra + PIE_CALLOUT_MAX_EXTRA_RADIUS;

  callouts.forEach((callout) => {
    placePieCalloutAtRadius(callout, callout.outerRadius + baseExtra, drawBounds);
  });

  for (let pass = 0; pass < 16; pass += 1) {
    let movedOutward = false;
    for (let leftIndex = 0; leftIndex < callouts.length; leftIndex += 1) {
      for (
        let rightIndex = leftIndex + 1;
        rightIndex < callouts.length;
        rightIndex += 1
      ) {
        const leftCallout = callouts[leftIndex];
        const rightCallout = callouts[rightIndex];
        if (!doPieCalloutsOverlap(leftCallout, rightCallout)) {
          continue;
        }
        // On overlap, push the nearer label further out — never inward.
        const nearerCallout =
          leftCallout.labelRadius <= rightCallout.labelRadius
            ? leftCallout
            : rightCallout;
        const nextRadius = nearerCallout.labelRadius + PIE_CALLOUT_RADIUS_STEP;
        if (nextRadius > maxRadiusByOuter(nearerCallout.outerRadius)) {
          continue;
        }
        placePieCalloutAtRadius(nearerCallout, nextRadius, drawBounds);
        movedOutward = true;
      }
    }
    if (!movedOutward) {
      break;
    }
  }
}

function measureMaxPieLabelWidth(ctx, names) {
  ctx.save();
  ctx.font = "bold 11px sans-serif";
  let maxWidth = 0;
  names.forEach((name) => {
    maxWidth = Math.max(maxWidth, ctx.measureText(String(name || "")).width);
  });
  ctx.restore();
  return maxWidth;
}

function computePieCalloutPadding(ctx, sliceNames) {
  const maxLabelWidth = measureMaxPieLabelWidth(ctx, sliceNames);
  // Reserve room outside the doughnut so full names fit on the canvas.
  const side = Math.ceil(
    PIE_LABEL_LINE_LENGTH +
      PIE_LABEL_TEXT_GAP +
      PIE_LABEL_LINE_TO_TEXT_GAP +
      maxLabelWidth +
      PIE_CALLOUT_EDGE_PAD +
      8,
  );
  const vertical = Math.ceil(
    PIE_LABEL_LINE_LENGTH + PIE_LABEL_TEXT_GAP + PIE_CALLOUT_EDGE_PAD + 14,
  );
  return { top: vertical, right: side, bottom: vertical, left: side };
}

function syncPieFitLayout(chart, sliceNames) {
  // Must run outside Chart.js layout — mutating options inside beforeLayout
  // trips the options proxy and stack-overflows on update/click.
  const nextPadding = computePieCalloutPadding(chart.ctx, sliceNames);
  const prev = chart.options.layout?.padding || {};
  if (
    prev.top === nextPadding.top &&
    prev.right === nextPadding.right &&
    prev.bottom === nextPadding.bottom &&
    prev.left === nextPadding.left &&
    chart.options.radius === "100%"
  ) {
    return;
  }
  chart.options.layout = {
    ...(chart.options.layout || {}),
    padding: nextPadding,
  };
  chart.options.radius = "100%";
}

function drawPieOutsideCallout(ctx, callout) {
  const edgeX = callout.centerX + Math.cos(callout.midAngle) * callout.outerRadius;
  const edgeY = callout.centerY + Math.sin(callout.midAngle) * callout.outerRadius;
  const elbowX =
    callout.centerX +
    Math.cos(callout.midAngle) * (callout.outerRadius + PIE_LABEL_LINE_LENGTH);
  const elbowY =
    callout.centerY +
    Math.sin(callout.midAngle) * (callout.outerRadius + PIE_LABEL_LINE_LENGTH);

  ctx.beginPath();
  ctx.moveTo(edgeX, edgeY);
  ctx.lineTo(elbowX, elbowY);
  if (Math.abs(callout.labelY - elbowY) > 1 || Math.abs(callout.labelX - elbowX) > 1) {
    ctx.lineTo(callout.labelX, callout.labelY);
  }
  ctx.strokeStyle = "#64748b";
  ctx.lineWidth = 1;
  ctx.stroke();

  const textX =
    callout.labelX +
    (callout.isRight ? PIE_LABEL_LINE_TO_TEXT_GAP : -PIE_LABEL_LINE_TO_TEXT_GAP);
  ctx.fillStyle = PIE_OUTSIDE_LABEL_COLOR;
  ctx.textAlign = callout.isRight ? "left" : "right";
  ctx.textBaseline = "middle";
  ctx.font = "bold 11px sans-serif";
  ctx.fillText(callout.labelName, textX, callout.labelY);
}

function drawPieInnerReturnValue(ctx, callout) {
  const radius =
    callout.innerRadius + (callout.outerRadius - callout.innerRadius) * 0.55;
  const x = callout.centerX + Math.cos(callout.midAngle) * radius;
  const y = callout.centerY + Math.sin(callout.midAngle) * radius;
  ctx.fillStyle = PIE_INNER_VALUE_COLOR;
  ctx.font = "bold 13px sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(callout.returnLabel, x, y);
}

const sectorPieSliceLabelsPlugin = {
  id: "sectorPieSliceLabels",
  afterDatasetsDraw(chart) {
    const slices = chart._sectorAnalysisSlices;
    const dataset = chart.data.datasets[0];
    const chartArea = chart.chartArea;
    if (!slices || !dataset || !Array.isArray(dataset.data) || !chartArea) {
      return;
    }
    const meta = chart.getDatasetMeta(0);
    if (!meta || !Array.isArray(meta.data)) {
      return;
    }
    const entries = listPieCalloutEntries(slices, dataset, meta.data);
    if (!entries.length) {
      return;
    }
    // The first visible arc carries the shared doughnut center.
    const centerX = entries[0].arc.x;
    const centerY = entries[0].arc.y;
    const callouts = entries.map((entry) => ({
      ...entry,
      centerX,
      centerY,
      isRight: Math.cos(entry.midAngle) >= 0,
      labelRadius: entry.outerRadius + PIE_LABEL_LINE_LENGTH + PIE_LABEL_TEXT_GAP,
      labelX: 0,
      labelY: 0,
    }));
    const drawBounds = {
      left: 0,
      right: chart.width,
      top: 0,
      bottom: chart.height,
    };
    resolvePieCalloutOverlapsOutward(callouts, drawBounds);
    const { ctx } = chart;
    ctx.save();
    callouts.forEach((callout) => {
      drawPieOutsideCallout(ctx, callout);
      drawPieInnerReturnValue(ctx, callout);
    });
    ctx.restore();
  },
};

const topMoversBarLabelsPlugin = {
  id: "topMoversBarLabels",
  afterDatasetsDraw(chart) {
    const topMovers = chart._sectorAnalysisTopMovers;
    const meta = chart.getDatasetMeta(0);
    if (!topMovers || !meta || !Array.isArray(meta.data)) {
      return;
    }
    const { ctx } = chart;
    ctx.save();
    ctx.fillStyle = BAR_INNER_LABEL_COLOR;
    ctx.font = "bold 12px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    meta.data.forEach((bar, index) => {
      if (!bar || bar.hidden) {
        return;
      }
      const mover = topMovers[index];
      if (!mover) {
        return;
      }
      const barLeft = Math.min(bar.x, bar.base);
      const barRight = Math.max(bar.x, bar.base);
      if (barRight - barLeft < 36) {
        return;
      }
      const returnLabel = formatPieReturnLabel(mover.daily_return);
      ctx.fillText(returnLabel, (barLeft + barRight) / 2, bar.y);
    });
    ctx.restore();
  },
};

function getReturnColor(dailyReturn) {
  if (dailyReturn > 0) {
    const intensity = Math.min(Math.abs(dailyReturn) / 3, 1);
    return `rgba(22, 163, 74, ${0.35 + intensity * 0.55})`;
  }
  if (dailyReturn < 0) {
    const intensity = Math.min(Math.abs(dailyReturn) / 3, 1);
    return `rgba(220, 38, 38, ${0.35 + intensity * 0.55})`;
  }
  return "rgba(148, 163, 184, 0.7)";
}

function listSectorNames(historyPoints) {
  const names = new Set();
  historyPoints.forEach((historyPoint) => {
    Object.keys(historyPoint.returns_by_sector || {}).forEach((name) => {
      names.add(name);
    });
  });
  return Array.from(names).sort();
}

function buildIndexedReturnValues(historyPoints, sectorName, startDate) {
  // Base 100 at the window start, then compound each later daily percent return.
  const values = startDate ? [100] : [];
  let indexLevel = 100;
  let hasBasePoint = Boolean(startDate);
  historyPoints.forEach((historyPoint) => {
    const dailyReturn = historyPoint.returns_by_sector[sectorName];
    if (dailyReturn === undefined || dailyReturn === null) {
      values.push(null);
      return;
    }
    if (!hasBasePoint) {
      values.push(100);
      hasBasePoint = true;
      indexLevel = 100;
    }
    indexLevel *= 1 + dailyReturn / 100;
    values.push(indexLevel);
  });
  return values;
}

function getPerformersHistoryChartLabels(windowPoints, startDate) {
  if (!startDate) {
    return windowPoints.map((point) => point.date);
  }
  return [startDate, ...windowPoints.map((point) => point.date)];
}

function listSubsectorSlicesForSector(subsectorDay, sectorName) {
  return subsectorDay.filter((slice) => slice.sector === sectorName);
}

function getSubsectorWithBiggestContribution(subsectorSlices) {
  if (!subsectorSlices.length) {
    return null;
  }
  return subsectorSlices.reduce((best, slice) => {
    if (!best) {
      return slice;
    }
    if (Math.abs(slice.contribution) > Math.abs(best.contribution)) {
      return slice;
    }
    if (
      Math.abs(slice.contribution) === Math.abs(best.contribution) &&
      Math.abs(slice.daily_return) > Math.abs(best.daily_return)
    ) {
      return slice;
    }
    return best;
  }, null);
}

function getSubsectorPieTitle(sectorName) {
  return sectorName
    ? `Subsector Day Move — ${sectorName}`
    : "Subsector Day Move";
}

function getTopMoversTitle(subsectorName) {
  return subsectorName
    ? `Top 3 Equities — ${subsectorName}`
    : "Top 3 Equities";
}

function getSectorPieBorderWidths(slices, sectorName) {
  return slices.map((slice) => (slice.name === sectorName ? 3 : 1));
}

function getSectorPieBorderColors(slices) {
  // Same stroke on every slice so shared edges stay black (neighbor white
  // borders otherwise paint over one side of the selected outline).
  return slices.map(() => "#0f172a");
}

function buildLineDatasetStyle(sectorName, index, palette) {
  // Match market_charts line stroke; no fill under the curve.
  const colors = palette || HISTORICAL_LINE_PALETTE;
  const color = colors[index % colors.length];
  return {
    label: sectorName,
    borderColor: color,
    backgroundColor: color,
    tension: 0.3,
    fill: false,
    pointRadius: 3,
  };
}

function buildIndexedLineDatasets(historyPoints, sectorNames, startDate, palette) {
  return sectorNames.map((sectorName, index) => ({
    ...buildLineDatasetStyle(sectorName, index, palette),
    data: buildIndexedReturnValues(historyPoints, sectorName, startDate),
  }));
}

function updateSelectedSectorHighlight(sectorName) {
  if (!sectorPieChart) {
    return;
  }
  const slices = sectorPieChart._sectorAnalysisSlices;
  sectorPieChart.data.datasets[0].borderWidth = getSectorPieBorderWidths(
    slices,
    sectorName,
  );
  sectorPieChart.data.datasets[0].borderColor = getSectorPieBorderColors(slices);
  sectorPieChart.update();
}

function updateSelectedSubsectorHighlight(subsectorName) {
  if (!subsectorPieChart) {
    return;
  }
  const slices = subsectorPieChart._sectorAnalysisSlices;
  subsectorPieChart.data.datasets[0].borderWidth = getSectorPieBorderWidths(
    slices,
    subsectorName,
  );
  subsectorPieChart.data.datasets[0].borderColor =
    getSectorPieBorderColors(slices);
  subsectorPieChart.update();
}

function parseIsoDate(isoDate) {
  if (!isoDate || typeof isoDate !== "string") {
    return null;
  }
  const [yearText, monthText, dayText] = isoDate.split("-");
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  if (!year || !month || !day) {
    return null;
  }
  return new Date(Date.UTC(year, month - 1, day));
}

function formatIsoDate(dateValue) {
  const year = dateValue.getUTCFullYear();
  const month = String(dateValue.getUTCMonth() + 1).padStart(2, "0");
  const day = String(dateValue.getUTCDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function shiftUtcDays(dateValue, dayDelta) {
  const shifted = new Date(dateValue.getTime());
  shifted.setUTCDate(shifted.getUTCDate() + dayDelta);
  return shifted;
}

function shiftUtcMonths(dateValue, monthDelta) {
  const shifted = new Date(
    Date.UTC(
      dateValue.getUTCFullYear(),
      dateValue.getUTCMonth() + monthDelta,
      dateValue.getUTCDate(),
    ),
  );
  // Clamp overflow (e.g. Jan 31 → Feb) back to the last day of the target month.
  if (shifted.getUTCDate() !== dateValue.getUTCDate()) {
    shifted.setUTCDate(0);
  }
  return shifted;
}

function listSortedHistoryDates(historyPoints) {
  return historyPoints
    .map((point) => point.date)
    .filter(Boolean)
    .sort();
}

function findLatestHistoryDateOnOrBefore(historyDates, targetIso) {
  let matched = null;
  historyDates.forEach((historyDate) => {
    if (historyDate <= targetIso) {
      matched = historyDate;
    }
  });
  return matched;
}

function findPeriodStartDate(asOfIso, period, historyDates, customStartIso) {
  const asOfDate = parseIsoDate(asOfIso);
  if (!asOfDate || historyDates.length === 0) {
    return null;
  }
  if (period === PERFORMERS_PERIOD_CUSTOM) {
    if (!customStartIso || !(customStartIso < asOfIso)) {
      return null;
    }
    const customAnchor = findLatestHistoryDateOnOrBefore(
      historyDates,
      customStartIso,
    );
    return customAnchor && customAnchor < asOfIso ? customAnchor : null;
  }
  if (period === PERFORMERS_PERIOD_YTD) {
    const priorYearEnd = formatIsoDate(
      new Date(Date.UTC(asOfDate.getUTCFullYear() - 1, 11, 31)),
    );
    const priorYearAnchor = findLatestHistoryDateOnOrBefore(
      historyDates,
      priorYearEnd,
    );
    if (priorYearAnchor && priorYearAnchor < asOfIso) {
      return priorYearAnchor;
    }
    const yearPrefix = `${asOfDate.getUTCFullYear()}-`;
    const firstInYear = historyDates.find(
      (historyDate) => historyDate.startsWith(yearPrefix) && historyDate < asOfIso,
    );
    return firstInYear || null;
  }
  const targetDate =
    period === PERFORMERS_PERIOD_WEEK
      ? shiftUtcDays(asOfDate, -7)
      : shiftUtcMonths(asOfDate, -1);
  const anchor = findLatestHistoryDateOnOrBefore(
    historyDates,
    formatIsoDate(targetDate),
  );
  if (anchor && anchor < asOfIso) {
    return anchor;
  }
  return null;
}

function compoundSectorPeriodReturn(historyPoints, sectorName, startDate, endDate) {
  let growth = 1;
  let sawReturn = false;
  historyPoints.forEach((historyPoint) => {
    if (historyPoint.date <= startDate || historyPoint.date > endDate) {
      return;
    }
    const dailyReturn = historyPoint.returns_by_sector[sectorName];
    if (dailyReturn === undefined || dailyReturn === null) {
      return;
    }
    growth *= 1 + dailyReturn / 100;
    sawReturn = true;
  });
  return sawReturn ? (growth - 1) * 100 : null;
}

function listSectorPeriodReturns(historyPoints, asOfIso, period, customStartIso) {
  const historyDates = listSortedHistoryDates(historyPoints);
  const startDate = findPeriodStartDate(
    asOfIso,
    period,
    historyDates,
    customStartIso,
  );
  if (!startDate) {
    return [];
  }
  const sectorNames = new Set();
  historyPoints.forEach((historyPoint) => {
    if (historyPoint.date <= startDate || historyPoint.date > asOfIso) {
      return;
    }
    Object.keys(historyPoint.returns_by_sector || {}).forEach((name) => {
      sectorNames.add(name);
    });
  });
  const periodReturns = [];
  sectorNames.forEach((sectorName) => {
    const periodReturn = compoundSectorPeriodReturn(
      historyPoints,
      sectorName,
      startDate,
      asOfIso,
    );
    if (periodReturn === null) {
      return;
    }
    const daySlice = sectorDayByName[sectorName] || {};
    periodReturns.push({
      name: sectorName,
      period_return: periodReturn,
      weight: daySlice.weight,
      contribution: daySlice.contribution,
      start_date: startDate,
      end_date: asOfIso,
    });
  });
  return periodReturns;
}

function listTopSectorsByPeriodReturn(periodReturns, count, ascending) {
  const sorted = [...periodReturns].sort((left, right) => {
    if (left.period_return !== right.period_return) {
      return ascending
        ? left.period_return - right.period_return
        : right.period_return - left.period_return;
    }
    return left.name.localeCompare(right.name);
  });
  return sorted.slice(0, count);
}

function filterHistoryPointsToPeriod(historyPoints, startDate, endDate) {
  if (!startDate) {
    return historyPoints.filter((point) => point.date <= endDate);
  }
  return historyPoints.filter(
    (point) => point.date > startDate && point.date <= endDate,
  );
}

function getHistoryWindowForPeriod(period, customStartIso) {
  const historyDates = listSortedHistoryDates(lineHistoryPoints);
  const startDate = findPeriodStartDate(
    pageAsOfDate,
    period,
    historyDates,
    customStartIso,
  );
  return {
    startDate,
    windowPoints: filterHistoryPointsToPeriod(
      lineHistoryPoints,
      startDate,
      pageAsOfDate,
    ),
  };
}

function listTopSectorsForPeriod(period, customStartIso, ascending) {
  return listTopSectorsByPeriodReturn(
    listSectorPeriodReturns(
      lineHistoryPoints,
      pageAsOfDate,
      period,
      customStartIso,
    ),
    SECTOR_PERFORMERS_COUNT,
    ascending,
  );
}

function listMergedPerformerRows(bestSectors, worstSectors) {
  // Best block: highest first (top). Worst block: best-of-worst first, then
  // down to worst-of-worst at the bottom. Labels stay sector names only.
  const worstOrdered = [...worstSectors].sort((left, right) => {
    if (left.period_return !== right.period_return) {
      return right.period_return - left.period_return;
    }
    return left.name.localeCompare(right.name);
  });
  return [
    ...bestSectors.map((sector) => ({ ...sector, group: "Best" })),
    ...worstOrdered.map((sector) => ({ ...sector, group: "Worst" })),
  ];
}

const performersBarLabelsPlugin = {
  id: "performersBarLabels",
  afterDatasetsDraw(chart) {
    const rows = chart._sectorAnalysisPerformers;
    const meta = chart.getDatasetMeta(0);
    if (!rows || !meta || !Array.isArray(meta.data)) {
      return;
    }
    const { ctx } = chart;
    ctx.save();
    ctx.fillStyle = BAR_INNER_LABEL_COLOR;
    ctx.font = "bold 12px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    meta.data.forEach((bar, index) => {
      if (!bar || bar.hidden) {
        return;
      }
      const row = rows[index];
      if (!row) {
        return;
      }
      const barLeft = Math.min(bar.x, bar.base);
      const barRight = Math.max(bar.x, bar.base);
      if (barRight - barLeft < 40) {
        return;
      }
      ctx.fillText(
        formatPieReturnLabel(row.period_return),
        (barLeft + barRight) / 2,
        bar.y,
      );
    });
    ctx.restore();
  },
};

function clearTopMoversEmptyMessage(canvas) {
  const wrap = canvas.parentElement;
  if (!wrap) {
    return;
  }
  wrap.querySelectorAll(".sector-analysis-empty").forEach((node) => node.remove());
  canvas.hidden = false;
}

function showChartEmptyMessage(canvas, message) {
  const wrap = canvas.parentElement;
  if (!wrap) {
    return;
  }
  clearTopMoversEmptyMessage(canvas);
  canvas.hidden = true;
  const empty = document.createElement("p");
  empty.className = "sector-analysis-empty";
  empty.textContent = message;
  wrap.appendChild(empty);
}

function showTopMoversEmptyMessage(canvas) {
  showChartEmptyMessage(canvas, "No equity movers stored for this subsector.");
}

function destroyChartRef(chartRefName) {
  const chart = {
    topMoversChart,
    performersBarChart,
    performersHistoryChart,
    lineChart,
  }[chartRefName];
  if (!chart) {
    return;
  }
  const chartIndex = chartInstances.indexOf(chart);
  if (chartIndex >= 0) {
    chartInstances.splice(chartIndex, 1);
  }
  chart.destroy();
  if (chartRefName === "topMoversChart") {
    topMoversChart = null;
  } else if (chartRefName === "performersBarChart") {
    performersBarChart = null;
  } else if (chartRefName === "performersHistoryChart") {
    performersHistoryChart = null;
  } else if (chartRefName === "lineChart") {
    lineChart = null;
  }
}

function renderTopMoversBarChart(canvas, topMovers) {
  destroyChartRef("topMoversChart");
  if (!topMovers || topMovers.length === 0) {
    showTopMoversEmptyMessage(canvas);
    return;
  }
  clearTopMoversEmptyMessage(canvas);
  const labels = topMovers.map((mover) => mover.company);
  // Magnitude only so bars always grow left → right; tooltip keeps the signed pp.
  const contributionMagnitudes = topMovers.map((mover) =>
    Math.abs(mover.contribution),
  );
  topMoversChart = new Chart(canvas.getContext("2d"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Contribution (pp)",
          data: contributionMagnitudes,
          backgroundColor: topMovers.map((mover) => getReturnColor(mover.daily_return)),
          borderColor: topMovers.map((mover) => getReturnColor(mover.daily_return)),
          borderWidth: 1,
          barPercentage: 0.85,
          categoryPercentage: 0.75,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      resizeDelay: 50,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label(context) {
              const mover = topMovers[context.dataIndex];
              return [
                `Contribution: ${mover.contribution.toFixed(2)} pp`,
                `Weight: ${mover.weight.toFixed(2)}%`,
                `Return: ${mover.daily_return.toFixed(2)}%`,
              ];
            },
          },
        },
      },
      scales: {
        x: {
          beginAtZero: true,
          title: { display: true, text: "Contribution (pp)" },
        },
        y: {
          ticks: { autoSkip: false },
        },
      },
    },
    plugins: [topMoversBarLabelsPlugin],
  });
  topMoversChart._sectorAnalysisTopMovers = topMovers;
  chartInstances.push(topMoversChart);
}

function renderSectorPerformersBarChart(canvas, rows) {
  destroyChartRef("performersBarChart");
  if (!rows || rows.length === 0) {
    showChartEmptyMessage(
      canvas,
      "Not enough sector history for this performers window.",
    );
    return;
  }
  clearTopMoversEmptyMessage(canvas);
  performersBarChart = new Chart(canvas.getContext("2d"), {
    type: "bar",
    data: {
      labels: rows.map((row) => row.name),
      datasets: [
        {
          label: "Period return (%)",
          data: rows.map((row) => row.period_return),
          backgroundColor: rows.map((row) => getReturnColor(row.period_return)),
          borderColor: rows.map((row) => getReturnColor(row.period_return)),
          borderWidth: 1,
          barPercentage: 0.85,
          categoryPercentage: 0.75,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      resizeDelay: 50,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label(context) {
              const row = rows[context.dataIndex];
              const lines = [
                `Period return: ${row.period_return.toFixed(2)}%`,
                `Period: ${row.start_date} / ${row.end_date}`,
              ];
              if (typeof row.weight === "number") {
                lines.push(`Weight: ${row.weight.toFixed(2)}%`);
              }
              return lines;
            },
          },
        },
      },
      scales: {
        x: {
          title: { display: true, text: "Period return (%)" },
        },
        y: {
          ticks: { autoSkip: false },
        },
      },
    },
    plugins: [performersBarLabelsPlugin],
  });
  performersBarChart._sectorAnalysisPerformers = rows;
  chartInstances.push(performersBarChart);
}

function updateTopMoversCard(subsectorDay, subsectorName, canvas) {
  selectedSubsectorName = subsectorName;
  if (topMoversTitle) {
    topMoversTitle.textContent = getTopMoversTitle(subsectorName);
  }
  const selectedSlice = subsectorDay.find((slice) => slice.name === subsectorName);
  renderTopMoversBarChart(canvas, selectedSlice ? selectedSlice.top_movers : []);
  updateSelectedSubsectorHighlight(subsectorName);
}

function updateSubsectorPie(subsectorDay, sectorName, topMoversCanvas) {
  selectedSectorName = sectorName;
  const slices = listSubsectorSlicesForSector(subsectorDay, sectorName);
  if (subsectorPieTitle) {
    subsectorPieTitle.textContent = getSubsectorPieTitle(sectorName);
  }
  updateSelectedSectorHighlight(sectorName);
  if (!subsectorPieChart) {
    return;
  }
  subsectorPieChart.data.labels = slices.map((slice) => slice.name);
  subsectorPieChart.data.datasets[0].data = slices.map((slice) => slice.weight);
  subsectorPieChart.data.datasets[0].backgroundColor = slices.map((slice) =>
    getReturnColor(slice.daily_return),
  );
  subsectorPieChart._sectorAnalysisSlices = slices;
  const defaultSubsector = getSubsectorWithBiggestContribution(slices);
  selectedSubsectorName = defaultSubsector ? defaultSubsector.name : null;
  subsectorPieChart.data.datasets[0].borderWidth = getSectorPieBorderWidths(
    slices,
    selectedSubsectorName,
  );
  subsectorPieChart.data.datasets[0].borderColor =
    getSectorPieBorderColors(slices);
  syncPieFitLayout(
    subsectorPieChart,
    slices.map((slice) => slice.name),
  );
  subsectorPieChart.update();
  updateTopMoversCard(subsectorDay, selectedSubsectorName, topMoversCanvas);
}

function renderPerformersHistoryChart(canvas, windowPoints, sectorNames, startDate) {
  destroyChartRef("performersHistoryChart");
  performersHistoryChart = new Chart(canvas.getContext("2d"), {
    type: "line",
    data: {
      labels: getPerformersHistoryChartLabels(windowPoints, startDate),
      datasets: buildIndexedLineDatasets(
        windowPoints,
        sectorNames,
        startDate,
        PERFORMERS_HISTORY_PALETTE,
      ),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      resizeDelay: 50,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          display: true,
          position: "bottom",
          labels: { boxWidth: 10, font: { size: 10 } },
        },
      },
      scales: {
        x: { ticks: { maxTicksLimit: 6 } },
        y: { title: { display: true, text: "Index (100 = window start)" } },
      },
    },
  });
  chartInstances.push(performersHistoryChart);
}

function refreshPerformersBarChart() {
  if (!performersBarCanvas) {
    return;
  }
  const bestSectors = listTopSectorsForPeriod(
    performersBarPeriod,
    performersBarCustomStart,
    false,
  );
  const worstSectors = listTopSectorsForPeriod(
    performersBarPeriod,
    performersBarCustomStart,
    true,
  );
  renderSectorPerformersBarChart(
    performersBarCanvas,
    listMergedPerformerRows(bestSectors, worstSectors),
  );
}

function refreshPerformersHistoryChart(mode) {
  performersHistoryMode = mode || performersHistoryMode;
  const bestSectors = listTopSectorsForPeriod(
    performersHistoryPeriod,
    performersHistoryCustomStart,
    false,
  );
  const worstSectors = listTopSectorsForPeriod(
    performersHistoryPeriod,
    performersHistoryCustomStart,
    true,
  );
  bestSectorNames = bestSectors.map((sector) => sector.name);
  worstSectorNames = worstSectors.map((sector) => sector.name);
  const sectorNames =
    performersHistoryMode === "worst" ? worstSectorNames : bestSectorNames;
  if (!performersHistoryCanvas) {
    return;
  }
  const { startDate, windowPoints } = getHistoryWindowForPeriod(
    performersHistoryPeriod,
    performersHistoryCustomStart,
  );
  if (!performersHistoryChart) {
    renderPerformersHistoryChart(
      performersHistoryCanvas,
      windowPoints,
      sectorNames,
      startDate,
    );
    return;
  }
  performersHistoryChart.data.labels = getPerformersHistoryChartLabels(
    windowPoints,
    startDate,
  );
  performersHistoryChart.data.datasets = buildIndexedLineDatasets(
    windowPoints,
    sectorNames,
    startDate,
    PERFORMERS_HISTORY_PALETTE,
  );
  performersHistoryChart.update();
}

function refreshHistoricalLineChart(sectorNames) {
  if (sectorNames) {
    selectedLineSectorNames = [...sectorNames];
  }
  if (!historicalLineCanvas) {
    return;
  }
  const { startDate, windowPoints } = getHistoryWindowForPeriod(
    historicalLinePeriod,
    historicalLineCustomStart,
  );
  const labels = getPerformersHistoryChartLabels(windowPoints, startDate);
  const datasets = buildIndexedLineDatasets(
    windowPoints,
    selectedLineSectorNames,
    startDate,
    HISTORICAL_LINE_PALETTE,
  );
  if (!lineChart) {
    destroyChartRef("lineChart");
    lineChart = new Chart(historicalLineCanvas.getContext("2d"), {
      type: "line",
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        resizeDelay: 50,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            display: true,
            position: "bottom",
            labels: { boxWidth: 10, font: { size: 10 } },
          },
        },
        scales: {
          x: { ticks: { maxTicksLimit: 6 } },
          y: { title: { display: true, text: "Index (100 = window start)" } },
        },
      },
    });
    chartInstances.push(lineChart);
    return;
  }
  lineChart.data.labels = labels;
  lineChart.data.datasets = datasets;
  lineChart.update();
}

function defaultPeriodStartDateValue() {
  if (!pageAsOfDate) {
    return "";
  }
  const asOfDate = parseIsoDate(pageAsOfDate);
  if (!asOfDate) {
    return "";
  }
  return formatIsoDate(shiftUtcMonths(asOfDate, -1));
}

function resolveDisplayedPeriodStart(period, customStartIso) {
  if (period === PERFORMERS_PERIOD_CUSTOM) {
    return customStartIso || defaultPeriodStartDateValue();
  }
  const startDate = findPeriodStartDate(
    pageAsOfDate,
    period,
    listSortedHistoryDates(lineHistoryPoints),
    null,
  );
  return startDate || "";
}

function createPeriodControls(activePeriod, customStart, onChange, options = {}) {
  const alwaysShowDate = Boolean(options.alwaysShowDate);
  const controls = document.createElement("div");
  controls.className = "sector-analysis-period-controls";

  const select = document.createElement("select");
  select.className = "sector-analysis-chart-select";
  select.setAttribute("aria-label", "Period");
  PERFORMERS_PERIOD_OPTIONS.forEach((option) => {
    const optionNode = document.createElement("option");
    optionNode.value = option.value;
    optionNode.textContent = option.label;
    select.appendChild(optionNode);
  });
  select.value = activePeriod;

  const dateInput = document.createElement("input");
  dateInput.type = "date";
  dateInput.className = "sector-analysis-chart-select";
  dateInput.setAttribute("aria-label", "Period start date");
  if (pageAsOfDate) {
    dateInput.max = pageAsOfDate;
  }
  // Mirror the active preset window (YTD/Week/Month) in the date field.
  dateInput.value = resolveDisplayedPeriodStart(activePeriod, customStart);
  if (!alwaysShowDate) {
    dateInput.hidden = activePeriod !== PERFORMERS_PERIOD_CUSTOM;
  }

  const emitChange = () => {
    onChange({
      period: select.value,
      customStart:
        select.value === PERFORMERS_PERIOD_CUSTOM && dateInput.value
          ? dateInput.value
          : null,
    });
  };

  select.addEventListener("change", () => {
    if (!alwaysShowDate) {
      dateInput.hidden = select.value !== PERFORMERS_PERIOD_CUSTOM;
    }
    dateInput.value = resolveDisplayedPeriodStart(select.value, dateInput.value);
    emitChange();
  });
  dateInput.addEventListener("change", () => {
    // Picking a start date selects the free Period window.
    if (select.value !== PERFORMERS_PERIOD_CUSTOM) {
      select.value = PERFORMERS_PERIOD_CUSTOM;
    }
    emitChange();
  });

  controls.appendChild(select);
  controls.appendChild(dateInput);
  return { controls, select, dateInput };
}

function renderWeightReturnPie(canvas, slices, onSliceClick, highlightName) {
  const chart = new Chart(canvas.getContext("2d"), {
    type: "doughnut",
    data: {
      labels: slices.map((slice) => slice.name),
      datasets: [
        {
          data: slices.map((slice) => slice.weight),
          backgroundColor: slices.map((slice) => getReturnColor(slice.daily_return)),
          borderWidth: highlightName
            ? getSectorPieBorderWidths(slices, highlightName)
            : 1,
          borderColor: highlightName
            ? getSectorPieBorderColors(slices)
            : "#0f172a",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      resizeDelay: 50,
      // Padding sized from full names so callouts stay on-canvas.
      radius: "100%",
      layout: {
        padding: computePieCalloutPadding(
          canvas.getContext("2d"),
          slices.map((slice) => slice.name),
        ),
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label(context) {
              const slice = chart._sectorAnalysisSlices[context.dataIndex];
              if (!slice) {
                return context.label || "";
              }
              return [
                `${slice.name}`,
                `Weight: ${slice.weight.toFixed(2)}%`,
                `Return: ${slice.daily_return.toFixed(2)}%`,
                `Contribution: ${slice.contribution.toFixed(2)} pp`,
              ];
            },
          },
        },
      },
      onHover(event, elements) {
        const target = event.native && event.native.target;
        if (target) {
          target.style.cursor = elements.length ? "pointer" : "default";
        }
      },
      onClick(_event, elements) {
        if (!onSliceClick || elements.length === 0) {
          return;
        }
        // Chart.js reports the clicked slice index in elements[0].
        const slice = chart._sectorAnalysisSlices[elements[0].index];
        if (slice) {
          onSliceClick(slice.name);
        }
      },
    },
    plugins: [sectorPieSliceLabelsPlugin],
  });
  chart._sectorAnalysisSlices = slices;
  chartInstances.push(chart);
  return chart;
}

function createChartCard(title, canvasId) {
  const card = document.createElement("article");
  card.className = "sector-analysis-card";
  const header = document.createElement("div");
  header.className = "sector-analysis-chart-header";
  const heading = document.createElement("h2");
  heading.textContent = title;
  header.appendChild(heading);
  const wrap = document.createElement("div");
  wrap.className = "sector-analysis-chart-wrap";
  const canvas = document.createElement("canvas");
  canvas.id = canvasId;
  wrap.appendChild(canvas);
  card.appendChild(header);
  card.appendChild(wrap);
  return { card, canvas, heading, wrap, header };
}

function formatLineMultiselectButtonLabel(sectorNames) {
  if (sectorNames.length === 0) {
    return "Select sectors…";
  }
  if (sectorNames.length === 1) {
    return sectorNames[0];
  }
  return `${sectorNames.length} sectors selected`;
}

function syncLineMultiselectCheckboxes(root, sectorNames) {
  const selected = new Set(sectorNames);
  root.querySelectorAll(".multiselect-checkbox-item input").forEach((checkbox) => {
    checkbox.checked = selected.has(checkbox.value);
  });
}

function syncLineMultiselectUi(sectorNames) {
  const root = document.querySelector(
    ".sector-analysis-header-controls .multiselect-dropdown-wrapper",
  );
  if (!root) {
    return;
  }
  const button = root.querySelector(".multiselect-dropdown-button");
  if (button) {
    button.textContent = formatLineMultiselectButtonLabel(sectorNames);
  }
  syncLineMultiselectCheckboxes(root, sectorNames);
}

function selectLineChartSector(sectorName) {
  pendingLineSectorNames = [sectorName];
  refreshHistoricalLineChart([sectorName]);
  syncLineMultiselectUi([sectorName]);
}

function createLineSectorMultiselect(sectorNames, defaultSelectedNames) {
  // Same markup / classes as economic_charts multiselect controls.
  const wrapper = document.createElement("div");
  wrapper.className = "multiselect-dropdown-wrapper";

  const button = document.createElement("button");
  button.type = "button";
  button.className = "multiselect-dropdown-button";
  button.textContent = formatLineMultiselectButtonLabel(defaultSelectedNames);

  const dropdown = document.createElement("div");
  dropdown.className = "multiselect-dropdown-content";
  dropdown.style.display = "none";

  const actions = document.createElement("div");
  actions.className = "multiselect-action-buttons";
  const selectAllBtn = document.createElement("button");
  selectAllBtn.type = "button";
  selectAllBtn.className = "multiselect-action-btn";
  selectAllBtn.textContent = "Select All";
  const unselectAllBtn = document.createElement("button");
  unselectAllBtn.type = "button";
  unselectAllBtn.className = "multiselect-action-btn";
  unselectAllBtn.textContent = "Unselect All";
  actions.appendChild(selectAllBtn);
  actions.appendChild(unselectAllBtn);
  dropdown.appendChild(actions);

  const options = document.createElement("div");
  options.className = "multiselect-checkbox-list";
  sectorNames.forEach((sectorName, index) => {
    const option = document.createElement("div");
    option.className = "multiselect-checkbox-item";
    const checkboxId = `sector-line-multiselect-${index}`;
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = checkboxId;
    checkbox.value = sectorName;
    checkbox.checked = defaultSelectedNames.includes(sectorName);
    const label = document.createElement("label");
    label.htmlFor = checkboxId;
    label.textContent = sectorName;
    option.appendChild(checkbox);
    option.appendChild(label);
    options.appendChild(option);
  });
  dropdown.appendChild(options);

  const validation = document.createElement("div");
  validation.className = "multiselect-validation-buttons";
  const applyBtn = document.createElement("button");
  applyBtn.type = "button";
  applyBtn.className = "multiselect-apply-btn";
  applyBtn.textContent = "Apply";
  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "multiselect-cancel-btn";
  cancelBtn.textContent = "Cancel";
  validation.appendChild(applyBtn);
  validation.appendChild(cancelBtn);
  dropdown.appendChild(validation);

  function closeDropdown() {
    dropdown.style.display = "none";
    button.classList.remove("active");
  }

  function openDropdown() {
    pendingLineSectorNames = [...selectedLineSectorNames];
    syncLineMultiselectCheckboxes(wrapper, pendingLineSectorNames);
    dropdown.style.display = "block";
    button.classList.add("active");
  }

  button.addEventListener("click", (event) => {
    event.stopPropagation();
    if (dropdown.style.display === "block") {
      closeDropdown();
    } else {
      openDropdown();
    }
  });

  selectAllBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    pendingLineSectorNames = [...sectorNames];
    syncLineMultiselectCheckboxes(wrapper, pendingLineSectorNames);
  });

  unselectAllBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    pendingLineSectorNames = [];
    syncLineMultiselectCheckboxes(wrapper, pendingLineSectorNames);
  });

  options.addEventListener("change", () => {
    pendingLineSectorNames = Array.from(
      options.querySelectorAll("input:checked"),
    ).map((checkbox) => checkbox.value);
  });

  applyBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    refreshHistoricalLineChart(pendingLineSectorNames);
    button.textContent = formatLineMultiselectButtonLabel(selectedLineSectorNames);
    closeDropdown();
  });

  cancelBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    closeDropdown();
  });

  document.addEventListener("click", (event) => {
    if (!wrapper.contains(event.target)) {
      closeDropdown();
    }
  });

  wrapper.appendChild(button);
  wrapper.appendChild(dropdown);
  return wrapper;
}

function createHeaderControlsRow(...children) {
  const row = document.createElement("div");
  row.className = "sector-analysis-header-controls";
  children.forEach((child) => {
    if (child) {
      row.appendChild(child);
    }
  });
  return row;
}

function createLineChartCard(title, canvasId, sectorNames, defaultSelectedNames) {
  const cardParts = createChartCard(title, canvasId);
  const multiselect = createLineSectorMultiselect(sectorNames, defaultSelectedNames);
  const periodControls = createPeriodControls(
    historicalLinePeriod,
    historicalLineCustomStart,
    ({ period, customStart }) => {
      historicalLinePeriod = period;
      historicalLineCustomStart = customStart;
      refreshHistoricalLineChart();
    },
  );
  cardParts.header.appendChild(
    createHeaderControlsRow(multiselect, periodControls.controls),
  );
  return { ...cardParts, multiselect, periodControls };
}

function createPerformersBarCard() {
  const cardParts = createChartCard(
    "Top 3 Best / Worst Sectors",
    "performers-bar",
  );
  const periodControls = createPeriodControls(
    performersBarPeriod,
    performersBarCustomStart,
    ({ period, customStart }) => {
      performersBarPeriod = period;
      performersBarCustomStart = customStart;
      refreshPerformersBarChart();
    },
    { alwaysShowDate: true },
  );
  cardParts.header.appendChild(createHeaderControlsRow(periodControls.controls));
  return { ...cardParts, periodControls };
}

function createPerformersHistoryCard() {
  const cardParts = createChartCard(
    "Best / Worst Performers Trend",
    "performers-history-line",
  );
  const modeSelect = document.createElement("select");
  modeSelect.className = "sector-analysis-chart-select";
  modeSelect.setAttribute("aria-label", "Best or worst performers");
  [
    { value: "best", label: "Best" },
    { value: "worst", label: "Worst" },
  ].forEach((option) => {
    const optionNode = document.createElement("option");
    optionNode.value = option.value;
    optionNode.textContent = option.label;
    modeSelect.appendChild(optionNode);
  });
  modeSelect.value = performersHistoryMode;
  modeSelect.addEventListener("change", () => {
    refreshPerformersHistoryChart(modeSelect.value);
  });
  const periodControls = createPeriodControls(
    performersHistoryPeriod,
    performersHistoryCustomStart,
    ({ period, customStart }) => {
      performersHistoryPeriod = period;
      performersHistoryCustomStart = customStart;
      refreshPerformersHistoryChart();
    },
    { alwaysShowDate: true },
  );
  cardParts.header.appendChild(
    createHeaderControlsRow(modeSelect, periodControls.controls),
  );
  return { ...cardParts, modeSelect, periodControls };
}

function getPageSubtitle(pageData) {
  const locationLabel =
    LOCATION_LABEL_BY_CODE[pageData.location] || pageData.location;
  const indexLabel =
    INDEX_LABEL_BY_CODE[pageData.equity_index] || pageData.equity_index;
  const asOfLabel = pageData.as_of ? `As of ${pageData.as_of}` : "No data yet";
  return `${locationLabel} · ${indexLabel} · ${asOfLabel}`;
}

const EARNINGS_CURRENCY_BY_LOCATION = {
  US: "$",
  FR: "€",
  JP: "¥",
};

const EARNINGS_AMOUNT_MAGNITUDES = ["", "k", "m", "b", "t"];
const EARNINGS_COLLAPSED_VISIBLE_COUNT = 3;

const EARNINGS_IDENTITY_COLUMNS = [
  { key: "company", label: "Name", type: "string" },
  { key: "weight_pct", label: "Weight", type: "number" },
];

const EARNINGS_UPCOMING_COLUMNS = [
  { key: "next_call", label: "Next Call", type: "date" },
  { key: "next_eps_expected", label: "Exp. EPS", type: "number" },
  { key: "next_revenue_expected", label: "Exp. Revenue", type: "number" },
];

const EARNINGS_PAST_COLUMNS = [
  { key: "past_period", label: "Period", type: "date" },
  { key: "past_eps", label: "EPS", type: "number" },
  { key: "past_revenue", label: "Revenue", type: "number" },
  { key: "past_operating_income", label: "Op. Income", type: "number" },
  { key: "past_gross_profit", label: "Gross Profit", type: "number" },
  { key: "past_ebitda", label: "EBITDA", type: "number" },
];

const EARNINGS_TABLE_COLUMNS = [
  ...EARNINGS_IDENTITY_COLUMNS,
  ...EARNINGS_UPCOMING_COLUMNS,
  ...EARNINGS_PAST_COLUMNS,
];

/** Next scheduled print (call date + street estimates). */
function getEarningsUpcomingInformation(company) {
  return company.upcoming || {};
}

/** Latest reported results shown in the Past group. */
function getEarningsCurrentInformation(company) {
  return company.current || {};
}

/** Print before the latest, used for Past change baselines. */
function getEarningsPreviousInformation(company) {
  return company.previous || {};
}

function formatEarningsSpacedNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  const number = Number(value);
  const sign = number < 0 ? "-" : "";
  const [intPart, decPart] = Math.abs(number).toFixed(digits).split(".");
  const spacedInt = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return `${sign}${spacedInt}.${decPart}`;
}

function formatEarningsWeight(weightPct) {
  if (weightPct === null || weightPct === undefined || Number.isNaN(Number(weightPct))) {
    return "—";
  }
  return `${formatEarningsSpacedNumber(weightPct, 2)}%`;
}

function formatEarningsPeriodLabel(isoDate) {
  if (!isoDate) {
    return "—";
  }
  const periodEnd = new Date(`${isoDate}T00:00:00Z`);
  if (Number.isNaN(periodEnd.getTime())) {
    return "—";
  }
  const quarter = Math.floor(periodEnd.getUTCMonth() / 3) + 1;
  const yearShort = periodEnd.getUTCFullYear() % 100;
  return `${String(yearShort).padStart(2, "0")}Q${quarter}`;
}

function formatEarningsPeriodWindow(previousIsoDate, currentIsoDate) {
  const previousLabel = formatEarningsPeriodLabel(previousIsoDate);
  const currentLabel = formatEarningsPeriodLabel(currentIsoDate);
  if (previousLabel === "—" && currentLabel === "—") {
    return "—";
  }
  if (previousLabel === "—") {
    return currentLabel;
  }
  if (currentLabel === "—") {
    return previousLabel;
  }
  return `${previousLabel} → ${currentLabel}`;
}

function formatEarningsAnnouncement(isoDatetime) {
  if (!isoDatetime) {
    return "—";
  }
  const announcementDate = new Date(isoDatetime);
  if (Number.isNaN(announcementDate.getTime())) {
    return "—";
  }
  return announcementDate.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function getEarningsAmountScale(value) {
  let scaled = Math.abs(Number(value));
  let magnitudeIndex = 0;
  while (scaled > 999 && magnitudeIndex < EARNINGS_AMOUNT_MAGNITUDES.length - 1) {
    scaled /= 1000;
    magnitudeIndex += 1;
  }
  return { scaled, magnitudeIndex };
}

function formatEarningsAmount(value, currencySymbol) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  const { scaled, magnitudeIndex } = getEarningsAmountScale(value);
  const signedScaled = Number(value) < 0 ? -scaled : scaled;
  const magnitudeLabel = EARNINGS_AMOUNT_MAGNITUDES[magnitudeIndex];
  const unitLabel = magnitudeLabel
    ? `${magnitudeLabel}${currencySymbol}`
    : currencySymbol;
  return `${formatEarningsSpacedNumber(signedScaled, 2)} ${unitLabel}`;
}

function getEarningsAbsoluteChange(actual, baseline) {
  if (
    actual === null ||
    actual === undefined ||
    baseline === null ||
    baseline === undefined ||
    Number.isNaN(Number(actual)) ||
    Number.isNaN(Number(baseline))
  ) {
    return null;
  }
  return Number(actual) - Number(baseline);
}

function getEarningsPercentChange(actual, baseline) {
  if (
    actual === null ||
    actual === undefined ||
    baseline === null ||
    baseline === undefined ||
    Number.isNaN(Number(actual)) ||
    Number.isNaN(Number(baseline)) ||
    Number(baseline) === 0
  ) {
    return null;
  }
  return ((Number(actual) - Number(baseline)) / Math.abs(Number(baseline))) * 100;
}

function getEarningsChangeClass(changeValue) {
  if (changeValue === null || changeValue === undefined) {
    return "";
  }
  if (changeValue > 0) {
    return "earnings-change-positive";
  }
  if (changeValue < 0) {
    return "earnings-change-negative";
  }
  return "earnings-change-unchanged";
}

function formatEarningsAbsoluteChangeLabel(absoluteChange) {
  if (absoluteChange === null || absoluteChange === undefined) {
    return "—";
  }
  if (absoluteChange === 0) {
    return "0.00";
  }
  const prefix = absoluteChange > 0 ? "+" : "";
  return `${prefix}${formatEarningsSpacedNumber(absoluteChange, 2)}`;
}

function formatEarningsPercentChangeLabel(percentChange) {
  if (percentChange === null || percentChange === undefined) {
    return "—";
  }
  if (percentChange === 0) {
    return "0.00%";
  }
  const prefix = percentChange > 0 ? "+" : "";
  return `${prefix}${formatEarningsSpacedNumber(percentChange, 2)}%`;
}

function formatEarningsChangeParenthesisHtml(changeValue, label) {
  const changeClass = getEarningsChangeClass(changeValue);
  if (!changeClass) {
    return ` <span class="earnings-change">(${label})</span>`;
  }
  return ` <span class="earnings-change ${changeClass}">(${label})</span>`;
}

function formatEarningsEpsExpectedHtml(upcomingInformation, currentInformation) {
  if (
    !upcomingInformation ||
    upcomingInformation.eps_expected === null ||
    upcomingInformation.eps_expected === undefined
  ) {
    return "—";
  }
  const expectedText = formatEarningsSpacedNumber(upcomingInformation.eps_expected, 2);
  const absoluteChange = getEarningsAbsoluteChange(
    upcomingInformation.eps_expected,
    currentInformation ? currentInformation.eps : null,
  );
  return `${expectedText}${formatEarningsChangeParenthesisHtml(
    absoluteChange,
    formatEarningsAbsoluteChangeLabel(absoluteChange),
  )}`;
}

function formatEarningsRevenueExpectedHtml(upcomingInformation, currentInformation, currencySymbol) {
  if (
    !upcomingInformation ||
    upcomingInformation.revenue_expected === null ||
    upcomingInformation.revenue_expected === undefined
  ) {
    return "—";
  }
  const expectedText = formatEarningsAmount(
    upcomingInformation.revenue_expected,
    currencySymbol,
  );
  const percentChange = getEarningsPercentChange(
    upcomingInformation.revenue_expected,
    currentInformation ? currentInformation.revenue : null,
  );
  return `${expectedText}${formatEarningsChangeParenthesisHtml(
    percentChange,
    formatEarningsPercentChangeLabel(percentChange),
  )}`;
}

function formatEarningsActExpChangeHtml(
  actualText,
  expectedText,
  changeValue,
  changeLabel,
) {
  return `${actualText} / ${expectedText}${formatEarningsChangeParenthesisHtml(
    changeValue,
    changeLabel,
  )}`;
}

function formatEarningsEpsActExpHtml(actualInformation) {
  const actualValue = actualInformation ? actualInformation.eps : null;
  const expectedValue = actualInformation ? actualInformation.eps_expected : null;
  if (
    (actualValue === null || actualValue === undefined) &&
    (expectedValue === null || expectedValue === undefined)
  ) {
    return "—";
  }
  const actual =
    actualValue === null || actualValue === undefined
      ? "—"
      : formatEarningsSpacedNumber(actualValue, 2);
  const expected =
    expectedValue === null || expectedValue === undefined
      ? "—"
      : formatEarningsSpacedNumber(expectedValue, 2);
  const absoluteChange = getEarningsAbsoluteChange(actualValue, expectedValue);
  return formatEarningsActExpChangeHtml(
    actual,
    expected,
    absoluteChange,
    formatEarningsAbsoluteChangeLabel(absoluteChange),
  );
}

function formatEarningsRevenueActExpChangeHtml(actualInformation, currencySymbol) {
  const actualValue = actualInformation ? actualInformation.revenue : null;
  const expectedValue = actualInformation ? actualInformation.revenue_expected : null;
  if (
    (actualValue === null || actualValue === undefined) &&
    (expectedValue === null || expectedValue === undefined)
  ) {
    return "—";
  }
  const percentChange = getEarningsPercentChange(actualValue, expectedValue);
  return formatEarningsActExpChangeHtml(
    formatEarningsAmount(actualValue, currencySymbol),
    formatEarningsAmount(expectedValue, currencySymbol),
    percentChange,
    formatEarningsPercentChangeLabel(percentChange),
  );
}

function formatEarningsAmountActChangeHtml(actual, prior, currencySymbol) {
  const percentChange = getEarningsPercentChange(actual, prior);
  return `${formatEarningsAmount(actual, currencySymbol)}${formatEarningsChangeParenthesisHtml(
    percentChange,
    formatEarningsPercentChangeLabel(percentChange),
  )}`;
}

function getEarningsSortValue(company, columnKey) {
  const upcomingInformation = getEarningsUpcomingInformation(company);
  const currentInformation = getEarningsCurrentInformation(company);
  const previousInformation = getEarningsPreviousInformation(company);
  switch (columnKey) {
  case "company":
    return company.company || "";
  case "weight_pct":
    return company.weight_pct;
  case "next_call":
    return upcomingInformation.announcement_datetime || "";
  case "next_eps_expected":
    return upcomingInformation.eps_expected;
  case "next_revenue_expected":
    return upcomingInformation.revenue_expected;
  case "past_period":
    return (
      currentInformation.reporting_period_end ||
      previousInformation.reporting_period_end ||
      ""
    );
  case "past_eps":
    return currentInformation.eps != null
      ? currentInformation.eps
      : currentInformation.eps_expected;
  case "past_revenue":
    return currentInformation.revenue;
  case "past_operating_income":
    return currentInformation.operating_income;
  case "past_gross_profit":
    return currentInformation.gross_profit;
  case "past_ebitda":
    return currentInformation.ebitda;
  default:
    return null;
  }
}

function compareEarningsSortValues(leftValue, rightValue, columnType, direction) {
  const leftMissing = leftValue === null || leftValue === undefined || leftValue === "";
  const rightMissing =
    rightValue === null || rightValue === undefined || rightValue === "";
  if (leftMissing && rightMissing) {
    return 0;
  }
  if (leftMissing) {
    return 1;
  }
  if (rightMissing) {
    return -1;
  }
  let comparison = 0;
  if (columnType === "number") {
    comparison = Number(leftValue) - Number(rightValue);
  } else if (columnType === "date") {
    comparison = String(leftValue).localeCompare(String(rightValue));
  } else {
    comparison = String(leftValue).localeCompare(String(rightValue), undefined, {
      sensitivity: "base",
    });
  }
  return direction === "desc" ? -comparison : comparison;
}

function sortEarningsCompanies(companies, columnKey, direction) {
  const column = EARNINGS_TABLE_COLUMNS.find((entry) => entry.key === columnKey);
  const columnType = column ? column.type : "string";
  return [...companies].sort((leftCompany, rightCompany) =>
    compareEarningsSortValues(
      getEarningsSortValue(leftCompany, columnKey),
      getEarningsSortValue(rightCompany, columnKey),
      columnType,
      direction,
    ),
  );
}

function renderEarningsTableBody(tbody, companies, currencySymbol) {
  tbody.replaceChildren();
  companies.forEach((company) => {
    const upcomingInformation = getEarningsUpcomingInformation(company);
    const currentInformation = getEarningsCurrentInformation(company);
    const previousInformation = getEarningsPreviousInformation(company);
    const row = document.createElement("tr");
    const cells = [
      { html: company.company, className: "", isHtml: false },
      { html: formatEarningsWeight(company.weight_pct), className: "", isHtml: false },
      {
        html: formatEarningsAnnouncement(upcomingInformation.announcement_datetime),
        className: "sector-analysis-earnings-group-start",
        isHtml: false,
      },
      {
        html: formatEarningsEpsExpectedHtml(upcomingInformation, currentInformation),
        className: "",
        isHtml: true,
      },
      {
        html: formatEarningsRevenueExpectedHtml(
          upcomingInformation,
          currentInformation,
          currencySymbol,
        ),
        className: "",
        isHtml: true,
      },
      {
        html: formatEarningsPeriodWindow(
          previousInformation.reporting_period_end,
          currentInformation.reporting_period_end,
        ),
        className: "sector-analysis-earnings-group-start",
        isHtml: false,
      },
      {
        html: formatEarningsEpsActExpHtml(currentInformation),
        className: "",
        isHtml: true,
      },
      {
        html: formatEarningsRevenueActExpChangeHtml(currentInformation, currencySymbol),
        className: "",
        isHtml: true,
      },
      {
        html: formatEarningsAmountActChangeHtml(
          currentInformation.operating_income,
          previousInformation.operating_income,
          currencySymbol,
        ),
        className: "",
        isHtml: true,
      },
      {
        html: formatEarningsAmountActChangeHtml(
          currentInformation.gross_profit,
          previousInformation.gross_profit,
          currencySymbol,
        ),
        className: "",
        isHtml: true,
      },
      {
        html: formatEarningsAmountActChangeHtml(
          currentInformation.ebitda,
          previousInformation.ebitda,
          currencySymbol,
        ),
        className: "",
        isHtml: true,
      },
    ];
    cells.forEach((cell) => {
      const tableCell = document.createElement("td");
      if (cell.className) {
        tableCell.className = cell.className;
      }
      if (cell.isHtml) {
        tableCell.innerHTML = cell.html;
      } else {
        tableCell.textContent = cell.html;
      }
      row.appendChild(tableCell);
    });
    tbody.appendChild(row);
  });
}

function updateEarningsSortHeaders(headerCells, sortKey, sortDirection) {
  headerCells.forEach((headerCell) => {
    const columnKey = headerCell.dataset.sortKey;
    headerCell.classList.remove("is-sorted-asc", "is-sorted-desc");
    headerCell.setAttribute("aria-sort", "none");
    if (columnKey !== sortKey) {
      return;
    }
    headerCell.classList.add(
      sortDirection === "asc" ? "is-sorted-asc" : "is-sorted-desc",
    );
    headerCell.setAttribute(
      "aria-sort",
      sortDirection === "asc" ? "ascending" : "descending",
    );
  });
}

function createEarningsSortableHeader(column, onSort, extraClassName = "") {
  const headerCell = document.createElement("th");
  headerCell.dataset.sortKey = column.key;
  headerCell.scope = "col";
  headerCell.tabIndex = 0;
  headerCell.className = ["sector-analysis-earnings-sortable", extraClassName]
    .filter(Boolean)
    .join(" ");
  headerCell.innerHTML = `<span>${column.label}</span><span class="sector-analysis-earnings-sort-indicator" aria-hidden="true"></span>`;
  headerCell.addEventListener("click", () => onSort(column.key));
  headerCell.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }
    event.preventDefault();
    headerCell.click();
  });
  return headerCell;
}

function getEarningsVisibleCompanies(companies, isExpanded) {
  if (isExpanded || companies.length <= EARNINGS_COLLAPSED_VISIBLE_COUNT) {
    return companies;
  }
  return companies.slice(0, EARNINGS_COLLAPSED_VISIBLE_COUNT);
}

function createEarningsCard(pageData) {
  const card = document.createElement("article");
  card.className = "sector-analysis-card sector-analysis-earnings-card";
  const heading = document.createElement("h2");
  heading.textContent = "Earnings Table";
  card.appendChild(heading);
  const note = document.createElement("p");
  note.className = "sector-analysis-earnings-note";
  note.textContent =
    "Independent of Target Date — As of / date selection above does not change this earnings view. " +
    "In Past cells, the number after “/” is the expectation and the number in parentheses is the change.";
  card.appendChild(note);

  const companies = pageData.earnings_card || [];
  if (companies.length === 0) {
    const empty = document.createElement("p");
    empty.className = "sector-analysis-empty";
    empty.textContent =
      "No earnings watchlist rows yet. Run earnings ingest or refresh.";
    card.appendChild(empty);
    return card;
  }

  const currencySymbol = EARNINGS_CURRENCY_BY_LOCATION[pageData.location] || "$";
  let sortKey = "next_call";
  let sortDirection = "asc";
  let isExpanded = false;
  let sortedCompanies = sortEarningsCompanies(companies, sortKey, sortDirection);

  const tableWrap = document.createElement("div");
  tableWrap.className = "sector-analysis-earnings-table-wrap";
  const table = document.createElement("table");
  table.className = "sector-analysis-earnings-table";
  const thead = document.createElement("thead");

  const groupRow = document.createElement("tr");
  const identityGroup = document.createElement("th");
  identityGroup.colSpan = EARNINGS_IDENTITY_COLUMNS.length;
  identityGroup.scope = "colgroup";
  identityGroup.className =
    "sector-analysis-earnings-group-header sector-analysis-earnings-group-company";
  identityGroup.textContent = "Company";
  const upcomingGroup = document.createElement("th");
  upcomingGroup.colSpan = EARNINGS_UPCOMING_COLUMNS.length;
  upcomingGroup.scope = "colgroup";
  upcomingGroup.className =
    "sector-analysis-earnings-group-header sector-analysis-earnings-group-upcoming sector-analysis-earnings-group-start";
  upcomingGroup.textContent = "Upcoming";
  const pastGroup = document.createElement("th");
  pastGroup.colSpan = EARNINGS_PAST_COLUMNS.length;
  pastGroup.scope = "colgroup";
  pastGroup.className =
    "sector-analysis-earnings-group-header sector-analysis-earnings-group-past sector-analysis-earnings-group-start";
  pastGroup.textContent = "Past";
  groupRow.appendChild(identityGroup);
  groupRow.appendChild(upcomingGroup);
  groupRow.appendChild(pastGroup);

  const headerRow = document.createElement("tr");
  const headerCells = [];
  const tbody = document.createElement("tbody");
  const refreshEarningsTableBody = () => {
    renderEarningsTableBody(
      tbody,
      getEarningsVisibleCompanies(sortedCompanies, isExpanded),
      currencySymbol,
    );
    card.setAttribute(
      "aria-expanded",
      sortedCompanies.length <= EARNINGS_COLLAPSED_VISIBLE_COUNT || isExpanded
        ? "true"
        : "false",
    );
  };
  const onSort = (columnKey) => {
    if (sortKey === columnKey) {
      sortDirection = sortDirection === "asc" ? "desc" : "asc";
    } else {
      sortKey = columnKey;
      sortDirection = "asc";
    }
    sortedCompanies = sortEarningsCompanies(companies, sortKey, sortDirection);
    updateEarningsSortHeaders(headerCells, sortKey, sortDirection);
    refreshEarningsTableBody();
  };
  const appendSortableColumns = (columns, groupStartKey) => {
    columns.forEach((column) => {
      const extraClassName =
        column.key === groupStartKey ? "sector-analysis-earnings-group-start" : "";
      const headerCell = createEarningsSortableHeader(
        column,
        onSort,
        extraClassName,
      );
      headerCells.push(headerCell);
      headerRow.appendChild(headerCell);
    });
  };
  appendSortableColumns(EARNINGS_IDENTITY_COLUMNS, "");
  appendSortableColumns(EARNINGS_UPCOMING_COLUMNS, "next_call");
  appendSortableColumns(EARNINGS_PAST_COLUMNS, "past_period");

  thead.appendChild(groupRow);
  thead.appendChild(headerRow);
  table.appendChild(thead);
  table.appendChild(tbody);
  tableWrap.appendChild(table);
  card.appendChild(tableWrap);

  // Same pattern as daily recap: click anywhere on the card toggles expand,
  // except sortable column headers (and only when there are rows to reveal).
  card.addEventListener("click", (event) => {
    if (sortedCompanies.length <= EARNINGS_COLLAPSED_VISIBLE_COUNT) {
      return;
    }
    if (event.target.closest(".sector-analysis-earnings-sortable")) {
      return;
    }
    isExpanded = !isExpanded;
    refreshEarningsTableBody();
  });

  updateEarningsSortHeaders(headerCells, sortKey, sortDirection);
  refreshEarningsTableBody();
  return card;
}

function renderEmptyPage(root, pageData) {
  const emptyCard = document.createElement("article");
  emptyCard.className = "sector-analysis-card sector-analysis-empty-card";
  const heading = document.createElement("h2");
  heading.textContent = getPageSubtitle(pageData);
  const empty = document.createElement("p");
  empty.className = "sector-analysis-empty";
  empty.textContent =
    "No sector moves stored for this date. Run ingestion or pick another date.";
  emptyCard.appendChild(heading);
  emptyCard.appendChild(empty);
  root.appendChild(createEarningsCard(pageData));
  root.appendChild(emptyCard);
}

function renderPage(pageData) {
  const root = document.getElementById("sector-analysis-root");
  root.replaceChildren();
  chartInstances.length = 0;
  performersHistoryChart = null;
  performersBarChart = null;
  lineChart = null;
  sectorPieChart = null;
  subsectorPieChart = null;
  topMoversChart = null;
  subsectorPieTitle = null;
  topMoversTitle = null;
  performersBarCanvas = null;
  performersHistoryCanvas = null;
  historicalLineCanvas = null;
  selectedSectorName = pageData.selected_sector;
  selectedSubsectorName = pageData.selected_subsector;
  lineHistoryPoints = pageData.sector_history || [];
  pageAsOfDate = pageData.as_of;
  sectorDayByName = Object.fromEntries(
    (pageData.sector_day || []).map((slice) => [slice.name, slice]),
  );
  performersHistoryMode = "best";
  performersBarPeriod = PERFORMERS_PERIOD_YTD;
  performersBarCustomStart = null;
  performersHistoryPeriod = PERFORMERS_PERIOD_YTD;
  performersHistoryCustomStart = null;
  historicalLinePeriod = PERFORMERS_PERIOD_YTD;
  historicalLineCustomStart = null;
  const availableSectorNames = listSectorNames(lineHistoryPoints);
  selectedLineSectorNames =
    selectedSectorName && availableSectorNames.includes(selectedSectorName)
      ? [selectedSectorName]
      : availableSectorNames.slice(0, 1);
  pendingLineSectorNames = [...selectedLineSectorNames];

  if (!pageData.sector_day || pageData.sector_day.length === 0) {
    renderEmptyPage(root, pageData);
    return;
  }

  const cards = document.createElement("div");
  cards.className = "sector-analysis-cards";
  const sectorPie = createChartCard("Sector Day Move", "sector-pie");
  const subsectorPie = createChartCard(
    getSubsectorPieTitle(selectedSectorName),
    "subsector-pie",
  );
  const topMovers = createChartCard(
    getTopMoversTitle(selectedSubsectorName),
    "top-movers-bar",
  );
  const performersBar = createPerformersBarCard();
  const performersHistory = createPerformersHistoryCard();
  const line = createLineChartCard(
    "Historical Sector Performance",
    "sector-line",
    availableSectorNames,
    selectedLineSectorNames,
  );
  subsectorPieTitle = subsectorPie.heading;
  topMoversTitle = topMovers.heading;
  performersBarCanvas = performersBar.canvas;
  performersHistoryCanvas = performersHistory.canvas;
  historicalLineCanvas = line.canvas;

  // Row 1: sector | subsector
  // Row 2: top equities | historical sector performance
  // Row 3: best/worst bars | best/worst index
  cards.appendChild(sectorPie.card);
  cards.appendChild(subsectorPie.card);
  cards.appendChild(topMovers.card);
  cards.appendChild(line.card);
  cards.appendChild(performersBar.card);
  cards.appendChild(performersHistory.card);
  root.appendChild(createEarningsCard(pageData));
  root.appendChild(cards);

  const initialSubsectorSlices = listSubsectorSlicesForSector(
    pageData.subsector_day,
    selectedSectorName,
  );
  sectorPieChart = renderWeightReturnPie(
    sectorPie.canvas,
    pageData.sector_day,
    (sectorName) => {
      updateSubsectorPie(pageData.subsector_day, sectorName, topMovers.canvas);
      selectLineChartSector(sectorName);
    },
    selectedSectorName,
  );
  subsectorPieChart = renderWeightReturnPie(
    subsectorPie.canvas,
    initialSubsectorSlices,
    (subsectorName) => {
      updateTopMoversCard(pageData.subsector_day, subsectorName, topMovers.canvas);
    },
    selectedSubsectorName,
  );
  updateTopMoversCard(pageData.subsector_day, selectedSubsectorName, topMovers.canvas);
  refreshPerformersBarChart();
  refreshPerformersHistoryChart();
  refreshHistoricalLineChart();
}

function initializeRegionButtons() {
  document.querySelectorAll(".region-btn").forEach((button) => {
    button.addEventListener("click", function onRegionClick() {
      const region = this.getAttribute("data-region");
      const params = new URLSearchParams(window.location.search);
      params.set("region", region);
      window.location.search = params.toString();
    });
  });
}

function initializeLastButton() {
  const lastBtn = document.getElementById("lastBtn");
  if (!lastBtn || !window.defaultReferenceDate) {
    return;
  }
  lastBtn.addEventListener("click", function onLastClick() {
    const referenceDateInput = document.getElementById("reference_date");
    const form = document.getElementById("sector-analysis-date-form");
    if (referenceDateInput && form) {
      referenceDateInput.value = window.defaultReferenceDate;
      form.submit();
    }
  });
}

initializeRegionButtons();
initializeLastButton();
renderPage(SECTOR_ANALYSIS_DATA);
