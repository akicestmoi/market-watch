function initializeLastButton() {
  const lastBtn = document.getElementById('lastBtn');
  if (lastBtn && window.defaultReferenceDate && window.defaultPreviousDate) {
    lastBtn.addEventListener('click', function() {
      const referenceDateInput = document.getElementById('reference_date');
      const previousDateInput = document.getElementById('previous_date');

      if (referenceDateInput && previousDateInput) {
        referenceDateInput.value = window.defaultReferenceDate;
        previousDateInput.value = window.defaultPreviousDate;
        document.querySelector('form').submit();
      }
    });
  }
}

function getCellClass(value) {
  if (value > 2.5) {
    return 'table-change-positive';
  } else if (value > 0) {
    return 'table-change-slightly-positive';
  } else if (value < -2.5) {
    return 'table-change-negative';
  } else if (value < 0) {
    return 'table-change-slightly-negative';
  }
  return '';
}

function renderFxMatrix() {
  if (!window.fxMatrix || !window.fxMatrixOrder) {
    return;
  }

  const container = document.getElementById('fxMatrixContainer');
  const header = document.getElementById('fxMatrixHeader');
  const body = document.getElementById('fxMatrixBody');

  if (!container || !header || !body) {
    return;
  }

  // Create header row
  const headerRow = document.createElement('tr');
  const emptyHeader = document.createElement('th');
  headerRow.appendChild(emptyHeader);

  window.fxMatrixOrder.forEach(currency => {
    const th = document.createElement('th');
    th.textContent = currency;
    headerRow.appendChild(th);
  });
  header.appendChild(headerRow);

  // Create a map for quick lookup
  const matrixMap = {};
  window.fxMatrix.forEach(row => {
    matrixMap[row.currency] = row;
  });

  // Create body rows
  window.fxMatrixOrder.forEach(baseCurrency => {
    const row = document.createElement('tr');
    const currencyHeader = document.createElement('th');
    currencyHeader.textContent = baseCurrency;
    row.appendChild(currencyHeader);

    window.fxMatrixOrder.forEach(quoteCurrency => {
      const cell = document.createElement('td');
      const value = baseCurrency === quoteCurrency ? 0 : (matrixMap[baseCurrency]?.[quoteCurrency] || 0);
      cell.textContent = value.toFixed(2);
      cell.className = getCellClass(value);
      row.appendChild(cell);
    });

    body.appendChild(row);
  });

  container.style.display = 'block';
}

initializeLastButton();
renderFxMatrix();

