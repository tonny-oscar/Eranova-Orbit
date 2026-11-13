import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiRequest } from '@/lib/api/client'

export const TASK_STATUS = {
  created: { label: 'Created', variant: 'default' },
  assigned: { label: 'Assigned', variant: 'accent' },
  in_progress: { label: 'In progress', variant: 'accent' },
  submitted: { label: 'Submitted for review', variant: 'warning' },
  under_review: { label: 'Under review', variant: 'warning' },
  revision_requested: { label: 'Revision requested', variant: 'destructive' },
  approved: { label: 'Approved', variant: 'success' },
  completed: { label: 'Completed', variant: 'success' },
  cancelled: { label: 'Cancelled', variant: 'default' },
}
export const TRANSITION_LABELS = {
  in_progress: 'Start work',
  submitted: 'Submit for review',
  under_review: 'Start review',
  completed: 'Mark completed',
  cancelled: 'Cancel task',
}
export const PROJECT_STATUSES = ['planned', 'active', 'on_hold', 'completed', 'cancelled']
export const PRIORITIES = ['low', 'medium', 'high', 'critical']
export const LINK_KINDS = [
  { value: 'github_pr', label: 'Pull request' },
  { value: 'github_issue', label: 'GitHub issue' },
  { value: 'commit', label: 'Commit' },
  { value: 'deployment', label: 'Deployment' },
  { value: 'document', label: 'Document' },
  { value: 'attachment', label: 'File link' },
  { value: 'other', label: 'Other' },
]

export function useProjects(filters) {
  return useQuery({
    queryKey: ['projects', 'list', filters],
    queryFn: ({ signal }) => apiRequest('/api/v1/projects', { query: filters, signal }),
    placeholderData: keepPreviousData,
  })
}

export function useProject(id) {
  return useQuery({
    queryKey: ['projects', 'detail', id],
    queryFn: ({ signal }) => apiRequest(`/api/v1/projects/${id}`, { signal }),
  })
}

export function useTasks(filters, options = {}) {
  return useQuery({
    queryKey: ['tasks', 'list', filters],
    queryFn: ({ signal }) => apiRequest('/api/v1/tasks', { query: filters, signal }),
    placeholderData: keepPreviousData,
    ...options,
  })
}

export function useTask(id) {
  return useQuery({
    queryKey: ['tasks', 'detail', id],
    queryFn: ({ signal }) => apiRequest(`/api/v1/tasks/${id}`, { signal }),
  })
}

function useWorkMutation(mutationFn, detailKey) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: (data) => {
      if (data?.id && detailKey) queryClient.setQueryData([detailKey, 'detail', data.id], data)
      queryClient.invalidateQueries({ queryKey: ['tasks', 'list'] })
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      queryClient.invalidateQueries({ queryKey: ['me', 'work'] })
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
  })
}

export function useCreateProject() {
  return useWorkMutation(
    (payload) => apiRequest('/api/v1/projects', { method: 'POST', body: payload }),
    'projects',
  )
}

export function useProjectActions(id) {
  const base = `/api/v1/projects/${id}`
  return {
    update: useWorkMutation(
      (payload) => apiRequest(base, { method: 'PATCH', body: payload }),
      'projects',
    ),
    addMember: useWorkMutation(
      (payload) => apiRequest(`${base}/members`, { method: 'POST', body: payload }),
      'projects',
    ),
    removeMember: useWorkMutation(
      (memberId) => apiRequest(`${base}/members/${memberId}`, { method: 'DELETE' }),
      'projects',
    ),
    addMilestone: useWorkMutation(
      (payload) => apiRequest(`${base}/milestones`, { method: 'POST', body: payload }),
      'projects',
    ),
    updateMilestone: useWorkMutation(
      ({ id: milestoneId, ...payload }) =>
        apiRequest(`${base}/milestones/${milestoneId}`, { method: 'PUT', body: payload }),
      'projects',
    ),
  }
}

export function useCreateTask() {
  return useWorkMutation(
    (payload) => apiRequest('/api/v1/tasks', { method: 'POST', body: payload }),
    'tasks',
  )
}

export function useTaskActions(id) {
  const base = `/api/v1/tasks/${id}`
  return {
    update: useWorkMutation(
      (payload) => apiRequest(base, { method: 'PATCH', body: payload }),
      'tasks',
    ),
    transition: useWorkMutation(
      (payload) => apiRequest(`${base}/transition`, { method: 'POST', body: payload }),
      'tasks',
    ),
    review: useWorkMutation(
      (payload) => apiRequest(`${base}/review`, { method: 'POST', body: payload }),
      'tasks',
    ),
    comment: useWorkMutation(
      (body) => apiRequest(`${base}/comments`, { method: 'POST', body: { body } }),
      'tasks',
    ),
    addDependency: useWorkMutation(
      (dependsOn) =>
        apiRequest(`${base}/dependencies`, {
          method: 'POST',
          body: { depends_on_task_id: dependsOn },
        }),
      'tasks',
    ),
    removeDependency: useWorkMutation(
      (dependsOn) => apiRequest(`${base}/dependencies/${dependsOn}`, { method: 'DELETE' }),
      'tasks',
    ),
    addLink: useWorkMutation(
      (payload) => apiRequest(`${base}/links`, { method: 'POST', body: payload }),
      'tasks',
    ),
  }
}
