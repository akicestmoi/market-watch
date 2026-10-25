/**
 * Comparison-period presets for recap date forms.
 * Frontend-only: fills Target / Previous date inputs then submits the GET form.
 * Business days follow weekday calendar (Mon–Fri), matching pandas BDay.
 */
(function (global) {
  function parseISODate(iso) {
    const [year, month, day] = iso.split('-').map(Number);
    return new Date(year, month - 1, day);
  }

  function formatISODate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  function isWeekday(date) {
    const day = date.getDay();
    return day !== 0 && day !== 6;
  }

  function addBusinessDays(from, count) {
    const result = new Date(from.getFullYear(), from.getMonth(), from.getDate());
    const step = count < 0 ? -1 : 1;
    let remaining = Math.abs(count);
    while (remaining > 0) {
      result.setDate(result.getDate() + step);
      if (isWeekday(result)) {
        remaining -= 1;
      }
    }
    return result;
  }

  function lastBusinessDayOnOrBefore(date) {
    const result = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    while (!isWeekday(result)) {
      result.setDate(result.getDate() - 1);
    }
    return result;
  }

  function shiftCalendarMonths(date, months) {
    const year = date.getFullYear();
    const month = date.getMonth() + months;
    const day = date.getDate();
    const lastDayOfTargetMonth = new Date(year, month + 1, 0).getDate();
    return new Date(year, month, Math.min(day, lastDayOfTargetMonth));
  }

  function shiftCalendarYears(date, years) {
    const year = date.getFullYear() + years;
    const month = date.getMonth();
    const day = date.getDate();
    const lastDayOfTargetMonth = new Date(year, month + 1, 0).getDate();
    return new Date(year, month, Math.min(day, lastDayOfTargetMonth));
  }

  function resolveTargetDate() {
    if (global.defaultReferenceDate) {
      return parseISODate(global.defaultReferenceDate);
    }
    return addBusinessDays(new Date(), -1);
  }

  /**
   * @param {'day'|'week'|'month'|'year'} period
   * @returns {{ referenceDate: string, previousDate: string } | null}
   */
  function computeComparisonDates(period) {
    const target = resolveTargetDate();
    let previous;

    switch (period) {
      case 'day':
        if (global.defaultPreviousDate) {
          previous = parseISODate(global.defaultPreviousDate);
        } else {
          previous = addBusinessDays(target, -1);
        }
        break;
      case 'week':
        previous = new Date(
          target.getFullYear(),
          target.getMonth(),
          target.getDate() - 7
        );
        break;
      case 'month':
        previous = lastBusinessDayOnOrBefore(shiftCalendarMonths(target, -1));
        break;
      case 'year':
        previous = lastBusinessDayOnOrBefore(shiftCalendarYears(target, -1));
        break;
      default:
        return null;
    }

    return {
      referenceDate: formatISODate(target),
      previousDate: formatISODate(previous),
    };
  }

  /**
   * True when previous is exactly one business day before reference (day comparison).
   * @param {string} referenceIso
   * @param {string} previousIso
   * @returns {boolean}
   */
  function isDayOverDayComparison(referenceIso, previousIso) {
    if (!referenceIso || !previousIso) {
      return false;
    }
    const reference = parseISODate(referenceIso);
    const expectedPrevious = addBusinessDays(reference, -1);
    return formatISODate(expectedPrevious) === previousIso;
  }

  /**
   * @param {{ formSelector?: string, selectId?: string }} [options]
   */
  function initializeComparisonPeriodSelect(options) {
    const opts = options || {};
    const select = document.getElementById(opts.selectId || 'comparisonPeriod');
    if (!select) {
      return;
    }

    select.addEventListener('change', function () {
      const period = select.value;
      if (!period) {
        return;
      }

      const dates = computeComparisonDates(period);
      if (!dates) {
        return;
      }

      const referenceDateInput = document.getElementById('reference_date');
      const previousDateInput = document.getElementById('previous_date');
      if (!referenceDateInput || !previousDateInput) {
        return;
      }

      referenceDateInput.value = dates.referenceDate;
      previousDateInput.value = dates.previousDate;

      const form =
        (opts.formSelector && document.querySelector(opts.formSelector)) ||
        select.closest('form');
      if (form) {
        form.submit();
      }
    });
  }

  global.ComparisonPeriod = {
    computeComparisonDates,
    isDayOverDayComparison,
    initializeComparisonPeriodSelect,
  };
})(window);
