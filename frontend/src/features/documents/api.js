import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiRequest } from '@/lib/api/client'

export const CATEGORIES = [
  { value: 'contract', label: 'Contract' },
  { value: 'policy', label: 'Policy' },
  { value: 'proposal', label: 'Proposal' },
  { value: 'minutes', label: 'Minutes' },
  { value: 'product_doc', label: 'Product documentation' },
  { value: 'report', label: 'Report' },
  { value: 'asset', label: 'Asset' },
  { value: 'other', label: 'Other' },
]
export const CATEGORY = Object.fromEntries(CATEGORIES.map((c) => [c.value, c.label]))
export const ACCEPT =
  '.pdf,.docx,.xlsx,.pptx,.odt,.ods,.odp,.doc,.xls,.ppt,.png,.jpg,.jpeg,.webp,.csv,.txt,.md'
export const MAX_BYTES = 10 * 1024 * 1024

export function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export const downloadUrl = (id, version) =>
  `/api/v1/documents/${id}/download${version ? `?version=${version}` : ''}`

export function useDocuments(filters) {
  return useQuery({
    queryKey: ['documents', 'list', filters],
    queryFn: ({ signal }) => apiRequest('/api/v1/documents', { query: filters, signal }),
    placeholderData: keepPreviousData,
  })
}

export function useDocument(id) {
  return useQuery({
    queryKey: ['documents', 'detail', id],
    queryFn: ({ signal }) => apiRequest(`/api/v1/documents/${id}`, { signal }),
  })
}

function useDocumentMutation(mutationFn) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: (doc) => {
      if (doc?.id) queryClient.setQueryData(['documents', 'detail', doc.id], doc)
      queryClient.invalidateQueries({ queryKey: ['documents', 'list'] })
    },
  })
}

export function useUploadDocument() {
  return useDocumentMutation((form) =>
    apiRequest('/api/v1/documents', { method: 'POST', body: form }),
  )
}

export function useDocumentActions(id) {
  const base = `/api/v1/documents/${id}`
  return {
    update: useDocumentMutation((body) => apiRequest(base, { method: 'PATCH', body })),
    addVersion: useDocumentMutation((form) =>
      apiRequest(`${base}/versions`, { method: 'POST', body: form }),
    ),
    setMembers: useDocumentMutation((userIds) =>
      apiRequest(`${base}/members`, { method: 'PUT', body: { user_ids: userIds } }),
    ),
    remove: useDocumentMutation(() => apiRequest(base, { method: 'DELETE' })),
  }
}
