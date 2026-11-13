import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiRequest } from '@/lib/api/client'

export const CUSTOMER_STATUSES = [
  { value: 'prospect', label: 'Prospect', variant: 'accent' },
  { value: 'active', label: 'Active', variant: 'success' },
  { value: 'paused', label: 'Paused', variant: 'warning' },
  { value: 'churned', label: 'Churned', variant: 'destructive' },
]
export const CUSTOMER_STATUS = Object.fromEntries(CUSTOMER_STATUSES.map((s) => [s.value, s]))
export const SUBSCRIPTION_STATUSES = ['trial', 'active', 'cancelled', 'expired']

export function useCustomers(filters) {
  return useQuery({
    queryKey: ['customers', 'list', filters],
    queryFn: ({ signal }) => apiRequest('/api/v1/customers', { query: filters, signal }),
    placeholderData: keepPreviousData,
  })
}

export function useCustomer(id) {
  return useQuery({
    queryKey: ['customers', 'detail', id],
    queryFn: ({ signal }) => apiRequest(`/api/v1/customers/${id}`, { signal }),
  })
}

function useCustomerMutation(mutationFn) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: (customer) => {
      if (customer?.id) queryClient.setQueryData(['customers', 'detail', customer.id], customer)
      queryClient.invalidateQueries({ queryKey: ['customers', 'list'] })
    },
  })
}

export function useCreateCustomer() {
  return useCustomerMutation((payload) =>
    apiRequest('/api/v1/customers', { method: 'POST', body: payload }),
  )
}

export function useCustomerActions(id) {
  const base = `/api/v1/customers/${id}`
  return {
    update: useCustomerMutation((payload) => apiRequest(base, { method: 'PATCH', body: payload })),
    addContact: useCustomerMutation((payload) =>
      apiRequest(`${base}/contacts`, { method: 'POST', body: payload }),
    ),
    removeContact: useCustomerMutation((contactId) =>
      apiRequest(`${base}/contacts/${contactId}`, { method: 'DELETE' }),
    ),
    setSubscription: useCustomerMutation((payload) =>
      apiRequest(`${base}/subscriptions`, { method: 'PUT', body: payload }),
    ),
    removeSubscription: useCustomerMutation((subId) =>
      apiRequest(`${base}/subscriptions/${subId}`, { method: 'DELETE' }),
    ),
    addActivity: useCustomerMutation((payload) =>
      apiRequest(`${base}/activities`, { method: 'POST', body: payload }),
    ),
  }
}
