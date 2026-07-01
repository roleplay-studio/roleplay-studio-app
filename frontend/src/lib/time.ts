import moment from 'moment';
import 'moment/locale/ru';

/**
 * Format a date string as relative time using moment.js with locale support.
 *
 * Examples:
 *   "только что"       — < 1 minute
 *   "2 минуты назад"   — < 1 hour
 *   "3 часа назад"     — < 1 day
 *   "2 дня назад"      — < 30 days
 *   "21 мая"           — older
 */
export function formatRelativeTime(dateStr: null | string, lang: string = 'en'): string {
  if (!dateStr) return '';

  const langCode = lang === 'ru' ? 'ru' : 'en';
  moment.locale(langCode);

  const m = moment(dateStr);
  const diffDays = moment().diff(m, 'days');

  if (diffDays < 30) {
    return m.fromNow();
  }

  return m.format('MMM D');
}
