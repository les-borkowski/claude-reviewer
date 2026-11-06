import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { tasksApi, projectsApi, storiesApi } from '../services/api'
import type { TaskResponse, StoryResponse, MemberResponse, Status, Priority } from '../services/api'
import { useRole } from '../hooks/useRole'
import { StatusPill } from '../components/common/StatusPill'
import { PriorityBars } from '../components/common/PriorityBars'
import { LoadMoreButton } from '../components/common/LoadMoreButton'
import { EmptyState } from '../components/common/EmptyState'
import { ConfirmDialog } from '../components/common/ConfirmDialog'
import { MarkdownEditor } from '../components/common/MarkdownEditor'
import { SkeletonCard } from '../components/common/Skeleton'
import { useToast } from '../context/ToastContext'
import { formatRelative } from '../utils/time'

const IPlus = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 5v14M5 12h14"/>
  </svg>
)

type SortField = 'created_at' | 'status' | 'priority' | 'title'
type SortDir = 'asc' | 'desc'

const STATUS_ORDER: Record<string, number> = { to_do: 0, in_progress: 1, in_review: 2, in_testing: 3, done: 4 }
const PRIORITY_ORDER: Record<string, number> = { low: 0, medium: 1, high: 2 }

function applySortField<T extends { created_at: string; status: string; priority: string; title: string }>(
  a: T, b: T, field: SortField
): number {
  if (field === 'status') return STATUS_ORDER[a.status] - STATUS_ORDER[b.status]
  if (field === 'priority') return PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]
  if (field === 'title') return a.title.localeCompare(b.title)
  return new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
}

function DetailField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[80px_1fr] items-center gap-3">
      <span className="text-[10.5px] uppercase tracking-wider text-stone-400 font-medium">{label}</span>
      <div>{children}</div>
    </div>
  )
}

