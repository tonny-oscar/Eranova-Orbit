import { QueryCache, QueryClient, MutationCache } from '@tanstack/react-query'
import { ApiError } from '@/lib/api/client'

export const ME_QUERY_KEY = ['auth', 'me']

function shouldRetry(failureCount, error) {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false
  return failureCount < 2
}

export function createQueryClient() {
  const client = new QueryClient({
    queryCache: new QueryCache({
      onError: (error) => handleUnauthenticated(client, error),
    }),
    mutationCache: new MutationCache({
      onError: (error) => handleUnauthenticated(client, error),
    }),
    defaultOptions: {
      queries: { retry: shouldRetry, staleTime: 30_000, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  })
  return client
}

// An expired or revoked session anywhere sends the user back to sign-in.
function handleUnauthenticated(client, error) {
  if (error instanceof ApiError && error.status === 401) {
    client.setQueryData(ME_QUERY_KEY, null)
  }
}
