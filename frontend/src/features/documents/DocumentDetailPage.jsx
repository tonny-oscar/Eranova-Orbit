import { ArrowLeft, Download, Upload } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ConfirmButton } from '@/components/ui/confirm-button'
import { Input, Label } from '@/components/ui/input'
import { ErrorState, LoadingState } from '@/components/ui/states'
import { useMe, usePermissions } from '@/features/auth/hooks'
import { useUserOptions } from '@/features/products/api'
import { formatDateTime } from '@/lib/utils'
import {
  ACCEPT,
  CATEGORY,
  MAX_BYTES,
  downloadUrl,
  formatBytes,
  useDocument,
  useDocumentActions,
} from './api'

function NewVersion({ doc }) {
  const { addVersion } = useDocumentActions(doc.id)
  const [file, setFile] = useState(null)
  const [note, setNote] = useState('')
  return (
    <form
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault()
        const data = new FormData()
        data.set('file', file)
        if (note.trim()) data.set('note', note.trim())
        addVersion.mutate(data, {
          onSuccess: () => {
            setFile(null)
            setNote('')
            e.target.reset()
          },
        })
      }}
    >
      {addVersion.isError && <Alert variant="error" title={addVersion.error.message} />}
      <Label htmlFor="version-file">Upload a new version</Label>
      <Input
        id="version-file"
        type="file"
        accept={ACCEPT}
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />
      <Label htmlFor="version-note">What changed (optional)</Label>
      <Input
        id="version-note"
        maxLength={500}
        value={note}
        onChange={(e) => setNote(e.target.value)}
      />
      <Button
        type="submit"
        size="sm"
        variant="outline"
        loading={addVersion.isPending}
        disabled={!file || file.size > MAX_BYTES}
      >
        <Upload aria-hidden="true" /> Upload version
      </Button>
    </form>
  )
}

function Members({ doc }) {
  const { setMembers } = useDocumentActions(doc.id)
  const users = useUserOptions()
  const [selected, setSelected] = useState(doc.members.map((m) => m.id))
  if (!users.enabled)
    return (
      <p className="text-sm text-muted-foreground">
        Members: {doc.members.map((m) => m.name).join(', ') || 'none'}
      </p>
    )
  const toggle = (id) =>
    setSelected(selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id])
  return (
    <form
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault()
        setMembers.mutate(selected)
      }}
    >
      {setMembers.isError && <Alert variant="error" title={setMembers.error.message} />}
      {setMembers.isSuccess && <Alert variant="success" title="Access updated" />}
      <ul className="max-h-56 space-y-1 overflow-y-auto text-sm">
        {(users.data ?? []).map((u) => (
          <li key={u.id}>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={selected.includes(u.id)}
                onChange={() => toggle(u.id)}
              />
              {u.full_name}
            </label>
          </li>
        ))}
      </ul>
      <Button type="submit" size="sm" loading={setMembers.isPending}>
        Save access
      </Button>
    </form>
  )
}

export function DocumentDetailPage() {
  const { documentId } = useParams()
  const navigate = useNavigate()
  const { data: me } = useMe()
  const { has } = usePermissions()
  const tz = me.company.timezone
  const { data: doc, isPending, isError, error, refetch } = useDocument(documentId)
  const { update, remove } = useDocumentActions(documentId)
  if (isPending) return <LoadingState label="Loading document…" />
  if (isError) return <ErrorState title="Couldn't load document" error={error} onRetry={refetch} />
  return (
    <>
      <Link
        to="/app/documents"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> Documents
      </Link>
      <PageHeader
        title={doc.title}
        description={doc.description || `${doc.filename} · ${formatBytes(doc.size_bytes)}`}
        actions={
          <a href={downloadUrl(doc.id)} className={buttonVariants({ variant: 'default' })}>
            <Download aria-hidden="true" /> Download
          </a>
        }
      />
      <div className="mb-4 flex flex-wrap gap-2">
        <Badge variant="accent">{CATEGORY[doc.category]}</Badge>
        <Badge variant={doc.visibility === 'restricted' ? 'warning' : 'default'}>
          {doc.visibility === 'restricted' ? 'Restricted' : 'Shared by role'}
        </Badge>
        {doc.product && <Badge>{doc.product.name}</Badge>}
        {doc.department && <Badge>{doc.department.name}</Badge>}
        {doc.project && <Badge>{doc.project.name}</Badge>}
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Versions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <ul className="divide-y text-sm">
              {doc.versions.map((v) => (
                <li key={v.version} className="flex items-center justify-between gap-3 py-2.5">
                  <div>
                    <p className="font-medium">
                      v{v.version} · {v.filename}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatBytes(v.size_bytes)} · {v.uploaded_by?.name ?? 'unknown'} ·{' '}
                      {formatDateTime(v.created_at, tz)}
                      {v.note ? ` · ${v.note}` : ''}
                    </p>
                    <p
                      className="font-mono text-[10px] text-muted-foreground"
                      title="SHA-256 checksum"
                    >
                      {v.sha256.slice(0, 16)}…
                    </p>
                  </div>
                  <a
                    href={downloadUrl(doc.id, v.version)}
                    className={buttonVariants({ variant: 'ghost', size: 'sm' })}
                    aria-label={`Download version ${v.version}`}
                  >
                    <Download aria-hidden="true" />
                  </a>
                </li>
              ))}
            </ul>
            {doc.can_update && <NewVersion doc={doc} />}
          </CardContent>
        </Card>
        <div className="space-y-4">
          {doc.can_update && (
            <Card>
              <CardHeader>
                <CardTitle>Access</CardTitle>
                <CardDescription>
                  {doc.visibility === 'restricted'
                    ? 'Only the owner and the people below can open this document.'
                    : 'Anyone whose role covers this area can open it.'}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {update.isError && <Alert variant="error" title={update.error.message} />}
                <Button
                  size="sm"
                  variant="outline"
                  loading={update.isPending}
                  onClick={() =>
                    update.mutate({
                      visibility: doc.visibility === 'restricted' ? 'scoped' : 'restricted',
                    })
                  }
                >
                  {doc.visibility === 'restricted'
                    ? 'Share by role instead'
                    : 'Restrict to named people'}
                </Button>
                {doc.can_manage_members && <Members key={doc.members.length} doc={doc} />}
              </CardContent>
            </Card>
          )}
          <Card>
            <CardContent className="space-y-1 pt-5 text-sm">
              <p>
                <span className="text-muted-foreground">Owner: </span>
                {doc.owner?.name ?? '—'}
              </p>
              <p>
                <span className="text-muted-foreground">Updated: </span>
                {formatDateTime(doc.updated_at, tz)}
              </p>
              <p className="text-xs text-muted-foreground">
                Every download is recorded in the audit log.
              </p>
            </CardContent>
          </Card>
          {has('document.delete') && (
            <ConfirmButton
              confirmLabel="Confirm delete"
              loading={remove.isPending}
              onConfirm={() =>
                remove.mutate(undefined, { onSuccess: () => navigate('/app/documents') })
              }
            >
              Delete document
            </ConfirmButton>
          )}
        </div>
      </div>
    </>
  )
}
