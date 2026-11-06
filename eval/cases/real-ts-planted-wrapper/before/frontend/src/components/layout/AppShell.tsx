import { useEffect, useState } from 'react'
import { NavLink, useNavigate, useLocation, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../context/AuthContext'
import { invitationsApi, projectsApi, recentApi } from '../../services/api'
import type { ProjectResponse, RecentItemResponse } from '../../services/api'

const ISearch = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>
  </svg>
)
const IPlus = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 5v14M5 12h14"/>
  </svg>
)
const IHome = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
    <path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10"/>
  </svg>
)
const IInbox = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
    <path d="M3 13h5l1 3h6l1-3h5"/><path d="M3 13l3-8h12l3 8v6H3z"/>
  </svg>
)
const ICog = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
    <circle cx="12" cy="12" r="3"/>
    <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1A2 2 0 1 1 4.3 17l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>
  </svg>
)
const ICaret = () => (
  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="m6 9 6 6 6-6"/>
  </svg>
)
const IFolder = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
  </svg>
)
const IDoc = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <path d="M14 2v6h6M8 13h8M8 17h5"/>
  </svg>
)
const ICheck = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M20 6 9 17l-5-5"/>
  </svg>
)

const recentIcon = (type: RecentItemResponse['type']) => {
  if (type === 'project') return <IFolder />
  if (type === 'story') return <IDoc />
  return <ICheck />
}

const recentLink = (item: RecentItemResponse): string => {
  if (item.type === 'project') return `/projects/${item.id}`
  if (item.type === 'story') return `/projects/${item.project_id}/stories/${item.id}`
  if (item.story_id) return `/stories/${item.story_id}/tasks/${item.id}`
  return `/projects/${item.project_id}`
}

const SUB_ITEM = 'flex items-center gap-2 pl-8 pr-2 py-1 text-[12.5px] rounded-md truncate text-stone-500 dark:text-stone-400 hover:bg-stone-50 dark:hover:bg-stone-900 hover:text-stone-800 dark:hover:text-stone-200'
const SUB_ITEM_ACTIVE = 'flex items-center gap-2 pl-8 pr-2 py-1 text-[12.5px] rounded-md truncate bg-stone-100 dark:bg-stone-900 text-stone-900 dark:text-stone-100'

interface Props {
  children: React.ReactNode
}

