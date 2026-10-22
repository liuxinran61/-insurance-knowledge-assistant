import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { IconActivity, IconRefresh } from '@/components/ui/Icons'
import { runKnowledgeOpsAgent } from '@/services/knowledgeOpsService'
import type { KnowledgeOpsRunResult } from '@/types'

const DEFAULT_QUERY = '请检查知识库运行情况'

function formatStepResult(result: Record<string, unknown>): string {
  if ('total_documents' in result) {
    const statuses = result.status_counts as Record<string, number> | undefined
    const readyCount = statuses?.ready ?? 0
    const failed = result.failed_documents as unknown[] | undefined
    return `文档共 ${result.total_documents} 份，其中 ${readyCount} 份已就绪，失败 ${failed?.length ?? 0} 份。`
  }

  if ('published_count' in result) {
    return `已发布更新 ${result.published_count} 条，未读 ${result.unread_count} 条。`
  }

  if ('total_calls' in result) {
    return `近 ${result.window_hours} 小时调用 ${result.total_calls} 次，失败 ${result.failed_calls} 次，平均耗时 ${result.avg_latency_ms} ms。`
  }

  if ('error' in result) {
    return `执行失败：${String(result.error)}`
  }

  return JSON.stringify(result, null, 2)
}

export default function KnowledgeOpsPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [query, setQuery] = useState(DEFAULT_QUERY)
  const [result, setResult] = useState<KnowledgeOpsRunResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleRun() {
    const trimmedQuery = query.trim()
    if (!trimmedQuery) {
      setError('请输入巡检任务。')
      return
    }

    setLoading(true)
    setError('')
    try {
      const nextResult = await runKnowledgeOpsAgent(trimmedQuery)
      setResult(nextResult)
    } catch {
      setError('巡检运行失败，请确认管理员权限、后端服务和模型配置。')
    } finally {
      setLoading(false)
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
        <div className="flex items-center gap-2">
          <IconActivity className="text-brand-500" />
          <h1 className="text-sm font-semibold text-[var(--text-primary)]">
            知识运营巡检
          </h1>
        </div>
      </header>

      <main className="max-w-5xl mx-auto p-6 space-y-6">
        <section className="rounded-xl border border-[var(--border-primary)] bg-[var(--bg-secondary)] p-5">
          <div className="flex items-start justify-between gap-4 mb-4">
            <div>
              <h2 className="text-base font-semibold text-[var(--text-primary)]">
                发起只读运营巡检
              </h2>
              <p className="mt-1 text-sm text-[var(--text-tertiary)]">
                Agent 会规划任务、检查文档与知识更新状态，并生成运行报告。
              </p>
            </div>
            <span className="shrink-0 rounded-full bg-brand-500/10 px-2.5 py-1 text-xs text-brand-600">
              管理员工具
            </span>
          </div>

          <textarea
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            rows={3}
            disabled={loading}
            className="w-full resize-y rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] p-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 disabled:opacity-60"
            placeholder="例如：请检查知识库运行情况"
          />

          {error && (
            <p className="mt-3 text-sm text-[var(--color-error)]">{error}</p>
          )}

          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={handleRun}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <IconRefresh className={loading ? 'animate-spin' : ''} />
              {loading ? 'Agent 正在巡检…' : '开始巡检'}
            </button>
            {loading && (
              <p className="text-xs text-[var(--text-tertiary)]">
                正在规划、查询并生成报告，通常需要十几秒。
              </p>
            )}
          </div>
        </section>

        {result && (
          <>
            <section className="rounded-xl border border-[var(--border-primary)] bg-[var(--bg-secondary)] p-5">
              <div className="flex items-center justify-between gap-3 mb-4">
                <h2 className="text-base font-semibold text-[var(--text-primary)]">
                  运营报告
                </h2>
                <span className="text-xs text-[var(--text-tertiary)]">
                  会话 {result.session_id.slice(-8)}
                </span>
              </div>
              <article className="whitespace-pre-wrap text-sm leading-7 text-[var(--text-secondary)]">
                {result.response}
              </article>
            </section>

            <section className="rounded-xl border border-[var(--border-primary)] bg-[var(--bg-secondary)] overflow-hidden">
              <div className="px-5 py-4 border-b border-[var(--border-primary)]">
                <h2 className="text-base font-semibold text-[var(--text-primary)]">
                  Agent 执行轨迹
                </h2>
              </div>
              <ol className="divide-y divide-[var(--border-secondary)]">
                {result.steps.map((step, index) => (
                  <li key={`${step.step_id}-${index}`} className="p-5 flex gap-4">
                    <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-brand-500/10 text-xs font-semibold text-brand-600">
                      {index + 1}
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-[var(--text-primary)]">
                        {step.task}
                      </p>
                      <p className="mt-1 text-xs text-[var(--text-tertiary)]">
                        工具：{step.tool_name}
                      </p>
                      <p className="mt-2 text-sm text-[var(--text-secondary)]">
                        {formatStepResult(step.result)}
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
            </section>

            {result.errors.length > 0 && (
              <section className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-5">
                <h2 className="text-sm font-medium text-amber-700">执行提醒</h2>
                <ul className="mt-2 list-disc pl-5 text-sm text-amber-700 space-y-1">
                  {result.errors.map((item, index) => <li key={index}>{item}</li>)}
                </ul>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  )
}
