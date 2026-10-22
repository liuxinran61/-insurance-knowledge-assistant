import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import type {
  KnowledgeCategory,
  KnowledgePriority,
  KnowledgeUpdate,
  KnowledgeUpdatePayload,
} from '@/types'
import {
  createKnowledgeUpdate,
  listAdminKnowledgeUpdates,
  publishKnowledgeUpdate,
  updateKnowledgeUpdate,
} from '@/services/knowledgeUpdateService'

const statusLabels = {
  draft: '草稿',
  published: '已发布',
  archived: '已归档',
}

const statusColors = {
  draft: 'bg-amber-500/10 text-amber-600',
  published: 'bg-emerald-500/10 text-emerald-600',
  archived: 'bg-slate-500/10 text-slate-500',
}

const categoryOptions: Array<{ value: KnowledgeCategory; label: string }> = [
  { value: 'product', label: '产品知识' },
  { value: 'claims', label: '理赔服务' },
  { value: 'service', label: '客服流程' },
  { value: 'compliance', label: '合规提醒' },
]

const priorityOptions: Array<{ value: KnowledgePriority; label: string }> = [
  { value: 'normal', label: '普通' },
  { value: 'important', label: '重要' },
  { value: 'urgent', label: '紧急' },
]

type UpdateForm = {
  title: string
  summary: string
  content: string
  category: KnowledgeCategory
  priority: KnowledgePriority
  version: string
  effective_at: string
}

const emptyForm: UpdateForm = {
  title: '',
  summary: '',
  content: '',
  category: 'service',
  priority: 'normal',
  version: '1.0',
  effective_at: '',
}

function updateToForm(item: KnowledgeUpdate): UpdateForm {
  return {
    title: item.title,
    summary: item.summary ?? '',
    content: item.content,
    category: item.category,
    priority: item.priority,
    version: item.version,
    effective_at: item.effective_at
      ? new Date(item.effective_at).toISOString().slice(0, 16)
      : '',
  }
}