export function AppShell({ children }: Props) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const { t } = useTranslation()
  const [pendingCount, setPendingCount] = useState(0)
  const [menuOpen, setMenuOpen] = useState(false)
  const [recentProjects, setRecentProjects] = useState<ProjectResponse[]>([])
  const [hasMoreProjects, setHasMoreProjects] = useState(false)
  const [recentItems, setRecentItems] = useState<RecentItemResponse[]>([])
  const initials = user?.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase() ?? '?'

  useEffect(() => {
    invitationsApi.mine().then((res) => {
      setPendingCount(res.data.filter(i => i.status === 'pending').length)
    }).catch(() => {})

    projectsApi.list({ limit: 6 }).then((res) => {
      const items = res.data.items
      const hasMore = items.length === 6
      setHasMoreProjects(hasMore)
      setRecentProjects(items.slice(0, hasMore ? 4 : 5))
    }).catch(() => {})

    recentApi.list().then((res) => {
      setRecentItems(res.data)
    }).catch(() => {})
  }, [])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const projectsActive = location.pathname === '/projects'

  return (
    <div className="flex min-h-screen bg-stone-50 dark:bg-stone-950 text-stone-900 dark:text-stone-100">
      {/* Sidebar */}
      <aside className="w-[240px] shrink-0 border-r border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-950 flex flex-col h-screen sticky top-0">

        {/* Scrollable zone: workspace + search + nav */}
        <div className="flex-1 overflow-y-auto min-h-0 flex flex-col">
          {/* Workspace */}
          <div className="px-3 py-3 border-b border-stone-200 dark:border-stone-800 shrink-0">
            <Link to="/projects" className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-stone-50 dark:hover:bg-stone-900">
              <span className="w-6 h-6 rounded-md accent-bg flex items-center justify-center text-[11px] font-semibold">SP</span>
              <span className="flex-1 min-w-0">
                <span className="block text-[13px] font-semibold leading-tight">{t('shell.workspace')}</span>
              </span>
            </Link>
          </div>

          {/* Search stub */}
          <div className="px-3 pt-3 shrink-0">
            <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-md border border-stone-200 dark:border-stone-800 text-stone-400 text-[12px]">
              <ISearch />
              <span className="flex-1 text-left">{t('shell.search')}</span>
            </div>
          </div>

          {/* Primary nav */}
          <nav className="px-2 py-3 space-y-0.5 text-[13px]">

            {/* Recent Work */}
            {recentItems.length > 0 && (
              <div className="mb-1">
                <div className="flex items-center gap-2.5 px-2 py-1.5 text-stone-600 dark:text-stone-300 select-none">
                  <span className="flex-1">{t('nav.recent_work')}</span>
                </div>
                {recentItems.map(item => (
                  <Link
                    key={`${item.type}-${item.id}`}
                    to={recentLink(item)}
                    className={SUB_ITEM}
                  >
                    <span className="text-stone-400 shrink-0">{recentIcon(item.type)}</span>
                    <span className="truncate">{item.title}</span>
                  </Link>
                ))}
              </div>
            )}

            {/* Projects */}
            <div className="mb-1">
              <div className={`flex items-center gap-2.5 px-2 py-1.5 rounded-md ${projectsActive ? 'text-stone-900 dark:text-stone-100 font-medium' : 'text-stone-600 dark:text-stone-300'}`}>
                <span className="text-stone-400"><IHome /></span>
                <span className="flex-1">{t('nav.projects')}</span>
                <Link
                  to="/projects"
                  className="text-stone-400 hover:text-stone-700 dark:hover:text-stone-200 p-0.5 rounded"
                  aria-label="New project"
                >
                  <IPlus />
                </Link>
              </div>
              {recentProjects.map(project => (
                <NavLink
                  key={project.id}
                  to={`/projects/${project.id}`}
                  className={({ isActive }) => isActive ? SUB_ITEM_ACTIVE : SUB_ITEM}
                >
                  <span className="truncate">{project.name}</span>
                </NavLink>
              ))}
              {hasMoreProjects && (
                <Link to="/projects" className={SUB_ITEM}>
                  {t('nav.all_projects')} →
                </Link>
              )}
            </div>

            {/* Invitations */}
            <NavLink
              to="/invitations"
              className={({ isActive }) =>
                `w-full flex items-center gap-2.5 px-2 py-1.5 rounded-md ${isActive ? 'bg-stone-100 dark:bg-stone-900 text-stone-900 dark:text-stone-100' : 'text-stone-600 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-900'}`
              }
            >
              <span className="text-stone-400"><IInbox /></span>
              <span className={pendingCount > 0 ? 'font-semibold' : ''}>
                {t('nav.invitations')}{pendingCount > 0 ? ` (${pendingCount})` : ''}
              </span>
            </NavLink>

          </nav>
        </div>

        {/* Footer — always visible at bottom of viewport */}
        <div className="border-t border-stone-200 dark:border-stone-800 p-2 space-y-0.5 shrink-0">
          <NavLink
            to="/config"
            className={({ isActive }) =>
              `w-full flex items-center gap-2.5 px-2 py-1.5 rounded-md text-[13px] ${isActive ? 'bg-stone-100 dark:bg-stone-900' : 'text-stone-600 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-900'}`
            }
          >
            <span className="text-stone-400"><ICog /></span>
            <span>{t('nav.settings')}</span>
          </NavLink>

          <div className="relative">
            <button
              onClick={() => setMenuOpen(o => !o)}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-stone-50 dark:hover:bg-stone-900"
            >
              <span className="w-6 h-6 rounded-full av-2 inline-flex items-center justify-center text-white text-[9.5px] font-semibold">
                {initials}
              </span>
              <span className="flex-1 min-w-0 text-left">
                <span className="block text-[12px] font-medium leading-tight truncate text-stone-800 dark:text-stone-100">{user?.name}</span>
                <span className="block text-[10.5px] text-stone-500 leading-tight capitalize">{user?.role}</span>
              </span>
              <span className="text-stone-400"><ICaret /></span>
            </button>
            {menuOpen && (
              <div className="absolute bottom-full left-0 right-0 mb-1 bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-800 rounded-md shadow-lg z-50 overflow-hidden">
                <Link
                  to="/config"
                  onClick={() => setMenuOpen(false)}
                  className="flex items-center gap-2 px-3 py-2 text-[12.5px] text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-800"
                >
                  <ICog /> {t('nav.settings')}
                </Link>
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2 px-3 py-2 text-[12.5px] text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-800"
                >
                  <IPlus /> {t('shell.sign_out')}
                </button>
              </div>
            )}
          </div>
        </div>

      </aside>

      {/* Main content */}
      <main className="flex-1 min-w-0 flex flex-col min-h-screen">
        {children}
      </main>
    </div>
  )
}
