const KEY = 'orbit.attribution'
const UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign']

/**
 * Remembers how the visitor first arrived (UTM tags, referrer, landing page)
 * for this browser session, so enquiries carry source attribution.
 * Stored in sessionStorage only; nothing is sent until a form is submitted.
 */
export function captureAttribution(location = window.location, referrer = document.referrer) {
  try {
    if (sessionStorage.getItem(KEY)) return
    const params = new URLSearchParams(location.search)
    const data = { landing_page: `${location.pathname}${location.search}`.slice(0, 500) }
    for (const key of UTM_KEYS) {
      const value = params.get(key)
      if (value) data[key] = value.slice(0, 100)
    }
    if (referrer && !referrer.startsWith(location.origin)) data.referrer = referrer.slice(0, 500)
    sessionStorage.setItem(KEY, JSON.stringify(data))
  } catch {
    // Storage can be unavailable (privacy modes); attribution is optional.
  }
}

export function getAttribution() {
  try {
    return JSON.parse(sessionStorage.getItem(KEY) ?? '{}')
  } catch {
    return {}
  }
}
