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

initializeUpcomingEventsPager();
