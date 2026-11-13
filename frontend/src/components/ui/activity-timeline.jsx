import { useState } from 'react'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select, Textarea } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { formatDateTime } from '@/lib/utils'

const TYPES = ['call', 'email', 'meeting', 'whatsapp', 'sms', 'note']

/** Shared communication history for leads and customers (append-only). */
export function ActivityTimeline({
  activities,
  timeZone,
  onAdd,
  adding,
  error,
  idPrefix = 'activity',
}) {
  const [type, setType] = useState('call')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')

  return (
    <div className="space-y-4">
      {onAdd && (
        <form
          className="space-y-2 rounded-lg border p-3"
          onSubmit={(e) => {
            e.preventDefault()
            onAdd({ type, subject: subject.trim(), body: body.trim() }, () => {
              setSubject('')
              setBody('')
            })
          }}
        >
          {error && <Alert variant="error" title={error.message} />}
          <div className="grid gap-2 sm:grid-cols-[9rem_1fr]">
            <div className="space-y-1">
              <Label htmlFor={`${idPrefix}-type`}>Type</Label>
              <Select
                id={`${idPrefix}-type`}
                value={type}
                onChange={(e) => setType(e.target.value)}
              >
                {TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t[0].toUpperCase() + t.slice(1)}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor={`${idPrefix}-subject`}>Summary</Label>
              <Input
                id={`${idPrefix}-subject`}
                maxLength={200}
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-1">
            <Label htmlFor={`${idPrefix}-body`}>Details (optional)</Label>
            <Textarea
              id={`${idPrefix}-body`}
              rows={2}
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </div>
          <Button
            type="submit"
            size="sm"
            variant="outline"
            disabled={subject.trim().length < 2}
            loading={adding}
          >
            Log activity
          </Button>
        </form>
      )}
      {activities.length === 0 ? (
        <p className="text-sm text-muted-foreground">No activity recorded yet.</p>
      ) : (
        <ol className="space-y-3">
          {activities.map((a) => (
            <li key={a.id} className="border-l-2 border-accent/40 pl-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Badge>{a.type}</Badge>
                <span className="font-medium">{a.subject}</span>
              </div>
              {a.body && <p className="mt-1 whitespace-pre-line text-muted-foreground">{a.body}</p>}
              <p className="mt-1 text-xs text-muted-foreground">
                {formatDateTime(a.occurred_at, timeZone)}
                {a.created_by ? ` · ${a.created_by.name}` : ''}
              </p>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
