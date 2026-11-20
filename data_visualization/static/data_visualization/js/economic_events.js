function getUpcomingWeekPairs() {
  const body = document.getElementById("upcomingReleasesBody");
  if (!body) {
    return [];
  }
  return Array.from(body.querySelectorAll(".upcoming-week-pair"));
}

function updateUpcomingWeekPager(activePageIndex) {
  const pairs = getUpcomingWeekPairs();
  const prevBtn = document.getElementById("upcomingWeekPrev");
  const nextBtn = document.getElementById("upcomingWeekNext");
  const pageLabel = document.getElementById("upcomingWeekPagerLabel");
  if (!pairs.length) {
    return;
  }

  pairs.forEach((pair, index) => {
    pair.hidden = index !== activePageIndex;
  });

  if (pageLabel) {
    pageLabel.textContent = `Weeks ${activePageIndex * 2 + 1}–${activePageIndex * 2 + 2} of ${pairs.length * 2}`;
  }
  if (prevBtn) {
    prevBtn.disabled = activePageIndex <= 0;
  }
  if (nextBtn) {
    nextBtn.disabled = activePageIndex >= pairs.length - 1;
  }
}

function initializeUpcomingEventsPager() {
  const pairs = getUpcomingWeekPairs();
  if (!pairs.length) {
    return;
  }

  let activePageIndex = 0;
  const prevBtn = document.getElementById("upcomingWeekPrev");
  const nextBtn = document.getElementById("upcomingWeekNext");

  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      if (activePageIndex <= 0) {
        return;
      }
      activePageIndex -= 1;
      updateUpcomingWeekPager(activePageIndex);
    });
  }
  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      if (activePageIndex >= pairs.length - 1) {
        return;
      }
      activePageIndex += 1;
      updateUpcomingWeekPager(activePageIndex);
    });
  }

  updateUpcomingWeekPager(activePageIndex);
}

function getEnabledEventTypes() {
  const enabledTypes = new Set();
  document.querySelectorAll(".upcoming-event-type-toggle.active").forEach((button) => {
    const eventType = button.getAttribute("data-event-type");
    if (!eventType) {
      return;
    }
    enabledTypes.add(eventType);
    // Holidays follow the Economic Data toggle.
    if (eventType === "economic") {
      enabledTypes.add("holiday");
    }
  });
  return enabledTypes;
}

function setElementFilteredOut(element, isFilteredOut) {
  element.classList.toggle("is-filtered-out", isFilteredOut);
  element.hidden = isFilteredOut;
}

function updateUpcomingEventTypeVisibility() {
  const enabledTypes = getEnabledEventTypes();
  document.querySelectorAll(".upcoming-event-row[data-event-type]").forEach((eventRow) => {
    const eventType = eventRow.getAttribute("data-event-type");
    setElementFilteredOut(eventRow, !enabledTypes.has(eventType));
  });

  document.querySelectorAll(".upcoming-day").forEach((daySection) => {
    daySection
      .querySelectorAll(".upcoming-day-holidays, .upcoming-day-releases")
      .forEach((container) => {
        const hasVisibleEventRow = Array.from(
          container.querySelectorAll(".upcoming-event-row[data-event-type]")
        ).some((eventRow) => !eventRow.classList.contains("is-filtered-out"));
        setElementFilteredOut(container, !hasVisibleEventRow);
      });

    const hasVisibleEvent = Array.from(
      daySection.querySelectorAll(".upcoming-event-row[data-event-type]")
    ).some((eventRow) => !eventRow.classList.contains("is-filtered-out"));
    const emptyMessage = daySection.querySelector(".upcoming-day-empty");
    if (emptyMessage) {
      setElementFilteredOut(emptyMessage, hasVisibleEvent);
    }
  });
}

function initializeUpcomingEventTypeToggles() {
  const toggleButtons = Array.from(
    document.querySelectorAll(".upcoming-event-type-toggle")
  );
  if (!toggleButtons.length) {
    return;
  }

  toggleButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const willEnable = !button.classList.contains("active");
      button.classList.toggle("active", willEnable);
      button.setAttribute("aria-pressed", willEnable ? "true" : "false");
      updateUpcomingEventTypeVisibility();
    });
  });

  updateUpcomingEventTypeVisibility();
}

initializeUpcomingEventsPager();
initializeUpcomingEventTypeToggles();