export default function KnowledgeUpdateManagePage() {
  const navigate = useNavigate()
  const { user } = useAuth()

  const [updates, setUpdates] = useState<KnowledgeUpdate[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [form, setForm] = useState<UpdateForm>(emptyForm)
  const [saving, setSaving] = useState(false)

  async function loadUpdates() {
    setError('')

    try {
      const data = await listAdminKnowledgeUpdates()
      setUpdates(data)
      setSelectedId((currentId) => {
        const nextId = currentId ?? data[0]?.id ?? null
        const nextItem = data.find((item) => item.id === nextId)
        setForm(nextItem ? updateToForm(nextItem) : emptyForm)
        return nextId
      })
    } catch {
      setError('加载知识更新失败，请稍后重试。')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadUpdates()
  }, [])

  const selectedUpdate = updates.find((item) => item.id === selectedId) ?? null
  const canEdit = !selectedUpdate || selectedUpdate.status === 'draft'

  function selectUpdate(item: KnowledgeUpdate) {
    setSelectedId(item.id)
    setForm(updateToForm(item))
    setError('')
    setNotice('')
  }

  function startNewDraft() {
    setSelectedId(null)
    setForm(emptyForm)
    setError('')
    setNotice('')
  }

  function toPayload(): KnowledgeUpdatePayload {
    return {
      title: form.title.trim(),
      summary: form.summary.trim() || null,
      content: form.content.trim(),
      category: form.category,
      priority: form.priority,
      version: form.version.trim() || '1.0',
      effective_at: form.effective_at
        ? new Date(form.effective_at).toISOString()
        : null,
    }
  }

  async function saveDraft() {
    const payload = toPayload()
    if (!payload.title || !payload.content) {
      setError('请填写标题和正文后再保存。')
      return
    }

    setSaving(true)
    setError('')
    try {
      const saved = selectedUpdate
        ? await updateKnowledgeUpdate(selectedUpdate.id, payload)
        : await createKnowledgeUpdate(payload)

      setUpdates((current) => {
        const exists = current.some((item) => item.id === saved.id)
        return exists
          ? current.map((item) => (item.id === saved.id ? saved : item))
          : [saved, ...current]
      })
      setSelectedId(saved.id)
      setForm(updateToForm(saved))
      setNotice('草稿已保存。确认内容无误后即可发布。')
    } catch {
      setError('保存草稿失败，请检查管理员权限和网络后重试。')
    } finally {
      setSaving(false)
    }
  }

  async function publishDraft() {
    if (!selectedUpdate || selectedUpdate.status !== 'draft') return

    const payload = toPayload()
    if (!payload.title || !payload.content) {
      setError('请填写标题和正文后再发布。')
      return
    }

    setSaving(true)
    setError('')
    setNotice('')
    try {
      // 发布前先保存当前表单，避免管理员编辑后直接发布时丢失修改。
      const saved = await updateKnowledgeUpdate(selectedUpdate.id, payload)
      const published = await publishKnowledgeUpdate(saved.id)
      setUpdates((current) =>
        current.map((item) => (item.id === published.id ? published : item)),
      )
      setForm(updateToForm(published))
      setNotice('知识更新已发布，客服现在可以在“最新知识”中查看。')
    } catch {
      setError('发布失败，请稍后重试。')
    } finally {
      setSaving(false)
    }
  }

  if (!user?.is_superuser) {
    return (
      <div className="min-h-screen bg-[var(--bg-primary)] grid place-items-center p-6">
        <div className="text-center">
          <p className="text-sm text-[var(--text-secondary)]">
            该页面仅供知识运营管理员使用。
          </p>
          <button
            onClick={() => navigate('/chat')}
            className="mt-4 text-sm text-brand-500 hover:text-brand-600"
          >
            返回智能问答
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      <header className="h-14 border-b border-[var(--border-primary)] bg-[var(--bg-secondary)] flex items-center px-6 gap-4">
        <button
          onClick={() => navigate('/chat')}
          className="text-sm text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
        >
          ← 返回
        </button>
        <h1 className="text-sm font-semibold text-[var(--text-primary)]">
          知识更新管理
        </h1>
      </header>

      <main className="max-w-6xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-6">
        <section className="rounded-xl border border-[var(--border-primary)] bg-[var(--bg-secondary)] overflow-hidden">
          <div className="px-4 py-3 border-b border-[var(--border-primary)]">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-medium text-[var(--text-primary)]">
                全部更新 ({updates.length})
              </h2>
              <button
                onClick={startNewDraft}
                className="rounded-lg bg-brand-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-600"
              >
                新建草稿
              </button>
            </div>
          </div>

          {loading ? (
            <p className="p-4 text-sm text-[var(--text-tertiary)]">加载中…</p>
          ) : error ? (
            <p className="p-4 text-sm text-[var(--color-error)]">{error}</p>
          ) : updates.length === 0 ? (
            <p className="p-4 text-sm text-[var(--text-tertiary)]">
              暂无知识更新。
            </p>
          ) : (
            <div className="divide-y divide-[var(--border-secondary)]">
              {updates.map((item) => (
                <button
                  key={item.id}
                  onClick={() => selectUpdate(item)}
                  className={`w-full text-left p-4 transition-colors ${
                    selectedId === item.id
                      ? 'bg-brand-500/10'
                      : 'hover:bg-[var(--bg-tertiary)]'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium text-[var(--text-primary)] line-clamp-2">
                      {item.title}
                    </p>
                    <span className={`shrink-0 rounded px-2 py-0.5 text-xs ${statusColors[item.status]}`}>
                      {statusLabels[item.status]}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-[var(--text-tertiary)]">
                    v{item.version} · {new Date(item.updated_at).toLocaleString('zh-CN')}
                  </p>
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="rounded-xl border border-[var(--border-primary)] bg-[var(--bg-secondary)] min-h-80 p-6">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[var(--border-primary)] pb-4">
            <div>
              <p className="text-base font-semibold text-[var(--text-primary)]">
                {selectedUpdate ? '编辑知识更新' : '新建知识更新草稿'}
              </p>
              <p className="mt-1 text-xs text-[var(--text-tertiary)]">
                {selectedUpdate
                  ? `当前状态：${statusLabels[selectedUpdate.status]}`
                  : '保存后仍为草稿，发布后才会对客服可见。'}
              </p>
            </div>

            {selectedUpdate?.status === 'draft' && (
              <button
                onClick={publishDraft}
                disabled={saving}
                className="rounded-lg border border-brand-500 px-3 py-2 text-sm font-medium text-brand-500 hover:bg-brand-500/10 disabled:cursor-not-allowed disabled:opacity-50"
              >
                发布更新
              </button>
            )}
          </div>

          {error && (
            <p className="mt-4 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-500">
              {error}
            </p>
          )}

          {notice && (
            <p className="mt-4 rounded-lg bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700">
              {notice}
            </p>
          )}

          {!canEdit && (
            <p className="mt-4 rounded-lg bg-amber-500/10 px-3 py-2 text-sm text-amber-600">
              已发布内容不可直接修改。请新建一条更新，保留规则版本记录。
            </p>
          )}

          <div className="mt-5 grid gap-4">
            <label className="grid gap-1.5 text-sm text-[var(--text-secondary)]">
              标题
              <input
                value={form.title}
                disabled={!canEdit || saving}
                onChange={(event) => setForm({ ...form, title: event.target.value })}
                placeholder="例如：车险理赔材料规则调整"
                className="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] px-3 py-2 text-[var(--text-primary)] outline-none focus:border-brand-500 disabled:cursor-not-allowed disabled:opacity-60"
              />
            </label>

            <label className="grid gap-1.5 text-sm text-[var(--text-secondary)]">
              摘要
              <input
                value={form.summary}
                disabled={!canEdit || saving}
                onChange={(event) => setForm({ ...form, summary: event.target.value })}
                placeholder="给客服快速理解的一句话说明"
                className="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] px-3 py-2 text-[var(--text-primary)] outline-none focus:border-brand-500 disabled:cursor-not-allowed disabled:opacity-60"
              />
            </label>

            <div className="grid gap-4 sm:grid-cols-3">
              <label className="grid gap-1.5 text-sm text-[var(--text-secondary)]">
                分类
                <select
                  value={form.category}
                  disabled={!canEdit || saving}
                  onChange={(event) => setForm({ ...form, category: event.target.value as KnowledgeCategory })}
                  className="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] px-3 py-2 text-[var(--text-primary)] outline-none focus:border-brand-500 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {categoryOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </label>

              <label className="grid gap-1.5 text-sm text-[var(--text-secondary)]">
                优先级
                <select
                  value={form.priority}
                  disabled={!canEdit || saving}
                  onChange={(event) => setForm({ ...form, priority: event.target.value as KnowledgePriority })}
                  className="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] px-3 py-2 text-[var(--text-primary)] outline-none focus:border-brand-500 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {priorityOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </label>

              <label className="grid gap-1.5 text-sm text-[var(--text-secondary)]">
                版本号
                <input
                  value={form.version}
                  disabled={!canEdit || saving}
                  onChange={(event) => setForm({ ...form, version: event.target.value })}
                  className="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] px-3 py-2 text-[var(--text-primary)] outline-none focus:border-brand-500 disabled:cursor-not-allowed disabled:opacity-60"
                />
              </label>
            </div>

            <label className="grid gap-1.5 text-sm text-[var(--text-secondary)]">
              生效时间（可选）
              <input
                type="datetime-local"
                value={form.effective_at}
                disabled={!canEdit || saving}
                onChange={(event) => setForm({ ...form, effective_at: event.target.value })}
                className="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] px-3 py-2 text-[var(--text-primary)] outline-none focus:border-brand-500 disabled:cursor-not-allowed disabled:opacity-60"
              />
            </label>

            <label className="grid gap-1.5 text-sm text-[var(--text-secondary)]">
              正文
              <textarea
                rows={10}
                value={form.content}
                disabled={!canEdit || saving}
                onChange={(event) => setForm({ ...form, content: event.target.value })}
                placeholder="说明变更内容、适用范围、客服口径和需要提醒客户的事项。"
                className="resize-y rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] px-3 py-2 text-[var(--text-primary)] outline-none focus:border-brand-500 disabled:cursor-not-allowed disabled:opacity-60"
              />
            </label>

            {canEdit && (
              <div className="flex justify-end">
                <button
                  onClick={saveDraft}
                  disabled={saving}
                  className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {saving ? '保存中…' : '保存草稿'}
                </button>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  )
}
