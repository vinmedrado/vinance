type CivilDatePart = 'year' | 'month' | 'day';

function datePart(parts: Intl.DateTimeFormatPart[], type: CivilDatePart) {
  return parts.find((item) => item.type === type)?.value;
}

/**
 * Format a civil date for an HTML date input without converting it to UTC.
 * A time zone is injectable so the boundary behavior is deterministic in tests.
 */
export function localDateInputValue(date = new Date(), timeZone?: string) {
  if (timeZone) {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(date);
    const year = datePart(parts, 'year');
    const month = datePart(parts, 'month');
    const day = datePart(parts, 'day');
    if (year && month && day) return `${year}-${month}-${day}`;
  }

  const year = String(date.getFullYear()).padStart(4, '0');
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}
