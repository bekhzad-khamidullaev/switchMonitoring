(function () {
  'use strict';

  function normalizeText(value) {
    return value.replace(/\s+/g, ' ').trim();
  }

  function getCellValue(row, columnIndex) {
    const cell = row.cells[columnIndex];
    if (!cell) {
      return '';
    }
    if (cell.dataset && cell.dataset.sortValue !== undefined) {
      return String(cell.dataset.sortValue);
    }
    return normalizeText(cell.textContent || '');
  }

  function detectType(value) {
    const normalized = value.replace(/,/g, '').trim();
    if (/^-?\d+(\.\d+)?$/.test(normalized)) {
      return 'number';
    }

    const timestamp = Date.parse(value);
    if (!Number.isNaN(timestamp) && /[-/:.]/.test(value)) {
      return 'date';
    }

    return 'text';
  }

  function compareValues(left, right, type) {
    if (type === 'number') {
      return Number.parseFloat(left.replace(/,/g, '')) - Number.parseFloat(right.replace(/,/g, ''));
    }
    if (type === 'date') {
      return Date.parse(left) - Date.parse(right);
    }
    return left.localeCompare(right, undefined, { numeric: true, sensitivity: 'base' });
  }

  function setHeaderSortState(headers, activeIndex, direction) {
    headers.forEach((header, index) => {
      if (index === activeIndex) {
        header.setAttribute('aria-sort', direction === 'asc' ? 'ascending' : 'descending');
        header.dataset.sortDirection = direction;
      } else {
        header.setAttribute('aria-sort', 'none');
        delete header.dataset.sortDirection;
      }
    });
  }

  function makeTableSortable(table) {
    if (table.dataset.sortable === 'false' || table.dataset.sortableBound === 'true') {
      return;
    }

    const thead = table.tHead;
    const tbody = table.tBodies[0];
    if (!thead || !tbody || !thead.rows.length) {
      return;
    }

    const headers = Array.from(thead.rows[0].cells).filter((cell) => cell.tagName === 'TH');
    if (!headers.length) {
      return;
    }

    headers.forEach((header, index) => {
      if (header.dataset.nosort === 'true') {
        return;
      }

      header.classList.add('cursor-pointer', 'select-none');
      header.setAttribute('role', 'button');
      if (!header.hasAttribute('aria-sort')) {
        header.setAttribute('aria-sort', 'none');
      }

      header.addEventListener('click', function () {
        const currentDirection = header.dataset.sortDirection === 'asc' ? 'asc' : 'desc';
        const nextDirection = currentDirection === 'asc' ? 'desc' : 'asc';
        const rows = Array.from(tbody.rows)
          .map((row, rowIndex) => ({
            row: row,
            index: rowIndex,
            value: getCellValue(row, index),
          }));

        const firstComparable = rows.find((entry) => entry.value !== '');
        const valueType = firstComparable ? detectType(firstComparable.value) : 'text';

        rows.sort((left, right) => {
          const result = compareValues(left.value, right.value, valueType);
          if (result === 0) {
            return left.index - right.index;
          }
          return nextDirection === 'asc' ? result : -result;
        });

        rows.forEach((entry) => tbody.appendChild(entry.row));
        setHeaderSortState(headers, index, nextDirection);
      });
    });

    table.dataset.sortableBound = 'true';
  }

  function initSortableTables(root) {
    const scope = root && root.querySelectorAll ? root : document;
    if (scope.tagName === 'TABLE') {
      makeTableSortable(scope);
    }
    scope.querySelectorAll('table').forEach(makeTableSortable);
  }

  document.addEventListener('DOMContentLoaded', function () {
    initSortableTables(document);
  });

  document.body.addEventListener('htmx:afterSwap', function (event) {
    initSortableTables(event.target);
  });
})();
