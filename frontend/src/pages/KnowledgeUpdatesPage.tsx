import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type {
  KnowledgeCategory,
  KnowledgePriority,
  KnowledgeUpdate,
} from '@/types'
import {
  listKnowledgeUpdates,
  markKnowledgeUpdateAsRead,
} from '@/services/knowledgeUpdateService'

type CategoryFilter = 'all' | KnowledgeCategory

const categoryLabels: Record<KnowledgeCategory, string> = {
  product: '产品知识',
  claims: '理赔服务',
  service: '客服流程',
  compliance: '合规提醒',
}

const priorityLabels: Record<KnowledgePriority, string> = {
  normal: '普通',
  important: '重要',
  urgent: '紧急',
}

const priorityStyles: Record<KnowledgePriority, string> = {
  normal:
    'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
  important:
    'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  urgent:
    'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300',
}

function formatDate(value: string | null) {
  if (!value) return '暂未设置'

  return new Date(value).toLocaleString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function KnowledgeUpdatesPage() {
  const navigate = useNavigate()
  const [updates, setUpdates] = useState<KnowledgeUpdate[]>([])
  const [activeCategory, setActiveCategory] =
    useState<CategoryFilter>('all')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function loadUpdates() {
    setLoading(true)
    setError('')

    try {
      const data = await listKnowledgeUpdates()
      setUpdates(data)
    } catch {
      setError('暂时无法获取最新知识，请稍后重试。')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadUpdates()
  }, [])

  const filteredUpdates = useMemo(() => {
    if (activeCategory === 'all') return updates

    return updates.filter(
      (item) => item.category === activeCategory,
    )
  }, [activeCategory, updates])

  const selectedUpdate =
    filteredUpdates.find((item) => item.id === selectedId) ??
    filteredUpdates[0]

  const unreadCount = updates.filter((item) => !item.is_read).length

  async function handleSelect(item: KnowledgeUpdate) {
    setSelectedId(item.id)

    if (item.is_read) return

    try {
      const readRecord = await markKnowledgeUpdateAsRead(item.id)

      setUpdates((current) =>
        current.map((update) =>
          update.id === item.id
            ? {
                ...update,
                is_read: true,
                read_at: readRecord.read_at,
              }
            : update,
        ),
      )
    } catch {
      setError('已打开知识，但阅读状态暂未同步。')
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      <header className="h-14 border-b border-[var(--border-primary)] bg-[var(--bg-secondary)] flex items-center px-6 gap-4">
        <button
          onClick={() => navigate('/chat')}
          className="text-sm text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors"
        >
          ← 返回
        </button>

        <h1 className="text-sm font-semibold text-[var(--text-primary)]">
          最新知识
        </h1>

        {unreadCount > 0 && (
          <span className="px-2 py-0.5 rounded-full bg-red-500/10 text-red-500 text-xs font-medium">
            {unreadCount} 条未读
          </span>
        )}
      </header>

      <main className="max-w-6xl mx-auto p-6">
        <div className="mb-6">
          <p className="text-2xl font-semibold text-[var(--text-primary)]">
            保险售后知识更新
          </p>
          <p className="mt-2 text-sm text-[var(--text-tertiary)]">
            及时阅读最新规则，保证客户服务口径一致。
          </p>
        </div>

        <div className="flex flex-wrap gap-2 mb-6">
          {(
            [
              ['all', '全部'],
              ['product', '产品知识'],
              ['claims', '理赔服务'],
              ['service', '客服流程'],
              ['compliance', '合规提醒'],
            ] as [CategoryFilter, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              onClick={() => {
                setActiveCategory(key)
                setSelectedId(null)
              }}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                activeCategory === key
                  ? 'bg-brand-500 text-white'
                  : 'border border-[var(--border-primary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="grid lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] gap-5">
            <div className="h-80 rounded-xl bg-[var(--bg-tertiary)] animate-pulse" />
            <div className="h-80 rounded-xl bg-[var(--bg-tertiary)] animate-pulse" />
          </div>
        ) : error ? (
          <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-5">
            <p className="text-sm text-red-500">{error}</p>
            <button
              onClick={loadUpdates}
              className="mt-3 text-sm text-brand-500 hover:text-brand-400"
            >
              重新加载
            </button>
          </div>
        ) : filteredUpdates.length === 0 ? (
          <div className="rounded-xl border border-dashed border-[var(--border-primary)] py-20 text-center">
            <p className="text-sm text-[var(--text-tertiary)]">
              当前分类下暂无已发布知识。
            </p>
          </div>
        ) : (
          <div className="grid lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] gap-5">
            <section className="space-y-3">
              {filteredUpdates.map((item) => (
                <button
                  key={item.id}
                  onClick={() => handleSelect(item)}
                  className={`w-full text-left p-4 rounded-xl border transition-colors ${
                    selectedUpdate?.id === item.id
                      ? 'border-brand-500 bg-brand-500/5'
                      : 'border-[var(--border-primary)] hover:bg-[var(--bg-secondary)]'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <span
                      className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${
                        item.is_read ? 'bg-transparent' : 'bg-red-500'
                      }`}
                    />

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-brand-500">
                          {categoryLabels[item.category]}
                        </span>
                        <span
                          className={`px-1.5 py-0.5 rounded text-xs ${
                            priorityStyles[item.priority]
                          }`}
                        >
                          {priorityLabels[item.priority]}
                        </span>
                      </div>

                      <p className="mt-2 text-sm font-medium text-[var(--text-primary)]">
                        {item.title}
                      </p>

                      {item.summary && (
                        <p className="mt-1 text-xs text-[var(--text-tertiary)] line-clamp-2">
                          {item.summary}
                        </p>
                      )}

                      <p className="mt-3 text-xs text-[var(--text-tertiary)]">
                        发布时间：{formatDate(item.published_at)}
                      </p>
                    </div>
                  </div>
                </button>
              ))}
            </section>

            {selectedUpdate && (
              <article className="rounded-xl border border-[var(--border-primary)] bg-[var(--bg-secondary)] p-6">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs text-brand-500">
                    {categoryLabels[selectedUpdate.category]}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-xs ${
                      priorityStyles[selectedUpdate.priority]
                    }`}
                  >
                    {priorityLabels[selectedUpdate.priority]}
                  </span>
                  <span className="text-xs text-[var(--text-tertiary)]">
                    版本 {selectedUpdate.version}
                  </span>
                </div>

                <h2 className="mt-4 text-xl font-semibold text-[var(--text-primary)]">
                  {selectedUpdate.title}
                </h2>

                {selectedUpdate.summary && (
                  <p className="mt-3 text-sm text-[var(--text-secondary)]">
                    {selectedUpdate.summary}
                  </p>
                )}

                <div className="my-5 border-t border-[var(--border-primary)]" />

                <p className="whitespace-pre-wrap text-sm leading-7 text-[var(--text-secondary)]">
                  {selectedUpdate.content}
                </p>

                <div className="mt-8 pt-4 border-t border-[var(--border-primary)] text-xs text-[var(--text-tertiary)] space-y-1">
                  <p>
                    生效时间：{formatDate(selectedUpdate.effective_at)}
                  </p>
                  <p>
                    发布时间：{formatDate(selectedUpdate.published_at)}
                  </p>
                  <p>
                    阅读状态：
                    {selectedUpdate.is_read ? ' 已确认阅读' : ' 打开后自动确认'}
                  </p>
                </div>
              </article>
            )}
          </div>
        )}
      </main>
    </div>
  )
}