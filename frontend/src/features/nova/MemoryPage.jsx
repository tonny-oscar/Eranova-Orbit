import { ArrowLeft, Brain, Check, Pencil, Plus, Trash2, X } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ConfirmButton } from '@/components/ui/confirm-button'
import { Checkbox, Select } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states'
import { useMe } from '@/features/auth/hooks'
import { formatDateTime } from '@/lib/utils'
import { useMemories, useMemoryActions, useNovaProfile, useSaveNovaProfile } from './api'

const SOURCES = {
  told: { label: 'You told NOVA', variant: 'accent' },
  learned: { label: 'NOVA noticed', variant: 'warning' },
  feedback: { label: 'From your feedback', variant: 'default' },
}
const CATEGORIES = ['fact', 'preference', 'goal', 'style']

function ProfileForm({ profile }) {
  const save = useSaveNovaProfile()
  const [form, setForm] = useState({ ...profile, preferred_name: profile.preferred_name ?? '' })
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })
  return (
    <form
      className="grid gap-4 md:grid-cols-2"
      onSubmit={(e) => {
        e.preventDefault()
        save.mutate({ ...form, preferred_name: form.preferred_name.trim() || null })
      }}
    >
      {save.isError && (
        <div className="md:col-span-2">
          <Alert variant="error" title={save.error.message} />
        </div>
      )}
      {save.isSuccess && (
        <div className="md:col-span-2">
          <Alert variant="success" title="Saved. NOVA will use this from your next message." />
        </div>
      )}
      <div className="space-y-1.5">
        <Label htmlFor="nova-name">What should NOVA call you?</Label>
        <Input
          id="nova-name"
          maxLength={60}
          value={form.preferred_name}
          onChange={set('preferred_name')}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="nova-style">Answer style</Label>
        <Select id="nova-style" value={form.response_style} onChange={set('response_style')}>
          <option value="concise">Short and to the point</option>
          <option value="balanced">Balanced</option>
          <option value="detailed">Detailed explanations</option>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="nova-language">Language</Label>
        <Select id="nova-language" value={form.language} onChange={set('language')}>
          <option value="en">English</option>
          <option value="sw">Kiswahili</option>
        </Select>
      </div>
      <Checkbox
        id="nova-learning"
        className="self-end"
        label="Let NOVA learn about me"
        description="NOVA saves lasting preferences and facts it notices, and lessons from your 👎 feedback. You can review everything below."
        checked={form.learning_enabled}
        onChange={(e) => setForm({ ...form, learning_enabled: e.target.checked })}
      />
      <div className="md:col-span-2">
        <Button type="submit" loading={save.isPending}>
          Save
        </Button>
      </div>
    </form>
  )
}

function MemoryRow({ note, timeZone }) {
  const { update, remove } = useMemoryActions()
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(note.content)
  const source = SOURCES[note.source] ?? { label: note.source }
  return (
    <li className="space-y-1 py-3">
      {editing ? (
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            update.mutate({ id: note.id, content: text }, { onSuccess: () => setEditing(false) })
          }}
        >
          <Label htmlFor={`memory-${note.id}`} className="sr-only">
            Edit note
          </Label>
          <Input
            id={`memory-${note.id}`}
            value={text}
            maxLength={500}
            onChange={(e) => setText(e.target.value)}
          />
          <Button type="submit" size="sm" aria-label="Save note" loading={update.isPending}>
            <Check aria-hidden="true" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            aria-label="Cancel editing"
            onClick={() => setEditing(false)}
          >
            <X aria-hidden="true" />
          </Button>
        </form>
      ) : (
        <div className="flex items-start justify-between gap-3">
          <p className={note.active ? '' : 'text-muted-foreground line-through'}>{note.content}</p>
          <div className="flex shrink-0 gap-1">
            <Button
              variant="ghost"
              size="sm"
              aria-label={`Edit "${note.content}"`}
              onClick={() => setEditing(true)}
            >
              <Pencil aria-hidden="true" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              aria-label={`Forget "${note.content}"`}
              loading={remove.isPending}
              onClick={() => remove.mutate(note.id)}
            >
              <Trash2 aria-hidden="true" />
            </Button>
          </div>
        </div>
      )}
      {update.isError && <Alert variant="error" title={update.error.message} />}
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge variant={source.variant}>{source.label}</Badge>
        <span>{note.category}</span>
        <span>· saved {formatDateTime(note.created_at, timeZone)}</span>
        {note.use_count > 0 && <span>· used {note.use_count}×</span>}
        <button
          type="button"
          className="underline"
          onClick={() => update.mutate({ id: note.id, active: !note.active })}
        >
          {note.active ? 'Pause' : 'Use again'}
        </button>
      </div>
    </li>
  )
}

function AddMemory() {
  const { add } = useMemoryActions()
  const [content, setContent] = useState('')
  const [category, setCategory] = useState('fact')
  return (
    <form
      className="flex flex-wrap items-end gap-2"
      onSubmit={(e) => {
        e.preventDefault()
        add.mutate({ content: content.trim(), category }, { onSuccess: () => setContent('') })
      }}
    >
      {add.isError && (
        <div className="w-full">
          <Alert variant="error" title={add.error.message} />
        </div>
      )}
      <div className="min-w-64 flex-1 space-y-1.5">
        <Label htmlFor="memory-new">Teach NOVA something</Label>
        <Input
          id="memory-new"
          maxLength={500}
          placeholder="e.g. I manage ShulePoa and HostPilot"
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="memory-category">Type</Label>
        <Select id="memory-category" value={category} onChange={(e) => setCategory(e.target.value)}>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </Select>
      </div>
      <Button type="submit" loading={add.isPending} disabled={content.trim().length < 3}>
        <Plus aria-hidden="true" /> Add
      </Button>
    </form>
  )
}

export function MemoryPage() {
  const { data: me } = useMe()
  const profile = useNovaProfile()
  const memories = useMemories()
  const { clear } = useMemoryActions()
  return (
    <>
      <Link
        to="/app/nova"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> NOVA
      </Link>
      <PageHeader
        title="What NOVA knows about you"
        description="NOVA personalises answers using your settings and these notes. Only you can see them."
      />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Your preferences</CardTitle>
          </CardHeader>
          <CardContent>
            {profile.isPending && <LoadingState label="Loading…" />}
            {profile.isError && (
              <ErrorState
                title="Couldn't load settings"
                error={profile.error}
                onRetry={profile.refetch}
              />
            )}
            {profile.data && (
              <ProfileForm key={JSON.stringify(profile.data)} profile={profile.data} />
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Brain className="size-4" aria-hidden="true" /> Memory
            </CardTitle>
            <CardDescription>
              Things you told NOVA, things it noticed, and lessons from your feedback. NOVA never
              stores passwords, codes or payment details. Notes never change what you&apos;re
              allowed to see or do.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <AddMemory />
            {memories.isPending && <LoadingState label="Loading memory…" />}
            {memories.data?.length === 0 && (
              <EmptyState
                icon={Brain}
                title="Nothing remembered yet"
                description={'Tell NOVA "remember that…" or add a note above.'}
              />
            )}
            {memories.data?.length > 0 && (
              <>
                <ul className="divide-y text-sm">
                  {memories.data.map((note) => (
                    <MemoryRow
                      key={`${note.id}-${note.updated_at}`}
                      note={note}
                      timeZone={me.company.timezone}
                    />
                  ))}
                </ul>
                <ConfirmButton
                  confirmLabel="Yes, forget everything"
                  loading={clear.isPending}
                  onConfirm={() => clear.mutate()}
                >
                  Forget everything
                </ConfirmButton>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  )
}
