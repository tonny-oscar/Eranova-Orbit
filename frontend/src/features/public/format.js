export function formatPrice(plan) {
  if (!plan.amount) return 'Price on request'
  const amount = Number(plan.amount).toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })
  const interval = {
    monthly: '/ month',
    quarterly: '/ quarter',
    yearly: '/ year',
    one_time: 'one-time',
  }[plan.interval]
  return [plan.currency, amount, interval].filter(Boolean).join(' ')
}
