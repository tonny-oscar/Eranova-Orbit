import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ME_QUERY_KEY } from '@/app/queryClient'
import { changePassword, devLogin, fetchDevLoginStatus, fetchMe, login, logout } from './api'

export function useDevLoginStatus({ enabled = true } = {}) {
  return useQuery({
    queryKey: ['auth', 'dev-login'],
    queryFn: ({ signal }) => fetchDevLoginStatus({ signal }),
    enabled,
    staleTime: Infinity,
    retry: false,
  })
}

export function useDevLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: devLogin,
    onSuccess: (me) => queryClient.setQueryData(ME_QUERY_KEY, me),
  })
}

export function useMe() {
  return useQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: ({ signal }) => fetchMe({ signal }),
    staleTime: 60_000,
  })
}

export function usePermissions() {
  const { data: me } = useMe()
  const permissions = new Set(me?.permissions ?? [])
  return {
    has: (permission) => permissions.has(permission),
    permissions,
  }
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: login,
    onSuccess: (me) => {
      queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== ME_QUERY_KEY[0] })
      queryClient.setQueryData(ME_QUERY_KEY, me)
    },
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: logout,
    onSettled: () => {
      queryClient.clear()
      queryClient.setQueryData(ME_QUERY_KEY, null)
    },
  })
}

export function useChangePassword() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: changePassword,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ME_QUERY_KEY }),
  })
}
