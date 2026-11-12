export const LIFECYCLE_STATUSES = [
  { value: 'draft', label: 'Draft', variant: 'default' },
  { value: 'development', label: 'In development', variant: 'accent' },
  { value: 'beta', label: 'Beta', variant: 'accent' },
  { value: 'live', label: 'Live', variant: 'success' },
  { value: 'maintenance', label: 'Maintenance', variant: 'warning' },
  { value: 'sunset', label: 'Sunsetting', variant: 'warning' },
  { value: 'retired', label: 'Retired', variant: 'destructive' },
]

export const STATUS_BY_VALUE = Object.fromEntries(LIFECYCLE_STATUSES.map((s) => [s.value, s]))

export const ANALYTICS_SOURCES = [
  { value: 'ga4', label: 'Google Analytics 4' },
  { value: 'search_console', label: 'Google Search Console' },
  { value: 'orbit_sdk', label: 'Orbit tracking SDK' },
  { value: 'other', label: 'Other' },
]

export const PRICING_INTERVALS = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'quarterly', label: 'Quarterly' },
  { value: 'yearly', label: 'Yearly' },
  { value: 'one_time', label: 'One-time' },
  { value: 'custom', label: 'Custom' },
]

export function slugify(value) {
  return value
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/[\s-]+/g, '-')
    .slice(0, 64)
}
