import { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useProjects } from '../hooks/useProjects'
import { useRole } from '../hooks/useRole'
import { StatusPill } from '../components/common/StatusPill'
import { PriorityBars } from '../components/common/PriorityBars'
import { LoadMoreButton } from '../components/common/LoadMoreButton'
import { EmptyState } from '../components/common/EmptyState'
import { ConfirmDialog } from '../components/common/ConfirmDialog'
import { projectsApi } from '../services/api'
import { MarkdownEditor } from '../components/common/MarkdownEditor'
import { SkeletonCard } from '../components/common/Skeleton'
import { useToast } from '../context/ToastContext'
import { formatRelative } from '../utils/time'
import type { Status, Priority } from '../services/api'

const IPlus = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 5v14M5 12h14"/>
  </svg>
)
const STATUS_VARS: Record<string, string> = {
  to_do: '--st-todo', in_progress: '--st-prog', in_review: '--st-rev',
  in_testing: '--st-test', done: '--st-done',
}

function MiniProgress({ status }: { status: string }) {
  const doneW = status === 'done' ? 100 : status === 'in_testing' ? 80 : status === 'in_review' ? 55 : status === 'in_progress' ? 35 : 0
  const progW = status === 'in_progress' ? 35 : status === 'in_review' ? 20 : status === 'in_testing' ? 10 : 0
  const revW  = status === 'in_review' ? 15 : status === 'in_testing' ? 5 : 0
  const testW = status === 'in_testing' ? 5 : 0
  const todoW = Math.max(0, 100 - doneW - progW - revW - testW)

  const segs = [
    { v: '--st-todo', w: todoW },
    { v: '--st-prog', w: progW },
    { v: '--st-rev',  w: revW },
    { v: '--st-test', w: testW },
    { v: '--st-done', w: doneW },
  ].filter(s => s.w > 0)

  return (
    <div className="mt-3 flex h-1.5 rounded-full overflow-hidden bg-stone-100 dark:bg-stone-800">
      {segs.map((s, i) => (
        <span key={i} style={{ width: `${s.w}%`, background: `var(${s.v})` }} />
      ))}
    </div>
  )
}

