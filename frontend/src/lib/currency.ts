import type { Rates } from './types';

/**
 * Convert an amount for display only. Returns null when no reliable rate is
 * available, in which case the caller shows the original provider amount.
 */
export function convert(amount: number, from: string, to: string, rates: Rates | null): number | null {
  if (from === to) return amount;
  if (!rates || rates.base !== from) return null;
  const rate = rates.rates[to];
  return typeof rate === 'number' && Number.isFinite(rate) && rate > 0 ? amount * rate : null;
}

// Region (ISO 3166) → currency for the places FlyCompare travellers most often search from.
const REGION_CURRENCY: Record<string, string> = {
  PK: 'PKR', IN: 'INR', BD: 'BDT', LK: 'LKR', NP: 'NPR', AE: 'AED', SA: 'SAR', QA: 'QAR', KW: 'KWD', BH: 'BHD', OM: 'OMR',
  EG: 'EGP', TR: 'TRY', GB: 'GBP', US: 'USD', CA: 'CAD', AU: 'AUD', NZ: 'NZD', JP: 'JPY', CN: 'CNY', HK: 'HKD', SG: 'SGD',
  MY: 'MYR', TH: 'THB', ID: 'IDR', PH: 'PHP', VN: 'VND', KR: 'KRW', CH: 'CHF', SE: 'SEK', NO: 'NOK', DK: 'DKK', PL: 'PLN',
  ZA: 'ZAR', BR: 'BRL', MX: 'MXN', NG: 'NGN', KE: 'KES', MA: 'MAD', JO: 'JOD',
  DE: 'EUR', FR: 'EUR', ES: 'EUR', IT: 'EUR', NL: 'EUR', BE: 'EUR', AT: 'EUR', IE: 'EUR', PT: 'EUR', FI: 'EUR', GR: 'EUR',
};

// IANA timezone → region. The timezone reflects where the device is set, which is a
// better location signal than the browser language (often en-US everywhere).
const TIMEZONE_REGION: Record<string, string> = {
  'Asia/Karachi': 'PK', 'Asia/Kolkata': 'IN', 'Asia/Calcutta': 'IN', 'Asia/Dhaka': 'BD', 'Asia/Colombo': 'LK', 'Asia/Kathmandu': 'NP',
  'Asia/Dubai': 'AE', 'Asia/Riyadh': 'SA', 'Asia/Qatar': 'QA', 'Asia/Kuwait': 'KW', 'Asia/Bahrain': 'BH', 'Asia/Muscat': 'OM',
  'Africa/Cairo': 'EG', 'Europe/Istanbul': 'TR', 'Europe/London': 'GB', 'Asia/Tokyo': 'JP', 'Asia/Shanghai': 'CN', 'Asia/Hong_Kong': 'HK',
  'Asia/Singapore': 'SG', 'Asia/Kuala_Lumpur': 'MY', 'Asia/Bangkok': 'TH', 'Asia/Jakarta': 'ID', 'Asia/Manila': 'PH',
  'Asia/Ho_Chi_Minh': 'VN', 'Asia/Seoul': 'KR', 'Europe/Zurich': 'CH', 'Europe/Stockholm': 'SE', 'Europe/Oslo': 'NO',
  'Europe/Copenhagen': 'DK', 'Europe/Warsaw': 'PL', 'Africa/Johannesburg': 'ZA', 'America/Sao_Paulo': 'BR', 'America/Mexico_City': 'MX',
  'Africa/Lagos': 'NG', 'Africa/Nairobi': 'KE', 'Africa/Casablanca': 'MA', 'Asia/Amman': 'JO',
  'Europe/Berlin': 'DE', 'Europe/Paris': 'FR', 'Europe/Madrid': 'ES', 'Europe/Rome': 'IT', 'Europe/Amsterdam': 'NL',
  'Europe/Brussels': 'BE', 'Europe/Vienna': 'AT', 'Europe/Dublin': 'IE', 'Europe/Lisbon': 'PT', 'Europe/Helsinki': 'FI', 'Europe/Athens': 'GR',
  'Pacific/Auckland': 'NZ',
};

/**
 * Best guess at the visitor's local currency from the device timezone, then the
 * browser locale's region. Runs entirely in the browser: no location permission
 * prompt and nothing is sent anywhere. Returns null when there is no confident match.
 */
export function detectLocalCurrency(): string | null {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const tzRegion = TIMEZONE_REGION[tz];
    if (tzRegion) return REGION_CURRENCY[tzRegion] ?? null;
    if (tz?.startsWith('America/') && !tz.includes('Sao_Paulo') && !tz.includes('Mexico')) {
      return tz.match(/Toronto|Vancouver|Edmonton|Winnipeg|Halifax|Regina|St_Johns/) ? 'CAD' : 'USD';
    }
    if (tz?.startsWith('Australia/')) return 'AUD';
    for (const lang of navigator.languages ?? [navigator.language]) {
      const region = new Intl.Locale(lang).maximize().region;
      if (region && REGION_CURRENCY[region]) return REGION_CURRENCY[region];
    }
  } catch { /* old browsers without Intl.Locale */ }
  return null;
}
