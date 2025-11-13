// Central Banks Recap JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Last button
    initializeLastButton();

    // Highlight max and second max values in probability matrix
    highlightProbabilityMatrix();

    // Calculate and display probability matrix diffs
    calculateProbabilityDiffs();
});

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

function highlightProbabilityMatrix() {
    // Find all probability matrix tables (main, not diff)
    const mainTables = document.querySelectorAll('table.probability-matrix-table[data-type="main"]');

    mainTables.forEach(table => {
        const rows = table.querySelectorAll('tbody tr');

        rows.forEach(row => {
            const cells = row.querySelectorAll('td.prob-cell[data-value]');
            const values = Array.from(cells).map(cell => {
                const value = parseFloat(cell.getAttribute('data-value')) || 0;
                return { cell, value };
            });

            values.sort((a, b) => b.value - a.value);

            if (values.length > 0 && values[0].value > 0) {
                values[0].cell.classList.add('prob-max');
            }
            if (values.length > 1 && values[1].value > 0) {
                values[1].cell.classList.add('prob-second-max');
            }
            if (values.length > 2 && values[2].value > 0) {
                values[2].cell.classList.add('prob-third-max');
            }
        });
    });
}

function calculateProbabilityDiffs() {
    // Find all diff tables
    const diffTables = document.querySelectorAll('table.probability-matrix-table[data-type="diff"]');

    diffTables.forEach(table => {
        const bank = table.getAttribute('data-bank');
        const rows = table.querySelectorAll('tbody tr');

        rows.forEach(row => {
            const cells = row.querySelectorAll('td.diff-cell[data-diff]');

            cells.forEach(cell => {
                const diff = parseFloat(cell.getAttribute('data-diff')) || 0;

                // Remove existing diff classes
                cell.classList.remove(
                    'diff-positive-large',
                    'diff-positive-small',
                    'diff-negative-large',
                    'diff-negative-small'
                );

                // Add appropriate color class based on diff value
                if (diff > 25) {
                    cell.classList.add('diff-positive-large');
                } else if (diff > 0) {
                    cell.classList.add('diff-positive-small');
                } else if (diff === -25) {
                    cell.classList.add('diff-negative-large');
                } else if (diff < 0) {
                    cell.classList.add('diff-negative-small');
                }
            });
        });
    });
}

