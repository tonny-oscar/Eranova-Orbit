import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatNumber } from '@/lib/utils'

function display(value) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'number') return formatNumber(value)
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(value))
    return new Date(value).toLocaleString()
  return String(value)
}

export function ReportSections({ report }) {
  if (report.sections.length === 0)
    return (
      <p className="text-sm text-muted-foreground">
        There is nothing in this report that your role can see.
      </p>
    )
  return (
    <div className="space-y-4">
      {report.sections.map((section) => (
        <Card key={section.title}>
          <CardHeader>
            <CardTitle>{section.title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {section.metrics.length > 0 && (
              <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
                {section.metrics.map((m) => (
                  <div key={m.label}>
                    <dt className="text-xs text-muted-foreground">{m.label}</dt>
                    <dd className="text-xl font-semibold">
                      {display(m.value)}
                      {m.value != null && m.unit ? (
                        <span className="ml-1 text-sm font-normal text-muted-foreground">
                          {m.unit}
                        </span>
                      ) : null}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
            {section.columns.length > 0 &&
              (section.rows.length === 0 ? (
                <p className="text-sm text-muted-foreground">No records in this period.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <caption className="sr-only">{section.title}</caption>
                    <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <tr>
                        {section.columns.map((c) => (
                          <th key={c} scope="col" className="px-2 py-2 font-medium">
                            {c}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {section.rows.map((row, i) => (
                        <tr key={i}>
                          {row.map((cell, j) => (
                            <td key={j} className="px-2 py-2">
                              {display(cell)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            {section.note && <p className="text-xs text-muted-foreground">{section.note}</p>}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
