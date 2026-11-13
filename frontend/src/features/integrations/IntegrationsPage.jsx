import { Plug, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states'
import { useProductOptions } from '@/features/admin/api'
import { RequirePermission } from '@/features/auth/guards'
import { useMe, usePermissions } from '@/features/auth/hooks'
import { formatDateTime } from '@/lib/utils'
import { connectionHealth, useCreateIntegration, useIntegrations, useProviders } from './api'

export function ConfigFields({ provider, values, onChange, idPrefix }) {
  return provider.config_fields.map((field) => (
    <div key={field.name} className="space-y-1.5">
      <Label htmlFor={`${idPrefix}-${field.name}`}>
        {field.label}
        {field.required ? '' : ' (optional)'}
      </Label>
      <Input
        id={`${idPrefix}-${field.name}`}
        type={field.kind === 'url' ? 'url' : 'text'}
        value={values[field.name] ?? ''}
        required={field.required}
        onChange={(e) => onChange({ ...values, [field.name]: e.target.value })}
      />
      {field.help && <p className="text-xs text-muted-foreground">{field.help}</p>}
    </div>
  ))
}

function NewIntegration({ providers, onClose }) {
  const navigate = useNavigate()
  const create = useCreateIntegration()
  const products = useProductOptions()
  const [providerKey, setProviderKey] = useState(providers[0]?.provider ?? '')
  const [name, setName] = useState('')
  const [productId, setProductId] = useState('')
  const [config, setConfig] = useState({})
  const [secretRef, setSecretRef] = useState('')
  const [webhookRef, setWebhookRef] = useState('')
  const [syncInterval, setSyncInterval] = useState(60)
  const provider = providers.find((p) => p.provider === providerKey)

  return (
    <Card className="mb-4">
      <CardHeader>
        <CardTitle>Connect a system</CardTitle>
        <CardDescription>
          Secrets are never entered here. Store each credential as an environment variable named
          <code className="mx-1">INTEGRATION_…</code>on the API server and reference it by name.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-4 md:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault()
            create.mutate(
              {
                provider: providerKey,
                name: name.trim(),
                product_id: productId || null,
                config,
                secret_ref: secretRef.trim() || null,
                webhook_secret_ref: webhookRef.trim() || null,
                sync_interval_minutes: Number(syncInterval),
              },
              { onSuccess: (c) => navigate(`/app/integrations/${c.id}`) },
            )
          }}
        >
          {create.isError && (
            <div className="md:col-span-2">
              <Alert variant="error" title={create.error.message} />
            </div>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="int-provider">System</Label>
            <Select
              id="int-provider"
              value={providerKey}
              onChange={(e) => {
                setProviderKey(e.target.value)
                setConfig({})
              }}
            >
              {providers.map((p) => (
                <option key={p.provider} value={p.provider}>
                  {p.label}
                </option>
              ))}
            </Select>
            {provider && <p className="text-xs text-muted-foreground">{provider.description}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="int-name">Connection name</Label>
            <Input
              id="int-name"
              value={name}
              placeholder="e.g. CRM production"
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="int-product">Product</Label>
            <Select
              id="int-product"
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
            >
              <option value="">Company-wide</option>
              {(products.data ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="int-interval">Sync every (minutes)</Label>
            <Input
              id="int-interval"
              type="number"
              min={5}
              max={1440}
              value={syncInterval}
              onChange={(e) => setSyncInterval(e.target.value)}
            />
          </div>
          {provider && (
            <ConfigFields provider={provider} values={config} onChange={setConfig} idPrefix="int" />
          )}
          {provider && (
            <div className="space-y-1.5">
              <Label htmlFor="int-secret">
                Credential variable{provider.secret_required ? '' : ' (optional)'}
              </Label>
              <Input
                id="int-secret"
                placeholder="INTEGRATION_CRM_API_KEY"
                value={secretRef}
                onChange={(e) => setSecretRef(e.target.value.toUpperCase())}
              />
              <p className="text-xs text-muted-foreground">{provider.secret_help}</p>
            </div>
          )}
          {provider?.supports_webhooks && (
            <div className="space-y-1.5">
              <Label htmlFor="int-webhook">Webhook signing variable (optional)</Label>
              <Input
                id="int-webhook"
                placeholder="INTEGRATION_CRM_WEBHOOK_SECRET"
                value={webhookRef}
                onChange={(e) => setWebhookRef(e.target.value.toUpperCase())}
              />
            </div>
          )}
          <div className="flex gap-2 md:col-span-2">
            <Button type="submit" loading={create.isPending} disabled={name.trim().length < 2}>
              Connect
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

function IntegrationsList() {
  const { has } = usePermissions()
  const { data: me } = useMe()
  const providers = useProviders()
  const { data, isPending, isError, error, refetch } = useIntegrations()
  const [creating, setCreating] = useState(false)

  return (
    <>
      <div className="mb-4 flex justify-end">
        {has('integration.manage') && !creating && providers.data && (
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus aria-hidden="true" /> Connect a system
          </Button>
        )}
      </div>
      {creating && providers.data && (
        <NewIntegration providers={providers.data} onClose={() => setCreating(false)} />
      )}
      {isPending && <LoadingState label="Loading integrations…" />}
      {isError && <ErrorState title="Couldn't load integrations" error={error} onRetry={refetch} />}
      {data?.length === 0 && (
        <EmptyState
          icon={Plug}
          title="Nothing connected yet"
          description="Connect your live products, repositories, deployments and analytics so Orbit can show real operational data."
        />
      )}
      {data?.length > 0 && (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {data.map((c) => {
            const health = connectionHealth(c)
            return (
              <Link key={c.id} to={`/app/integrations/${c.id}`} className="block">
                <Card className="h-full transition-colors hover:border-accent/60">
                  <CardContent className="space-y-2 pt-5">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="font-medium">{c.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {c.provider_label} · {c.product?.name ?? 'Company-wide'}
                        </p>
                      </div>
                      <Badge variant={health.variant}>{health.label}</Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {c.last_success_at
                        ? `Last success ${formatDateTime(c.last_success_at, me.company.timezone)}`
                        : 'No successful sync yet'}
                    </p>
                    {c.last_error && (
                      <p className="line-clamp-2 text-xs text-destructive">{c.last_error}</p>
                    )}
                  </CardContent>
                </Card>
              </Link>
            )
          })}
        </div>
      )}
    </>
  )
}

export function IntegrationsPage() {
  return (
    <>
      <PageHeader
        title="Integrations"
        description="Connections to your live products and the services they run on."
      />
      <RequirePermission permission="integration.read">
        <IntegrationsList />
      </RequirePermission>
    </>
  )
}
