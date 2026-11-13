import {
  Bot,
  Brain,
  ExternalLink,
  Mic,
  MicOff,
  Plus,
  Send,
  ShieldCheck,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  Volume2,
  VolumeX,
  Wrench,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { ErrorState, LoadingState } from '@/components/ui/states'
import { useMe } from '@/features/auth/hooks'
import { cn, formatNumber } from '@/lib/utils'
import {
  STATUS_LABELS,
  useApprovals,
  useConversation,
  useConversations,
  useCreateConversation,
  useDeleteConversation,
  useFeedback,
  useNovaProfile,
  useNovaStatus,
  useNovaUsage,
  useSendMessage,
} from './api'
import { ApprovalCard } from './ApprovalCard'
import { useSpeechInput, useSpeechOutput } from './useVoice'

const SUGGESTIONS = [
  'What should I work on today?',
  'Give me a business summary',
  'Which tasks are overdue?',
  'Show open support tickets',
]

function ModeBadge({ status }) {
  if (!status) return null
  return status.mode === 'ai' ? (
    <Badge variant="success">AI · {status.model}</Badge>
  ) : (
    <Badge variant="warning" title="No AI model configured on the server">
      Basic mode · look-ups only
    </Badge>
  )
}

function Executions({ items }) {
  if (!items?.length) return null
  return (
    <ul className="mt-2 space-y-1" aria-label="What NOVA did">
      {items.map((e) => {
        const s = STATUS_LABELS[e.status] ?? { label: e.status }
        return (
          <li
            key={e.id}
            className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground"
          >
            <Wrench className="size-3" aria-hidden="true" />
            <code>{e.tool}</code>
            <Badge variant={s.variant}>{s.label}</Badge>
            <span>{e.error ?? e.summary}</span>
          </li>
        )
      })}
    </ul>
  )
}

function Feedback({ message, conversationId }) {
  const feedback = useFeedback(conversationId)
  const [asking, setAsking] = useState(false)
  const [comment, setComment] = useState('')
  const rate = (rating, text) =>
    feedback.mutate(
      { messageId: message.id, rating, comment: text },
      { onSuccess: () => setAsking(false) },
    )
  return (
    <div className="mt-1 space-y-1">
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          aria-label="Helpful"
          aria-pressed={message.rating === 1}
          className={message.rating === 1 ? 'text-success' : ''}
          onClick={() => rate(1)}
        >
          <ThumbsUp aria-hidden="true" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          aria-label="Not helpful"
          aria-pressed={message.rating === -1}
          className={message.rating === -1 ? 'text-destructive' : ''}
          onClick={() => setAsking(true)}
        >
          <ThumbsDown aria-hidden="true" />
        </Button>
        {feedback.isSuccess && (
          <span className="text-[10px] text-muted-foreground">Thanks, noted.</span>
        )}
      </div>
      {asking && (
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            rate(-1, comment.trim())
          }}
        >
          <Label htmlFor={`fb-${message.id}`} className="sr-only">
            What should NOVA do differently?
          </Label>
          <Input
            id={`fb-${message.id}`}
            maxLength={500}
            placeholder="What should NOVA do differently? (it will remember)"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
          <Button type="submit" size="sm" loading={feedback.isPending}>
            Send
          </Button>
        </form>
      )}
      {feedback.isError && <p className="text-xs text-destructive">{feedback.error.message}</p>}
    </div>
  )
}

