import { ArrowLeft, CalendarClock, Download } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { ErrorState, LoadingState } from '@/components/ui/states'
import { useProductOptions } from '@/features/admin/api'
import { useMe, usePermissions } from '@/features/auth/hooks'
import { useUserOptions } from '@/features/products/api'
import { formatDateTime } from '@/lib/utils'
import { exportUrl, useCreateSchedule, useReport, useRun } from './api'
import { ReportSections } from './ReportSections'

const iso = (d) => d.toISOString().slice(0, 10)

function ScheduleForm({ reportKey, title, productId, onClose }) {
  const { data: me } = useMe()
  const users = useUserOptions()
  const create = useCreateSchedule()
  const [name, setName] = useState(title)
  const [frequency, setFrequency] = useState('weekly')
  const [rangeDays, setRangeDays] = useState(7)
  const [recipients, setRecipients] = useState([me.user.id])
  const toggle = (id) =>
    setRecipients(
      recipients.includes(id) ? recipients.filter((r) => r !== id) : [...recipients, id],
    )
  return (
    <Card className="mb-4">
      <CardHeader>
        <CardTitle>Schedule this report</CardTitle>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-3 md:grid-cols-3"
          onSubmit={(e) => {
            e.preventDefault()
            create.mutate(
              {
                name: name.trim(),
                report_key: reportKey,
                frequency,
                range_days: Number(rangeDays),
                product_id: productId || null,
                recipient_user_ids: recipients,
              },
              { onSuccess: onClose },
            )
          }}
        >
          {create.isError && (
            <div className="md:col-span-3">
              <Alert variant="error" title={create.error.message} />
            </div>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="sched-name">Name</Label>
            <Input id="sched-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="sched-frequency">Frequency</Label>
            <Select
              id="sched-frequency"
              value={frequency}
              onChange={(e) => setFrequency(e.target.value)}
            >
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="sched-range">Covering the last (days)</Label>
            <Input
              id="sched-range"
              type="number"
              min={1}
              max={366}
              value={rangeDays}
              onChange={(e) => setRangeDays(e.target.value)}
            />
          </div>
          <fieldset className="md:col-span-3">
            <legend className="mb-1 text-sm font-medium">Recipients</legend>
            {users.enabled ? (
              <div className="flex max-h-40 flex-wrap gap-3 overflow-y-auto text-sm">
                {(users.data ?? []).map((u) => (
                  <label key={u.id} className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={recipients.includes(u.id)}
                      onChange={() => toggle(u.id)}
                    />
                    {u.full_name}
                  </label>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Delivered to you.</p>
            )}
          </fieldset>
          <p className="text-xs text-muted-foreground md:col-span-3">
            Delivered as an in-app notification at 06:00 company time. Email delivery is not
            configured.
          </p>
          <div className="flex gap-2 md:col-span-3">
            <Button
              type="submit"
              loading={create.isPending}
              disabled={!recipients.length || name.trim().length < 2}
            >
              Create schedule
            </Button>
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

function Header({ report, tz }) {
  return (
    <p className="mb-4 text-xs text-muted-foreground">
      Period {report.period.start} to {report.period.end} · generated{' '}
      {formatDateTime(report.generated_at, tz)} from live Orbit records
    </p>
  )
}

export function ReportViewPage() {
  const { reportKey } = useParams()
  const { data: me } = useMe()
  const { has } = usePermissions()
  const products = useProductOptions()
  const today = new Date()
  const [start, setStart] = useState(iso(new Date(today.getTime() - 29 * 86_400_000)))
  const [end, setEnd] = useState(iso(today))
  const [productId, setProductId] = useState('')
  const [scheduling, setScheduling] = useState(false)
  const filters = { start, end, product_id: productId }
  const { data, isPending, isError, error, refetch, isFetching } = useReport(reportKey, filters)
  return (
    <>
      <Link
        to="/app/reports"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> Reports
      </Link>
      <PageHeader title={data?.title ?? 'Report'} />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="report-start">From</Label>
          <Input
            id="report-start"
            type="date"
            value={start}
            max={end}
            onChange={(e) => setStart(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="report-end">To</Label>
          <Input
            id="report-end"
            type="date"
            value={end}
            min={start}
            onChange={(e) => setEnd(e.target.value)}
          />
        </div>
        {reportKey !== 'people' && (
          <div className="space-y-1.5">
            <Label htmlFor="report-product">Product</Label>
            <Select
              id="report-product"
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
            >
              <option value="">All products</option>
              {(products.data ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>
          </div>
        )}
        <div className="ml-auto flex flex-wrap gap-2">
          {has('report.export') && (
            <>
              <a
                href={exportUrl(reportKey, 'xlsx', filters)}
                className="inline-flex h-8 items-center gap-2 rounded-md border border-input px-3 text-xs hover:bg-muted"
              >
                <Download className="size-4" aria-hidden="true" /> Excel
              </a>
              <a
                href={exportUrl(reportKey, 'csv', filters)}
                className="inline-flex h-8 items-center gap-2 rounded-md border border-input px-3 text-xs hover:bg-muted"
              >
                <Download className="size-4" aria-hidden="true" /> CSV
              </a>
            </>
          )}
          {has('report.create') && !scheduling && data && (
            <Button size="sm" variant="outline" onClick={() => setScheduling(true)}>
              <CalendarClock aria-hidden="true" /> Schedule
            </Button>
          )}
        </div>
      </div>
      {scheduling && (
        <ScheduleForm
          reportKey={reportKey}
          title={data.title}
          productId={productId}
          onClose={() => setScheduling(false)}
        />
      )}
      {isPending && <LoadingState label="Generating report…" />}
      {isError && (
        <ErrorState title="Couldn't generate this report" error={error} onRetry={refetch} />
      )}
      {data && (
        <div aria-busy={isFetching}>
          <Header report={data} tz={me.company.timezone} />
          <ReportSections report={data} />
        </div>
      )}
    </>
  )
}

export function ReportRunPage() {
  const { runId } = useParams()
  const { data: me } = useMe()
  const { data, isPending, isError, error, refetch } = useRun(runId)
  if (isPending) return <LoadingState label="Loading report…" />
  if (isError)
    return <ErrorState title="Couldn't load this report" error={error} onRetry={refetch} />
  return (
    <>
      <Link
        to="/app/reports"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> Reports
      </Link>
      <PageHeader
        title={data.title}
        description="A saved snapshot. Figures reflect the moment it was generated."
      />
      <Header report={data} tz={me.company.timezone} />
      <ReportSections report={data} />
    </>
  )
}
