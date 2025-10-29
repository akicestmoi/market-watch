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

initializeLastButton();