export function BacklogPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { t } = useTranslation()
  const { isManager } = useRole(projectId)
  const { addToast } = useToast()

  const [projectName, setProjectName] = useState('')
  const [members, setMembers] = useState<MemberResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [tasks, setTasks] = useState<TaskResponse[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [isLoadingMore, setIsLoadingMore] = useState(false)

  const [showCreateTask, setShowCreateTask] = useState(false)
  const [newTaskTitle, setNewTaskTitle] = useState('')
  const [creatingTask, setCreatingTask] = useState(false)
  const [deleteTaskId, setDeleteTaskId] = useState<string | null>(null)
  const [editTask, setEditTask] = useState<{ id: string; title: string; description: string } | null>(null)
  const [savingTask, setSavingTask] = useState(false)
  const [editingTaskField, setEditingTaskField] = useState<{ id: string; field: 'status' | 'priority' } | null>(null)
  const [sortField, setSortField] = useState<SortField>('created_at')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [stories, setStories] = useState<StoryResponse[]>([])
  const [newTaskDescription, setNewTaskDescription] = useState('')
  const [newTaskStatus, setNewTaskStatus] = useState<Status>('to_do')
  const [newTaskPriority, setNewTaskPriority] = useState<Priority>('medium')
  const [newTaskAssigneeId, setNewTaskAssigneeId] = useState('')
  const [newTaskStoryId, setNewTaskStoryId] = useState('')

  const fetchTasks = useCallback(async () => {
    if (!projectId) return
    const res = await tasksApi.listForProject(projectId, { unassigned: true, limit: 25 })
    setTasks(res.data.items)
    setNextCursor(res.data.next_cursor ?? null)
  }, [projectId])

  useEffect(() => {
    if (!showCreateTask) return
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setShowCreateTask(false)
        setNewTaskTitle('')
        setNewTaskDescription('')
        setNewTaskStatus('to_do')
        setNewTaskPriority('medium')
        setNewTaskAssigneeId('')
        setNewTaskStoryId('')
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [showCreateTask])

  useEffect(() => {
    if (!projectId) return
    Promise.all([
      projectsApi.get(projectId).then((r) => setProjectName(r.data.name)),
      projectsApi.listMembers(projectId).then((r) => setMembers(r.data)),
      storiesApi.list(projectId).then((r) => setStories(r.data.items)),
      fetchTasks(),
    ]).finally(() => setLoading(false))
  }, [projectId, fetchTasks])

  const loadMore = async () => {
    if (!projectId || !nextCursor) return
    setIsLoadingMore(true)
    try {
      const res = await tasksApi.listForProject(projectId, { unassigned: true, limit: 25, cursor: nextCursor })
      setTasks(prev => [...prev, ...res.data.items])
      setNextCursor(res.data.next_cursor ?? null)
    } finally {
      setIsLoadingMore(false)
    }
  }

  const handleTaskFieldChange = async (taskId: string, field: 'status' | 'priority', value: string) => {
    await tasksApi.update(taskId, { [field]: value })
    setEditingTaskField(null)
    await fetchTasks()
    addToast(`${field === 'status' ? 'Status' : 'Priority'} updated`)
  }

  const handleSaveTask = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editTask) return
    setSavingTask(true)
    try {
      await tasksApi.update(editTask.id, { title: editTask.title, description: editTask.description || undefined })
      setEditTask(null)
      await fetchTasks()
      addToast('Task updated')
    } finally {
      setSavingTask(false)
    }
  }

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!projectId) return
    setCreatingTask(true)
    try {
      const data = {
        title: newTaskTitle,
        description: newTaskDescription || undefined,
        status: newTaskStatus,
        priority: newTaskPriority,
        assignee_id: newTaskAssigneeId || undefined,
      }
      if (newTaskStoryId) {
        await tasksApi.create(newTaskStoryId, data)
      } else {
        await tasksApi.createForProject(projectId, data)
      }
      setShowCreateTask(false)
      setNewTaskTitle('')
      setNewTaskDescription('')
      setNewTaskStatus('to_do')
      setNewTaskPriority('medium')
      setNewTaskAssigneeId('')
      setNewTaskStoryId('')
      await fetchTasks()
      addToast('Task created')
    } finally {
      setCreatingTask(false)
    }
  }

  const statuses: Status[] = ['to_do', 'in_progress', 'in_review', 'in_testing', 'done']
  const priorities: Priority[] = ['low', 'medium', 'high']

  if (loading) return (
    <div className="flex-1 flex flex-col">
      <div className="px-7 pt-6 pb-4">
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}</div>
      </div>
    </div>
  )

  const sortedTasks = [...tasks].sort((a, b) => {
    const c = applySortField(a, b, sortField)
    return sortDir === 'asc' ? c : -c
  })

  return (
    <div className="flex-1 flex flex-col">
      {/* Header */}
      <div className="px-7 pt-5 pb-4 border-b border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-950">
        <div className="flex items-center gap-2 text-[11.5px] text-stone-500 mb-2">
          <Link to="/projects" className="hover:text-stone-800 dark:hover:text-stone-200">{t('projects.title')}</Link>
          <span>/</span>
          <Link to={`/projects/${projectId}`} className="hover:text-stone-800 dark:hover:text-stone-200">{projectName || '…'}</Link>
          <span>/</span>
          <span>{t('stories.backlog')}</span>
        </div>
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <h1 className="text-[22px] font-semibold tracking-tight">{t('stories.backlog')}</h1>
            <p className="text-[13px] text-stone-500 mt-1">{t('tasks.no_story')}</p>
          </div>
          {isManager && (
            <button
              onClick={() => setShowCreateTask(true)}
              className="px-2.5 py-1.5 text-[12px] rounded-md accent-bg inline-flex items-center gap-1.5 shrink-0"
            >
              <IPlus /> {t('tasks.create')}
            </button>
          )}
        </div>
      </div>

      {/* Two-column layout */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_280px] min-h-0">
        {/* Main column */}
        <div className="px-7 py-5 overflow-y-auto">
          <section>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-[13px] font-medium text-stone-700 dark:text-stone-200">
                {t('tasks.title')} <span className="text-stone-400 font-normal ml-1">{tasks.length}</span>
              </h2>
              <div className="flex items-center gap-2">
                <select
                  value={sortField}
                  onChange={(e) => setSortField(e.target.value as SortField)}
                  className="text-[11px] px-2 py-1 rounded border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-900"
                >
                  <option value="created_at">{t('sort.created')}</option>
                  <option value="status">{t('sort.status')}</option>
                  <option value="priority">{t('sort.priority')}</option>
                  <option value="title">{t('sort.title')}</option>
                </select>
                <button
                  onClick={() => setSortDir(d => d === 'asc' ? 'desc' : 'asc')}
                  className="text-[11px] px-2 py-1 rounded border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-900"
                  aria-label={sortDir === 'asc' ? 'Sort descending' : 'Sort ascending'}
                >
                  {sortDir === 'asc' ? '↑' : '↓'}
                </button>
              </div>
            </div>

            {tasks.length === 0 ? (
              <EmptyState
                message={t('tasks.empty')}
                action={isManager ? { label: t('tasks.create'), onClick: () => setShowCreateTask(true) } : undefined}
              />
            ) : (
              <div className="rounded-lg border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 divide-y divide-stone-100 dark:divide-stone-800/80">
                {sortedTasks.map((task) => (
                  <div key={task.id} className="flex items-center gap-3 px-4 py-2.5 hover:bg-stone-50/80 dark:hover:bg-stone-800/50">
                    <div className="flex-1 min-w-0">
                      <Link
                        to={`/projects/${projectId}/tasks/${task.id}`}
                        className="text-[13px] font-medium hover:accent-text"
                      >
                        {task.title}
                      </Link>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {editingTaskField?.id === task.id && editingTaskField.field === 'priority' ? (
                        <select
                          autoFocus
                          defaultValue={task.priority}
                          onChange={(e) => handleTaskFieldChange(task.id, 'priority', e.target.value)}
                          onBlur={() => setEditingTaskField(null)}
                          className="text-[11px] px-2 py-1 rounded border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-900"
                        >
                          {priorities.map((p) => <option key={p} value={p}>{t(`priority.${p}`)}</option>)}
                        </select>
                      ) : (
                        <button onClick={() => setEditingTaskField({ id: task.id, field: 'priority' })}>
                          <PriorityBars priority={task.priority} />
                        </button>
                      )}
                      {editingTaskField?.id === task.id && editingTaskField.field === 'status' ? (
                        <select
                          autoFocus
                          defaultValue={task.status}
                          onChange={(e) => handleTaskFieldChange(task.id, 'status', e.target.value)}
                          onBlur={() => setEditingTaskField(null)}
                          className="text-[11px] px-2 py-1 rounded border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-900"
                        >
                          {statuses.map((s) => <option key={s} value={s}>{t(`status.${s}`)}</option>)}
                        </select>
                      ) : (
                        <button onClick={() => setEditingTaskField({ id: task.id, field: 'status' })}>
                          <StatusPill status={task.status} />
                        </button>
                      )}
                      {task.assignee_id && (() => {
                        const m = members.find(mem => mem.user_id === task.assignee_id)
                        if (!m) return null
                        const ini = m.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
                        return (
                          <span title={m.name} className="inline-flex items-center justify-center w-5 h-5 rounded-full av-2 text-white text-[9px] font-semibold">{ini}</span>
                        )
                      })()}
                      <span className="text-[11px] text-stone-400 w-10 text-right">{formatRelative(task.created_at)}</span>
                      {isManager && (
                        <div className="flex gap-2">
                          <button
                            onClick={() => setEditTask({ id: task.id, title: task.title, description: task.description ?? '' })}
                            className="text-[11px] text-stone-400 hover:text-stone-700 dark:hover:text-stone-200"
                          >
                            {t('actions.edit')}
                          </button>
                          <button onClick={() => setDeleteTaskId(task.id)} className="text-[11px] text-rose-400 hover:text-rose-600">
                            {t('actions.delete')}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {nextCursor && <LoadMoreButton onLoadMore={loadMore} isLoading={isLoadingMore} />}
          </section>
        </div>

        {/* Right rail */}
        <aside className="border-l border-stone-200 dark:border-stone-800 bg-stone-50/40 dark:bg-stone-950/30 px-5 py-5 space-y-5 text-[12.5px]">
          <DetailField label={t('detail.project')}>
            <Link to={`/projects/${projectId}`} className="accent-text hover:underline text-[12.5px]">
              {projectName}
            </Link>
          </DetailField>
          <DetailField label={t('tasks.title')}>
            <span className="text-stone-700 dark:text-stone-200">{tasks.length}</span>
          </DetailField>
        </aside>
      </div>

      {/* Modals */}
      {showCreateTask && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white dark:bg-stone-900 rounded-xl shadow-2xl border border-stone-200 dark:border-stone-800 p-6 w-[min(90vw,_900px)] min-w-[67vw] mx-4">
            <h3 className="text-[15px] font-semibold mb-5">{t('tasks.create')}</h3>
            <form onSubmit={handleCreateTask} className="space-y-4">
              <input
                type="text"
                placeholder={t('board.col_title')}
                value={newTaskTitle}
                onChange={(e) => setNewTaskTitle(e.target.value)}
                required
                autoFocus
                className="w-full px-3 py-2 rounded-md border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-950 text-[13px] focus-ring"
              />
              <MarkdownEditor
                value={newTaskDescription}
                onChange={setNewTaskDescription}
                rows={4}
                placeholder={t('tasks.description')}
                autoExpand
              />
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label htmlFor="backlog-create-task-status" className="text-[11.5px] font-medium text-stone-500">{t('filter.status')}</label>
                  <select
                    id="backlog-create-task-status"
                    value={newTaskStatus}
                    onChange={(e) => setNewTaskStatus(e.target.value as Status)}
                    className="w-full px-3 py-2 rounded-md border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-950 text-[13px]"
                  >
                    {statuses.map((s) => <option key={s} value={s}>{t(`status.${s}`)}</option>)}
                  </select>
                </div>
                <div className="space-y-1">
                  <label htmlFor="backlog-create-task-priority" className="text-[11.5px] font-medium text-stone-500">{t('filter.priority')}</label>
                  <select
                    id="backlog-create-task-priority"
                    value={newTaskPriority}
                    onChange={(e) => setNewTaskPriority(e.target.value as Priority)}
                    className="w-full px-3 py-2 rounded-md border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-950 text-[13px]"
                  >
                    {priorities.map((p) => <option key={p} value={p}>{t(`priority.${p}`)}</option>)}
                  </select>
                </div>
                <div className="space-y-1">
                  <label htmlFor="backlog-create-task-story" className="text-[11.5px] font-medium text-stone-500">{t('tasks.story')}</label>
                  <select
                    id="backlog-create-task-story"
                    value={newTaskStoryId}
                    onChange={(e) => setNewTaskStoryId(e.target.value)}
                    className="w-full px-3 py-2 rounded-md border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-950 text-[13px]"
                  >
                    <option value="">{t('tasks.no_story')}</option>
                    {stories.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
                  </select>
                </div>
                <div className="space-y-1">
                  <label htmlFor="backlog-create-task-assignee" className="text-[11.5px] font-medium text-stone-500">{t('tasks.assignee')}</label>
                  <select
                    id="backlog-create-task-assignee"
                    value={newTaskAssigneeId}
                    onChange={(e) => setNewTaskAssigneeId(e.target.value)}
                    className="w-full px-3 py-2 rounded-md border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-950 text-[13px]"
                  >
                    <option value="">{t('tasks.unassigned')}</option>
                    {members.map((m) => <option key={m.user_id} value={m.user_id}>{m.name}</option>)}
                  </select>
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-1">
                <button type="button" onClick={() => { setShowCreateTask(false); setNewTaskTitle(''); setNewTaskDescription(''); setNewTaskStatus('to_do'); setNewTaskPriority('medium'); setNewTaskAssigneeId(''); setNewTaskStoryId('') }} className="px-3 py-1.5 text-[12.5px] border border-stone-200 dark:border-stone-700 rounded-md text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-800">
                  {t('actions.cancel')}
                </button>
                <button type="submit" disabled={creatingTask} className="px-3 py-1.5 text-[12.5px] accent-bg rounded-md disabled:opacity-50">
                  {t('actions.create')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {editTask && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white dark:bg-stone-900 rounded-xl shadow-2xl border border-stone-200 dark:border-stone-800 p-6 max-w-md w-full mx-4">
            <h3 className="text-[15px] font-semibold mb-4">{t('actions.edit')}</h3>
            <form onSubmit={handleSaveTask} className="space-y-4">
              <input
                type="text"
                value={editTask.title}
                onChange={(e) => setEditTask({ ...editTask, title: e.target.value })}
                required
                className="w-full px-3 py-2 rounded-md border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-950 text-[13px] focus-ring"
              />
              <MarkdownEditor value={editTask.description} onChange={(v) => setEditTask({ ...editTask, description: v })} rows={3} autoExpand />
              <div className="flex justify-end gap-2">
                <button type="button" onClick={() => setEditTask(null)} className="px-3 py-1.5 text-[12.5px] border border-stone-200 dark:border-stone-700 rounded-md text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-800">
                  {t('actions.cancel')}
                </button>
                <button type="submit" disabled={savingTask} className="px-3 py-1.5 text-[12.5px] accent-bg rounded-md disabled:opacity-50">
                  {t('actions.save')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {deleteTaskId && (
        <ConfirmDialog
          title={t('actions.confirm')}
          description={`Delete task "${tasks.find(t => t.id === deleteTaskId)?.title ?? ''}"?`}
          onConfirm={async () => {
            await tasksApi.delete(deleteTaskId)
            setDeleteTaskId(null)
            await fetchTasks()
            addToast('Task deleted')
          }}
          onCancel={() => setDeleteTaskId(null)}
          confirmLabel={t('actions.delete')}
        />
      )}
    </div>
  )
}