function Message({ message, executions, approvals, timeZone, conversationId }) {
  const mine = message.role === 'user'
  return (
    <li className={cn('flex', mine ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[85%] rounded-lg px-3 py-2 text-sm',
          mine ? 'bg-primary/20' : 'border bg-card',
          message.status === 'error' && 'border-destructive/50',
        )}
      >
        {!mine && (
          <p className="mb-1 flex items-center gap-1 text-xs font-medium text-accent">
            <Bot className="size-3" aria-hidden="true" /> NOVA
          </p>
        )}
        <p className="whitespace-pre-wrap">{message.content}</p>
        {message.links?.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {message.links.map((l) => (
              <Link
                key={l.href}
                to={l.href}
                className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs hover:border-accent"
              >
                {l.label} <ExternalLink className="size-3" aria-hidden="true" />
              </Link>
            ))}
          </div>
        )}
        {!mine && <Executions items={executions} />}
        {approvals?.length > 0 && (
          <div className="mt-2 space-y-2">
            {approvals.map((a) => (
              <ApprovalCard key={a.id} approval={a} timeZone={timeZone} />
            ))}
          </div>
        )}
        {!mine && <Feedback message={message} conversationId={conversationId} />}
        <p className="mt-1 text-[10px] text-muted-foreground">
          {message.via === 'voice' ? 'Spoken · ' : ''}
          {new Date(message.created_at).toLocaleTimeString(undefined, {
            timeZone,
            hour: '2-digit',
            minute: '2-digit',
          })}
        </p>
      </div>
    </li>
  )
}

function groupExecutions(messages, executions) {
  const byMessage = {}
  let previous = ''
  for (const m of messages) {
    if (m.role !== 'assistant') continue
    byMessage[m.id] = executions.filter(
      (e) => e.created_at > previous && e.created_at <= m.created_at,
    )
    previous = m.created_at
  }
  return byMessage
}

function Thread({ conversationId, timeZone, extraApprovals, pending }) {
  const { data, isPending, isError, error, refetch } = useConversation(conversationId)
  const end = useRef(null)
  const count = data?.messages.length ?? 0
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: 'end' })
  }, [count, pending])
  if (!conversationId) return null
  if (isPending) return <LoadingState label="Loading conversation…" />
  if (isError)
    return <ErrorState title="Couldn't load conversation" error={error} onRetry={refetch} />
  const executions = groupExecutions(data.messages, data.executions)
  return (
    <ol className="space-y-3" aria-live="polite">
      {data.messages.map((m) => (
        <Message
          key={m.id}
          message={m}
          executions={executions[m.id]}
          approvals={extraApprovals[m.id]}
          timeZone={timeZone}
          conversationId={conversationId}
        />
      ))}
      {pending && (
        <li className="text-sm text-muted-foreground" role="status">
          NOVA is working…
        </li>
      )}
      <li ref={end} aria-hidden="true" />
    </ol>
  )
}

function Usage() {
  const { data } = useNovaUsage()
  if (!data) return null
  const tokens = data.prompt_tokens + data.completion_tokens
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Usage · last {data.window_days} days</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1 text-xs text-muted-foreground">
        <p>
          {formatNumber(data.replies)} replies · {formatNumber(tokens)} tokens
          {data.scope === 'company' ? ' (whole company)' : ''}
        </p>
        {data.cost_usd != null && <p>Estimated cost: ${data.cost_usd.toFixed(2)}</p>}
        {data.avg_latency_ms > 0 && (
          <p>Average response: {(data.avg_latency_ms / 1000).toFixed(1)} s</p>
        )}
        {data.provider_errors > 0 && (
          <p className="text-destructive">{data.provider_errors} provider errors</p>
        )}
        <p>Daily limit per person: {formatNumber(data.daily_token_limit)} tokens</p>
      </CardContent>
    </Card>
  )
}

