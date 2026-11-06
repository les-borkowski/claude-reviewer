import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { timelineApi, projectsApi } from '../services/api'
import type { TimelineTask, Priority } from '../services/api'
import { EmptyState } from '../components/common/EmptyState'

const PRIORITY_COLOURS: Record<Priority, string> = {
  low: '#6b7280',
  medium: '#3b82f6',
  high: '#ef4444',
}

const ROW_HEIGHT = 32   // px per stacked task sub-row
const LEFT_COL = 220    // px for the left title column
const DAY_WIDTH = 24    // px per day

function parseDate(s: string): Date {
  return new Date(s + 'T00:00:00')
}

function daysBetween(a: Date, b: Date): number {
  return Math.round((b.getTime() - a.getTime()) / 86400000)
}

function formatDay(d: Date, locale: string): string {
  return d.toLocaleDateString(locale, { day: 'numeric', month: 'short' })
}

interface PlacedTask {
  task: TimelineTask
  row: number       // which sub-row within the group (0-based)
  startPx: number
  widthPx: number
}

// Assign tasks to sub-rows to avoid overlap (calendar-style stacking)
function assignRows(tasks: TimelineTask[], rangeStart: Date): PlacedTask[] {
  const placed: PlacedTask[] = []
  const rowEnds: number[] = []   // rightmost pixel used in each sub-row

  for (const task of tasks) {
    const startPx = daysBetween(rangeStart, parseDate(task.bar_start)) * DAY_WIDTH
    const endPx = daysBetween(rangeStart, parseDate(task.bar_end)) * DAY_WIDTH
    const widthPx = Math.max(endPx - startPx, DAY_WIDTH)  // min 1 day wide

    let row = rowEnds.findIndex((end) => end <= startPx)
    if (row === -1) row = rowEnds.length
    rowEnds[row] = startPx + widthPx + 4  // 4px gap between bars

    placed.push({ task, row, startPx, widthPx })
  }
  return placed
}

interface Group {
  label: string
  tasks: TimelineTask[]
}

// Group tasks by sprint_id; unassigned tasks go last
function buildGroups(items: TimelineTask[]): Group[] {
  const bySprintId = new Map<string | null, TimelineTask[]>()
  for (const item of items) {
    const key = item.sprint_id
    if (!bySprintId.has(key)) bySprintId.set(key, [])
    bySprintId.get(key)!.push(item)
  }
  const groups: Group[] = []
  for (const [sprintId, tasks] of bySprintId) {
    if (sprintId !== null) {
      // Sprint name not in timeline response — label as "Sprint"
      groups.push({ label: 'Sprint', tasks })
    }
  }
  const unassigned = bySprintId.get(null)
  if (unassigned) groups.push({ label: 'Unassigned', tasks: unassigned })
  return groups
}

interface TooltipProps {
  task: TimelineTask
}

function Tooltip({ task }: TooltipProps) {
  const { t } = useTranslation()
  const sourceLabel: Record<string, string> = {
    deadline: t('timeline.source_deadline'),
    sprint: t('timeline.source_sprint'),
    status_history: t('timeline.source_history'),
  }
  return (
    <div className="absolute z-50 bottom-full mb-1 bg-stone-900 dark:bg-stone-100 text-white dark:text-stone-900 text-[11px] rounded-lg px-3 py-2 shadow-xl pointer-events-none whitespace-nowrap">
      <div className="font-medium mb-0.5">{task.title}</div>
      <div className="text-stone-300 dark:text-stone-600">{task.status} · {task.priority}</div>
      <div className="mt-0.5 opacity-70">{sourceLabel[task.source]}</div>
    </div>
  )
}

