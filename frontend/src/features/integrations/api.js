import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiRequest } from '@/lib/api/client'

export const PROVIDER_LABELS = {
  product_api: 'Eranova product API',
  github: 'GitHub',
  vercel: 'Vercel',
  ga4: 'Google Analytics 4',
  http_monitor: 'Uptime monitor',
}

export function useProviders() {
  return useQuery({
    queryKey: ['integrations', 'providers'],
    queryFn: ({ signal }) => apiRequest('/api/v1/integrations/providers', { signal }),
    staleTime: Infinity,
  })
}

export function useIntegrations(productId) {
  return useQuery({
    queryKey: ['integrations', 'list', productId ?? null],
    queryFn: ({ signal }) =>
      apiRequest('/api/v1/integrations', { query: { product_id: productId }, signal }),
  })
}

export function useIntegration(id) {
  return useQuery({
    queryKey: ['integrations', 'detail', id],
    queryFn: ({ signal }) => apiRequest(`/api/v1/integrations/${id}`, { signal }),
  })
}

export function useIntegrationRuns(id) {
  return useQuery({
    queryKey: ['integrations', 'runs', id],
    queryFn: ({ signal }) => apiRequest(`/api/v1/integrations/${id}/runs`, { signal }),
  })
}

export function useProductOperations(productId) {
  return useQuery({
    queryKey: ['integrations', 'operations', productId],
    queryFn: ({ signal }) => apiRequest(`/api/v1/products/${productId}/operations`, { signal }),
  })
}

export function useAnalyticsOverview() {
  return useQuery({
    queryKey: ['integrations', 'analytics'],
    queryFn: ({ signal }) => apiRequest('/api/v1/analytics/overview', { signal }),
  })
}

export function useMonitoringOverview() {
  return useQuery({
    queryKey: ['integrations', 'monitoring'],
    queryFn: ({ signal }) => apiRequest('/api/v1/monitoring/overview', { signal }),
    refetchInterval: 60_000,
  })
}

function useIntegrationMutation(mutationFn) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: (data) => {
      if (data?.id && data?.provider) {
        queryClient.setQueryData(['integrations', 'detail', data.id], data)
      }
      queryClient.invalidateQueries({ queryKey: ['integrations'] })
    },
  })
}

export function useCreateIntegration() {
  return useIntegrationMutation((payload) =>
    apiRequest('/api/v1/integrations', { method: 'POST', body: payload }),
  )
}

export function useIntegrationActions(id) {
  const base = `/api/v1/integrations/${id}`
  return {
    update: useIntegrationMutation((payload) =>
      apiRequest(base, { method: 'PATCH', body: payload }),
    ),
    test: useIntegrationMutation(() => apiRequest(`${base}/test`, { method: 'POST' })),
    sync: useIntegrationMutation(() => apiRequest(`${base}/sync`, { method: 'POST' })),
    remove: useIntegrationMutation(() => apiRequest(base, { method: 'DELETE' })),
  }
}

/** Human status for a connection: never claims "healthy" without a recent success. */
export function connectionHealth(c) {
  if (c.status === 'paused') return { label: 'Paused', variant: 'default' }
  if (c.status === 'error' || c.last_error) return { label: 'Failing', variant: 'destructive' }
  if (!c.last_success_at) return { label: 'Not synced yet', variant: 'warning' }
  if (c.is_stale ?? c.stale) return { label: 'Stale', variant: 'warning' }
  return { label: 'Healthy', variant: 'success' }
}
