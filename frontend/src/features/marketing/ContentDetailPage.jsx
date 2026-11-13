import { ArrowLeft, ExternalLink } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ConfirmButton } from '@/components/ui/confirm-button'
import { Textarea } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { ErrorState, LoadingState } from '@/components/ui/states'
import { useMe, usePermissions } from '@/features/auth/hooks'
import { formatDateTime } from '@/lib/utils'
import { ACTION_LABELS, CONTENT_KIND, CONTENT_STATUS, useContent, useContentActions } from './api'

const NEEDS_NOTE = new Set(['request_changes', 'record_failed'])

function Editor({ item }) {
  const { update } = useContentActions(item.id)
  const [title, setTitle] = useState(item.title)
  const [body, setBody] = useState(item.body)
  const dirty = title !== item.title || body !== item.body
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault()
        update.mutate({ title: title.trim(), body })
      }}
    >
      {update.isError && <Alert variant="error" title={update.error.message} />}
      {item.status === 'in_review' && (
        <Alert title="Editing returns this item to draft so reviewers see the final text." />
      )}
      <div className="space-y-1.5">
        <Label htmlFor="content-edit-title">Title</Label>
        <Input id="content-edit-title" value={title} onChange={(e) => setTitle(e.target.value)} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="content-edit-body">Content</Label>
        <Textarea
          id="content-edit-body"
          rows={14}
          value={body}
          onChange={(e) => setBody(e.target.value)}
        />
        <p className="text-xs text-muted-foreground">{body.length.toLocaleString()} characters</p>
      </div>
      <Button type="submit" disabled={!dirty || title.trim().length < 2} loading={update.isPending}>
        Save draft
      </Button>
    </form>
  )
}