export function TimelineView({ projectId }: { projectId: string }) {
  const { t, i18n } = useTranslation()
  const locale = i18n.language || navigator.language

  const [items, setItems] = useState<TimelineTask[]>([])
  const [loading, setLoading] = useState(true)
  const [hoveredId, setHoveredId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [tlResp] = await Promise.all([
        timelineApi.get(projectId),
        projectsApi.get(projectId),
      ])
      setItems(tlResp.data)
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => { load() }, [load])

  const { rangeStart, rangeEnd, totalDays } = useMemo(() => {
    if (items.length === 0) return { rangeStart: new Date(), rangeEnd: new Date(), totalDays: 30 }
    const starts = items.map(i => parseDate(i.bar_start))
    const ends = items.map(i => parseDate(i.bar_end))
    const minD = new Date(Math.min(...starts.map(d => d.getTime())))
    const maxD = new Date(Math.max(...ends.map(d => d.getTime())))
    minD.setDate(minD.getDate() - 7)   // 7-day left padding
    maxD.setDate(maxD.getDate() + 7)   // 7-day right padding
    return { rangeStart: minD, rangeEnd: maxD, totalDays: daysBetween(minD, maxD) }
  }, [items])

  // Weekly date axis ticks
  const axisTicks: Date[] = useMemo(() => {
    const ticks: Date[] = []
    const d = new Date(rangeStart)
    while (d <= rangeEnd) {
      ticks.push(new Date(d))
      d.setDate(d.getDate() + 7)
    }
    return ticks
  }, [rangeStart, rangeEnd])

  const groups = useMemo(() => buildGroups(items), [items])

  if (loading) {
    return <div className="p-6 text-[13px] text-stone-400">Loading…</div>
  }
  if (items.length === 0) {
    return <EmptyState message={t('timeline.empty')} />
  }

  const canvasWidth = totalDays * DAY_WIDTH

  return (
    <div className="p-6">
      <h2 className="text-[15px] font-semibold mb-4">{t('timeline.title')}</h2>
      <div className="overflow-x-auto border border-stone-200 dark:border-stone-800 rounded-lg">
        <div style={{ minWidth: LEFT_COL + canvasWidth }}>
          {/* Date axis */}
          <div className="flex border-b border-stone-200 dark:border-stone-800 bg-stone-50 dark:bg-stone-900">
            <div
              style={{ width: LEFT_COL }}
              className="shrink-0 px-3 py-2 text-[10px] font-medium text-stone-400 uppercase tracking-wider"
            >
              Task
            </div>
            <div className="relative flex-1" style={{ height: 28 }}>
              {axisTicks.map((tick, i) => (
                <span
                  key={i}
                  className="absolute top-1.5 text-[10px] text-stone-400"
                  style={{ left: daysBetween(rangeStart, tick) * DAY_WIDTH }}
                >
                  {formatDay(tick, locale)}
                </span>
              ))}
            </div>
          </div>

          {/* Groups */}
          {groups.map((group, gi) => {
            const placed = assignRows(group.tasks, rangeStart)
            const rowCount = Math.max(...placed.map(p => p.row + 1), 1)
            const groupHeight = rowCount * ROW_HEIGHT

            return (
              <div key={gi} className="border-b border-stone-100 dark:border-stone-800 last:border-0">
                {/* Group label row */}
                <div className="flex items-center bg-stone-50/50 dark:bg-stone-900/50 px-3 py-1.5 border-b border-stone-100 dark:border-stone-800">
                  <span
                    className="text-[10.5px] font-semibold text-stone-500 uppercase tracking-wider"
                    style={{ width: LEFT_COL - 12 }}
                  >
                    {group.label}
                  </span>
                </div>

                {/* Title column + bar canvas */}
                <div className="flex">
                  {/* Left: task titles */}
                  <div
                    style={{ width: LEFT_COL }}
                    className="shrink-0 border-r border-stone-100 dark:border-stone-800"
                  >
                    {placed.map(({ task, row }) => (
                      <div
                        key={task.task_id}
                        className="flex items-center gap-2 px-3 text-[12px] truncate"
                        style={{ height: ROW_HEIGHT, marginTop: row === 0 ? 0 : undefined }}
                      >
                        <span
                          className="w-2 h-2 rounded-full shrink-0"
                          style={{ backgroundColor: PRIORITY_COLOURS[task.priority] }}
                        />
                        <span className="truncate">{task.title}</span>
                      </div>
                    ))}
                  </div>

                  {/* Right: bar canvas */}
                  <div
                    className="relative"
                    style={{ width: canvasWidth, height: groupHeight }}
                  >
                    {placed.map(({ task, row, startPx, widthPx }) => (
                      <div
                        key={task.task_id}
                        className="absolute flex items-center"
                        style={{
                          left: startPx,
                          top: row * ROW_HEIGHT + 6,
                          height: ROW_HEIGHT - 12,
                        }}
                        onMouseEnter={() => setHoveredId(task.task_id)}
                        onMouseLeave={() => setHoveredId(null)}
                      >
                        <div
                          className={`h-full rounded ${
                            task.source === 'status_history'
                              ? 'border-2 border-dashed'
                              : ''
                          }`}
                          style={{
                            width: widthPx,
                            backgroundColor: PRIORITY_COLOURS[task.priority] + '33',
                            borderColor:
                              task.source === 'status_history'
                                ? PRIORITY_COLOURS[task.priority]
                                : undefined,
                          }}
                        />
                        {hoveredId === task.task_id && (
                          <div className="relative">
                            <Tooltip task={task} />
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
