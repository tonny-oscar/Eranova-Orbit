import { ArrowDown, ArrowLeft, ArrowUp, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ConfirmButton } from '@/components/ui/confirm-button'
import { Textarea } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { ErrorState, LoadingState } from '@/components/ui/states'
import { useMe } from '@/features/auth/hooks'
import { formatDateTime } from '@/lib/utils'
import { useContentPage, useSaveDraft, useSetPagePublished } from './api'

function Editor({ page }) {
  const { data: me } = useMe()
  const save = useSaveDraft(page.slug)
  const publish = useSetPagePublished(page.slug)
  const [title, setTitle] = useState(page.draft.title)
  const [summary, setSummary] = useState(page.draft.summary)
  const [seo, setSeo] = useState(page.draft.seo_description)
  const [sections, setSections] = useState(page.draft.sections)
  const [dirty, setDirty] = useState(false)
  const readOnly = !page.can_edit
  const error = save.error ?? publish.error

  const touch = (setter) => (value) => {
    setter(value)
    setDirty(true)
  }
  const updateSection = (index, key, value) =>
    touch(setSections)(sections.map((s, i) => (i === index ? { ...s, [key]: value } : s)))
  const move = (index, delta) => {
    const next = [...sections]
    const [item] = next.splice(index, 1)
    next.splice(index + delta, 0, item)
    touch(setSections)(next)
  }

  const onSave = (event) => {
    event.preventDefault()
    save.mutate(
      { title: title.trim(), summary, seo_description: seo, sections },
      { onSuccess: () => setDirty(false) },
    )
  }

  return (
    <form onSubmit={onSave} className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
      <div className="space-y-4">
        {error && <Alert variant="error" title={error.message} />}
        <Card>
          <CardContent className="space-y-4 pt-5">
            <div className="space-y-1.5">
              <Label htmlFor="page-title">Page title</Label>
              <Input
                id="page-title"
                maxLength={150}
                value={title}
                disabled={readOnly}
                onChange={(e) => touch(setTitle)(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="page-summary">Summary</Label>
              <Textarea
                id="page-summary"
                rows={2}
                maxLength={500}
                value={summary}
                disabled={readOnly}
                onChange={(e) => touch(setSummary)(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="page-seo">Search description</Label>
              <Input
                id="page-seo"
                maxLength={300}
                value={seo}
                disabled={readOnly}
                onChange={(e) => touch(setSeo)(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Shown by search engines. Up to 300 characters.
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Sections</CardTitle>
            <CardDescription>Plain text. Leave a blank line between paragraphs.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {sections.length === 0 && (
              <p className="text-sm text-muted-foreground">No sections yet.</p>
            )}
            {sections.map((section, index) => (
              <fieldset key={index} className="space-y-2 rounded-lg border p-3">
                <legend className="sr-only">Section {index + 1}</legend>
                <div className="flex items-end gap-2">
                  <div className="flex-1 space-y-1.5">
                    <Label htmlFor={`section-${index}-heading`}>Heading</Label>
                    <Input
                      id={`section-${index}-heading`}
                      maxLength={150}
                      value={section.heading}
                      disabled={readOnly}
                      onChange={(e) => updateSection(index, 'heading', e.target.value)}
                    />
                  </div>
                  {!readOnly && (
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label="Move section up"
                        disabled={index === 0}
                        onClick={() => move(index, -1)}
                      >
                        <ArrowUp />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label="Move section down"
                        disabled={index === sections.length - 1}
                        onClick={() => move(index, 1)}
                      >
                        <ArrowDown />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`Remove section ${index + 1}`}
                        onClick={() => touch(setSections)(sections.filter((_, i) => i !== index))}
                      >
                        <Trash2 />
                      </Button>
                    </div>
                  )}
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor={`section-${index}-body`}>Text</Label>
                  <Textarea
                    id={`section-${index}-body`}
                    rows={5}
                    maxLength={5000}
                    value={section.body}
                    disabled={readOnly}
                    onChange={(e) => updateSection(index, 'body', e.target.value)}
                  />
                </div>
              </fieldset>
            ))}
            {!readOnly && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => touch(setSections)([...sections, { heading: '', body: '' }])}
              >
                <Plus aria-hidden="true" /> Add section
              </Button>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Publishing</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex flex-wrap gap-1.5">
              {page.published ? (
                <Badge variant="success">Published</Badge>
              ) : (
                <Badge>Not published</Badge>
              )}
              {(page.has_unpublished_changes || dirty) && (
                <Badge variant="warning">Draft differs from live</Badge>
              )}
            </div>
            {page.published_at && (
              <p className="text-muted-foreground">
                Last published {formatDateTime(page.published_at, me.company.timezone)}
              </p>
            )}
            {!readOnly && (
              <Button
                type="submit"
                className="w-full"
                loading={save.isPending}
                disabled={!dirty || !title.trim()}
              >
                Save draft
              </Button>
            )}
            {save.isSuccess && !dirty && <p className="text-xs text-success">Draft saved.</p>}
            {page.can_publish ? (
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="accent"
                  disabled={dirty || !page.has_unpublished_changes}
                  loading={publish.isPending && publish.variables === true}
                  onClick={() => publish.mutate(true)}
                >
                  Publish draft
                </Button>
                {page.published && (
                  <ConfirmButton
                    confirmLabel="Confirm unpublish"
                    onConfirm={() => publish.mutate(false)}
                  >
                    Unpublish
                  </ConfirmButton>
                )}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                Publishing requires approval rights; save your draft and ask an approver.
              </p>
            )}
            {dirty && page.can_publish && (
              <p className="text-xs text-muted-foreground">Save the draft before publishing.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </form>
  )
}

export function PageEditorPage() {
  const { slug } = useParams()
  const { data, isPending, isError, error, refetch } = useContentPage(slug)
  return (
    <>
      <Link
        to="/app/website"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> Website
      </Link>
      <PageHeader title={data ? `Edit: ${data.label}` : 'Edit page'} />
      {isPending && <LoadingState label="Loading page…" />}
      {isError && <ErrorState title="Couldn't load this page" error={error} onRetry={refetch} />}
      {data && <Editor key={data.updated_at ?? slug} page={data} />}
    </>
  )
}
