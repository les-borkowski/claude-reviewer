import axios from 'axios'
import i18n from '../i18n'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type Status = 'to_do' | 'in_progress' | 'in_review' | 'in_testing' | 'done'
export type Priority = 'low' | 'medium' | 'high'
export type Role = 'manager' | 'contributor'
export type Theme = 'light' | 'dark' | 'system'
export type Locale = 'en-GB' | 'pl'
export type InvitationStatus = 'pending' | 'accepted' | 'declined' | 'expired'

export interface UserResponse {
  id: string
  email: string
  name: string
  role: Role
  created_at: string
  config?: UserConfigResponse
}

export interface ProjectResponse {
  id: string
  name: string
  description: string | null
  owner_id: string
  status: Status
  priority: Priority
  archived_at: string | null
  created_by: string
  created_at: string
}

export interface StoryResponse {
  id: string
  project_id: string
  title: string
  description: string | null
  status: Status
  priority: Priority
  created_by: string
  created_at: string
}

export interface TaskResponse {
  id: string
  project_id: string
  story_id: string | null
  title: string
  description: string | null
  status: Status
  priority: Priority
  assignee_id: string | null
  created_by: string
  created_at: string
}

export interface CommentResponse {
  id: string
  body: string
  author_id: string
  author_name: string
  created_at: string
  updated_at: string
}

export interface MemberResponse {
  user_id: string
  role: Role
  joined_at: string
  name: string
  email: string
}

export interface InvitationResponse {
  id: string
  project_id: string
  project_name: string
  invitee_email: string
  inviter_name: string
  role: Role
  status: InvitationStatus
  created_at: string
  expires_at: string
}

export interface RecentItemResponse {
  type: 'project' | 'story' | 'task'
  id: string
  title: string
  project_id: string
  story_id: string | null
  updated_at: string
}

export interface StatusHistoryEntry {
  id: string
  from_status: Status | null
  to_status: Status
  changed_by: string
  changed_by_name: string
  changed_at: string
  elapsed_seconds: number | null
}

export interface TimeMetrics {
  total_seconds: number
  by_status: Record<Status, number>
  history: StatusHistoryEntry[]
}

export interface ApiKeyResponse {
  id: string
  label: string
  scopes: string[]
  last_used_at: string | null
  created_at: string
}

export interface ApiKeyCreatedResponse extends ApiKeyResponse {
  key: string
}

export interface UserConfigResponse {
  theme: Theme
  locale: Locale
  display_preferences: Record<string, unknown>
}

export interface PaginatedResponse<T> {
  items: T[]
  next_cursor: string | null
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

// ---------------------------------------------------------------------------
// Token accessor — populated by AuthContext after creation
// ---------------------------------------------------------------------------

let _getAccessToken: () => string | null = () => null
let _refreshTokenFn: (() => Promise<string | null>) | null = null
let _onUnauthorized: (() => void) | null = null

export function setTokenAccessor(fn: () => string | null) {
  _getAccessToken = fn
}
export function setRefreshFn(fn: () => Promise<string | null>) {
  _refreshTokenFn = fn
}
export function setOnUnauthorized(fn: () => void) {
  _onUnauthorized = fn
}

// ---------------------------------------------------------------------------
// Axios instance
// ---------------------------------------------------------------------------

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = _getAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  config.headers['Accept-Language'] = i18n.language || 'en-GB'
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && !error.config._retried) {
      error.config._retried = true
      if (_refreshTokenFn) {
        const newToken = await _refreshTokenFn()
        if (newToken) {
          error.config.headers.Authorization = `Bearer ${newToken}`
          return api(error.config)
        }
      }
      _onUnauthorized?.()
    }
    return Promise.reject(error)
  }
)

// ---------------------------------------------------------------------------
// Auth API
// ---------------------------------------------------------------------------

export const authApi = {
  login: (email: string, password: string) =>
    api.post<TokenResponse>('/auth/login', { email, password }),
  register: (email: string, name: string, password: string) =>
    api.post<TokenResponse>('/auth/register', { email, name, password }),
  me: () => api.get<UserResponse>('/auth/me'),
  refresh: (refresh_token: string) =>
    api.post<TokenResponse>('/auth/refresh', { refresh_token }),
}

// ---------------------------------------------------------------------------
// Projects API
// ---------------------------------------------------------------------------

export const projectsApi = {
  list: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<ProjectResponse>>('/projects', { params }),
  create: (data: { name: string; description?: string; status?: Status; priority?: Priority }) =>
    api.post<ProjectResponse>('/projects', data),
  get: (id: string) => api.get<ProjectResponse>(`/projects/${id}`),
  update: (id: string, data: Partial<{ name: string; description: string; status: Status; priority: Priority }>) =>
    api.patch<ProjectResponse>(`/projects/${id}`, data),
  delete: (id: string) => api.delete(`/projects/${id}`),
  archive: (id: string) => api.post(`/projects/${id}/archive`),
  restore: (id: string) => api.post(`/projects/${id}/restore`),
  listMembers: (id: string) => api.get<MemberResponse[]>(`/projects/${id}/members`),
  addMember: (id: string, data: { user_id: string; role: Role }) =>
    api.post(`/projects/${id}/members`, data),
  updateMember: (id: string, userId: string, data: { role: Role }) =>
    api.patch(`/projects/${id}/members/${userId}`, data),
  removeMember: (id: string, userId: string) =>
    api.delete(`/projects/${id}/members/${userId}`),
}

// ---------------------------------------------------------------------------
// Stories API
// ---------------------------------------------------------------------------

