import { Badge } from '@/components/ui/badge'
import { STATUS_BY_VALUE } from './constants'

export function ProductStatusBadge({ status }) {
  const meta = STATUS_BY_VALUE[status] ?? { label: status, variant: 'default' }
  return <Badge variant={meta.variant}>{meta.label}</Badge>
}

export function UnconfirmedBadge({ confirmed }) {
  if (confirmed) return null
  return (
    <Badge variant="warning" title="Details have not been confirmed by the product owner">
      Awaiting confirmation
    </Badge>
  )
}