function Workflow({ item }) {
  const { act } = useContentActions(item.id)
  const [pending, setPending] = useState(null)
  const [note, setNote] = useState('')
  const [when, setWhen] = useState('')
  const [url, setUrl] = useState('')
  const reset = () => {
    setPending(null)
    setNote('')
    setWhen('')
    setUrl('')
  }
  const run = (action) => {
    const body = { action }
    if (NEEDS_NOTE.has(action) || action === 'approve') body.note = note.trim() || null
    if (action === 'schedule') body.scheduled_for = new Date(when).toISOString()
    if (action === 'record_published') body.published_url = url.trim()
    act.mutate(body, { onSuccess: reset })
  }
  const needsInput = (a) => NEEDS_NOTE.has(a) || a === 'schedule' || a === 'record_published'

  if (item.allowed_actions.length === 0)
    return <p className="text-sm text-muted-foreground">No actions available to you right now.</p>

  return (
    <div className="space-y-3">
      {act.isError && <Alert variant="error" title={act.error.message} />}
      <div className="flex flex-wrap gap-2">
        {item.allowed_actions.map((a) => (
          <Button
            key={a}
            size="sm"
            variant={a === 'approve' || a === 'submit' ? 'default' : 'outline'}
            loading={act.isPending && act.variables?.action === a}
            onClick={() => (needsInput(a) ? setPending(a) : run(a))}
          >
            {ACTION_LABELS[a]}
          </Button>
        ))}
      </div>
      {pending && (
        <form
          className="space-y-3 rounded-md border p-3"
          onSubmit={(e) => {
            e.preventDefault()
            run(pending)
          }}
        >
          {NEEDS_NOTE.has(pending) && (
            <div className="space-y-1.5">
              <Label htmlFor="action-note">
                {pending === 'record_failed' ? 'What went wrong?' : 'What needs to change?'}
              </Label>
              <Textarea
                id="action-note"
                rows={3}
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </div>
          )}
          {pending === 'schedule' && (
            <div className="space-y-1.5">
              <Label htmlFor="action-when">Publish at</Label>
              <Input
                id="action-when"
                type="datetime-local"
                value={when}
                onChange={(e) => setWhen(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                No publishing account is connected, so Orbit will remind you at this time. It will
                not post automatically.
              </p>
            </div>
          )}
          {pending === 'record_published' && (
            <div className="space-y-1.5">
              <Label htmlFor="action-url">Link to the live post</Label>
              <Input
                id="action-url"
                type="url"
                placeholder="https://"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Recorded as published manually by you.
              </p>
            </div>
          )}
          <div className="flex gap-2">
            <Button
              type="submit"
              size="sm"
              loading={act.isPending}
              disabled={
                (NEEDS_NOTE.has(pending) && !note.trim()) ||
                (pending === 'schedule' && !when) ||
                (pending === 'record_published' && !url.trim())
              }
            >
              {ACTION_LABELS[pending]}
            </Button>
            <Button size="sm" variant="ghost" onClick={reset}>
              Cancel
            </Button>
          </div>
        </form>
      )}
    </div>
  )
}

export function ContentDetailPage() {
  const { contentId } = useParams()
  const navigate = useNavigate()
  const { data: me } = useMe()
  const { has } = usePermissions()
  const tz = me.company.timezone
  const { data: item, isPending, isError, error, refetch } = useContent(contentId)
  const { remove } = useContentActions(contentId)
  if (isPending) return <LoadingState label="Loading content…" />
  if (isError) return <ErrorState title="Couldn't load content" error={error} onRetry={refetch} />
  const status = CONTENT_STATUS[item.status]
  return (
    <>
      <Link
        to="/app/marketing/content"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> Content studio
      </Link>
      <PageHeader
        title={item.title}
        description={[
          CONTENT_KIND[item.kind]?.label,
          item.channel,
          item.campaign?.name ?? item.product?.name,
        ]
          .filter(Boolean)
          .join(' · ')}
      />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Badge variant={status?.variant}>{status?.label}</Badge>
        {item.status === 'published' && item.publish_method === 'manual' && (
          <Badge>Manually confirmed by {item.published_by?.name ?? 'staff'}</Badge>
        )}
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Content</CardTitle>
          </CardHeader>
          <CardContent>
            {item.can_edit ? (
              <Editor key={item.updated_at} item={item} />
            ) : (
              <>
                <p className="mb-3 text-xs text-muted-foreground">
                  Locked after approval. Reopen it as a draft to make changes.
                </p>
                <div className="whitespace-pre-wrap text-sm">{item.body || 'No content yet.'}</div>
              </>
            )}
          </CardContent>
        </Card>
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Workflow</CardTitle>
              <CardDescription>Draft → review → approved → scheduled → published.</CardDescription>
            </CardHeader>
            <CardContent>
              <Workflow item={item} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>History</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1.5 text-sm">
              <p>
                <span className="text-muted-foreground">Author: </span>
                {item.author?.name ?? '—'}
              </p>
              {item.review_note && (
                <p>
                  <span className="text-muted-foreground">Reviewer note: </span>
                  {item.review_note}
                </p>
              )}
              {item.approved_at && (
                <p>
                  <span className="text-muted-foreground">Approved: </span>
                  {item.approved_by?.name} · {formatDateTime(item.approved_at, tz)}
                </p>
              )}
              {item.scheduled_for && (
                <p>
                  <span className="text-muted-foreground">Scheduled for: </span>
                  {formatDateTime(item.scheduled_for, tz)}
                </p>
              )}
              {item.published_at && (
                <p>
                  <span className="text-muted-foreground">Published: </span>
                  {formatDateTime(item.published_at, tz)}{' '}
                  {item.published_url && (
                    <a
                      href={item.published_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-accent hover:underline"
                    >
                      view <ExternalLink className="size-3" aria-hidden="true" />
                    </a>
                  )}
                </p>
              )}
              {item.failure_reason && (
                <p className="text-destructive">Failed: {item.failure_reason}</p>
              )}
            </CardContent>
          </Card>
          {has('campaign.delete') && item.status !== 'published' && (
            <ConfirmButton
              confirmLabel="Confirm delete"
              loading={remove.isPending}
              onConfirm={() =>
                remove.mutate(undefined, { onSuccess: () => navigate('/app/marketing/content') })
              }
            >
              Delete
            </ConfirmButton>
          )}
        </div>
      </div>
    </>
  )
}