export function ProjectsPage() {
  const { t } = useTranslation()
  const { isManager } = useRole()
  const { addToast } = useToast()

  const [statusFilter, setStatusFilter] = useState<Status | ''>('')
  const [priorityFilter, setPriorityFilter] = useState<Priority | ''>('')
  const [archived, setArchived] = useState(false)
  const [search, setSearch] = useState('')

  const { items, nextCursor, isLoading, initialized, refresh, loadMore } = useProjects({
    status: statusFilter,
    priority: priorityFilter,
    archived,
    q: search,
  })

  const location = useLocation()
  useEffect(() => {
    if ((location.state as { modal?: string } | null)?.modal === 'create-project') {
      setShowCreate(true)
      window.history.replaceState({}, '')
    }
  }, [location.state])

  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [creating, setCreating] = useState(false)

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    try {
      await projectsApi.create({ name: newName, description: newDesc || undefined })
      setShowCreate(false)
      setNewName('')
      setNewDesc('')
      refresh()
      addToast('Project created')
    } finally {
      setCreating(false)
    }
  }

  const [deleteId, setDeleteId] = useState<string | null>(null)
  const handleDelete = async () => {
    if (!deleteId) return
    await projectsApi.delete(deleteId)
    setDeleteId(null)
    refresh()
    addToast('Project deleted')
  }

  const [editProject, setEditProject] = useState<{ id: string; name: string; description: string } | null>(null)
  const [saving, setSaving] = useState(false)
  const handleEditSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editProject) return
    setSaving(true)
    try {
      await projectsApi.update(editProject.id, { name: editProject.name, description: editProject.description || undefined })
      setEditProject(null)
      refresh()
      addToast('Project updated')
    } finally {
      setSaving(false)
    }
  }

  const statuses: Status[] = ['to_do', 'in_progress', 'in_review', 'in_testing', 'done']
  const priorities: Priority[] = ['low', 'medium', 'high']

  return (
    <div className="flex-1 flex flex-col">
      {/* Page header */}
      <div className="px-7 pt-6 pb-4 border-b border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-950">
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-[22px] font-semibold tracking-tight">{t('projects.title')}</h1>
            {initialized && (
              <p className="text-[13px] text-stone-500 mt-0.5">{items.length} {archived ? t('projects.archived_label') : t('projects.active')}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as Status | '')}
                className="text-[12px] px-2.5 py-1.5 rounded-md border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 text-stone-700 dark:text-stone-300"
              >
                <option value="">{t('filter.status')}: {t('filter.all')}</option>
                {statuses.map((s) => (
                  <option key={s} value={s}>{t(`status.${s}`)}</option>
                ))}
              </select>
              <select
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value as Priority | '')}
                className="text-[12px] px-2.5 py-1.5 rounded-md border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 text-stone-700 dark:text-stone-300"
              >
                <option value="">{t('filter.priority')}: {t('filter.all')}</option>
                {priorities.map((p) => (
                  <option key={p} value={p}>{t(`priority.${p}`)}</option>
                ))}
              </select>
              <label className="flex items-center gap-1.5 text-[12px] text-stone-600 dark:text-stone-300 px-2.5 py-1.5 rounded-md border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 cursor-pointer">
                <input
                  type="checkbox"
                  checked={archived}
                  onChange={(e) => setArchived(e.target.checked)}
                  className="rounded"
                />
                {t('projects.archived')}
              </label>
              <input
                type="text"
                placeholder={t('filter.search')}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="text-[12px] px-2.5 py-1.5 rounded-md border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 text-stone-700 dark:text-stone-300 min-w-[160px] focus-ring"
              />
            </div>
            {isManager && (
              <button
                onClick={() => setShowCreate(true)}
                className="px-2.5 py-1.5 text-[12px] rounded-md accent-bg inline-flex items-center gap-1.5"
              >
                <IPlus /> {t('projects.create')}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Grid */}
      <div className="px-7 py-5 flex-1">
        {!initialized ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            message={t('projects.empty')}
            action={isManager ? { label: t('projects.create'), onClick: () => setShowCreate(true) } : undefined}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {items.map((project) => (
              <div
                key={project.id}
                className="group lift bg-white dark:bg-stone-900 rounded-xl border border-stone-200 dark:border-stone-800 p-4 flex flex-col hover:border-stone-300 dark:hover:border-stone-700"
              >
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span
                    className="inline-block w-2.5 h-2.5 rounded-full"
                    style={{ background: `var(${STATUS_VARS[project.status] ?? '--st-todo'})` }}
                  />
                  <StatusPill status={project.status} />
                  {project.archived_at && (
                    <span className="inline-flex px-2 py-0.5 rounded-full text-[10px] font-medium bg-stone-100 dark:bg-stone-800 text-stone-500">{t('board.archived')}</span>
                  )}
                  <span className="flex-1" />
                  {isManager && (
                    <div className="flex gap-2 opacity-0 group-hover:opacity-100">
                      <button
                        onClick={() => setEditProject({ id: project.id, name: project.name, description: project.description ?? '' })}
                        className="text-[11px] text-stone-400 hover:text-stone-700 dark:hover:text-stone-200"
                      >
                        {t('actions.edit')}
                      </button>
                      <button
                        onClick={() => setDeleteId(project.id)}
                        className="text-[11px] text-rose-400 hover:text-rose-600"
                      >
                        {t('actions.delete')}
                      </button>
                    </div>
                  )}
                </div>
                <Link to={`/projects/${project.id}`} className="block">
                  <div className="text-[15px] font-semibold tracking-tight hover:accent-text transition-colors">{project.name}</div>
                  {project.description && (
                    <p className="text-[12.5px] text-stone-500 dark:text-stone-400 mt-0.5 line-clamp-2">{project.description}</p>
                  )}
                </Link>
                <MiniProgress status={project.status} />
                <div className="mt-3 flex items-center justify-between">
                  <PriorityBars priority={project.priority} withLabel />
                  <div className="flex items-center gap-3 text-[11px] text-stone-400">
                    <span>{formatRelative(project.created_at)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {nextCursor && <LoadMoreButton onLoadMore={loadMore} isLoading={isLoading} />}
      </div>

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white dark:bg-stone-900 rounded-xl shadow-2xl border border-stone-200 dark:border-stone-800 p-6 max-w-md w-full mx-4">
            <h3 className="text-[15px] font-semibold mb-4">{t('projects.create')}</h3>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-[11px] uppercase tracking-wider text-stone-400 font-medium mb-1">{t('projects.name')}</label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  required
                  className="w-full px-3 py-2 rounded-md border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-950 text-[13px] focus-ring"
                />
              </div>
              <div>
                <label className="block text-[11px] uppercase tracking-wider text-stone-400 font-medium mb-1">{t('projects.description')}</label>
                <MarkdownEditor value={newDesc} onChange={setNewDesc} rows={3} autoExpand />
              </div>
              <div className="flex justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="px-3 py-1.5 text-[12.5px] border border-stone-200 dark:border-stone-700 rounded-md text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-800"
                >
                  {t('actions.cancel')}
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-3 py-1.5 text-[12.5px] accent-bg rounded-md disabled:opacity-50"
                >
                  {t('actions.create')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit modal */}
      {editProject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white dark:bg-stone-900 rounded-xl shadow-2xl border border-stone-200 dark:border-stone-800 p-6 max-w-md w-full mx-4">
            <h3 className="text-[15px] font-semibold mb-4">{t('actions.edit')}</h3>
            <form onSubmit={handleEditSave} className="space-y-4">
              <div>
                <label className="block text-[11px] uppercase tracking-wider text-stone-400 font-medium mb-1">{t('projects.name')}</label>
                <input
                  type="text"
                  value={editProject.name}
                  onChange={(e) => setEditProject({ ...editProject, name: e.target.value })}
                  required
                  className="w-full px-3 py-2 rounded-md border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-950 text-[13px] focus-ring"
                />
              </div>
              <div>
                <label className="block text-[11px] uppercase tracking-wider text-stone-400 font-medium mb-1">{t('projects.description')}</label>
                <MarkdownEditor value={editProject.description} onChange={(v) => setEditProject({ ...editProject, description: v })} rows={3} autoExpand />
              </div>
              <div className="flex justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setEditProject(null)}
                  className="px-3 py-1.5 text-[12.5px] border border-stone-200 dark:border-stone-700 rounded-md text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-800"
                >
                  {t('actions.cancel')}
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-3 py-1.5 text-[12.5px] accent-bg rounded-md disabled:opacity-50"
                >
                  {t('actions.save')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete confirm */}
      {deleteId && (
        <ConfirmDialog
          title={t('actions.confirm')}
          description={t('actions.delete') + ' project?'}
          onConfirm={handleDelete}
          onCancel={() => setDeleteId(null)}
          confirmLabel={t('actions.delete')}
        />
      )}
    </div>
  )
}
