import { FlaskConical } from 'lucide-react'
import { DEMO_MODE } from '@/lib/api/client'

/** Always-visible notice so sample data is never mistaken for live company data. */
export function DemoBanner() {
  if (!DEMO_MODE) return null
  return (
    <div
      role="status"
      className="sticky top-0 z-50 flex items-center justify-center gap-2 bg-warning px-4 py-1.5 text-center text-xs font-medium text-midnight-950"
    >
      <FlaskConical className="size-3.5" aria-hidden="true" />
      Demo preview: sign-in is disabled and all data is sample data. Nothing is saved or sent to the
      API.
    </div>
  )
}
