import { ArrowLeft, Copy, Pause, Play, RefreshCw, Stethoscope } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ConfirmButton } from '@/components/ui/confirm-button'
import { Input, Label } from '@/components/ui/input'
import { ErrorState, LoadingState, Skeleton } from '@/components/ui/states'
import { useMe, usePermissions } from '@/features/auth/hooks'
import { formatDateTime } from '@/lib/utils'
import {
  connectionHealth,
  useIntegration,
  useIntegrationActions,
  useIntegrationRuns,
  useProviders,
} from './api'
import { ConfigFields } from './IntegrationsPage'

const RUN_VARIANT = { success: 'success', failed: 'destructive', running: 'accent' }

function Runs({ id, timeZone }) {
  const { data, isPending, isError, error, refetch } = useIntegrationRuns(id)
  if (isPending) return <Skeleton className="h-24" />
  if (isError)
    return <ErrorState title="Couldn't load sync history" error={error} onRetry={refetch} />
  if (data.length === 0) return <p className="text-sm text-muted-foreground">No syncs yet.</p>
  return (
    <ul className="divide-y">
      {data.map((run) => (
        <li key={run.id} className="py-2.5 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={RUN_VARIANT[run.status]}>{run.status}</Badge>
            <span className="text-muted-foreground">
              {formatDateTime(run.started_at, timeZone)} · {run.trigger}
            </span>
          </div>
          {Object.keys(run.summary ?? {}).length > 0 && (
            <p className="mt-1 text-xs text-muted-foreground">
              {Object.entries(run.summary)
                .map(([k, v]) => `${k.replaceAll('_', ' ')}: ${v}`)
                .join(' · ')}
            </p>
          )}
          {run.error && <p className="mt-1 text-xs text-destructive">{run.error}</p>}
        </li>
      ))}
    </ul>
  )
}

function SettingsForm({ connection, provider }) {
  const { update } = useIntegrationActions(connection.id)
  const [name, setName] = useState(connection.name)
  const [config, setConfig] = useState(connection.config)
  const [secretRef, setSecretRef] = useState(connection.secret_ref ?? '')
  const [webhookRef, setWebhookRef] = useState(connection.webhook_secret_ref ?? '')
  const [syncInterval, setSyncInterval] = useState(connection.sync_interval_minutes)
  return (
    <form
      className="grid gap-4 md:grid-cols-2"
      onSubmit={(e) => {
        e.preventDefault()
        update.mutate({
          name: name.trim(),
          config,
          secret_ref: secretRef.trim() || null,
          webhook_secret_ref: webhookRef.trim() || null,
          sync_interval_minutes: Number(syncInterval),
        })
      }}
    >
      {update.isError && (
        <div className="md:col-span-2">
          <Alert variant="error" title={update.error.message} />
        </div>
      )}
      {update.isSuccess && (
        <div className="md:col-span-2">
          <Alert variant="success" title="Saved" />
        </div>
      )}
      <div className="space-y-1.5">
        <Label htmlFor="edit-name">Connection name</Label>
        <Input id="edit-name" value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="edit-interval">Sync every (minutes)</Label>
        <Input
          id="edit-interval"
          type="number"
          min={5}
          max={1440}
          value={syncInterval}
          onChange={(e) => setSyncInterval(e.target.value)}
        />
      </div>
      <ConfigFields provider={provider} values={config} onChange={setConfig} idPrefix="edit" />
      <div className="space-y-1.5">
        <Label htmlFor="edit-secret">Credential variable</Label>
        <Input
          id="edit-secret"
          value={secretRef}
          onChange={(e) => setSecretRef(e.target.value.toUpperCase())}
        />
      </div>
      {provider.supports_webhooks && (
        <div className="space-y-1.5">
          <Label htmlFor="edit-webhook">Webhook signing variable</Label>
          <Input
            id="edit-webhook"
            value={webhookRef}
            onChange={(e) => setWebhookRef(e.target.value.toUpperCase())}
          />
        </div>
      )}
      <div className="md:col-span-2">
        <Button type="submit" loading={update.isPending}>
          Save changes
        </Button>
      </div>
    </form>
  )
}