function Composer({ conversationId, onCreated, onReply, onPending, speakReplies, voiceOut }) {
  const [text, setText] = useState('')
  const [via, setVia] = useState('text')
  const create = useCreateConversation()
  const send = useSendMessage()
  useEffect(() => {
    onPending(send.isPending)
  }, [send.isPending, onPending])
  const voiceIn = useSpeechInput({
    onFinal: (transcript) => {
      setText((t) => (t ? `${t} ${transcript}` : transcript))
      setVia('voice')
    },
  })

  const submit = async (content = text) => {
    const body = { content: content.trim(), via }
    if (!body.content) return
    let id = conversationId
    if (!id) {
      id = (await create.mutateAsync()).id
      onCreated(id)
    }
    setText('')
    send.mutate(
      { conversationId: id, ...body },
      {
        onSuccess: (reply) => {
          setVia('text')
          onReply(reply)
          if (speakReplies) voiceOut.speak(reply.message.content)
        },
        onError: () => setText(body.content),
      },
    )
  }
  const busy = send.isPending || create.isPending
  const startTalking = () => {
    voiceOut.cancel()
    voiceIn.start()
  }

  return (
    <form
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
    >
      {(send.isError || create.isError) && (
        <Alert variant="error" title={(send.error ?? create.error).message} />
      )}
      {voiceIn.error && <Alert variant="error" title={voiceIn.error} />}
      {voiceIn.listening && (
        <p role="status" className="flex items-center gap-2 text-sm text-destructive">
          <span className="size-2 animate-pulse rounded-full bg-destructive" aria-hidden="true" />
          Listening… {voiceIn.interim}
        </p>
      )}
      {via === 'voice' && !voiceIn.listening && text && (
        <p className="text-xs text-muted-foreground">
          Check the transcript, then send. Actions from voice are shown for confirmation first.
        </p>
      )}
      <Label htmlFor="nova-input" className="sr-only">
        Message NOVA
      </Label>
      <Textarea
        id="nova-input"
        rows={3}
        value={text}
        placeholder="Ask NOVA about your work, customers, tickets or reports…"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            submit()
          }
        }}
      />
      <div className="flex flex-wrap items-center gap-2">
        {voiceIn.supported ? (
          <Button
            type="button"
            variant={voiceIn.listening ? 'destructive' : 'outline'}
            size="sm"
            aria-pressed={voiceIn.listening}
            title="Hold to talk (or press and hold Space on this button)"
            onPointerDown={startTalking}
            onPointerUp={voiceIn.stop}
            onPointerLeave={() => voiceIn.listening && voiceIn.stop()}
            onKeyDown={(e) => {
              if (e.key === ' ' && !e.repeat) {
                e.preventDefault()
                startTalking()
              }
            }}
            onKeyUp={(e) => e.key === ' ' && voiceIn.stop()}
          >
            {voiceIn.listening ? <MicOff aria-hidden="true" /> : <Mic aria-hidden="true" />}
            {voiceIn.listening ? 'Release to stop' : 'Hold to talk'}
          </Button>
        ) : (
          <span className="text-xs text-muted-foreground">
            Voice input isn't supported in this browser. Type instead.
          </span>
        )}
        <Button type="submit" size="sm" className="ml-auto" loading={busy} disabled={!text.trim()}>
          <Send aria-hidden="true" /> Send
        </Button>
      </div>
      {!conversationId && (
        <div className="flex flex-wrap gap-2 pt-1">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              className="rounded-full border px-3 py-1 text-xs text-muted-foreground hover:border-accent hover:text-foreground"
              onClick={() => submit(s)}
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </form>
  )
}

