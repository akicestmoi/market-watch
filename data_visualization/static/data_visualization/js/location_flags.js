const LOCATION_FLAGS = {
  "United States": "🇺🇸",
  Europe: "🇪🇺",
  Germany: "🇩🇪",
  France: "🇫🇷",
  Japan: "🇯🇵",
};

function formatLocationWithFlag(locationLabel) {
  const flag = LOCATION_FLAGS[locationLabel];
  if (!flag) {
    return locationLabel;
  }
  return `${flag} ${locationLabel}`;
}

function applyLocationFlags(root) {
  const scope = root || document;
  scope.querySelectorAll("[data-location]").forEach((element) => {
    const locationLabel = element.getAttribute("data-location") || "";
    element.textContent = formatLocationWithFlag(locationLabel);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  applyLocationFlags();
});

window.LocationFlags = {
  formatLocationWithFlag,
  applyLocationFlags,
};