export function IntegrationDetailPage() {
  const { integrationId } = useParams()
  const navigate = useNavigate()
  const { data: me } = useMe()
  const { has } = usePermissions()
  const timeZone = me.company.timezone
  const { data: c, isPending, isError, error, refetch } = useIntegration(integrationId)
  const providers = useProviders()
  const actions = useIntegrationActions(integrationId)
  const [copied, setCopied] = useState(false)

  if (isPending) return <LoadingState label="Loading integration…" />
  if (isError)
    return <ErrorState title="Couldn't load integration" error={error} onRetry={refetch} />

  const provider = providers.data?.find((p) => p.provider === c.provider)
  const health = connectionHealth(c)
  const canOperate = has('integration.update')
  const testResult = actions.test.data

  return (
    <>
      <Link
        to="/app/integrations"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> Integrations
      </Link>
      <PageHeader
        title={c.name}
        description={`${c.provider_label} · ${c.product?.name ?? 'Company-wide'}`}
        actions={
          canOperate && (
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                loading={actions.test.isPending}
                onClick={() => actions.test.mutate()}
              >
                <Stethoscope aria-hidden="true" /> Test connection
              </Button>
              <Button
                size="sm"
                disabled={c.status === 'paused'}
                loading={actions.sync.isPending}
                onClick={() => actions.sync.mutate()}
              >
                <RefreshCw aria-hidden="true" /> Sync now
              </Button>
            </div>
          )
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Badge variant={health.variant}>{health.label}</Badge>
        {c.capabilities.map((cap) => (
          <Badge key={cap}>{cap.replaceAll('_', ' ')}</Badge>
        ))}
      </div>
      {testResult && (
        <div className="mb-4">
          <Alert
            variant={testResult.ok ? 'success' : 'error'}
            title={testResult.ok ? 'Connection works' : 'Connection failed'}
          >
            {testResult.message}
          </Alert>
        </div>
      )}
      {[actions.test, actions.sync, actions.update, actions.remove]
        .filter((m) => m.isError)
        .map((m) => (
          <div key={m.error.message} className="mb-4">
            <Alert variant="error" title={m.error.message} />
          </div>
        ))}
      {actions.sync.data?.status === 'failed' && (
        <div className="mb-4">
          <Alert variant="error" title="Sync failed">
            {actions.sync.data.error}
          </Alert>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <p>
                <span className="text-muted-foreground">Last successful sync: </span>
                {c.last_success_at ? formatDateTime(c.last_success_at, timeZone) : 'Never'}
              </p>
              <p>
                <span className="text-muted-foreground">Last attempt: </span>
                {c.last_sync_at ? formatDateTime(c.last_sync_at, timeZone) : 'Never'}
              </p>
              <p>
                <span className="text-muted-foreground">Schedule: </span>every{' '}
                {c.sync_interval_minutes} minutes
              </p>
              {c.last_error && (
                <Alert variant="error" title="Last error">
                  {c.last_error}
                </Alert>
              )}
              {c.webhook_url && (
                <div className="space-y-1.5 pt-2">
                  <Label htmlFor="webhook-url">Webhook URL</Label>
                  <div className="flex gap-2">
                    <Input id="webhook-url" readOnly value={c.webhook_url} />
                    <Button
                      variant="outline"
                      size="sm"
                      aria-label="Copy webhook URL"
                      onClick={() => {
                        navigator.clipboard?.writeText(c.webhook_url)
                        setCopied(true)
                      }}
                    >
                      <Copy aria-hidden="true" /> {copied ? 'Copied' : 'Copy'}
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Deliveries are rejected unless signed with the secret in{' '}
                    {c.webhook_secret_ref ?? 'a webhook signing variable (not configured)'}.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
          {c.can_manage && provider && (
            <Card>
              <CardHeader>
                <CardTitle>Settings</CardTitle>
                <CardDescription>{provider.secret_help}</CardDescription>
              </CardHeader>
              <CardContent>
                <SettingsForm key={c.id} connection={c} provider={provider} />
              </CardContent>
            </Card>
          )}
        </div>
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Sync history</CardTitle>
            </CardHeader>
            <CardContent>
              <Runs id={c.id} timeZone={timeZone} />
            </CardContent>
          </Card>
          {c.can_manage && (
            <Card>
              <CardHeader>
                <CardTitle>Manage</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  loading={actions.update.isPending}
                  onClick={() =>
                    actions.update.mutate({ status: c.status === 'paused' ? 'active' : 'paused' })
                  }
                >
                  {c.status === 'paused' ? (
                    <>
                      <Play aria-hidden="true" /> Resume
                    </>
                  ) : (
                    <>
                      <Pause aria-hidden="true" /> Pause
                    </>
                  )}
                </Button>
                {has('integration.delete') && (
                  <ConfirmButton
                    confirmLabel="Confirm disconnect"
                    loading={actions.remove.isPending}
                    onConfirm={() =>
                      actions.remove.mutate(undefined, {
                        onSuccess: () => navigate('/app/integrations'),
                      })
                    }
                  >
                    Disconnect
                  </ConfirmButton>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </>
  )
}
