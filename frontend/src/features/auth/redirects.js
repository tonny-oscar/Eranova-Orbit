/** Only allows same-app relative paths, preventing open redirects via ?next=. */
export function safeNextPath(raw) {
  if (!raw || !raw.startsWith('/app') || raw.startsWith('//')) return '/app'
  return raw
}