export function NovaPage() {
  const { data: me } = useMe()
  const timeZone = me.company.timezone
  const [params, setParams] = useSearchParams()
  const conversationId = params.get('c')
  const status = useNovaStatus()
  const profile = useNovaProfile()
  const conversations = useConversations()
  const remove = useDeleteConversation()
  const pendingApprovals = useApprovals('pending')
  const voiceOut = useSpeechOutput()
  const [speakReplies, setSpeakReplies] = useState(false)
  const [extraApprovals, setExtraApprovals] = useState({})
  const [sending, setSending] = useState(false)
  const open = (id) => setParams(id ? { c: id } : {})
  const decidable = (pendingApprovals.data ?? []).filter((a) => a.can_decide).length

  return (
    <div className="grid gap-4 lg:grid-cols-[16rem_minmax(0,1fr)]">
      <aside className="space-y-3">
        <Button className="w-full" onClick={() => open(null)}>
          <Plus aria-hidden="true" /> New conversation
        </Button>
        <Link
          to="/app/nova/approvals"
          className="flex items-center justify-between rounded-md border px-3 py-2 text-sm hover:border-accent"
        >
          <span className="flex items-center gap-2">
            <ShieldCheck className="size-4" aria-hidden="true" /> Approvals
          </span>
          {decidable > 0 && <Badge variant="warning">{decidable}</Badge>}
        </Link>
        <Link
          to="/app/nova/memory"
          className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm hover:border-accent"
        >
          <Brain className="size-4" aria-hidden="true" /> About you
        </Link>
        <nav aria-label="Conversations" className="space-y-1">
          {(conversations.data ?? []).map((c) => (
            <div
              key={c.id}
              className={cn(
                'group flex items-center gap-1 rounded-md',
                c.id === conversationId ? 'bg-primary/15' : 'hover:bg-muted',
              )}
            >
              <button
                type="button"
                className="min-w-0 flex-1 truncate px-3 py-2 text-left text-sm"
                aria-current={c.id === conversationId ? 'page' : undefined}
                onClick={() => open(c.id)}
              >
                {c.title}
              </button>
              <Button
                variant="ghost"
                size="sm"
                aria-label={`Delete conversation ${c.title}`}
                className="opacity-60 group-hover:opacity-100"
                onClick={() =>
                  remove.mutate(c.id, { onSuccess: () => c.id === conversationId && open(null) })
                }
              >
                <Trash2 aria-hidden="true" />
              </Button>
            </div>
          ))}
        </nav>
        <Usage />
      </aside>

      <section className="flex min-h-[70vh] flex-col rounded-lg border bg-navy-900/40">
        <header className="flex flex-wrap items-center gap-2 border-b px-4 py-3">
          <h1 className="flex items-center gap-2 text-lg font-semibold">
            <Bot className="size-5 text-accent" aria-hidden="true" /> NOVA
          </h1>
          <ModeBadge status={status.data} />
          <div className="ml-auto flex items-center gap-2">
            {voiceOut.supported && (
              <Button
                variant="ghost"
                size="sm"
                aria-pressed={speakReplies}
                onClick={() => {
                  if (speakReplies) voiceOut.cancel()
                  setSpeakReplies(!speakReplies)
                }}
              >
                {speakReplies ? <Volume2 aria-hidden="true" /> : <VolumeX aria-hidden="true" />}
                {speakReplies ? 'Reading replies aloud' : 'Read replies aloud'}
              </Button>
            )}
            {voiceOut.speaking && (
              <Button variant="outline" size="sm" onClick={voiceOut.cancel}>
                Stop speaking
              </Button>
            )}
          </div>
        </header>
        <div className="flex-1 overflow-y-auto p-4">
          {conversationId ? (
            <Thread
              conversationId={conversationId}
              timeZone={timeZone}
              extraApprovals={extraApprovals}
              pending={sending}
            />
          ) : (
            <div className="mx-auto max-w-xl space-y-3 py-10 text-center">
              <Bot className="mx-auto size-10 text-accent" aria-hidden="true" />
              <p className="text-lg font-medium">
                Hi {profile.data?.preferred_name || me.user.full_name.split(' ')[0]}, how can I
                help?
              </p>
              <p className="text-sm text-muted-foreground">
                I only see what your role allows. Anything sensitive waits for confirmation or an
                administrator&apos;s approval, and every action is recorded.
              </p>
              {status.data?.mode === 'basic' && (
                <Alert title="Basic mode">
                  No AI model is configured yet, so NOVA answers look-ups straight from Orbit
                  records. An administrator can enable full NOVA by setting NOVA_PROVIDER,
                  NOVA_MODEL and NOVA_API_KEY on the server.
                </Alert>
              )}
            </div>
          )}
        </div>
        <div className="border-t p-4">
          <Composer
            conversationId={conversationId}
            onCreated={open}
            onPending={setSending}
            onReply={(reply) => {
              if (reply.approvals?.length)
                setExtraApprovals((prev) => ({ ...prev, [reply.message.id]: reply.approvals }))
            }}
            speakReplies={speakReplies}
            voiceOut={voiceOut}
          />
        </div>
      </section>
    </div>
  )
}