export const storiesApi = {
  list: (projectId: string, params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<StoryResponse>>(`/projects/${projectId}/stories`, { params }),
  create: (projectId: string, data: { title: string; description?: string; status?: Status; priority?: Priority }) =>
    api.post<StoryResponse>(`/projects/${projectId}/stories`, data),
  get: (id: string) => api.get<StoryResponse>(`/stories/${id}`),
  update: (id: string, data: Partial<{ title: string; description: string; status: Status; priority: Priority }>) =>
    api.patch<StoryResponse>(`/stories/${id}`, data),
  delete: (id: string) => api.delete(`/stories/${id}`),
  move: (id: string, project_id: string) =>
    api.post(`/stories/${id}/move`, { project_id }),
}

// ---------------------------------------------------------------------------
// Tasks API
// ---------------------------------------------------------------------------

export const tasksApi = {
  list: (storyId: string, params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<TaskResponse>>(`/stories/${storyId}/tasks`, { params }),
  listForProject: (projectId: string, params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<TaskResponse>>(`/projects/${projectId}/tasks`, { params }),
  create: (storyId: string, data: { title: string; description?: string; status?: Status; priority?: Priority; assignee_id?: string }) =>
    api.post<TaskResponse>(`/stories/${storyId}/tasks`, data),
  createForProject: (projectId: string, data: { title: string; description?: string; status?: Status; priority?: Priority; assignee_id?: string }) =>
    api.post<TaskResponse>(`/projects/${projectId}/tasks`, data),
  get: (id: string) => api.get<TaskResponse>(`/tasks/${id}`),
  update: (id: string, data: Partial<{ title: string; description: string; status: Status; priority: Priority; assignee_id: string | null }>) =>
    api.patch<TaskResponse>(`/tasks/${id}`, data),
  delete: (id: string) => api.delete(`/tasks/${id}`),
}

// ---------------------------------------------------------------------------
// Comments API
// ---------------------------------------------------------------------------

export const commentsApi = {
  listForProject: (projectId: string) =>
    api.get<PaginatedResponse<CommentResponse>>(`/projects/${projectId}/comments`),
  listForStory: (storyId: string) =>
    api.get<PaginatedResponse<CommentResponse>>(`/stories/${storyId}/comments`),
  listForTask: (taskId: string) =>
    api.get<PaginatedResponse<CommentResponse>>(`/tasks/${taskId}/comments`),
  createForProject: (projectId: string, body: string) =>
    api.post<CommentResponse>(`/projects/${projectId}/comments`, { body }),
  createForStory: (storyId: string, body: string) =>
    api.post<CommentResponse>(`/stories/${storyId}/comments`, { body }),
  createForTask: (taskId: string, body: string) =>
    api.post<CommentResponse>(`/tasks/${taskId}/comments`, { body }),
  update: (id: string, body: string) =>
    api.patch<CommentResponse>(`/comments/${id}`, { body }),
  delete: (id: string) => api.delete(`/comments/${id}`),
}

// ---------------------------------------------------------------------------
// Invitations API
// ---------------------------------------------------------------------------

export const invitationsApi = {
  listForProject: (projectId: string) =>
    api.get<InvitationResponse[]>(`/projects/${projectId}/invitations`),
  create: (projectId: string, data: { invitee_email: string; role: Role }) =>
    api.post<InvitationResponse>(`/projects/${projectId}/invitations`, data),
  cancel: (id: string) => api.delete(`/invitations/${id}`),
  accept: (id: string) => api.post(`/invitations/${id}/accept`),
  decline: (id: string) => api.post(`/invitations/${id}/decline`),
  mine: () => api.get<InvitationResponse[]>('/invitations/mine'),
}

// ---------------------------------------------------------------------------
// Time Tracking API
// ---------------------------------------------------------------------------

export const timeTrackingApi = {
  historyForProject: (id: string) =>
    api.get<StatusHistoryEntry[]>(`/projects/${id}/status-history`),
  historyForStory: (id: string) =>
    api.get<StatusHistoryEntry[]>(`/stories/${id}/status-history`),
  historyForTask: (id: string) =>
    api.get<StatusHistoryEntry[]>(`/tasks/${id}/status-history`),
  metricsForProject: (id: string) =>
    api.get<TimeMetrics>(`/projects/${id}/time-metrics`),
  metricsForStory: (id: string) =>
    api.get<TimeMetrics>(`/stories/${id}/time-metrics`),
  metricsForTask: (id: string) =>
    api.get<TimeMetrics>(`/tasks/${id}/time-metrics`),
}

// ---------------------------------------------------------------------------
// Config API
// ---------------------------------------------------------------------------

export const configApi = {
  get: () => api.get<UserConfigResponse>('/config'),
  update: (data: Partial<{ theme: Theme; locale: Locale; display_preferences: Record<string, unknown> }>) =>
    api.patch<UserConfigResponse>('/config', data),
  listApiKeys: () => api.get<ApiKeyResponse[]>('/config/api-keys'),
  createApiKey: (data: { label: string; scopes: string[] }) =>
    api.post<ApiKeyCreatedResponse>('/config/api-keys', data),
  revokeApiKey: (id: string) => api.delete(`/config/api-keys/${id}`),
}

// ---------------------------------------------------------------------------
// Recent Items API
// ---------------------------------------------------------------------------

export const recentApi = {
  list: () => api.get<RecentItemResponse[]>('/recent'),
}

// ---------------------------------------------------------------------------
// Search API
// ---------------------------------------------------------------------------

export const searchApi = {
  search: (q: string) =>
    api.get<RecentItemResponse[]>('/search', { params: { q } }),
}
