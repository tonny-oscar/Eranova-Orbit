import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { ErrorState, LoadingState } from '@/components/ui/states'
import { RequirePermission } from '@/features/auth/guards'
import { useMe } from '@/features/auth/hooks'
import { cn } from '@/lib/utils'
import { CONTENT_STATUS, useCalendar } from './api'
import { MarketingNav } from './MarketingNav'

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function dayKey(date, timeZone) {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date)
}

function Month({ month, timeZone }) {
  const first = new Date(month.getFullYear(), month.getMonth(), 1)
  const next = new Date(month.getFullYear(), month.getMonth() + 1, 1)
  const offset = (first.getDay() + 6) % 7
  const gridStart = new Date(first)
  gridStart.setDate(first.getDate() - offset)
  const gridEnd = new Date(gridStart)
  gridEnd.setDate(gridStart.getDate() + 42)
  const { data, isPending, isError, error, refetch } = useCalendar(
    gridStart.toISOString(),
    gridEnd.toISOString(),
  )
  if (isPending) return <LoadingState label="Loading calendar…" />
  if (isError) return <ErrorState title="Couldn't load calendar" error={error} onRetry={refetch} />

  const byDay = {}
  for (const item of data.content) {
    const when = item.published_at ?? item.scheduled_for
    if (when) (byDay[dayKey(new Date(when), timeZone)] ??= []).push(item)
  }
  const days = Array.from({ length: 42 }, (_, i) => {
    const d = new Date(gridStart)
    d.setDate(gridStart.getDate() + i)
    return d
  })
  const today = dayKey(new Date(), timeZone)
  return (
    <>
      <div className="grid grid-cols-7 gap-px overflow-hidden rounded-lg border bg-border text-xs">
        {WEEKDAYS.map((w) => (
          <div key={w} className="bg-muted/60 px-2 py-1.5 font-medium text-muted-foreground">
            {w}
          </div>
        ))}
        {days.map((d) => {
          const key = dayKey(d, timeZone)
          const inMonth = d >= first && d < next
          return (
            <div
              key={key}
              className={cn('min-h-24 bg-card p-1.5', !inMonth && 'opacity-40')}
              aria-label={key}
            >
              <p className={cn('mb-1 text-right', key === today && 'font-bold text-accent')}>
                {d.getDate()}
              </p>
              <ul className="space-y-1">
                {(byDay[key] ?? []).map((item) => (
                  <li key={item.id}>
                    <Link
                      to={`/app/marketing/content/${item.id}`}
                      className="block truncate rounded bg-muted px-1 py-0.5 hover:bg-accent/20"
                      title={`${item.title} (${CONTENT_STATUS[item.status]?.label})`}
                    >
                      <span
                        className={cn(
                          'mr-1 inline-block size-1.5 rounded-full',
                          item.status === 'published' && 'bg-success',
                          item.status === 'scheduled' && 'bg-warning',
                          item.status === 'failed' && 'bg-destructive',
                        )}
                        aria-hidden="true"
                      />
                      {item.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )
        })}
      </div>
      {data.campaigns.length > 0 && (
        <Card className="mt-4">
          <CardContent className="pt-5">
            <p className="mb-2 text-sm font-medium">Campaigns running this period</p>
            <ul className="flex flex-wrap gap-2">
              {data.campaigns.map((c) => (
                <li key={c.id}>
                  <Link to={`/app/marketing/campaigns/${c.id}`}>
                    <Badge>
                      {c.name} · {c.start_date ?? '…'} → {c.end_date ?? '…'}
                    </Badge>
                  </Link>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </>
  )
}

function CalendarView() {
  const { data: me } = useMe()
  const [month, setMonth] = useState(() => {
    const now = new Date()
    return new Date(now.getFullYear(), now.getMonth(), 1)
  })
  const shift = (n) => setMonth(new Date(month.getFullYear(), month.getMonth() + n, 1))
  return (
    <>
      <div className="mb-3 flex items-center gap-2">
        <Button variant="outline" size="sm" aria-label="Previous month" onClick={() => shift(-1)}>
          <ChevronLeft aria-hidden="true" />
        </Button>
        <h2 className="min-w-40 text-center font-medium">
          {month.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}
        </h2>
        <Button variant="outline" size="sm" aria-label="Next month" onClick={() => shift(1)}>
          <ChevronRight aria-hidden="true" />
        </Button>
        <p className="ml-auto text-xs text-muted-foreground">
          Shows scheduled and published content. Published means confirmed, not just planned.
        </p>
      </div>
      <Month key={month.toISOString()} month={month} timeZone={me.company.timezone} />
    </>
  )
}

export function CalendarPage() {
  return (
    <>
      <PageHeader title="Marketing" description="Campaigns, content and the publishing calendar." />
      <MarketingNav />
      <RequirePermission permission="campaign.read">
        <CalendarView />
      </RequirePermission>
    </>
  )
}
